import pandas as pd

from app.firms import build_url
from app.model import analyze


def test_build_url_uses_bbox_instead_of_world():
    from datetime import date

    url = build_url("secret-key", "MODIS_NRT", (-120, 49, -110, 60), date(2026, 7, 20))
    assert "/MODIS_NRT/-120,49,-110,60/1/2026-07-20" in url
    assert "/world/" not in url


def test_empty_model_result():
    result = analyze(pd.DataFrame())
    assert result.metrics["detections"] == 0
    assert result.perimeters == {"type": "FeatureCollection", "features": []}


def test_model_clusters_nearby_detections():
    frame = pd.DataFrame(
        {
            "latitude": [53.5000, 53.5030, 53.5060, 54.5],
            "longitude": [-113.5000, -113.5050, -113.5100, -115.0],
            "acq_date": ["2026-07-20"] * 4,
            "acq_time": [1200, 1205, 1210, 1300],
            "source": ["VIIRS_SNPP_NRT"] * 4,
            "sensor": ["VIIRS SNPP"] * 4,
            "confidence": [80, 90, 70, 50],
            "daynight": ["D", "D", "D", "N"],
        }
    )
    result = analyze(frame)
    assert result.metrics["detections"] == 4
    assert result.metrics["clusters"] == 1
    assert result.metrics["outliers"] == 1
    assert result.metrics["perimeters"] == 2
    assert result.metrics["average_confidence"] == 72.5

