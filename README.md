# SmartAlarm (Group 8)

### Overview
SmartAlarm is an alarm system designed to ensure you wake up on time through cognitive verification. It consists of two main components:
- **Flask Web Application (`/app`)**: A web app where users can create accounts, schedule alarms, pair devices, and view sleep analytics.
- **Alarm Device (`/alarm`)**: A Python-based service running on a Raspberry Pi that monitors scheduled alarms, controls hardware (LCD, buzzer, joystick), and triggers puzzles that must be solved to dismiss the alarm.

## Folder and File Structure
The project is organized into three main directories:

- **`/app` (Flask Web Application)**
  - `__init__.py`: App factory and database initialisation.
  - `run.py`: Entry point for the Flask application.
  - `models.py`: Database schemas for Users, Devices, Alarms, and Sessions.
  - `routes.py`: Logic for and not limited to authentication, device pairing, alarm management, and API routes.
  - `forms.py`: Web forms for user interaction.
  - `analysis.py`: Implementation for the dynamic alarm ML model.
  - `utils.py`: Utility functions for time data and data parsing.
  - `templates/` & `static/`: HTML templates and assets (CSS/JS).
- **`/alarm` (Raspberry Pi Alarm Device)**
  - `main.py`: Entry point and main event loop for the hardware.
  - `alarm_controller.py`: Core state machine managing alarm lifecycle.
  - `flask_api_client.py`: Handles communication with the Flask server.
  - `thingsboard_client.py`: Handles communication with the ThingsBoard server.
  - `alarm_sync.py`: Handles synchronisation between the alarm, server, and local caching.
  - `device_cache.py`: Manages local caching for offline functionality.
  - `ArduinoBluetooth.ino`: Script for Arduino Bluetooth connection.
  - `io/`: Hardware abstraction layer for GrovePi components (LCD, Buzzer, Input).
  - `puzzles/`: Logic for various wake-up games (Maths, Memory, etc.).
- **`/tests`**: Comprehensive unit and integration tests using `pytest`.

## Setup Instructions
### Prerequisites

The following software is required to run the project:

#### Web Application

- **Docker Desktop (recommended)** - required for the containerised version.
- **Python 3.12+** - required for running the application without Docker.
- **pip** - required to install dependencies without Docker.
- **Git (optional)** - for cloning the repository.

#### Physical Device

- **Python 3.7.3+** - The Python version on the IoT kit's Raspberry Pi
- **pip** - required to install dependencies
- **Git (optional)** - for cloning the repository

### Installation

Below are the following steps to install the project:

#### Web Application

Download the project or clone the project repository, and navigate to the downloaded folder:
```commandline
git clone <repository-url>
cd <repository-root-folder>
```
All dependencies will be automatically installed if running with Docker. If you are not running with Docker, 
install the Python package dependencies manually:
```commandline
pip install -r app/requirements.txt
```

#### Physical Device

Download the project or clone the project repository, and navigate to the downloaded folder:
```commandline
git clone <repository-url>
cd <repository-root-folder>
```

Install the Python package dependencies (not including Grove libraries):
```commandline
pip install -r alarm/requirements.txt
```

Please ensure, if you are not running on debug mode, that all relevant Grove libraries are installed.


### Configuration

#### Web Application

Copy the example environment file as the basis for its .env:
```commandline
cp app/.env.example .env
```

This file contains configuration values such as:

- Database details
- Flask setup

By default, the database is set to a local SQLite DB, stored inside the repository. This can be changed by modifying the
database/db fields to link the project to a production database, by either providing a database url, or filling out the
individual database details. 

If using Docker, ensure that any database url you supply resolves to an IPv4 address, unless otherwise configured.

Below is an example of specifying the docker-compose MySQL database, although these should only be used as EXAMPLE data, and be changed on deployment:
```dotenv
DATABASE_URL=

DB_ENGINE=mysql

SQLITE_PATH=

DB_USER=example_username
DB_PASSWORD=example_password
DB_HOST=db
DB_PORT=3306
DB_NAME=db

MYSQL_ROOT_PASSWORD=root_password

FLASK_HOST_PORT=5000
```

Ensure a flask secret key is entered for the application to run.

#### Physical Device

Copy the example environment file as the basis for its .env:
```commandline
cp alarm/.env.example .env
```

This file contains configuration values such as:

- Server URL
- Device serial number
- Timezone information

Here is a minimal example .env file for running the alarm:
```dotenv
DEVICE_DEBUG_MODE=False
BASE_URL=http://10.3.182.184:5000
SERIAL_NUMBER=<random string>
```
The above are **example** values, ensure the `SERIAL_NUMBER` is unique and the `BASE_URL` is valid.
Instructions for using other settings in the .env are all provided above each setting.

## Running the Project

Instructions on how to run each aspect of the project:

### Web Application

#### Running with Docker (Recommended)

