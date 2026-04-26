import io
from collections import deque
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import selectinload

from app import database as db
from app.models import AlarmSession, DifficultyModel, SleepSession
from app.utils import as_utc, minutes_after_midnight, safe_avg

MODEL_RETRAIN_AFTER_DAYS = 7
MIN_TRAINING_SAMPLES = 10

feature_names = [
    # Context
    "alarm_time_minutes",
    "day_of_week",
    # Sleep data
    "avg_sleep_hours_last_3",
    "avg_sleep_quality_last_3",
    "avg_sleep_efficiency_last_3",
    "num_sleep_days_used",
    "sleep_data_age_days",
    # Behaviour (recent)
    "avg_snoozes_last_10",
    "avg_puzzle_time_last_10",
    "avg_attempts_last_10",
    # Behaviour (context)
    "avg_snoozes_same_day",
    "avg_snoozes_same_time",
    "avg_puzzle_time_same_day",
    "avg_puzzle_time_same_time",
]


def _session_metrics(session: AlarmSession) -> dict[str, float]:
    """Compute attempts/snoozes/average puzzle time metrics for an alarm session."""
    attempts = len(session.puzzle_sessions)
    avg_puzzle_time = safe_avg(
        [float(p.time_taken_seconds) for p in session.puzzle_sessions]
    )
    return {
        "attempts": float(attempts),
        "snoozes": float(max(attempts - 1, 0)),
        "avg_puzzle_time": avg_puzzle_time,
        "waking_difficulty": session.waking_difficulty,
    }


def _compute_sleep_statistics(
    sleep_sessions: list[SleepSession],
) -> tuple[dict[int, float], dict[int, float]]:
    """Return sleep quality and efficiency maps keyed by SleepSession id."""
    sleep_quality_by_id: dict[int, float] = {}
    sleep_efficiency_by_id: dict[int, float] = {}

    for sleep in sleep_sessions:
        stages = sleep.sleep_stages
        if not stages:
            sleep_quality_by_id[sleep.id] = 0.0
            sleep_efficiency_by_id[sleep.id] = 0.0
            continue

        in_bed_seconds = 0.0
        asleep_seconds = 0.0
        restorative_seconds = 0.0

        for stage in stages:
            if not stage.start_date or not stage.end_date:
                continue

            # Calculate duration of stage
            duration = max(
                (as_utc(stage.end_date) - as_utc(stage.start_date)).total_seconds(), 0.0
            )
            if duration <= 0:
                continue

            # Calculate asleep seconds and restorative seconds
            # Deep and core sleep stages count as restorative
            stage_name = (stage.stage or "").lower()
            in_bed_seconds += duration
            if "awake" not in stage_name:
                asleep_seconds += duration
            if "deep" in stage_name or "core" in stage_name:
                restorative_seconds += duration

        efficiency = (
            (asleep_seconds / in_bed_seconds) * 100.0 if in_bed_seconds > 0 else 0.0
        )
        quality = (
            (restorative_seconds / asleep_seconds) * 100.0
            if asleep_seconds > 0
            else 0.0
        )

        sleep_quality_by_id[sleep.id] = quality
        sleep_efficiency_by_id[sleep.id] = efficiency

    return sleep_quality_by_id, sleep_efficiency_by_id


