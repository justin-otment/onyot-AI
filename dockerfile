FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg ca-certificates xvfb lsb-release \
    libxi6 libnss3 libxss1 libdbus-glib-1-2 libgtk-3-0 \
    fonts-liberation libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libxshmfence1 libu2f-udev libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install a specific, known-good version of Google Chrome
ENV CHROME_VERSION=122.0.6261.69-1

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable=${CHROME_VERSION} && \
    rm -rf /var/lib/apt/lists/*

# Install matching ChromeDriver version
ENV CHROMEDRIVER_VERSION=122.0.6261.69

RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ["Skip Tracing", "/app/Skip Tracing"]
COPY ["externals/VPNs", "/app/externals/VPNs"]

# Default command
CMD ["xvfb-run", "-a", "python", "/app/Skip Tracing/truppl_parser.py"]
