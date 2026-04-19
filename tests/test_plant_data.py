"""Tests for the pure-function plant_data module."""

import pytest

from plant_data import PLANT_INTERVALS, IntervalMatch, suggest_interval


class TestSuggestInterval:
    def test_exact_match_returns_display_name(self) -> None:
        assert suggest_interval("monstera") == IntervalMatch(7, "Monstera")

    def test_case_insensitive(self) -> None:
        match = suggest_interval("MONSTERA")
        assert match is not None
        assert match.interval == 7

    def test_strips_surrounding_whitespace(self) -> None:
        match = suggest_interval("  snake plant  ")
        assert match is not None
        assert match.match == "Snake Plant"

    def test_input_as_substring_of_entry(self) -> None:
        # "snake" is inside "snake plant"
        match = suggest_interval("snake")
        assert match == IntervalMatch(14, "Snake Plant")

    def test_entry_as_substring_of_input(self) -> None:
        # "basil" is inside "sweet basil"
        match = suggest_interval("sweet basil")
        assert match is not None
        assert match.interval == 3

    def test_unknown_plant_returns_none(self) -> None:
        assert suggest_interval("carnivorous rock garden") is None

    @pytest.mark.parametrize("empty_input", ["", "   ", "\t\n"])
    def test_empty_input_returns_none(self, empty_input: str) -> None:
        assert suggest_interval(empty_input) is None

    def test_every_known_plant_resolves_to_itself(self) -> None:
        for key, days in PLANT_INTERVALS.items():
            match = suggest_interval(key)
            assert match is not None, f"{key!r} failed to resolve"
            assert match.interval == days
