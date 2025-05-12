# Use official Python slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies and Chromium dependencies
RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg ca-certificates build-essential \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 libxss1 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxshmfence1 \
    xvfb && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x and latest NPM
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    npm install -g npm@10

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN npm install -D @playwright/test && \
    npx playwright install --with-deps && \
    playwright install chromium

# Copy application source and VPN configs
COPY ["Skip Tracing", "/app/Skip Tracing"]
COPY ["externals/VPNs", "/app/externals/VPNs"]

# Default command: write secrets to files and run script under xvfb
CMD ["sh", "-c", "echo \"$GOOGLE_CREDENTIALS_JSON\" > credentials.json && echo \"$GOOGLE_TOKEN_JSON\" > token.json && xvfb-run -a python '/app/Skip Tracing/truppl_parser.py'"]
