"""
This module initialises the Flask application, initialises extensions (login manager, etc.)
and registers application routes.
"""
import os
import tempfile
from urllib.parse import quote_plus

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from flask_wtf.csrf import generate_csrf

# Load environment variables from .env if present
load_dotenv()

app = Flask(__name__,)

def _missing_required(fields):
    missing = [name for name, value in fields.items() if not value]
    return ", ".join(missing) if missing else ""


def _build_database_uri():
    """
    Database config precedence:
    1) DATABASE_URL (full SQLAlchemy URL)
    2) DB_ENGINE + DB_* fields
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    db_engine = os.getenv("DB_ENGINE", "").strip().lower()

    if not db_engine:
        db_engine = "sqlite"
        print("No database configuration found in .env, Falling back to sqlite.")

    if db_engine in {"sqlite", "sqlite3"}:
        sqlite_path = os.getenv("SQLITE_PATH")

        if sqlite_path:
            if not os.path.isabs(sqlite_path):
                sqlite_path = os.path.abspath(sqlite_path)
            print(sqlite_path)
            return f"sqlite:///{sqlite_path}"

        temp_dir = tempfile.gettempdir()
        return f"sqlite:///{os.path.join(temp_dir, 'data.sqlite3')}"

    fields = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_NAME": os.getenv("DB_NAME"),
    }
    missing = _missing_required(fields)
    if missing:
        raise ValueError(f"MySQL/PostgreSQL configuration is incomplete. Missing: {missing}")

    db_user = quote_plus(fields["DB_USER"])
    db_password = quote_plus(fields["DB_PASSWORD"])

    if db_engine in {"mysql", "mariadb"}:
        db_port = os.getenv("DB_PORT", "3306")
        return (
            f"mysql+pymysql://{db_user}:{db_password}"
            f"@{fields['DB_HOST']}:{db_port}/{fields['DB_NAME']}"
        )

    if db_engine in {"postgres", "postgresql"}:
        db_port = os.getenv("DB_PORT", "5432")
        return (
            f"postgresql+psycopg2://{db_user}:{db_password}"
            f"@{fields['DB_HOST']}:{db_port}/{fields['DB_NAME']}"
        )

    raise ValueError(
        "Unsupported DB_ENGINE value. Use one of: sqlite, mysql, postgresql."
    )


app.config['SQLALCHEMY_DATABASE_URI'] = _build_database_uri()

# Secret key for sessions (can be set in .env)
if not os.getenv("SECRET_KEY"):
    raise ValueError("You must define a flask SECRET_KEY in .env")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

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