def _build_feature_dict(
    alarm_time_minutes: int,
    day_of_week: int,
    avg_sleep_hours_last_3: list[float],
    avg_sleep_quality_last_3: list[float],
    avg_sleep_efficiency_last_3: list[float],
    sleep_data_age_days: float,
    avg_snoozes_last_10: list[float],
    avg_puzzle_time_last_10: list[float],
    avg_attempts_last_10: list[float],
    avg_snoozes_same_day: list[float],
    avg_snoozes_same_time: list[float],
    avg_puzzle_time_same_day: list[float],
    avg_puzzle_time_same_time: list[float],
) -> dict[str, float]:
    """Build the canonical feature dictionary used for both training and prediction."""
    return {
        "alarm_time_minutes": float(alarm_time_minutes),
        "day_of_week": float(day_of_week),
        "avg_sleep_hours_last_3": safe_avg(avg_sleep_hours_last_3),
        "avg_sleep_quality_last_3": safe_avg(avg_sleep_quality_last_3),
        "avg_sleep_efficiency_last_3": safe_avg(avg_sleep_efficiency_last_3),
        "num_sleep_days_used": float(len(avg_sleep_hours_last_3)),
        "sleep_data_age_days": float(max(sleep_data_age_days, 0.0)),
        "avg_snoozes_last_10": safe_avg(avg_snoozes_last_10),
        "avg_puzzle_time_last_10": safe_avg(avg_puzzle_time_last_10),
        "avg_attempts_last_10": safe_avg(avg_attempts_last_10),
        "avg_snoozes_same_day": safe_avg(avg_snoozes_same_day),
        "avg_snoozes_same_time": safe_avg(avg_snoozes_same_time),
        "avg_puzzle_time_same_day": safe_avg(avg_puzzle_time_same_day),
        "avg_puzzle_time_same_time": safe_avg(avg_puzzle_time_same_time),
    }


def _load_user_alarm_sessions(user_id: int) -> list[AlarmSession]:
    """Load alarm sessions for a user in chronological order with puzzle sessions preloaded."""
    return (
        AlarmSession.query.filter_by(user_id=user_id)
        .options(selectinload(AlarmSession.puzzle_sessions))
        .order_by(AlarmSession.triggered_at.asc())
        .all()
    )


def _load_user_sleep_sessions(user_id: int) -> list[SleepSession]:
    """Load sleep sessions for a user in chronological order with stages preloaded."""
    sleep_sessions: list[SleepSession] = (
        SleepSession.query.filter_by(user_id=user_id)
        .options(selectinload(SleepSession.sleep_stages))
        .order_by(SleepSession.end_date.asc())
        .all()
    )

    sleep_sessions.sort(
        key=lambda s: (
            as_utc(s.end_date)
            if s.end_date is not None
            else datetime.max.replace(tzinfo=timezone.utc)
        )
    )
    return sleep_sessions


def _build_session_rows(alarm_sessions: list[AlarmSession]) -> list[dict]:
    """Build normalized per-session rows used when computing prior behavioral aggregates."""
    rows = []
    for session in alarm_sessions:
        when_utc = as_utc(session.triggered_at)
        rows.append(
            {
                "session_id": session.id,
                "when_utc": when_utc,
                "alarm_time_minutes": minutes_after_midnight(when_utc),
                "day_of_week": when_utc.weekday(),
                "metrics": _session_metrics(session),
            }
        )
    return rows


def _extract_prior_behavior_lists(
    prior_rows: list[dict],
    day_of_week: int,
    alarm_time_minutes: int,
) -> dict[str, list[float]]:
    """Extract recent/same-day/same-time behavior vectors from prior session rows."""
    recent_rows = prior_rows[-10:]
    same_day_rows = [row for row in prior_rows if row["day_of_week"] == day_of_week]
    same_time_rows = [
        row for row in prior_rows if row["alarm_time_minutes"] == alarm_time_minutes
    ]

    return {
        "recent_snoozes": [row["metrics"]["snoozes"] for row in recent_rows],
        "recent_puzzle_times": [
            row["metrics"]["avg_puzzle_time"] for row in recent_rows
        ],
        "recent_attempts": [row["metrics"]["attempts"] for row in recent_rows],
        "same_day_snoozes": [row["metrics"]["snoozes"] for row in same_day_rows],
        "same_time_snoozes": [row["metrics"]["snoozes"] for row in same_time_rows],
        "same_day_puzzle_times": [
            row["metrics"]["avg_puzzle_time"] for row in same_day_rows
        ],
        "same_time_puzzle_times": [
            row["metrics"]["avg_puzzle_time"] for row in same_time_rows
        ],
    }


