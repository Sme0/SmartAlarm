"""
This module will contain the database models, only including data that is Flask will rely on,
and not telemetry data that will be recorded on ThingsBoard.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import database as db
from app import login_manager as lm


class User(UserMixin, db.Model):
    """User model for account management."""

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(64), nullable=False, index=True, unique=True)
    password_hash = db.Column(db.String(64))

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
    serial_number = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('devices', lazy='select'))

    @staticmethod
    def register(serial_number: int, name: str, user: User) -> 'Device':
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

        if name is None:
            device.name = f"Alarm Clock {len(user.devices)}"
        else:
            device.name = name

        # Save to DB
        db.session.add(device)
        db.session.commit()

        return device