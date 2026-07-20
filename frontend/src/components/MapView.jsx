import { useEffect } from "react";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";

const SENSOR_COLORS = {
  "VIIRS NOAA-20": "#2ec4b6",
  "VIIRS NOAA-21": "#47a7ff",
  "VIIRS SNPP": "#ff9f43",
  MODIS: "#ef5b5b",
};

function Viewport({ location }) {
  const map = useMap();

  useEffect(() => {
    if (!location) return;
    const [west, south, east, north] = location.bbox;
    map.fitBounds(
      [
        [south, west],
        [north, east],
      ],
      { padding: [24, 24], animate: true }
    );
  }, [location, map]);

  return null;
}

function DetectionPopup({ detection }) {
  return (
    <div className="map-popup">
      <p className="popup-kicker">Satellite detection</p>
      <strong>{detection.sensor}</strong>
      <dl>
        <div><dt>Observed</dt><dd>{detection.date} · {detection.time}</dd></div>
        <div><dt>Confidence</dt><dd>{detection.confidence == null ? "Not reported" : `${detection.confidence}%`}</dd></div>
        <div><dt>FRP</dt><dd>{detection.frp == null ? "—" : `${detection.frp} MW`}</dd></div>
        <div><dt>Cluster</dt><dd>{detection.cluster < 0 ? "Outlier" : `#${detection.cluster + 1}`}</dd></div>
      </dl>
    </div>
  );
}

export default function MapView({
  theme,
  location,
  detections,
  perimeters,
  showDetections,
  showPerimeters,
}) {
  const tileUrl = theme === "dark"
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  return (
    <MapContainer
      center={location?.center || [54.5, -115]}
      zoom={location?.zoom || 5}
      minZoom={2}
      worldCopyJump
      zoomControl
      className="map-canvas"
    >
      <TileLayer
        key={theme}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; CARTO'
        url={tileUrl}
      />
      <Viewport location={location} />

      {showPerimeters && perimeters?.features?.length > 0 && (
        <GeoJSON
          key={JSON.stringify(perimeters).length + theme}
          data={perimeters}
          style={(feature) => ({
            color: feature.properties.kind === "cluster" ? "#ff694d" : "#ffb34d",
            weight: feature.properties.kind === "cluster" ? 2 : 1.5,
            opacity: 0.95,
            fillColor: feature.properties.kind === "cluster" ? "#ff5a43" : "#ffb34d",
            fillOpacity: theme === "dark" ? 0.24 : 0.18,
          })}
          onEachFeature={(feature, layer) => {
            const label = feature.properties.kind === "cluster"
              ? `TAFP cluster #${feature.properties.cluster + 1}`
              : "Buffered outlier";
            layer.bindTooltip(`${label} · ${Number(feature.properties.area_hectares).toLocaleString()} ha`);
          }}
        />
      )}

      {showDetections && detections.map((detection, index) => (
        <CircleMarker
          key={`${detection.source}-${detection.latitude}-${detection.longitude}-${index}`}
          center={[detection.latitude, detection.longitude]}
          radius={detection.source === "MODIS_NRT" ? 5 : 4}
          pathOptions={{
            color: theme === "dark" ? "#08110f" : "#ffffff",
            weight: 1,
            fillColor: SENSOR_COLORS[detection.sensor] || "#ff6b50",
            fillOpacity: 0.9,
          }}
        >
          <Popup><DetectionPopup detection={detection} /></Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

