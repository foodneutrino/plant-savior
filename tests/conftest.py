"""Shared pytest fixtures for the Plant Savior suite."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from calendar_service import CalendarClient
from database import PlantRepository, sqlite_connection_factory
from plant_service import PlantService

DEFAULT_TZ = ZoneInfo("America/New_York")


@pytest.fixture
def repository(tmp_path: Path) -> PlantRepository:
    """Fresh :class:`PlantRepository` backed by a per-test SQLite file."""
    repo = PlantRepository(sqlite_connection_factory(tmp_path / "plants.db"))
    repo.init_schema()
    return repo


@pytest.fixture
def fake_calendar() -> MagicMock:
    """A spec'd :class:`MagicMock` replacing :class:`CalendarClient`.

    Default happy-path behavior:
      * ``schedule_watering`` → ``("evt-1", 2026-05-01 09:00 America/New_York)``
      * ``delete_event`` is a silent no-op

    Tests should override per case (e.g. ``.side_effect``).
    """
    cal = MagicMock(spec=CalendarClient)
    cal.schedule_watering.return_value = (
        "evt-1",
        datetime(2026, 5, 1, 9, 0, tzinfo=DEFAULT_TZ),
    )
    return cal


@pytest.fixture
def service(
    repository: PlantRepository, fake_calendar: MagicMock
) -> PlantService:
    """A :class:`PlantService` wired to a real repo and a fake calendar."""
    return PlantService(repository, fake_calendar)
