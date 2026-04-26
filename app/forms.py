"""
This module contains all the forms that will be referenced throughout
the .html files.
"""
from flask_wtf import FlaskForm
from wtforms.fields import SelectField
from wtforms.fields.numeric import IntegerField
from wtforms.fields.simple import EmailField, PasswordField, BooleanField, SubmitField, StringField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from wtforms import ValidationError, widgets, SelectMultipleField
from app.models import User


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
        # Don't enforce a minimum length on the login form; registration enforces length.
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

    def validate_email_address(self, field):
        # Ensure email is unique (case-insensitive)
        if User.query.filter_by(email_address=(field.data or '').strip().lower()).first():
            raise ValidationError('Email already registered.')

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
    confirmation = BooleanField('I understand this action is permanent', validators=[
        DataRequired(message='You must confirm account deletion.')
    ])
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


class ResetPreferredNameForm(FlaskForm):
    """
    Form for resetting the user's preferred name.
    """
    preferred_name = StringField('Preferred name', validators=[
        DataRequired(),
        Length(min=1, max=32)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    submit = SubmitField('Change Preferred Name')

class PairDeviceForm(FlaskForm):
    """
    Form for pairing device to user via 6-digit code
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
    time = StringField('Alarm Time')
    use_dynamic_alarm = BooleanField('Use Dynamic Alarm')
    dynamic_start_time = StringField('Dynamic Window Start')
    dynamic_end_time = StringField('Dynamic Window End')
    days_of_week = SelectMultipleField(
        'Days of Week',
        choices=[
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
            (6, 'Sunday')
        ],
        coerce=int,
        option_widget=widgets.CheckboxInput(),
        widget=widgets.ListWidget(prefix_label=False),
        validators=[]
    )
    puzzle_type = SelectField('Puzzle Type', choices=[('maths', 'Maths'), ('memory', 'Memory'), ('recommended', 'Recommended')], validators=[DataRequired()])
    submit = SubmitField('Save Alarm')

    def validate_days_of_week(self, field):
        values = field.data or []
        if not values:
            raise ValidationError('Select at least one day.')
        if any(day < 0 or day > 6 for day in values):
            raise ValidationError('Invalid day selected.')


class EditAlarmForm(FlaskForm):
    """Form for editing an existing alarm without changing its day."""
    device = SelectField('Device', choices=[])
    time = StringField('Alarm Time')
    use_dynamic_alarm = BooleanField('Use Dynamic Alarm (AI Picks Best Time)')
    dynamic_start_time = StringField('Dynamic Window Start')
    dynamic_end_time = StringField('Dynamic Window End')
    puzzle_type = SelectField('Puzzle Type', choices=[('maths', 'Maths'), ('memory', 'Memory'), ('recommended', 'Recommended')], validators=[DataRequired()])
    submit = SubmitField('Update Alarm')


class DeviceSettingsForm(FlaskForm):
    """
    Form to edit a device's display name or unpair it from the account.
    """
    name = StringField('Device name', validators=[Length(min=0, max=64)])
    max_snoozes = IntegerField('Max snoozes', validators=[DataRequired(), NumberRange(min=0, max=20)])
    save = SubmitField('Save')
    unpair = SubmitField('Unpair')


class DataPermissionsForm(FlaskForm):
    """
    Form for managing user data collection preferences.
    """
    collect_alarm_sessions = BooleanField('Collect alarm session data')
    collect_brainteaser_performance = BooleanField('Collect brainteaser performance')
    ask_waking_difficulty = BooleanField('Ask for waking difficulty')
    use_health_data = BooleanField('Use imported health data for dynamic alarm')

    submit = SubmitField('Save preferences')
