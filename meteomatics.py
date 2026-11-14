import os
import dotenv
import calendar
import requests
from datetime import datetime, timezone
from collections import defaultdict
from statistics import mean

dotenv.load_dotenv()


MODEL = "ecmwf-mmsf"


PARAMS = {
    "precip_24h:mm": "rainfall",
    "evaporation_24h:mm": "evaporation",
    "t_max_2m_24h:C": "temp_max",
    "t_min_2m_24h:C": "temp_min",
    "relative_humidity_2m:p": "humidity",
    "wind_speed_10m:kmh": "wind_speed",
    "global_rad_24h:Wh": "solar_radiation",
}


def get_monthly_forecast(lat, lon, months=6):
    auth = (os.getenv("METEOMATICS_USERNAME"), os.getenv("METEOMATICS_PASSWORD"))

    now = datetime.now(timezone.utc)
    n = now.year * 12 + now.month - 1
    sy, sm = divmod(n + 1, 12)
    ey, em = divmod(n + months, 12)
    start = datetime(sy, sm + 1, 1, 12)
    end = datetime(ey, em + 1, calendar.monthrange(ey, em + 1)[1], 12)

    url = (
        f"https://api.meteomatics.com/{start:%Y-%m-%dT%H:%M:%SZ}--{end:%Y-%m-%dT%H:%M:%SZ}:PT24H/"
        f"{','.join(PARAMS)}/{lat},{lon}/json"
    )
    r = requests.get(url, params={"source": MODEL, "ens_select": "mean"}, auth=auth, timeout=180)
    r.raise_for_status()

    days = defaultdict(dict)
    for p in r.json()["data"]:
        key = next(k for k in PARAMS if p["parameter"].startswith(k))
        for d in p["coordinates"][0]["dates"]:
            if d["value"] != -999:
                days[d["date"]][PARAMS[key]] = d["value"]

    by_month = defaultdict(list)
    for date, v in sorted(days.items()):
        by_month[date[:7]].append(v)

    def vals(rows, name):
        return [r[name] for r in rows if name in r]

    result = {}
    for month, rows in by_month.items():
        rain = sum(vals(rows, "rainfall"))
        evap = -sum(vals(rows, "evaporation"))
        result[month] = {
            "rainfall_mm": round(rain, 2),
            "evaporation_mm": round(evap, 2),
            "water_balance_mm": round(rain - evap, 2),
            "temp_max_c": round(max(vals(rows, "temp_max")), 2),
            "temp_min_c": round(min(vals(rows, "temp_min")), 2),
            "humidity_pct": round(mean(vals(rows, "humidity")), 2),
            "wind_kmh": round(mean(vals(rows, "wind_speed")), 2),
            "solar_wh_m2_day": round(mean(vals(rows, "solar_radiation")), 2),
            "days": len(rows),
        }
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(get_monthly_forecast(-6.9175, 106.9242), indent=2))