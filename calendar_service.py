"""Google Calendar integration for watering reminders.

:class:`CalendarClient` wraps the subset of the Google Calendar API we
need. The underlying ``service`` object is injected via the constructor
so tests can pass a mock; production code uses the
:meth:`CalendarClient.from_credentials` factory, which loads OAuth
credentials via :mod:`auth` and builds a real client.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

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
        reminder_hour: Hour of day (0-23) to schedule the reminder event.
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
    :meth:`create_watering_event`, :meth:`delete_event`, :meth:`reschedule`.
    The calendar's timezone is fetched once and cached for the lifetime
    of the instance.
    """

    def __init__(self, service: Any, config: CalendarConfig) -> None:
        self._service = service
        self._config = config
        self._timezone: str | None = None

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

    def create_watering_event(
        self, plant_name: str, water_date: datetime, plant_id: int
    ) -> str:
        """Create a watering reminder event and return its ID.

        Raises:
            CalendarServiceError: if the insert call fails.
        """
        tz = self._get_timezone()
        event_start = water_date.replace(
            hour=self._config.reminder_hour, minute=0, second=0, microsecond=0
        )
        event_end = event_start + timedelta(minutes=30)
        water_url = f"{self._config.base_url}/water/{plant_id}"

        body = {
            "summary": f"Water: {plant_name}",
            "description": (
                f"Time to check on your {plant_name}!\n\n"
                f"Tap to respond:\n{water_url}"
            ),
            "start": {"dateTime": event_start.isoformat(), "timeZone": tz},
            "end": {"dateTime": event_end.isoformat(), "timeZone": tz},
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
        return event["id"]

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

    def reschedule(
        self,
        plant_id: int,
        plant_name: str,
        days_from_now: int,
        old_event_id: str | None,
    ) -> tuple[str, str]:
        """Remove the old reminder and schedule a new one N days out.

        Returns:
            ``(new_event_id, next_water_date)`` where ``next_water_date``
            is an ISO ``YYYY-MM-DD`` string.
        """
        if old_event_id:
            self.delete_event(old_event_id)
        next_date = datetime.now() + timedelta(days=days_from_now)
        new_event_id = self.create_watering_event(plant_name, next_date, plant_id)
        return new_event_id, next_date.strftime("%Y-%m-%d")

    def _get_timezone(self) -> str:
        if self._timezone is not None:
            return self._timezone
        try:
            settings = self._service.settings().get(setting="timezone").execute()
            self._timezone = settings["value"]
        except HttpError:
            self._timezone = self._config.default_timezone
        return self._timezone
