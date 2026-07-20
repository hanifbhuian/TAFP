from __future__ import annotations

import asyncio
from datetime import date
from io import StringIO

import httpx
import pandas as pd

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/usfs/api/area/csv"
SOURCES = {
    "MODIS_NRT": "MODIS",
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20",
    "VIIRS_NOAA21_NRT": "VIIRS NOAA-21",
    "VIIRS_SNPP_NRT": "VIIRS SNPP",
}


class FirmsError(RuntimeError):
    """A safe-to-display FIRMS retrieval error."""


def _bbox_string(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{coordinate:g}" for coordinate in bbox)


def build_url(
    map_key: str,
    source: str,
    bbox: tuple[float, float, float, float],
    acquisition_date: date,
) -> str:
    if source not in SOURCES:
        raise ValueError(f"Unsupported FIRMS source: {source}")
    return (
        f"{FIRMS_BASE_URL}/{map_key}/{source}/{_bbox_string(bbox)}"
        f"/1/{acquisition_date.isoformat()}"
    )


async def _fetch_source(
    client: httpx.AsyncClient,
    map_key: str,
    source: str,
    bbox: tuple[float, float, float, float],
    acquisition_date: date,
) -> pd.DataFrame:
    response = await client.get(build_url(map_key, source, bbox, acquisition_date))
    response.raise_for_status()
    body = response.text.strip()
    if not body or body.lower().startswith(("no data", "invalid map_key")):
        if body.lower().startswith("invalid map_key"):
            raise FirmsError("NASA FIRMS rejected the configured MAP_KEY.")
        return pd.DataFrame()

    try:
        frame = pd.read_csv(StringIO(body))
    except Exception as exc:  # pandas gives several parser exception types
        raise FirmsError(f"FIRMS returned an unreadable {source} response.") from exc

    if frame.empty:
        return frame

    required = {"latitude", "longitude", "acq_date", "acq_time"}
    if not required.issubset(frame.columns):
        raise FirmsError(f"FIRMS {source} response is missing required columns.")

    frame = frame.copy()
    frame["source"] = source
    frame["sensor"] = SOURCES[source]
    return frame


async def fetch_detections(
    map_key: str,
    bbox: tuple[float, float, float, float],
    acquisition_date: date,
    timeout_seconds: float,
) -> pd.DataFrame:
    timeout = httpx.Timeout(timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            frames = await asyncio.gather(
                *(
                    _fetch_source(client, map_key, source, bbox, acquisition_date)
                    for source in SOURCES
                )
            )
    except FirmsError:
        raise
    except httpx.HTTPStatusError as exc:
        raise FirmsError(
            f"NASA FIRMS returned HTTP {exc.response.status_code}. Try again shortly."
        ) from exc
    except httpx.HTTPError as exc:
        raise FirmsError("NASA FIRMS could not be reached. Try again shortly.") from exc

    populated = [frame for frame in frames if not frame.empty]
    if not populated:
        return pd.DataFrame()
    return pd.concat(populated, ignore_index=True, sort=False)

