# Use Python 3.12 slim base image
FROM python:3.12-slim

# Sets working directory inside container
WORKDIR /app

# Copy requirements and install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code into container
COPY .. .

# Default application port across local Python, Docker and Compose
ENV FLASK_HOST_PORT=5000
ENV GUNICORN_WORKERS=2
ENV GUNICORN_THREADS=4
ENV GUNICORN_TIMEOUT=60

# Expose the default application port
EXPOSE 5000

# Start the Flask app with Gunicorn on FLASK_HOST_PORT
ENTRYPOINT ["sh", "-c", "gunicorn app:app --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-60} --bind 0.0.0.0:${FLASK_HOST_PORT:-5000}"]
