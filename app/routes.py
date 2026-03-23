"""
This module implements all the routes for the Flask application.
"""
from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, database as db, login_manager, csrf
from app.models import User, Device, Alarm
from app.forms import LoginForm, RegistrationForm, PairDeviceForm, AlarmForm, EditAlarmForm, DeviceSettingsForm
from werkzeug.exceptions import InternalServerError

# Return JSON 401 for API/AJAX requests, otherwise redirect to the login page.
@login_manager.unauthorized_handler
def unauthorized_callback():
    from flask import request, redirect, url_for, flash, jsonify

    # If client expects JSON (AJAX / API), return a 401 JSON response.
    wants_json = False
    # Prefer explicit JSON content type or common AJAX header
    if request.is_json:
        wants_json = True
    elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        wants_json = True
    else:
        # also check Accept header
        best = request.accept_mimetypes.best
        if best and 'json' in best:
            wants_json = True

    if wants_json:
        return jsonify({'response': 'unauthenticated', 'message': 'authentication required'}), 401

    # For regular browser requests, flash a message and redirect to the login page.
    flash(login_manager.login_message, login_manager.login_message_category)
    # Use `next` so the user can be returned after login
    return redirect(url_for(login_manager.login_view, next=request.path))

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
    Public landing page for unauthenticated users.
    Authenticated users are redirected to their dashboard.
    """

    # Test User
    if User.query.filter_by(email_address="test@test.com").first() is None:
        User.register("test@test.com", "12345", "test")

    # If the user is authenticated, send them to the main dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    
    return render_template("home.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Dedicated login page and handler."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    login_form = LoginForm()
    if login_form.validate_on_submit() and login_form.submit.data:
        email_normalized = (login_form.email_address.data or '').strip().lower()
        user = User.query.filter_by(email_address=email_normalized).first()

        if user and user.verify_password(login_form.password.data):
            login_user(user, remember=login_form.remember_me.data)
            flash('Logged in successfully!', 'success')

            next_page = request.args.get('next') or request.form.get('next')
            if next_page and isinstance(next_page, str) and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html', login_form=login_form, auth_mode='login')

@app.route("/account")
@login_required
def account():

    """
    Account management page.

    login_required ensures only authenticated users can access this route.
    If a user is not logged in, Flask-Login will redirect them to the login page.
    """
    try:
        return render_template("account.html", user=current_user)
    except Exception as e:

        # Raise a 500 server error if something unexpected occurs
        raise InternalServerError("An error occurred while loading the account page.")


@app.route('/dashboard')
@login_required
def dashboard():
    """Main user dashboard with greeting, quick actions, and an overview of alarms/devices."""
    devices = list(current_user.devices)
    alarms = Alarm.query.filter_by(user_id=current_user.id).all()
    enabled_alarms = [alarm for alarm in alarms if getattr(alarm, 'enabled', True)]

    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    online_device_count = sum(1 for device in devices if device.is_online())

    next_alarm = None
    if enabled_alarms:
        now = datetime.now()
        current_day = now.weekday()
        current_minutes = now.hour * 60 + now.minute

        def minutes_until_alarm(alarm_obj):
            alarm_day = int(getattr(alarm_obj, 'day_of_week', 0))
            day_offset = (alarm_day - current_day) % 7
            alarm_minutes = alarm_obj.time.hour * 60 + alarm_obj.time.minute
            delta = (day_offset * 24 * 60) + (alarm_minutes - current_minutes)
            if delta <= 0:
                delta += 7 * 24 * 60
            return delta

        next_alarm = min(enabled_alarms, key=minutes_until_alarm)

    # Build a lightweight preview list ordered by weekday then time.
    sorted_alarms = sorted(alarms, key=lambda alarm_obj: (int(getattr(alarm_obj, 'day_of_week', 0)), alarm_obj.time))
    alarm_preview = []
    for alarm_obj in sorted_alarms[:5]:
        day_idx = int(getattr(alarm_obj, 'day_of_week', 0))
        day_name = weekdays[day_idx] if 0 <= day_idx < 7 else 'Unknown'
        alarm_preview.append({
            'id': alarm_obj.id,
            'day_name': day_name,
            'time': alarm_obj.time.strftime('%H:%M'),
            'puzzle_type': getattr(alarm_obj, 'puzzle_type', 'random'),
            'device_name': alarm_obj.device.name if alarm_obj.device and alarm_obj.device.name else alarm_obj.device_serial
        })

    return render_template(
        'dashboard.html',
        device_count=len(devices),
        online_device_count=online_device_count,
        total_alarm_count=len(alarms),
        enabled_alarm_count=len(enabled_alarms),
        next_alarm=next_alarm,
        weekdays=weekdays,
        alarm_preview=alarm_preview,
        devices=devices,
    )



@app.route('/signup', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Dedicated registration route. Accepts GET (render form) and POST (process registration).
    Returns JSON for AJAX requests and full page redirect/flash for normal requests.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit() and form.submit.data:
        # Basic server-side checks (form validators already cover many cases)
        existing = User.query.filter_by(email_address=(form.email_address.data or '').strip().lower()).first()
        if existing:
            flash('Email already registered.', 'danger')
            return render_template('register.html', register_form=form)

        if form.password.data != form.repeated_password.data:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', register_form=form)

        try:
            user = User.register(
                email_address=form.email_address.data,
                password=form.password.data,
                preferred_name=form.preferred_name.data if hasattr(form, 'preferred_name') else None
            )

            # Auto-login the new user and redirect to dashboard or `next` if provided
            login_user(user)
            next_page = request.args.get('next') or request.form.get('next')
            if next_page and isinstance(next_page, str) and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        except ValueError as ve:
            # Likely duplicate email surfaced from the model layer
            flash(str(ve) or 'Email already registered.', 'danger')
            return render_template('register.html', register_form=form)
        except Exception:
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', register_form=form)

    # GET or validation errors
    return render_template('register.html', register_form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/pair-device", methods=["GET", "POST"])
@login_required
def pair_device():
    """
    Pair device page where users will enter the code displayed on their device
    :return: Redirect/template for page
    """
    pairing_form = PairDeviceForm()

    # If the form was submitted, validate and either pair the device or
    # re-render the form with errors so the user can see field-level messages.
    if pairing_form.validate_on_submit() and pairing_form.pairing_code.data:
        code = pairing_form.pairing_code.data.strip().upper()
        device = Device.query.filter_by(pairing_code=code).first()

        if device is None or not device.pairing_expiry or (device.pairing_expiry < datetime.utcnow()):
            flash("Invalid or expired pairing code. Enter the code on your device.", "danger")
            return render_template('pair_device.html', pairing_form=pairing_form)

        device.pair(current_user.id)
        flash("Device paired successfully.", "success")
        return redirect(url_for('account'))

    # GET or validation error -> render the pairing page with the form instance
    return render_template('pair_device.html', pairing_form=pairing_form)


@app.route("/alarms", methods=["GET"])
@login_required
def alarms():
    # Determine which device's alarms to view. Use GET param 'view_device'.
    view_device_serial = request.args.get('view_device', 'all')

    # Prepare days mapping
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    alarms_by_day = {day: [] for day in days}

    if view_device_serial == 'all' or not current_user.devices:
        # Merge alarms from all devices
        for device in current_user.devices:
            device_alarms_by_day = device.get_alarms_by_day()
            for day in days:
                alarms_by_day[day].extend(device_alarms_by_day.get(day, []))
    else:
        # Find the requested device belonging to the current user
        device = Device.query.filter_by(serial_number=view_device_serial, user_id=current_user.id).first()
        if device:
            alarms_by_day = device.get_alarms_by_day()
        else:
            # If device not found or not belonging to user, default to empty mapping
            alarms_by_day = {day: [] for day in days}

    return render_template("alarm.html", alarms_by_day=alarms_by_day)


@app.route('/alarms/add', methods=['GET', 'POST'])
@login_required
def add_alarm():
    form = AlarmForm()
    form.device.choices = [
        (d.serial_number, d.name if d.name else d.serial_number)
        for d in current_user.devices
    ]

    if request.method == 'GET':
        preselected = request.args.get('device')
        if preselected and any(d.serial_number == preselected for d in current_user.devices):
            form.device.data = preselected

    if form.validate_on_submit():
        selected_serial = form.device.data
        device = Device.query.filter_by(serial_number=selected_serial, user_id=current_user.id).first() if selected_serial else None
        if device is None:
            flash('Please select one of your paired devices.', 'danger')
            return render_template('add_alarm.html', form=form)

        try:
            alarm_time = datetime.strptime(form.time.data, '%H:%M').time()
        except Exception:
            flash('Please choose a valid time (HH:MM).', 'danger')
            return render_template('add_alarm.html', form=form)

        selected_days = sorted(set(form.days_of_week.data or []))
        if not selected_days:
            flash('Select at least one day.', 'danger')
            return render_template('add_alarm.html', form=form)

        try:
            for day_idx in selected_days:
                alarm = Alarm()
                alarm.device_serial = device.serial_number
                alarm.user_id = current_user.id
                alarm.time = alarm_time
                alarm.day_of_week = day_idx
                alarm.enabled = True
                alarm.created_at = datetime.utcnow()
                alarm.puzzle_type = form.puzzle_type.data
                db.session.add(alarm)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Failed to add alarms. Please try again.', 'danger')
            return render_template('add_alarm.html', form=form)

        flash(f'Added {len(selected_days)} alarm(s).', 'success')
        return redirect(url_for('alarms', view_device=device.serial_number))

    return render_template('add_alarm.html', form=form)


@app.route('/alarms/<int:alarm_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_alarm(alarm_id):
    alarm = Alarm.query.get(alarm_id)
    if alarm is None:
        flash('Alarm not found.', 'danger')
        return redirect(url_for('alarms'))

    if alarm.user_id != current_user.id:
        flash('You do not have permission to edit this alarm.', 'danger')
        return redirect(url_for('alarms'))

    form = EditAlarmForm()
    form.device.choices = [
        (d.serial_number, d.name if d.name else d.serial_number)
        for d in current_user.devices
    ]

    if request.method == 'GET':
        form.device.data = alarm.device_serial
        form.time.data = alarm.time.strftime('%H:%M') if alarm.time else ''
        form.puzzle_type.data = alarm.puzzle_type or 'random'

    if form.validate_on_submit():
        selected_serial = form.device.data
        device = Device.query.filter_by(serial_number=selected_serial, user_id=current_user.id).first() if selected_serial else None
        if device is None:
            flash('Please select one of your paired devices.', 'danger')
            return render_template('edit_alarm.html', form=form, alarm=alarm)

        try:
            alarm_time = datetime.strptime(form.time.data, '%H:%M').time()
        except Exception:
            flash('Please choose a valid time (HH:MM).', 'danger')
            return render_template('edit_alarm.html', form=form, alarm=alarm)

        try:
            alarm.device_serial = device.serial_number
            alarm.time = alarm_time
            alarm.puzzle_type = form.puzzle_type.data
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Failed to update alarm. Please try again.', 'danger')
            return render_template('edit_alarm.html', form=form, alarm=alarm)

        view_device = request.args.get('view_device')
        flash('Alarm updated.', 'success')
        if view_device and view_device != 'all':
            return redirect(url_for('alarms', view_device=view_device))
        return redirect(url_for('alarms', view_device=device.serial_number))

    return render_template('edit_alarm.html', form=form, alarm=alarm)


@app.route('/alarms/delete', methods=['POST'])
@login_required
def delete_alarm():
    """Delete an alarm by id. Only the owner (user) may delete their alarm."""
    alarm_id = request.form.get('alarm_id')
    view_device = request.form.get('view_device', 'all')
    if not alarm_id:
        flash('Missing alarm id.', 'danger')
        return redirect(url_for('alarms', view_device=view_device) if view_device and view_device != 'all' else url_for('alarms'))

    try:
        alarm = Alarm.query.get(int(alarm_id))
    except Exception:
        alarm = None

    if alarm is None:
        flash('Alarm not found.', 'danger')
        return redirect(url_for('alarms', view_device=view_device) if view_device and view_device != 'all' else url_for('alarms'))

    # Ensure the current user owns the alarm
    if alarm.user_id != current_user.id:
        flash('You do not have permission to delete this alarm.', 'danger')
        return redirect(url_for('alarms', view_device=view_device) if view_device and view_device != 'all' else url_for('alarms'))

    # Perform deletion
    try:
        db.session.delete(alarm)
        db.session.commit()
        flash('Alarm deleted.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to delete alarm.', 'danger')

    if view_device and view_device != 'all':
        return redirect(url_for('alarms', view_device=view_device))
    return redirect(url_for('alarms'))


@app.route('/api/alarms', methods=['GET'])
@login_required
def api_get_alarms():
    """Return alarms grouped by day for AJAX requests. Use query param view_device=<serial>|all"""
    view_device = request.args.get('view_device', 'all')
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    result = {d: [] for d in days}

    if view_device == 'all' or not current_user.devices:
        for device in current_user.devices:
            for day, alarms in device.get_alarms_by_day().items():
                for alarm in alarms:
                    result[day].append({
                        'id': alarm.id,
                        'time': alarm.time.strftime('%H:%M'),
                        'puzzle_type': getattr(alarm, 'puzzle_type', 'random'),
                        'device_serial': alarm.device_serial,
                        'device_name': alarm.device.name if alarm.device and alarm.device.name else None
                    })
    else:
        device = Device.query.filter_by(serial_number=view_device, user_id=current_user.id).first()
        if device:
            for day, alarms in device.get_alarms_by_day().items():
                for alarm in alarms:
                    result[day].append({
                        'id': alarm.id,
                        'time': alarm.time.strftime('%H:%M'),
                        'puzzle_type': getattr(alarm, 'puzzle_type', 'random'),
                        'device_serial': alarm.device_serial,
                        'device_name': device.name if device.name else None
                    })

    return jsonify({'alarms_by_day': result})


@app.route('/api/alarms/create', methods=['POST'])
@login_required
def api_create_alarm():
    """Create one or more alarms via AJAX. Expects JSON: device_serial, time (HH:MM), day_of_week or days_of_week, puzzle_type."""
    data = request.get_json()
    if not data:
        return jsonify({'response': 'failed', 'message': 'invalid request'}), 400

    device_serial = data.get('device_serial')
    time_str = data.get('time')
    day_of_week = data.get('day_of_week')
    days_of_week = data.get('days_of_week')
    puzzle_type = data.get('puzzle_type', 'random')

    # Resolve device
    device = None
    if device_serial:
        device = Device.query.filter_by(serial_number=device_serial, user_id=current_user.id).first()
    if device is None:
        device = current_user.devices[0] if current_user.devices else None
    if device is None:
        return jsonify({'response': 'failed', 'message': 'no paired device'}), 400

    # Parse time
    try:
        alarm_time = datetime.strptime(time_str, '%H:%M').time()
    except Exception:
        return jsonify({'response': 'failed', 'message': 'invalid time format'}), 400

    day_indexes = []
    raw_days = days_of_week if isinstance(days_of_week, list) else None
    if raw_days is None and day_of_week is not None:
        raw_days = [day_of_week]

    if not raw_days:
        return jsonify({'response': 'failed', 'message': 'missing day selection'}), 400

    try:
        day_indexes = sorted({int(day) for day in raw_days})
    except Exception:
        return jsonify({'response': 'failed', 'message': 'invalid day value'}), 400

    if any(day < 0 or day > 6 for day in day_indexes):
        return jsonify({'response': 'failed', 'message': 'invalid day value'}), 400

    # Create new alarm
    try:
        created_alarms = []
        for day_idx in day_indexes:
            alarm = Alarm()
            alarm.device_serial = device.serial_number
            alarm.user_id = current_user.id
            alarm.time = alarm_time
            alarm.day_of_week = day_idx
            alarm.enabled = True
            alarm.created_at = datetime.utcnow()
            alarm.puzzle_type = puzzle_type
            db.session.add(alarm)
            created_alarms.append(alarm)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'response': 'failed', 'message': 'db error'}), 500

    return jsonify({
        'response': 'ok',
        'alarms': [
            {
                'id': alarm.id,
                'time': alarm.time.strftime('%H:%M'),
                'puzzle_type': alarm.puzzle_type,
                'device_serial': alarm.device_serial,
                'device_name': device.name if device.name else None,
                'day_of_week': alarm.day_of_week
            }
            for alarm in created_alarms
        ]
    })


@app.route('/api/alarms/delete', methods=['POST'])
@login_required
def api_delete_alarm():
    """Delete alarm via AJAX. Expects JSON: alarm_id"""
    data = request.get_json()
    if not data or 'alarm_id' not in data:
        return jsonify({'response': 'failed', 'message': 'missing alarm_id'}), 400

    try:
        alarm_id = int(data.get('alarm_id'))
    except Exception:
        return jsonify({'response': 'failed', 'message': 'invalid alarm_id'}), 400

    alarm = Alarm.query.get(alarm_id)
    if alarm is None:
        return jsonify({'response': 'failed', 'message': 'not found'}), 404

    if alarm.user_id != current_user.id:
        return jsonify({'response': 'failed', 'message': 'forbidden'}), 403

    try:
        db.session.delete(alarm)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'response': 'failed', 'message': 'db error'}), 500

    return jsonify({'response': 'ok'})




# API Routes

@app.route("/api/device/request-pairing-code", methods=["POST"])
@csrf.exempt
def request_pairing_code():
    """
    API route for the device to request a code for pairing.
    :return: Will return a valid pairing code
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "response": "failed",
            "message": "invalid request"
        }), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({
            "response": "failed",
            "message": "missing serial number"
        }), 400

    device = Device.query.get(serial_number)

    if device is None:
        device = Device.register(serial_number, None, None)

    if device.user_id is not None:
        return jsonify({
            "response": "failed",
            "message": "device already paired"
        }), 400

    if not device.pairing_expiry or device.pairing_expiry < datetime.utcnow():
        device.generate_pairing_code()

    return jsonify({
        "pairing_code": device.pairing_code
    })

