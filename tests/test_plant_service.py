"""Tests for the PlantService orchestration layer.

These tests exercise business logic against a real :class:`PlantRepository`
(backed by a per-test SQLite file) and a :class:`MagicMock` standing in
for :class:`calendar_service.CalendarClient`. No network, no Google
credentials required.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from database import PlantRepository
from exceptions import CalendarServiceError, PlantNotFoundError
from plant_service import PlantService

_TZ = ZoneInfo("America/New_York")


def _scheduled(event_id: str, when: datetime) -> tuple[str, datetime]:
    """Shape matching :meth:`CalendarClient.schedule_watering`'s return."""
    return event_id, when


class TestAddPlant:
    def test_uses_explicit_interval_when_provided(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("Monstera", "monstera", 10)
        assert result.plant.watering_interval_days == 10

    def test_falls_back_to_suggested_interval_for_known_type(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("My Plant", "monstera", None)
        assert result.plant.watering_interval_days == 7

    def test_uses_default_when_name_and_type_unknown(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("Unknown", "unrecognised type", None)
        assert (
            result.plant.watering_interval_days
            == PlantService.DEFAULT_INTERVAL_DAYS
        )

    def test_uses_name_for_lookup_when_type_blank(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("snake plant", "", None)
        assert result.plant.watering_interval_days == 14

    def test_strips_whitespace_from_name(self, service: PlantService) -> None:
        result = service.add_plant("  Monstera  ", "monstera", 7)
        assert result.plant.name == "Monstera"

    def test_whitespace_only_type_becomes_none(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("Monstera", "   ", 7)
        assert result.plant.plant_type is None

    def test_creates_calendar_event(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        fake_calendar.schedule_watering.return_value = _scheduled(
            "evt-xyz", datetime(2026, 5, 1, 9, 0, tzinfo=_TZ)
        )
        result = service.add_plant("Monstera", "monstera", 7)

        fake_calendar.schedule_watering.assert_called_once()
        assert result.plant.calendar_event_id == "evt-xyz"
        assert result.calendar_error is None
        assert result.next_date is not None
        assert result.next_date.tzinfo is not None  # must be tz-aware

    def test_passes_days_from_now_to_calendar(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        service.add_plant("Monstera", "monstera", 10)
        # signature: schedule_watering(plant_name, plant_id, days_from_now)
        assert fake_calendar.schedule_watering.call_args.args[2] == 10

    def test_persists_plant_even_when_calendar_fails(
        self,
        service: PlantService,
        fake_calendar: MagicMock,
        repository: PlantRepository,
    ) -> None:
        fake_calendar.schedule_watering.side_effect = CalendarServiceError(
            "api down"
        )
        result = service.add_plant("Monstera", "monstera", 7)

        assert result.calendar_error == "api down"
        assert result.next_date is None
        saved = repository.get_plant(result.plant.id)
        assert saved is not None
        assert saved.calendar_event_id is None


class TestDeletePlant:
    def test_removes_from_repository(
        self, service: PlantService, repository: PlantRepository
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        service.delete_plant(result.plant.id)
        assert repository.get_plant(result.plant.id) is None

    def test_deletes_attached_calendar_event(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        fake_calendar.schedule_watering.return_value = _scheduled(
            "evt-to-delete", datetime(2026, 5, 1, 9, 0, tzinfo=_TZ)
        )
        result = service.add_plant("Monstera", None, 7)
        service.delete_plant(result.plant.id)
        fake_calendar.delete_event.assert_called_once_with("evt-to-delete")

    def test_skips_calendar_call_when_no_event_attached(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        fake_calendar.schedule_watering.side_effect = CalendarServiceError(
            "nope"
        )
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.delete_event.reset_mock()

        service.delete_plant(result.plant.id)
        fake_calendar.delete_event.assert_not_called()

    def test_tolerates_calendar_delete_failure(
        self,
        service: PlantService,
        fake_calendar: MagicMock,
        repository: PlantRepository,
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.delete_event.side_effect = CalendarServiceError("gone")

        service.delete_plant(result.plant.id)  # must not raise
        assert repository.get_plant(result.plant.id) is None

    def test_raises_for_missing_plant(self, service: PlantService) -> None:
        with pytest.raises(PlantNotFoundError):
            service.delete_plant(9999)


class TestRecordWatering:
    def test_watered_schedules_one_full_interval_out(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.schedule_watering.reset_mock()

        service.record_watering(result.plant.id, "watered")

        # schedule_watering(plant_name, plant_id, days_from_now)
        assert fake_calendar.schedule_watering.call_args.args[2] == 7

    def test_skipped_schedules_retry_days(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.schedule_watering.reset_mock()

        service.record_watering(result.plant.id, "skipped")

        assert (
            fake_calendar.schedule_watering.call_args.args[2]
            == PlantService.SKIPPED_RETRY_DAYS
        )

    def test_appends_to_watering_log(
        self, service: PlantService, repository: PlantRepository
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        service.record_watering(result.plant.id, "watered")

        history = repository.get_watering_history(result.plant.id)
        assert len(history) == 1
        assert history[0]["action"] == "watered"

    def test_updates_stored_event_id_and_date(
        self,
        service: PlantService,
        fake_calendar: MagicMock,
        repository: PlantRepository,
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.schedule_watering.return_value = _scheduled(
            "evt-new", datetime(2026, 5, 15, 9, 0, tzinfo=_TZ)
        )

        service.record_watering(result.plant.id, "watered")

        plant = repository.get_plant(result.plant.id)
        assert plant is not None
        assert plant.calendar_event_id == "evt-new"
        assert plant.next_water_date == "2026-05-15"

    def test_deletes_old_event_after_scheduling_new(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        fake_calendar.schedule_watering.return_value = _scheduled(
            "evt-old", datetime(2026, 5, 1, 9, 0, tzinfo=_TZ)
        )
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.schedule_watering.return_value = _scheduled(
            "evt-new", datetime(2026, 5, 8, 9, 0, tzinfo=_TZ)
        )

        service.record_watering(result.plant.id, "watered")

        fake_calendar.delete_event.assert_called_once_with("evt-old")

    def test_surfaces_calendar_error_without_raising(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.schedule_watering.side_effect = CalendarServiceError(
            "boom"
        )

        outcome = service.record_watering(result.plant.id, "watered")

        assert outcome.calendar_error == "boom"
        assert outcome.next_date == ""

    def test_old_event_preserved_when_new_event_fails(
        self, service: PlantService, fake_calendar: MagicMock
    ) -> None:
        """If scheduling the new event fails we must not delete the old
        one — the user would otherwise be left with no reminder."""
        result = service.add_plant("Monstera", None, 7)
        fake_calendar.delete_event.reset_mock()
        fake_calendar.schedule_watering.side_effect = CalendarServiceError(
            "503"
        )

        service.record_watering(result.plant.id, "watered")

        fake_calendar.delete_event.assert_not_called()

    def test_raises_for_missing_plant(self, service: PlantService) -> None:
        with pytest.raises(PlantNotFoundError):
            service.record_watering(9999, "watered")


class TestGetHistory:
    def test_new_plant_has_empty_history(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        assert service.get_history(result.plant.id) == []

    def test_returns_logged_entries(
        self, service: PlantService
    ) -> None:
        result = service.add_plant("Monstera", None, 7)
        service.record_watering(result.plant.id, "watered")
        service.record_watering(result.plant.id, "skipped")

        history = service.get_history(result.plant.id)
        assert len(history) == 2

    def test_raises_for_missing_plant(self, service: PlantService) -> None:
        with pytest.raises(PlantNotFoundError):
            service.get_history(9999)
