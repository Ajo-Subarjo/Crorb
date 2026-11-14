import requests

url = "https://power.larc.nasa.gov/api/temporal/daily/point"

params = {
    "parameters": "T2M,RH2M,GWETTOP,PRECTOTCORR",  
    "community": "AG",
    "longitude": 106.8456,
    "latitude": -6.2088,
    "start": "20250101",
    "end": "20250112",
    "format": "JSON"
}

response = requests.get(url, params=params)
response.raise_for_status()
data = response.json()

# Extract the parameter container dict
parameters_data = data["properties"]["parameter"]

# Use T2M keys as our date reference list
dates = list(parameters_data["T2M"].keys())

# Print a neat header
print(f"{'Date':<10} | {'Temp (°C)':<10} | {'Humidity (%)':<12} | {'Soil Wetness':<14} | {'Precip (mm)':<12}")
print("-" * 65)

for date in dates:
    t2m = parameters_data["T2M"].get(date, -999)
    rh2m = parameters_data["RH2M"].get(date, -999)
    gwettop = parameters_data["GWETTOP"].get(date, -999)
    prectot = parameters_data["PRECTOTCORR"].get(date, -999)

    # Convert -999 (NASA's missing flag) to a readable string
    t2m_str = f"{t2m:.2f}" if t2m != -999 else "N/A"
    rh2m_str = f"{rh2m:.2f}" if rh2m != -999 else "N/A"
    gwettop_str = f"{gwettop:.4f}" if gwettop != -999 else "N/A"
    prectot_str = f"{prectot:.2f}" if prectot != -999 else "N/A"

    print(f"{date:<10} | {t2m_str:<10} | {rh2m_str:<12} | {gwettop_str:<14} | {prectot_str:<12}")