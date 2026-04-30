# Smart Alarm (Group 8)

### Overview
TODO: Add overview of project

## Folder and File Structure
TODO: A detailed description of the directory layout and the purpose of each folder and file. This helps others understand how the project is organized.

## Setup Instructions
### Prerequisites

The following software is required to run the project:

#### Web Application

- **Docker Desktop (recommended)** - required for the containerised version.
- **Python 3.12+** - required for running the application without Docker.
- **pip** - required to install dependencies without Docker.
- **Git (optional)** - for cloning the repository.

#### Physical Device

TODO: List any software, libraries, or frameworks that need to be installed before setting up the project.

### Installation

Below are the following steps to install the project:

#### Web Application

Download the project or clone the project repository, and navigate to the downloaded folder:
```commandline
git clone <repository-url>
cd <repository-root-folder>
```
All dependencies will be automatically installed if running with Docker. If you are not running with Docker, 
install the python dependencies manually:
```commandline
pip install -r app/requirements.txt
```

#### Physical Device
TODO: Detailed commands and steps to install dependencies and set up the environment.

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
TODO: Instructions on how to configure the project, including any environment variables or configuration files that need to be set.

## Running the Project

Instructions on how to run each aspect of the project:

### Web Application

#### Running with Docker (Recommended)

To run docker-compose with the local MySQL server, run:
```commandline
docker compose up --build
```

To run only Docker file and use another database of your choice, run (assuming ports are 5000):
```commandline
docker build -t alarm-app .
docker run -p 5000:5000 --env-file .env alarm-app
```

Running one of these sets of commands will start the web application, and link/start the corresponding database.
Assuming no errors occur, you may access the web application, for example using:
```
http://localhost:<port>
```
This will however depend on where the docker is being run, and the port you have entered into the .env file.

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

### Arduino setup:
Load the `ArduinoBluetooth.ino` file onto the arduino and wait for `Finished bluetooth setup` to appear.

### Raspberry Pi setup:
On the pi, open a terminal window and run:  
`git clone <repository-url>`  
`cd SmartAlarm`

Open another terminal window and run:  
`bluetoothctl`  
`remove 00:0E:EA:CF:6D:A5`  
`scan on`  
[wait for 00:0E:EA:CF:6D:A5 to show up]  
`scan off`  
`pair 00:0E:EA:CF:6D:A5`  
[pin]: `1234`  
`trust 00:0E:EA:CF:6D:A5`  
`quit`  
`sudo rfcomm connect hci0 00:0E:EA:CF:6D:A5`  

This should confirm that bluetooth is connected. Do not close this terminal window.

Return to the other terminal window and run:  
`cp alarm/.env.example .env`

Navigate to `pi/SmartAlarm/alarm` in the file explorer. Open the newly created .env file and fill in the following values:

```
DEVICE_DEBUG_MODE=False
ENABLE_LOGGING=True

BASE_URL= <the web app host ip>:<port>

REQUESTS_CA_BUNDLE=

SERIAL_NUMBER=<any integer>

DEVICE_TIMEZONE=

THINGSBOARD_ENABLED=True
THINGSBOARD_HOST=thingsboard.cd.cf.ac.uk
THINGSBOARD_ACCESS_TOKEN=abcdefghijklmnop
```

Save and exit this file. Return to the terminal window and run:  
`python3 -m alarm.main`  
If successful, this should run the alarm setup sequence, and the LCD should display a pairing code if the alarm is unpaired, or the time if it is.

## Third-Party Software and Frameworks
TODO: Provide details of any third-party software, libraries, or frameworks used in the project. This includes:
- Names and versions of the software/frameworks.
- Purpose of each third-party component.
- Links to their official documentation.

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
- Usede for database interaction

## Code Documentation
TODO: Mention any in-line code comments, docstrings, or additional documentation files that explain the code in more detail.

## Troubleshooting
TODO: Common issues that might arise during setup or usage and their solutions.
