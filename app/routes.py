"""
This module implements all the routes for the Flask application.
"""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import app, database
from app.models import User
from app.forms import LoginForm, RegistrationForm
from werkzeug.exceptions import InternalServerError


@app.route("/status")
def status():
    """
    Simple health-check route used to verify that the server is running.
    Useful for debugging or monitoring.
    """ 
    return "Server is running!"

@app.route("/", methods=["GET", "POST"])
def index():

    """
    Main entry point of the application.
    Behaviour:
    - If the user is already logged in -> show the alarm dashboard
    - If not logged in -> show the login/registration page
    """

    # If the user is authenticated, show the main alarm dashboard
    if current_user.is_authenticated:
        return render_template("alarm.html", user=current_user)
    
    # Create instances of both forms
    login_form = LoginForm()
    register_form = RegistrationForm()
    
    # If the login form was submitted and passed validation
    if login_form.validate_on_submit() and login_form.submit.data:

        # Look up the user by email
        user = User.query.filter_by(
            email_address=login_form.email_address.data).first()
        
        # Verify the password matches the stored hash
        if user and user.verify_password(login_form.password.data):

            # Log the user in using Flask-Login
            login_user(user, remember=login_form.remember_me.data)
            flash("Logged in successfully!", "success")

            # Redirect prevents form re-submission on page refresh
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password.", "danger")


    # If the registration form was submitted and passed validation
    if register_form.validate_on_submit() and register_form.submit.data:

        # Check if the email already exists
        if User.query.filter_by(email_address=register_form.email_address.data).first():
            flash("Email already registered.", "danger")
        
        # Ensure the two password fields match
        elif register_form.password.data != register_form.repeated_password.data:
            flash("Passwords do not match.", "danger")
        else:
            try:

                # Create a new user using the model helper function
                User.register(
                    email_address=register_form.email_address.data,
                    password=register_form.password.data
                )
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("index"))
            except Exception as e:

                # Catch unexpected database or server errors
                flash("An error occurred during registration. Please try again.", "danger")
        
    # Render the login/register page if user is not authenticated
    return render_template(
        "index.html",
        login_form=login_form,
        register_form=register_form
    )

@app.route("/account")
@login_required
def account():

    """
    Account management page.

    login_required ensures only authenticated users can access this route.
    If a user is not logged in, Flask-Login will redirect them to the login page.
    """
    try:
        return render_template("accounts.html", user=current_user)
    except Exception as e:

        # Raise a 500 server error if something unexpected occurs
        raise InternalServerError("An error occurred while loading the account page.")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))