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
cd <repository-folder>
```
All dependencies will be automatically installed if running with Docker. If you are not running with Docker, 
install the python dependencies manually:
```commandline
pip install -r requirements.txt
```

#### Physical Device
TODO: Detailed commands and steps to install dependencies and set up the environment.

### Configuration

Copy the example environment file as the basis for its .env:
```commandline
cp .env.example .env
```
This file contains configuration values such as:

- Database details
- Flask setup
- Alarm device details

#### Web Application

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
docker build -t alarm-web .
docker run -p 5000:5000 --env-file .env alarm-web
```

Running one of these sets of commands will start the web application, and link/start the corresponding database.
Assuming no errors occur, you may access the web application, for example using:
```
http://localhost:<port>
```
This will however depend on where the docker is being run, and the port you have entered into the .env file.

#### Running directly with Python (Without Docker)

Assuming all dependencies have already been installed (as per above instructions), run the dedicated python script using one
of the following (depending on operating system):

```commandline
Windows -> python web.py
MacOS/Linux -> python3 web.py
```
Assuming no errors occur, you may now access the web application, for example using:
```
http://localhost:<port>
```


### Physical Device

TODO: Explain how to run the project, including:	
- Commands to start the application.
- Instructions to run any included scripts or tools.
- Examples of expected output or behavior.

## Third-Party Software and Frameworks
TODO: Provide details of any third-party software, libraries, or frameworks used in the project. This includes:
- Names and versions of the software/frameworks.
- Purpose of each third-party component.
- Links to their official documentation.

## Code Documentation
TODO: Mention any in-line code comments, docstrings, or additional documentation files that explain the code in more detail.

## Troubleshooting
TODO: Common issues that might arise during setup or usage and their solutions.
