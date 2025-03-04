"""Custom scanner module for Zeddring."""

import logging
import subprocess
import time
import random
import datetime
import asyncio
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from bleak import BleakScanner, BleakError
from zeddring.database import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.scanner")

# Define the Colmi device name pattern
COLMI_DEVICE_PATTERN = re.compile(r'colmi', re.IGNORECASE)

@dataclass
class ColmiDevice:
    """Class representing a Colmi device."""
    name: str
    address: str

async def scan_with_bleak(timeout: int = 10) -> List[Dict[str, Any]]:
    """Scan for BLE devices using Bleak."""
    logger.info("Scanning for Bluetooth devices using Bleak...")
    try:
        devices = await BleakScanner.discover(timeout=timeout)
        logger.info(f"Found {len(devices)} devices with Bleak")
        
        found_devices = []
        for device in devices:
            device_info = {
                "address": device.address,
                "name": device.name or "Unknown",
                "rssi": device.rssi,
                "metadata": device.metadata
            }
            logger.debug(f"Found device: {device_info}")
            found_devices.append(device_info)
        
        return found_devices
    except BleakError as e:
        logger.error(f"Bleak scanning error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during Bleak scanning: {e}")
        return []

def scan_with_hcitool() -> List[Dict[str, Any]]:
    """Scan for BLE devices using hcitool."""
    logger.info("Scanning for Bluetooth devices using hcitool...")
    try:
        # Run hcitool lescan for a short time
        process = subprocess.Popen(
            ["timeout", "5", "hcitool", "lescan"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(5)  # Give it time to scan
        process.terminate()
        
        # Now get the cached results
        result = subprocess.run(
            ["hcitool", "leinfo", "--cached"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.warning(f"hcitool command failed: {result.stderr}")
            return []
        
        # Parse the output
        found_devices = []
        lines = result.stdout.strip().split('\n')
        current_device = None
        
        for line in lines:
            if ":" in line and len(line.split(':')) == 6:  # MAC address format
                mac = line.strip()
                current_device = {
                    "address": mac,
                    "name": "Unknown",
                    "rssi": None
                }
                found_devices.append(current_device)
            elif current_device and "Name" in line:
                name_match = re.search(r'Name:\s+(.+)', line)
                if name_match:
                    current_device["name"] = name_match.group(1)
        
        logger.info(f"Found {len(found_devices)} devices with hcitool")
        return found_devices
    except Exception as e:
        logger.error(f"Error scanning with hcitool: {e}")
        return []

def scan_with_bluetoothctl() -> List[Dict[str, Any]]:
    """Scan for BLE devices using bluetoothctl."""
    logger.info("Scanning for Bluetooth devices using bluetoothctl...")
    try:
        # Start scan
        subprocess.run(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        
        # Wait for scan to collect some data
        time.sleep(5)
        
        # Get devices
        result = subprocess.run(
            ["bluetoothctl", "devices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Stop scan
        subprocess.run(
            ["bluetoothctl", "scan", "off"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if result.returncode != 0:
            logger.warning(f"bluetoothctl command failed: {result.stderr}")
            return []
        
        # Parse the output
        found_devices = []
        device_pattern = re.compile(r'Device\s+([0-9A-F:]+)\s+(.*)')
        
        for line in result.stdout.strip().split('\n'):
            match = device_pattern.match(line)
            if match:
                mac, name = match.groups()
                device_info = {
                    "address": mac,
                    "name": name or "Unknown",
                    "rssi": None
                }
                found_devices.append(device_info)
        
        logger.info(f"Found {len(found_devices)} devices with bluetoothctl")
        return found_devices
    except Exception as e:
        logger.error(f"Error scanning with bluetoothctl: {e}")
        return []

def is_colmi_device(device: Dict[str, Any]) -> bool:
    """Check if a device is a Colmi device based on its name."""
    name = device.get("name", "").lower()
    return bool(COLMI_DEVICE_PATTERN.search(name))

async def scan_for_devices(timeout: int = 10) -> List[Dict[str, Any]]:
    """
    Scan for Colmi devices using multiple methods.
    Returns a list of found Colmi devices.
    """
    logger.info("Starting scan for Colmi devices...")
    
    # Try different scanning methods
    all_devices = []
    
    # Method 1: Bleak
    bleak_devices = await scan_with_bleak(timeout)
    all_devices.extend(bleak_devices)
    
    # If Bleak didn't find any devices, try other methods
    if not bleak_devices:
        logger.warning("Bleak scanning found no devices, trying alternative methods")
        
        # Method 2: hcitool
        hcitool_devices = scan_with_hcitool()
        all_devices.extend(hcitool_devices)
        
        # Method 3: bluetoothctl
        if not hcitool_devices:
            bluetoothctl_devices = scan_with_bluetoothctl()
            all_devices.extend(bluetoothctl_devices)
    
    # Filter for Colmi devices
    colmi_devices = [device for device in all_devices if is_colmi_device(device)]
    logger.info(f"Found {len(colmi_devices)} Colmi devices out of {len(all_devices)} total devices")
    
    # If no devices found, log a warning but don't add a mock device
    if not colmi_devices:
        logger.warning("No Colmi devices found during scan")
    
    return colmi_devices

class MockColmiR02Client:
    """Mock implementation of ColmiR02Client for testing."""
    
    def __init__(self, address):
        """Initialize the mock client."""
        self.address = address
        self.connected = False
        self._battery = 75
        self._steps = 1100
        self._heart_rate = [70, 72, 75]
        self._last_sync = datetime.datetime.now() - datetime.timedelta(hours=6)
        self._historical_data = {
            'steps_history': [],
            'heart_rate_history': []
        }
        self._time_set = False
        
        # Generate some historical data
        self._generate_historical_data()
        
    def _generate_historical_data(self):
        """Generate mock historical data."""
        # Generate data for the past 24 hours
        now = datetime.datetime.now()
        for i in range(24):
            timestamp = now - datetime.timedelta(hours=i)
            
            # Add steps data (increasing throughout the day)
            steps_value = 5000 - (i * 200) + random.randint(-100, 100)
            steps_value = max(0, steps_value)  # Ensure non-negative
            
            self._historical_data['steps_history'].append({
                'timestamp': timestamp.isoformat(),
                'value': steps_value
            })
            
            # Add heart rate data (varying throughout the day)
            base_hr = 70
            if i < 8:  # Sleeping hours
                base_hr = 60
            elif i > 16:  # Evening activity
                base_hr = 75
                
            hr_value = base_hr + random.randint(-5, 10)
            
            self._historical_data['heart_rate_history'].append({
                'timestamp': timestamp.isoformat(),
                'value': hr_value
            })
            
    async def connect(self):
        """Mock connect method."""
        logger.info(f"Mock connecting to {self.address}")
        self.connected = True
        return True
            
    async def disconnect(self):
        """Mock disconnect method."""
        logger.info(f"Mock disconnecting from {self.address}")
        self.connected = False
        return True
        
    def get_battery(self):
        """Mock get_battery method."""
        logger.info(f"Mock getting battery for {self.address}")
        # Simulate battery drain
        self._battery = max(0, self._battery - random.randint(0, 2))
        return self._battery
            
    def get_steps(self):
        """Mock get_steps method."""
        logger.info(f"Mock getting steps for {self.address}")
        # Simulate steps increasing more realistically
        time_since_last_sync = (datetime.datetime.now() - self._last_sync).total_seconds()
        # Add 10-30 steps per minute on average
        steps_to_add = int((time_since_last_sync / 60) * random.randint(10, 30))
        self._steps += steps_to_add
        self._last_sync = datetime.datetime.now()
        return self._steps
            
    def get_real_time_heart_rate(self):
        """Mock get_real_time_heart_rate method."""
        logger.info(f"Mock getting heart rate for {self.address}")
        # Simulate heart rate fluctuations
        self._heart_rate = [
            max(60, min(100, hr + random.randint(-5, 5)))
            for hr in self._heart_rate
        ]
        return self._heart_rate
        
    async def get_heart_rate(self):
        """Mock get_heart_rate method."""
        logger.info(f"Mock getting heart rate for {self.address}")
        # Simulate heart rate fluctuations
        hr = max(60, min(100, self._heart_rate[0] + random.randint(-5, 5)))
        self._heart_rate[0] = hr
        return hr
        
    async def get_historical_data(self):
        """Mock get_historical_data method."""
        logger.info(f"Mock getting historical data for {self.address}")
        return self._historical_data
        
    async def set_time(self, current_time):
        """Mock set_time method."""
        logger.info(f"Mock setting time for {self.address} to {current_time}")
        self._time_set = True
        return True
        
    async def reboot(self):
        """Mock reboot method."""
        logger.info(f"Mock rebooting {self.address}")
        self.connected = False
        # Simulate reboot time
        await asyncio.sleep(2)
        return True 