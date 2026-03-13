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
- **Python 3.12+** - required for running the application in development mode without Docker.
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
All dependencies will be automatically installed if running with Docker. If you are not running with Docker
(development mode), install the python dependencies manually:
```commandline
pip install -r requirements.txt
```

#### Physical Device
TODO: Detailed commands and steps to install dependencies and set up the environment.

### Configuration

Below are the following steps to correctly configure the project:

#### Web Application

Copy the example environment file as the basis for its .env:
```commandline
cp .env.example .env
```
This file contains configuration values such as:

- Database general details
- Database login details
- Flask secret key

If running with Docker/in production, you may ignore most of the attributes.
However, ensure you have modified the secret key and database login details
from their default values.

If running in Development Mode, ensure you change the secret key attribute from its default, and follow the instructions
inside the .env file.

#### Physical Device
TODO: Instructions on how to configure the project, including any environment variables or configuration files that need to be set.

## Running the Project

Instructions on how to run each aspect of the project:

### Web Application

#### Running with Docker (Recommended)

From the project root directory, run:
```commandline
docker compose up --build
```
This will start both the web application and the MySQL database. Once both containers are up and running,
open a browser and navigate to:
```
http://localhost:<port>
```
This will however depend on where the docker is being run, and the port you have entered into the .env file.

#### Running in Development Mode (Without Docker)

Assuming all dependencies have already been installed (as per above instructions), run the flask development
server using one of the following (depending on operating system):

```commandline
Windows -> python run_dev_server.py
MacOS/Linux -> python3 run_dev_server.py
```
Then open a browser and navigate to:
```
http://localhost:<port>
```
This mode will run using:

- The Flask development server
- A local SQLite database

This mode is intended for development and testing ONLY.

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
