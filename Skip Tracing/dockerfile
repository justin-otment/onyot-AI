FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system and Chromium dependencies
RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg ca-certificates build-essential \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 libxss1 \
    libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxshmfence1 \
    xvfb && rm -rf /var/lib/apt/lists/*

# Install Python dependencies and Playwright
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps

# Copy source code and VPN configs
COPY ["Skip Tracing", "/app/Skip Tracing"]
COPY ["externals/VPNs", "/app/externals/VPNs"]

# Write secrets to files and run script
CMD ["sh", "-c", "echo \"$GOOGLE_CREDENTIALS_JSON\" > credentials.json && echo \"$GOOGLE_TOKEN_JSON\" > token.json && xvfb-run -a python '/app/Skip Tracing/truppl_parser.py'"]
