"""Definisi domain: rekomendasi program olahraga.

Setiap atribut punya tipe "numeric" atau "categorical". Engine RDR tidak
bergantung pada domain ini; ganti file ini untuk memakai domain lain.
"""

DOMAIN_NAME = "Rekomendasi Program Olahraga"
EXPERT_ROLE = "Personal Trainer"

DEFAULT_CONCLUSION = (
    "Latihan full-body 3x seminggu (45 menit, intensitas sedang: "
    "kombinasi kardio ringan + latihan beban dasar)"
)

ATTRIBUTES = [
    {
        "name": "usia",
        "label": "Usia",
        "type": "numeric",
        "unit": "tahun",
        "min": 10,
        "max": 90,
        "step": 1,
        "default": 25,
    },
    {
        "name": "bmi",
        "label": "BMI",
        "type": "numeric",
        "unit": "kg/m²",
        "min": 12.0,
        "max": 50.0,
        "step": 0.1,
        "default": 22.0,
    },
    {
        "name": "tujuan",
        "label": "Tujuan utama",
        "type": "categorical",
        "options": [
            "kebugaran_umum",
            "turun_berat",
            "bentuk_otot",
            "stamina",
            "fleksibilitas",
        ],
    },
    {
        "name": "level",
        "label": "Level pengalaman",
        "type": "categorical",
        "options": ["pemula", "menengah", "mahir"],
    },
    {
        "name": "hari_luang",
        "label": "Hari luang per minggu",
        "type": "numeric",
        "unit": "hari",
        "min": 1,
        "max": 7,
        "step": 1,
        "default": 3,
    },
    {
        "name": "durasi_sesi",
        "label": "Durasi per sesi",
        "type": "numeric",
        "unit": "menit",
        "min": 10,
        "max": 180,
        "step": 5,
        "default": 45,
    },
    {
        "name": "cedera",
        "label": "Riwayat cedera",
        "type": "categorical",
        "options": ["tidak_ada", "lutut", "punggung", "bahu"],
    },
    {
        "name": "fasilitas",
        "label": "Akses fasilitas",
        "type": "categorical",
        "options": ["rumah", "gym", "outdoor", "kolam_renang"],
    },
]

ATTR_BY_NAME = {a["name"]: a for a in ATTRIBUTES}
