"""Pydantic models for request/response validation."""

from pydantic import BaseModel


class PlantCreate(BaseModel):
    name: str
    plant_type: str | None = None
    watering_interval_days: int | None = None


class WaterAction(BaseModel):
    action: str  # "watered" or "not_watered"
