const form = document.querySelector("#analysis-form");
const submitButton = document.querySelector("#submit-button");
const toast = document.querySelector("#toast");
let selectedBbox = null;

const currentYear = new Date().getFullYear();
const startYear = document.querySelector("#start-year");
const endYear = document.querySelector("#end-year");
if (startYear && endYear) {
  startYear.value = String(currentYear - 2);
  endYear.value = String(currentYear - 1);
}
const todayLabel = document.querySelector("#today-label");
if (todayLabel) todayLabel.textContent = new Intl.DateTimeFormat("en-US", {
  day: "numeric",
  month: "long",
  year: "numeric",
}).format(new Date());

const number = (value, digits = 1) =>
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value)
    : null;

const average = (values) => {
  const valid = values.filter((value) => typeof value === "number" && Number.isFinite(value));
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 4500);
}

function updateSelectedArea(bounds, map, rectangle) {
  const southWest = bounds.getSouthWest();
  const northEast = bounds.getNorthEast();
  const bbox = [
    southWest.lng,
    southWest.lat,
    northEast.lng,
    northEast.lat,
  ];
  if (bbox[2] - bbox[0] > 0.25 || bbox[3] - bbox[1] > 0.25) {
    rectangle.remove();
    showToast("The selected area is too large. Choose a box no more than 0.25° wide and tall.");
    return false;
  }

  selectedBbox = bbox.map((value) => Number(value.toFixed(7)));
  document.querySelector("#longitude").value = ((bbox[0] + bbox[2]) / 2).toFixed(6);
  document.querySelector("#latitude").value = ((bbox[1] + bbox[3]) / 2).toFixed(6);
  document.querySelector("#bbox-summary").textContent =
    `Selected area · ${(bbox[2] - bbox[0]).toFixed(4)}° × ${(bbox[3] - bbox[1]).toFixed(4)}° · midpoint used for coordinates`;
  sessionStorage.setItem("crorb-selected-bbox", JSON.stringify(selectedBbox));
  return true;
}

function initAreaPicker() {
  const mapElement = document.querySelector("#area-map");
  if (!mapElement || !window.L) return;

  const latitude = Number(document.querySelector("#latitude").value);
  const longitude = Number(document.querySelector("#longitude").value);
  const halfSpan = 0.01;
  const initialBbox = [
    longitude - halfSpan,
    latitude - halfSpan,
    longitude + halfSpan,
    latitude + halfSpan,
  ];
  try {
    const savedBbox = JSON.parse(sessionStorage.getItem("crorb-selected-bbox") || "null");
    if (Array.isArray(savedBbox) && savedBbox.length === 4 && savedBbox.every(Number.isFinite)) {
      initialBbox.splice(0, 4, ...savedBbox);
    }
  } catch (error) {
    console.warn("Saved Crorb area could not be restored.", error);
  }

  const map = L.map(mapElement, { scrollWheelZoom: true }).setView(
    [(initialBbox[1] + initialBbox[3]) / 2, (initialBbox[0] + initialBbox[2]) / 2],
    14,
  );
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Tiles &copy; Esri" },
  ).addTo(map);
  const rectangle = L.rectangle(
    [[initialBbox[1], initialBbox[0]], [initialBbox[3], initialBbox[2]]],
    { color: "#b7ed83", weight: 2, fillColor: "#a9df76", fillOpacity: 0.18 },
  ).addTo(map);
  map.fitBounds(rectangle.getBounds(), { padding: [12, 12] });
  selectedBbox = initialBbox;
  updateSelectedArea(rectangle.getBounds(), map, rectangle);
  window.setTimeout(() => map.invalidateSize(), 100);
  const resizeObserver = new ResizeObserver(() => map.invalidateSize({ pan: false }));
  resizeObserver.observe(mapElement);

  const drawButton = document.querySelector("#draw-area-button");
  const mapContainer = map.getContainer();
  let drawingEnabled = false;
  let startPoint = null;
  let draftRectangle = null;

  function setDrawingMode(enabled) {
    drawingEnabled = enabled;
    drawButton.classList.toggle("active", enabled);
    drawButton.textContent = enabled
      ? "Cancel selection"
      : selectedBbox
        ? "Redraw box"
        : "Draw a box";
    mapContainer.classList.toggle("drawing", enabled);
    if (enabled) {
      map.dragging.disable();
      map.touchZoom.disable();
    } else {
      map.dragging.enable();
      map.touchZoom.enable();
    }
  }

  function cancelDraft() {
    startPoint = null;
    if (draftRectangle) draftRectangle.remove();
    draftRectangle = null;
  }

  drawButton.addEventListener("click", () => {
    const enabled = !drawingEnabled;
    setDrawingMode(enabled);
    document.querySelector("#bbox-summary").textContent = drawingEnabled
      ? "Click and drag on the map to draw the field boundary."
      : "Drag on the map to select a field area. The box midpoint is used as the coordinates.";
  });

  mapContainer.addEventListener("pointerdown", (event) => {
    if (!drawingEnabled || !event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    mapContainer.setPointerCapture(event.pointerId);
    startPoint = map.mouseEventToLatLng(event);
    draftRectangle = L.rectangle([startPoint, startPoint], {
      color: "#d8ff8a",
      weight: 2,
      dashArray: "6 5",
      fillOpacity: 0.12,
    }).addTo(map);
  });

  mapContainer.addEventListener("pointermove", (event) => {
    if (!startPoint || !draftRectangle) return;
    const currentPoint = map.mouseEventToLatLng(event);
    draftRectangle.setBounds(L.latLngBounds(startPoint, currentPoint));
  });

  mapContainer.addEventListener("pointerup", (event) => {
    if (!startPoint || !draftRectangle) return;
    const currentPoint = map.mouseEventToLatLng(event);
    const bounds = L.latLngBounds(startPoint, currentPoint);
    const completedRectangle = draftRectangle;
    cancelDraft();
    if (bounds.getNorthEast().lat - bounds.getSouthWest().lat < 0.0001
      || bounds.getNorthEast().lng - bounds.getSouthWest().lng < 0.0001) {
      completedRectangle.remove();
      setDrawingMode(false);
      return;
    }
    if (updateSelectedArea(bounds, map, completedRectangle)) {
      rectangle.remove();
      map.fitBounds(bounds, { padding: [18, 18], maxZoom: 16 });
    }
    setDrawingMode(false);
  });

  mapContainer.addEventListener("pointercancel", () => {
    if (!startPoint) return;
    cancelDraft();
    setDrawingMode(false);
  });
}

