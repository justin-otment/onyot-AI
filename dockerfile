FROM python:3.11-slim

# Avoid writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies and Chrome browser with xvfb
RUN apt-get update && apt-get install -y \
    curl unzip wget gnupg ca-certificates gnupg2 software-properties-common \
    xvfb libxi6 libgconf-2-4 libnss3 libxss1 libappindicator3-1 libindicator7 \
    libdbus-glib-1-2 libgtk-3-0 fonts-liberation libasound2 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libxshmfence1 libu2f-udev libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') && \
    DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code and VPN config files
COPY ["Skip Tracing", "/app/Skip Tracing"]
COPY ["externals/VPNs", "/app/externals/VPNs"]

# Entrypoint (run with Xvfb for headless)
CMD ["xvfb-run", "-a", "python", "/app/Skip Tracing/truppl_parser.py"]
