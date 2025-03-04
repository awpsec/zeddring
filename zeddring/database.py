"""Database module for Zeddring."""

import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os
import logging

from zeddring.config import DATABASE_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.database")

# Get database path from environment variable or use default
DB_PATH = os.environ.get('ZEDDRING_DB_PATH', DATABASE_PATH)

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables."""
    logger.info(f"Initializing database at {DB_PATH}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create rings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mac_address TEXT UNIQUE NOT NULL,
        last_connected TIMESTAMP,
        battery_level INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create heart_rate table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS heart_rate (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ring_id INTEGER NOT NULL,
        value INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ring_id) REFERENCES rings (id)
    )
    ''')
    
    # Create steps table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ring_id INTEGER NOT NULL,
        value INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ring_id) REFERENCES rings (id)
    )
    ''')
    
    # Create battery table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS battery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ring_id INTEGER NOT NULL,
        value INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ring_id) REFERENCES rings (id)
    )
    ''')
    
    # Check if battery_level column exists in rings table
    cursor.execute("PRAGMA table_info(rings)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    # Add battery_level column if it doesn't exist
    if 'battery_level' not in column_names:
        try:
            cursor.execute("ALTER TABLE rings ADD COLUMN battery_level INTEGER")
            logger.info("Added battery_level column to rings table")
        except sqlite3.OperationalError:
            logger.info("battery_level column already exists in rings table")
    
    conn.commit()
    conn.close()
    
    logger.info("Database initialized successfully")

class Database:
    """Database class for interacting with the SQLite database."""
    
    def __init__(self):
        """Initialize the database."""
        init_db()
    
    def add_ring(self, name, mac_address):
        """Add a new ring to the database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO rings (name, mac_address) VALUES (?, ?)",
                (name, mac_address)
            )
            conn.commit()
            ring_id = cursor.lastrowid
            logger.info(f"Added new ring: {name} ({mac_address})")
            return ring_id
        except sqlite3.IntegrityError:
            # Ring with this MAC address already exists
            cursor.execute(
                "SELECT id FROM rings WHERE mac_address = ?",
                (mac_address,)
            )
            ring_id = cursor.fetchone()[0]
            logger.info(f"Ring with MAC {mac_address} already exists with ID {ring_id}")
            return ring_id
        finally:
            conn.close()
    
    def update_ring_connection(self, ring_id):
        """Update the last_connected timestamp for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE rings SET last_connected = ? WHERE id = ?",
            (datetime.datetime.now(), ring_id)
        )
        conn.commit()
        conn.close()
    
    def get_rings(self):
        """Get all rings from the database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rings ORDER BY name")
        rings = cursor.fetchall()
        
        conn.close()
        return rings
    
    def get_ring(self, ring_id):
        """Get a specific ring by ID."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rings WHERE id = ?", (ring_id,))
        ring = cursor.fetchone()
        
        conn.close()
        return ring
    
    def get_ring_by_mac(self, mac_address):
        """Get a ring by MAC address."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rings WHERE mac_address = ?", (mac_address,))
        ring = cursor.fetchone()
        
        conn.close()
        return ring
    
    def add_heart_rate(self, ring_id, value):
        """Add a heart rate reading for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO heart_rate (ring_id, value) VALUES (?, ?)",
            (ring_id, value)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Added heart rate {value} for ring {ring_id}")
    
    def add_steps(self, ring_id, value):
        """Add a steps reading for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO steps (ring_id, value) VALUES (?, ?)",
            (ring_id, value)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Added steps {value} for ring {ring_id}")
    
    def add_battery(self, ring_id, value):
        """Add a battery reading for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO battery (ring_id, value) VALUES (?, ?)",
            (ring_id, value)
        )
        conn.commit()
        conn.close()
        logger.debug(f"Added battery {value}% for ring {ring_id}")
    
    def get_heart_rate_data(self, ring_id, limit=100):
        """Get heart rate data for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value, timestamp FROM heart_rate WHERE ring_id = ? ORDER BY timestamp DESC LIMIT ?",
            (ring_id, limit)
        )
        data = cursor.fetchall()
        
        conn.close()
        return data
    
    def get_steps_data(self, ring_id, limit=100):
        """Get steps data for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value, timestamp FROM steps WHERE ring_id = ? ORDER BY timestamp DESC LIMIT ?",
            (ring_id, limit)
        )
        data = cursor.fetchall()
        
        conn.close()
        return data
    
    def get_battery_data(self, ring_id, limit=100):
        """Get battery data for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value, timestamp FROM battery WHERE ring_id = ? ORDER BY timestamp DESC LIMIT ?",
            (ring_id, limit)
        )
        data = cursor.fetchall()
        
        conn.close()
        return data

    def remove_ring(self, ring_id: int) -> bool:
        """Remove a ring and all its data from the database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Start a transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Delete heart rate data
            cursor.execute("DELETE FROM heart_rate WHERE ring_id = ?", (ring_id,))
            
            # Delete steps data
            cursor.execute("DELETE FROM steps WHERE ring_id = ?", (ring_id,))
            
            # Delete battery data
            cursor.execute("DELETE FROM battery WHERE ring_id = ?", (ring_id,))
            
            # Delete the ring
            cursor.execute("DELETE FROM rings WHERE id = ?", (ring_id,))
            
            # Commit the transaction
            conn.commit()
            
            logger.info(f"Removed ring with ID {ring_id}")
            return True
        except Exception as e:
            # Rollback in case of error
            conn.rollback()
            logger.error(f"Error removing ring {ring_id}: {e}")
            return False
        finally:
            conn.close()

    def add_or_update_ring(self, mac_address: str, name: Optional[str] = None) -> int:
        """Add a new ring or update an existing one."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if ring exists
            cursor.execute("SELECT id FROM rings WHERE mac_address = ?", (mac_address,))
            result = cursor.fetchone()
            
            if result:
                # Update existing ring
                if name:
                    cursor.execute(
                        "UPDATE rings SET name = ?, last_connected = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, result['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE rings SET last_connected = CURRENT_TIMESTAMP WHERE id = ?",
                        (result['id'],)
                    )
                conn.commit()
                return result['id']
            else:
                # Add new ring
                cursor.execute(
                    "INSERT INTO rings (mac_address, name, last_connected) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (mac_address, name or f"Ring {mac_address[-5:]}")
                )
                conn.commit()
                return cursor.lastrowid
        finally:
            conn.close()

    def get_daily_heart_rate_stats(self, ring_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily heart rate statistics for the last N days."""
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                MIN(value) as min_value,
                MAX(value) as max_value,
                AVG(value) as avg_value,
                COUNT(*) as count
            FROM heart_rate
            WHERE ring_id = ? AND timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY date DESC
        """, (ring_id, start_date))
        
        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return result

    def get_daily_steps_stats(self, ring_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily steps statistics for the last N days."""
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                MAX(value) as max_value
            FROM steps
            WHERE ring_id = ? AND timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY date DESC
        """, (ring_id, start_date))
        
        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return result

    def update_ring_battery(self, ring_id: int, battery_level: int) -> None:
        """Update the battery level for a ring."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "UPDATE rings SET battery_level = ?, last_connected = CURRENT_TIMESTAMP WHERE id = ?",
                (battery_level, ring_id)
            )
            conn.commit()
            logger.debug(f"Updated battery level for ring {ring_id} to {battery_level}%")
        except Exception as e:
            logger.error(f"Error updating battery level for ring {ring_id}: {e}")
        finally:
            conn.close()

    def add_heart_rate_with_timestamp(self, ring_id: int, value: int, timestamp: datetime.datetime) -> None:
        """Add a heart rate reading with a specific timestamp."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO heart_rate (ring_id, value, timestamp) VALUES (?, ?, ?)",
                (ring_id, value, timestamp)
            )
            conn.commit()
            logger.debug(f"Added heart rate {value} for ring {ring_id} at {timestamp}")
        except Exception as e:
            logger.error(f"Error adding heart rate for ring {ring_id}: {e}")
        finally:
            conn.close()
            
    def add_steps_with_timestamp(self, ring_id: int, value: int, timestamp: datetime.datetime) -> None:
        """Add a steps reading with a specific timestamp."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO steps (ring_id, value, timestamp) VALUES (?, ?, ?)",
                (ring_id, value, timestamp)
            )
            conn.commit()
            logger.debug(f"Added steps {value} for ring {ring_id} at {timestamp}")
        except Exception as e:
            logger.error(f"Error adding steps for ring {ring_id}: {e}")
        finally:
            conn.close()
            
    def add_battery_with_timestamp(self, ring_id: int, value: int, timestamp: datetime.datetime) -> None:
        """Add a battery reading with a specific timestamp."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO battery (ring_id, value, timestamp) VALUES (?, ?, ?)",
                (ring_id, value, timestamp)
            )
            conn.commit()
            logger.debug(f"Added battery {value}% for ring {ring_id} at {timestamp}")
        except Exception as e:
            logger.error(f"Error adding battery for ring {ring_id}: {e}")
        finally:
            conn.close() 