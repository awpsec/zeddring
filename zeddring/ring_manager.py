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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.ring_manager")

# Try to import the colmi_r02_client package
try:
    from colmi_r02_client import Client as ColmiClient
    COLMI_CLIENT_AVAILABLE = True
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
        if self.connected:
            logger.warning(f"Ring {self.mac_address} is already connected")
            return True
            
        try:
            if COLMI_CLIENT_AVAILABLE:
                self.client = ColmiClient(self.mac_address)
                await self.client.connect()
            else:
                self.client = MockColmiR02Client(self.mac_address)
                await self.client.connect()
                
            self.connected = True
            logger.info(f"Connected to ring {self.mac_address}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to ring {self.mac_address}: {e}")
            self.connected = False
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
            return
            
        try:
            logger.info(f"Syncing historical data for ring {self.id}")
            historical_data = await self.client.get_historical_data()
            
            if historical_data and 'steps_history' in historical_data:
                for entry in historical_data['steps_history']:
                    timestamp = entry.get('timestamp')
                    steps = entry.get('value')
                    if timestamp and steps:
                        # Convert timestamp to datetime if needed
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp)
                        # Add to database with specific timestamp
                        self.db.add_steps_with_timestamp(self.id, steps, timestamp)
                        
            if historical_data and 'heart_rate_history' in historical_data:
                for entry in historical_data['heart_rate_history']:
                    timestamp = entry.get('timestamp')
                    heart_rate = entry.get('value')
                    if timestamp and heart_rate:
                        # Convert timestamp to datetime if needed
                        if isinstance(timestamp, str):
                            timestamp = datetime.fromisoformat(timestamp)
                        # Add to database with specific timestamp
                        self.db.add_heart_rate_with_timestamp(self.id, heart_rate, timestamp)
            
            # Update the last sync time in the database
            self.db.update_last_sync(self.id)
                        
            logger.info(f"Historical data sync completed for ring {self.id}")
            return True
        except Exception as e:
            logger.error(f"Error syncing historical data for ring {self.id}: {e}")
            return False
            
    async def set_ring_time(self):
        """Set the time on the ring to match the server time."""
        if not self.client or not hasattr(self.client, 'set_time'):
            return False
            
        try:
            logger.info(f"Setting time for ring {self.id}")
            current_time = datetime.now()
            success = await self.client.set_time(current_time)
            logger.info(f"Time set for ring {self.id}: {success}")
            return success
        except Exception as e:
            logger.error(f"Error setting time for ring {self.id}: {e}")
            return False
            
    async def reboot(self):
        """Reboot the ring."""
        if not self.client or not hasattr(self.client, 'reboot'):
            logger.warning(f"Ring {self.id} client does not support reboot")
            return False
            
        try:
            logger.info(f"Rebooting ring {self.id}")
            success = await self.client.reboot()
            if success:
                self.connected = False
                logger.info(f"Ring {self.id} is rebooting")
            else:
                logger.warning(f"Failed to reboot ring {self.id}")
            return success
        except Exception as e:
            logger.error(f"Error rebooting ring {self.id}: {e}")
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
            # Skip if already connected
            if mac_address in self.clients:
                logger.info(f"Already connected to {mac_address}")
                return True
                
            # Get ring info from database to check if it's marked as mock
            ring_info = self.db.get_ring(ring_id)
            if not ring_info:
                logger.error(f"Ring {ring_id} not found in database")
                return False
            
            # Handle sqlite3.Row objects which don't have a get method
            is_mock_in_db = ring_info['is_mock'] == 1 if 'is_mock' in ring_info.keys() else False
            ring_name = ring_info['name'] if 'name' in ring_info.keys() else 'Unknown Ring'
            
            # Create client
            # For manually added rings (not the default mock), always try to use the real client
            is_mock_default = mac_address == "00:11:22:33:44:55"
            
            if COLMI_CLIENT_AVAILABLE and not is_mock_default and not is_mock_in_db:
                logger.info(f"Using real ColmiClient for {ring_name} ({mac_address})")
                client = ColmiClient(mac_address)
            else:
                if is_mock_default:
                    logger.info(f"Using MockColmiR02Client for default mock ring {mac_address}")
                elif is_mock_in_db:
                    logger.info(f"Using MockColmiR02Client for ring marked as mock in database: {ring_name} ({mac_address})")
                else:
                    logger.warning(f"ColmiClient not available, using MockColmiR02Client for {ring_name} ({mac_address})")
                client = MockColmiR02Client(mac_address)
            
            # Connect
            logger.info(f"Connecting to {ring_name} ({mac_address})...")
            
            # Try to connect with retry logic
            retry_count = 0
            connected = False
            
            while retry_count < MAX_RETRY_ATTEMPTS and not connected:
                # Handle the async connect
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    connected = loop.run_until_complete(client.connect())
                    if connected:
                        logger.info(f"Successfully connected to {ring_name} ({mac_address}) on attempt {retry_count + 1}")
                    else:
                        retry_count += 1
                        logger.warning(f"Failed to connect on attempt {retry_count}, will retry in {RETRY_DELAY} seconds")
                        time.sleep(RETRY_DELAY)
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Error during connect attempt {retry_count}: {e}")
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        logger.warning(f"Will retry in {RETRY_DELAY} seconds")
                        time.sleep(RETRY_DELAY)
            
            # If we couldn't connect with a real client, fall back to mock
            if not connected and COLMI_CLIENT_AVAILABLE and not is_mock_default and not is_mock_in_db:
                logger.warning(f"Failed to connect with real client, falling back to mock for {ring_name} ({mac_address})")
                client = MockColmiR02Client(mac_address)
                
                # Try to connect with mock client
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    connected = loop.run_until_complete(client.connect())
                    if connected:
                        logger.info(f"Successfully connected with mock client for {ring_name} ({mac_address})")
                        # Update database to mark this ring as mock
                        self.db.update_ring(ring_id, {'is_mock': 1})
                        logger.info(f"Updated database to mark {ring_name} ({mac_address}) as mock")
                except Exception as e:
                    logger.error(f"Error connecting with mock client: {e}")
                    connected = False
                finally:
                    loop.close()
            
            if connected:
                logger.info(f"Connected to {ring_name} ({mac_address})")
                self.clients[mac_address] = client
                self.connected_rings[mac_address] = True
                self.db.update_ring_connection(ring_id)
                
                # Try to sync historical data after connecting if this is a real ring
                if not is_mock_default and not is_mock_in_db and COLMI_CLIENT_AVAILABLE:
                    try:
                        logger.info(f"Syncing historical data for ring {ring_name} ({mac_address})")
                        
                        # Get last sync time
                        last_sync = ring_info.get('last_sync')
                        if last_sync:
                            try:
                                last_sync = datetime.fromisoformat(last_sync)
                                logger.info(f"Last sync for {ring_name} was at {last_sync}")
                            except ValueError:
                                last_sync = datetime.now() - datetime.timedelta(days=7)
                                logger.warning(f"Invalid last_sync format for {ring_name}, using 7 days ago")
                        else:
                            last_sync = datetime.now() - datetime.timedelta(days=7)
                            logger.info(f"No previous sync for {ring_name}, using 7 days ago")
                        
                        # Get historical data
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        historical_data = loop.run_until_complete(client.get_historical_data(since=last_sync))
                        loop.close()
                        
                        if historical_data and 'steps_history' in historical_data:
                            for entry in historical_data['steps_history']:
                                timestamp = entry.get('timestamp')
                                steps = entry.get('value')
                                if timestamp and steps:
                                    # Convert timestamp to datetime if needed
                                    if isinstance(timestamp, str):
                                        timestamp = datetime.fromisoformat(timestamp)
                                    # Add to database with specific timestamp
                                    self.db.add_steps_with_timestamp(ring_id, steps, timestamp)
                                    
                        if historical_data and 'heart_rate_history' in historical_data:
                            for entry in historical_data['heart_rate_history']:
                                timestamp = entry.get('timestamp')
                                heart_rate = entry.get('value')
                                if timestamp and heart_rate:
                                    # Convert timestamp to datetime if needed
                                    if isinstance(timestamp, str):
                                        timestamp = datetime.fromisoformat(timestamp)
                                    # Add to database with specific timestamp
                                    self.db.add_heart_rate_with_timestamp(ring_id, heart_rate, timestamp)
                        
                        # Update last sync time
                        now = datetime.now()
                        self.db.update_ring(ring_id, {'last_sync': now.isoformat()})
                        logger.info(f"Historical data sync completed for ring {ring_name} and updated last_sync to {now}")
                    except Exception as e:
                        logger.error(f"Error syncing historical data: {e}")
                    
                return True
            else:
                logger.error(f"Failed to connect to {ring_name} ({mac_address}) after all attempts")
                return False
                
        except Exception as e:
            logger.error(f"Error in _connect_to_ring for {mac_address}: {e}")
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
                client = ColmiClient(mac_address)
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
            # Get the ring from the database
            ring = self.db.get_ring(ring_id)
            if not ring:
                logger.error(f"Ring {ring_id} not found")
                return False
                
            # Get the MAC address
            mac_address = ring['mac_address']
            
            # Connect to the ring
            connected = await self._connect_to_ring(mac_address, ring_id)
            if not connected:
                logger.error(f"Failed to connect to ring {ring_id}")
                return False
                
            # Set the time on the ring
            if ring_id in self.clients:
                await self.clients[mac_address].set_ring_time()
                
            logger.info(f"Connected to ring {ring_id}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to ring {ring_id}: {e}")
            return False
            
    async def disconnect_ring(self, ring_id: int) -> bool:
        """Disconnect from a ring."""
        try:
            ring = self.db.get_ring(ring_id)
            if not ring:
                return False
                
            # Skip if not connected
            if ring['mac_address'] not in self.clients:
                return True
                
            # Disconnect
            client = self.clients[ring['mac_address']]
            await client.disconnect()
            
            # Remove from clients
            del self.clients[ring['mac_address']]
            
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