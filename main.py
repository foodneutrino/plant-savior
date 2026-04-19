"""Plant Savior HTTP entry point.

This module is deliberately thin: every route parses input, delegates
to :class:`plant_service.PlantService`, and renders a response. All
business logic lives in the service layer.

Run with::

    uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from calendar_service import CalendarClient, CalendarConfig
from database import DEFAULT_DB_PATH, PlantRepository, sqlite_connection_factory
from exceptions import PlantNotFoundError
from plant_data import suggest_interval
from plant_service import PlantService

templates = Jinja2Templates(directory="templates")

_service: PlantService | None = None


def _calendar_config_from_env() -> CalendarConfig:
    return CalendarConfig(
        calendar_id=os.getenv("CALENDAR_ID", "primary"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000"),
        reminder_hour=int(os.getenv("REMINDER_HOUR", "9")),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise (and tear down) application-wide singletons."""
    global _service
    repository = PlantRepository(sqlite_connection_factory(DEFAULT_DB_PATH))
    repository.init_schema()
    calendar = CalendarClient.from_credentials(_calendar_config_from_env())
    _service = PlantService(repository, calendar)
    try:
        yield
    finally:
        _service = None


app = FastAPI(title="Plant Savior", lifespan=lifespan)


def get_service() -> PlantService:
    """FastAPI dependency returning the initialised :class:`PlantService`."""
    if _service is None:
        raise RuntimeError(
            "PlantService not initialised — lifespan startup did not run"
        )
    return _service


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/plants")


@app.get("/plants", response_class=HTMLResponse)
def list_plants(
    request: Request,
    message: str = "",
    service: PlantService = Depends(get_service),
):
    return templates.TemplateResponse(
        "plants.html",
        {"request": request, "plants": service.list_plants(), "message": message},
    )


@app.post("/plants", response_class=RedirectResponse)
def add_plant(
    name: str = Form(...),
    plant_type: str = Form(""),
    watering_interval_days: int | None = Form(None),
    service: PlantService = Depends(get_service),
) -> RedirectResponse:
    result = service.add_plant(name, plant_type, watering_interval_days)
    if result.calendar_error or result.next_date is None:
        message = (
            f"Plant added but calendar event failed: "
            f"{result.calendar_error or 'unknown'}"
        )
    else:
        message = (
            f"Added {result.plant.name} — "
            f"next watering on {result.next_date.strftime('%b %d')}"
        )
    return RedirectResponse(url=f"/plants?message={message}", status_code=303)


@app.post("/plants/{plant_id}/delete", response_class=RedirectResponse)
def remove_plant(
    plant_id: int,
    service: PlantService = Depends(get_service),
) -> RedirectResponse:
    try:
        service.delete_plant(plant_id)
    except PlantNotFoundError:
        return RedirectResponse(
            url="/plants?message=Plant not found", status_code=303
        )
    return RedirectResponse(url="/plants?message=Plant removed", status_code=303)


@app.get("/water/{plant_id}", response_class=HTMLResponse)
def water_page(
    request: Request,
    plant_id: int,
    service: PlantService = Depends(get_service),
):
    try:
        plant = service.get_plant(plant_id)
    except PlantNotFoundError:
        return RedirectResponse(
            url="/plants?message=Plant not found", status_code=303
        )
    return templates.TemplateResponse(
        "water.html", {"request": request, "plant": plant}
    )


@app.post("/water/{plant_id}", response_class=HTMLResponse)
def handle_water_action(
    request: Request,
    plant_id: int,
    action: str = Form(...),
    service: PlantService = Depends(get_service),
):
    if action not in ("watered", "skipped"):
        raise HTTPException(status_code=400, detail="invalid action")
    try:
        plant = service.get_plant(plant_id)
    except PlantNotFoundError:
        return RedirectResponse(
            url="/plants?message=Plant not found", status_code=303
        )

    result = service.record_watering(plant_id, action)
    next_date_display = (
        f"(calendar error: {result.calendar_error})"
        if result.calendar_error
        else result.next_date
    )
    return templates.TemplateResponse(
        "confirmed.html",
        {
            "request": request,
            "plant": plant,
            "action": action,
            "next_date": next_date_display,
        },
    )


@app.get("/suggest-interval")
def get_suggested_interval(plant_type: str):
    match = suggest_interval(plant_type)
    if match is None:
        return {"interval": None, "match": None}
    return {"interval": match.interval, "match": match.match}


@app.get("/history/{plant_id}", response_class=HTMLResponse)
def plant_history(
    request: Request,
    plant_id: int,
    service: PlantService = Depends(get_service),
):
    try:
        plant = service.get_plant(plant_id)
        history = service.get_history(plant_id)
    except PlantNotFoundError:
        return RedirectResponse(
            url="/plants?message=Plant not found", status_code=303
        )
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "plant": plant, "history": history},
    )
