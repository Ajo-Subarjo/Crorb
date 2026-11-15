import json
import logging
import math
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/cuaca.html": ("cuaca.html", "text/html; charset=utf-8"),
    "/tanah.html": ("tanah.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/overview.css": ("overview.css", "text/css; charset=utf-8"),
    "/weather.css": ("weather.css", "text/css; charset=utf-8"),
    "/soil.css": ("soil.css", "text/css; charset=utf-8"),
}
MAX_REQUEST_SIZE = 16_384
MAX_BBOX_SPAN_DEGREES = 0.25
logger = logging.getLogger("crorb.server")


def _validate_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Please complete the form first.")

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("The location name must be 1–80 characters.")

    try:
        latitude = float(payload["latitude"])
        longitude = float(payload["longitude"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Enter valid latitude and longitude coordinates.") from None

    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    start = str(payload.get("start", ""))
    end = str(payload.get("end", ""))
    if not re.fullmatch(r"\d{4}", start) or not re.fullmatch(r"\d{4}", end):
        raise ValueError("Start and end years must each use four digits.")
    if int(start) < 1981 or int(end) < int(start):
        raise ValueError("The date range must be ordered and start in 1981 or later.")

    raw_bbox = payload.get("bbox")
    if raw_bbox is None:
        half_span = 0.01
        bbox = [
            max(-180, longitude - half_span),
            max(-90, latitude - half_span),
            min(180, longitude + half_span),
            min(90, latitude + half_span),
        ]
    else:
        if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
            raise ValueError("The field area must have four coordinate boundaries.")
        try:
            bbox = [float(value) for value in raw_bbox]
        except (TypeError, ValueError):
            raise ValueError("The field area boundaries are invalid.") from None

    west, south, east, north = bbox
    if not all(math.isfinite(value) for value in bbox):
        raise ValueError("The field area boundaries must be valid coordinates.")
    if not -180 <= west < east <= 180 or not -90 <= south < north <= 90:
        raise ValueError("The field area boundaries must be within valid geographic coordinates.")
    if east - west > MAX_BBOX_SPAN_DEGREES or north - south > MAX_BBOX_SPAN_DEGREES:
        raise ValueError("The selected area is too large. Choose a box no more than 0.25° wide and tall.")

    latitude = (south + north) / 2
    longitude = (west + east) / 2

    return {
        "name": name.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "bbox": bbox,
        "start": start,
        "end": end,
    }


def _fetch_data(location):
    errors = {}
    from data import get_data

    data = get_data(
        lon=location["longitude"],
        lat=location["latitude"],
        start=location["start"],
        end=location["end"],
        errors=errors,
    )
    return data, errors


def _fetch_ndvi(location):
    from sentinel_ndvi import get_ndvi_data

    return get_ndvi_data(location["bbox"])


def _ndvi_summary(payload):
    raw_ndvi = payload.get("ndvi")
    if not isinstance(raw_ndvi, dict):
        return {}

    summary = {}
    scene_date = raw_ndvi.get("scene_date")
    if isinstance(scene_date, str) and len(scene_date) <= 40:
        summary["scene_date"] = scene_date

    for field in ("cloud_cover_pct", "mean", "median", "min", "max"):
        value = raw_ndvi.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            continue
        if field == "cloud_cover_pct" and not 0 <= value <= 100:
            continue
        if field != "cloud_cover_pct" and not -1 <= value <= 1:
            continue
        if field in raw_ndvi:
            summary[field] = value
    return summary


def _get_recommendation(name, data):
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER")):
        return None, "Set OPENROUTER_API_KEY to enable AI recommendations."

    try:
        from API import analisis_lokasi

        return analisis_lokasi(name, data), None
    except Exception:
        logger.exception("Crop recommendation failed")
        return None, "AI analysis failed. Field data was still loaded successfully."


class CrorbHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(200, {"ok": True})
            return

        static_file = STATIC_FILES.get(path)
        if static_file is None:
            self.send_error(404)
            return

        filename, content_type = static_file
        body = (ROOT / "frontend" / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/analyze", "/api/ndvi"):
            self._send_json(404, {"error": "Endpoint not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(content_length))
            location = _validate_request(payload)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return

        if path == "/api/ndvi":
            try:
                ndvi = _fetch_ndvi(location)
            except Exception:
                logger.exception("NDVI provider failed")
                self._send_json(200, {
                    "ndvi": None,
                    "error": "Sentinel-2 imagery is currently unavailable for this area.",
                })
                return
            self._send_json(200, {"ndvi": ndvi})
            return

        try:
            data, source_errors = _fetch_data(location)
            data["ndvi"] = _ndvi_summary(payload)
            recommendation, recommendation_error = _get_recommendation(location["name"], data)
        except Exception:
            logger.exception("Analyze failed")
            self._send_json(500, {"error": "Analysis failed on the server. Check the logs."})
            return

        self._send_json(200, {
            "location": location,
            "data": data,
            "source_errors": source_errors,
            "recommendation": recommendation,
            "recommendation_error": recommendation_error,
        })

    def log_message(self, format_string, *args):
        logger.info("%s - %s", self.address_string(), format_string % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), CrorbHandler)
    logger.info("Crorb is listening on port %s", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
