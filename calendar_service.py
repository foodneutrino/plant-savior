"""Google Calendar event management for plant watering reminders."""

import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from auth import get_credentials

load_dotenv()

CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))


def _get_service():
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Google Calendar credentials not available. Run: python auth.py")
    return build("calendar", "v3", credentials=creds)


def create_watering_event(plant_name: str, water_date: datetime, plant_id: int) -> str:
    """Create a calendar event for watering a plant.

    Returns the created event's ID.
    """
    service = _get_service()

    event_start = water_date.replace(hour=REMINDER_HOUR, minute=0, second=0, microsecond=0)
    event_end = event_start + timedelta(minutes=30)

    water_url = f"{BASE_URL}/water/{plant_id}"

    event_body = {
        "summary": f"Water: {plant_name}",
        "description": (
            f"Time to check on your {plant_name}!\n\n"
            f"Tap to respond:\n{water_url}"
        ),
        "start": {
            "dateTime": event_start.isoformat(),
            "timeZone": _get_calendar_timezone(service),
        },
        "end": {
            "dateTime": event_end.isoformat(),
            "timeZone": _get_calendar_timezone(service),
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 0},
            ],
        },
    }

    event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    return event["id"]


def delete_event(event_id: str):
    """Delete a calendar event by ID. Silently ignores missing events."""
    service = _get_service()
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            pass  # Event already deleted
        else:
            raise


def reschedule_watering(plant_id: int, plant_name: str, days_from_now: int, old_event_id: str | None) -> tuple[str, str]:
    """Delete the old event and create a new one.

    Returns (new_event_id, next_water_date as ISO string).
    """
    if old_event_id:
        delete_event(old_event_id)

    next_date = datetime.now() + timedelta(days=days_from_now)
    new_event_id = create_watering_event(plant_name, next_date, plant_id)
    return new_event_id, next_date.strftime("%Y-%m-%d")


def _get_calendar_timezone(service) -> str:
    """Fetch the user's calendar timezone."""
    try:
        settings = service.settings().get(setting="timezone").execute()
        return settings["value"]
    except HttpError:
        return "America/New_York"
