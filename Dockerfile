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

# Install colmi_r02_client directly
RUN git clone https://github.com/tahnok/colmi_r02_client.git /tmp/colmi_r02_client && \
    cd /tmp/colmi_r02_client && \
    pip install -e . && \
    cd /app

# Find the package location and create a custom client class that uses the real client
RUN PACKAGE_DIR=$(python -c "import colmi_r02_client; print(colmi_r02_client.__path__[0])") && \
    echo "Package directory: $PACKAGE_DIR" && \
    mkdir -p "$PACKAGE_DIR" && \
    echo "from colmi_r02_client import *" > "$PACKAGE_DIR/custom_client.py" && \
    echo "from colmi_r02_client.client import ColmiR02Client" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "class Client:" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    def __init__(self, address):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        self.address = address" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        self.connected = False" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Creating real client for {address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        self._real_client = ColmiR02Client(address)" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def connect(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Connecting to real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        result = await self._real_client.connect()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        self.connected = result" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Connection result: {result}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return result" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def disconnect(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Disconnecting from real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        result = await self._real_client.disconnect()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        self.connected = False" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return result" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    def get_battery(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Getting battery from real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return self._real_client.get_battery()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    def get_steps(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Getting steps from real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return self._real_client.get_steps()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def get_heart_rate(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Getting heart rate from real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return await self._real_client.get_heart_rate()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def get_historical_data(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Getting historical data from real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return await self._real_client.get_historical_data()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def set_time(self, current_time):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Setting time on real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return await self._real_client.set_time(current_time)" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    async def reboot(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Rebooting real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return await self._real_client.reboot()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "    def set_ring_time(self):" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        import datetime" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        import asyncio" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        print(f'Setting time on real device at {self.address}')" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        loop = asyncio.get_event_loop()" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "        return loop.run_until_complete(self.set_time(datetime.datetime.now()))" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "" >> "$PACKAGE_DIR/custom_client.py" && \
    echo "from .custom_client import Client" >> "$PACKAGE_DIR/__init__.py"

# Simple verification that doesn't use complex Python syntax
RUN python -c "import colmi_r02_client; print('Package found at:', colmi_r02_client.__path__[0])"

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=zeddring.web

# Run the application using the app.py entry point
CMD ["python", "-m", "zeddring.app"] 