# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg2 software-properties-common \
    build-essential libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    ca-certificates xvfb nodejs npm openvpn \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python requirements
COPY requirements.txt pip-requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r pip-requirements.txt

# Install Playwright and Chromium with correct Node/NPM setup
RUN npm install -g npm@10 && \
    npm install -D @playwright/test && \
    npx playwright install --with-deps && \
    playwright install chromium

# Copy VPN configs
COPY externals/VPNs /app/externals/VPNs

# Copy folder with space in name
COPY ["Skip Tracing", "/app/Skip Tracing"]

# Set working directory
WORKDIR /app/Skip Tracing

# Default command to run the main script (adjust as needed)
CMD ["python", "truepeople_tracer1.py"]
