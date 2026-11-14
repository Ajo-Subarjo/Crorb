import logging

if __package__:
    from .mpc import get_mpc_data
    from .nasa_power import get_nasa_data
    from .soils_grid import get_soil_data
    from .meteomatics import get_monthly_forecast
else:
    from mpc import get_mpc_data
    from nasa_power import get_nasa_data
    from soils_grid import get_soil_data
    from meteomatics import get_monthly_forecast

logger = logging.getLogger(__name__)


def get_data(lon, lat, start, end, errors=None, bbox=None):
    sources = {
        "mpc": lambda: get_mpc_data(lon, lat),
        "nasa_power": lambda: get_nasa_data(lon, lat, start, end),
        "soilgrids": lambda: get_soil_data(lon, lat),
        "meteomatics": lambda: get_monthly_forecast(lat=lat, lon=lon, months=6),
    }
    if bbox is not None:
        sources["ndvi"] = lambda: _get_ndvi_data(bbox)

    data = {}
    for source, fetch in sources.items():
        try:
            data[source] = fetch()
        except Exception:
            logger.exception("Data provider %s failed", source)
            data[source] = {}
            if errors is not None:
                errors[source] = "This data source is currently unavailable."

    return data


def _get_ndvi_data(bbox):
    if __package__:
        from .sentinel_ndvi import get_ndvi_data
    else:
        from sentinel_ndvi import get_ndvi_data

    return get_ndvi_data(bbox)