"""
This module implements all the routes for the Flask application.
"""

from datetime import datetime, timedelta
from threading import Thread
from typing import List

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import InternalServerError

from app import app, csrf, login_manager
from app import database as db
from app.analysis import find_suitable_alarm, should_retrain_model
from app.forms import (
    AlarmForm,
    DeleteAccountForm,
    DeviceSettingsForm,
    EditAlarmForm,
    LoginForm,
    PairDeviceForm,
    RegistrationForm,
)
from app.models import (
    Alarm,
    AlarmSession,
    DifficultyModel,
    Device,
    PuzzleSession,
    SleepSession,
    SleepStage,
    User,
    resolve_effective_puzzle_type,
)
from app.utils import (
    as_utc,
    group_sleep_records,
    next_weekday_utc,
    parse_apple_dt,
    parse_hhmm_time,
    resolve_timezone,
    utc_now,
)


def _is_expired(value: datetime) -> bool:
    normalized = as_utc(value)
    return normalized is not None and normalized < utc_now()


def _resolve_alarm_time(
    user_id: int,
    day_of_week: int,
    preferred_time,
    use_dynamic_alarm: bool,
    dynamic_start_time=None,
    dynamic_end_time=None,
):
    """Resolve final alarm time, using analysis when dynamic mode is enabled."""
    if not use_dynamic_alarm:
        return preferred_time, False

    try:
        start_time = dynamic_start_time or preferred_time
        end_time = dynamic_end_time or preferred_time

        min_dt = next_weekday_utc(day_of_week=day_of_week, time_value=start_time)
        max_dt = min_dt.replace(
            hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0
        )
        if max_dt <= min_dt:
            max_dt += timedelta(days=1)

        result = find_suitable_alarm(user_id=user_id, min_time=min_dt, max_time=max_dt)
        best = (result or {}).get("best_candidate") or {}
        best_time = best.get("candidate_time")

        if isinstance(best_time, datetime):
            return best_time.timetz().replace(tzinfo=None), True
    except Exception:
        pass

    return preferred_time, False


def _run_dynamic_alarm_optimization(
    alarm_id: str,
    user_id: int,
    day_of_week: int,
    preferred_time,
    dynamic_start_time,
    dynamic_end_time,
    expected_alarm_time,
    expected_dynamic_start_time,
    expected_dynamic_end_time,
):
    """Background worker that updates Alarm.time with model-selected time."""
    with app.app_context():
        try:
            resolved_time, _ = _resolve_alarm_time(
                user_id=user_id,
                day_of_week=day_of_week,
                preferred_time=preferred_time,
                use_dynamic_alarm=True,
                dynamic_start_time=dynamic_start_time,
                dynamic_end_time=dynamic_end_time,
            )

            alarm = db.session.get(Alarm, alarm_id)
            if not alarm or not getattr(alarm, 'use_dynamic_alarm', False):
                return

            # Prevent stale background jobs from overwriting newer user edits.
            if alarm.time != expected_alarm_time:
                return
            if alarm.dynamic_start_time != expected_dynamic_start_time:
                return
            if alarm.dynamic_end_time != expected_dynamic_end_time:
                return

            alarm.time = resolved_time
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.remove()


def _schedule_dynamic_alarm_optimization(
    alarm_id: str,
    user_id: int,
    day_of_week: int,
    preferred_time,
    dynamic_start_time,
    dynamic_end_time,
    expected_alarm_time,
    expected_dynamic_start_time,
    expected_dynamic_end_time,
):
    """Start a detached thread to optimise one dynamic alarm without blocking the request."""
    Thread(
        target=_run_dynamic_alarm_optimization,
        args=(
            alarm_id,
            user_id,
            day_of_week,
            preferred_time,
            dynamic_start_time,
            dynamic_end_time,
            expected_alarm_time,
            expected_dynamic_start_time,
            expected_dynamic_end_time,
        ),
        daemon=True,
    ).start()


def _dynamic_alarm_ui_state(user_id: int) -> tuple[int, bool]:
    """Return alarm-session count and whether dynamic UI should be enabled (>10 sessions)."""
    alarm_session_count = AlarmSession.query.filter_by(user_id=user_id).count()
    return alarm_session_count, alarm_session_count > 10


# Return JSON 401 for API/AJAX requests, otherwise redirect to the login page.
@login_manager.unauthorized_handler
def unauthorized_callback():
    from flask import flash, jsonify, redirect, request, url_for

    # If client expects JSON (AJAX / API), return a 401 JSON response.
    wants_json = False
    # Prefer explicit JSON content type or common AJAX header
    if request.is_json:
        wants_json = True
    elif request.headers.get("X-Requested-With") == "XMLHttpRequest":
        wants_json = True
    else:
        # also check Accept header
        best = request.accept_mimetypes.best
        if best and "json" in best:
            wants_json = True

    if wants_json:
        return jsonify(
            {"response": "unauthenticated", "message": "authentication required"}
        ), 401

    # For regular browser requests, flash a message and redirect to the login page.
    flash(login_manager.login_message, login_manager.login_message_category)
    # Use `next` so the user can be returned after login
    return redirect(url_for(login_manager.login_view, next=request.path))


