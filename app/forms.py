"""
This module contains all the forms that will be referenced throughout
the .html files.
"""
from flask_wtf import FlaskForm
from wtforms.fields.simple import EmailField, PasswordField, BooleanField, SubmitField
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
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    repeated_password = PasswordField('Repeat Password', validators=[
        DataRequired(),
        Length(min=8)
    ])

class DeleteAccountForm(FlaskForm):
    """
    Form for deleting accounts.
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