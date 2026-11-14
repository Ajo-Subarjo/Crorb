import json
import requests

url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
params = {
    "lon": -7.557,
    "lat": 41.196,
    "property": ["phh2o", "nitrogen", "clay", "silt", "sand", "soc"],
    "depth": ["0-5cm", "5-15cm"],
    "value": ["mean"],
}

response = requests.get(url, params=params)
data = response.json()

# print(json.dumps(data, indent=4))

try:
  layers = data.get("properties", {}).get("layers", [])
  for layer in layers:
    prop_name = layer.get("name")
    unit = layer.get("unit_measure", {}).get("mapped_value_unit", "")
    print(f"\nParameter: {prop_name} ({unit})")

    for depth in layer.get("depths", []):
      depth_label = depth.get("label")
      mean_val = depth.get("values", {}).get("mean")
      print(f"  - Kedalaman {depth_label}: {mean_val}")
except Exception as e:
  print("faoled data structure:", e)