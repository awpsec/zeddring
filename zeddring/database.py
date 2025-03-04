"""Database module for Zeddring."""

import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from zeddring.config import DATABASE_PATH


class Database:
    """Database handler for Zeddring."""

    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize the database."""
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create rings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT UNIQUE NOT NULL,
                name TEXT,
                last_seen TIMESTAMP,
                battery_level INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create heart_rate table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS heart_rate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ring_id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                value INTEGER NOT NULL,
                FOREIGN KEY (ring_id) REFERENCES rings (id)
            )
            ''')
            
            # Create steps table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ring_id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                value INTEGER NOT NULL,
                FOREIGN KEY (ring_id) REFERENCES rings (id)
            )
            ''')
            
            # Create spo2 table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS spo2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ring_id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                value INTEGER NOT NULL,
                FOREIGN KEY (ring_id) REFERENCES rings (id)
            )
            ''')
            
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        # Ensure the directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_or_update_ring(self, mac_address: str, name: Optional[str] = None) -> int:
        """Add a new ring or update an existing one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if ring exists
            cursor.execute("SELECT id FROM rings WHERE mac_address = ?", (mac_address,))
            result = cursor.fetchone()
            
            if result:
                # Update existing ring
                if name:
                    cursor.execute(
                        "UPDATE rings SET name = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                        (name, result['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE rings SET last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                        (result['id'],)
                    )
                return result['id']
            else:
                # Add new ring
                cursor.execute(
                    "INSERT INTO rings (mac_address, name, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (mac_address, name)
                )
                return cursor.lastrowid

    def update_ring_battery(self, ring_id: int, battery_level: int) -> None:
        """Update the battery level for a ring."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rings SET battery_level = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (battery_level, ring_id)
            )

    def get_rings(self) -> List[Dict[str, Any]]:
        """Get all registered rings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rings ORDER BY last_seen DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_ring_by_mac(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """Get a ring by MAC address."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rings WHERE mac_address = ?", (mac_address,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_ring_by_id(self, ring_id: int) -> Optional[Dict[str, Any]]:
        """Get a ring by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rings WHERE id = ?", (ring_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_ring_name(self, ring_id: int, name: str) -> None:
        """Update the name of a ring."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE rings SET name = ? WHERE id = ?", (name, ring_id))

    def add_heart_rate(self, ring_id: int, value: int, timestamp: Optional[datetime.datetime] = None) -> None:
        """Add a heart rate measurement."""
        if timestamp is None:
            timestamp = datetime.datetime.now()
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO heart_rate (ring_id, timestamp, value) VALUES (?, ?, ?)",
                (ring_id, timestamp, value)
            )

    def add_steps(self, ring_id: int, value: int, timestamp: Optional[datetime.datetime] = None) -> None:
        """Add a steps measurement."""
        if timestamp is None:
            timestamp = datetime.datetime.now()
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO steps (ring_id, timestamp, value) VALUES (?, ?, ?)",
                (ring_id, timestamp, value)
            )

    def add_spo2(self, ring_id: int, value: int, timestamp: Optional[datetime.datetime] = None) -> None:
        """Add an SPO2 measurement."""
        if timestamp is None:
            timestamp = datetime.datetime.now()
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO spo2 (ring_id, timestamp, value) VALUES (?, ?, ?)",
                (ring_id, timestamp, value)
            )

    def get_heart_rate_data(self, ring_id: int, start_time: Optional[datetime.datetime] = None, 
                           end_time: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """Get heart rate data for a specific ring within a time range."""
        query = "SELECT * FROM heart_rate WHERE ring_id = ?"
        params = [ring_id]
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
            
        query += " ORDER BY timestamp DESC"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_steps_data(self, ring_id: int, start_time: Optional[datetime.datetime] = None, 
                      end_time: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """Get steps data for a specific ring within a time range."""
        query = "SELECT * FROM steps WHERE ring_id = ?"
        params = [ring_id]
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
            
        query += " ORDER BY timestamp DESC"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_spo2_data(self, ring_id: int, start_time: Optional[datetime.datetime] = None, 
                     end_time: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """Get SPO2 data for a specific ring within a time range."""
        query = "SELECT * FROM spo2 WHERE ring_id = ?"
        params = [ring_id]
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
            
        query += " ORDER BY timestamp DESC"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_heart_rate_stats(self, ring_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily heart rate statistics for the last N days."""
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        with self._get_connection() as conn:
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
            
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_steps_stats(self, ring_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily steps statistics for the last N days."""
        start_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        with self._get_connection() as conn:
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
            
            return [dict(row) for row in cursor.fetchall()] 