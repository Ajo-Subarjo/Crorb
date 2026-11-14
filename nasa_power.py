import requests

PARAMS = {
    "T2M": "temperature",
    "RH2M": "humidity",
    "GWETTOP": "soil_wetness",
    "PRECTOTCORR": "rainfall",
    "ALLSKY_SFC_SW_DWN": "solar_radiation",
}

def get_nasa_data(lon, lat, start, end):
    url = "https://power.larc.nasa.gov/api/temporal/monthly/point"

    params = {
        "parameters": ",".join(PARAMS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }

    try:
        response = requests.get(url, params=params, timeout=30)

        if not response.ok:
            print(f"NASA POWER API Error: {response.status_code}")
            print(response.text)
            return {}

        series = response.json()["properties"]["parameter"]

        result = {}
        for date in series["T2M"]:
            result[date] = {
                name: (None if series[code].get(date) == -999 else series[code].get(date))
                for code, name in PARAMS.items()
            }

        return result

    except requests.RequestException as e:
        print(f"NASA POWER API error: {e}")
        return {}

    except (KeyError, ValueError, TypeError) as e:
        print(f"Data processing error: {e}")
        return {}


if __name__ == "__main__":
    print(get_nasa_data(lon=106.8456, lat=-6.2088, start="2025", end="2025"))