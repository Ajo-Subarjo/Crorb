import planetary_computer
import pystac_client
import rioxarray
import xrspatial

# 1. Hubungkan ke STAC Catalog Microsoft Planetary Computer
catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

# 2. Cari data DEM (Contoh: Copernicus DEM 30m di sekitar Grand Canyon)
point_of_interest = [-112.15, 36.05]  # [Longitude, Latitude]
search = catalog.search(
    collections=["cop-dem-glo-30"],
    intersects={"type": "Point", "coordinates": point_of_interest},
)

items = list(search.get_items())
print(f"Ditemukan {len(items)} file tile DEM.")

# 3. Ambil link aset bertanda tangan (signed asset) dan baca pakai rioxarray
signed_asset = planetary_computer.sign(items[0].assets["data"])
dem_data = (
    rioxarray.open_rasterio(signed_asset.href).squeeze().drop_bars()
    if hasattr(rioxarray.open_rasterio(signed_asset.href).squeeze(), "drop_bars")
    else rioxarray.open_rasterio(signed_asset.href).squeeze().drop("band")
)

# 4. Hitung Slope (Kemiringan Lereng) secara otomatis pakai xarray-spatial
slope_data = xrspatial.slope(dem_data)

print("Elevasi dan Slope berhasil diekstrak!")
print(f"Rentang Elevasi: {dem_data.min().item():.1f} hingga {dem_data.max().item():.1f} meter")
print(f"Rentang Slope: {slope_data.min().item():.1f} hingga {slope_data.max().item():.1f} derajat")