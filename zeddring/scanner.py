"""Custom scanner module for Zeddring."""

import logging
import subprocess
import time
import random
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
    
    # If no devices found with any method, return a mock device
    if not devices:
        logger.warning("No devices found, returning mock device")
        devices = [ColmiDevice(name="Mock Colmi R02", address="87:89:99:BC:B4:D5")]
    
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
        import asyncio
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
        self._steps = 1000
        self._heart_rate = [70, 72, 75]
        
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
        self._battery = max(0, self._battery - 1)
        return self._battery
            
    def get_steps(self):
        """Mock get_steps method."""
        logger.info(f"Mock getting steps for {self.address}")
        # Simulate steps increasing
        self._steps += 100
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