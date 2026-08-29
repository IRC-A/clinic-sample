# Multi-stage Dockerfile for The Fortified Healthcare Fleet Streamlit Web UI & Agents
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir google-adk google-genai pytest-asyncio

# Copy application source code
COPY . /app

# Cloud Run uses PORT environment variable (defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Run Streamlit on Cloud Run port
CMD streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0
