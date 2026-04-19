"""Application service: coordinates the repository with the calendar.

The HTTP layer (``main.py``) should stay thin — parse inputs, call a
method here, render a response. All workflow logic lives in this module
so it can be unit-tested without FastAPI, SQLite on disk, or a real
Google Calendar connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from calendar_service import CalendarClient
from database import PlantRepository
from exceptions import CalendarServiceError, PlantNotFoundError
from models import Plant, WaterActionType
from plant_data import suggest_interval


@dataclass(frozen=True)
class AddPlantResult:
    """Outcome of :meth:`PlantService.add_plant`.

    The plant is always persisted; ``calendar_error`` is populated when
    the reminder event could not be created so the caller can surface a
    flash message. ``next_date`` is ``None`` exactly when
    ``calendar_error`` is set.
    """

    plant: Plant
    next_date: datetime | None
    calendar_error: str | None


@dataclass(frozen=True)
class WaterResult:
    """Outcome of :meth:`PlantService.record_watering`."""

    next_date: str
    calendar_error: str | None


class PlantService:
    """Orchestrates the plant + calendar workflows."""

    DEFAULT_INTERVAL_DAYS = 7
    SKIPPED_RETRY_DAYS = 1

    def __init__(
        self, repository: PlantRepository, calendar: CalendarClient
    ) -> None:
        self._repository = repository
        self._calendar = calendar

    def list_plants(self) -> list[Plant]:
        return self._repository.get_all_plants()

    def get_history(
        self, plant_id: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return recent watering log entries for the given plant.

        Raises :class:`PlantNotFoundError` if the plant does not exist.
        """
        self.get_plant(plant_id)  # existence check
        return self._repository.get_watering_history(plant_id, limit=limit)

    def get_plant(self, plant_id: int) -> Plant:
        """Return a plant or raise :class:`PlantNotFoundError`."""
        plant = self._repository.get_plant(plant_id)
        if plant is None:
            raise PlantNotFoundError(f"Plant {plant_id} does not exist")
        return plant

    def add_plant(
        self,
        name: str,
        plant_type: str | None,
        watering_interval_days: int | None,
    ) -> AddPlantResult:
        """Persist a new plant and attempt to create its reminder event.

        The plant is always saved. If the calendar insert fails, the
        returned :class:`AddPlantResult` carries the error message so
        the caller can surface it; a later action can set the event.
        """
        clean_name = name.strip()
        clean_type = self._clean_optional(plant_type)
        interval = watering_interval_days or self._suggest_or_default(
            clean_type or clean_name
        )

        plant_id = self._repository.add_plant(clean_name, clean_type, interval)

        next_date: datetime | None = None
        calendar_error: str | None = None
        try:
            event_id, next_date = self._calendar.schedule_watering(
                clean_name, plant_id, interval
            )
            self._repository.update_event(
                plant_id, event_id, next_date.strftime("%Y-%m-%d")
            )
        except CalendarServiceError as e:
            calendar_error = str(e)

        plant = self._repository.get_plant(plant_id)
        assert plant is not None, "row missing immediately after insert"
        return AddPlantResult(
            plant=plant, next_date=next_date, calendar_error=calendar_error
        )

    def delete_plant(self, plant_id: int) -> None:
        """Remove a plant and its reminder event (best-effort)."""
        plant = self.get_plant(plant_id)
        if plant.calendar_event_id:
            try:
                self._calendar.delete_event(plant.calendar_event_id)
            except CalendarServiceError:
                pass
        self._repository.delete_plant(plant_id)

    def record_watering(
        self, plant_id: int, action: WaterActionType
    ) -> WaterResult:
        """Log a watering action and reschedule the reminder.

        A ``"watered"`` action schedules the next reminder one full
        interval out; ``"skipped"`` schedules a retry the next day.

        The new event is created *before* the old one is deleted so a
        failure mid-flight never leaves the user without a reminder.
        """
        plant = self.get_plant(plant_id)
        self._repository.log_watering(plant_id, action)

        days = (
            plant.watering_interval_days
            if action == "watered"
            else self.SKIPPED_RETRY_DAYS
        )

        try:
            event_id, new_start = self._calendar.schedule_watering(
                plant.name, plant_id, days
            )
        except CalendarServiceError as e:
            return WaterResult(next_date="", calendar_error=str(e))

        if plant.calendar_event_id:
            try:
                self._calendar.delete_event(plant.calendar_event_id)
            except CalendarServiceError:
                pass

        next_date_iso = new_start.strftime("%Y-%m-%d")
        self._repository.update_event(plant_id, event_id, next_date_iso)
        return WaterResult(next_date=next_date_iso, calendar_error=None)

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @classmethod
    def _suggest_or_default(cls, lookup: str) -> int:
        match = suggest_interval(lookup)
        return match.interval if match else cls.DEFAULT_INTERVAL_DAYS
