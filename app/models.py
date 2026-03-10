"""
This module contains the database models, including only data that Flask relies on,
and not telemetry data that will be recorded on ThingsBoard.
"""
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import database as db
from app import login_manager as lm


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
    def register(email_address, password) -> 'User':
        """
        Creates a new user account and saves it to the database.
        :param email_address: The user's unique email address
        :param password: The user's plaintext password
        :return: The newly created (and stored) User object
        """

        # Fill out attributes
        user = User()
        user.email_address = email_address
        user.set_password(password)

        # Save to DB
        db.session.add(user)
        db.session.commit()

        return user

    @staticmethod
    @lm.user_loader
    def get(user_id: int) -> 'User':
        return User.query.get(int(user_id))


class Device(db.Model):
    """
    Device model representing a physical alarm clock registered by the user.
    """
    __tablename__ = 'devices'
    serial_number = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(64), nullable=True)
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

    def generate_pairing_code(self) -> (str, datetime):
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Device.query.filter_by(pairing_code=code).first():
                break

        self.pairing_code = code
        self.pairing_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.session.commit()
        return self.pairing_code, self.pairing_expiry

    def pair(self, user_id: int):
        self.user_id = user_id
        self.pairing_code = None
        self.pairing_expiry = None
        db.session.commit()

    def update_heartbeat(self):
        self.last_seen = datetime.now(timezone.utc)
        db.session.commit()

    def is_online(self) -> bool:
        if not self.last_seen:
            return False
        return datetime.now(timezone.utc) - self.last_seen < timedelta(minutes=2)