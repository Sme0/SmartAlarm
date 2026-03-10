"""
This module implements all the routes for the Flask application.
"""
from datetime import datetime, timedelta

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app
from app.models import User, Device
from app.forms import LoginForm, RegistrationForm, PairDeviceForm
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

@app.route("/pair-device", methods=["GET", "POST"])
@login_required
def pair_device():
    pairing_form = PairDeviceForm()

    if pairing_form.validate_on_submit():
        code = pairing_form.pairing_code.data.strip().upper()
        device = Device.query.filter_by(pairing_code=code).first()

        if (device is None
                or not device.pairing_expiry
                or (device.pairing_expiry < datetime.now())
        ):
            flash("Invalid pairing code. Enter the code on your device.", "danger")
            return redirect(url_for("pair_device"))

        device.pair(current_user.id)
        flash("Device paired successfully.", "success")
        return redirect(url_for('account'))

    # TODO: html file
    return render_template('pair_device.html', form=pairing_form)





# API Routes

@app.route("/api/device/request-pairing-code", methods=["POST"])
def request_pairing_code():
    data = request.get_json()
    if not data:
        return jsonify({"response": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "missing serial number"}), 400

    device = Device.query.get(serial_number)

    if device is None:
        device = Device.register(serial_number, None, None)

    if device.user_id is not None:
        return jsonify({
            "response": "failed"
        })

    if not device.pairing_expiry or device.pairing_expiry < datetime.now():
        device.generate_pairing_code()

    return jsonify({
        "pairing_code": device.pairing_code
    })

@app.route("/api/device/pairing-status", methods=['POST'])
def pairing_status():
    data = request.get_json()
    if not data:
        return jsonify({"response": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "missing serial number"}), 400

    device = Device.query.get(serial_number)

    if device is None:
        return jsonify({
            "pairing_status": "failed",
            "reason": "Device never requested pairing code"
        })

    if device.user_id is not None:
        return jsonify({
            "pairing_status": "paired",
            "reason": "Device already paired"
        })

    if device.pairing_expiry and device.pairing_expiry < datetime.now():
        return jsonify({
            "pairing_status": "failed",
            "reason": "Pairing code has expired. Request a new one"
        })

    return jsonify({
        "pairing_status": "pairing",
        "reason": "Waiting for user to enter pairing code"
    })

@app.route("/api/device/heartbeat", methods=['POST'])
def heartbeat():
    data = request.get_json()
    if not data:
        return jsonify({"response": "invalid request"}), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({"response": "missing serial number"}), 400

    device = Device.query.get(serial_number)
    if device:
        device.update_heartbeat()
        return jsonify({"response": "success"})

    return jsonify({"response": "failed"}), 400
