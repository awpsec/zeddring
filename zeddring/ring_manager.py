"""Ring manager module for Zeddring."""

import time
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import json
import os
import sqlite3
from dataclasses import dataclass
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.ring_manager")

# Try to import the colmi_r02_client package
try:
    # Try different possible class names
    try:
        from colmi_r02_client import Client as ColmiClient
        COLMI_CLIENT_AVAILABLE = True
    except ImportError:
        try:
            from colmi_r02_client import ColmiR02Client as ColmiClient
            COLMI_CLIENT_AVAILABLE = True
        except ImportError:
            try:
                from colmi_r02_client import ColmiClient
                COLMI_CLIENT_AVAILABLE = True
            except ImportError:
                try:
                    # Try importing from submodules
                    from colmi_r02_client.client import Client as ColmiClient
                    COLMI_CLIENT_AVAILABLE = True
                except ImportError:
                    try:
                        from colmi_r02_client.client import ColmiR02Client as ColmiClient
                        COLMI_CLIENT_AVAILABLE = True
                    except ImportError:
                        try:
                            from colmi_r02_client.client import ColmiClient
                            COLMI_CLIENT_AVAILABLE = True
                        except ImportError:
                            try:
                                # Try importing from custom_client
                                from colmi_r02_client.custom_client import Client as ColmiClient
                                COLMI_CLIENT_AVAILABLE = True
                            except ImportError:
                                # Try to dynamically find a client class in the package
                                try:
                                    import colmi_r02_client
                                    import inspect
                                    
                                    # Find all classes in the module
                                    client_classes = [obj for name, obj in inspect.getmembers(colmi_r02_client) 
                                                    if inspect.isclass(obj) and obj.__module__ == 'colmi_r02_client']
                                    
                                    # Look for a class that might be a client
                                    for cls in client_classes:
                                        if any(name in cls.__name__.lower() for name in ['client', 'colmi', 'ring']):
                                            ColmiClient = cls
                                            COLMI_CLIENT_AVAILABLE = True
                                            logger.info(f"Found potential client class: {cls.__name__}")
                                            break
                                    else:
                                        COLMI_CLIENT_AVAILABLE = False
                                        logger.warning("No suitable client class found in colmi_r02_client")
                                except Exception as e:
                                    COLMI_CLIENT_AVAILABLE = False
                                    logger.warning(f"Error finding client class: {e}")
except ImportError:
    logger.warning("colmi_r02_client not available, using mock client")
    COLMI_CLIENT_AVAILABLE = False
    ColmiClient = None

# Import our custom scanner
from zeddring.scanner import scan_for_devices, MockColmiR02Client

# Import database functions
from zeddring.database import Database, get_db_connection

# Import config
try:
    from zeddring.config import SCAN_INTERVAL, SCAN_TIMEOUT, MAX_RETRY_ATTEMPTS, RETRY_DELAY, PERSISTENT_CONNECTION
except ImportError:
    # Default values if config is not available
    SCAN_INTERVAL = 20
    SCAN_TIMEOUT = 10
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 300
    PERSISTENT_CONNECTION = True