@app.route("/status")
def status():
    """
    Simple health check route used to verify that the server is running.
    Useful for debugging or monitoring.
    """
    return "Server is running!"


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Public landing page for unauthenticated users.
    Authenticated users are redirected to their dashboard.
    """

    # Test User
    if User.query.filter_by(email_address="test@test.com").first() is None:
        User.register("test@test.com", "12345", "test")

    # If the user is authenticated, send them to the main dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Dedicated login page and handler."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    login_form = LoginForm()
    if login_form.validate_on_submit() and login_form.submit.data:
        email_normalized = (login_form.email_address.data or "").strip().lower()
        user = User.query.filter_by(email_address=email_normalized).first()

        if user and user.verify_password(login_form.password.data):
            login_user(user, remember=login_form.remember_me.data)
            flash("Logged in successfully!", "success")

            next_page = request.args.get("next") or request.form.get("next")
            if next_page and isinstance(next_page, str) and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html", login_form=login_form, auth_mode="login")


@app.route("/account")
@login_required
def account():
    """
    Account management page.

    login_required ensures only authenticated users can access this route.
    If a user is not logged in, Flask-Login will redirect them to the login page.
    """
    try:
        delete_account_form = DeleteAccountForm()
        return render_template(
            "account.html", user=current_user, delete_account_form=delete_account_form
        )
    except Exception:
        # Raise a 500 server error if something unexpected occurs
        raise InternalServerError("An error occurred while loading the account page.")


@app.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    delete_account_form = DeleteAccountForm()

    if not delete_account_form.validate_on_submit():
        flash("Please complete the delete-account confirmation fields.", "danger")
        return redirect(url_for("account") + "#delete-account")

    entered_email = (delete_account_form.email_address.data or "").strip().lower()
    current_email = (current_user.email_address or "").strip().lower()

    if entered_email != current_email:
        flash("Email does not match your account.", "danger")
        return redirect(url_for("account") + "#delete-account")

    if not current_user.verify_password(delete_account_form.password.data or ""):
        flash("Incorrect password.", "danger")
        return redirect(url_for("account") + "#delete-account")

    user_id = current_user.id
    owned_serials = [
        row[0] for row in db.session.query(Device.serial_number).filter_by(user_id=user_id).all()
    ]

    try:
        if owned_serials:
            Alarm.query.filter(Alarm.device_serial.in_(owned_serials)).delete(
                synchronize_session=False
            )
            Device.query.filter(Device.serial_number.in_(owned_serials)).update(
                {"user_id": None, "pairing_code": None, "pairing_expiry": None},
                synchronize_session=False,
            )

        Alarm.query.filter_by(user_id=user_id).delete(synchronize_session=False)

        alarm_session_ids = [
            row[0] for row in db.session.query(AlarmSession.id).filter_by(user_id=user_id).all()
        ]
        if alarm_session_ids:
            PuzzleSession.query.filter(
                PuzzleSession.alarm_session_id.in_(alarm_session_ids)
            ).delete(synchronize_session=False)

        AlarmSession.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        SleepStage.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        SleepSession.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        DifficultyModel.query.filter_by(user_id=user_id).delete(synchronize_session=False)

        user = db.session.get(User, user_id)
        if user is not None:
            db.session.delete(user)

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not delete account right now. Please try again.", "danger")
        return redirect(url_for("account") + "#delete-account")

    logout_user()
    flash("Your account and all associated data have been deleted.", "success")
    return redirect(url_for("index"))


@app.route("/account/session-history", methods=["GET"])
@login_required
def session_history():
    """Show recorded alarm/puzzle sessions grouped by day for the current user."""
    display_tz, active_tz = resolve_timezone((request.args.get("tz") or "").strip())

    # Only use names for devices owned by the current user; otherwise fallback to serial number.
    serial_to_device_name = {
        d.serial_number: (
            d.name.strip()
            if isinstance(d.name, str) and d.name.strip()
            else d.serial_number
        )
        for d in current_user.devices
    }

    alarm_sessions = (
        AlarmSession.query.filter_by(user_id=current_user.id)
        .options(selectinload(AlarmSession.puzzle_sessions))
        .order_by(AlarmSession.triggered_at.desc())
        .all()
    )

    grouped_by_day: dict[str, dict] = {}
    for alarm_session in alarm_sessions:
        triggered_at_utc = as_utc(alarm_session.triggered_at)
        if triggered_at_utc is None:
            continue
        triggered_at_local = triggered_at_utc.astimezone(display_tz)
        day_key = triggered_at_local.date().isoformat()

        if day_key not in grouped_by_day:
            grouped_by_day[day_key] = {
                "day_key": day_key,
                "day_label": triggered_at_local.strftime("%A %d %B %Y"),
                "sessions": [],
            }

        grouped_by_day[day_key]["sessions"].append(
            {
                "id": alarm_session.id,
                "device_serial": alarm_session.device_serial,
                "device_display_name": serial_to_device_name.get(
                    alarm_session.device_serial, alarm_session.device_serial
                ),
                "triggered_at": triggered_at_local,
                "waking_difficulty": alarm_session.waking_difficulty,
                "puzzle_sessions": sorted(
                    alarm_session.puzzle_sessions, key=lambda s: s.id
                ),
            }
        )

    day_groups = [
        grouped_by_day[key] for key in sorted(grouped_by_day.keys(), reverse=True)
    ]
    selected_day = request.args.get("day")

    return render_template(
        "session_history.html",
        day_groups=day_groups,
        selected_day=selected_day,
        active_tz=active_tz,
    )


@app.route(
    "/account/session-history/alarm/<int:alarm_session_id>/waking-difficulty",
    methods=["POST"],
)
@login_required
def update_alarm_session_waking_difficulty(alarm_session_id):
    alarm_session = db.session.get(AlarmSession, alarm_session_id)
    day = request.form.get('day')
    tz_name = request.form.get('tz')

    if alarm_session is None or alarm_session.user_id != current_user.id:
        flash("Alarm session not found.", "danger")
        return redirect(
            url_for("session_history", day=day, tz=tz_name)
            if day
            else url_for("session_history", tz=tz_name)
        )

    raw_score = (request.form.get("waking_difficulty") or "").strip()
    if not raw_score:
        alarm_session.waking_difficulty = None
    else:
        try:
            score = int(raw_score)
        except ValueError:
            flash("Wake difficulty must be a whole number between 1 and 10.", "danger")
            return redirect(
                url_for("session_history", day=day, tz=tz_name)
                if day
                else url_for("session_history", tz=tz_name)
            )

        if score < 1 or score > 10:
            flash("Wake difficulty must be between 1 and 10.", "danger")
            return redirect(
                url_for("session_history", day=day, tz=tz_name)
                if day
                else url_for("session_history", tz=tz_name)
            )

        alarm_session.waking_difficulty = score

    try:
        db.session.commit()
        flash("Wake difficulty saved.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to save wake difficulty.", "danger")

    return redirect(
        url_for("session_history", day=day, tz=tz_name)
        if day
        else url_for("session_history", tz=tz_name)
    )


@app.route(
    "/account/session-history/alarm/<int:alarm_session_id>/delete", methods=["POST"]
)
@login_required
def delete_alarm_session(alarm_session_id):
    alarm_session = AlarmSession.query.filter_by(
        id=alarm_session_id, user_id=current_user.id
    ).first()
    day = request.form.get("day")
    tz_name = request.form.get("tz")

    if alarm_session is None:
        flash("Alarm session not found.", "danger")
        return redirect(
            url_for("session_history", day=day, tz=tz_name)
            if day
            else url_for("session_history", tz=tz_name)
        )

    try:
        # Explicitly remove child puzzle sessions so this works even on older DB schemas
        # that may not yet enforce ON DELETE CASCADE at the database level.
        PuzzleSession.query.filter_by(alarm_session_id=alarm_session.id).delete(
            synchronize_session=False
        )
        db.session.delete(alarm_session)
        db.session.commit()
        flash("Alarm session deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete alarm session.", "danger")

    return redirect(
        url_for("session_history", day=day, tz=tz_name)
        if day
        else url_for("session_history", tz=tz_name)
    )


@app.route(
    "/account/session-history/puzzle/<int:puzzle_session_id>/delete", methods=["POST"]
)
@login_required
def delete_puzzle_session(puzzle_session_id):
    puzzle_session = db.session.get(PuzzleSession, puzzle_session_id)
    day = request.form.get('day')
    tz_name = request.form.get('tz')

    if puzzle_session is None or puzzle_session.alarm_session is None:
        flash("Puzzle session not found.", "danger")
        return redirect(
            url_for("session_history", day=day, tz=tz_name)
            if day
            else url_for("session_history", tz=tz_name)
        )

    if puzzle_session.alarm_session.user_id != current_user.id:
        flash("You do not have permission to delete this puzzle session.", "danger")
        return redirect(
            url_for("session_history", day=day, tz=tz_name)
            if day
            else url_for("session_history", tz=tz_name)
        )

    try:
        db.session.delete(puzzle_session)
        db.session.commit()
        flash("Puzzle session deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete puzzle session.", "danger")

    return redirect(
        url_for("session_history", day=day, tz=tz_name)
        if day
        else url_for("session_history", tz=tz_name)
    )


@app.route("/sleep-data", methods=["GET", "POST"])
@login_required
def sleep_data():
    range_start, range_end = (
        db.session.query(
            func.min(SleepSession.start_date),
            func.max(SleepSession.end_date),
        )
        .filter(SleepSession.user_id == current_user.id)
        .first()
    )

    return render_template(
        "sleep_data.html",
        imported_range_start=range_start,
        imported_range_end=range_end,
    )


@app.route("/sleep-data/delete-all", methods=["POST"])
@login_required
def delete_all_sleep_data():
    try:
        deleted_stages = SleepStage.query.filter(
            SleepStage.user_id == current_user.id
        ).delete(synchronize_session=False)
        deleted_sessions = SleepSession.query.filter(
            SleepSession.user_id == current_user.id
        ).delete(synchronize_session=False)
        db.session.commit()
        flash(
            f"Deleted {deleted_sessions} sleep session(s) and {deleted_stages} stage record(s).",
            "success",
        )

        user_id = current_user.id

        # Train model in background without blocking
        def train_model():
            with app.app_context():
                try:
                    from app.analysis import train_user_model
                    train_user_model(user_id)
                except Exception:
                    pass
                finally:
                    db.session.remove()

        Thread(target=train_model, daemon=True).start()

    except Exception:
        db.session.rollback()
        flash("Failed to delete sleep data.", "danger")

    return redirect(url_for("sleep_data"))


@app.route("/sleep-data/update", methods=["POST"])
@login_required
@csrf.exempt
def update_sleep_data():

    # Data must be in JSON format
    if not request.is_json:
        return jsonify({"response": "failed", "message": "request must be JSON"}), 400

    payload = request.get_json(silent=True) or {}
    raw_sleep_data = payload.get("sleep_data")

    # Basic validation
    if raw_sleep_data is None:
        return jsonify({"response": "failed", "message": "missing sleep data"}), 400

    if not isinstance(raw_sleep_data, list):
        return jsonify(
            {"response": "failed", "message": "sleep data must be a list"}
        ), 400

    parsed_data = []
    for record in raw_sleep_data:
        if not isinstance(record, dict):
            continue

        try:
            stage_raw = record.get("stage")

            # Bad data, if so ignore
            if not isinstance(stage_raw, str):
                continue

            # Extract data
            stage = stage_raw.replace("HKCategoryValueSleepAnalysis", "")
            start_time = parse_apple_dt(record.get("start_date"))
            end_time = parse_apple_dt(record.get("end_date"))
            creation_date = parse_apple_dt(record.get("creation_date"))
            source_name = record.get("source_name")
        except (ValueError, TypeError):
            continue

        parsed_data.append(
            {
                "stage": stage,
                "start_time": start_time,
                "end_time": end_time,
                "source_name": source_name,
                "creation_date": creation_date,
            }
        )

    if not parsed_data:
        return jsonify(
            {"response": "failed", "message": "no valid sleep records found"}
        ), 400

    # Groups the stage data into a night session
    grouped_nights = group_sleep_records(parsed_data)
    if not grouped_nights:
        return jsonify(
            {"response": "failed", "message": "no sleep sessions grouped"}
        ), 400

    # Determine import time range
    min_date = min(r["start_time"] for r in parsed_data)
    max_date = max(r["end_time"] for r in parsed_data)

    # Delete existing sleep stages in this range
    SleepStage.query.filter(
        SleepStage.user_id == current_user.id,
        SleepStage.start_date <= max_date,
        SleepStage.end_date >= min_date,
    ).delete(synchronize_session=False)

    # Delete existing sleep sessions in this range
    SleepSession.query.filter(
        SleepSession.user_id == current_user.id,
        SleepSession.start_date <= max_date,
        SleepSession.end_date >= min_date,
    ).delete(synchronize_session=False)

    try:
        for night_records in grouped_nights:
            start_time = night_records[0]["start_time"]
            end_time = night_records[-1]["end_time"]
            total_duration = int(
                sum(
                    (r["end_time"] - r["start_time"]).total_seconds()
                    for r in night_records
                    if r["stage"].lower() != "awake"
                )
            )

            sleep_session = SleepSession()
            sleep_session.user_id = current_user.id
            sleep_session.start_date = start_time
            sleep_session.end_date = end_time
            sleep_session.total_duration = total_duration

            db.session.add(sleep_session)
            db.session.flush()

            for record in night_records:
                stage = SleepStage()
                stage.user_id = current_user.id
                stage.stage = record["stage"]
                stage.start_date = record["start_time"]
                stage.end_date = record["end_time"]
                stage.creation_date = record["creation_date"]
                stage.source_name = record["source_name"]
                stage.sleep_session_id = sleep_session.id
                db.session.add(stage)

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(
            {"response": "failed", "message": "database error while saving sleep data"}
        ), 500

    imported_range_start, imported_range_end = (
        db.session.query(
            func.min(SleepSession.start_date),
            func.max(SleepSession.end_date),
        )
        .filter(SleepSession.user_id == current_user.id)
        .first()
    )

    user_id = current_user.id

    # Train model in background without blocking
    def train_model():
        with app.app_context():
            try:
                from app.analysis import train_user_model
                train_user_model(user_id)
            except Exception:
                pass
            finally:
                db.session.remove()

    Thread(target=train_model, daemon=True).start()

    return jsonify(
        {
            "response": "ok",
            "message": f"imported {len(grouped_nights)} sleep sessions",
            "imported_range_start": imported_range_start.isoformat()
            if imported_range_start
            else None,
            "imported_range_end": imported_range_end.isoformat()
            if imported_range_end
            else None,
        }
    ), 200


@app.route("/dashboard")
@login_required
def dashboard():
    """Main user dashboard with greeting, quick actions, and an overview of alarms/devices."""
    devices = list(current_user.devices)
    alarms = Alarm.query.filter_by(user_id=current_user.id).all()
    enabled_alarms = [alarm for alarm in alarms if getattr(alarm, "enabled", True)]

    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    online_device_count = sum(1 for device in devices if device.is_online())

    next_alarm = None
    if enabled_alarms:
        now = utc_now()
        current_day = now.weekday()
        current_minutes = now.hour * 60 + now.minute

        def minutes_until_alarm(alarm_obj):
            alarm_day = int(getattr(alarm_obj, "day_of_week", 0))
            day_offset = (alarm_day - current_day) % 7
            alarm_minutes = alarm_obj.time.hour * 60 + alarm_obj.time.minute
            delta = (day_offset * 24 * 60) + (alarm_minutes - current_minutes)
            if delta <= 0:
                delta += 7 * 24 * 60
            return delta

        next_alarm = min(enabled_alarms, key=minutes_until_alarm)

    # Build a lightweight preview list ordered by weekday then time.
    sorted_alarms = sorted(
        alarms,
        key=lambda alarm_obj: (
            int(getattr(alarm_obj, "day_of_week", 0)),
            alarm_obj.time,
        ),
    )
    alarm_preview = []
    for alarm_obj in sorted_alarms[:5]:
        day_idx = int(getattr(alarm_obj, "day_of_week", 0))
        day_name = weekdays[day_idx] if 0 <= day_idx < 7 else "Unknown"
        alarm_preview.append(
            {
                "id": alarm_obj.id,
                "day_name": day_name,
                "time": alarm_obj.time.strftime("%H:%M"),
                "puzzle_type": getattr(alarm_obj, "puzzle_type", "recommended"),
                "device_name": alarm_obj.device.name
                if alarm_obj.device and alarm_obj.device.name
                else alarm_obj.device_serial,
            }
        )

    return render_template(
        "dashboard.html",
        device_count=len(devices),
        online_device_count=online_device_count,
        total_alarm_count=len(alarms),
        enabled_alarm_count=len(enabled_alarms),
        next_alarm=next_alarm,
        weekdays=weekdays,
        alarm_preview=alarm_preview,
        devices=devices,
    )


@app.route("/signup", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Dedicated registration route. Accepts GET (render form) and POST (process registration).
    Returns JSON for AJAX requests and full page redirect/flash for normal requests.
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegistrationForm()
    if form.validate_on_submit() and form.submit.data:
        # Basic server-side checks (form validators already cover many cases)
        existing = User.query.filter_by(
            email_address=(form.email_address.data or "").strip().lower()
        ).first()
        if existing:
            flash("Email already registered.", "danger")
            return render_template("register.html", register_form=form)

        if form.password.data != form.repeated_password.data:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", register_form=form)

        try:
            user = User.register(
                email_address=form.email_address.data,
                password=form.password.data,
                preferred_name=form.preferred_name.data
                if hasattr(form, "preferred_name")
                else None,
            )

            # Auto-login the new user and redirect to dashboard or `next` if provided
            login_user(user)
            next_page = request.args.get("next") or request.form.get("next")
            if next_page and isinstance(next_page, str) and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        except ValueError as ve:
            # Likely duplicate email surfaced from the model layer
            flash(str(ve) or "Email already registered.", "danger")
            return render_template("register.html", register_form=form)
        except Exception:
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template("register.html", register_form=form)

    # GET or validation errors
    return render_template("register.html", register_form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/pair-device", methods=["GET", "POST"])
@login_required
def pair_device():
    """
    Pair device page where users will enter the code displayed on their device
    :return: Redirect/template for page
    """
    pairing_form = PairDeviceForm()

    # If the form was submitted, validate and either pair the device or
    # re-render the form with errors so the user can see field-level messages.
    if pairing_form.validate_on_submit() and pairing_form.pairing_code.data:
        code = pairing_form.pairing_code.data.strip().upper()
        device = Device.query.filter_by(pairing_code=code).first()

        if (
            device is None
            or not device.pairing_expiry
            or _is_expired(device.pairing_expiry)
        ):
            flash(
                "Invalid or expired pairing code. Enter the code on your device.",
                "danger",
            )
            return render_template("pair_device.html", pairing_form=pairing_form)

        device.pair(current_user.id)
        flash("Device paired successfully.", "success")
        return redirect(url_for("account"))

    # GET or validation error -> render the pairing page with the form instance
    return render_template("pair_device.html", pairing_form=pairing_form)


@app.route("/alarms", methods=["GET"])
@login_required
def alarms():
    # Determine which device's alarms to view. Use GET param 'view_device'.
    view_device_serial = request.args.get("view_device", "all")

    # Prepare days mapping
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    alarms_by_day = {day: [] for day in days}

    if view_device_serial == "all" or not current_user.devices:
        # Merge alarms from all devices
        for device in current_user.devices:
            device_alarms_by_day = device.get_alarms_by_day()
            for day in days:
                alarms_by_day[day].extend(device_alarms_by_day.get(day, []))
    else:
        # Find the requested device belonging to the current user
        device = Device.query.filter_by(
            serial_number=view_device_serial, user_id=current_user.id
        ).first()
        if device:
            alarms_by_day = device.get_alarms_by_day()
        else:
            # If device not found or not belonging to user, default to empty mapping
            alarms_by_day = {day: [] for day in days}

    return render_template("alarm.html", alarms_by_day=alarms_by_day)


@app.route("/alarms/add", methods=["GET", "POST"])
@login_required
def add_alarm():
    form = AlarmForm()
    form.device.choices = [
        (d.serial_number, d.name if d.name else d.serial_number)
        for d in current_user.devices
    ]

    alarm_session_count, can_use_dynamic_alarm = _dynamic_alarm_ui_state(
        current_user.id
    )

    if request.method == "GET":
        preselected = request.args.get("device")
        if preselected and any(
            d.serial_number == preselected for d in current_user.devices
        ):
            form.device.data = preselected
        form.use_dynamic_alarm.data = False
        form.dynamic_start_time.data = ""
        form.dynamic_end_time.data = ""

    if form.validate_on_submit():
        selected_serial = form.device.data
        device = (
            Device.query.filter_by(
                serial_number=selected_serial, user_id=current_user.id
            ).first()
            if selected_serial
            else None
        )
        if device is None:
            flash("Please select one of your paired devices.", "danger")
            return render_template(
                "add_alarm.html",
                form=form,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        if form.use_dynamic_alarm.data and not can_use_dynamic_alarm:
            flash(
                "Dynamic alarms unlock after more than 10 completed alarm sessions.",
                "info",
            )
            form.use_dynamic_alarm.data = False

        dynamic_start_time = None
        dynamic_end_time = None
        alarm_time = parse_hhmm_time(form.time.data)
        if form.use_dynamic_alarm.data:
            dynamic_start_time = parse_hhmm_time(form.dynamic_start_time.data)
            dynamic_end_time = parse_hhmm_time(form.dynamic_end_time.data)
            if dynamic_start_time is None or dynamic_end_time is None:
                flash(
                    "For dynamic alarms, select a valid start and end time window.",
                    "danger",
                )
                return render_template(
                    "add_alarm.html",
                    form=form,
                    can_use_dynamic_alarm=can_use_dynamic_alarm,
                    alarm_session_count=alarm_session_count,
                )
            if alarm_time is None:
                alarm_time = dynamic_start_time
        elif alarm_time is None:
            flash("Please choose a valid time (HH:MM).", "danger")
            return render_template(
                "add_alarm.html",
                form=form,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        selected_days = sorted(set(form.days_of_week.data or []))
        if not selected_days:
            flash("Select at least one day.", "danger")
            return render_template(
                "add_alarm.html",
                form=form,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        dynamic_jobs = []
        try:
            for day_idx in selected_days:
                alarm = Alarm()
                alarm.device_serial = device.serial_number
                alarm.user_id = current_user.id
                alarm.time = alarm_time
                alarm.day_of_week = day_idx
                alarm.enabled = True
                alarm.created_at = utc_now()
                alarm.puzzle_type = form.puzzle_type.data
                alarm.use_dynamic_alarm = bool(form.use_dynamic_alarm.data)
                alarm.dynamic_start_time = (
                    dynamic_start_time if form.use_dynamic_alarm.data else None
                )
                alarm.dynamic_end_time = (
                    dynamic_end_time if form.use_dynamic_alarm.data else None
                )
                db.session.add(alarm)
                db.session.flush()

                if form.use_dynamic_alarm.data:
                    dynamic_jobs.append(
                        {
                            "alarm_id": alarm.id,
                            "day_of_week": day_idx,
                            "preferred_time": alarm_time,
                            "dynamic_start_time": dynamic_start_time,
                            "dynamic_end_time": dynamic_end_time,
                            "expected_alarm_time": alarm.time,
                            "expected_dynamic_start_time": alarm.dynamic_start_time,
                            "expected_dynamic_end_time": alarm.dynamic_end_time,
                        }
                    )
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to add alarms. Please try again.", "danger")
            return render_template(
                "add_alarm.html",
                form=form,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        for job in dynamic_jobs:
            _schedule_dynamic_alarm_optimization(
                alarm_id=job["alarm_id"],
                user_id=current_user.id,
                day_of_week=job["day_of_week"],
                preferred_time=job["preferred_time"],
                dynamic_start_time=job["dynamic_start_time"],
                dynamic_end_time=job["dynamic_end_time"],
                expected_alarm_time=job["expected_alarm_time"],
                expected_dynamic_start_time=job["expected_dynamic_start_time"],
                expected_dynamic_end_time=job["expected_dynamic_end_time"],
            )

        if form.use_dynamic_alarm.data:
            flash(
                "Dynamic alarms saved. Optimization is running in the background.",
                "success",
            )
        else:
            flash(f"Added {len(selected_days)} alarm(s).", "success")
        return redirect(url_for("alarms", view_device=device.serial_number))

    return render_template(
        "add_alarm.html",
        form=form,
        can_use_dynamic_alarm=can_use_dynamic_alarm,
        alarm_session_count=alarm_session_count,
    )


@app.route("/alarms/<string:alarm_id>/edit", methods=["GET", "POST"])
@login_required
def edit_alarm(alarm_id):
    alarm = db.session.get(Alarm, alarm_id)
    if alarm is None:
        flash("Alarm not found.", "danger")
        return redirect(url_for("alarms"))

    if alarm.user_id != current_user.id:
        flash("You do not have permission to edit this alarm.", "danger")
        return redirect(url_for("alarms"))

    form = EditAlarmForm()
    alarm_session_count, can_use_dynamic_alarm = _dynamic_alarm_ui_state(
        current_user.id
    )
    form.device.choices = [
        (d.serial_number, d.name if d.name else d.serial_number)
        for d in current_user.devices
    ]

    if request.method == "GET":
        form.device.data = alarm.device_serial
        form.time.data = alarm.time.strftime("%H:%M") if alarm.time else ""
        form.puzzle_type.data = alarm.puzzle_type or "recommended"
        form.use_dynamic_alarm.data = bool(getattr(alarm, "use_dynamic_alarm", False))
        form.dynamic_start_time.data = (
            alarm.dynamic_start_time.strftime("%H:%M")
            if getattr(alarm, "dynamic_start_time", None)
            else ""
        )
        form.dynamic_end_time.data = (
            alarm.dynamic_end_time.strftime("%H:%M")
            if getattr(alarm, "dynamic_end_time", None)
            else ""
        )

    if form.validate_on_submit():
        selected_serial = form.device.data
        device = (
            Device.query.filter_by(
                serial_number=selected_serial, user_id=current_user.id
            ).first()
            if selected_serial
            else None
        )
        if device is None:
            flash("Please select one of your paired devices.", "danger")
            return render_template(
                "edit_alarm.html",
                form=form,
                alarm=alarm,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        if form.use_dynamic_alarm.data and not can_use_dynamic_alarm:
            flash(
                "Dynamic alarms unlock after more than 10 completed alarm sessions.",
                "info",
            )
            form.use_dynamic_alarm.data = False

        dynamic_start_time = None
        dynamic_end_time = None
        alarm_time = parse_hhmm_time(form.time.data)
        if form.use_dynamic_alarm.data:
            dynamic_start_time = parse_hhmm_time(form.dynamic_start_time.data)
            dynamic_end_time = parse_hhmm_time(form.dynamic_end_time.data)
            if dynamic_start_time is None or dynamic_end_time is None:
                flash(
                    "For dynamic alarms, select a valid start and end time window.",
                    "danger",
                )
                return render_template(
                    "edit_alarm.html",
                    form=form,
                    alarm=alarm,
                    can_use_dynamic_alarm=can_use_dynamic_alarm,
                    alarm_session_count=alarm_session_count,
                )
            if alarm_time is None:
                alarm_time = dynamic_start_time
        elif alarm_time is None:
            flash("Please choose a valid time (HH:MM).", "danger")
            return render_template(
                "edit_alarm.html",
                form=form,
                alarm=alarm,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        try:
            alarm.device_serial = device.serial_number
            alarm.time = alarm_time
            alarm.puzzle_type = form.puzzle_type.data
            alarm.use_dynamic_alarm = bool(form.use_dynamic_alarm.data)
            alarm.dynamic_start_time = (
                dynamic_start_time if form.use_dynamic_alarm.data else None
            )
            alarm.dynamic_end_time = (
                dynamic_end_time if form.use_dynamic_alarm.data else None
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to update alarm. Please try again.", "danger")
            return render_template(
                "edit_alarm.html",
                form=form,
                alarm=alarm,
                can_use_dynamic_alarm=can_use_dynamic_alarm,
                alarm_session_count=alarm_session_count,
            )

        view_device = request.args.get("view_device")
        if form.use_dynamic_alarm.data:
            _schedule_dynamic_alarm_optimization(
                alarm_id=alarm.id,
                user_id=current_user.id,
                day_of_week=alarm.day_of_week,
                preferred_time=alarm_time,
                dynamic_start_time=dynamic_start_time,
                dynamic_end_time=dynamic_end_time,
                expected_alarm_time=alarm.time,
                expected_dynamic_start_time=alarm.dynamic_start_time,
                expected_dynamic_end_time=alarm.dynamic_end_time,
            )
            flash(
                "Alarm updated. Dynamic optimization is running in the background.",
                "success",
            )
        else:
            flash("Alarm updated.", "success")
        if view_device and view_device != "all":
            return redirect(url_for("alarms", view_device=view_device))
        return redirect(url_for("alarms", view_device=device.serial_number))

    return render_template(
        "edit_alarm.html",
        form=form,
        alarm=alarm,
        can_use_dynamic_alarm=can_use_dynamic_alarm,
        alarm_session_count=alarm_session_count,
    )


@app.route("/alarms/delete", methods=["POST"])
@login_required
def delete_alarm():
    """Delete an alarm by id. Only the owner (user) may delete their alarm."""
    alarm_id = request.form.get("alarm_id")
    view_device = request.form.get("view_device", "all")
    if not alarm_id:
        flash("Missing alarm id.", "danger")
        return redirect(
            url_for("alarms", view_device=view_device)
            if view_device and view_device != "all"
            else url_for("alarms")
        )

    try:
        alarm = db.session.get(Alarm, alarm_id)
    except Exception:
        alarm = None

    if alarm is None:
        flash("Alarm not found.", "danger")
        return redirect(
            url_for("alarms", view_device=view_device)
            if view_device and view_device != "all"
            else url_for("alarms")
        )

    # Ensure the current user owns the alarm
    if alarm.user_id != current_user.id:
        flash("You do not have permission to delete this alarm.", "danger")
        return redirect(
            url_for("alarms", view_device=view_device)
            if view_device and view_device != "all"
            else url_for("alarms")
        )

    # Perform deletion
    try:
        db.session.delete(alarm)
        db.session.commit()
        flash("Alarm deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete alarm.", "danger")

    if view_device and view_device != "all":
        return redirect(url_for("alarms", view_device=view_device))
    return redirect(url_for("alarms"))


@app.route("/api/alarms", methods=["GET"])
@login_required
def api_get_alarms():
    """Return alarms grouped by day for AJAX requests. Use query param view_device=<serial>|all"""
    view_device = request.args.get("view_device", "all")
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    result = {d: [] for d in days}

    if view_device == "all" or not current_user.devices:
        for device in current_user.devices:
            for day, alarms in device.get_alarms_by_day().items():
                for alarm in alarms:
                    result[day].append(
                        {
                            "id": alarm.id,
                            "time": alarm.time.strftime("%H:%M"),
                            "puzzle_type": getattr(alarm, "puzzle_type", "recommended"),
                            "use_dynamic_alarm": bool(
                                getattr(alarm, "use_dynamic_alarm", False)
                            ),
                            "dynamic_start_time": alarm.dynamic_start_time.strftime(
                                "%H:%M"
                            )
                            if getattr(alarm, "dynamic_start_time", None)
                            else None,
                            "dynamic_end_time": alarm.dynamic_end_time.strftime("%H:%M")
                            if getattr(alarm, "dynamic_end_time", None)
                            else None,
                            "device_serial": alarm.device_serial,
                            "device_name": alarm.device.name
                            if alarm.device and alarm.device.name
                            else None,
                        }
                    )
    else:
        device = Device.query.filter_by(
            serial_number=view_device, user_id=current_user.id
        ).first()
        if device:
            for day, alarms in device.get_alarms_by_day().items():
                for alarm in alarms:
                    result[day].append(
                        {
                            "id": alarm.id,
                            "time": alarm.time.strftime("%H:%M"),
                            "puzzle_type": getattr(alarm, "puzzle_type", "recommended"),
                            "use_dynamic_alarm": bool(
                                getattr(alarm, "use_dynamic_alarm", False)
                            ),
                            "dynamic_start_time": alarm.dynamic_start_time.strftime(
                                "%H:%M"
                            )
                            if getattr(alarm, "dynamic_start_time", None)
                            else None,
                            "dynamic_end_time": alarm.dynamic_end_time.strftime("%H:%M")
                            if getattr(alarm, "dynamic_end_time", None)
                            else None,
                            "device_serial": alarm.device_serial,
                            "device_name": device.name if device.name else None,
                        }
                    )

    return jsonify({"alarms_by_day": result})


@app.route("/api/alarms/create", methods=["POST"])
@login_required
def api_create_alarm():
    """Create one or more alarms via AJAX. Expects JSON: device_serial, time (HH:MM), day_of_week or days_of_week, puzzle_type."""
    data = request.get_json()
    if not data:
        return jsonify({"response": "failed", "message": "invalid request"}), 400

    device_serial = data.get("device_serial")
    time_str = data.get("time")
    day_of_week = data.get("day_of_week")
    days_of_week = data.get("days_of_week")
    puzzle_type = data.get("puzzle_type", "recommended")

    # Resolve device
    device = None
    if device_serial:
        device = Device.query.filter_by(
            serial_number=device_serial, user_id=current_user.id
        ).first()
    if device is None:
        device = current_user.devices[0] if current_user.devices else None
    if device is None:
        return jsonify({"response": "failed", "message": "no paired device"}), 400

    # Parse time
    try:
        alarm_time = datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return jsonify({"response": "failed", "message": "invalid time format"}), 400

    day_indexes = []
    raw_days = days_of_week if isinstance(days_of_week, list) else None
    if raw_days is None and day_of_week is not None:
        raw_days = [day_of_week]

    if not raw_days:
        return jsonify({"response": "failed", "message": "missing day selection"}), 400

    try:
        day_indexes = sorted({int(day) for day in raw_days})
    except Exception:
        return jsonify({"response": "failed", "message": "invalid day value"}), 400

    if any(day < 0 or day > 6 for day in day_indexes):
        return jsonify({"response": "failed", "message": "invalid day value"}), 400

    # Create new alarm
    try:
        created_alarms = []
        for day_idx in day_indexes:
            alarm = Alarm()
            alarm.device_serial = device.serial_number
            alarm.user_id = current_user.id
            alarm.time = alarm_time
            alarm.day_of_week = day_idx
            alarm.enabled = True
            alarm.created_at = utc_now()
            alarm.puzzle_type = puzzle_type
            alarm.use_dynamic_alarm = False
            alarm.dynamic_start_time = None
            alarm.dynamic_end_time = None
            db.session.add(alarm)
            created_alarms.append(alarm)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"response": "failed", "message": "db error"}), 500

    return jsonify(
        {
            "response": "ok",
            "alarms": [
                {
                    "id": alarm.id,
                    "time": alarm.time.strftime("%H:%M"),
                    "puzzle_type": alarm.puzzle_type,
                    "use_dynamic_alarm": bool(
                        getattr(alarm, "use_dynamic_alarm", False)
                    ),
                    "dynamic_start_time": alarm.dynamic_start_time.strftime("%H:%M")
                    if getattr(alarm, "dynamic_start_time", None)
                    else None,
                    "dynamic_end_time": alarm.dynamic_end_time.strftime("%H:%M")
                    if getattr(alarm, "dynamic_end_time", None)
                    else None,
                    "device_serial": alarm.device_serial,
                    "device_name": device.name if device.name else None,
                    "day_of_week": alarm.day_of_week,
                }
                for alarm in created_alarms
            ],
        }
    )


@app.route("/api/alarms/delete", methods=["POST"])
@login_required
def api_delete_alarm():
    """Delete alarm via AJAX. Expects JSON: alarm_id"""
    data = request.get_json()
    if not data or "alarm_id" not in data:
        return jsonify({"response": "failed", "message": "missing alarm_id"}), 400

    try:
        alarm_id = data.get("alarm_id")
    except Exception:
        return jsonify({"response": "failed", "message": "invalid alarm_id"}), 400

    alarm = db.session.get(Alarm, alarm_id)
    if alarm is None:
        return jsonify({"response": "failed", "message": "not found"}), 404

    if alarm.user_id != current_user.id:
        return jsonify({"response": "failed", "message": "forbidden"}), 403

    try:
        db.session.delete(alarm)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"response": "failed", "message": "db error"}), 500

    return jsonify({"response": "ok"})


# API Routes


@app.route("/api/device/request-pairing-code", methods=["POST"])
@csrf.exempt
def request_pairing_code():
    """
    API route for the device to request a code for pairing.
    :return: Will return a valid pairing code
    """
    data = request.get_json()
    if not data:
        return jsonify({"response": "failed", "message": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "failed", "message": "missing serial number"}), 400

    device = db.session.get(Device, serial_number)

    if device is None:
        device = Device.register(serial_number, None, None)

    if device.user_id is not None:
        return jsonify({"response": "failed", "message": "device already paired"}), 400

    if not device.pairing_expiry or _is_expired(device.pairing_expiry):
        device.generate_pairing_code()

    return jsonify({"pairing_code": device.pairing_code})


@app.route("/api/device/pairing-status", methods=["POST"])
@csrf.exempt
def pairing_status():
    """
    API route for the device to get the current status of the pairing process.
    :return: paired, pairing or failed depending on the pairing status
    """
    data = request.get_json()
    if not data:
        return jsonify({"response": "failed", "message": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "failed", "message": "missing serial number"}), 400

    device = db.session.get(Device, serial_number)

    if device is None:
        return jsonify(
            {"response": "failed", "message": "device never requested pairing code"}
        ), 400

    if device.user_id is not None:
        return jsonify({"response": "paired", "message": "Device already paired"})

    if device.pairing_expiry and _is_expired(device.pairing_expiry):
        return jsonify(
            {
                "response": "failed",
                "message": "Pairing code has expired. Request a new one",
            }
        ), 400

    return jsonify(
        {"response": "pairing", "message": "Waiting for user to enter pairing code"}
    )


@app.route("/api/device/get-alarms", methods=["POST"])
@csrf.exempt
def get_alarms():
    """
    API route for device to retrieve the alarms for that device/user
    :return:
    """

    data = request.get_json()
    if not data:
        return jsonify({"response": "failed", "message": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "failed", "message": "missing serial number"}), 400

    device: Device = db.session.get(Device, serial_number)
    if device is None or device.user_id is None:
        return jsonify({"response": "failed", "message": "device not paired"})

    device.update_heartbeat()

    alarms: List[Alarm] = device.get_alarms()
    return jsonify(
        {
            "alarms": [
                {
                    "id": alarm.id,
                    "time": alarm.time.strftime("%H:%M"),
                    "enabled": alarm.enabled,
                    "day_of_week": getattr(alarm, "day_of_week", 0),
                    "puzzle_type": resolve_effective_puzzle_type(alarm, device),
                    "use_dynamic_alarm": bool(
                        getattr(alarm, "use_dynamic_alarm", False)
                    ),
                    "dynamic_start_time": alarm.dynamic_start_time.strftime("%H:%M")
                    if getattr(alarm, "dynamic_start_time", None)
                    else None,
                    "dynamic_end_time": alarm.dynamic_end_time.strftime("%H:%M")
                    if getattr(alarm, "dynamic_end_time", None)
                    else None,
                    "max_snoozes": device.max_snoozes
                    if device.max_snoozes is not None
                    else 3,
                }
                for alarm in alarms
            ]
        }
    )


@app.route("/api/device/submit-complete-sessions", methods=["POST"])
@csrf.exempt
def submit_complete_sessions():
    """
    API route for a device to submit completed alarm + puzzle sessions.

    Expected payload:
    {
        "serial_number": "DEVICE123",
        "complete_sessions": {
            "alarm-session-key": {
                "triggered_at": "2026-03-29T12:00:00",
                "puzzle_sessions": [
                    {
                        "puzzle_type": "Memory",
                        "question": "1+1",
                        "is_correct": true,
                        "time_taken_seconds": 4.2,
                        "outcome_action": "dismissed"
                    }
                ],
                "waking_difficulty": 5
            }
        }
    }
    """

    # Data validation
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"response": "failed", "message": "invalid request"}), 400

    serial_number = data.get("serial_number")
    complete_sessions = data.get("complete_sessions")

    if not serial_number:
        return jsonify({"response": "failed", "message": "missing serial number"}), 400

    if complete_sessions is None:
        return jsonify(
            {"response": "failed", "message": "missing complete_sessions"}
        ), 400

    if not isinstance(complete_sessions, dict):
        return jsonify(
            {"response": "failed", "message": "complete_sessions must be an dictionary"}
        ), 400

    device: Device = db.session.get(Device, serial_number)
    if device is None or device.user_id is None:
        return jsonify({"response": "failed", "message": "device not paired"}), 400

    device.update_heartbeat()

    try:
        for _, session_data in complete_sessions.items():
            if not isinstance(session_data, dict):
                continue

            when_raw = session_data.get("when") or session_data.get("triggered_at")
            if when_raw:
                try:
                    normalized_when = str(when_raw).replace("Z", "+00:00")
                    when = datetime.fromisoformat(normalized_when)
                except (TypeError, ValueError):
                    return jsonify(
                        {"response": "failed", "message": "invalid session datetime"}
                    ), 400
            else:
                when = utc_now()

            waking_difficulty = session_data.get("waking_difficulty")
            puzzle_sessions = session_data.get("puzzle_sessions", [])
            if not isinstance(puzzle_sessions, list):
                db.session.rollback()
                return jsonify({"response": "failed", "message": "puzzle_sessions must be a list"}), 400

            alarm_session = AlarmSession.create(
                user_id=device.user_id,
                device_serial=device.serial_number,
                triggered_at=when,
                waking_difficulty=waking_difficulty,
                commit=False,
            )

            for puzzle_data in puzzle_sessions:
                if not isinstance(puzzle_data, dict):
                    continue

                puzzle_type = puzzle_data.get("puzzle_type")
                question = puzzle_data.get("question")
                if not puzzle_type or not question:
                    continue

                raw_time_taken = puzzle_data.get("time_taken_seconds", 0)
                try:
                    time_taken_seconds = int(round(float(raw_time_taken)))
                except (TypeError, ValueError):
                    time_taken_seconds = 0

                outcome_action = puzzle_data.get("outcome_action")

                PuzzleSession.create(
                    alarm_session_id=alarm_session.id,
                    puzzle_type=str(puzzle_type),
                    question=str(question),
                    is_correct=bool(puzzle_data.get("is_correct", False)),
                    time_taken_seconds=time_taken_seconds,
                    outcome_action=str(outcome_action)
                    if outcome_action is not None
                    else None,
                    commit=False,
                )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(
            {"response": "failed", "message": "db error while storing sessions"}
        ), 500

    return jsonify(
        {
            "response": "ok",
            "message": "sessions stored",
        }
    )


# Debug routes


@app.route("/debug/pair-device/<code>", methods=["GET", "POST"])
def pair_device_debug(code=None):
    """
    Debug API route for the device to pair with the testing account with the code.
    Does not rely on any forms or html.
    :param code:
    :return:
    """

    # If code exists
    if code:
        code = code.strip().upper()
        device = Device.query.filter_by(pairing_code=code).first()

        # If device does not exist or code is out of date
        if (
            device is None
            or not device.pairing_expiry
            or _is_expired(device.pairing_expiry)
        ):
            print("Invalid pairing code. Enter the code on your device.")
            return "Invalid pairing code."

        device.update_heartbeat()

        # Pair device with user
        user = User.query.filter_by(email_address="test@test.com").first()
        device.pair(user.id)
        print("Device paired successfully.")
        return "Device paired successfully."

    else:
        print("No code provided.")
        return "No code provided."


@app.route("/dev/sample-data")
def dev_sample_data():
    """
    Development utility: create a sample user, log them in, create a device, and generate sample alarms.
    """
    import random

    from flask_login import login_user

    # Create or get sample user
    email = "sampleuser@example.com"
    user = User.query.filter_by(email_address=email).first()
    if not user:
        user = User.register(email, "samplepass", "Sample User")
    # Log in the user
    login_user(user)
    # Create or get devices
    device = Device.query.filter_by(user_id=user.id).first()
    if not device:
        Device.register(serial_number="SAMPLE123", name="Jeff's Alarm", user=user)
        Device.register(serial_number="SAMPLE456", name="Bob's Alarm", user=user)

    device = (
        Device.query.filter_by(user_id=user.id)
        .order_by(Device.serial_number.asc())
        .first()
    )

    # Reset sample sessions so rerunning this route produces a consistent sample dataset size.
    existing_sessions = AlarmSession.query.filter_by(user_id=user.id).all()
    existing_session_ids = [s.id for s in existing_sessions]
    if existing_session_ids:
        PuzzleSession.query.filter(
            PuzzleSession.alarm_session_id.in_(existing_session_ids)
        ).delete(synchronize_session=False)
        AlarmSession.query.filter(AlarmSession.id.in_(existing_session_ids)).delete(
            synchronize_session=False
        )
        db.session.commit()

    # Generate 15-20 sessions on different calendar days, each between 06:00 and 10:59 UTC.
    # Earlier alarms are intentionally a bit harder (more attempts + slower solve times).
    session_count = random.randint(15, 20)
    total_puzzle_rows = 0
    snoozed_session_count = 0
    now_utc = utc_now()
    for i in range(session_count):
        day_anchor = (now_utc - timedelta(days=i + 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        hour = random.randint(6, 10)
        minute = random.randint(0, 59)
        triggered_at = day_anchor.replace(hour=hour, minute=minute)

        # 06:00 is hardest, 10:59 is easiest.
        hardness = max(0, 10 - hour)
        attempts = min(6, random.randint(1 + (hardness // 2), 2 + hardness))

        # Build a 1-10 wake difficulty target (1=easiest, 10=hardest) with light noise.
        waking_difficulty = max(1, min(10, hardness + random.randint(-1, 2)))

        alarm_session = AlarmSession(
            user_id=user.id,
            device_serial=device.serial_number,
            triggered_at=triggered_at,
            waking_difficulty=waking_difficulty,
        )
        db.session.add(alarm_session)
        db.session.flush()

        # Ensure at least some sessions represent snoozing behavior (multiple successful puzzles).
        if attempts == 1 and random.random() < 0.35:
            attempts = 2
        if attempts > 1:
            snoozed_session_count += 1

        # Earlier alarms are more error-prone; inject occasional incorrect attempts.
        incorrect_attempt_indexes = set()
        if hardness >= 3 and attempts >= 2 and random.random() < 0.6:
            incorrect_attempt_indexes.add(random.randint(0, attempts - 2))
        if hardness >= 4 and attempts >= 3 and random.random() < 0.35:
            incorrect_attempt_indexes.add(random.randint(0, attempts - 2))

        for attempt_idx in range(attempts):
            puzzle_type = random.choice(["Maths", "Memory"])
            if puzzle_type == "Maths":
                a = random.randint(1, 12)
                b = random.randint(1, 12)
                question = f"{a} + {b}"
            else:
                question = "Repeat pattern"

            # Earlier hours generally take longer.
            base_seconds = 7 + (hardness * 5)
            time_taken_seconds = max(
                3, base_seconds + random.randint(-3, 8) + (attempt_idx * 3)
            )

            # Keep final attempt correct, but allow some earlier mistakes (more common for early alarms).
            if attempt_idx == attempts - 1:
                is_correct = True
            else:
                is_correct = attempt_idx not in incorrect_attempt_indexes

            db.session.add(
                PuzzleSession(
                    alarm_session_id=alarm_session.id,
                    puzzle_type=puzzle_type,
                    question=question,
                    is_correct=is_correct,
                    time_taken_seconds=time_taken_seconds,
                )
            )
            total_puzzle_rows += 1

    db.session.commit()

    flash(
        (
            f"Sample user prepared with {session_count} alarm sessions, "
            f"{total_puzzle_rows} puzzle sessions, and {snoozed_session_count} snoozed alarms."
        ),
        "success",
    )
    return redirect(url_for("dashboard"))


@app.route("/device/<serial>/settings", methods=["GET", "POST"])
@login_required
def device_settings(serial):
    # Lookup device and ensure it belongs to current_user
    device = Device.query.filter_by(
        serial_number=serial, user_id=current_user.id
    ).first()
    if not device:
        flash("Device not found or not owned by you.", "danger")
        return redirect(url_for("account"))

    form = DeviceSettingsForm()
    if form.validate_on_submit():
        # Unpair takes precedence
        if form.unpair.data:
            try:
                device.user_id = None
                db.session.commit()
                flash("Device unpaired successfully.", "success")
                return redirect(url_for("account"))
            except Exception:
                db.session.rollback()
                flash("Failed to unpair device.", "danger")
                return redirect(url_for("device_settings", serial=serial))

        # Save name
        if form.save.data:
            try:
                device.name = form.name.data.strip() if form.name.data else None
                device.max_snoozes = form.max_snoozes.data
                db.session.commit()
                flash("Device updated.", "success")
                return redirect(url_for("account"))
            except Exception:
                db.session.rollback()
                flash("Failed to update device.", "danger")

    # Pre-fill the form on GET
    if request.method == "GET":
        form.name.data = device.name
        form.max_snoozes.data = (
            device.max_snoozes if device.max_snoozes is not None else 3
        )

    return render_template("device_settings.html", device=device, form=form)


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@app.route("/api/analytics/recommendation")
@login_required
def recommendation():

    # Retrain in the background so this API stays responsive.
    if should_retrain_model(current_user.id):
        user_id = current_user.id

        def train_model():
            with app.app_context():
                try:
                    from app.analysis import train_user_model

                    train_user_model(user_id)
                except Exception:
                    app.logger.exception("Failed background model retrain for user %s", user_id)
                finally:
                    db.session.remove()

        Thread(target=train_model, daemon=True).start()

    now = datetime.now()

    # currently recommended time will be between 6 and 10, can change this
    min_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    max_time = now.replace(hour=10, minute=0, second=0, microsecond=0)

    result = find_suitable_alarm(current_user.id, min_time, max_time)

    best = result.get("best_candidate")

    if not best:
        return {"time": None, "best_puzzle_type": None}

    puzzle_results = (
        db.session.query(
            PuzzleSession.puzzle_type,
            func.avg(PuzzleSession.is_correct.cast(db.Integer)),
        )
        .join(AlarmSession)
        .filter(AlarmSession.user_id == current_user.id)
        .group_by(PuzzleSession.puzzle_type)
        .all()
    )

    best_type = max(puzzle_results, key=lambda x: x[1])[0] if puzzle_results else None

    return {
        "time": best["candidate_time"].strftime("%H:%M"),
        "best_puzzle_type": best_type,
    }


@app.route("/api/analytics/success-over-time")
@login_required
def success_over_time():

    sessions = (
        db.session.query(AlarmSession)
        .filter_by(user_id=current_user.id)
        .order_by(AlarmSession.triggered_at.asc())
        .all()
    )

    if not sessions:
        return {"labels": [], "values": []}

    weekly = {}

    for s in sessions:
        iso = s.triggered_at.isocalendar()

        week_start = datetime.fromisocalendar(iso.year, iso.week, 1).date()

        day = s.triggered_at.date()
        snoozes = max(len(s.puzzle_sessions) - 1, 0)

        weekly.setdefault(week_start, {})
        weekly[week_start][day] = snoozes

    sorted_weeks = sorted(weekly.keys())

    first_week = sorted_weeks[0]
    last_week = sorted_weeks[-1]

    labels = []
    values = []

    current = first_week

    while current <= last_week:
        days = weekly.get(current, {})
        success_days = sum(1 for snooze in days.values() if snooze <= 1)
        week_start = current
        week_end = current + timedelta(days=6)

        labels.append(
            f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
        )

        values.append(success_days)

        current += timedelta(weeks=1)

    return {"labels": labels, "values": values}


@app.route("/api/analytics/alarm-success")
@login_required
def alarm_success():

    sessions = AlarmSession.query.filter_by(user_id=current_user.id).all()

    total = len(sessions)

    if total == 0:
        return {"labels": ["No Data"], "values": [100]}

    # calculates success rate
    success = 0

    for s in sessions:
        if all(p.is_correct for p in s.puzzle_sessions):
            success += 1

    return {
        "labels": ["Successful", "Unsuccessful"],
        "values": [success / total * 100, (total - success) / total * 100],
    }


@app.route("/api/analytics/puzzle-types")
@login_required
def puzzle_types():

    # calculates success rate per puzzle type
    results = (
        db.session.query(
            PuzzleSession.puzzle_type,
            func.avg(PuzzleSession.is_correct.cast(db.Integer)),
        )
        .join(AlarmSession)
        .filter(AlarmSession.user_id == current_user.id)
        .group_by(PuzzleSession.puzzle_type)
        .all()
    )

    return {
        "labels": [r[0] for r in results],
        "values": [round(r[1] * 100, 2) for r in results],
    }
