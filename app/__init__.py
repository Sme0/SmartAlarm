"""
This module initialises the Flask application, initialises extensions (login manager, etc.)
and registers application routes.
"""
import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

app = Flask(
    __name__,
    instance_path=os.path.join(os.path.dirname(__file__), 'instance'))

db_user = os.getenv('MYSQL_USER')
db_password = os.getenv('MYSQL_PASSWORD')
db_host = os.getenv('MYSQL_HOST')
db_name = os.getenv('MYSQL_DATABASE')

# Use MySQL if env variables exist, else fallback to SQLite for local dev
if db_user and db_password and db_name:
    # Hostname inside Docker Compose is 'db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///data.sqlite3"

# Secret key for sessions (can be set in .env)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-key")

# Initialisation
login_manager = LoginManager(app)
database = SQLAlchemy(app)

# Redirects users to login view if route requires authentication
login_manager.login_view = 'login'

# Register application routes and database models
# Required to avoid circular imports
from app import routes
from app import models

# Initialise database
with app.app_context():
    database.create_all()