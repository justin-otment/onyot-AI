# Use slim Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg2 software-properties-common \
    build-essential libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    ca-certificates xvfb nodejs npm openvpn && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt pip-requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r pip-requirements.txt

# Install Node and Playwright
RUN npm install -g npm && \
    npm install -D @playwright/test && \
    npx playwright install --with-deps && \
    playwright install chromium

# Copy VPN config
COPY externals/VPNs /app/externals/VPNs

# Copy Skip Tracing script directory (handle space in name)
COPY ["Skip Tracing", "/app/Skip Tracing"]

# Set working directory
WORKDIR "/app/Skip Tracing"

# Set entrypoint
ENTRYPOINT ["python", "truppl_parser.py"]
