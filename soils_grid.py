import requests

PROPERTIES = ["phh2o", "nitrogen", "clay", "silt", "sand", "soc"]
DEPTHS = ["0-5cm", "5-15cm"]


def get_soil_data(lon, lat):
    # full structure, every value null until filled
    result = {p: {d: None for d in DEPTHS} for p in PROPERTIES}

    try:
        response = requests.get(
            "https://rest.isric.org/soilgrids/v2.0/properties/query",
            params={
                "lon": lon,
                "lat": lat,
                "property": PROPERTIES,
                "depth": DEPTHS,
                "value": ["mean"],
            },
            timeout=30,
        )
        response.raise_for_status()

        for layer in response.json().get("properties", {}).get("layers", []):
            name = layer.get("name")
            if name not in result:
                continue
            for depth in layer.get("depths", []):
                label = depth.get("label")
                if label in result[name]:
                    result[name][label] = (depth.get("values") or {}).get("mean")

    except (requests.RequestException, ValueError, TypeError) as e:
        print(f"SoilGrids error: {e}")

    return result


if __name__ == "__main__":
    print(get_soil_data(lon=-7.557, lat=41.196))