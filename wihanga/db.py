"""Local-only sightings log (SQLite). Nothing is ever uploaded anywhere."""
from __future__ import annotations

import csv
import io
import sqlite3
import threading
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS sightings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    common_name     TEXT    NOT NULL,
    scientific_name TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    endemic         INTEGER NOT NULL DEFAULT 0,
    lat             REAL,
    lon             REAL
);
CREATE INDEX IF NOT EXISTS idx_sci_ts ON sightings (scientific_name, ts);
"""

CSV_FIELDS = ["ts", "common_name", "scientific_name", "confidence", "endemic", "lat", "lon"]


class SightingsDB:
    def __init__(self, path: str = "sightings.db", dedupe_seconds: int = 300):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._dedupe = timedelta(seconds=dedupe_seconds)
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def log(
        self,
        common_name: str,
        scientific_name: str,
        confidence: float,
        endemic: bool,
        lat: float | None = None,
        lon: float | None = None,
        now: datetime | None = None,
    ) -> bool:
        """Record a sighting. Returns False if the same species was already
        logged within the dedupe window (the same bird singing for a minute
        should be one sighting, not ten)."""
        now = now or datetime.now()
        cutoff = (now - self._dedupe).isoformat(timespec="seconds")
        with self._lock:
            seen = self._conn.execute(
                "SELECT 1 FROM sightings WHERE scientific_name = ? AND ts >= ? LIMIT 1",
                (scientific_name, cutoff),
            ).fetchone()
            if seen:
                return False
            self._conn.execute(
                "INSERT INTO sightings (ts, common_name, scientific_name, confidence, endemic, lat, lon)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    now.isoformat(timespec="seconds"),
                    common_name,
                    scientific_name,
                    round(float(confidence), 3),
                    int(bool(endemic)),
                    lat,
                    lon,
                ),
            )
            self._conn.commit()
            return True

    def recent(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, common_name, scientific_name, confidence, endemic, lat, lon"
                " FROM sightings ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in reversed(self.recent(limit=100000)):
            writer.writerow(row)
        return buf.getvalue()