function setMetric(id, value, unit, digits = 1) {
  const element = document.querySelector(`#${id}`);
  if (!element) return;
  const formatted = number(value, digits);
  element.innerHTML = formatted === null ? `—<small>${unit}</small>` : `${formatted} <small>${unit}</small>`;
}

function setLoading(loading, label = "Collecting data…") {
  if (!submitButton) return;
  submitButton.disabled = loading;
  submitButton.classList.toggle("loading", loading);
  submitButton.querySelector(".button-label").textContent = loading ? label : "Analyze field";
}

function renderRecommendation(recommendation, error, location) {
  const body = document.querySelector("#recommendation-body");
  if (!body) return;
  if (!recommendation) {
    body.innerHTML = `
      <div class="empty-plant" aria-hidden="true"><span>!</span></div>
      <h2>${error ? "Field data loaded." : "Analysis is not available yet."}</h2>
      <p>${error || "Try again when data sources are available."}</p>
      <div class="recommendation-footer"><span>◎</span> ${escapeHtml(location.name)}</div>
    `;
    return;
  }

  const score = Number(recommendation.skor_kecocokan);
  const alternatives = Array.isArray(recommendation.alternatif)
    ? recommendation.alternatif
    : [];
  body.innerHTML = `
    <div class="crop-label">TOP CROP</div>
    <h2 class="crop-name">${escapeHtml(recommendation.tanaman_utama || "No recommendation yet")}</h2>
    <div class="match-row">
      <div class="match-track"><span style="width:${Number.isFinite(score) ? Math.min(100, Math.max(0, score)) : 0}%"></span></div>
      <strong>${Number.isFinite(score) ? `${escapeHtml(String(score))}%` : "—"}</strong>
      <span>match score</span>
    </div>
    <p class="recommendation-reason">${escapeHtml(recommendation.alasan || "No explanation available.")}</p>
    ${alternatives.length ? `<div class="alternatives"><span>ALTERNATIVES</span>${alternatives.map((crop) => `<b>${escapeHtml(crop)}</b>`).join("")}</div>` : ""}
    ${recommendation.catatan_data ? `<p class="data-note">${escapeHtml(recommendation.catatan_data)}</p>` : ""}
    <div class="recommendation-footer"><span>◎</span> ${escapeHtml(location.name)}</div>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function renderMetrics(data) {
  const nasa = Object.entries(data.nasa_power || {})
    .filter(([date]) => date.length === 6 && !date.endsWith("13"))
    .map(([, values]) => values);
  const mpc = data.mpc || {};
  const meanRainfall = average(nasa.map((month) => month.rainfall));
  setMetric("metric-temperature", average(nasa.map((month) => month.temperature)), "°C");
  setMetric("metric-rainfall", meanRainfall === null ? null : meanRainfall * 30.44, "mm/month");
  setMetric("metric-humidity", average(nasa.map((month) => month.humidity)), "%");
  setMetric("metric-soil-wetness", average(nasa.map((month) => month.soil_wetness)), "index", 2);
  setMetric("metric-solar", average(nasa.map((month) => month.solar_radiation)), "kWh/m²/day");
  setMetric("metric-elevation", mpc.elevation, "m");
  setMetric("metric-slope", mpc.slope, "°");
}

function renderChart(forecast) {
  const chart = document.querySelector("#rain-chart");
  if (!chart) return;
  const months = Object.entries(forecast || {})
    .filter(([, values]) => typeof values.rainfall_mm === "number")
    .sort(([first], [second]) => first.localeCompare(second));
  if (!months.length) {
    chart.innerHTML = '<div class="chart-empty">No forecast is available for this location.</div>';
    return;
  }

  const maximum = Math.max(...months.map(([, values]) => values.rainfall_mm), 1);
  const bars = months.map(([month, values]) => {
    const height = Math.max(5, (values.rainfall_mm / maximum) * 100);
    const label = new Intl.DateTimeFormat("en-US", { month: "short" })
      .format(new Date(`${month}-01T00:00:00`));
    return `
      <div class="chart-column" title="${escapeHtml(label)}: ${number(values.rainfall_mm)} mm">
        <span class="chart-value">${number(values.rainfall_mm, 0)}</span>
        <div class="bar-track"><span style="height:${height}%"></span></div>
        <span class="chart-month">${escapeHtml(label)}</span>
      </div>
    `;
  }).join("");
  chart.innerHTML = `<div class="chart-grid"><span>${number(maximum, 0)}</span><span>${number(maximum / 2, 0)}</span><span>0</span></div><div class="chart-bars">${bars}</div>`;
}

function renderSoil(soil) {
  const container = document.querySelector("#soil-list");
  if (!container) return;
  const properties = [
    ["phh2o", "Soil pH"],
    ["nitrogen", "Nitrogen"],
    ["clay", "Clay"],
    ["silt", "Silt"],
    ["sand", "Sand"],
    ["soc", "Organic carbon"],
  ];
  const rows = properties.map(([key, label]) => {
    const depths = (soil || {})[key] || {};
    const valueAtDepth = (depth) => {
      const formatted = number(depths[depth]);
      return formatted === null ? "Not available" : formatted;
    };
    return `<div class="soil-row"><span>${label}</span><strong>${valueAtDepth("0-5cm")}</strong><strong>${valueAtDepth("5-15cm")}</strong></div>`;
  });
  container.innerHTML = rows.join("");
}

function renderNdvi(ndvi, error) {
  const image = document.querySelector("#ndvi-image");
  if (!image) return;
  const placeholder = document.querySelector("#ndvi-empty");
  const date = document.querySelector("#ndvi-scene-date");
  const mean = document.querySelector("#ndvi-mean");
  const median = document.querySelector("#ndvi-median");
  const cloud = document.querySelector("#ndvi-cloud");
  if (!ndvi?.thumbnail) {
    image.hidden = true;
    placeholder.hidden = false;
    placeholder.textContent = error || "NDVI imagery is not available. Check the selected area or try again.";
    date.textContent = "Imagery unavailable";
    mean.textContent = "—";
    median.textContent = "—";
    cloud.textContent = "—";
    return;
  }

  image.src = `data:image/png;base64,${ndvi.thumbnail}`;
  image.hidden = false;
  placeholder.hidden = true;
  date.textContent = `Sentinel-2 · ${ndvi.scene_date || "date unavailable"}`;
  mean.textContent = number(ndvi.mean, 3) ?? "—";
  median.textContent = number(ndvi.median, 3) ?? "—";
  cloud.textContent = number(ndvi.cloud_cover_pct, 1) === null
    ? "—"
    : `${number(ndvi.cloud_cover_pct, 1)}%`;
}

function renderForecastTable(forecast, location) {
  const body = document.querySelector("#forecast-rows");
  if (!body) return;
  const locationLabel = document.querySelector("#forecast-location");
  if (locationLabel) locationLabel.textContent = location?.name || "No location yet";

  const months = Object.entries(forecast || {})
    .filter(([, values]) => typeof values.rainfall_mm === "number")
    .sort(([first], [second]) => first.localeCompare(second));
  if (!months.length) {
    body.innerHTML = '<tr><td colspan="5" class="table-empty">Forecast data will appear after analyzing a location.</td></tr>';
    return;
  }
  body.innerHTML = months.map(([month, values]) => {
    const date = new Date(`${month}-01T00:00:00`);
    const monthLabel = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(date);
    const temperature = [number(values.temp_min_c), number(values.temp_max_c)].filter(Boolean).join("–");
    return `<tr><td>${escapeHtml(monthLabel)}</td><td>${number(values.rainfall_mm)} mm</td><td>${number(values.water_balance_mm)} mm</td><td>${temperature ? `${temperature} °C` : "—"}</td><td>${number(values.humidity_pct)}%</td></tr>`;
  }).join("");
}

function renderSourceErrors(errors) {
  const names = {
    mpc: "terrain",
    nasa_power: "historical climate",
    soilgrids: "soil",
    meteomatics: "weather forecast",
    ndvi: "NDVI satellite imagery",
  };
  const failed = Object.keys(errors || {}).map((source) => names[source] || source);
  if (failed.length) showToast(`Some data is unavailable: ${failed.join(", ")}.`);
}

function renderAnalysis(result) {
  const data = result.data || {};
  if (Array.isArray(result.location?.bbox)) {
    selectedBbox = result.location.bbox;
    sessionStorage.setItem("crorb-selected-bbox", JSON.stringify(selectedBbox));
  }
  renderMetrics(data);
  renderChart(data.meteomatics);
  renderForecastTable(data.meteomatics, result.location);
  renderSoil(data.soilgrids);
  renderNdvi(data.ndvi, result.source_errors?.ndvi);
  renderRecommendation(result.recommendation, result.recommendation_error, result.location);
  const caption = document.querySelector("#data-caption");
  if (caption) {
    caption.textContent = `${result.location.name} · ${result.location.latitude}, ${result.location.longitude}`;
  }
  renderSourceErrors(result.source_errors);
}

initAreaPicker();

try {
  const savedAnalysis = sessionStorage.getItem("crorb-analysis");
  if (savedAnalysis) renderAnalysis(JSON.parse(savedAnalysis));
} catch (error) {
  console.warn("Saved Crorb analysis could not be restored.", error);
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const fields = new FormData(form);
  const payload = {
    name: fields.get("name"),
    latitude: fields.get("latitude"),
    longitude: fields.get("longitude"),
    bbox: selectedBbox,
    start: fields.get("start"),
    end: fields.get("end"),
  };
  if (Number(payload.end) < Number(payload.start)) {
    showToast("The end year must be the same as or later than the start year.");
    return;
  }

  setLoading(true, "Loading satellite imagery…");
  document.querySelector("#data-caption").textContent = "Loading satellite imagery…";
  renderNdvi(null, "Loading Sentinel-2 imagery for the selected area…");
  document.querySelector("#ndvi-scene-date").textContent = "Searching for imagery…";
  let ndvi = null;
  let ndviError = null;
  try {
    try {
      const ndviResponse = await fetch("/api/ndvi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const ndviResult = await ndviResponse.json();
      if (!ndviResponse.ok) throw new Error(ndviResult.error || "Satellite imagery could not be loaded.");
      ndvi = ndviResult.ndvi;
      ndviError = ndviResult.error || null;
    } catch (error) {
      ndviError = error.message || "Satellite imagery could not be loaded.";
    }

    renderNdvi(ndvi, ndviError);
    setLoading(true, "Collecting field data…");
    document.querySelector("#data-caption").textContent = "Collecting weather, soil, and terrain data…";
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...payload,
        ndvi: ndvi && {
          scene_date: ndvi.scene_date,
          cloud_cover_pct: ndvi.cloud_cover_pct,
          mean: ndvi.mean,
          median: ndvi.median,
          min: ndvi.min,
          max: ndvi.max,
        },
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The request could not be processed.");

    result.data = result.data || {};
    result.data.ndvi = ndvi;
    if (ndviError) result.source_errors = { ...result.source_errors, ndvi: ndviError };
    sessionStorage.setItem("crorb-analysis", JSON.stringify(result));
    renderAnalysis(result);
  } catch (error) {
    const caption = document.querySelector("#data-caption");
    if (caption) caption.textContent = "Analysis failed";
    showToast(error.message || "Could not connect to the server. Please try again.");
  } finally {
    setLoading(false);
  }
});