@app.route("/api/device/pairing-status", methods=['POST'])
@csrf.exempt
def pairing_status():
    """
    API route for the device to get the current status of the pairing process.
    :return: paired, pairing or failed depending on the pairing status
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "response": "failed",
            "message": "invalid request"
        }), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({
            "response": "failed",
            "message": "missing serial number"
        }), 400

    device = Device.query.get(serial_number)

    if device is None:
        return jsonify({
            "response": "failed",
            "message": "device never requested pairing code"
        }), 400

    if device.user_id is not None:
        return jsonify({
            "response": "paired",
            "message": "Device already paired"
        })

    if device.pairing_expiry and device.pairing_expiry < datetime.utcnow():
        return jsonify({
            "response": "failed",
            "message": "Pairing code has expired. Request a new one"
        }), 400

    return jsonify({
        "response": "pairing",
        "message": "Waiting for user to enter pairing code"
    })

@app.route("/api/device/heartbeat", methods=['POST'])
@csrf.exempt
def heartbeat():
    """
    API route for the device to send a heartbeat update
    :return: success or failed depending on outcome
    """
    data = request.get_json()
    if not data:
        return jsonify({
            "response": "failed",
            "message": "invalid request"
        }), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({
            "response": "failed",
            "message": "missing serial number"
        }), 400

    device = Device.query.get(serial_number)
    if device:
        device.update_heartbeat()
        return jsonify({
            "response": "success",
            "message": "heartbeat recognised"
        })

    return jsonify({
        "response": "failed",
        "message": "invalid serial number"
    }), 400

@app.route("/api/device/get-alarms", methods=["POST"])
@csrf.exempt
def get_alarms():
    """
    API route for device to retrieve the alarms for that device/user
    :return:
    """

    data = request.get_json()
    if not data:
        return jsonify({
            "response": "failed",
            "message": "invalid request"
        }), 400

    serial_number = data.get("serial_number")
    if not serial_number:
        return jsonify({
            "response": "failed",
            "message": "missing serial number"
        }), 400

    device: Device = Device.query.get(serial_number)
    if device is None or device.user_id is None:
        return jsonify({
            "response": "failed",
            "message": "device not paired"
        })

    alarms: list[Alarm] = device.get_alarms()
    return jsonify({
        "alarms": [
            {
                "id": alarm.id,
                "time": alarm.time.strftime("%H:%M"),
                "enabled": alarm.enabled,
                "day_of_week": getattr(alarm, 'day_of_week', 0),
                "puzzle_type": getattr(alarm, 'puzzle_type', 'random'),
                "max_snoozes": device.max_snoozes if device.max_snoozes is not None else 3
            }
            for alarm in alarms
        ]
    })

# Debug routes

@app.route("/debug/pair-device/<code>", methods=["GET", "POST"])
def pair_device_debug(code=None):
    """
    Debug API route for the device to pair with the testing account with the code.
    Does not rely on any forms or html.
    :param code:
    :return:
    """

    # If code exists
    if code:
        code = code.strip().upper()
        device = Device.query.filter_by(pairing_code=code).first()

        # If device does not exist or code is out of date
        if (device is None
                or not device.pairing_expiry
                or (device.pairing_expiry < datetime.utcnow())):
            print("Invalid pairing code. Enter the code on your device.")
            return "Invalid pairing code."

        # Pair device with user
        user = User.query.filter_by(
            email_address="test@test.com").first()
        device.pair(user.id)
        print("Device paired successfully.")
        return "Device paired successfully."

    else:
        print("No code provided.")
        return "No code provided."


@app.route("/dev/sample-data")
def dev_sample_data():
    """
    Development utility: create a sample user, log them in, create a device, and generate sample alarms.
    """
    from app import database as db
    from flask_login import login_user
    # Create or get sample user
    email = "sampleuser@example.com"
    user = User.query.filter_by(email_address=email).first()
    if not user:
        user = User.register(email, "samplepass", "Sample User")
    # Log in the user
    login_user(user)
    # Create or get a device
    device = Device.query.filter_by(user_id=user.id).first()
    if not device:
        device = Device.register(serial_number="SAMPLE123", name="Jeff's Alarm", user=user)
        device = Device.register(serial_number="SAMPLE456", name="Bob's Alarm", user=user)
    flash("Sample user, device, and alarms created. You are now logged in as the sample user.", "success")
    return redirect(url_for("dashboard"))


@app.route('/device/<serial>/settings', methods=['GET', 'POST'])
@login_required
def device_settings(serial):
    # Lookup device and ensure it belongs to current_user
    device = Device.query.filter_by(serial_number=serial, user_id=current_user.id).first()
    if not device:
        flash('Device not found or not owned by you.', 'danger')
        return redirect(url_for('account'))

    form = DeviceSettingsForm()
    if form.validate_on_submit():
        # Unpair takes precedence
        if form.unpair.data:
            try:
                device.user_id = None
                db.session.commit()
                flash('Device unpaired successfully.', 'success')
                return redirect(url_for('account'))
            except Exception:
                db.session.rollback()
                flash('Failed to unpair device.', 'danger')
                return redirect(url_for('device_settings', serial=serial))

        # Save name
        if form.save.data:
            try:
                device.name = form.name.data.strip() if form.name.data else None
                device.max_snoozes = form.max_snoozes.data
                db.session.commit()
                flash('Device updated.', 'success')
                return redirect(url_for('account'))
            except Exception:
                db.session.rollback()
                flash('Failed to update device.', 'danger')

    # Pre-fill the form on GET
    if request.method == 'GET':
        form.name.data = device.name
        form.max_snoozes.data = device.max_snoozes if device.max_snoozes is not None else 3

    return render_template('device_settings.html', device=device, form=form)

