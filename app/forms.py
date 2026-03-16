"""
This module contains all the forms that will be referenced throughout
the .html files.
"""
from flask_wtf import FlaskForm
from wtforms.fields import SelectField
from wtforms.fields.simple import EmailField, PasswordField, BooleanField, SubmitField, StringField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    """
    Form for the user login page.
    """
    email_address = EmailField('Email address', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Submit')

class RegistrationForm(FlaskForm):
    """
    Form for the user registration page.
    May expand based on the information we collect from the user.
    """
    email_address = EmailField('Email address', validators=[
        DataRequired(),
        Email()
    ])
    preferred_name = StringField('Preferred name', validators=[
        DataRequired(),
        Length(min=1)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    repeated_password = PasswordField('Repeat password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    submit = SubmitField('Register')

class DeactivateAccountForm(FlaskForm):
    """
    Form for deactivating accounts.
    Requires both email and password to ensure the chosen account is the correct
    one to be deactivated, and that the user is the account's owner.
    """
    email_address = EmailField('Email address', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    confirmation = BooleanField('Are you sure?')
    submit = SubmitField('Deactivate Account')

class DeleteAccountForm(FlaskForm):
    """
    Form for deleting accounts.
    Requires both email and password to ensure the chosen account is the correct
    one to be deleted, and that the user is the account's owner.
    """
    email_address = EmailField('Email address', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    confirmation = BooleanField('Are you sure?')
    submit = SubmitField('Delete Account')

class ResetPasswordForm(FlaskForm):
    """
    Form for resetting the user's password.
    """
    old_password = PasswordField('Current Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    submit = SubmitField('Change Password')

class ResetEmailAddressForm(FlaskForm):
    """
    Form for resetting the user's email address.
    """
    new_email_address = EmailField('Email address', validators=[
        DataRequired(),
        Email()
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    submit = SubmitField('Change Email Address')

class PairDeviceForm(FlaskForm):
    """
    Form for pairing device to user via 6 digit code
    """
    pairing_code = StringField('Pairing code', validators=[
        DataRequired(),
        Length(min=6, max=6)
    ])
    submit = SubmitField('Confirm Pairing Code')

class AlarmForm(FlaskForm):
    """
    Form for creating or editing alarms.
    """
    device = SelectField('Device', choices=[])
    time = StringField('Alarm Time', validators=[DataRequired()])
    day_of_week = SelectField('Day of Week', choices=[
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], validators=[DataRequired()])
    puzzle_type = SelectField('Puzzle Type', choices=[('maths', 'Maths'), ('memory', 'Memory'), ('random', 'Random')], validators=[DataRequired()])
    submit = SubmitField('Save Alarm')
