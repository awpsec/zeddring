FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including git and bluetooth
RUN apt-get update && apt-get install -y \
    bluez \
    bluetooth \
    libbluetooth-dev \
    git \
    build-essential \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install bleak for Bluetooth scanning
RUN pip install bleak

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /data
ENV ZEDDRING_DB_PATH=/data/zeddring_data.sqlite

# Expose web port
EXPOSE 5000

# Run the application
CMD ["python", "-m", "zeddring.app"] 