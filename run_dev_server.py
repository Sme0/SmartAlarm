"""
Simple script that runs the Flask application.
"""
import os

from app import app

if __name__ == "__main__":
    port = int(os.getenv("FLASK_HOST_PORT", 5000))
    app.run(debug=True, port=port)