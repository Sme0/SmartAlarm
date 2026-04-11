"""
This module contains the database models, including only data that Flask relies on,
and not telemetry data that will be recorded on ThingsBoard.
"""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from app import database as db
from app import login_manager as lm


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

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
        return User.query.get(int(user_id))


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
        self.pairing_expiry = _utc_now() + timedelta(minutes=5)
        db.session.commit()
        return self.pairing_code, self.pairing_expiry

    def pair(self, user_id: int):
        self.user_id = user_id
        self.pairing_code = None
        self.pairing_expiry = None
        db.session.commit()

    def update_heartbeat(self):
        self.last_seen = _utc_now()
        db.session.commit()

    def is_online(self) -> bool:
        if not self.last_seen:
            return False
        return _utc_now() - self.last_seen < timedelta(minutes=2)

    def get_alarms(self) -> list['Alarm']:
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
    created_at = db.Column(db.DateTime(timezone=True), default=_utc_now)
    puzzle_type = db.Column(db.String(16), nullable=False, default='random')

    device = db.relationship('Device', backref=db.backref('alarms', lazy='select'))
    user = db.relationship('User', backref=db.backref('alarms', lazy='select'))

    @staticmethod
    def create(device_serial: str, user_id: str, time, day_of_week: int, enabled: bool, puzzle_type: str):
        alarm = Alarm()
        alarm.device_serial = device_serial
        alarm.user_id = user_id
        alarm.time = time
        alarm.day_of_week = day_of_week
        alarm.enabled = enabled
        alarm.created_at = _utc_now()
        alarm.puzzle_type = puzzle_type

        db.session.add(alarm)
        db.session.commit()

class AlarmSession(db.Model):
    __tablename__ = 'alarm_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    device_serial = db.Column(db.String(64), db.ForeignKey('devices.serial_number'), nullable=False)
    triggered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utc_now)

    @staticmethod
    def create(user_id: int, device_serial: str, triggered_at: datetime | None = None):
        """
        Create and persist an AlarmSession entry recording when an alarm fired.

        :param user_id: id of the user owning the device
        :param device_serial: device serial which triggered
        :param triggered_at: optional timezone-aware datetime; if omitted, now (UTC) is used
        :return: the created AlarmSession instance
        """
        if triggered_at is None:
            triggered_at = datetime.now(timezone.utc)

        session = AlarmSession()
        session.user_id = user_id
        session.device_serial = device_serial
        session.triggered_at = triggered_at

        db.session.add(session)
        db.session.commit()
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
    ):
        """
        :param alarm_session_id: id of the alarm session
        :param puzzle_type: type of puzzle
        :param question: question of the puzzle
        :param is_correct: was the answer correct
        :param time_taken_seconds: time to complete the puzzle
        :return:
        """
        session = PuzzleSession()
        session.alarm_session_id = alarm_session_id
        session.puzzle_type = puzzle_type
        session.question = question
        session.is_correct = is_correct
        session.time_taken_seconds = time_taken_seconds
        db.session.add(session)
        db.session.commit()
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