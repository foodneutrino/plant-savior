"""Shared pytest fixtures for the Plant Savior suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from calendar_service import CalendarClient
from database import PlantRepository, sqlite_connection_factory
from plant_service import PlantService


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
      * ``create_watering_event`` → ``"evt-1"``
      * ``reschedule`` → ``("evt-2", "2026-05-01")``
      * ``delete_event`` is a silent no-op

    Tests should override per case (e.g. ``.side_effect``).
    """
    cal = MagicMock(spec=CalendarClient)
    cal.create_watering_event.return_value = "evt-1"
    cal.reschedule.return_value = ("evt-2", "2026-05-01")
    return cal


@pytest.fixture
def service(
    repository: PlantRepository, fake_calendar: MagicMock
) -> PlantService:
    """A :class:`PlantService` wired to a real repo and a fake calendar."""
    return PlantService(repository, fake_calendar)
