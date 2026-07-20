from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import Delaunay, QhullError
from shapely.geometry import MultiPoint, Point, Polygon, mapping
from shapely.ops import transform, unary_union
from sklearn.cluster import DBSCAN

MODEL_CRS = "ESRI:102001"
EPS_METERS = 1_500
MIN_SAMPLES = 3
ALPHA = 0.2
ALPHA_SCALE_FACTOR = 5
BUFFER_DISTANCES = {
    "MODIS_NRT": 1_000,
    "VIIRS_NOAA20_NRT": 375,
    "VIIRS_NOAA21_NRT": 375,
    "VIIRS_SNPP_NRT": 375,
}

TO_MODEL = Transformer.from_crs("EPSG:4326", MODEL_CRS, always_xy=True)
TO_WGS84 = Transformer.from_crs(MODEL_CRS, "EPSG:4326", always_xy=True)


@dataclass
class ModelResult:
    detections: list[dict[str, Any]]
    perimeters: dict[str, Any]
    metrics: dict[str, Any]


def _number(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _alpha_shape(points: np.ndarray) -> Polygon | Any:
    if len(points) < 4:
        return MultiPoint(points).convex_hull.buffer(EPS_METERS * 0.35)

    try:
        triangles = Delaunay(points)
    except QhullError:
        return MultiPoint(points).convex_hull.buffer(EPS_METERS * 0.35)

    accepted = []
    radius_limit = EPS_METERS * ALPHA_SCALE_FACTOR / max(ALPHA, 0.01)
    for indices in triangles.simplices:
        triangle_points = points[indices]
        a = np.linalg.norm(triangle_points[0] - triangle_points[1])
        b = np.linalg.norm(triangle_points[1] - triangle_points[2])
        c = np.linalg.norm(triangle_points[2] - triangle_points[0])
        semiperimeter = (a + b + c) / 2
        area_term = semiperimeter * (semiperimeter - a) * (semiperimeter - b) * (semiperimeter - c)
        if area_term <= 0:
            continue
        area = np.sqrt(area_term)
        circumradius = (a * b * c) / (4 * area)
        if circumradius <= radius_limit:
            accepted.append(Polygon(triangle_points))

    if not accepted:
        return MultiPoint(points).convex_hull.buffer(EPS_METERS * 0.35)
    return unary_union(accepted).buffer(EPS_METERS * 0.12)


def _confidence_value(row: pd.Series) -> float | None:
    value = row.get("confidence")
    numeric = _number(value)
    if numeric is not None:
        return numeric
    lookup = {"low": 30.0, "nominal": 60.0, "high": 90.0, "l": 30.0, "n": 60.0, "h": 90.0}
    return lookup.get(str(value).strip().lower())


def _serialize_detection(row: pd.Series, cluster: int) -> dict[str, Any]:
    raw_time = str(row.get("acq_time", "")).split(".")[0].zfill(4)
    time_label = f"{raw_time[:2]}:{raw_time[2:4]} UTC" if len(raw_time) >= 4 else "—"
    return {
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "date": str(row.get("acq_date", "")),
        "time": time_label,
        "sensor": str(row.get("sensor", row.get("source", "Unknown"))),
        "source": str(row.get("source", "Unknown")),
        "confidence": _confidence_value(row),
        "brightness": _number(row.get("bright_ti4", row.get("brightness"))),
        "frp": _number(row.get("frp")),
        "daynight": str(row.get("daynight", "")),
        "cluster": cluster,
    }


def analyze(frame: pd.DataFrame) -> ModelResult:
    if frame.empty:
        return ModelResult([], {"type": "FeatureCollection", "features": []}, _empty_metrics())

    clean = frame.dropna(subset=["longitude", "latitude"]).copy()
    clean["longitude"] = pd.to_numeric(clean["longitude"], errors="coerce")
    clean["latitude"] = pd.to_numeric(clean["latitude"], errors="coerce")
    clean = clean.dropna(subset=["longitude", "latitude"]).reset_index(drop=True)
    if clean.empty:
        return ModelResult([], {"type": "FeatureCollection", "features": []}, _empty_metrics())

    x_values, y_values = TO_MODEL.transform(clean["longitude"].to_numpy(), clean["latitude"].to_numpy())
    coordinates = np.column_stack([x_values, y_values])
    labels = DBSCAN(eps=EPS_METERS, min_samples=MIN_SAMPLES).fit_predict(coordinates)
    clean["cluster"] = labels

    geometries: list[tuple[Any, dict[str, Any]]] = []
    cluster_ids = sorted(cluster_id for cluster_id in set(labels) if cluster_id >= 0)
    for cluster_id in cluster_ids:
        mask = labels == cluster_id
        geometry = _alpha_shape(coordinates[mask])
        geometries.append((geometry, {"kind": "cluster", "cluster": int(cluster_id)}))

    for index in np.where(labels == -1)[0]:
        source = str(clean.iloc[index].get("source", ""))
        distance = BUFFER_DISTANCES.get(source, 500)
        geometries.append((Point(coordinates[index]).buffer(distance), {"kind": "outlier", "cluster": -1}))

    features = []
    total_area_hectares = 0.0
    for geometry, properties in geometries:
        if geometry.is_empty:
            continue
        area_hectares = geometry.area / 10_000
        total_area_hectares += area_hectares
        wgs84_geometry = transform(TO_WGS84.transform, geometry)
        features.append(
            {
                "type": "Feature",
                "geometry": mapping(wgs84_geometry),
                "properties": {**properties, "area_hectares": round(area_hectares, 1)},
            }
        )

    detections = [
        _serialize_detection(clean.iloc[index], int(labels[index]))
        for index in range(len(clean))
    ]
    confidence_values = [item["confidence"] for item in detections if item["confidence"] is not None]
    sensor_counts = clean["sensor"].fillna("Unknown").value_counts().to_dict()
    day_count = int((clean.get("daynight", pd.Series(dtype=str)).astype(str).str.upper() == "D").sum())

    metrics = {
        "detections": len(detections),
        "clusters": len(cluster_ids),
        "outliers": int(np.sum(labels == -1)),
        "perimeters": len(features),
        "area_hectares": round(total_area_hectares, 1),
        "average_confidence": round(float(np.mean(confidence_values)), 1) if confidence_values else None,
        "day_detections": day_count,
        "night_detections": len(detections) - day_count,
        "sensor_counts": {str(key): int(value) for key, value in sensor_counts.items()},
    }
    return ModelResult(detections, {"type": "FeatureCollection", "features": features}, metrics)


def _empty_metrics() -> dict[str, Any]:
    return {
        "detections": 0,
        "clusters": 0,
        "outliers": 0,
        "perimeters": 0,
        "area_hectares": 0,
        "average_confidence": None,
        "day_detections": 0,
        "night_detections": 0,
        "sensor_counts": {},
    }


def model_metadata() -> dict[str, Any]:
    return {
        "crs": MODEL_CRS,
        "eps_meters": EPS_METERS,
        "min_samples": MIN_SAMPLES,
        "alpha": ALPHA,
        "alpha_scale_factor": ALPHA_SCALE_FACTOR,
        "buffer_distances_meters": BUFFER_DISTANCES,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

