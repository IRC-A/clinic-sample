# Multi-stage Dockerfile for The Fortified Healthcare Fleet Streamlit Web UI & Agents
FROM python:3.11-slim

# Prevent interactive prompts during apt package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app

EXPOSE 8080

# Use python -m streamlit to guarantee execution regardless of PATH aliases
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
