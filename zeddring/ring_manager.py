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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.ring_manager")

# Try to import the colmi_r02_client package
try:
    from colmi_r02_client import Client
    from colmi_r02_client.client import Client as ColmiClient
    COLMI_CLIENT_AVAILABLE = True
except ImportError:
    logger.warning("colmi_r02_client not available, using mock client")
    COLMI_CLIENT_AVAILABLE = False
    ColmiClient = None

# Import our custom scanner
from zeddring.scanner import scan_for_devices

# Import database functions
from zeddring.database import get_db_connection, init_db

# Import config
try:
    from zeddring.config import SCAN_INTERVAL, SCAN_TIMEOUT, MAX_RETRY_ATTEMPTS, RETRY_DELAY
except ImportError:
    # Default values if config is not available
    SCAN_INTERVAL = 60
    SCAN_TIMEOUT = 10
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 300

class MockClient:
    """Mock client for testing when colmi_r02_client is not available."""
    
    def __init__(self, mac_address: str):
        self.mac_address = mac_address
        self.connected = False
        self.battery = 85
        self.steps = 0
        self.heart_rate = 70
        self._last_update = time.time()
        
    async def connect(self):
        """Connect to the device."""
        logger.info(f"Mock connecting to {self.mac_address}")
        self.connected = True
        return True
        
    async def disconnect(self):
        """Disconnect from the device."""
        logger.info(f"Mock disconnecting from {self.mac_address}")
        self.connected = False
        return True
        
    async def get_battery(self):
        """Get battery level."""
        # Decrease battery by 1% every hour
        hours_passed = (time.time() - self._last_update) / 3600
        self.battery = max(0, self.battery - int(hours_passed))
        return self.battery
        
    async def get_steps(self):
        """Get step count."""
        # Increase steps by 100-200 every hour
        hours_passed = (time.time() - self._last_update) / 3600
        self.steps += int(100 + 100 * hours_passed)
        return self.steps
        
    async def get_heart_rate(self):
        """Get heart rate."""
        # Fluctuate heart rate between 60-80
        import random
        self.heart_rate = random.randint(60, 80)
        return self.heart_rate
        
    def get_info(self):
        """Get device info."""
        return {
            "name": "Colmi R02",
            "mac_address": self.mac_address,
            "firmware_version": "1.0.0",
            "hardware_version": "1.0.0"
        }
        
    def is_connected(self):
        """Check if connected."""
        return self.connected

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
                self.client = MockClient(self.mac_address)
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
    """Manages smart ring devices."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.rings: Dict[int, Ring] = {}
        self.db_path = db_path
        self.scan_thread = None
        self.running = False
        self.event_loop = None
        
        # Initialize database
        init_db(db_path)
        
        # Load rings from database
        self._load_rings_from_db()
        
    def _load_rings_from_db(self):
        """Load rings from database."""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, mac_address FROM rings")
        rows = cursor.fetchall()
        
        for row in rows:
            ring_id, name, mac_address = row
            self.rings[ring_id] = Ring(ring_id, name, mac_address)
            
        conn.close()
        
    def add_ring(self, name: str, mac_address: str) -> Optional[int]:
        """Add a new ring."""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            # Check if ring with this MAC address already exists
            cursor.execute("SELECT id FROM rings WHERE mac_address = ?", (mac_address,))
            existing = cursor.fetchone()
            
            if existing:
                ring_id = existing[0]
                # Update name if different
                cursor.execute("UPDATE rings SET name = ? WHERE id = ?", (name, ring_id))
                conn.commit()
            else:
                # Insert new ring
                cursor.execute(
                    "INSERT INTO rings (name, mac_address) VALUES (?, ?)",
                    (name, mac_address)
                )
                conn.commit()
                ring_id = cursor.lastrowid
                
            # Create ring object
            self.rings[ring_id] = Ring(ring_id, name, mac_address)
            
            conn.close()
            return ring_id
        except Exception as e:
            logger.error(f"Error adding ring: {e}")
            return None
            
    def remove_ring(self, ring_id: int) -> bool:
        """Remove a ring."""
        try:
            if ring_id not in self.rings:
                return False
                
            # Disconnect if connected
            ring = self.rings[ring_id]
            if ring.connected:
                asyncio.run(ring.disconnect())
                
            # Remove from database
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM rings WHERE id = ?", (ring_id,))
            conn.commit()
            conn.close()
            
            # Remove from memory
            del self.rings[ring_id]
            
            return True
        except Exception as e:
            logger.error(f"Error removing ring: {e}")
            return False
            
    def get_ring(self, ring_id: int) -> Optional[Ring]:
        """Get a ring by ID."""
        return self.rings.get(ring_id)
        
    def get_all_rings(self) -> List[Dict[str, Any]]:
        """Get all rings."""
        return [ring.to_dict() for ring in self.rings.values()]
        
    async def connect_ring(self, ring_id: int) -> bool:
        """Connect to a ring."""
        ring = self.get_ring(ring_id)
        if not ring:
            return False
            
        return await ring.connect()
        
    async def disconnect_ring(self, ring_id: int) -> bool:
        """Disconnect from a ring."""
        ring = self.get_ring(ring_id)
        if not ring:
            return False
            
        return await ring.disconnect()
        
    async def get_ring_data(self, ring_id: int) -> Optional[Dict[str, Any]]:
        """Get data from a ring."""
        ring = self.get_ring(ring_id)
        if not ring:
            return None
            
        return await ring.update_all()
        
    def save_ring_data(self, ring_id: int, data: Dict[str, Any]):
        """Save ring data to database."""
        try:
            if not data:
                return False
                
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            
            # Insert data
            cursor.execute(
                """
                INSERT INTO ring_data 
                (ring_id, timestamp, heart_rate, steps, battery) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ring_id, 
                    timestamp, 
                    data.get("heart_rate"), 
                    data.get("steps"), 
                    data.get("battery")
                )
            )
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            logger.error(f"Error saving ring data: {e}")
            return False
            
    def get_ring_history(self, ring_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get ring data history."""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT timestamp, heart_rate, steps, battery 
                FROM ring_data 
                WHERE ring_id = ? 
                AND timestamp > datetime('now', '-' || ? || ' days')
                ORDER BY timestamp ASC
                """,
                (ring_id, days)
            )
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                timestamp, heart_rate, steps, battery = row
                history.append({
                    "timestamp": timestamp,
                    "heart_rate": heart_rate,
                    "steps": steps,
                    "battery": battery
                })
                
            conn.close()
            return history
        except Exception as e:
            logger.error(f"Error getting ring history: {e}")
            return []
            
    def get_daily_data(self, ring_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """Get daily data for a ring."""
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
                
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            # Get data for the specified date
            cursor.execute(
                """
                SELECT timestamp, heart_rate, steps, battery 
                FROM ring_data 
                WHERE ring_id = ? 
                AND date(timestamp) = date(?)
                ORDER BY timestamp ASC
                """,
                (ring_id, date)
            )
            
            rows = cursor.fetchall()
            
            # Process data
            timestamps = []
            heart_rates = []
            steps_data = []
            battery_levels = []
            
            for row in rows:
                timestamp, heart_rate, steps, battery = row
                # Convert timestamp to hours:minutes format for display
                dt = datetime.fromisoformat(timestamp)
                hour_minute = dt.strftime("%H:%M")
                
                timestamps.append(hour_minute)
                heart_rates.append(heart_rate if heart_rate is not None else 0)
                steps_data.append(steps if steps is not None else 0)
                battery_levels.append(battery if battery is not None else 0)
                
            # Calculate daily stats
            avg_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else 0
            max_heart_rate = max(heart_rates) if heart_rates else 0
            min_heart_rate = min([hr for hr in heart_rates if hr > 0]) if heart_rates else 0
            last_steps = steps_data[-1] if steps_data else 0
            last_battery = battery_levels[-1] if battery_levels else 0
            
            conn.close()
            
            return {
                "date": date,
                "timestamps": timestamps,
                "heart_rates": heart_rates,
                "steps": steps_data,
                "battery_levels": battery_levels,
                "avg_heart_rate": round(avg_heart_rate, 1),
                "max_heart_rate": max_heart_rate,
                "min_heart_rate": min_heart_rate,
                "last_steps": last_steps,
                "last_battery": last_battery
            }
        except Exception as e:
            logger.error(f"Error getting daily data: {e}")
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "timestamps": [],
                "heart_rates": [],
                "steps": [],
                "battery_levels": [],
                "avg_heart_rate": 0,
                "max_heart_rate": 0,
                "min_heart_rate": 0,
                "last_steps": 0,
                "last_battery": 0
            }
            
    def _scan_loop(self):
        """Background thread for scanning for rings."""
        logger.info("Ring manager started")
        
        while self.running:
            try:
                logger.info("Scanning for rings...")
                
                # Scan for devices
                try:
                    devices = scan_for_devices(timeout=10)
                except Exception as e:
                    logger.error(f"Error in scan loop: {e}")
                    time.sleep(10)
                    continue
                    
                # Check if any of the devices match our rings
                for device in devices:
                    mac_address = device.get("mac_address")
                    
                    # Find ring with this MAC address
                    for ring_id, ring in self.rings.items():
                        if ring.mac_address.lower() == mac_address.lower():
                            # Try to connect if not already connected
                            if not ring.connected:
                                logger.info(f"Found ring {ring.name} ({mac_address}), connecting...")
                                
                                # Create a new event loop for this thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                # Connect to the ring
                                success = loop.run_until_complete(ring.connect())
                                
                                if success:
                                    # Get initial data
                                    data = loop.run_until_complete(ring.update_all())
                                    
                                    # Save data to database
                                    if data:
                                        self.save_ring_data(ring_id, data)
                                        
                                loop.close()
                
                # Update data for connected rings
                for ring_id, ring in self.rings.items():
                    if ring.connected:
                        try:
                            # Create a new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            # Get data
                            data = loop.run_until_complete(ring.update_all())
                            
                            # Save data to database
                            if data:
                                self.save_ring_data(ring_id, data)
                                
                            loop.close()
                        except Exception as e:
                            logger.error(f"Error updating ring {ring.mac_address}: {e}")
                            
                # Sleep for a while
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                time.sleep(10)
                
    def start(self):
        """Start the ring manager."""
        if self.running:
            return
            
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop)
        self.scan_thread.daemon = True
        self.scan_thread.start()
        
    def stop(self):
        """Stop the ring manager."""
        self.running = False
        
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
            
        # Disconnect all rings
        for ring_id, ring in self.rings.items():
            if ring.connected:
                asyncio.run(ring.disconnect())

# Singleton instance
_instance = None

def get_ring_manager(db_path: Optional[str] = None) -> RingManager:
    """Get the ring manager instance."""
    global _instance
    
    if _instance is None:
        _instance = RingManager(db_path)
        
    return _instance 