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
    """Logger for heart rate data from rings."""
    
    def __init__(self, db: Database, ring_manager: RingManager):
        """Initialize the heart rate logger."""
        self.db = db
        self.ring_manager = ring_manager
        self.running = False
        self.thread = None
        self.interval = 60  # Log heart rate every 60 seconds
        
    def start(self):
        """Start the heart rate logger."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._logger_loop, daemon=True)
        self.thread.start()
        
        logger.info("Heart rate logger started")
        
    def stop(self):
        """Stop the heart rate logger."""
        self.running = False
        logger.info("Heart rate logger stopped")
        
    def _logger_loop(self):
        """Main logger loop."""
        while self.running:
            try:
                # Get all rings
                rings = self.db.get_rings()
                
                for ring in rings:
                    try:
                        # Get ring data
                        ring_data = self.ring_manager.get_ring_data(ring['id'])
                        
                        # Log heart rate if available
                        if ring_data and 'latest_heart_rate' in ring_data:
                            heart_rate = ring_data['latest_heart_rate']
                            if heart_rate and heart_rate > 0:
                                self.db.add_heart_rate(ring['id'], heart_rate)
                                logger.info(f"Logged heart rate {heart_rate} for ring {ring['id']}")
                                
                        # Log steps if available
                        if ring_data and 'latest_steps' in ring_data:
                            steps = ring_data['latest_steps']
                            if steps and steps > 0:
                                self.db.add_steps(ring['id'], steps)
                                logger.info(f"Logged steps {steps} for ring {ring['id']}")
                                
                        # Log battery if available
                        if ring_data and 'latest_battery' in ring_data:
                            battery = ring_data['latest_battery']
                            if battery is not None:
                                self.db.add_battery(ring['id'], battery)
                                logger.info(f"Logged battery {battery}% for ring {ring['id']}")
                    except Exception as e:
                        logger.error(f"Error logging data for ring {ring['id']}: {e}")
                        
                # Sleep before next log
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in logger loop: {e}")
                time.sleep(10)  # Short delay before retrying
