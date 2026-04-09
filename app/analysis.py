import joblib
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
import numpy as np
import io
from collections import defaultdict
from datetime import datetime, timezone
from sklearn.preprocessing import StandardScaler
from sqlalchemy.orm import selectinload

from app.models import AlarmSession, DifficultyModel, SleepSession, SleepStage
from app import database as db

feature_names = [

    # Context
    "alarm_time_minutes", # Minutes after midnight the original alarm is set for
    "day_of_week", # Day of the week the alarm is set for

    # Sleep data
    "avg_sleep_hours_last_3", # Average sleep hours over the last 3 nights
    "avg_sleep_quality_last_3", # Average of how well the user has slept over the last 3 nights
    "avg_sleep_efficiency_last_3",
    "num_sleep_days_used",
    "sleep_data_age_days",

    # Behaviour (recent)
    "avg_snoozes_last_10", # Average number of snoozes in the last 10 alarms
    "avg_puzzle_time_last_10", # Average puzzle time over the last 10 alarms
    "avg_attempts_last_10", # Average puzzle attempts over the last 10 alarms

    # Behaviour (context)
    "avg_snoozes_same_day",
    "avg_snoozes_same_time",
    "avg_puzzle_time_same_day",
    "avg_puzzle_time_same_time",
]

def _save_model(user_id, model):
    """
    Serializes and persists a trained scikit-learn model to the database for the given user.

    Converts the model to binary using joblib, stores it in the DifficultyModel table,
    and records the training timestamp. If a model already exists for the user, it is updated;
    otherwise, a new record is created.

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
    user_model = DifficultyModel.query.filter_by(user_id=user_id).first()
    if user_model:
        user_model.model_blob = model_bytes.read()
        user_model.last_trained = datetime.now(timezone.utc)
    else:
        user_model = DifficultyModel(
            user_id=user_id,
            model_blob=model_bytes.read(),
            last_trained=datetime.now(timezone.utc),
        )
        db.session.add(user_model)
    db.session.commit()

def _load_model(user_id):
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

def _extract_features(user_id) -> list[dict]:
    """
    Extracts training features from alarm sessions, puzzle sessions, and sleep data for a given user.

    This function constructs one training sample per AlarmSession, computing features across
    multiple dimensions:
    - Context: alarm trigger time of day and weekday (from AlarmSession.triggered_at)
    - Sleep quality: hours slept, sleep quality/efficiency metrics, data freshness
    - Recent behavior: average snoozes, puzzle solve time, and puzzle attempts over last 10 alarms
    - Contextual behavior: same-day and same-time behavioral patterns from prior sessions

    Each sample is regressed on the observed average puzzle solve time, allowing the trained
    model to predict expected difficulty/latency for a given alarm context.

    :param user_id: The user ID for whom to extract features.
    :return: A list of dictionaries, each containing:
        - alarm_session_id: ID of the AlarmSession
        - features: Dictionary mapping feature_names to float values
        - target: Average puzzle solve time in seconds (regression target)
    """
    def _safe_avg(values: list[float]) -> float:
        """
        Safely compute the average of a list, returning 0.0 if empty.

        :param values: List of numeric values to average.
        :return: The mean value, or 0.0 if the list is empty.
        :rtype: float
        """
        return float(sum(values) / len(values)) if values else 0.0

    def _as_utc(dt: datetime) -> datetime:
        """
        Normalize a datetime to UTC, handling both naive and aware datetimes.

        :param dt: The datetime to normalize.
        :return: The same datetime in UTC timezone-aware format.
        :rtype: datetime
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _minutes_after_midnight(dt: datetime) -> int:
        """
        Convert a datetime to minutes elapsed since midnight.

        :param dt: The datetime to convert.
        :return: Minutes after midnight (0-1439).
        :rtype: int
        """
        return (dt.hour * 60) + dt.minute

    def _session_metrics(session: AlarmSession) -> dict[str, float]:
        """
        Compute behavioral metrics from a single AlarmSession and its associated puzzles.

        Metrics include:
        - attempts: Total number of puzzle attempts (puzzle_sessions) in this alarm
        - snoozes: Inferred as (attempts - 1), representing snooze count before final wake-up
        - avg_puzzle_time: Average time spent solving puzzles, in seconds

        :param session: The AlarmSession to analyze.
        :return: Dictionary with keys 'attempts', 'snoozes', 'avg_puzzle_time'.
        :rtype: dict[str, float]
        """
        attempts = len(session.puzzle_sessions)
        avg_puzzle_time = _safe_avg([float(p.time_taken_seconds) for p in session.puzzle_sessions])
        return {
            "attempts": float(attempts),
            "snoozes": float(max(attempts - 1, 0)),
            "avg_puzzle_time": avg_puzzle_time,
        }

    alarm_sessions: list[AlarmSession] = (
        AlarmSession.query
        .filter_by(user_id=user_id)
        .options(selectinload(AlarmSession.puzzle_sessions))
        .order_by(AlarmSession.triggered_at.asc())
        .all()
    )

    if not alarm_sessions:
        return []

    sleep_sessions: list[SleepSession] = (
        SleepSession.query
        .filter_by(user_id=user_id)
        .order_by(SleepSession.end_date.asc())
        .all()
    )

    sleep_session_ids = [s.id for s in sleep_sessions]
    sleep_stages: list[SleepStage] = []
    if sleep_session_ids:
        sleep_stages = (
            SleepStage.query
            .filter(SleepStage.sleep_session_id.in_(sleep_session_ids))
            .order_by(SleepStage.start_date.asc())
            .all()
        )

    stages_by_sleep_session: dict[int, list[SleepStage]] = defaultdict(list)
    for stage in sleep_stages:
        stages_by_sleep_session[stage.sleep_session_id].append(stage)

    sleep_quality_by_id: dict[int, float] = {}
    sleep_efficiency_by_id: dict[int, float] = {}
    for sleep in sleep_sessions:
        stages = stages_by_sleep_session.get(sleep.id, [])
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

            duration = max((_as_utc(stage.end_date) - _as_utc(stage.start_date)).total_seconds(), 0.0)
            if duration <= 0:
                continue

            stage_name = (stage.stage or "").lower()
            in_bed_seconds += duration
            if "awake" not in stage_name:
                asleep_seconds += duration
            if "deep" in stage_name or "rem" in stage_name:
                restorative_seconds += duration

        efficiency = (asleep_seconds / in_bed_seconds) * 100.0 if in_bed_seconds > 0 else 0.0
        quality = (restorative_seconds / asleep_seconds) * 100.0 if asleep_seconds > 0 else 0.0

        sleep_quality_by_id[sleep.id] = quality
        sleep_efficiency_by_id[sleep.id] = efficiency

    extracted_data = []

    per_session_context: dict[int, tuple[int, int]] = {}
    per_session_metrics: dict[int, dict[str, float]] = {}
    for session in alarm_sessions:
        when_utc = _as_utc(session.triggered_at)
        alarm_time_minutes = _minutes_after_midnight(when_utc)
        day_of_week = when_utc.weekday()

        per_session_context[session.id] = (alarm_time_minutes, day_of_week)
        per_session_metrics[session.id] = _session_metrics(session)

    for index, session in enumerate(alarm_sessions):
        when_utc = _as_utc(session.triggered_at)
        alarm_time_minutes, day_of_week = per_session_context[session.id]
        current_metrics = per_session_metrics[session.id]

        prior_sessions = alarm_sessions[:index]
        recent_sessions = prior_sessions[-10:]

        recent_snoozes = [per_session_metrics[s.id]["snoozes"] for s in recent_sessions]
        recent_puzzle_times = [per_session_metrics[s.id]["avg_puzzle_time"] for s in recent_sessions]
        recent_attempts = [per_session_metrics[s.id]["attempts"] for s in recent_sessions]

        same_day_sessions = [
            s for s in prior_sessions
            if per_session_context[s.id][1] == day_of_week
        ]
        same_time_sessions = [
            s for s in prior_sessions
            if per_session_context[s.id][0] == alarm_time_minutes
        ]

        same_day_snoozes = [per_session_metrics[s.id]["snoozes"] for s in same_day_sessions]
        same_time_snoozes = [per_session_metrics[s.id]["snoozes"] for s in same_time_sessions]
        same_day_puzzle_times = [per_session_metrics[s.id]["avg_puzzle_time"] for s in same_day_sessions]
        same_time_puzzle_times = [per_session_metrics[s.id]["avg_puzzle_time"] for s in same_time_sessions]

        previous_sleep_sessions = [
            sleep for sleep in sleep_sessions
            if _as_utc(sleep.end_date) <= when_utc
        ]
        last_three_sleeps = previous_sleep_sessions[-3:]

        sleep_hours = [float(sleep.total_duration) / 3600.0 for sleep in last_three_sleeps]
        sleep_quality = [sleep_quality_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps]
        sleep_efficiency = [sleep_efficiency_by_id.get(sleep.id, 0.0) for sleep in last_three_sleeps]
        sleep_data_age_days = (
            (when_utc - _as_utc(last_three_sleeps[-1].end_date)).total_seconds() / 86400.0
            if last_three_sleeps else 0.0
        )

        features = {
            "alarm_time_minutes": float(alarm_time_minutes),
            "day_of_week": float(day_of_week),
            "avg_sleep_hours_last_3": _safe_avg(sleep_hours),
            "avg_sleep_quality_last_3": _safe_avg(sleep_quality),
            "avg_sleep_efficiency_last_3": _safe_avg(sleep_efficiency),
            "num_sleep_days_used": float(len(last_three_sleeps)),
            "sleep_data_age_days": float(max(sleep_data_age_days, 0.0)),
            "avg_snoozes_last_10": _safe_avg(recent_snoozes),
            "avg_puzzle_time_last_10": _safe_avg(recent_puzzle_times),
            "avg_attempts_last_10": _safe_avg(recent_attempts),
            "avg_snoozes_same_day": _safe_avg(same_day_snoozes),
            "avg_snoozes_same_time": _safe_avg(same_time_snoozes),
            "avg_puzzle_time_same_day": _safe_avg(same_day_puzzle_times),
            "avg_puzzle_time_same_time": _safe_avg(same_time_puzzle_times),
        }

        extracted_data.append({
            "alarm_session_id": session.id,
            "features": features,
            #TODO: Change target to a user defined value
            "target": current_metrics["avg_puzzle_time"],
        })

    return extracted_data

