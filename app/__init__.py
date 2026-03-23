"""
This module initialises the Flask application, initialises extensions (login manager, etc.)
and registers application routes.
"""
import os
import tempfile

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from flask_wtf.csrf import generate_csrf

# Load environment variables from .env if present
load_dotenv()

app = Flask(__name__,)

is_development_mode = os.getenv('DEVELOPMENT_MODE', 'false').lower() == 'true'
db_user = os.getenv('MYSQL_USER')
db_password = os.getenv('MYSQL_PASSWORD')
db_host = os.getenv('MYSQL_HOST')
db_name = os.getenv('MYSQL_DATABASE')

# if is_development_mode:
#     app.instance_path=os.path.join(os.path.dirname(__file__), 'instance')

# Chooses between Production Mode and Development Mode
if not is_development_mode and db_user and db_password and db_name and db_host:
    # Hostname inside Docker Compose is 'db'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
elif is_development_mode:
    temp_dir = tempfile.gettempdir()
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(temp_dir, 'data.sqlite3')}"

    print(temp_dir)
    print(os.path.join(temp_dir, 'data.sqlite3'))
else:
    raise ValueError("Production mode requires all .env fields to be completed.")

# Secret key for sessions (can be set in .env)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-key")

# Initialisation
login_manager = LoginManager(app)
database = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Provide a `csrf_token()` helper to templates (used for AJAX/meta tag)
@app.context_processor
def inject_csrf_token():
    # `generate_csrf` returns the current CSRF token; exposing it as `csrf_token` means
    # templates can call `csrf_token()` (e.g. in a meta tag) or use `csrf_token` in forms.
    return dict(csrf_token=generate_csrf)

# Redirects users to login view if route requires authentication
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access that page."
login_manager.login_message_category = "warning"

# Register application routes and database models
# Required to avoid circular imports
from app import routes
from app import models

# Initialise database
with app.app_context():
    database.create_all()