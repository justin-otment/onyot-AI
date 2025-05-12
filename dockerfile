FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg2 software-properties-common \
    build-essential libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    ca-certificates xvfb openvpn && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 and Playwright dependencies
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -D @playwright/test && \
    npx playwright install --with-deps && \
    playwright install chromium

# Copy requirement files
COPY requirements.txt pip-requirements.txt ./

# Install Python requirements
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r pip-requirements.txt

# Copy script and VPNs
COPY ["externals/VPNs", "/app/externals/VPNs"]
COPY ["Skip Tracing", "/app/Skip Tracing"]

# Set working directory
WORKDIR /app/Skip Tracing

# Run the script
ENTRYPOINT ["python", "truppl_parser.py"]
