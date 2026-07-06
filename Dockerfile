# Use official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies needed for python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv to manage dependencies quickly
RUN pip install --no-cache-dir uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies into system Python
RUN uv pip install --system -r requirements.txt

# Copy application source code
COPY . .

# Expose port
EXPOSE 7860

# Run the app using python
CMD ["python", "app.py"]
