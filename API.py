import os, json, re
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL   = "nvidia/nemotron-3.5-super-vl:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY or os.getenv("OPEN_ROUTER"),
    default_headers={
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Crop Recommendations",
    },
)

SYSTEM_PROMPT = """You are an agronomist.
You receive a summary of one field's data, separated into:
- "iklim_historis": historical monthly NASA POWER data, including soil wetness
- "prakiraan_mendatang": Meteomatics monthly forecast data for the coming months
- "topografi": elevation (meters above sea level) and slope (degrees)
- "tanah": soil texture, pH, organic matter, and nitrogen
- "data_tidak_tersedia": parameters with missing values

Rules:
1. Never invent parameters listed in "data_tidak_tersedia". State that the data
   is unavailable and explain how this affects the recommendation.
2. Make a recommendation by comparing historical patterns, the upcoming forecast,
   and the latest Sentinel-2 NDVI as an indicator of current vegetation.
   Use forecast rainfall, water balance, temperature, and humidity to assess
   growing-season suitability, and use historical soil wetness as context.
   If both data sources are available, mention historical and forecast findings in "alasan".
3. Meteomatics forecasts do NOT currently provide soil wetness measurements.
   Do not treat forecast rainfall or water balance as soil wetness, and do not
   invent future soil-wetness values. Explain this limitation when relevant.
4. NDVI measures vegetation greenness in imagery; it does not identify crop types
   or guarantee yields. Use it only as supporting context.
5. Clearly distinguish historical conditions, satellite imagery, and forecasts.
   A forecast is an estimate, not an observation or certainty.
6. Slopes above 15 degrees require terracing; slopes above 30 degrees are not
   suitable for annual crops.
7. Reply ONLY with valid JSON in this structure:
{
  "tanaman_utama": "crop name",
  "alternatif": ["crop 1", "crop 2"],
  "skor_kecocokan": 0-100,
  "alasan": "a brief explanation in clear, simple English",
  "catatan_data": "missing data and its impact"
}
Write all natural-language values in clear, simple English."""


def _extract_json(teks: str) -> dict:
    """Handle responses wrapped in prose or a code fence."""
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", teks, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _angka(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _rata(nilai) -> float | None:
    nilai = [v for v in nilai if _angka(v)]
    return round(sum(nilai) / len(nilai), 2) if nilai else None


