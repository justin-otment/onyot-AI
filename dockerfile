# Use a lightweight Python base image
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Install Conda
RUN apt-get update && \
    apt-get install -y wget && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && \
    bash miniconda.sh -b -p /opt/conda && \
    rm miniconda.sh

ENV PATH="/opt/conda/bin:$PATH"

# Install dependencies
RUN conda install -c conda-forge --file requirements.txt -y || echo "Skipping unavailable Conda packages..."
RUN pip install --no-cache-dir asyncio playwright

# Set Skip Tracing as the working directory
WORKDIR /app/Skip\ Tracing

CMD ["python", "truppl_parser.py"]
