#!/usr/bin/env python3
"""Main application for Zeddring."""

import argparse
import logging
import signal
import sys
import time

from zeddring.config import WEB_HOST, WEB_PORT, DEBUG
from zeddring.database import Database
from zeddring.ring_manager import RingManager
from zeddring.hr_logger import HeartRateLogger
from zeddring.web import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.app")


def signal_handler(sig, frame):
    """Handle signals to gracefully shut down."""
    logger.info("Shutting down Zeddring...")
    sys.exit(0)


def main():
    """Run the main application."""
    parser = argparse.ArgumentParser(description='Zeddring - Colmi R02 Ring Manager')
    parser.add_argument('--no-web', action='store_true', help='Disable web interface')
    parser.add_argument('--host', type=str, default=WEB_HOST, help='Web server host')
    parser.add_argument('--port', type=int, default=WEB_PORT, help='Web server port')
    parser.add_argument('--debug', action='store_true', default=DEBUG, help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize components
    db = Database()
    ring_manager = RingManager(db)
    hr_logger = HeartRateLogger(db, ring_manager)
    
    # Start the ring manager and heart rate logger
    ring_manager.start()
    hr_logger.start()
    
    logger.info("Zeddring started")
    
    if not args.no_web:
        # Start the web server
        logger.info(f"Starting web server on {args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
    else:
        # Just keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    # Clean up
    ring_manager.stop()
    hr_logger.stop()
    logger.info("Zeddring stopped")


if __name__ == '__main__':
    main() 