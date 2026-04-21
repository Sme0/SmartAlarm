"""
This module contains the database models, including only data that Flask relies on,
and not telemetry data that will be recorded on ThingsBoard.
"""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app import database as db
from app import login_manager as lm
from app.utils import as_utc, utc_now

SUPPORTED_PUZZLE_TYPES = ("maths", "memory")
SUPPORTED_PUZZLE_OUTCOMES = ("dismissed", "snoozed")

def _stable_choice_seed(*parts) -> int:
    """
    Build a deterministic numeric seed without relying on Python's randomized hash().
    """
    joined = "|".join("" if part is None else str(part) for part in parts)
    return sum(ord(char) for char in joined)

class User(UserMixin, db.Model):
    """User model for account management."""

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(64), nullable=False, index=True, unique=True)
    preferred_name = db.Column(db.String(32), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password) -> bool:
        """
        Checks whether the provided password matches the stored password hash
        :param password: The password to verify
        :return: The result of the verification
        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def register(email_address, password, preferred_name) -> 'User':
        """
        Creates a new user account and saves it to the database.
        :param email_address: The user's unique email address
        :param password: The user's plaintext password
        :return: The newly created (and stored) User object
        """

        # Normalize inputs
        email_address = (email_address or '').strip().lower()
        if not preferred_name:
            preferred_name = email_address.split('@')[0] if '@' in email_address else email_address

        # Fill out attributes
        user = User()
        user.email_address = email_address
        user.set_password(password)
        user.preferred_name = preferred_name

        # Save to DB and handle uniqueness errors cleanly
        try:
            db.session.add(user)
            db.session.commit()
            return user
        except IntegrityError:
            db.session.rollback()
            # Surface a clear exception to callers so they can respond appropriately
            raise ValueError('email already registered')

    @staticmethod
    @lm.user_loader
    def get(user_id: int) -> 'User':
        return db.session.get(User, int(user_id))


class Device(db.Model):
    """
    Device model representing a physical alarm clock registered by the user.
    """
    __tablename__ = 'devices'
    serial_number = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(64), nullable=True)
    max_snoozes = db.Column(db.Integer, nullable=False, default=3)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    pairing_code = db.Column(db.String(6), nullable=True, unique=True)
    pairing_expiry = db.Column(db.DateTime(timezone=True), nullable=True)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship('User', backref=db.backref('devices', lazy='select'))


    @staticmethod
    def register(serial_number: str, name: Optional[str], user: Optional[User]) -> 'Device':
        """
        Creates a new device associated with the given User, and
        saves it to the database.
        :param serial_number: The device's unique identifier (hardcoded into device)
        :param name: The chosen name for the device
        :param user: The user who the device belongs to
        :return: The newly created (and stored) Device object
        """

        device = Device()
        device.serial_number = serial_number
        device.user = user
        device.name = name

        # Save to DB
        db.session.add(device)
        db.session.commit()

        return device

    def generate_pairing_code(self) -> tuple[str, datetime]:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Device.query.filter_by(pairing_code=code).first():
                break

        self.pairing_code = code
        self.pairing_expiry = utc_now() + timedelta(minutes=5)
        db.session.commit()
        return self.pairing_code, self.pairing_expiry

    def pair(self, user_id: int):
        self.user_id = user_id
        self.pairing_code = None
        self.pairing_expiry = None
        db.session.commit()

    def update_heartbeat(self):
        self.last_seen = utc_now()
        db.session.commit()

    def is_online(self) -> bool:
        last_seen_utc = as_utc(self.last_seen)
        if not last_seen_utc:
            return False
        return utc_now() - last_seen_utc < timedelta(minutes=2)

    def get_alarms(self) -> List['Alarm']:
        return Alarm.query.filter_by(device_serial=self.serial_number, user_id=self.user_id).all()
    
    def get_alarms_by_day(self):
        """
        Returns a dictionary mapping day names to lists of alarms for this device, grouped by day_of_week (0=Monday, 6=Sunday).
        """
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        alarms_by_day = {day: [] for day in days}
        alarms = self.get_alarms()
        for alarm_obj in alarms:
            day_idx = getattr(alarm_obj, 'day_of_week', 0)
            try:
                day_idx = int(day_idx)
                if 0 <= day_idx <= 6:
                    alarms_by_day[days[day_idx]].append(alarm_obj)
            except Exception:
                alarms_by_day[days[0]].append(alarm_obj)
        return alarms_by_day


class Alarm(db.Model):
    __tablename__ = 'alarms'
    id = db.Column(db.String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_serial = db.Column(db.String(64), db.ForeignKey('devices.serial_number'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    time = db.Column(db.Time, nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False, default=0)  # 0=Monday, 6=Sunday
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    puzzle_type = db.Column(db.String(16), nullable=False, default='random')
    use_dynamic_alarm = db.Column(db.Boolean, nullable=False, default=False)
    dynamic_start_time = db.Column(db.Time, nullable=True)
    dynamic_end_time = db.Column(db.Time, nullable=True)

    device = db.relationship('Device', backref=db.backref('alarms', lazy='select'))
    user = db.relationship('User', backref=db.backref('alarms', lazy='select'))

    @staticmethod
    def create(
        device_serial: str,
        user_id: str,
        time,
        day_of_week: int,
        enabled: bool,
        puzzle_type: str,
        use_dynamic_alarm: bool = False,
        dynamic_start_time=None,
        dynamic_end_time=None,
    ):
        alarm = Alarm()
        alarm.device_serial = device_serial
        alarm.user_id = user_id
        alarm.time = time
        alarm.day_of_week = day_of_week
        alarm.enabled = enabled
        alarm.created_at = utc_now()
        alarm.puzzle_type = puzzle_type
        alarm.use_dynamic_alarm = use_dynamic_alarm
        alarm.dynamic_start_time = dynamic_start_time
        alarm.dynamic_end_time = dynamic_end_time

        db.session.add(alarm)
        db.session.commit()
        return alarm

class AlarmSession(db.Model):
    __tablename__ = 'alarm_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    device_serial = db.Column(db.String(64), db.ForeignKey('devices.serial_number'), nullable=False)
    waking_difficulty = db.Column(db.Integer, nullable=True)
    triggered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    @staticmethod
    def create(
        user_id: int,
        device_serial: str,
        triggered_at: datetime | None = None,
        waking_difficulty: int = None,
        commit: bool = True,
    ):
        """
        Create and persist an AlarmSession entry recording when an alarm fired.

        :param user_id: id of the user owning the device
        :param device_serial: device serial which triggered
        :param triggered_at: optional timezone-aware datetime; if omitted, now (UTC) is used
        :param commit: whether to commit immediately; use False when batching work in one transaction
        :return: the created AlarmSession instance
        """
        if triggered_at is None:
            triggered_at = datetime.now(timezone.utc)

        session = AlarmSession()
        session.user_id = user_id
        session.device_serial = device_serial
        session.triggered_at = as_utc(triggered_at) or utc_now()
        session.waking_difficulty = waking_difficulty

        db.session.add(session)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return session

class PuzzleSession(db.Model):
    __tablename__ = 'puzzle_sessions'
    id = db.Column(db.Integer, primary_key=True)
    alarm_session_id = db.Column(
        db.Integer,
        db.ForeignKey('alarm_sessions.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    puzzle_type = db.Column(db.String(16), nullable=False)
    question = db.Column(db.String(64), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    time_taken_seconds = db.Column(db.Integer, nullable=False)
    outcome_action = db.Column(db.String(16), nullable=True)

    # Let the DB perform cascade deletes; avoid ORM issuing separate DELETEs by using passive_deletes.
    alarm_session = db.relationship(
        'AlarmSession',
        backref=db.backref('puzzle_sessions', lazy='select'),
        passive_deletes=True,
        foreign_keys=[alarm_session_id],
    )

    @staticmethod
    def create(
        alarm_session_id: str,
        puzzle_type: str,
        question: str,
        is_correct: bool,
        time_taken_seconds: int,
        outcome_action: str | None = None,
        commit: bool = True,
    ):
        """
        :param alarm_session_id: id of the alarm session
        :param puzzle_type: type of puzzle
        :param question: question of the puzzle
        :param is_correct: was the answer correct
        :param time_taken_seconds: time to complete the puzzle
        :param outcome_action: what the user did immediately after the puzzle
        :param commit: whether to commit immediately; use False when batching work in one transaction
        :return:
        """
        session = PuzzleSession()
        session.alarm_session_id = alarm_session_id
        session.puzzle_type = puzzle_type
        session.question = question
        session.is_correct = is_correct
        session.time_taken_seconds = time_taken_seconds
        normalized_outcome = (outcome_action or "").strip().lower()
        session.outcome_action = normalized_outcome if normalized_outcome in SUPPORTED_PUZZLE_OUTCOMES else None
        db.session.add(session)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return session

class SleepSession(db.Model):
    __tablename__ = 'sleep_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.DateTime(timezone=True), nullable=False)
    end_date = db.Column(db.DateTime(timezone=True), nullable=False)
    total_duration = db.Column(db.Integer, nullable=False)

    sleep_stages = db.relationship(
        'SleepStage',
        back_populates='sleep_session',
        lazy='selectin',
        order_by='SleepStage.start_date',
        cascade='all, delete-orphan',
    )

class SleepStage(db.Model):
    __tablename__ = 'sleep_stages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage = db.Column(db.String(64), nullable=False)
    creation_date = db.Column(db.DateTime(timezone=True))
    start_date = db.Column(db.DateTime(timezone=True))
    end_date = db.Column(db.DateTime(timezone=True))
    source_name = db.Column(db.String(64))
    sleep_session_id = db.Column(db.Integer, db.ForeignKey('sleep_sessions.id'), nullable=False)

    sleep_session = db.relationship('SleepSession', back_populates='sleep_stages')

class DifficultyModel(db.Model):
    __tablename__ = 'difficulty_models'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    model_blob = db.Column(db.LargeBinary, nullable=False)
    last_trained = db.Column(db.DateTime(timezone=True), nullable=False)

def resolve_effective_puzzle_type(alarm: Alarm, device: Device | None = None) -> str:
    """
    Resolve the actual puzzle type that should be sent to the device.

    Stored alarms may have:
    - an explicit puzzle type such as ``maths`` or ``memory``
    - ``random`` meaning the server should choose automatically

    The automatic choice uses recent puzzle history for the same user/device:
    - avoids repeating the most recent puzzle type
    - rewards puzzle types solved correctly and quickly
    - penalizes puzzle types answered incorrectly or very slowly
    - uses a deterministic tie-breaker so "no history" does not always mean maths
    """
    stored_type = (getattr(alarm, "puzzle_type", "") or "").strip().lower()
    if stored_type in SUPPORTED_PUZZLE_TYPES:
        return stored_type

    scores = {puzzle_type: 0 for puzzle_type in SUPPORTED_PUZZLE_TYPES}
    recent_alarm_sessions_query = (
        AlarmSession.query
        .filter(AlarmSession.user_id == alarm.user_id)
        .options(selectinload(AlarmSession.puzzle_sessions))
    )

    target_device_serial = getattr(device, "serial_number", None) or getattr(alarm, "device_serial", None)
    if target_device_serial:
        recent_alarm_sessions_query = recent_alarm_sessions_query.filter(AlarmSession.device_serial == target_device_serial)

    recent_alarm_sessions = (
        recent_alarm_sessions_query
        .order_by(AlarmSession.triggered_at.desc(), AlarmSession.id.desc())
        .limit(6)
        .all()
    )

    flattened_recent_puzzles: list[PuzzleSession] = []
    for alarm_session in recent_alarm_sessions:
        flattened_recent_puzzles.extend(sorted(alarm_session.puzzle_sessions, key=lambda s: s.id, reverse=True))

    if flattened_recent_puzzles:
        last_type = (flattened_recent_puzzles[0].puzzle_type or "").strip().lower()
        if last_type in scores:
            scores[last_type] -= 3

    for index, alarm_session in enumerate(recent_alarm_sessions):
        weight = max(1, 5 - index)
        ordered_puzzle_sessions = sorted(alarm_session.puzzle_sessions, key=lambda s: s.id)
        snoozed_sessions = [
            session for session in ordered_puzzle_sessions
            if (session.outcome_action or "").strip().lower() == "snoozed"
        ]
        snooze_count = len(snoozed_sessions)

        for session in ordered_puzzle_sessions:
            session_type = (session.puzzle_type or "").strip().lower()
            if session_type not in scores:
                continue

            if session.is_correct:
                scores[session_type] += 2 * weight
                if session.time_taken_seconds is not None:
                    if session.time_taken_seconds <= 30:
                        scores[session_type] += weight
                    elif session.time_taken_seconds >= 90:
                        scores[session_type] -= weight
            else:
                scores[session_type] -= 2 * weight

            outcome_action = (session.outcome_action or "").strip().lower()
            if outcome_action == "dismissed":
                scores[session_type] += 3 * weight
                if snooze_count == 0:
                    scores[session_type] += 2 * weight
            elif outcome_action == "snoozed":
                scores[session_type] -= 3 * weight
                if snooze_count > 1:
                    scores[session_type] -= (snooze_count - 1) * weight

    if getattr(alarm, "time", None) and getattr(alarm.time, "hour", 24) < 7:
        scores["memory"] += 1

    best_score = max(scores.values())
    candidates = [name for name, score in scores.items() if score == best_score]

    if len(candidates) == 1:
        return candidates[0]

    today_key = utc_now().date().isoformat()

    seed = _stable_choice_seed(
        getattr(alarm, "id", ""),
        getattr(alarm, "device_serial", ""),
        getattr(alarm, "day_of_week", ""),
        getattr(alarm, "time", ""),
        today_key,
    )
    return candidates[seed % len(candidates)]

