"""Google Calendar integration for watering reminders.

:class:`CalendarClient` wraps the subset of the Google Calendar API we
need. The underlying ``service`` object is injected via the constructor
so tests can pass a mock; production code uses the
:meth:`CalendarClient.from_credentials` factory, which loads OAuth
credentials via :mod:`auth` and builds a real client.

Timezone contract
-----------------
The caller never constructs a datetime. It passes ``days_from_now`` and
receives back a timezone-aware ``datetime`` anchored in the calendar's
own IANA zone (via :meth:`schedule_watering`). Internally the module
treats all instants as UTC (``datetime.now(timezone.utc)``) and only
converts to local time at the last step, when building the calendar
event payload. This keeps "wall-clock 9 AM on date X in New York"
deterministic regardless of the host's timezone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from auth import get_credentials
from exceptions import CalendarAuthError, CalendarServiceError


@dataclass(frozen=True)
class CalendarConfig:
    """Configuration for :class:`CalendarClient`.

    Attributes:
        calendar_id: Target calendar (``"primary"`` for the user's default).
        base_url: Public URL of the app, used to generate ``/water/<id>``
            deep links inside event descriptions.
        reminder_hour: Hour of day (0-23), in the calendar's local
            timezone, at which the reminder event should start.
        default_timezone: IANA timezone used when the calendar's own
            timezone cannot be fetched.
    """

    calendar_id: str = "primary"
    base_url: str = "http://localhost:8000"
    reminder_hour: int = 9
    default_timezone: str = "America/New_York"


class CalendarClient:
    """Thin, purpose-built wrapper around the Google Calendar API.

    Exposes only the operations needed for watering reminders:
    :meth:`schedule_watering` and :meth:`delete_event`. The calendar's
    timezone is fetched once and cached for the lifetime of the
    instance.
    """

    def __init__(self, service: Any, config: CalendarConfig) -> None:
        self._service = service
        self._config = config
        self._timezone_name: str | None = None

    @classmethod
    def from_credentials(cls, config: CalendarConfig) -> "CalendarClient":
        """Build a client from the on-disk OAuth credentials.

        Raises:
            CalendarAuthError: if credentials are missing or cannot be
                refreshed. Run ``python auth.py`` to generate them.
        """
        creds = get_credentials()
        if not creds:
            raise CalendarAuthError(
                "Google Calendar credentials not available. "
                "Run: python auth.py"
            )
        service = build("calendar", "v3", credentials=creds)
        return cls(service, config)

    def schedule_watering(
        self, plant_name: str, plant_id: int, days_from_now: int
    ) -> tuple[str, datetime]:
        """Create a reminder event ``days_from_now`` days out.

        The event lands at ``reminder_hour:00`` on that day in the
        calendar's own timezone (so it always displays at the
        configured local time, regardless of the host's timezone).

        Returns:
            ``(event_id, start)`` where ``start`` is a timezone-aware
            :class:`~datetime.datetime` in the calendar's zone. Callers
            can format it for storage or display without ambiguity.

        Raises:
            CalendarServiceError: if the calendar insert fails.
        """
        tz_name = self._get_timezone_name()
        tz = self._load_zone(tz_name)

        today_local = datetime.now(timezone.utc).astimezone(tz).date()
        target_date = today_local + timedelta(days=days_from_now)
        start = datetime.combine(
            target_date, time(hour=self._config.reminder_hour), tzinfo=tz
        )
        end = start + timedelta(minutes=30)

        body = {
            "summary": f"Water: {plant_name}",
            "description": (
                f"Time to check on your {plant_name}!\n\n"
                f"Tap to respond:\n{self._config.base_url}/water/{plant_id}"
            ),
            "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 0}],
            },
        }

        try:
            event = (
                self._service.events()
                .insert(calendarId=self._config.calendar_id, body=body)
                .execute()
            )
        except HttpError as e:
            raise CalendarServiceError(
                f"Failed to create event for plant {plant_id}: {e}"
            ) from e
        return event["id"], start

    def delete_event(self, event_id: str) -> None:
        """Delete a calendar event, silently tolerating a 404."""
        try:
            self._service.events().delete(
                calendarId=self._config.calendar_id, eventId=event_id
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return
            raise CalendarServiceError(
                f"Failed to delete event {event_id}: {e}"
            ) from e

    def _get_timezone_name(self) -> str:
        if self._timezone_name is not None:
            return self._timezone_name
        try:
            settings = self._service.settings().get(setting="timezone").execute()
            self._timezone_name = settings["value"]
        except HttpError:
            self._timezone_name = self._config.default_timezone
        return self._timezone_name

    @staticmethod
    def _load_zone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as e:
            raise CalendarServiceError(
                f"Unknown IANA timezone returned by calendar settings: {name!r}"
            ) from e
