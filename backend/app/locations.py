from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    country: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    zoom: int


LOCATIONS = (
    Location("alberta", "Alberta", "Canada", (-120.0, 48.99, -110.0, 60.0), (54.5, -115.0), 5),
    Location("british-columbia", "British Columbia", "Canada", (-139.1, 48.2, -114.0, 60.0), (54.4, -125.0), 5),
    Location("saskatchewan", "Saskatchewan", "Canada", (-110.0, 49.0, -101.35, 60.0), (54.5, -105.7), 5),
    Location("manitoba", "Manitoba", "Canada", (-102.0, 49.0, -88.9, 60.0), (54.8, -97.4), 5),
    Location("ontario", "Ontario", "Canada", (-95.2, 41.6, -74.3, 56.9), (49.2, -84.7), 5),
    Location("quebec", "Quebec", "Canada", (-79.8, 44.9, -57.1, 62.6), (52.0, -70.0), 5),
    Location("northwest-territories", "Northwest Territories", "Canada", (-136.5, 60.0, -102.0, 78.8), (66.4, -119.5), 4),
    Location("yukon", "Yukon", "Canada", (-141.1, 60.0, -123.8, 69.7), (64.5, -135.5), 5),
    Location("canada", "All Canada", "Canada", (-141.0, 41.7, -52.6, 83.1), (58.0, -96.0), 3),
    Location("california", "California", "USA", (-124.5, 32.4, -114.0, 42.1), (37.2, -119.5), 5),
    Location("pacific-northwest", "Pacific Northwest", "USA", (-125.0, 41.8, -116.8, 49.1), (45.7, -121.0), 5),
    Location("rocky-mountain", "Rocky Mountain Region", "USA", (-116.2, 31.2, -102.0, 49.1), (40.2, -109.0), 4),
    Location("alaska", "Alaska", "USA", (-179.2, 51.0, -129.9, 71.5), (63.5, -152.0), 4),
    Location("usa", "Contiguous USA", "USA", (-124.8, 24.4, -66.9, 49.4), (38.2, -96.5), 4),
)

LOCATION_BY_ID = {location.id: location for location in LOCATIONS}


def public_locations() -> list[dict]:
    return [asdict(location) for location in LOCATIONS]

