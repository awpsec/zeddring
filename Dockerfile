FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Bluetooth and D-Bus
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    bluetooth \
    libbluetooth-dev \
    dbus \
    libdbus-1-dev \
    python3-dbus \
    usbutils \
    procps \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Verify colmi_r02_client installation
RUN python -c "from colmi_r02_client import Client; print('ColmiClient successfully imported')" || echo "Warning: ColmiClient not available"

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=zeddring.web

# Run the application using the app.py entry point
CMD ["python", "-m", "zeddring.app"] 