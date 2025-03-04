"""Heart rate logger module for Zeddring."""

import time
import logging
import threading
from typing import Dict, Optional
import datetime

from zeddring.database import Database
from zeddring.ring_manager import RingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.hr_logger")


class HeartRateLogger:
    """Logger for heart rate data from Colmi R02 rings."""

    def __init__(self, db: Optional[Database] = None, ring_manager: Optional[RingManager] = None):
        """Initialize the heart rate logger."""
        self.db = db or Database()
        self.ring_manager = ring_manager or RingManager(self.db)
        self.running = False
        self.logger_thread = None

    def start(self) -> None:
        """Start the heart rate logger."""
        if self.running:
            return
            
        # Make sure the ring manager is running
        if not self.ring_manager.running:
            self.ring_manager.start()
            
        self.running = True
        self.logger_thread = threading.Thread(target=self._logger_loop, daemon=True)
        self.logger_thread.start()
        
        logger.info("Heart rate logger started")

    def stop(self) -> None:
        """Stop the heart rate logger."""
        self.running = False
        logger.info("Heart rate logger stopped")

    def _logger_loop(self) -> None:
        """Continuously log heart rate data."""
        while self.running:
            try:
                # Get connected rings
                ring_status = self.ring_manager.get_ring_status()
                connected_rings = [r for r in ring_status if r['connected']]
                
                for ring in connected_rings:
                    try:
                        mac_address = ring['mac_address']
                        ring_id = ring['id']
                        
                        # Get client for this ring
                        client = self.ring_manager.clients.get(mac_address)
                        if not client:
                            continue
                            
                        # Get heart rate
                        hr_data = client.get_real_time_heart_rate()
                        if hr_data and len(hr_data) > 0:
                            # Use the last (most recent) heart rate value
                            hr_value = hr_data[-1]
                            if hr_value > 0:  # Ignore zero values
                                self.db.add_heart_rate(ring_id, hr_value)
                                logger.debug(f"Recorded heart rate for {ring['name']} ({mac_address}): {hr_value}")
                    
                    except Exception as e:
                        logger.error(f"Error logging heart rate for ring {ring['name']}: {e}")
                
                # Sleep before next logging
                time.sleep(60)  # Log every minute
                
            except Exception as e:
                logger.error(f"Error in heart rate logger loop: {e}")
                time.sleep(10)  # Short delay before retrying
