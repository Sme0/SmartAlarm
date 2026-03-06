# Use Python 3.12 slim base image
FROM python:3.12-slim

# Sets working directory inside container
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code into container
COPY . .

# Expose port 8080 to match docker-compose mapping
EXPOSE 8080

# Start the Flask app with Gunicorn
ENTRYPOINT ["gunicorn", "app:app", "--bind", "0.0.0.0:8080"]
