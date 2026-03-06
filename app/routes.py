"""
This module implements all the routes for the Flask application.
"""

from flask import render_template
from app import app
from app import forms

@app.route("/status")
def status():
    return "Server is running!"
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/account")
def account():
    return render_template("accounts.html")