def _ringkas_data(data: dict) -> dict:
    """Summarize historical and forecast data for agronomic analysis."""
    mpc  = data.get("mpc") or {}
    nasa = data.get("nasa_power") or {}
    sg   = data.get("soilgrids") or {}
    meteomatics = data.get("meteomatics") or {}
    ndvi = data.get("ndvi") or {}

    # "202513" is NASA POWER's annual aggregate; other entries are monthly.
    bulanan = {k: v for k, v in nasa.items() if len(k) == 6 and not k.endswith("13")}
    tahunan = next((v for k, v in nasa.items() if k.endswith("13")), {})

    suhu         = _rata(v.get("temperature")  for v in bulanan.values())
    lembap       = _rata(v.get("humidity")     for v in bulanan.values())
    hujan_harian = _rata(v.get("rainfall")     for v in bulanan.values())
    wetness      = _rata(v.get("soil_wetness") for v in bulanan.values())

    hujan_bulanan = round(hujan_harian * 30.44, 1) if hujan_harian is not None else None
    hujan_tahunan = round(hujan_harian * 365.25, 1) if hujan_harian is not None else None
    if hujan_tahunan is None and _angka(tahunan.get("rainfall")):
        hujan_tahunan = round(tahunan["rainfall"] * 365.25, 1)

    historis_bulanan = {
        bulan: {
            "suhu_c": nilai.get("temperature"),
            "kelembapan_udara_persen": nilai.get("humidity"),
            "curah_hujan_mm_per_hari": nilai.get("rainfall"),
            "soil_wetness_top_layer": nilai.get("soil_wetness"),
            "radiasi_matahari": nilai.get("solar_radiation"),
        }
        for bulan, nilai in sorted(bulanan.items())
    }

    prakiraan_bulanan = {
        bulan: {
            field: nilai.get(field)
            for field in (
                "rainfall_mm",
                "evaporation_mm",
                "water_balance_mm",
                "temp_max_c",
                "temp_min_c",
                "humidity_pct",
                "wind_kmh",
                "solar_wh_m2_day",
            )
            if _angka(nilai.get(field))
        }
        for bulan, nilai in sorted(meteomatics.items())
        if isinstance(nilai, dict)
    }

    def per_lapisan(field):
        d = sg.get(field) or {}
        return {lap: d.get(lap) for lap in ("0-5cm", "5-15cm")}

    def rata_lapisan(field):
        return _rata((sg.get(field) or {}).values())

    tanah = {
        "clay_persen": rata_lapisan("clay"),
        "sand_persen": rata_lapisan("sand"),
        "silt_persen": rata_lapisan("silt"),
        "ph":          rata_lapisan("phh2o"),
        "soc":         rata_lapisan("soc"),
        "nitrogen":    rata_lapisan("nitrogen"),
        "per_lapisan": {f: per_lapisan(f) for f in
                        ("clay", "sand", "silt", "phh2o", "soc", "nitrogen")},
    }

    ringkas = {
        "topografi": {
            "elevasi_m":          mpc.get("elevation"),
            "elevasi_min_m":      mpc.get("elevation_min"),
            "elevasi_max_m":      mpc.get("elevation_max"),
            "lereng_derajat":     mpc.get("slope"),
            "lereng_min_derajat": mpc.get("slope_min"),
            "lereng_max_derajat": mpc.get("slope_max"),
        },
        "iklim_historis": {
            "suhu_rata2_c":              suhu,
            "kelembapan_rata2_persen":   lembap,
            "curah_hujan_mm_per_hari":   hujan_harian,
            "curah_hujan_mm_per_bulan":  hujan_bulanan,
            "curah_hujan_mm_per_tahun":  hujan_tahunan,
            "soil_wetness_rata2":        wetness,
            "bulan_tersedia":            sorted(bulanan),
            "data_bulanan":              historis_bulanan,
        },
        "prakiraan_mendatang": {
            "sumber": "Meteomatics",
            "soil_wetness_langsung": None,
            "data_bulanan": prakiraan_bulanan,
        },
        "vegetasi_satelit": {
            "sumber": "Sentinel-2",
            "tanggal_citra": ndvi.get("scene_date"),
            "ndvi_rata2": ndvi.get("mean"),
            "ndvi_median": ndvi.get("median"),
            "tutupan_awan_persen": ndvi.get("cloud_cover_pct"),
        },
        "tanah": tanah,
    }

    kosong = [f"{bagian}.{k}" for bagian in ("topografi", "iklim_historis")
              for k, v in ringkas[bagian].items() if v is None]
    kosong += [f"tanah.{k}" for k, v in tanah.items()
               if k != "per_lapisan" and v is None]
    if not prakiraan_bulanan:
        kosong.append("prakiraan_mendatang.data_bulanan")
    kosong.append("prakiraan_mendatang.soil_wetness_langsung")
    if ndvi.get("mean") is None:
        kosong.append("vegetasi_satelit.ndvi_rata2")
    ringkas["data_tidak_tersedia"] = kosong
    return ringkas


def analisis_lokasi(nama_lokasi: str, data: dict) -> dict:
    """Analyze raw topography, historical climate, soil, and forecast data."""
    payload = {"nama_lokasi": nama_lokasi, "data": _ringkas_data(data)}

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
        max_tokens=15000,
    )
    return _extract_json(resp.choices[0].message.content)


def ranking_lokasi(daftar_lokasi: list) -> dict:
    """Rank locations supplied as [{"nama_lokasi": "...", "data": {...}}, ...]."""
    ringkas = [
        {"nama_lokasi": l["nama_lokasi"], "data": _ringkas_data(l["data"])}
        for l in daftar_lokasi
    ]
    prompt = (
        "Here is a summary of data for several locations (JSON array). "
        "Rank them from most to least suitable for farming. "
        "Compare historical NASA POWER climate data with the upcoming Meteomatics forecast. "
        "Consider historical soil wetness, forecast rainfall and water balance, "
        "slope, elevation, and note any missing data. Do not invent forecast soil wetness "
        "because Meteomatics does not provide it. "
        'Reply ONLY with JSON: {"ranking":[{"nama_lokasi":"...","tanaman_terbaik":"...",'
        '"skor":0-100,"catatan":"brief reason"}]} — sort by highest score first.\n\n'
        + json.dumps(ringkas, ensure_ascii=False)
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=100000,
    )
    return _extract_json(resp.choices[0].message.content)


if __name__ == "__main__":
    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)

    hasil = analisis_lokasi("Lahan A", data)
    print(json.dumps(hasil, indent=2, ensure_ascii=False))