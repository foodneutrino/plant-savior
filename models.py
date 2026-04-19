"""Domain models and API schemas.

Domain entities (``Plant``) are plain dataclasses, decoupled from the
HTTP layer. Pydantic models (``PlantCreate``, ``WaterAction``) are
reserved for request validation at the edge.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

WaterActionType = Literal["watered", "skipped"]


@dataclass(frozen=True)
class Plant:
    """A tracked plant and its current watering schedule.

    Attributes:
        id: Primary key assigned by the database.
        name: Human-readable name shown in the UI.
        plant_type: Optional species or cultivar used for interval lookup.
        watering_interval_days: Days between waterings when healthy.
        calendar_event_id: ID of the most recent Google Calendar reminder,
            or None if the event has not been created yet.
        next_water_date: ISO ``YYYY-MM-DD`` date of the next reminder, or
            None if no reminder is scheduled.
        created_at: ISO timestamp the row was inserted.
    """

    id: int
    name: str
    plant_type: str | None
    watering_interval_days: int
    calendar_event_id: str | None
    next_water_date: str | None
    created_at: str


class PlantCreate(BaseModel):
    """Form payload for creating a new plant."""

    name: str
    plant_type: str | None = None
    watering_interval_days: int | None = None


class WaterAction(BaseModel):
    """Form payload for the /water/{id} endpoint."""

    action: WaterActionType
