"""
This module initialises the Flask application, initialises extensions (login manager, etc.)
and registers application routes.
"""
import os.path

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

app = Flask(
    __name__,
    instance_path=os.path.join(os.path.dirname(__file__), 'instance'))

# Configure SQLAlchemy to use SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite3'

# Secret key for sessions
#TODO: Setup .env to store key
app.config['SECRET_KEY'] = "temp-key"

# Initialisation
login_manager = LoginManager(app)
database = SQLAlchemy(app)

# Redirects users to login view if route requires authentication
login_manager.login_view = 'login'

# Register application routes, database and forms models
# Required to avoid circular imports
from app import routes
from app import models