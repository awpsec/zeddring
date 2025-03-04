"""Heart rate logger module for Zeddring."""

import time
import logging
import threading
from typing import Dict, Optional
import datetime
import asyncio

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
        self.interval = 10  # Log heart rate every 10 seconds
        
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
                        
                        # Check if the ring is connected
                        if not ring_data.get('connected', False):
                            logger.debug(f"Ring {ring['id']} is not connected, skipping data logging")
                            continue
                            
                        # Get the client for this ring
                        mac_address = ring['mac_address'] if 'mac_address' in ring.keys() else None
                        if not mac_address or mac_address not in self.ring_manager.clients:
                            logger.debug(f"No client found for ring {ring['id']}, skipping data logging")
                            continue
                            
                        client = self.ring_manager.clients[mac_address]
                        
                        # Create a new event loop for this ring
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Get heart rate directly from the client
                        try:
                            heart_rate = loop.run_until_complete(client.get_heart_rate())
                            if heart_rate and heart_rate > 0:
                                self.db.add_heart_rate(ring['id'], heart_rate)
                                logger.info(f"Logged heart rate {heart_rate} for ring {ring['id']}")
                        except Exception as e:
                            logger.error(f"Error getting heart rate for ring {ring['id']}: {e}")
                            
                        # Get steps directly from the client - properly handle async method
                        try:
                            # Check if get_steps is a coroutine function
                            if asyncio.iscoroutinefunction(client.get_steps):
                                steps = loop.run_until_complete(client.get_steps())
                            else:
                                steps = client.get_steps()
                                
                            if steps and steps > 0:
                                self.db.add_steps(ring['id'], steps)
                                logger.info(f"Logged steps {steps} for ring {ring['id']}")
                        except Exception as e:
                            logger.error(f"Error getting steps for ring {ring['id']}: {e}")
                            
                        # Get battery directly from the client - properly handle async method
                        try:
                            # Check if get_battery is a coroutine function
                            if asyncio.iscoroutinefunction(client.get_battery):
                                battery = loop.run_until_complete(client.get_battery())
                            else:
                                battery = client.get_battery()
                                
                            if battery is not None:
                                self.db.add_battery(ring['id'], battery)
                                logger.info(f"Logged battery {battery}% for ring {ring['id']}")
                        except Exception as e:
                            logger.error(f"Error getting battery for ring {ring['id']}: {e}")
                            
                        # Close the loop
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error logging data for ring {ring['id']}: {e}")
                        
                # Sleep before next log
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in logger loop: {e}")
                time.sleep(10)  # Short delay before retrying
