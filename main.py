"""Plant Savior - Watering reminder app powered by Google Calendar.

Run with: uvicorn main:app --host 0.0.0.0 --port 8000
"""

from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import database as db
import calendar_service as cal
from plant_data import suggest_interval

app = FastAPI(title="Plant Savior")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/plants")


@app.get("/plants", response_class=HTMLResponse)
def list_plants(request: Request, message: str = ""):
    plants = db.get_all_plants()
    return templates.TemplateResponse(
        "plants.html",
        {"request": request, "plants": plants, "message": message},
    )


@app.post("/plants", response_class=RedirectResponse)
def add_plant(
    name: str = Form(...),
    plant_type: str = Form(""),
    watering_interval_days: int = Form(None),
):
    # Use suggested interval if none provided
    if not watering_interval_days:
        lookup = plant_type or name
        watering_interval_days = suggest_interval(lookup) or 7

    plant_type_val = plant_type.strip() if plant_type.strip() else None
    plant_id = db.add_plant(name.strip(), plant_type_val, watering_interval_days)

    # Create the first calendar event
    next_date = datetime.now() + timedelta(days=watering_interval_days)
    try:
        event_id = cal.create_watering_event(name.strip(), next_date, plant_id)
        db.update_plant_event(plant_id, event_id, next_date.strftime("%Y-%m-%d"))
    except Exception as e:
        # Plant is saved even if calendar fails — user can retry
        return RedirectResponse(
            url=f"/plants?message=Plant added but calendar event failed: {e}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/plants?message=Added {name} — next watering on {next_date.strftime('%b %d')}",
        status_code=303,
    )


@app.post("/plants/{plant_id}/delete", response_class=RedirectResponse)
def remove_plant(plant_id: int):
    plant = db.get_plant(plant_id)
    if plant and plant["calendar_event_id"]:
        try:
            cal.delete_event(plant["calendar_event_id"])
        except Exception:
            pass
    db.delete_plant(plant_id)
    return RedirectResponse(url="/plants?message=Plant removed", status_code=303)


@app.get("/water/{plant_id}", response_class=HTMLResponse)
def water_page(request: Request, plant_id: int):
    plant = db.get_plant(plant_id)
    if not plant:
        return RedirectResponse(url="/plants?message=Plant not found")
    return templates.TemplateResponse(
        "water.html", {"request": request, "plant": plant}
    )


@app.post("/water/{plant_id}", response_class=HTMLResponse)
def handle_water_action(request: Request, plant_id: int, action: str = Form(...)):
    plant = db.get_plant(plant_id)
    if not plant:
        return RedirectResponse(url="/plants?message=Plant not found")

    if action == "watered":
        db.log_watering(plant_id, "watered")
        days = plant["watering_interval_days"]
    else:
        db.log_watering(plant_id, "skipped")
        days = 1

    try:
        new_event_id, next_date = cal.reschedule_watering(
            plant_id, plant["name"], days, plant["calendar_event_id"]
        )
        db.update_plant_event(plant_id, new_event_id, next_date)
    except Exception as e:
        return templates.TemplateResponse(
            "confirmed.html",
            {
                "request": request,
                "plant": plant,
                "action": action,
                "next_date": f"(calendar error: {e})",
            },
        )

    return templates.TemplateResponse(
        "confirmed.html",
        {
            "request": request,
            "plant": plant,
            "action": action,
            "next_date": next_date,
        },
    )


@app.get("/suggest-interval")
def get_suggested_interval(plant_type: str):
    interval = suggest_interval(plant_type)
    if interval:
        # Find the matched name for display
        normalized = plant_type.strip().lower()
        from plant_data import PLANT_INTERVALS
        match_name = plant_type
        for name in PLANT_INTERVALS:
            if normalized in name or name in normalized:
                match_name = name.title()
                break
        return {"interval": interval, "match": match_name}
    return {"interval": None, "match": None}


@app.get("/history/{plant_id}", response_class=HTMLResponse)
def plant_history(request: Request, plant_id: int):
    plant = db.get_plant(plant_id)
    if not plant:
        return RedirectResponse(url="/plants?message=Plant not found")
    history = db.get_watering_history(plant_id, limit=20)
    return templates.TemplateResponse(
        "plants.html",
        {"request": request, "plants": db.get_all_plants(), "message": ""},
    )
