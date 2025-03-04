"""Bluetooth scanner for Zeddring."""

import asyncio
import logging
from typing import List, Optional
from dataclasses import dataclass

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
except ImportError:
    logging.error("bleak package not installed. Please install it with 'pip install bleak'")
    raise

logger = logging.getLogger("zeddring.scanner")

@dataclass
class RingDevice:
    """Representation of a ring device."""
    name: str
    address: str
    rssi: int

async def _scan_async(timeout: int = 10) -> List[RingDevice]:
    """Scan for BLE devices asynchronously."""
    logger.info(f"Scanning for BLE devices (timeout: {timeout}s)...")
    devices = await BleakScanner.discover(timeout=timeout)
    
    ring_devices = []
    for device in devices:
        if device.name and ("R02" in device.name or "R06" in device.name or "R10" in device.name):
            logger.info(f"Found ring device: {device.name} ({device.address})")
            ring_devices.append(RingDevice(
                name=device.name,
                address=device.address,
                rssi=device.rssi
            ))
    
    return ring_devices

def scan_for_rings(timeout: int = 10) -> List[RingDevice]:
    """Scan for ring devices."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_scan_async(timeout))
    finally:
        loop.close() 