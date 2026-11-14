import base64
import io
from datetime import datetime, timedelta, timezone

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT


STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
IMAGE_SIZE = 512
COLOR_STOPS = np.array([-0.2, -0.05, 0.1, 0.25, 0.4, 0.6, 0.8], dtype=np.float32)
NDVI_COLORS = np.array([
    [61, 93, 156],
    [153, 183, 199],
    [221, 213, 171],
    [223, 199, 110],
    [160, 190, 100],
    [76, 145, 78],
    [29, 103, 58],
], dtype=np.uint8)


def _read_asset(asset, bbox, resampling):
    href = planetary_computer.sign(asset).href
    transform = from_bounds(*bbox, IMAGE_SIZE, IMAGE_SIZE)
    with rasterio.open(href) as source:
        with WarpedVRT(
            source,
            crs="EPSG:4326",
            transform=transform,
            width=IMAGE_SIZE,
            height=IMAGE_SIZE,
            resampling=resampling,
        ) as virtual:
            return virtual.read(1, masked=True).astype(np.float32).filled(np.nan)


def _render_thumbnail(ndvi, valid):
    import PIL.Image

    rgb = np.stack([
        np.interp(ndvi, COLOR_STOPS, NDVI_COLORS[:, channel])
        for channel in range(3)
    ], axis=-1).astype(np.uint8)
    rgba = np.dstack((rgb, np.where(valid, 255, 0).astype(np.uint8)))
    output = io.BytesIO()
    PIL.Image.fromarray(rgba, mode="RGBA").save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def get_ndvi_data(bbox):
    west, south, east, north = bbox
    now = datetime.now(timezone.utc)
    search = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    items = list(search.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{(now - timedelta(days=180)):%Y-%m-%d}/{now:%Y-%m-%d}",
        query={"eo:cloud_cover": {"lt": 60}},
        max_items=20,
        sortby=[{"field": "properties.datetime", "direction": "desc"}],
    ).items())
    if not items:
        raise RuntimeError("No matching Sentinel-2 imagery was found for this area and date range.")

    item = items[0]
    red = _read_asset(item.assets["B04"], bbox, Resampling.bilinear)
    nir = _read_asset(item.assets["B08"], bbox, Resampling.bilinear)
    denominator = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (denominator > 0)
    scl_asset = item.assets.get("SCL")
    if scl_asset is not None:
        scene_class = _read_asset(scl_asset, bbox, Resampling.nearest)
        valid &= np.isfinite(scene_class) & ~np.isin(scene_class, [0, 1, 3, 7, 8, 9, 10, 11])

    ndvi = np.full((IMAGE_SIZE, IMAGE_SIZE), np.nan, dtype=np.float32)
    ndvi[valid] = (nir[valid] - red[valid]) / denominator[valid]
    valid &= np.isfinite(ndvi)
    if not valid.any():
        raise RuntimeError("No cloud-free pixels are available to calculate NDVI for this scene.")

    values = ndvi[valid]
    scene_datetime = item.properties.get("datetime")
    return {
        "scene_date": scene_datetime[:10] if scene_datetime else item.id,
        "cloud_cover_pct": item.properties.get("eo:cloud_cover"),
        "mean": round(float(values.mean()), 3),
        "median": round(float(np.median(values)), 3),
        "min": round(float(values.min()), 3),
        "max": round(float(values.max()), 3),
        "valid_pixels": int(valid.sum()),
        "bbox": [west, south, east, north],
        "thumbnail": _render_thumbnail(np.where(valid, ndvi, COLOR_STOPS[0]), valid),
    }
