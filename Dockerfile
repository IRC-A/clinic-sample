# Multi-stage Dockerfile for The Fortified Healthcare Fleet Web UI, FastMCP Tools & Agents
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

# Execute server.py to expose FastMCP tool discovery routes and proxy Streamlit
CMD ["python", "server.py"]
