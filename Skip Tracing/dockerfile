# Base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install required OS packages
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    wget \
    gnupg \
    ca-certificates \
    build-essential \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (Playwright requires it)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    npm install -g npm@10

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright + Chromium
RUN npm install -D @playwright/test && \
    npx playwright install --with-deps && \
    playwright install chromium

# Copy the "Skip Tracing" folder
COPY ["Skip Tracing", "/app/Skip Tracing"]

# Copy VPN config files (if any)
COPY externals/VPNs /app/externals/VPNs

# Set working directory
WORKDIR /app/Skip Tracing

# Set default command to run the parser
CMD ["python", "truppl_parser.py"]
