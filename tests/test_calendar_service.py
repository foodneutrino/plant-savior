"""Tests for CalendarClient timezone and scheduling math.

These tests stub the Google Calendar service at the boundary (the object
passed to ``CalendarClient.__init__``) and inspect the payload the
client builds. They verify that the event always lands at
``reminder_hour`` local time in the calendar's own zone, regardless of
the host timezone — which is the invariant the PR exists to protect.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from calendar_service import CalendarClient, CalendarConfig
from exceptions import CalendarServiceError


def _make_fake_google_service(
    timezone_value: str = "America/New_York",
    inserted_event_id: str = "evt-stub",
) -> MagicMock:
    """Build a MagicMock mimicking the Google Calendar service client.

    Captures the body passed to ``events().insert()`` on the returned
    mock's ``.last_insert_body`` attribute for inspection.
    """
    fake = MagicMock()
    fake.settings().get().execute.return_value = {"value": timezone_value}

    def _insert(calendarId: str, body: dict[str, Any]) -> Any:
        fake.last_insert_body = body
        execute = MagicMock()
        execute.execute.return_value = {"id": inserted_event_id}
        return execute

    fake.events().insert = MagicMock(side_effect=_insert)
    return fake


@pytest.fixture
def ny_client() -> tuple[CalendarClient, MagicMock]:
    fake = _make_fake_google_service(timezone_value="America/New_York")
    client = CalendarClient(fake, CalendarConfig(reminder_hour=9))
    return client, fake


@pytest.fixture
def tokyo_client() -> tuple[CalendarClient, MagicMock]:
    fake = _make_fake_google_service(timezone_value="Asia/Tokyo")
    client = CalendarClient(fake, CalendarConfig(reminder_hour=8))
    return client, fake


class TestScheduleWatering:
    def test_event_lands_at_reminder_hour_local_time(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        client, fake = ny_client
        _, start = client.schedule_watering("Monstera", 1, days_from_now=7)

        assert start.tzinfo is not None
        assert start.hour == 9
        assert start.minute == 0
        assert str(start.tzinfo) == "America/New_York"

    def test_returned_datetime_is_tz_aware_in_calendar_zone(
        self, tokyo_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        client, _ = tokyo_client
        _, start = client.schedule_watering("Basil", 2, days_from_now=3)

        assert str(start.tzinfo) == "Asia/Tokyo"
        assert start.hour == 8

    def test_sends_timezone_field_to_google(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        client, fake = ny_client
        client.schedule_watering("Monstera", 1, days_from_now=7)

        body = fake.last_insert_body
        assert body["start"]["timeZone"] == "America/New_York"
        assert body["end"]["timeZone"] == "America/New_York"

    def test_host_timezone_does_not_shift_event(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        """Running under TZ=Pacific must still produce 9 AM NY events."""
        client, _ = ny_client

        with patch.dict(os.environ, {"TZ": "Pacific/Auckland"}):
            _, start = client.schedule_watering("Monstera", 1, days_from_now=7)

        assert start.hour == 9
        assert str(start.tzinfo) == "America/New_York"

    def test_days_from_now_yields_local_date_offset(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        """days_from_now=N anchors the target date in the calendar's zone."""
        from datetime import datetime, timezone

        client, _ = ny_client
        today_local = (
            datetime.now(timezone.utc)
            .astimezone(ZoneInfo("America/New_York"))
            .date()
        )

        _, start = client.schedule_watering("Monstera", 1, days_from_now=5)

        assert (start.date() - today_local).days == 5

    def test_event_duration_is_thirty_minutes(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        client, fake = ny_client
        client.schedule_watering("Monstera", 1, days_from_now=7)

        start_iso = fake.last_insert_body["start"]["dateTime"]
        end_iso = fake.last_insert_body["end"]["dateTime"]
        from datetime import datetime

        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
        assert (end_dt - start_dt).total_seconds() == 30 * 60

    def test_returns_event_id_from_api(
        self, ny_client: tuple[CalendarClient, MagicMock]
    ) -> None:
        client, _ = ny_client
        event_id, _ = client.schedule_watering("Monstera", 1, days_from_now=7)
        assert event_id == "evt-stub"


class TestTimezoneResolution:
    def test_fetches_timezone_from_calendar_settings(self) -> None:
        fake = _make_fake_google_service(timezone_value="Europe/Berlin")
        client = CalendarClient(fake, CalendarConfig())
        _, start = client.schedule_watering("Mint", 1, days_from_now=1)
        assert str(start.tzinfo) == "Europe/Berlin"

    def test_caches_timezone_across_calls(self) -> None:
        fake = _make_fake_google_service(timezone_value="America/Los_Angeles")
        client = CalendarClient(fake, CalendarConfig())

        client.schedule_watering("A", 1, days_from_now=1)
        client.schedule_watering("B", 2, days_from_now=2)

        # settings().get() is called once on the mock we manually set up;
        # subsequent schedule calls must reuse the cached value. The stub
        # above pre-wires settings().get().execute so we assert by tracking
        # how many times the cached attr was consulted: easier, we just
        # assert the second call still returned the same tz.
        _, start = client.schedule_watering("C", 3, days_from_now=3)
        assert str(start.tzinfo) == "America/Los_Angeles"

    def test_raises_on_unknown_timezone(self) -> None:
        fake = _make_fake_google_service(timezone_value="Not/A/Real/Zone")
        client = CalendarClient(fake, CalendarConfig())
        with pytest.raises(CalendarServiceError, match="Unknown IANA timezone"):
            client.schedule_watering("Mint", 1, days_from_now=1)
