import { useCallback, useEffect, useMemo, useState } from "react";
import MapView from "./components/MapView";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const FALLBACK_LOCATIONS = [
  { id: "alberta", name: "Alberta", country: "Canada", bbox: [-120, 48.99, -110, 60], center: [54.5, -115], zoom: 5 },
  { id: "british-columbia", name: "British Columbia", country: "Canada", bbox: [-139.1, 48.2, -114, 60], center: [54.4, -125], zoom: 5 },
  { id: "saskatchewan", name: "Saskatchewan", country: "Canada", bbox: [-110, 49, -101.35, 60], center: [54.5, -105.7], zoom: 5 },
  { id: "canada", name: "All Canada", country: "Canada", bbox: [-141, 41.7, -52.6, 83.1], center: [58, -96], zoom: 3 },
  { id: "california", name: "California", country: "USA", bbox: [-124.5, 32.4, -114, 42.1], center: [37.2, -119.5], zoom: 5 },
  { id: "pacific-northwest", name: "Pacific Northwest", country: "USA", bbox: [-125, 41.8, -116.8, 49.1], center: [45.7, -121], zoom: 5 },
  { id: "usa", name: "Contiguous USA", country: "USA", bbox: [-124.8, 24.4, -66.9, 49.4], center: [38.2, -96.5], zoom: 4 },
];

const EMPTY_METRICS = {
  detections: 0,
  clusters: 0,
  area_hectares: 0,
  average_confidence: null,
  sensor_counts: {},
  day_detections: 0,
  night_detections: 0,
};

function localDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function formatArea(value) {
  if (!value) return "0 ha";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M ha`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K ha`;
  return `${Math.round(value).toLocaleString()} ha`;
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function ThemeToggle({ theme, onToggle }) {
  return (
    <button className="theme-toggle" type="button" onClick={onToggle} aria-label={`Use ${theme === "dark" ? "light" : "dark"} theme`}>
      <span className="theme-icon" aria-hidden="true">{theme === "dark" ? "☾" : "☀"}</span>
      <span>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}

function MetricCard({ label, value, accent, detail }) {
  return (
    <article className="metric-card">
      <span className={`metric-signal ${accent}`} aria-hidden="true" />
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function Toggle({ checked, onChange, color, label, detail }) {
  return (
    <label className="layer-row">
      <span className="layer-swatch" style={{ background: color }} />
      <span className="layer-copy"><strong>{label}</strong><small>{detail}</small></span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="switch" aria-hidden="true" />
    </label>
  );
}

function SensorBars({ counts }) {
  const entries = Object.entries(counts || {});
  const max = Math.max(1, ...entries.map(([, value]) => value));
  if (!entries.length) return <p className="quiet-copy">No sensor detections for this selection.</p>;

  return (
    <div className="sensor-bars">
      {entries.map(([sensor, count]) => (
        <div className="sensor-item" key={sensor}>
          <div className="sensor-label"><span>{sensor}</span><strong>{count.toLocaleString()}</strong></div>
          <div className="bar-track"><span style={{ width: `${Math.max(4, (count / max) * 100)}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("tafp-theme") || "dark");
  const [locations, setLocations] = useState(FALLBACK_LOCATIONS);
  const [locationId, setLocationId] = useState("alberta");
  const [date, setDate] = useState(localDate());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showDetections, setShowDetections] = useState(true);
  const [showPerimeters, setShowPerimeters] = useState(true);

  const selectedLocation = useMemo(
    () => locations.find((location) => location.id === locationId) || FALLBACK_LOCATIONS[0],
    [locations, locationId]
  );
  const metrics = data?.metrics || EMPTY_METRICS;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("tafp-theme", theme);
  }, [theme]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/locations`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Location service unavailable")))
      .then((payload) => {
        if (payload.locations?.length) setLocations(payload.locations);
      })
      .catch(() => {
        // The built-in list keeps the map usable while a free backend wakes up.
      });
  }, []);

  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ location_id: locationId, date });
      const response = await fetch(`${API_BASE_URL}/api/analyze?${params}`);
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "The analysis could not be completed.");
      setData(payload);
    } catch (requestError) {
      setError(requestError.message || "The analysis could not be completed.");
    } finally {
      setLoading(false);
    }
  }, [locationId, date]);

  useEffect(() => {
    runAnalysis();
  }, []); // Run only the initial Alberta/today view; Apply controls later.

  const selectedLabel = data?.selection && !loading
    ? `${data.selection.location}, ${data.selection.country}`
    : `${selectedLocation.name}, ${selectedLocation.country}`;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main-map" aria-label="TAFP dashboard home">
          <span className="brand-mark"><i /><i /><i /></span>
          <span><strong>TAFP</strong><small>Wildfire Intelligence</small></span>
        </a>
        <div className="topbar-status">
          <span className="live-pill"><i /> NASA FIRMS · NRT</span>
          <ThemeToggle theme={theme} onToggle={() => setTheme(theme === "dark" ? "light" : "dark")} />
        </div>
      </header>

      <main className="dashboard-layout">
        <aside className="control-panel" aria-label="Analysis controls">
          <div className="panel-heading">
            <p className="eyebrow">Analysis workspace</p>
            <h1>Active-fire perimeter explorer</h1>
            <p>Choose a location and date. TAFP retrieves live satellite detections and models potential fire perimeters.</p>
          </div>

          <section className="control-section">
            <div className="section-title"><span>01</span><h2>Location & date</h2></div>
            <label className="field-label" htmlFor="location">Location</label>
            <div className="select-wrap">
              <select id="location" value={locationId} onChange={(event) => setLocationId(event.target.value)}>
                {["Canada", "USA"].map((country) => (
                  <optgroup label={country} key={country}>
                    {locations.filter((location) => location.country === country).map((location) => (
                      <option value={location.id} key={location.id}>{location.name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            <label className="field-label" htmlFor="date">Acquisition date</label>
            <input id="date" type="date" max={localDate()} value={date} onChange={(event) => setDate(event.target.value)} />
            <button className="run-button" type="button" onClick={runAnalysis} disabled={loading || !date}>
              {loading ? <><span className="spinner" /> Running TAFP…</> : <>Run analysis <span>→</span></>}
            </button>
          </section>

          <section className="control-section">
            <div className="section-title"><span>02</span><h2>Map layers</h2></div>
            <Toggle checked={showPerimeters} onChange={setShowPerimeters} color="#ff694d" label="TAFP perimeters" detail="Cluster hulls + outlier buffers" />
            <Toggle checked={showDetections} onChange={setShowDetections} color="#2ec4b6" label="FIRMS detections" detail="MODIS + three VIIRS feeds" />
          </section>

          <section className="control-section model-note">
            <div className="section-title"><span>03</span><h2>Model settings</h2></div>
            <dl className="model-grid">
              <div><dt>DBSCAN radius</dt><dd>1,500 m</dd></div>
              <div><dt>Min. samples</dt><dd>3</dd></div>
              <div><dt>Alpha</dt><dd>0.2</dd></div>
              <div><dt>Projection</dt><dd>ESRI:102001</dd></div>
            </dl>
          </section>
        </aside>

        <section className="map-workspace" id="main-map">
          <div className="selection-banner">
            <div>
              <p>Selected view</p>
              <h2>{selectedLabel}</h2>
            </div>
            <div className="selection-date"><span>Acquisition date</span><strong>{formatDate(data?.selection?.date || date)}</strong></div>
          </div>

          <div className="metrics-strip">
            <MetricCard label="Detections" value={metrics.detections.toLocaleString()} detail="thermal anomalies" accent="teal" />
            <MetricCard label="TAFP clusters" value={metrics.clusters.toLocaleString()} detail={`${metrics.outliers || 0} outliers`} accent="orange" />
            <MetricCard label="Estimated area" value={formatArea(metrics.area_hectares)} detail="modeled footprint" accent="red" />
            <MetricCard label="Avg. confidence" value={metrics.average_confidence == null ? "—" : `${metrics.average_confidence}%`} detail="reported by FIRMS" accent="blue" />
          </div>

          <div className="map-frame">
            <MapView
              theme={theme}
              location={selectedLocation}
              detections={data?.detections || []}
              perimeters={data?.perimeters}
              showDetections={showDetections}
              showPerimeters={showPerimeters}
            />
            {loading && <div className="map-state"><span className="radar-loader" /><strong>Retrieving satellite observations</strong><small>Running the TAFP spatial model…</small></div>}
            {error && (
              <div className="map-state error-state">
                <strong>Analysis unavailable</strong>
                <small>{error}</small>
                <button type="button" onClick={runAnalysis}>Try again</button>
              </div>
            )}
            {!loading && !error && data && metrics.detections === 0 && (
              <div className="map-state empty-state"><strong>No active-fire detections</strong><small>FIRMS reported no observations for this location and date.</small></div>
            )}
            <div className="map-legend" aria-label="Map legend">
              <span><i className="legend-perimeter" /> Modeled perimeter</span>
              <span><i className="legend-detection" /> Satellite detection</span>
            </div>
          </div>
        </section>

        <aside className="insight-panel" aria-label="Analysis summary">
          <section className="insight-block overview-block">
            <div className="insight-heading"><div><p className="eyebrow">Scene summary</p><h2>Observation profile</h2></div><span className="quality-badge">NRT</span></div>
            <div className="day-night">
              <div><span className="sun-dot">☀</span><strong>{metrics.day_detections.toLocaleString()}</strong><small>Daytime</small></div>
              <div><span className="moon-dot">●</span><strong>{metrics.night_detections.toLocaleString()}</strong><small>Nighttime</small></div>
            </div>
          </section>

          <section className="insight-block">
            <div className="insight-heading"><div><p className="eyebrow">Source mix</p><h2>Detections by sensor</h2></div></div>
            <SensorBars counts={metrics.sensor_counts} />
          </section>

          <section className="insight-block source-block">
            <p className="eyebrow">Data provenance</p>
            <h2>NASA FIRMS feeds</h2>
            <ul>
              <li><span>MODIS</span><small>1 km nominal resolution</small></li>
              <li><span>VIIRS NOAA-20</span><small>375 m nominal resolution</small></li>
              <li><span>VIIRS NOAA-21</span><small>375 m nominal resolution</small></li>
              <li><span>VIIRS Suomi NPP</span><small>375 m nominal resolution</small></li>
            </ul>
          </section>

          <p className="disclaimer">Modeled perimeters support situational awareness and are not official incident boundaries. Confirm decisions with local authorities.</p>
        </aside>
      </main>
    </div>
  );
}

