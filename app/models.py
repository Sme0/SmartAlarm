"""
This module will contain the database models, separate to the telemetry data stored on ThingsBoard.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import database as db
from app import login_manager as lm


class User(UserMixin, db.Model):
    """User model for account management."""

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(25), nullable=False, index=True, unique=True)
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
    def load_user(user_id: int):
        return User.query.get(int(user_id))



# TODO: Other database models (Device, etc.)
#       This does not include telemetry data that will be stored on ThingsBoard (e.g. sensor readings, data collected from
#       the alarm), nor per device settings such as max snoozes (will be stored as shared attributes on ThingsBoard)