def _advance_recent_sleep_window(
    sleep_sessions: list[SleepSession],
    sleep_idx: int,
    recent_sleep_window: deque[SleepSession],
    reference_time_utc: datetime,
) -> tuple[int, list[SleepSession]]:
    """Advance rolling sleep window up to reference_time_utc and return updated index/window list."""
    while sleep_idx < len(sleep_sessions):
        sleep = sleep_sessions[sleep_idx]
        if sleep.end_date is None:
            sleep_idx += 1
            continue
        if as_utc(sleep.end_date) <= reference_time_utc:
            recent_sleep_window.append(sleep)
            sleep_idx += 1
            continue
        break

    return sleep_idx, list(recent_sleep_window)


def _save_model(user_id, model, use_health_data : bool):
    """
    Serializes and persists a trained scikit-learn model to the database for the given user.

    Converts the model to binary using joblib.

    If a model already exists for the user, it is updated,
    otherwise a new record is created.

    :param user_id: The user ID for whom the model is being saved.
    :param model: The scikit-learn Pipeline model to serialize and store.
    :return: None
    """
    # Creates a memory buffer to write model to
    model_bytes = io.BytesIO()

    # Serialises the model and writes into the BytesIO buffer (in binary)
    joblib.dump(model, model_bytes)

    # Moves the file pointer back to the beginning
    model_bytes.seek(0)

    # Store the model
    user_model : DifficultyModel = DifficultyModel.query.filter_by(user_id=user_id).first()
    if user_model:
        user_model.model_blob = model_bytes.read()
        user_model.last_trained = datetime.now(timezone.utc)
        user_model.uses_health_data = use_health_data
    else:
        user_model = DifficultyModel(
            user_id=user_id,
            model_blob=model_bytes.read(),
            last_trained=datetime.now(timezone.utc),
            uses_health_data=use_health_data,
        )
        db.session.add(user_model)
    db.session.commit()


def _load_model(user_id) -> Pipeline | None:
    """
    Deserializes and retrieves a previously trained model for the given user from the database.

    Loads the binary serialized model using joblib and reconstructs the scikit-learn Pipeline.
    Returns None if no model exists for the user.

    :param user_id: The user ID for whom to retrieve the trained model.
    :return: The deserialized scikit-learn Pipeline model, or None if no model is found.
    """
    # Check if user has a model
    user_model = DifficultyModel.query.filter_by(user_id=user_id).first()
    if not user_model:
        print(f"No model found for user {user_id}.")
        return None

    # Creates a memory buffer
    model_bytes = io.BytesIO(user_model.model_blob)

    # Deserialises the binary data back into a fully built model
    model = joblib.load(model_bytes)
    return model


def should_retrain_model(
    user_id: int, max_age_days: int = MODEL_RETRAIN_AFTER_DAYS
) -> bool:
    """Return True when a user's stored model is missing, outdated, or mismatched with current data permissions."""
    user_model = DifficultyModel.query.filter_by(user_id=user_id).first()
    if not user_model:
        return True

    # Check if model was trained with different health data setting
    from app.models import User
    user = User.query.get(user_id)
    current_flag = bool(getattr(user, "use_health_data", False)) if user else False

    if user_model.uses_health_data != current_flag:
        return True

    # Check model age
    last_trained_utc = as_utc(user_model.last_trained)
    model_age = datetime.now(timezone.utc) - last_trained_utc

    return model_age > timedelta(days=max_age_days)


