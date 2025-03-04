#!/bin/bash
set -e

echo "Starting Zeddring application..."

# Start D-Bus if not already running
if [ ! -e /var/run/dbus/pid ]; then
    echo "Starting D-Bus system daemon..."
    mkdir -p /var/run/dbus
    dbus-daemon --system --fork
    sleep 1
fi

# Ensure Bluetooth service is running
if command -v bluetoothd &> /dev/null; then
    echo "Starting Bluetooth service..."
    if ! pgrep -x "bluetoothd" > /dev/null; then
        bluetoothd -d &
        sleep 2
    fi
fi

# Set proper permissions for Bluetooth devices
if [ -e /dev/bluetooth ]; then
    echo "Setting Bluetooth device permissions..."
    chmod -R 777 /dev/bluetooth
fi

# Ensure hci0 is up and running
if command -v hciconfig &> /dev/null; then
    echo "Configuring Bluetooth adapter..."
    hciconfig hci0 up || echo "Failed to bring up hci0, may not exist or already up"
    sleep 1
fi

# Start the Flask application
echo "Starting Flask application..."
python -m flask run --host=0.0.0.0 --port=5000

# Keep container running
exec "$@" 