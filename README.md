# Zeddring

A comprehensive management system for Colmi R02 smart rings.

## Features

- Automatically scan for and connect to Colmi R02 rings
- Collect and store heart rate and steps data
- View historical data through a web interface
- Manage multiple rings
- Dark theme web interface

## Requirements

- Python 3.9+
- Bluetooth adapter with BLE support
- Docker (optional, for containerized deployment)

## Installation

### Using Docker (recommended)

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/zeddring.git
   cd zeddring
   ```

2. Build and start the Docker container:
   ```
   docker-compose up -d
   ```

3. Access the web interface at http://localhost:5000

### Manual Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/zeddring.git
   cd zeddring
   ```

2. Install the package:
   ```
   pip install -e .
   ```

3. Run the application:
   ```
   zeddring
   ```

4. Access the web interface at http://localhost:5000

## Usage

### Adding a Ring

1. Navigate to the dashboard
2. Enter the MAC address of your ring (e.g., 87:89:99:BC:B4:D5)
3. Optionally provide a name for the ring
4. Click "Add Ring"

### Viewing Ring Data

1. Click "View Details" on a ring from the dashboard
2. Use the time range selector to view different periods of data
3. View heart rate and steps statistics

### Managing Rings

- **Connect**: Connect to a ring to start collecting data
- **Disconnect**: Disconnect from a ring
- **Reboot**: Reboot a ring if it's not responding correctly
- **Rename**: Change the name of a ring

## Configuration

The following environment variables can be used to configure the application:

- `ZEDDRING_DB_PATH`: Path to the SQLite database file
- `ZEDDRING_SCAN_INTERVAL`: Interval between Bluetooth scans (seconds)
- `ZEDDRING_SCAN_TIMEOUT`: Timeout for Bluetooth scans (seconds)
- `ZEDDRING_MAX_RETRY_ATTEMPTS`: Maximum number of retry attempts when connecting to a ring
- `ZEDDRING_RETRY_DELAY`: Delay between retry attempts (seconds)
- `ZEDDRING_WEB_HOST`: Host for the web server
- `ZEDDRING_WEB_PORT`: Port for the web server
- `ZEDDRING_DEBUG`: Enable debug mode (True/False)

## Apple Health Integration

To send data to Apple Health:
1. Create a Shortcut in the iOS Shortcuts app
2. Use the "Get Contents of URL" action to fetch data from the Zeddring API
3. Parse the JSON response
4. Use the "Log Health Sample" action to add the data to Apple Health
5. Schedule the shortcut to run periodically

## License

MIT 