def _extract_features(user_id, use_health_data: bool) -> list[dict] | None:
    """
    Extracts training features from alarm sessions, puzzle sessions, and sleep data for a given user.

    This function constructs one training sample per AlarmSession, computing features across
    multiple dimensions:
    - Context: alarm trigger time of day and weekday (from AlarmSession.triggered_at)
    - Sleep quality: hours slept, sleep quality/efficiency metrics, data freshness
    - Recent behavior: average snoozes, puzzle solve time, and puzzle attempts over last 10 alarms
    - Contextual behavior: same-day and same-time behavioural patterns from prior sessions

    Each sample is regressed on the observed average puzzle solve time, allowing the trained
    model to predict expected difficulty/latency for a given alarm context.

    :param user_id: The user ID for whom to extract features.
    :return: A list of dictionaries, each containing:
        - alarm_session_id: ID of the AlarmSession
        - features: Dictionary mapping feature_names to float values
        - target: Average puzzle solve time in seconds (regression target)
    """

    # Load all data
    alarm_sessions: list[AlarmSession] = _load_user_alarm_sessions(user_id)
    if not alarm_sessions:
        return None

    sleep_sessions: list[SleepSession] = _load_user_sleep_sessions(user_id) if use_health_data else []

    # Detects incomplete sleep sessions, places them at end of list
    none_end_count = sum(1 for s in sleep_sessions if s.end_date is None)
    if none_end_count:
        print(
            f"Found {none_end_count} SleepSession(s) with missing end_date; they will be placed at the end of the list."
        )

    sleep_quality_by_id, sleep_efficiency_by_id = _compute_sleep_statistics(
        sleep_sessions
    )

    extracted_data = []
    session_rows = _build_session_rows(alarm_sessions)

    sleep_idx = 0

    # Data structure that only stores 3 values, FIFO when deque reaches its maximum
    recent_sleep_window: deque[SleepSession] = deque(maxlen=3)

    for index, row in enumerate(session_rows):
        current_metrics = row["metrics"]

        if current_metrics["waking_difficulty"] is None:
            continue

        when_utc = row["when_utc"]
        alarm_time_minutes = row["alarm_time_minutes"]
        day_of_week = row["day_of_week"]

        behavior = _extract_prior_behavior_lists(
            prior_rows=session_rows[:index],
            day_of_week=day_of_week,
            alarm_time_minutes=alarm_time_minutes,
        )

        # Get last 3 sleeps date
        sleep_idx, last_three_sleeps = _advance_recent_sleep_window(
            sleep_sessions=sleep_sessions,
            sleep_idx=sleep_idx,
            recent_sleep_window=recent_sleep_window,
            reference_time_utc=when_utc,
        )

        # Handle sleep features depending on use_health_data
        if use_health_data:
            sleep_hours = [
                float(sleep.total_duration) / 3600.0 for sleep in last_three_sleeps
            ]
            sleep_quality = [
                sleep_quality_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps
            ]
            sleep_efficiency = [
                sleep_efficiency_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps
            ]
            sleep_data_age_days = (
                (when_utc - as_utc(last_three_sleeps[-1].end_date)).total_seconds()
                / 86400.0
                if last_three_sleeps
                else 0.0
            )
        else:
            sleep_hours = []
            sleep_quality = []
            sleep_efficiency = []
            sleep_data_age_days = 0.0

        # Collect all features
        features = _build_feature_dict(
            alarm_time_minutes=alarm_time_minutes,
            day_of_week=day_of_week,
            avg_sleep_hours_last_3=sleep_hours,
            avg_sleep_quality_last_3=sleep_quality,
            avg_sleep_efficiency_last_3=sleep_efficiency,
            sleep_data_age_days=sleep_data_age_days,
            avg_snoozes_last_10=behavior["recent_snoozes"],
            avg_puzzle_time_last_10=behavior["recent_puzzle_times"],
            avg_attempts_last_10=behavior["recent_attempts"],
            avg_snoozes_same_day=behavior["same_day_snoozes"],
            avg_snoozes_same_time=behavior["same_time_snoozes"],
            avg_puzzle_time_same_day=behavior["same_day_puzzle_times"],
            avg_puzzle_time_same_time=behavior["same_time_puzzle_times"],
        )

        # Collect all data
        extracted_data.append(
            {
                "alarm_session_id": row["session_id"],
                "features": features,
                "target": current_metrics["waking_difficulty"],
            }
        )

    return extracted_data


