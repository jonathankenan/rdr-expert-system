"""Mensimulasikan sesi pakar dari KB kosong dan menyimpan hasilnya ke examples/kb_demo.json.

Jalankan: python examples/build_demo_kb.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rdr import Condition, KnowledgeBase  # noqa: E402
from rdr.schema import ATTRIBUTES, DEFAULT_CONCLUSION  # noqa: E402

BASE = {
    "usia": 25, "bmi": 22.0, "tujuan": "kebugaran_umum", "level": "pemula",
    "hari_luang": 3, "durasi_sesi": 45, "cedera": "tidak_ada", "fasilitas": "gym",
}

# (kasus, kesimpulan pakar atau None jika setuju, kondisi yang dipilih pakar)
SESSIONS = [
    (
        {"usia": 35, "bmi": 32.5, "tujuan": "turun_berat", "fasilitas": "outdoor"},
        "Kardio low-impact (jalan cepat / sepeda statis) 5x seminggu 30–45 menit + latihan beban ringan 2x",
        [Condition("bmi", ">=", 30.0)],
    ),
    (
        {"usia": 40, "bmi": 33.0, "tujuan": "turun_berat", "cedera": "lutut", "fasilitas": "kolam_renang"},
        "Renang / aqua jogging 4x seminggu + penguatan otot paha tanpa beban (isometrik)",
        [Condition("cedera", "==", "lutut")],
    ),
    (
        {"usia": 65, "bmi": 24.0},
        "Jalan kaki 30 menit 5x seminggu + latihan keseimbangan & stretching (tai chi / yoga ringan)",
        [Condition("usia", ">=", 60)],
    ),
    (
        {"usia": 22, "bmi": 23.0, "tujuan": "bentuk_otot", "level": "menengah", "hari_luang": 4, "durasi_sesi": 60},
        "Split upper/lower 4x seminggu, progressive overload 8–12 repetisi",
        [Condition("tujuan", "==", "bentuk_otot")],
    ),
    (
        {"usia": 20, "bmi": 21.0, "tujuan": "bentuk_otot", "level": "pemula", "hari_luang": 3, "fasilitas": "rumah"},
        "Full-body bodyweight 3x seminggu (push-up, squat, plank) + resistance band",
        [Condition("fasilitas", "==", "rumah")],
    ),
    (
        {"usia": 28, "bmi": 22.5, "tujuan": "stamina", "level": "menengah", "hari_luang": 5, "fasilitas": "outdoor"},
        "Lari interval 2x + lari santai 2x + long run 1x seminggu (program 5K→10K)",
        [Condition("tujuan", "==", "stamina")],
    ),
    (
        {"usia": 30, "bmi": 23.0, "tujuan": "stamina", "level": "menengah", "hari_luang": 4,
         "cedera": "lutut", "fasilitas": "kolam_renang"},
        "Renang interval 3x seminggu + sepeda statis 1x (tanpa benturan pada lutut)",
        [Condition("cedera", "==", "lutut")],
    ),
    # pakar setuju dengan kesimpulan sistem
    ({"usia": 27, "bmi": 22.0, "tujuan": "kebugaran_umum", "hari_luang": 3}, None, []),
    ({"usia": 70, "bmi": 26.0, "tujuan": "kebugaran_umum"}, None, []),
]


def main() -> None:
    kb = KnowledgeBase(DEFAULT_CONCLUSION)
    for i, (partial, expert_conclusion, conditions) in enumerate(SESSIONS, 1):
        case = {**BASE, **partial}
        result = kb.infer(case)
        print(f"\n=== Kasus {i}: {partial}")
        print(f"Sistem  : {result.conclusion} (Rule #{result.fired_node_id})")
        if expert_conclusion is None:
            print("Pakar   : setuju")
            kb.log(case, result.conclusion, result.conclusion, True)
            continue
        diffs = kb.difference_list(case, kb.cornerstone_for(result), ATTRIBUTES)
        print(f"Pakar   : tidak setuju -> {expert_conclusion}")
        print(f"Daftar perbedaan: {[str(d) for d in diffs]}")
        node = kb.add_rule(case, expert_conclusion, conditions)
        kb.log(case, result.conclusion, expert_conclusion, False, node.id)
        print(f"Rule baru (#{node.id}, {kb.side_of(node.id)}-child dari #{node.parent}): {node.to_text()}")

    out = ROOT / "examples" / "kb_demo.json"
    kb.save(out)
    print(f"\nKB disimpan ke {out} ({len(kb.nodes)} rule)")


if __name__ == "__main__":
    main()
