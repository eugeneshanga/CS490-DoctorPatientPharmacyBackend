# Use an official Python base image (slim for smaller size)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, including config.py
COPY . .

# Expose the port (5000 for flask-app1)
EXPOSE 5000

ENV FLASK_APP=app.py

# Set environment variables (optional, e.g., to disable debug in production)
ENV FLASK_ENV=production

# Bind Flask to 0.0.0.0 so it’s reachable from the pod network
ENV FLASK_RUN_HOST=0.0.0.0

# Run the Flask application (assuming the entry point is app.py or wsgi.py)
# If your Flask app is launched via a different command or uses gunicorn, adjust accordingly.
CMD ["flask", "run", "--port=5000"]
