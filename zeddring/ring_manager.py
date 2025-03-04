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
    from zeddring.config import SCAN_INTERVAL, SCAN_TIMEOUT, MAX_RETRY_ATTEMPTS, RETRY_DELAY
except ImportError:
    # Default values if config is not available
    SCAN_INTERVAL = 60
    SCAN_TIMEOUT = 10
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 300

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
        """Update all ring data."""
        if not self.connected:
            success = await self.connect()
            if not success:
                return False
                
        try:
            heart_rate = await self.get_heart_rate()
            steps = await self.get_steps()
            battery = await self.get_battery()
            
            self.last_updated = datetime.now()
            
            return {
                "heart_rate": heart_rate,
                "steps": steps,
                "battery": battery
            }
        except Exception as e:
            logger.error(f"Error updating ring {self.mac_address}: {e}")
            return None

class RingManager:
    """Manager for Colmi R02 rings."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize the ring manager."""
        self.db = db or Database()
        self.clients = {}
        self.running = False
        self.scanner_thread = None

    def start(self) -> None:
        """Start the ring manager."""
        if self.running:
            return
            
        self.running = True
        self.scanner_thread = threading.Thread(target=self._scanner_loop, daemon=True)
        self.scanner_thread.start()
        
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
                devices = scan_for_devices(timeout=10)
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
                            
                            # Connect to the ring and get data
                            self._connect_and_get_data(device.address, ring_id)
                    except Exception as e:
                        logger.error(f"Error processing device {device.name}: {e}")
                
                # Sleep before next scan
                time.sleep(60)  # Scan every minute
                
            except Exception as e:
                logger.error(f"Error in scanner loop: {e}")
                time.sleep(10)  # Short delay before retrying

    def _connect_and_get_data(self, mac_address: str, ring_id: int) -> None:
        """Connect to a ring and get data."""
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
            ring = self.db.get_ring(ring_id)
            if not ring:
                return False
                
            # Skip if already connected
            if ring['mac_address'] in self.clients:
                return True
                
            # Create client
            if COLMI_CLIENT_AVAILABLE:
                client = ColmiClient(ring['mac_address'])
            else:
                client = MockColmiR02Client(ring['mac_address'])
                
            # Connect
            connected = await client.connect()
            
            if connected:
                self.clients[ring['mac_address']] = client
                self.db.update_ring_connection(ring_id)
                return True
            else:
                return False
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