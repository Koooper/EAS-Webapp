"""
SQLite database for alert archive.
"""

import sqlite3
import json
import base64
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class ArchivedAlert:
    """Represents an archived alert."""
    id: int
    created_at: datetime
    originator: str
    event: str
    locations: List[str]
    duration: int
    callsign: str
    header: str
    audio_data: Optional[bytes] = None
    has_voice: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self, include_audio: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'originator': self.originator,
            'event': self.event,
            'locations': self.locations,
            'duration': self.duration,
            'callsign': self.callsign,
            'header': self.header,
            'has_voice': self.has_voice,
            'has_audio': self.audio_data is not None
        }

        if include_audio and self.audio_data:
            result['audio'] = base64.b64encode(self.audio_data).decode('utf-8')

        if self.metadata:
            result['metadata'] = self.metadata

        return result


class AlertArchive:
    """
    SQLite-based alert archive with search and filter capabilities.
    """

    def __init__(self, db_path: str = 'alerts.db'):
        """Initialize archive with database path."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    originator TEXT NOT NULL,
                    event TEXT NOT NULL,
                    locations TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    callsign TEXT NOT NULL,
                    header TEXT NOT NULL,
                    audio_data BLOB,
                    has_voice INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT
                )
            ''')

            # create indices for common queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_event ON alerts(event)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_originator ON alerts(originator)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON alerts(created_at)')

            conn.commit()

    def add_alert(
        self,
        originator: str,
        event: str,
        locations: List[str],
        duration: int,
        callsign: str,
        header: str,
        audio_data: Optional[bytes] = None,
        has_voice: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add an alert to the archive.

        Returns:
            alert ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO alerts (
                    created_at, originator, event, locations,
                    duration, callsign, header, audio_data,
                    has_voice, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                originator,
                event,
                json.dumps(locations),
                duration,
                callsign,
                header,
                audio_data,
                1 if has_voice else 0,
                json.dumps(metadata) if metadata else None
            ))

            conn.commit()
            return cursor.lastrowid

    def get_alert(self, alert_id: int) -> Optional[ArchivedAlert]:
        """Get alert by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_alert(row)

    def search_alerts(
        self,
        event: Optional[str] = None,
        originator: Optional[str] = None,
        location: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        has_voice: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ArchivedAlert]:
        """
        Search alerts with filters.

        Args:
            event: Filter by event code
            originator: Filter by originator code
            location: Filter by location code (FIPS)
            start_date: Filter by start date
            end_date: Filter by end date
            has_voice: Filter by voice presence
            limit: Max results
            offset: Result offset

        Returns:
            List of matching alerts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = 'SELECT * FROM alerts WHERE 1=1'
            params = []

            if event:
                query += ' AND event = ?'
                params.append(event)

            if originator:
                query += ' AND originator = ?'
                params.append(originator)

            if location:
                query += ' AND locations LIKE ?'
                params.append(f'%"{location}"%')

            if start_date:
                query += ' AND created_at >= ?'
                params.append(start_date.isoformat())

            if end_date:
                query += ' AND created_at <= ?'
                params.append(end_date.isoformat())

            if has_voice is not None:
                query += ' AND has_voice = ?'
                params.append(1 if has_voice else 0)

            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_alert(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # total count
            cursor.execute('SELECT COUNT(*) FROM alerts')
            total_count = cursor.fetchone()[0]

            # counts by event
            cursor.execute('''
                SELECT event, COUNT(*) as count
                FROM alerts
                GROUP BY event
                ORDER BY count DESC
                LIMIT 10
            ''')
            event_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # counts by originator
            cursor.execute('''
                SELECT originator, COUNT(*) as count
                FROM alerts
                GROUP BY originator
            ''')
            originator_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # voice stats
            cursor.execute('SELECT COUNT(*) FROM alerts WHERE has_voice = 1')
            voice_count = cursor.fetchone()[0]

            # date range
            cursor.execute('SELECT MIN(created_at), MAX(created_at) FROM alerts')
            min_date, max_date = cursor.fetchone()

            return {
                'total_count': total_count,
                'event_counts': event_counts,
                'originator_counts': originator_counts,
                'voice_count': voice_count,
                'no_voice_count': total_count - voice_count,
                'date_range': {
                    'earliest': min_date,
                    'latest': max_date
                }
            }

    def delete_alert(self, alert_id: int) -> bool:
        """Delete an alert by ID. Returns True if deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM alerts WHERE id = ?', (alert_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_alert(self, row: sqlite3.Row) -> ArchivedAlert:
        """Convert database row to ArchivedAlert."""
        return ArchivedAlert(
            id=row['id'],
            created_at=datetime.fromisoformat(row['created_at']),
            originator=row['originator'],
            event=row['event'],
            locations=json.loads(row['locations']),
            duration=row['duration'],
            callsign=row['callsign'],
            header=row['header'],
            audio_data=row['audio_data'],
            has_voice=bool(row['has_voice']),
            metadata=json.loads(row['metadata']) if row['metadata'] else None
        )
