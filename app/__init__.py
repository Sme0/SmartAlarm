"""
This module initialises the Flask application, initialises extensions (login manager, etc.)
and registers application routes.
"""

from flask import Flask

app = Flask(__name__)

#TODO: Initialise database, login manager etc.

# Register application routes and database models
from app import routes
from app import models