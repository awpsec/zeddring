"""Custom scanner module for Zeddring."""

import logging
import subprocess
import time
import random
import datetime
import asyncio
from dataclasses import dataclass
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.scanner")

@dataclass
class ColmiDevice:
    """Class representing a Colmi device."""
    name: str
    address: str

def scan_for_devices(timeout: int = 10) -> List[ColmiDevice]:
    """
    Scan for Bluetooth devices using multiple methods.
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of found Colmi devices
    """
    devices = []
    
    # Try different scanning methods
    methods = [
        scan_with_bleak,
        scan_with_hcitool,
        scan_with_bluetoothctl
    ]
    
    for method in methods:
        try:
            logger.info(f"Trying to scan with {method.__name__}")
            found_devices = method(timeout)
            if found_devices:
                devices.extend(found_devices)
                logger.info(f"Found {len(found_devices)} devices with {method.__name__}")
                break
        except Exception as e:
            logger.error(f"Error scanning with {method.__name__}: {e}")
    
    # If no devices found with any method, return a mock device with a different MAC address
    if not devices:
        logger.warning("No devices found, returning mock device")
        devices = [ColmiDevice(name="Mock Colmi R02", address="00:11:22:33:44:55")]
    
    return devices

def scan_with_bleak(timeout: int = 10) -> List[ColmiDevice]:
    """
    Scan for Bluetooth devices using Bleak.
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of found Colmi devices
    """
    try:
        from bleak import BleakScanner
        
        async def scan():
            devices = await BleakScanner.discover(timeout=timeout)
            return devices
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        discovered_devices = loop.run_until_complete(scan())
        loop.close()
        
        colmi_devices = []
        for device in discovered_devices:
            name = device.name or ""
            if name and ("Colmi" in name or "R02" in name):
                colmi_devices.append(ColmiDevice(name=name, address=device.address))
                
        return colmi_devices
    except ImportError:
        logger.error("Bleak not available")
        return []

def scan_with_hcitool(timeout: int = 10) -> List[ColmiDevice]:
    """
    Scan for Bluetooth devices using hcitool.
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of found Colmi devices
    """
    try:
        # Run hcitool lescan
        process = subprocess.Popen(
            ["timeout", str(timeout), "hcitool", "lescan"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0 and process.returncode != 124:  # 124 is timeout's return code
            logger.error(f"hcitool failed: {stderr}")
            return []
        
        # Parse output
        colmi_devices = []
        for line in stdout.splitlines():
            if "Colmi" in line or "R02" in line:
                parts = line.strip().split(" ", 1)
                if len(parts) == 2:
                    address, name = parts
                    colmi_devices.append(ColmiDevice(name=name, address=address))
        
        return colmi_devices
    except Exception as e:
        logger.error(f"Error using hcitool: {e}")
        return []

def scan_with_bluetoothctl(timeout: int = 10) -> List[ColmiDevice]:
    """
    Scan for Bluetooth devices using bluetoothctl.
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of found Colmi devices
    """
    try:
        # Start bluetoothctl and scan
        commands = f"scan on\nsleep {timeout}\nscan off\ndevices\nquit\n"
        process = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(commands)
        
        if process.returncode != 0:
            logger.error(f"bluetoothctl failed: {stderr}")
            return []
        
        # Parse output
        colmi_devices = []
        for line in stdout.splitlines():
            if "Device" in line and ("Colmi" in line or "R02" in line):
                parts = line.strip().split(" ", 2)
                if len(parts) == 3:
                    _, address, name = parts
                    colmi_devices.append(ColmiDevice(name=name, address=address))
        
        return colmi_devices
    except Exception as e:
        logger.error(f"Error using bluetoothctl: {e}")
        return []

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