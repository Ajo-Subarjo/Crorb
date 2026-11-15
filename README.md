# Crorb

Crorb combines weather, soil, and elevation data to help assess a farm location and recommend suitable crops.

## Run the web app

Install the Python dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

Start the local web server from the repository root:

```powershell
.\.venv\Scripts\python.exe server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Set `PORT` to use a different local port.

The dashboard has three pages: **Field Overview**, **Weather & Climate**, and **Soil Conditions**. Analyze a location on the overview page; the results are kept for the current browser session and shown on the other pages.

On the overview page, use the satellite map to draw a field boundary. Crorb uses the bounding-box midpoint as the analysis latitude/longitude. When you analyze the field, it loads the latest suitable Sentinel-2 L2A image from Microsoft Planetary Computer and displays its NDVI results first, then collects the remaining weather, soil, and terrain data and generates the crop recommendation. If Sentinel-2 imagery is unavailable, the rest of the analysis continues.

The dashboard can display data from providers that are available. Configure `METEOMATICS_USERNAME` and `METEOMATICS_PASSWORD` for the monthly forecast, and `OPENROUTER_API_KEY` for AI crop recommendations. The data sources may take a little while to respond.