def train_user_model(user_id) -> Pipeline | None:
    """
    Trains a RandomForest regression model to predict puzzle solve time for a given user.

    Extracts features from the user's historical alarm and sleep data using _extract_features,
    constructs a feature matrix in the canonical feature_names order, and trains a scikit-learn
    Pipeline with StandardScaler and RandomForestRegressor. The trained model is persisted to
    the database via _save_model.

    Returns None if no training data is available for the user.

    :param user_id: The user ID for whom to train the model.
    :return: The trained scikit-learn Pipeline model, or None if training data is unavailable.
    """
    from app.models import User
    user = User.query.get(user_id)
    use_health_data = bool(getattr(user, "use_health_data", False)) if user else False

    data = _extract_features(user_id, use_health_data)

    if not data or len(data) < MIN_TRAINING_SAMPLES:
        print(
            f"Not enough training data for user {user_id}. This requires at least {MIN_TRAINING_SAMPLES} samples."
        )
        return None

    X_rows, y_rows = [], []

    for item in data:
        features = item["features"]
        row = [float(features.get(name, 0.0)) for name in feature_names]

        X_rows.append(row)
        y_rows.append(float(item["target"]))

    X_arr = np.array(X_rows)
    y_arr = np.array(y_rows)

    # Create the model
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestRegressor(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_split=5,
                    min_samples_leaf=2,
                ),
            ),
        ]
    )

    # Train the model on collected data
    model.fit(X_arr, y_arr)
    _save_model(user_id, model, use_health_data)

    print(f"Model trained for user: {user_id}.")
    return model


def _predict_user_model(user_id, prediction_data):
    """
    Makes difficulty/latency predictions using a user's trained model.

    Loads the persisted model for the user via _load_model and applies it to the
    provided prediction_data (expected to be a feature matrix in the canonical feature_names order).
    Returns None if no model exists for the user.

    :param user_id: The user ID whose trained model should be used.
    :param prediction_data: A numpy array or array-like feature matrix, with shape (n_samples, n_features).
                            Columns must correspond to the order of feature_names.
    :return: An array of predicted puzzle solve times (in seconds) for each sample, or None if no model is found.
    """
    model: Pipeline | None = None

    if should_retrain_model(user_id):
        # Try refresh first; if refresh fails due sparse data, keep using existing model if one exists.
        model = train_user_model(user_id)

    if model is None:
        model = _load_model(user_id)
    if model is None:
        return None

    return model.predict(prediction_data)


