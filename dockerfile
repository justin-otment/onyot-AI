
# command to build docker = docker build --no-cache -t onyot-ai .
# docker run -it --rm onyot-ai bash
# xvfb-run python Skip Tracing/truppl_parser.py
# docker exec -it onyot-ai-onyot-ai bash
# echo $TWO_CAPTCHA_API_KEY
# echo $VPN_USERNAME
# echo $VPN_PASSWORD
# run container = docker-compose up --build
# run container in detached mode = docker-compose up -d
# docker-compose down
# docker system prune -a  , to clean docker caches


FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

# Enable universe and multiverse repositories
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository universe && \
    add-apt-repository multiverse && \
    apt-get update

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    xvfb \
    openvpn \
    liblzo2-2 \
    libpkcs11-helper1 \
    iproute2 \
    iputils-ping \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxkbcommon0 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    libx11-xcb1 \
    libxshmfence1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    playwright install

# Copy VPN configuration files
COPY externals/VPNs /app/externals/VPNs

# Copy the Skip_Tracing directory into the container
COPY Skip Tracing /app/Skip Tracing

# Set the working directory
WORKDIR /app

# Run the script with xvfb
CMD ["xvfb-run", "python", "Skip Tracing/truppl_parser.py"]
