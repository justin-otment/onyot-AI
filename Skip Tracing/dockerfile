# Use official slim Python image
FROM python:3.11-slim

# Set environment variables for non-interactive installs
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    gnupg \
    ca-certificates \
    apt-transport-https \
    software-properties-common \
    openvpn \
    iproute2 \
    iputils-ping \
    sudo \
    nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 and npm@10
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    npm install -g npm@10

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
COPY pip-requirements.txt /app/pip-requirements.txt

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt -r pip-requirements.txt \
    && pip install --no-cache-dir "protobuf!=4.21.1,!=4.21.2,!=4.21.3,!=4.21.4,!=4.21.5,<7.0.0,>=3.20.2"

# Install Playwright and its dependencies
RUN npm install -D @playwright/test
RUN npm cache clean --force
RUN npx playwright install --with-deps
RUN playwright install chromium

# Copy script folder with space in name
COPY "Skip Tracing" "/app/Skip Tracing"

# Copy VPN configs
COPY externals/VPNs /app/externals/VPNs

# Set working directory
WORKDIR "/app/Skip Tracing"

# Run the parser script
CMD ["python", "truppl_parser.py"]
