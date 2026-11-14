from .mpc import get_mpc_data
from .nasa_power import get_nasa_data
from .soils_grid import get_soil_data
from .meteomatics import get_monthly_forecast


def get_data(lon, lat, start, end):
    return {
        "mpc": get_mpc_data(lon, lat),
        "nasa_power": get_nasa_data(lon, lat, start, end),
        "soilgrids": get_soil_data(lon, lat),
        "meteomatics": get_monthly_forecast(
            lat=lat,
            lon=lon,
            months=6
        )
    }