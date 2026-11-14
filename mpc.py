import warnings
warnings.filterwarnings("ignore")

import planetary_computer
import pystac_client
import rioxarray
import xrspatial
from pyproj import Transformer
from rasterio.enums import Resampling


def get_mpc_data(lon, lat, buffer_deg=0.02, radius_m=500):
    try:
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )

        items = list(catalog.search(
            collections=["nasadem"],
            intersects={"type": "Point", "coordinates": [lon, lat]},
        ).items())

        if not items:
            print("No DEM data found.")
            return {}

        href = planetary_computer.sign(items[0].assets["elevation"]).href

        with rioxarray.open_rasterio(href, masked=True) as da:
            dem = da.squeeze(drop=True).rio.clip_box(
                minx=lon - buffer_deg, miny=lat - buffer_deg,
                maxx=lon + buffer_deg, maxy=lat + buffer_deg,
            ).load()

        elevation = float(dem.sel(x=lon, y=lat, method="nearest").item())

        # Reproject to local UTM (meters) so x/y/z units match
        utm = dem.rio.estimate_utm_crs()
        dem_m = dem.rio.reproject(utm, resolution=30, resampling=Resampling.bilinear)

        slope = xrspatial.slope(dem_m)  # degrees

        # Crop to a window around the point (drops reprojection/edge NaNs)
        cx, cy = Transformer.from_crs("EPSG:4326", utm, always_xy=True).transform(lon, lat)
        dem_c = dem_m.rio.clip_box(cx - radius_m, cy - radius_m, cx + radius_m, cy + radius_m)
        slope_c = slope.rio.clip_box(cx - radius_m, cy - radius_m, cx + radius_m, cy + radius_m)

        return {
            "elevation": elevation,
            "elevation_min": float(dem_c.min().item()),
            "elevation_max": float(dem_c.max().item()),
            "slope": float(slope_c.mean().item()),
            "slope_min": float(slope_c.min().item()),
            "slope_max": float(slope_c.max().item()),
        }

    except Exception as e:
        print(f"Planetary Computer API error: {e}")
        return {}


if __name__ == "__main__":
    print(get_mpc_data(lon=106.8456, lat=-6.2088))