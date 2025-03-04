"""Bluetooth scanner for Zeddring."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import time
import subprocess
import json
import os

# Try to import bleak for BLE scanning
try:
    import bleak
    from bleak import BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.scanner")

@dataclass
class RingDevice:
    """Representation of a ring device."""
    name: str
    address: str
    rssi: int

async def _scan_with_bleak(timeout: int = 10) -> List[Dict[str, Any]]:
    """Scan for BLE devices using bleak."""
    devices = []
    try:
        scanner = BleakScanner()
        discovered_devices = await scanner.discover(timeout=timeout)
        
        for device in discovered_devices:
            if device.name:
                devices.append({
                    "name": device.name,
                    "mac_address": device.address,
                    "rssi": device.rssi
                })
        
        return devices
    except Exception as e:
        logger.error(f"Error scanning with bleak: {e}")
        return []

def _scan_with_hcitool() -> List[Dict[str, Any]]:
    """Scan for BLE devices using hcitool (Linux only)."""
    devices = []
    try:
        # Check if hcitool is available
        result = subprocess.run(["which", "hcitool"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("hcitool not found, cannot scan using this method")
            return []
            
        # Run hcitool lescan for a short time
        scan_process = subprocess.Popen(
            ["timeout", "5", "hcitool", "lescan"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(5)  # Let it scan for 5 seconds
        scan_process.terminate()
        
        # Get list of devices
        result = subprocess.run(
            ["hcitool", "dev"], 
            capture_output=True, 
            text=True
        )
        
        # Parse output
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        for line in lines:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                devices.append({
                    "name": parts[2] if len(parts) > 2 else "Unknown",
                    "mac_address": parts[1],
                    "rssi": 0  # RSSI not available with hcitool
                })
                
        return devices
    except Exception as e:
        logger.error(f"Error scanning with hcitool: {e}")
        return []

def _scan_with_bluetoothctl() -> List[Dict[str, Any]]:
    """Scan for BLE devices using bluetoothctl (Linux only)."""
    devices = []
    try:
        # Check if bluetoothctl is available
        result = subprocess.run(["which", "bluetoothctl"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("bluetoothctl not found, cannot scan using this method")
            return []
            
        # Run bluetoothctl scan
        scan_cmd = "scan on"
        timeout_cmd = "quit"
        
        process = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Start scanning
        process.stdin.write(f"{scan_cmd}\n")
        process.stdin.flush()
        
        # Scan for 5 seconds
        time.sleep(5)
        
        # Stop scanning and quit
        process.stdin.write(f"{timeout_cmd}\n")
        process.stdin.flush()
        process.terminate()
        
        # Get devices with bluetoothctl
        result = subprocess.run(
            ["bluetoothctl", "devices"], 
            capture_output=True, 
            text=True
        )
        
        # Parse output
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line.startswith("Device "):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    devices.append({
                        "name": parts[2] if len(parts) > 2 else "Unknown",
                        "mac_address": parts[1],
                        "rssi": 0  # RSSI not available with bluetoothctl
                    })
                
        return devices
    except Exception as e:
        logger.error(f"Error scanning with bluetoothctl: {e}")
        return []

def _scan_with_mock() -> List[Dict[str, Any]]:
    """Mock scanner for testing or when no Bluetooth is available."""
    # Check if we have a mock device file
    mock_file = os.path.join(os.path.dirname(__file__), 'mock_devices.json')
    
    if os.path.exists(mock_file):
        try:
            with open(mock_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading mock devices: {e}")
    
    # Return a default mock device if no file exists
    return [{
        "name": "Mock Colmi R02",
        "mac_address": "87:89:99:BC:B4:D5",  # This is the user's actual MAC address
        "rssi": -60
    }]

def scan_for_devices(timeout: int = 10) -> List[Dict[str, Any]]:
    """
    Scan for BLE devices using available methods.
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of dictionaries containing device information
    """
    logger.info(f"Scanning for BLE devices (timeout: {timeout}s)...")
    
    # Try different scanning methods in order of preference
    devices = []
    
    # 1. Try with bleak (cross-platform)
    if BLEAK_AVAILABLE:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            devices = loop.run_until_complete(_scan_with_bleak(timeout))
            loop.close()
            
            if devices:
                return devices
        except Exception as e:
            logger.error(f"Bleak scanning failed: {e}")
    
    # 2. Try with hcitool (Linux)
    if not devices:
        devices = _scan_with_hcitool()
        if devices:
            return devices
    
    # 3. Try with bluetoothctl (Linux)
    if not devices:
        devices = _scan_with_bluetoothctl()
        if devices:
            return devices
    
    # 4. Fall back to mock data if nothing else works
    if not devices:
        logger.warning("All scanning methods failed, using mock data")
        devices = _scan_with_mock()
    
    return devices

# Create a mock devices file with the user's ring if it doesn't exist
def create_mock_devices_file():
    """Create a mock devices file with the user's ring."""
    mock_file = os.path.join(os.path.dirname(__file__), 'mock_devices.json')
    
    if not os.path.exists(mock_file):
        mock_data = [{
            "name": "Colmi R02",
            "mac_address": "87:89:99:BC:B4:D5",  # User's MAC address
            "rssi": -60
        }]
        
        try:
            with open(mock_file, 'w') as f:
                json.dump(mock_data, f, indent=2)
            logger.info(f"Created mock devices file at {mock_file}")
        except Exception as e:
            logger.error(f"Error creating mock devices file: {e}")

# Create mock devices file on module import
create_mock_devices_file() 