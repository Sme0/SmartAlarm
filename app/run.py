"""
Simple script that runs the Flask application.
"""
import os

from app import app

if __name__ == "__main__":
    port = int(os.getenv("FLASK_HOST_PORT", 5000))
    app.run(host="0.0.0.0", debug=True, port=port, threaded=True)
