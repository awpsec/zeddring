"""Configuration module for Zeddring."""

import os
from pathlib import Path

# Base directory for the application
BASE_DIR = Path(__file__).parent.parent

# Database configuration
DATABASE_PATH = os.environ.get('ZEDDRING_DB_PATH', str(BASE_DIR / "zeddring_data.sqlite"))

# Web server configuration
WEB_HOST = os.environ.get('ZEDDRING_WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.environ.get('ZEDDRING_WEB_PORT', 5000))
DEBUG = os.environ.get('ZEDDRING_DEBUG', 'False').lower() == 'true'

# Bluetooth scanning configuration
SCAN_INTERVAL = int(os.environ.get('ZEDDRING_SCAN_INTERVAL', 60))
SCAN_TIMEOUT = int(os.environ.get('ZEDDRING_SCAN_TIMEOUT', 10))
MAX_RETRY_ATTEMPTS = int(os.environ.get('ZEDDRING_MAX_RETRY_ATTEMPTS', 3))
RETRY_DELAY = int(os.environ.get('ZEDDRING_RETRY_DELAY', 300))

# Ring configuration
DEFAULT_RING_NAME = os.environ.get('ZEDDRING_DEFAULT_RING_NAME', 'Colmi R02')
DEFAULT_MAC_ADDRESS = os.environ.get('ZEDDRING_DEFAULT_MAC_ADDRESS', '87:89:99:BC:B4:D5') 