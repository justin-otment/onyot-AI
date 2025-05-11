FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

# Install system dependencies for xvfb and GUI-based Playwright execution
RUN apt-get update && apt-get install -y \
    xvfb \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libxshmfence1 \
    libgbm1

# Copy all project files into the container
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    playwright install chromium

CMD ["xvfb-run", "python", "Skip Tracing/truppl_parser.py"]
