FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && playwright install chromium

CMD ["python", "Skip Tracing/truppl_parser.py"]