def find_suitable_alarm(user_id: int, min_time: datetime, max_time: datetime):

    # Convert time limits to UTC
    min_time_utc = as_utc(min_time)
    max_time_utc = as_utc(max_time)

    # Make time constraints consistent with alarm_time in feature extraction
    min_time_minutes = minutes_after_midnight(min_time_utc)
    max_time_minutes = minutes_after_midnight(max_time_utc)

    if min_time_minutes <= max_time_minutes:
        # Same day window
        candidate_specs = [
            (minute, 0) for minute in range(min_time_minutes, max_time_minutes + 1, 15)
        ]
    else:
        # Min time and max time on different days
        candidate_specs = [
            (minute, 0) for minute in range(min_time_minutes, 24 * 60, 15)
        ]
        candidate_specs.extend(
            (minute, 1) for minute in range(0, max_time_minutes + 1, 15)
        )

    # Select candidate alarm times
    midnight = min_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    candidate_datetimes: list[datetime] = [
        midnight + timedelta(days=day_offset, minutes=minute)
        for minute, day_offset in candidate_specs
    ]
    if not candidate_datetimes:
        return {"best_candidate": None, "candidates": []}

    alarm_sessions: list[AlarmSession] = _load_user_alarm_sessions(user_id)

    # Check if user has over the minimum required alarm sessions to train the model
    MIN_REQUIRED_SESSIONS = 10
    if len(alarm_sessions) < MIN_REQUIRED_SESSIONS:
        return {
            "best_candidate": None,
            "reason": "not_enough_alarm_data",
            "required_sessions": MIN_REQUIRED_SESSIONS,
            "current_sessions": len(alarm_sessions),
        }
    sleep_sessions: list[SleepSession] = _load_user_sleep_sessions(user_id)

    sleep_quality_by_id, sleep_efficiency_by_id = _compute_sleep_statistics(
        sleep_sessions
    )

    session_rows = _build_session_rows(alarm_sessions)
    candidate_payload = []

    sleep_idx = 0

    # Data structure that only stores 3 values, FIFO when deque reaches its maximum
    recent_sleep_window: deque[SleepSession] = deque(maxlen=3)

    # Loop through each of the candidate alarm times
    for candidate_dt in candidate_datetimes:
        candidate_utc = as_utc(candidate_dt)
        alarm_time_minutes = minutes_after_midnight(candidate_utc)
        day_of_week = candidate_utc.weekday()

        # Calculate statistics based on previous sessions
        prior_rows = [row for row in session_rows if row["when_utc"] < candidate_utc]
        behavior = _extract_prior_behavior_lists(
            prior_rows=prior_rows,
            day_of_week=day_of_week,
            alarm_time_minutes=alarm_time_minutes,
        )

        # Get the last three sleeps
        sleep_idx, last_three_sleeps = _advance_recent_sleep_window(
            sleep_sessions=sleep_sessions,
            sleep_idx=sleep_idx,
            recent_sleep_window=recent_sleep_window,
            reference_time_utc=candidate_utc,
        )

        # Calculate sleep statistics
        sleep_hours = [
            float(sleep.total_duration) / 3600.0 for sleep in last_three_sleeps
        ]
        sleep_quality = [
            sleep_quality_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps
        ]
        sleep_efficiency = [
            sleep_efficiency_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps
        ]
        sleep_data_age_days = (
            (candidate_utc - as_utc(last_three_sleeps[-1].end_date)).total_seconds()
            / 86400.0
            if last_three_sleeps
            else 0.0
        )

        features = _build_feature_dict(
            alarm_time_minutes=alarm_time_minutes,
            day_of_week=day_of_week,
            avg_sleep_hours_last_3=sleep_hours,
            avg_sleep_quality_last_3=sleep_quality,
            avg_sleep_efficiency_last_3=sleep_efficiency,
            sleep_data_age_days=sleep_data_age_days,
            avg_snoozes_last_10=behavior["recent_snoozes"],
            avg_puzzle_time_last_10=behavior["recent_puzzle_times"],
            avg_attempts_last_10=behavior["recent_attempts"],
            avg_snoozes_same_day=behavior["same_day_snoozes"],
            avg_snoozes_same_time=behavior["same_time_snoozes"],
            avg_puzzle_time_same_day=behavior["same_day_puzzle_times"],
            avg_puzzle_time_same_time=behavior["same_time_puzzle_times"],
        )

        candidate_payload.append(
            {
                "candidate_time": candidate_utc,
                "features": features,
                "feature_row": [
                    float(features.get(name, 0.0)) for name in feature_names
                ],
            }
        )

    # Prepares features ready for prediction
    prediction_matrix = np.array([item["feature_row"] for item in candidate_payload])
    predictions = _predict_user_model(user_id, prediction_matrix)

    if predictions is None:
        return {"best_candidate": None, "candidates": candidate_payload}

    # Extract predicted data
    for item, pred in zip(candidate_payload, predictions):
        item["predicted_puzzle_time_seconds"] = float(pred)

    # Find the best candidate (lowest difficulty score)
    best_candidate = min(
        candidate_payload,
        key=lambda row: row.get("predicted_puzzle_time_seconds", float("inf")),
    )

    return {
        "best_candidate": best_candidate,
        "candidates": candidate_payload,
    }
