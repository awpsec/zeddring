#!/usr/bin/env python3
"""Main application module for Zeddring."""

import os
import logging
import threading
import time
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.app")

# Import components
try:
    from zeddring.database import Database, init_db
    from zeddring.ring_manager import RingManager, get_ring_manager
    from zeddring.hr_logger import HeartRateLogger
    from zeddring.web import app as web_app
    from zeddring.config import WEB_HOST, WEB_PORT, DEBUG
except ImportError as e:
    logger.error(f"Error importing components: {e}")
    sys.exit(1)

def main():
    """Main entry point for the application."""
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        db = Database()
        
        # Initialize ring manager
        logger.info("Initializing ring manager...")
        ring_manager = get_ring_manager()
        ring_manager.start()
        
        # Initialize heart rate logger
        logger.info("Initializing heart rate logger...")
        hr_logger = HeartRateLogger(db, ring_manager)
        hr_logger.start()
        
        # Get configuration from environment
        host = WEB_HOST
        port = WEB_PORT
        debug = DEBUG
        
        # Start web server
        logger.info(f"Starting web server on {host}:{port} (debug={debug})...")
        web_app.config['RING_MANAGER'] = ring_manager
        web_app.config['DATABASE'] = db
        web_app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)
    finally:
        # Clean up
        if 'ring_manager' in locals():
            ring_manager.stop()
        if 'hr_logger' in locals():
            hr_logger.stop()

if __name__ == "__main__":
    main() 