import os, json, re
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

API_KEY = os.environ.get("OPENROUTER_API_KEY")   # JANGAN hardcode di kode!
MODEL   = "nvidia/nemotron-3.5-super-vl:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPEN_ROUTER"),
    default_headers={
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Rekomendasi Tanam",
    },
)

SYSTEM_PROMPT = """Kamu adalah ahli agronomi Indonesia.
Kamu menerima ringkasan data satu lahan dalam format JSON dengan bagian:
- "topografi": elevasi (m dpl) dan lereng (derajat)
- "iklim": suhu, kelembapan, curah hujan (harian/bulanan/tahunan), soil wetness
- "tanah": tekstur (clay/sand/silt %), pH, bahan organik (soc), nitrogen
- "data_tidak_tersedia": daftar parameter yang nilainya kosong

Aturan:
1. Parameter yang ada di "data_tidak_tersedia" TIDAK BOLEH dikarang. Sebutkan
   bahwa datanya belum tersedia dan jelaskan dampaknya pada rekomendasi.
2. Lereng > 15 derajat perlu terasering; > 30 derajat tidak cocok untuk
   tanaman semusim.
3. Balas HANYA JSON valid dengan struktur:
{
  "tanaman_utama": "nama tanaman",
  "alternatif": ["tanaman1", "tanaman2"],
  "skor_kecocokan": 0-100,
  "alasan": "penjelasan singkat dengan bahasa sederhana",
  "catatan_data": "data apa yang kurang dan pengaruhnya"
}
Gunakan bahasa Indonesia yang mudah dipahami petani."""


def _extract_json(teks: str) -> dict:
    """Jaga-jaga kalau model membungkus JSON dengan teks/code fence."""
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
    """Ubah payload mentah (mpc + nasa_power + soilgrids) jadi ringkasan
    yang ringkas dan aman dibaca model."""
    mpc  = data.get("mpc") or {}
    nasa = data.get("nasa_power") or {}
    sg   = data.get("soilgrids") or {}

    # "202513" = agregat tahunan NASA POWER, sisanya bulanan
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
        "iklim": {
            "suhu_rata2_c":              suhu,
            "kelembapan_rata2_persen":   lembap,
            "curah_hujan_mm_per_hari":   hujan_harian,
            "curah_hujan_mm_per_bulan":  hujan_bulanan,
            "curah_hujan_mm_per_tahun":  hujan_tahunan,
            "soil_wetness_rata2":        wetness,
            "bulan_tersedia":            sorted(bulanan),
        },
        "tanah": tanah,
    }

    kosong = [f"{bagian}.{k}" for bagian in ("topografi", "iklim")
              for k, v in ringkas[bagian].items() if v is None]
    kosong += [f"tanah.{k}" for k, v in tanah.items()
               if k != "per_lapisan" and v is None]
    ringkas["data_tidak_tersedia"] = kosong
    return ringkas


def analisis_lokasi(nama_lokasi: str, data: dict) -> dict:
    """data = payload mentah: {"mpc": {...}, "nasa_power": {...}, "soilgrids": {...}}"""
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
    """daftar_lokasi = [{"nama_lokasi": "...", "data": {...payload mentah...}}, ...]"""
    ringkas = [
        {"nama_lokasi": l["nama_lokasi"], "data": _ringkas_data(l["data"])}
        for l in daftar_lokasi
    ]
    prompt = (
        "Berikut ringkasan data beberapa lokasi (JSON array). "
        "Urutkan dari lokasi yang PALING BAGUS untuk ditanami. "
        "Perhatikan lereng, elevasi, dan lengkapi catatan bila ada data yang kosong. "
        'Balas HANYA JSON: {"ranking":[{"nama_lokasi":"...","tanaman_terbaik":"...",'
        '"skor":0-100,"catatan":"alasan singkat"}]} — urut skor tertinggi dulu.\n\n'
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