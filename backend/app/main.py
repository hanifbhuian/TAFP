from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .firms import FirmsError, fetch_detections
from .locations import LOCATION_BY_ID, public_locations
from .model import analyze, model_metadata

app = FastAPI(
    title="TAFP Wildfire API",
    version="1.0.0",
    description="Live NASA FIRMS retrieval and TAFP fire-perimeter analysis.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "firms_configured": bool(settings.firms_map_key)}


@app.get("/api/locations")
async def locations() -> dict:
    return {"locations": public_locations()}


@app.get("/api/analyze")
async def analyze_location(
    location_id: str = Query(default="alberta"),
    acquisition_date: date = Query(default_factory=date.today, alias="date"),
) -> dict:
    location = LOCATION_BY_ID.get(location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Unknown location.")
    if acquisition_date > date.today():
        raise HTTPException(status_code=422, detail="Date cannot be in the future.")
    if not settings.firms_map_key:
        raise HTTPException(
            status_code=503,
            detail="FIRMS_MAP_KEY is not configured on the server.",
        )

    try:
        frame = await fetch_detections(
            settings.firms_map_key,
            location.bbox,
            acquisition_date,
            settings.request_timeout_seconds,
        )
    except FirmsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result = analyze(frame)
    return {
        "selection": {
            "location_id": location.id,
            "location": location.name,
            "country": location.country,
            "date": acquisition_date.isoformat(),
            "bbox": location.bbox,
            "center": location.center,
            "zoom": location.zoom,
        },
        "metrics": result.metrics,
        "detections": result.detections,
        "perimeters": result.perimeters,
        "model": model_metadata(),
        "sources": [
            "MODIS_NRT",
            "VIIRS_NOAA20_NRT",
            "VIIRS_NOAA21_NRT",
            "VIIRS_SNPP_NRT",
        ],
    }

