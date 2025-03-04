"""Ring manager module for Zeddring."""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Any
import datetime

try:
    from colmi_r02_client.client import Client
except ImportError:
    logging.error("Could not import colmi_r02_client. Make sure it's installed correctly.")
    raise

from zeddring.config import SCAN_INTERVAL, SCAN_TIMEOUT, MAX_RETRY_ATTEMPTS, RETRY_DELAY
from zeddring.database import Database
from zeddring.scanner import scan_for_rings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.ring_manager")


class RingManager:
    """Manager for Colmi R02 rings."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize the ring manager."""
        self.db = db or Database()
        self.rings: Dict[str, Dict[str, Any]] = {}  # MAC address -> ring info
        self.clients: Dict[str, Client] = {}  # MAC address -> client
        self.running = False
        self.scan_thread = None
        self.data_thread = None
        self._load_known_rings()

    def _load_known_rings(self) -> None:
        """Load known rings from the database."""
        for ring in self.db.get_rings():
            self.rings[ring['mac_address']] = {
                'id': ring['id'],
                'name': ring['name'],
                'last_seen': ring['last_seen'],
                'battery_level': ring['battery_level'],
                'retry_count': 0,
                'connected': False
            }

    def start(self) -> None:
        """Start the ring manager."""
        if self.running:
            return
            
        self.running = True
        
        # Start scanning thread
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        
        # Start data collection thread
        self.data_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        self.data_thread.start()
        
        logger.info("Ring manager started")

    def stop(self) -> None:
        """Stop the ring manager."""
        self.running = False
        
        # Disconnect all clients
        for mac_address, client in list(self.clients.items()):
            try:
                client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {mac_address}: {e}")
            
            del self.clients[mac_address]
            
        logger.info("Ring manager stopped")

    def _scan_loop(self) -> None:
        """Continuously scan for rings."""
        while self.running:
            try:
                logger.info("Scanning for rings...")
                devices = scan_for_rings(timeout=SCAN_TIMEOUT)
                
                for device in devices:
                    mac_address = device.address
                    name = device.name
                    
                    # Check if this is a new ring
                    if mac_address not in self.rings:
                        logger.info(f"Found new ring: {name} ({mac_address})")
                        ring_id = self.db.add_or_update_ring(mac_address, name)
                        self.rings[mac_address] = {
                            'id': ring_id,
                            'name': name,
                            'last_seen': datetime.datetime.now(),
                            'battery_level': None,
                            'retry_count': 0,
                            'connected': False
                        }
                    else:
                        # Update last seen time
                        self.rings[mac_address]['last_seen'] = datetime.datetime.now()
                        self.rings[mac_address]['retry_count'] = 0
                        self.db.add_or_update_ring(mac_address)
                        
                        # Update name if it changed
                        if name and name != self.rings[mac_address]['name']:
                            self.rings[mac_address]['name'] = name
                            self.db.update_ring_name(self.rings[mac_address]['id'], name)
                            logger.info(f"Updated ring name: {name} ({mac_address})")
                
                # Sleep before next scan
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                time.sleep(10)  # Short delay before retrying

    def _data_collection_loop(self) -> None:
        """Continuously collect data from connected rings."""
        while self.running:
            try:
                current_time = datetime.datetime.now()
                
                # Process each known ring
                for mac_address, ring_info in list(self.rings.items()):
                    try:
                        # Skip rings that haven't been seen recently
                        if ring_info['last_seen'] is None or (
                            current_time - datetime.datetime.fromisoformat(ring_info['last_seen']) 
                            > datetime.timedelta(minutes=5)
                        ):
                            continue
                            
                        # Connect to the ring if not already connected
                        if mac_address not in self.clients:
                            logger.info(f"Connecting to ring: {ring_info['name']} ({mac_address})")
                            try:
                                client = Client(address=mac_address)
                                client.connect()
                                self.clients[mac_address] = client
                                self.rings[mac_address]['connected'] = True
                                self.rings[mac_address]['retry_count'] = 0
                                
                                # Get battery level
                                info = client.get_info()
                                battery_level = info.get('battery_level')
                                if battery_level is not None:
                                    self.rings[mac_address]['battery_level'] = battery_level
                                    self.db.update_ring_battery(ring_info['id'], battery_level)
                                    
                                # Set time on the ring
                                client.set_time()
                                
                                logger.info(f"Connected to ring: {ring_info['name']} ({mac_address}), "
                                           f"Battery: {battery_level}%")
                            except Exception as e:
                                logger.error(f"Error connecting to ring {mac_address}: {e}")
                                self.rings[mac_address]['retry_count'] += 1
                                
                                if self.rings[mac_address]['retry_count'] >= MAX_RETRY_ATTEMPTS:
                                    logger.warning(f"Max retry attempts reached for {mac_address}, "
                                                  f"will retry in {RETRY_DELAY} seconds")
                                    time.sleep(RETRY_DELAY)
                                    self.rings[mac_address]['retry_count'] = 0
                                    
                                continue
                        
                        # Collect data from the ring
                        client = self.clients[mac_address]
                        ring_id = ring_info['id']
                        
                        # Get heart rate
                        try:
                            hr_data = client.get_real_time_heart_rate()
                            if hr_data and len(hr_data) > 0:
                                # Use the last (most recent) heart rate value
                                hr_value = hr_data[-1]
                                if hr_value > 0:  # Ignore zero values
                                    self.db.add_heart_rate(ring_id, hr_value)
                                    logger.debug(f"Recorded heart rate for {mac_address}: {hr_value}")
                        except Exception as e:
                            logger.error(f"Error getting heart rate from {mac_address}: {e}")
                        
                        # Get steps
                        try:
                            steps_data = client.get_steps()
                            if steps_data and 'total_steps' in steps_data:
                                steps_value = steps_data['total_steps']
                                self.db.add_steps(ring_id, steps_value)
                                logger.debug(f"Recorded steps for {mac_address}: {steps_value}")
                        except Exception as e:
                            logger.error(f"Error getting steps from {mac_address}: {e}")
                            
                    except Exception as e:
                        logger.error(f"Error processing ring {mac_address}: {e}")
                        
                        # Disconnect on error
                        if mac_address in self.clients:
                            try:
                                self.clients[mac_address].disconnect()
                            except:
                                pass
                            del self.clients[mac_address]
                            self.rings[mac_address]['connected'] = False
                
                # Sleep before next data collection
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                time.sleep(10)  # Short delay before retrying

    def get_ring_status(self) -> List[Dict[str, Any]]:
        """Get the status of all known rings."""
        return [
            {
                'id': info['id'],
                'mac_address': mac,
                'name': info['name'],
                'last_seen': info['last_seen'],
                'battery_level': info['battery_level'],
                'connected': info['connected']
            }
            for mac, info in self.rings.items()
        ]

    def get_ring_by_id(self, ring_id: int) -> Optional[Dict[str, Any]]:
        """Get a ring by ID."""
        for mac, info in self.rings.items():
            if info['id'] == ring_id:
                return {
                    'id': info['id'],
                    'mac_address': mac,
                    'name': info['name'],
                    'last_seen': info['last_seen'],
                    'battery_level': info['battery_level'],
                    'connected': info['connected']
                }
        return None

    def reboot_ring(self, ring_id: int) -> bool:
        """Reboot a ring."""
        for mac, info in self.rings.items():
            if info['id'] == ring_id:
                if mac in self.clients:
                    try:
                        self.clients[mac].reboot()
                        
                        # Disconnect after reboot
                        self.clients[mac].disconnect()
                        del self.clients[mac]
                        self.rings[mac]['connected'] = False
                        
                        logger.info(f"Rebooted ring: {info['name']} ({mac})")
                        return True
                    except Exception as e:
                        logger.error(f"Error rebooting ring {mac}: {e}")
                        return False
                else:
                    logger.warning(f"Ring {mac} is not connected")
                    return False
        
        logger.warning(f"Ring with ID {ring_id} not found")
        return False

    def rename_ring(self, ring_id: int, new_name: str) -> bool:
        """Rename a ring."""
        for mac, info in self.rings.items():
            if info['id'] == ring_id:
                self.db.update_ring_name(ring_id, new_name)
                self.rings[mac]['name'] = new_name
                logger.info(f"Renamed ring {mac} to {new_name}")
                return True
        
        logger.warning(f"Ring with ID {ring_id} not found")
        return False

    def disconnect_ring(self, ring_id: int) -> bool:
        """Disconnect from a ring."""
        for mac, info in self.rings.items():
            if info['id'] == ring_id:
                if mac in self.clients:
                    try:
                        self.clients[mac].disconnect()
                        del self.clients[mac]
                        self.rings[mac]['connected'] = False
                        logger.info(f"Disconnected from ring: {info['name']} ({mac})")
                        return True
                    except Exception as e:
                        logger.error(f"Error disconnecting from ring {mac}: {e}")
                        return False
                else:
                    logger.warning(f"Ring {mac} is not connected")
                    return False
        
        logger.warning(f"Ring with ID {ring_id} not found")
        return False

    def connect_ring(self, ring_id: int) -> bool:
        """Connect to a ring."""
        for mac, info in self.rings.items():
            if info['id'] == ring_id:
                if mac in self.clients:
                    logger.warning(f"Ring {mac} is already connected")
                    return True
                
                try:
                    client = Client(address=mac)
                    client.connect()
                    self.clients[mac] = client
                    self.rings[mac]['connected'] = True
                    
                    # Get battery level
                    info = client.get_info()
                    battery_level = info.get('battery_level')
                    if battery_level is not None:
                        self.rings[mac]['battery_level'] = battery_level
                        self.db.update_ring_battery(ring_id, battery_level)
                    
                    # Set time on the ring
                    client.set_time()
                    
                    logger.info(f"Connected to ring: {self.rings[mac]['name']} ({mac})")
                    return True
                except Exception as e:
                    logger.error(f"Error connecting to ring {mac}: {e}")
                    return False
        
        logger.warning(f"Ring with ID {ring_id} not found")
        return False 