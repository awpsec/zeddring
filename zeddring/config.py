"""Configuration settings for the Zeddring application."""

import os
from pathlib import Path

# Base directory for the application
BASE_DIR = Path(__file__).parent.parent

# Database settings
DATABASE_PATH = os.environ.get("ZEDDRING_DB_PATH", str(BASE_DIR / "zeddring_data.sqlite"))

# Scanning settings
SCAN_INTERVAL = int(os.environ.get("ZEDDRING_SCAN_INTERVAL", 60))  # seconds
SCAN_TIMEOUT = int(os.environ.get("ZEDDRING_SCAN_TIMEOUT", 10))  # seconds
MAX_RETRY_ATTEMPTS = int(os.environ.get("ZEDDRING_MAX_RETRY_ATTEMPTS", 3))
RETRY_DELAY = int(os.environ.get("ZEDDRING_RETRY_DELAY", 300))  # seconds

# Web server settings
WEB_HOST = os.environ.get("ZEDDRING_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("ZEDDRING_WEB_PORT", 5000))
DEBUG = os.environ.get("ZEDDRING_DEBUG", "False").lower() == "true" 