def train_user_model(user_id):
    """
    Trains a RandomForest regression model to predict puzzle solve time for a given user.

    Extracts features from the user's historical alarm and sleep data using _extract_features,
    constructs a feature matrix in the canonical feature_names order, and trains a scikit-learn
    Pipeline with StandardScaler and RandomForestRegressor. The trained model is persisted to
    the database via _save_model.

    Returns None if no training data is available for the user.

    :param user_id: The user ID for whom to train the model.
    :return: The trained scikit-learn Pipeline model, or None if training data is unavailable.
    :rtype: Pipeline | None
    """
    data = _extract_features(user_id)
    if not data:
        print(f"No training data found for user: {user_id}.")
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
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=2,
        ))
    ])

    # Train the model on collected data
    model.fit(X_arr, y_arr)
    _save_model(user_id, model)

    print(f"Model trained for user: {user_id}.")
    return model

def predict_user_model(user_id, prediction_data):
    """
    Makes difficulty/latency predictions using a user's trained model.

    Loads the persisted model for the user via _load_model and applies it to the
    provided prediction_data (expected to be a feature matrix in the canonical feature_names order).
    Returns None if no model exists for the user.

    :param user_id: The user ID whose trained model should be used.
    :param prediction_data: A numpy array or array-like feature matrix, with shape (n_samples, n_features).
                            Columns must correspond to the order of feature_names.
    :return: An array of predicted puzzle solve times (in seconds) for each sample, or None if no model is found.
    :rtype: ndarray | None
    """
    model: Pipeline = _load_model(user_id)
    if model is None:
        return None
    
    return model.predict(prediction_data)