To run docker-compose with the local MySQL server, run:
```commandline
docker compose up --build
```

To run only the Docker file and use another database of your choice, run (assuming ports are 5000):
```commandline
docker build -t alarm-app .
docker run -p 5000:5000 --env-file .env alarm-app
```

Running one of these sets of commands will start the web application, and link/start the corresponding database.
Assuming no errors occur, you may access the web application, for example using:
```
http://localhost:<port>
```
This will however depend on where the docker is being run and the port you have entered into the .env file.

#### Running directly with Python (Without Docker)

Assuming all dependencies have already been installed (as per above instructions), run the dedicated python script.
Please note some operating systems use `python3` instead of `python`.

```commandline
python -m app.run
```
Assuming no errors occur, you may now access the web application, for example using:
```
http://localhost:<port>
```


### Physical Device

#### Arduino setup:
Load the `ArduinoBluetooth.ino` file onto the Arduino and wait for `Finished bluetooth setup` to appear.

#### Raspberry Pi setup:

Open a new terminal window and run the following commands in order (replacing the Bluetooth address with the one from the Arduino):  
```commandline
bluetoothctl
remove 00:0E:EA:CF:6D:A5
scan on
[wait for 00:0E:EA:CF:6D:A5 to show up]  
scan off
pair 00:0E:EA:CF:6D:A5  
[pin]: 1234  
trust 00:0E:EA:CF:6D:A5  
quit
sudo rfcomm connect hci0 00:0E:EA:CF:6D:A5 
```


This should confirm that Bluetooth is connected. Do not close this terminal window.

Assuming all dependencies have already been installed (as per above instructions), return to the original terminal window
and run the dedicated python script.
Please note some operating systems use `python3` instead of `python`.

```commandline
python -m alarm.main
```

If successful, this should run the alarm setup sequence, and the LCD should display a pairing code if the alarm is unpaired, or the time if it is.

## Third-Party Software and Frameworks

#### mathgenerator 1.5.0
- https://lukew3.github.io/mathgenerator/mathgenerator.html
- Used for generating maths questions for the alarm

#### paho-mqtt 2.1.0
- https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
- Used to connect to the thingsboard dashboard for data collection and display

#### requests 2.32.4
- https://requests.readthedocs.io/en/latest/
- Used to connect the client (alarm) to the server (web app)

#### pytz
- https://pythonhosted.org/pytz/
- Used to support different timezones

#### flask 3.0.0
- https://flask.palletsprojects.com/en/stable/
- Used for web app hosting

#### flask-login 0.6.3
- https://flask-login.readthedocs.io/en/latest/
- Used for user account creation and login

#### flask-wtf 1.2.2
- https://flask-wtf.readthedocs.io/en/1.2.x/
- Used for forms on the web app

#### werkzeug 3.0.11
- https://palletsprojects.com/contributing/
- Used for password hashing and server error handling

#### wtforms 3.1.2
- https://wtforms.readthedocs.io/en/3.2.x/
- Used for web app forms

#### email_validator 2.1.1
- https://pypi.org/project/email-validator/
- Used for checking user email address validity

#### gunicord 25.1.0
- https://gunicorn.org/reference/settings/
- Used to start the web app

#### joblib 1.5.3
- https://joblib.readthedocs.io/en/stable/
- Used in user data analysis for converting the machine learning model to and from binary 

#### pymysql 1.1.2
- https://pymysql.readthedocs.io/en/latest/
- Connects the web app to the sql server

#### psycopg2-binary 2.9.10
- https://www.psycopg.org/docs/
- Adapts the database to python

#### scikit-learn 1.8.0
- https://scikit-learn.sourceforge.net/stable/documentation.html
- Used for machine learning in user data analysis

#### sqlalchemy 2.0.25
- https://www.sqlalchemy.org/
- Used for database interaction

## Code Documentation
The codebase follows standard Python documentation practices:
- **Docstrings**: Most classes and methods include docstrings explaining their purpose and parameters.
- **In-line Comments**: Complicated logic, such as data analysis, is clarified with in-line comments.

## Troubleshooting
- **GrovePi I/O Errors**: If you encounter `IOError` when running on the Pi, ensure the GrovePi is properly seated and the firmware is up to date. Check for pin conflicts in `alarm/io/input_handler.py`.
- **Timezone Mismatch**: If alarms fire at the wrong time, ensure `DEVICE_TIMEZONE` is correctly set in your `.env` file (e.g., `Europe/London`), or that the Pi is running in the correct timezone.
- **Pairing Issues**: If the device doesn't pair, verify that the `SERIAL_NUMBER` in `alarm/.env` is unique and the `BASE_URL` is accessible from the Pi.
- **Bluetooth Issues**: If Bluetooth is not working, ensure the Arduino is on and loaded with its bluetooth script, and follow the bluetooth pairing instructions above.
