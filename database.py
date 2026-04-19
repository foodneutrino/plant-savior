"""SQLite persistence layer for plants and watering history.

The :class:`PlantRepository` accepts a connection factory rather than a
hard-coded path so tests can point it at a temporary database without
monkey-patching module globals.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from models import Plant, WaterActionType

DEFAULT_DB_PATH = Path(__file__).parent / "plants.db"

ConnectionFactory = Callable[[], sqlite3.Connection]

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS plants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        plant_type TEXT,
        watering_interval_days INTEGER NOT NULL,
        calendar_event_id TEXT,
        next_water_date TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS watering_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plant_id INTEGER NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('watered', 'skipped')),
        logged_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
    );
"""


def sqlite_connection_factory(db_path: Path | str) -> ConnectionFactory:
    """Return a factory that opens fresh SQLite connections to ``db_path``.

    Each returned connection has ``Row`` row factory enabled and foreign-key
    constraints turned on.
    """
    path_str = str(db_path)

    def factory() -> sqlite3.Connection:
        conn = sqlite3.connect(path_str)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    return factory


class PlantRepository:
    """CRUD operations for plants and their watering log.

    Args:
        connection_factory: Callable returning a new SQLite connection on
            each invocation. Enables dependency injection for tests.
    """

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connect = connection_factory

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create the ``plants`` and ``watering_log`` tables if absent."""
        with self._cursor() as conn:
            conn.executescript(_SCHEMA)

    def add_plant(
        self,
        name: str,
        plant_type: str | None,
        watering_interval_days: int,
    ) -> int:
        """Insert a new plant and return its generated ID."""
        with self._cursor() as conn:
            cursor = conn.execute(
                "INSERT INTO plants (name, plant_type, watering_interval_days)"
                " VALUES (?, ?, ?)",
                (name, plant_type, watering_interval_days),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_plant(self, plant_id: int) -> Plant | None:
        """Return the plant with the given ID, or ``None`` if not found."""
        with self._cursor() as conn:
            row = conn.execute(
                "SELECT * FROM plants WHERE id = ?", (plant_id,)
            ).fetchone()
        return _row_to_plant(row) if row else None

    def get_all_plants(self) -> list[Plant]:
        """Return every plant ordered by name."""
        with self._cursor() as conn:
            rows = conn.execute("SELECT * FROM plants ORDER BY name").fetchall()
        return [_row_to_plant(r) for r in rows]

    def update_event(
        self, plant_id: int, event_id: str, next_water_date: str
    ) -> None:
        """Attach a newly created calendar event to an existing plant."""
        with self._cursor() as conn:
            conn.execute(
                "UPDATE plants SET calendar_event_id = ?, next_water_date = ?"
                " WHERE id = ?",
                (event_id, next_water_date, plant_id),
            )

    def delete_plant(self, plant_id: int) -> None:
        """Remove the plant and cascade-delete its watering log."""
        with self._cursor() as conn:
            conn.execute("DELETE FROM plants WHERE id = ?", (plant_id,))

    def log_watering(self, plant_id: int, action: WaterActionType) -> None:
        """Append a watered/skipped entry to the plant's log."""
        with self._cursor() as conn:
            conn.execute(
                "INSERT INTO watering_log (plant_id, action) VALUES (?, ?)",
                (plant_id, action),
            )

    def get_watering_history(
        self, plant_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return recent watering log entries for a plant, newest first."""
        with self._cursor() as conn:
            rows = conn.execute(
                "SELECT * FROM watering_log WHERE plant_id = ?"
                " ORDER BY logged_at DESC LIMIT ?",
                (plant_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def _row_to_plant(row: sqlite3.Row) -> Plant:
    return Plant(
        id=row["id"],
        name=row["name"],
        plant_type=row["plant_type"],
        watering_interval_days=row["watering_interval_days"],
        calendar_event_id=row["calendar_event_id"],
        next_water_date=row["next_water_date"],
        created_at=row["created_at"],
    )
