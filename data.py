import json

from mpc import get_mpc_data
from nasa_power import get_nasa_data
from soils_grid import get_soil_data


def get_data(lon, lat, start, end):

    data = {
        "mpc": get_mpc_data(lon, lat),
        "nasa_power": get_nasa_data(lon, lat, start, end),
        "soilgrids": get_soil_data(lon, lat)
    }

    return data


result = get_data(
    lon=106.8456,
    lat=-6.2088,
    start="2025",
    end="2025"
)
with open("farm_data.json", "w") as file:
    json.dump(result, file, indent=4)

print(json.dumps(result, indent=4))
