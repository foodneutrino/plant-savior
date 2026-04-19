"""Tests for the PlantRepository persistence layer."""

from __future__ import annotations

import sqlite3

import pytest

from database import PlantRepository
from models import Plant


class TestAddAndGet:
    def test_insert_returns_generated_id(self, repository: PlantRepository) -> None:
        plant_id = repository.add_plant("Monstera", "monstera", 7)
        assert plant_id > 0

    def test_get_returns_typed_plant(self, repository: PlantRepository) -> None:
        plant_id = repository.add_plant("Monstera", "monstera", 7)
        plant = repository.get_plant(plant_id)
        assert isinstance(plant, Plant)
        assert plant.name == "Monstera"
        assert plant.plant_type == "monstera"
        assert plant.watering_interval_days == 7
        assert plant.calendar_event_id is None
        assert plant.next_water_date is None

    def test_get_missing_returns_none(self, repository: PlantRepository) -> None:
        assert repository.get_plant(9999) is None

    def test_optional_plant_type_persists_as_null(
        self, repository: PlantRepository
    ) -> None:
        plant_id = repository.add_plant("Mystery", None, 10)
        plant = repository.get_plant(plant_id)
        assert plant is not None
        assert plant.plant_type is None


class TestListing:
    def test_empty_when_no_rows(self, repository: PlantRepository) -> None:
        assert repository.get_all_plants() == []

    def test_ordered_by_name(self, repository: PlantRepository) -> None:
        repository.add_plant("Zebra Plant", None, 7)
        repository.add_plant("Aloe", None, 14)
        repository.add_plant("Monstera", None, 7)
        names = [p.name for p in repository.get_all_plants()]
        assert names == ["Aloe", "Monstera", "Zebra Plant"]


class TestUpdateEvent:
    def test_update_attaches_event_and_date(
        self, repository: PlantRepository
    ) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        repository.update_event(plant_id, "evt-abc", "2026-05-01")
        plant = repository.get_plant(plant_id)
        assert plant is not None
        assert plant.calendar_event_id == "evt-abc"
        assert plant.next_water_date == "2026-05-01"


class TestDeletion:
    def test_delete_removes_row(self, repository: PlantRepository) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        repository.delete_plant(plant_id)
        assert repository.get_plant(plant_id) is None

    def test_delete_cascades_to_watering_log(
        self, repository: PlantRepository
    ) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        repository.log_watering(plant_id, "watered")
        repository.log_watering(plant_id, "skipped")
        repository.delete_plant(plant_id)
        assert repository.get_watering_history(plant_id) == []


class TestWateringLog:
    def test_history_returns_newest_first(
        self, repository: PlantRepository
    ) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        repository.log_watering(plant_id, "watered")
        repository.log_watering(plant_id, "skipped")
        history = repository.get_watering_history(plant_id)
        assert len(history) == 2
        assert history[0]["action"] == "skipped"
        assert history[1]["action"] == "watered"

    def test_history_respects_limit(self, repository: PlantRepository) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        for _ in range(5):
            repository.log_watering(plant_id, "watered")
        assert len(repository.get_watering_history(plant_id, limit=3)) == 3

    def test_history_for_unknown_plant_is_empty(
        self, repository: PlantRepository
    ) -> None:
        assert repository.get_watering_history(9999) == []

    def test_check_constraint_rejects_invalid_action(
        self, repository: PlantRepository
    ) -> None:
        plant_id = repository.add_plant("Monstera", None, 7)
        with pytest.raises(sqlite3.IntegrityError):
            repository.log_watering(plant_id, "nonsense")  # type: ignore[arg-type]

    def test_foreign_key_constraint_blocks_orphan_logs(
        self, repository: PlantRepository
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            repository.log_watering(9999, "watered")
