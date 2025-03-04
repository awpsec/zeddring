FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bluez \
    bluetooth \
    libbluetooth-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create bluetooth group and set permissions
RUN addgroup --system bluetooth && \
    adduser --system --ingroup bluetooth bluetooth

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for database
RUN mkdir -p /data
ENV ZEDDRING_DB_PATH=/data/zeddring_data.sqlite

# Set permissions for Bluetooth
RUN setcap 'cap_net_raw,cap_net_admin+eip' /usr/local/bin/python3.9

# Expose web interface port
EXPOSE 5000

# Run the application
CMD ["python", "-m", "zeddring.app"] 