class Ring:
    """Represents a smart ring device."""
    
    def __init__(self, id: int, name: str, mac_address: str):
        self.id = id
        self.name = name
        self.mac_address = mac_address
        self.client = None
        self.connected = False
        self.last_heart_rate = None
        self.last_steps = None
        self.last_battery = None
        self.last_updated = None
        
    def to_dict(self):
        """Convert ring to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "mac_address": self.mac_address,
            "connected": self.connected,
            "last_heart_rate": self.last_heart_rate,
            "last_steps": self.last_steps,
            "last_battery": self.last_battery,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }
        
    async def connect(self):
        """Connect to the ring."""
        try:
            # Check if ColmiClient is available
            if not COLMI_CLIENT_AVAILABLE:
                logger.error(f"ColmiClient not available, cannot connect to {self.name} ({self.mac_address})")
                return False
                
            # Create a new client
            self.client = ColmiClient(self.mac_address)
            
            # Connect to the ring
            connected = await self.client.connect()
            
            if connected:
                logger.info(f"Connected to {self.name} ({self.mac_address})")
                self.connected = True
                return True
            else:
                logger.error(f"Failed to connect to {self.name} ({self.mac_address})")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to {self.name} ({self.mac_address}): {e}")
            return False
            
    async def disconnect(self):
        """Disconnect from the ring."""
        if not self.connected:
            return True
            
        try:
            if self.client:
                await self.client.disconnect()
            self.connected = False
            logger.info(f"Disconnected from ring {self.mac_address}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from ring {self.mac_address}: {e}")
            return False
            
    async def get_heart_rate(self):
        """Get heart rate from the ring."""
        if not self.connected:
            logger.warning(f"Ring {self.mac_address} is not connected")
            return None
            
        try:
            heart_rate = await self.client.get_heart_rate()
            self.last_heart_rate = heart_rate
            self.last_updated = datetime.now()
            return heart_rate
        except Exception as e:
            logger.error(f"Error getting heart rate from ring {self.mac_address}: {e}")
            return None
            
    async def get_steps(self):
        """Get steps from the ring."""
        if not self.connected:
            logger.warning(f"Ring {self.mac_address} is not connected")
            return None
            
        try:
            steps = await self.client.get_steps()
            self.last_steps = steps
            self.last_updated = datetime.now()
            return steps
        except Exception as e:
            logger.error(f"Error getting steps from ring {self.mac_address}: {e}")
            return None
            
    async def get_battery(self):
        """Get battery level from the ring."""
        if not self.connected:
            logger.warning(f"Ring {self.mac_address} is not connected")
            return None
            
        try:
            battery = await self.client.get_battery()
            self.last_battery = battery
            self.last_updated = datetime.now()
            return battery
        except Exception as e:
            logger.error(f"Error getting battery from ring {self.mac_address}: {e}")
            return None
            
    async def update_all(self):
        """Update all data from the ring."""
        try:
            # Get heart rate
            heart_rate = await self.get_heart_rate()
            
            # Get steps
            steps = await self.get_steps()
            
            # Get battery
            battery = await self.get_battery()
            
            # Sync historical data if available
            await self.sync_historical_data()
            
            return {
                'heart_rate': heart_rate,
                'steps': steps,
                'battery': battery
            }
        except Exception as e:
            logger.error(f"Error updating data for ring {self.id}: {e}")
            return None
            
    async def sync_historical_data(self):
        """Sync historical data from the ring."""
        if not self.client or not hasattr(self.client, 'get_historical_data'):
            logger.error(f"Client for ring {self.id} does not support get_historical_data")
            return False
            
        try:
            logger.info(f"Syncing historical data for ring {self.id}")
            historical_data = await self.client.get_historical_data()
            
            if not historical_data:
                logger.warning(f"No historical data returned for ring {self.id}")
                return False
                
            logger.info(f"Received historical data: {historical_data}")
            
            synced_data = False
            
            if historical_data and 'steps_history' in historical_data:
                steps_count = 0
                for entry in historical_data['steps_history']:
                    timestamp = entry.get('timestamp')
                    steps = entry.get('value')
                    if timestamp and steps:
                        # Convert timestamp to datetime if needed
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp)
                        # Add to database with specific timestamp
                        self.db.add_steps_with_timestamp(self.id, steps, timestamp)
                        steps_count += 1
                logger.info(f"Synced {steps_count} steps entries for ring {self.id}")
                if steps_count > 0:
                    synced_data = True
                        
            if historical_data and 'heart_rate_history' in historical_data:
                hr_count = 0
                for entry in historical_data['heart_rate_history']:
                    timestamp = entry.get('timestamp')
                    heart_rate = entry.get('value')
                    if timestamp and heart_rate:
                        # Convert timestamp to datetime if needed
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp)
                        # Add to database with specific timestamp
                        self.db.add_heart_rate_with_timestamp(self.id, heart_rate, timestamp)
                        hr_count += 1
                logger.info(f"Synced {hr_count} heart rate entries for ring {self.id}")
                if hr_count > 0:
                    synced_data = True
            
            # Update the last sync time in the database
            if synced_data:
                self.db.update_last_sync(self.id)
                logger.info(f"Historical data sync completed for ring {self.id}")
                return True
            else:
                logger.warning(f"No data was synced for ring {self.id}")
                return False
        except Exception as e:
            logger.error(f"Error syncing historical data for ring {self.id}: {e}")
            return False
            
    async def set_ring_time(self):
        """Set the time on the ring."""
        if not self.connected:
            logger.error(f"Ring {self.name} ({self.mac_address}) is not connected")
            return False
            
        if not self.client:
            logger.error(f"No client available for ring {self.name} ({self.mac_address})")
            return False
            
        try:
            current_time = datetime.now()
            await self.client.set_time(current_time)
            logger.info(f"Set time on ring {self.name} ({self.mac_address}) to {current_time}")
            return True
        except Exception as e:
            logger.error(f"Error setting time on ring {self.name} ({self.mac_address}): {e}")
            return False
            
    async def reboot(self):
        """Reboot the ring."""
        if not self.connected:
            logger.error(f"Ring {self.name} ({self.mac_address}) is not connected")
            return False
            
        if not self.client:
            logger.error(f"No client available for ring {self.name} ({self.mac_address})")
            return False
            
        try:
            await self.client.reboot()
            logger.info(f"Rebooted ring {self.name} ({self.mac_address})")
            return True
        except Exception as e:
            logger.error(f"Error rebooting ring {self.name} ({self.mac_address}): {e}")
            return False

class RingManager:
    """Manager for Colmi R02 rings."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize the ring manager."""
        self.db = db or Database()
        self.clients = {}
        self.running = False
        self.scanner_thread = None
        self.data_thread = None
        self.connected_rings = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        """Start the ring manager."""
        if self.running:
            return
            
        self.running = True
        self.scanner_thread = threading.Thread(target=self._scanner_loop, daemon=True)
        self.scanner_thread.start()
        
        # Start a separate thread for data collection
        self.data_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        self.data_thread.start()
        
        logger.info("Ring manager started")

    def stop(self) -> None:
        """Stop the ring manager."""
        self.running = False
        logger.info("Ring manager stopped")

    def _scanner_loop(self) -> None:
        """Continuously scan for and connect to rings."""
        while self.running:
            try:
                # Scan for devices
                logger.info("Scanning for devices...")
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the coroutine and get the result
                devices = loop.run_until_complete(scan_for_devices(timeout=10))
                loop.close()
                
                logger.info(f"Found {len(devices)} devices")
                
                # Process found devices
                for device in devices:
                    if not self.running:
                        break
                        
                    try:
                        # Check if this is a ring we're interested in
                        if "Colmi" in device.name or "R02" in device.name:
                            logger.info(f"Found ring: {device.name} ({device.address})")
                            
                            # Add to database if not already there
                            ring = self.db.get_ring_by_mac(device.address)
                            if not ring:
                                ring_id = self.db.add_ring(device.name, device.address)
                                logger.info(f"Added new ring with ID {ring_id}")
                            else:
                                ring_id = ring['id']
                                logger.info(f"Ring already in database with ID {ring_id}")
                            
                            # Connect to the ring if not already connected
                            if device.address not in self.clients and PERSISTENT_CONNECTION:
                                self._connect_to_ring(device.address, ring_id)
                            elif not PERSISTENT_CONNECTION:
                                # Connect, get data, and disconnect
                                self._connect_and_get_data(device.address, ring_id)
                    except Exception as e:
                        logger.error(f"Error processing device {device.name}: {e}")
                
                # Sleep before next scan
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
                time.sleep(10)  # Short delay before retrying

    def _data_collection_loop(self) -> None:
        """Collect data from connected rings."""
        while self.running:
            try:
                # Get all rings from the database
                rings = self.db.get_rings()
                
                for ring in rings:
                    ring_id = ring['id']
                    mac_address = ring['mac_address']
                    
                    # Check if we should connect to this ring
                    if mac_address not in self.clients:
                        # Try to connect to the ring
                        if PERSISTENT_CONNECTION:
                            logger.info(f"Attempting to connect to ring {ring_id} ({mac_address})")
                            connected = self._connect_to_ring(mac_address, ring_id)
                            if connected:
                                # Set the time on the ring after connecting
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self.clients[mac_address].set_ring_time())
                                loop.close()
                    
                    # If the ring is connected, get data
                    if mac_address in self.clients:
                        try:
                            # Create a new event loop for this ring
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            # Get data from the ring
                            client = self.clients[mac_address]
                            
                            # Get heart rate
                            try:
                                heart_rate = loop.run_until_complete(client.get_heart_rate())
                                if heart_rate and heart_rate > 0:
                                    self.db.add_heart_rate(ring_id, heart_rate)
                                    logger.debug(f"Added heart rate {heart_rate} for ring {ring_id}")
                            except Exception as e:
                                logger.error(f"Error getting heart rate: {e}")
                            
                            # Get steps
                            try:
                                steps = client.get_steps()
                                if steps and steps > 0:
                                    self.db.add_steps(ring_id, steps)
                                    logger.debug(f"Added steps {steps} for ring {ring_id}")
                            except Exception as e:
                                logger.error(f"Error getting steps: {e}")
                            
                            # Get battery
                            try:
                                battery = client.get_battery()
                                if battery is not None:
                                    self.db.add_battery(ring_id, battery)
                                    self.db.update_ring_battery(ring_id, battery)
                                    logger.debug(f"Added battery {battery}% for ring {ring_id}")
                            except Exception as e:
                                logger.error(f"Error getting battery: {e}")
                            
                            # Close the loop
                            loop.close()
                            
                        except Exception as e:
                            logger.error(f"Error getting data from ring {ring_id}: {e}")
                            
                            # Disconnect if there was an error
                            if mac_address in self.clients:
                                try:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    loop.run_until_complete(self.clients[mac_address].disconnect())
                                    loop.close()
                                except Exception as disconnect_error:
                                    logger.error(f"Error disconnecting from ring {ring_id}: {disconnect_error}")
                                finally:
                                    if mac_address in self.clients:
                                        del self.clients[mac_address]
                
                # Sleep before next collection
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                time.sleep(10)  # Short delay before retrying

    def _connect_to_ring(self, mac_address: str, ring_id: int) -> bool:
        """Connect to a ring and keep the connection open."""
        try:
            # Get ring info from database
            ring_info = self.db.get_ring(ring_id)
            if not ring_info:
                logger.error(f"Ring {ring_id} not found in database")
                return False
            
            # Handle sqlite3.Row objects which don't have a get method
            ring_name = ring_info['name'] if 'name' in ring_info.keys() else 'Unknown Ring'
            is_mock = ring_info['is_mock'] if 'is_mock' in ring_info.keys() else 0
            
            # Check if already connected
            if mac_address in self.clients:
                # Check if the connection is still valid
                client = self.clients[mac_address]
                if hasattr(client, 'connected') and client.connected:
                    logger.info(f"Already connected to {mac_address}")
                    return True
                else:
                    # Connection is no longer valid, remove it and reconnect
                    logger.info(f"Connection to {mac_address} is no longer valid, reconnecting...")
                    try:
                        # Try to disconnect cleanly
                        if hasattr(client, 'disconnect'):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(client.disconnect())
                            loop.close()
                    except Exception as e:
                        logger.warning(f"Error disconnecting from {mac_address}: {e}")
                    
                    # Remove the client
                    del self.clients[mac_address]
                    if mac_address in self.connected_rings:
                        del self.connected_rings[mac_address]
            
            # Check if this is a valid MAC address (should be in format like 00:11:22:33:44:55)
            is_valid_mac = bool(re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', mac_address))
            
            # If it's not a valid MAC or marked as mock, use the mock client
            if not is_valid_mac or is_mock:
                logger.warning(f"Using mock client for {ring_name} ({mac_address}) - Valid MAC: {is_valid_mac}, Is Mock: {is_mock}")
                client = MockColmiR02Client(mac_address)
                
                # For mock client, simulate connection
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(client.connect())
                loop.close()
                
                if connected:
                    logger.info(f"Connected to mock ring {ring_name} ({mac_address})")
                    self.clients[mac_address] = client
                    self.connected_rings[mac_address] = True
                    self.db.update_ring_connection(ring_id)
                    return True
                else:
                    logger.error(f"Failed to connect to mock ring {ring_name} ({mac_address})")
                    return False
            
            # Check if ColmiClient is available for real connections
            if not COLMI_CLIENT_AVAILABLE:
                logger.error(f"ColmiClient not available, cannot connect to real ring {ring_name} ({mac_address})")
                return False
            
            # Use real client for real MAC addresses
            logger.info(f"Using real ColmiClient for {ring_name} ({mac_address})")
            try:
                client = ColmiClient(mac_address)
            except Exception as e:
                logger.error(f"Error creating ColmiClient: {e}")
                return False
            
            # Connect
            connected = False
            
            # Create a new event loop for the connection
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                connected = loop.run_until_complete(client.connect())
            except Exception as e:
                logger.error(f"Error connecting to ring: {e}")
                connected = False
            finally:
                loop.close()
            
            if connected:
                logger.info(f"Connected to real ring {ring_name} ({mac_address})")
                self.clients[mac_address] = client
                self.connected_rings[mac_address] = True
                self.db.update_ring_connection(ring_id)
                return True
            else:
                logger.error(f"Failed to connect to real ring {ring_name} ({mac_address})")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to ring: {e}")
            return False

    def _connect_and_get_data(self, mac_address: str, ring_id: int) -> None:
        """Connect to a ring, get data, and disconnect."""
        # Skip if already connected
        if mac_address in self.clients:
            logger.info(f"Already connected to {mac_address}")
            return
            
        try:
            # Create client
            if COLMI_CLIENT_AVAILABLE:
                try:
                    client = ColmiClient(mac_address)
                except Exception as e:
                    logger.error(f"Error creating ColmiClient: {e}")
                    client = MockColmiR02Client(mac_address)
            else:
                client = MockColmiR02Client(mac_address)
                
            self.clients[mac_address] = client
            
            # Connect
            logger.info(f"Connecting to {mac_address}...")
            
            # For the mock client, we need to handle the async connect differently
            if COLMI_CLIENT_AVAILABLE:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(client.connect())
                loop.close()
            else:
                # For mock client, simulate async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                connected = loop.run_until_complete(client.connect())
                loop.close()
                
            if connected:
                logger.info(f"Connected to {mac_address}")
                self.db.update_ring_connection(ring_id)
                
                # Get battery
                try:
                    if COLMI_CLIENT_AVAILABLE:
                        battery = client.get_battery()
                    else:
                        battery = client.get_battery()
                    logger.info(f"Battery: {battery}%")
                    self.db.add_battery(ring_id, battery)
                    
                    # Update the ring's battery level in the database
                    self.db.update_ring_battery(ring_id, battery)
                except Exception as e:
                    logger.error(f"Error getting battery: {e}")
                
                # Get steps
                try:
                    if COLMI_CLIENT_AVAILABLE:
                        steps = client.get_steps()
                    else:
                        steps = client.get_steps()
                    logger.info(f"Steps: {steps}")
                    self.db.add_steps(ring_id, steps)
                except Exception as e:
                    logger.error(f"Error getting steps: {e}")
                
                # Get heart rate
                try:
                    if COLMI_CLIENT_AVAILABLE:
                        heart_rates = client.get_real_time_heart_rate()
                    else:
                        heart_rates = client.get_real_time_heart_rate()
                        
                    if heart_rates and len(heart_rates) > 0:
                        # Use the last (most recent) heart rate value
                        hr_value = heart_rates[-1]
                        if hr_value > 0:  # Ignore zero values
                            logger.info(f"Heart rate: {hr_value}")
                            self.db.add_heart_rate(ring_id, hr_value)
                except Exception as e:
                    logger.error(f"Error getting heart rate: {e}")
                
                # Disconnect
                logger.info(f"Disconnecting from {mac_address}...")
                if COLMI_CLIENT_AVAILABLE:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(client.disconnect())
                    loop.close()
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(client.disconnect())
                    loop.close()
                
                logger.info(f"Disconnected from {mac_address}")
            else:
                logger.error(f"Failed to connect to {mac_address}")
                
        except Exception as e:
            logger.error(f"Error connecting to {mac_address}: {e}")
        finally:
            # Clean up
            if mac_address in self.clients:
                del self.clients[mac_address]

    def get_ring_status(self) -> List[Dict]:
        """Get status of all rings."""
        rings = self.db.get_rings()
        result = []
        
        for ring in rings:
            # Convert to dict for easier manipulation
            ring_dict = dict(ring)
            
            # Add connected status
            ring_dict['connected'] = ring['mac_address'] in self.clients
            
            # Get latest data
            try:
                heart_rate_data = self.db.get_heart_rate_data(ring['id'], limit=1)
                if heart_rate_data:
                    ring_dict['heart_rate'] = heart_rate_data[0]['value']
                    ring_dict['heart_rate_time'] = heart_rate_data[0]['timestamp']
                
                steps_data = self.db.get_steps_data(ring['id'], limit=1)
                if steps_data:
                    ring_dict['steps'] = steps_data[0]['value']
                    ring_dict['steps_time'] = steps_data[0]['timestamp']
                
                battery_data = self.db.get_battery_data(ring['id'], limit=1)
                if battery_data:
                    ring_dict['battery'] = battery_data[0]['value']
                    ring_dict['battery_time'] = battery_data[0]['timestamp']
                
                # Get last sync time (most recent data point)
                last_sync = None
                if heart_rate_data and steps_data:
                    hr_time = heart_rate_data[0]['timestamp']
                    steps_time = steps_data[0]['timestamp']
                    last_sync = max(hr_time, steps_time)
                elif heart_rate_data:
                    last_sync = heart_rate_data[0]['timestamp']
                elif steps_data:
                    last_sync = steps_data[0]['timestamp']
                
                if last_sync:
                    ring_dict['last_sync'] = last_sync
            except Exception as e:
                logger.error(f"Error getting data for ring {ring['id']}: {e}")
            
            result.append(ring_dict)
        
        return result

    def get_ring_data(self, ring_id: int) -> Dict:
        """Get detailed data for a specific ring."""
        ring = self.db.get_ring(ring_id)
        if not ring:
            return {}
            
        # Convert to dict for easier manipulation
        result = dict(ring)
        
        # Add connected status
        result['connected'] = ring['mac_address'] in self.clients
        
        # Get data
        try:
            # Get heart rate data
            heart_rate_data = self.db.get_heart_rate_data(ring_id, limit=100)
            result['heart_rate_data'] = [
                {'value': row['value'], 'timestamp': row['timestamp']}
                for row in heart_rate_data
            ]
            
            # Calculate min, max, avg heart rate
            if heart_rate_data:
                hr_values = [row['value'] for row in heart_rate_data]
                result['min_heart_rate'] = min(hr_values)
                result['max_heart_rate'] = max(hr_values)
                result['avg_heart_rate'] = sum(hr_values) / len(hr_values)
                result['latest_heart_rate'] = heart_rate_data[0]['value']
            
            # Get steps data
            steps_data = self.db.get_steps_data(ring_id, limit=100)
            result['steps_data'] = [
                {'value': row['value'], 'timestamp': row['timestamp']}
                for row in steps_data
            ]
            
            # Get latest steps
            if steps_data:
                result['latest_steps'] = steps_data[0]['value']
            
            # Get battery data
            battery_data = self.db.get_battery_data(ring_id, limit=100)
            result['battery_data'] = [
                {'value': row['value'], 'timestamp': row['timestamp']}
                for row in battery_data
            ]
            
            # Get latest battery
            if battery_data:
                result['latest_battery'] = battery_data[0]['value']
                result['battery_level'] = battery_data[0]['value']  # Add this for the detail page
                
            # Add last_seen field
            if 'last_connected' in result and result['last_connected']:
                result['last_seen'] = result['last_connected']
                
        except Exception as e:
            logger.error(f"Error getting data for ring {ring_id}: {e}")
        
        return result
        
    def remove_ring(self, ring_id: int) -> bool:
        """Remove a ring from the database."""
        try:
            ring = self.db.get_ring(ring_id)
            if not ring:
                return False
                
            # Disconnect if connected
            if ring['mac_address'] in self.clients:
                try:
                    client = self.clients[ring['mac_address']]
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(client.disconnect())
                    loop.close()
                    del self.clients[ring['mac_address']]
                except Exception as e:
                    logger.error(f"Error disconnecting from ring {ring_id}: {e}")
            
            # Remove from database
            return self.db.remove_ring(ring_id)
        except Exception as e:
            logger.error(f"Error removing ring {ring_id}: {e}")
            return False
            
    async def connect_ring(self, ring_id: int) -> bool:
        """Connect to a ring."""
        try:
            # Get ring info from database
            ring_info = self.db.get_ring(ring_id)
            if not ring_info:
                logger.error(f"Ring {ring_id} not found in database")
                return False
            
            # Handle sqlite3.Row objects which don't have a get method
            mac_address = ring_info['mac_address'] if 'mac_address' in ring_info.keys() else None
            ring_name = ring_info['name'] if 'name' in ring_info.keys() else 'Unknown Ring'
            
            if not mac_address:
                logger.error(f"Ring {ring_id} has no MAC address")
                return False
                
            logger.info(f"Attempting to connect to ring {ring_id} ({mac_address})")
            
            # Check if ColmiClient is available
            if not COLMI_CLIENT_AVAILABLE:
                logger.error(f"ColmiClient not available, cannot connect to {ring_name} ({mac_address})")
                return False
                
            # Create a temporary Ring object to connect
            temp_ring = Ring(ring_id, ring_name, mac_address)
            
            # Connect using the Ring object
            connected = await temp_ring.connect()
            
            if connected:
                # Store the client
                self.clients[mac_address] = temp_ring.client
                self.connected_rings[mac_address] = True
                self.db.update_ring_connection(ring_id)
                return True
            else:
                logger.error(f"Failed to connect to ring {ring_id} ({mac_address})")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to ring {ring_id}: {e}")
            return False
            
    async def disconnect_ring(self, ring_id: int) -> bool:
        """Disconnect from a ring."""
        try:
            ring = self.db.get_ring(ring_id)
            if not ring:
                logger.error(f"Ring {ring_id} not found in database")
                return False
                
            mac_address = ring['mac_address'] if 'mac_address' in ring.keys() else None
            if not mac_address:
                logger.error(f"Ring {ring_id} has no MAC address")
                return False
                
            # Skip if not connected
            if mac_address not in self.clients:
                logger.info(f"Ring {ring_id} ({mac_address}) is not connected")
                return True
                
            # Disconnect
            client = self.clients[mac_address]
            logger.info(f"Disconnecting from ring {ring_id} ({mac_address})...")
            
            try:
                # Check if disconnect is a coroutine function
                if asyncio.iscoroutinefunction(client.disconnect):
                    await client.disconnect()
                else:
                    # For non-async disconnect methods
                    client.disconnect()
                
                logger.info(f"Successfully disconnected from ring {ring_id} ({mac_address})")
            except Exception as e:
                logger.error(f"Error during disconnect operation: {e}")
                # Continue with cleanup even if disconnect fails
            
            # Remove from clients and update database
            del self.clients[mac_address]
            if mac_address in self.connected_rings:
                del self.connected_rings[mac_address]
            
            # Update connection status in database
            self.db.update_ring_disconnection(ring_id)
            
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from ring {ring_id}: {e}")
            return False
            
    def get_ring_history(self, ring_id: int, days: int = 7) -> Dict:
        """Get ring data history."""
        try:
            # This would need to be implemented in the Database class
            # return self.db.get_ring_history(ring_id, days)
            return {}
        except Exception as e:
            logger.error(f"Error getting ring history for {ring_id}: {e}")
            return {}
            
    def get_daily_data(self, ring_id: int, date: Optional[str] = None) -> Dict:
        """Get daily data for a ring."""
        try:
            # This would need to be implemented in the Database class
            # return self.db.get_daily_data(ring_id, date)
            return {}
        except Exception as e:
            logger.error(f"Error getting daily data for {ring_id}: {e}")
            return {}
            
    def save_ring_data(self, ring_id: int, data: Dict) -> bool:
        """Save ring data to database."""
        try:
            if 'heart_rate' in data and data['heart_rate']:
                self.db.add_heart_rate(ring_id, data['heart_rate'])
                
            if 'steps' in data and data['steps']:
                self.db.add_steps(ring_id, data['steps'])
                
            if 'battery' in data and data['battery']:
                self.db.add_battery(ring_id, data['battery'])
                
            return True
        except Exception as e:
            logger.error(f"Error saving ring data for {ring_id}: {e}")
            return False

    async def reboot_ring(self, ring_id: int) -> bool:
        """Reboot a ring."""
        try:
            # Get ring info from database
            ring_info = self.db.get_ring(ring_id)
            if not ring_info:
                logger.error(f"Ring {ring_id} not found in database")
                return False
            
            # Handle sqlite3.Row objects which don't have a get method
            mac_address = ring_info['mac_address'] if 'mac_address' in ring_info.keys() else None
            ring_name = ring_info['name'] if 'name' in ring_info.keys() else 'Unknown Ring'
            
            if not mac_address:
                logger.error(f"Ring {ring_id} has no MAC address")
                return False
                
            # Check if the ring is connected
            if mac_address not in self.clients:
                logger.error(f"Ring {ring_id} ({mac_address}) is not connected")
                return False
                
            # Get the client
            client = self.clients[mac_address]
            logger.info(f"Rebooting ring {ring_id} ({mac_address})...")
            
            # Reboot the ring
            try:
                # Check if reboot is a coroutine function
                if asyncio.iscoroutinefunction(client.reboot):
                    await client.reboot()
                else:
                    # For non-async reboot methods
                    client.reboot()
                
                logger.info(f"Successfully rebooted ring {ring_id} ({mac_address})")
                
                # Remove from clients since connection will be lost after reboot
                del self.clients[mac_address]
                if mac_address in self.connected_rings:
                    del self.connected_rings[mac_address]
                
                # Update connection status in database
                self.db.update_ring_disconnection(ring_id)
                
                return True
            except Exception as e:
                logger.error(f"Error during reboot operation: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error rebooting ring {ring_id}: {e}")
            return False

    async def sync_historical_data_for_ring(self, ring_id: int) -> bool:
        """Sync historical data for a specific ring."""
        try:
            # Get ring info from database
            ring_info = self.db.get_ring(ring_id)
            if not ring_info:
                logger.error(f"Ring {ring_id} not found in database")
                return False
            
            # Handle sqlite3.Row objects which don't have a get method
            mac_address = ring_info['mac_address'] if 'mac_address' in ring_info.keys() else None
            ring_name = ring_info['name'] if 'name' in ring_info.keys() else 'Unknown Ring'
            
            if not mac_address:
                logger.error(f"Ring {ring_id} has no MAC address")
                return False
                
            # Check if the ring is connected
            if mac_address not in self.clients:
                logger.error(f"Ring {ring_id} ({mac_address}) is not connected, attempting to connect...")
                # Try to connect to the ring first
                connected = await self.connect_ring(ring_id)
                if not connected:
                    logger.error(f"Failed to connect to ring {ring_id} ({mac_address})")
                    return False
            
            # Get the client
            client = self.clients[mac_address]
            logger.info(f"Syncing historical data for ring {ring_id} ({mac_address})...")
            
            # Check if the client supports get_historical_data
            if not hasattr(client, 'get_historical_data'):
                logger.error(f"Client for ring {ring_id} does not support get_historical_data")
                return False
            
            # Sync historical data
            try:
                # Get historical data
                if asyncio.iscoroutinefunction(client.get_historical_data):
                    historical_data = await client.get_historical_data()
                else:
                    historical_data = client.get_historical_data()
                
                if not historical_data:
                    logger.warning(f"No historical data returned for ring {ring_id}")
                    return False
                
                logger.info(f"Received historical data for ring {ring_id}")
                
                synced_data = False
                
                # Process steps history
                if 'steps_history' in historical_data and historical_data['steps_history']:
                    steps_count = 0
                    for entry in historical_data['steps_history']:
                        timestamp = entry.get('timestamp')
                        steps = entry.get('value')
                        if timestamp and steps:
                            # Convert timestamp to datetime if needed
                            if isinstance(timestamp, str):
                                try:
                                    timestamp = datetime.fromisoformat(timestamp)
                                except ValueError:
                                    # Try different format if isoformat fails
                                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                            # Add to database with specific timestamp
                            self.db.add_steps_with_timestamp(ring_id, steps, timestamp)
                            steps_count += 1
                    logger.info(f"Synced {steps_count} steps entries for ring {ring_id}")
                    if steps_count > 0:
                        synced_data = True
                
                # Process heart rate history
                if 'heart_rate_history' in historical_data and historical_data['heart_rate_history']:
                    hr_count = 0
                    for entry in historical_data['heart_rate_history']:
                        timestamp = entry.get('timestamp')
                        heart_rate = entry.get('value')
                        if timestamp and heart_rate:
                            # Convert timestamp to datetime if needed
                            if isinstance(timestamp, str):
                                try:
                                    timestamp = datetime.fromisoformat(timestamp)
                                except ValueError:
                                    # Try different format if isoformat fails
                                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                            # Add to database with specific timestamp
                            self.db.add_heart_rate_with_timestamp(ring_id, heart_rate, timestamp)
                            hr_count += 1
                    logger.info(f"Synced {hr_count} heart rate entries for ring {ring_id}")
                    if hr_count > 0:
                        synced_data = True
                
                # Update the last sync time in the database
                if synced_data:
                    self.db.update_last_sync(ring_id)
                    logger.info(f"Historical data sync completed for ring {ring_id}")
                    return True
                else:
                    logger.warning(f"No data was synced for ring {ring_id}")
                    return False
                
            except Exception as e:
                logger.error(f"Error syncing historical data for ring {ring_id}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in sync_historical_data_for_ring for ring {ring_id}: {e}")
            return False

# Singleton instance
_instance = None

def get_ring_manager(db_path: Optional[str] = None) -> RingManager:
    """Get the ring manager instance."""
    global _instance
    
    if _instance is None:
        if db_path:
            db = Database()
            _instance = RingManager(db)
        else:
            _instance = RingManager()
        
    return _instance 