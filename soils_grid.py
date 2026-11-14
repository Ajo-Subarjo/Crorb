import requests

def get_soil_data(lon, lat):
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"

    params = {
        "lon": lon,
        "lat": lat,
        "property": ["phh2o", "nitrogen", "clay", "silt", "sand", "soc"],
        "depth": ["0-5cm", "5-15cm"],
        "value": ["mean"],
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        result = {}

        layers = data.get("properties", {}).get("layers", [])

        for layer in layers:
            prop_name = layer.get("name")
            depths = layer.get("depths", [])

            result[prop_name] = {}

            for depth in depths:
                depth_label = depth.get("label")
                mean_val = depth.get("values", {}).get("mean")

                result[prop_name][depth_label] = mean_val

        return result

    except requests.RequestException as e:
        print(f"SoilGrids API error: {e}")
        return {}

    except (ValueError, TypeError) as e:
        print(f"Data processing error: {e}")
        return {}




if __name__ == "__main__":
    soil_data = get_soil_data(lon=-7.557, lat=41.196)
    print(soil_data)