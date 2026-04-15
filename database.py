"""SQLite database for plant and watering log storage."""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "plants.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
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
    """)
    conn.commit()
    conn.close()


def add_plant(name: str, plant_type: str | None, watering_interval_days: int) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO plants (name, plant_type, watering_interval_days) VALUES (?, ?, ?)",
        (name, plant_type, watering_interval_days),
    )
    plant_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return plant_id


def get_plant(plant_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_plants() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM plants ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_plant_event(plant_id: int, event_id: str, next_water_date: str):
    conn = get_connection()
    conn.execute(
        "UPDATE plants SET calendar_event_id = ?, next_water_date = ? WHERE id = ?",
        (event_id, next_water_date, plant_id),
    )
    conn.commit()
    conn.close()


def delete_plant(plant_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
    conn.commit()
    conn.close()


def log_watering(plant_id: int, action: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO watering_log (plant_id, action) VALUES (?, ?)",
        (plant_id, action),
    )
    conn.commit()
    conn.close()


def get_watering_history(plant_id: int, limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM watering_log WHERE plant_id = ? ORDER BY logged_at DESC LIMIT ?",
        (plant_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
