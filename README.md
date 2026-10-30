# RDR Expert System: Rekomendasi Program Olahraga

Sistem pakar berbasis **Ripple Down Rules (RDR)** untuk tugas IF4070 Knowledge Representation and Reasoning.
Seorang pakar (*personal trainer*) memakai sistem ini untuk memberi rekomendasi program olahraga
kepada konsumennya. Basis pengetahuan dibangun **bertahap** oleh pakar, langsung dari kasus-kasus nyata.

## Menjalankan

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Aplikasi terbuka di http://localhost:8501. Menjalankan unit test:

```bash
.venv/bin/python -m pytest -q
```

Simulasi sesi pakar lewat CLI (sekaligus membangun `examples/kb_demo.json`):

```bash
.venv/bin/python examples/build_demo_kb.py
```

## Cara kerja

### Basis pengetahuan awal
KB hanya berisi **Rule #0**: `IF true THEN Latihan full-body 3x seminggu (...)`.
Kesimpulan default ini bisa diganti lewat menu **Reset KB ke Rule 0** di sidebar.

### Struktur pohon biner
Setiap node berisi satu rule `IF <kondisi> THEN <kesimpulan> BECAUSE OF <kasus kunci>`.

| Cabang | Kapan dievaluasi | Makna |
|---|---|---|
| **true-child** (anak kanan) | kondisi node **terpenuhi** | perkecualian dari rule tersebut |
| **false-child** (anak kiri) | kondisi node **tidak terpenuhi** | alternatif berikutnya |

### Inferensi
1. Mulai dari root. Rule #0 selalu terpenuhi.
2. Jika kondisi node terpenuhi, kesimpulannya dicatat sebagai *kesimpulan sementara*, lalu inferensi lanjut ke true-child.
   Jika tidak terpenuhi, inferensi lanjut ke false-child.
3. Inferensi berhenti ketika anak yang dituju kosong.
4. **Kesimpulan akhir = kesimpulan rule terakhir yang terpenuhi.** Kesimpulan sebelumnya dianulir oleh yang lebih baru.

### Akuisisi pengetahuan
- **Pakar setuju**: rekomendasi diberikan dan proses selesai. Kasus dicatat di riwayat.
- **Pakar tidak setuju**:
  1. Pakar memilih atau menulis kesimpulan yang benar.
  2. Sistem menampilkan perbandingan kasus baru dengan **kasus kunci** dari rule terakhir yang terpenuhi,
     lalu membuat **daftar perbedaan**, yaitu kondisi yang *dipenuhi kasus baru dan tidak dipenuhi kasus kunci*.
     - Atribut kategorikal: `attr == nilai_baru` dan `attr != nilai_kunci`.
     - Atribut numerik: `attr > nilai_kunci` atau `attr < nilai_kunci`. Pakar boleh menggeser ambangnya
       (misal `bmi > 30`), selama tetap memisahkan kedua kasus. Sistem memvalidasi hal ini.
     - Jika rule terakhir adalah Rule #0 (tanpa kasus kunci), semua kondisi yang dipenuhi kasus baru boleh dipilih.
  3. Rule baru dipasang di **posisi kosong tempat inferensi berhenti**:
     - sebagai true-child, jika rule terakhir yang dievaluasi terpenuhi;
     - sebagai false-child, jika rule terakhir yang dievaluasi tidak terpenuhi.

     Kasus baru menjadi kasus kunci rule tersebut. Dengan begitu, semua kasus kunci lama tetap
     menghasilkan kesimpulan yang sama.

### Atribut domain (`rdr/schema.py`)

| Atribut | Tipe | Nilai |
|---|---|---|
| usia | numerik | 10–90 tahun |
| bmi | numerik | 12–50 kg/m² (ada kalkulator BMI di UI) |
| tujuan | kategorikal | kebugaran_umum, turun_berat, bentuk_otot, stamina, fleksibilitas |
| level | kategorikal | pemula, menengah, mahir |
| hari_luang | numerik | 1–7 hari/minggu |
| durasi_sesi | numerik | 10–180 menit |
| cedera | kategorikal | tidak_ada, lutut, punggung, bahu |
| fasilitas | kategorikal | rumah, gym, outdoor, kolam_renang |

Untuk memakai domain lain, cukup ubah `rdr/schema.py`. Engine tidak bergantung pada domain.

## Fitur UI
- **Konsultasi**: input kasus, rekomendasi beserta jalur inferensi, tombol setuju/tidak setuju,
  form akuisisi rule baru, dan pratinjau posisi rule baru pada pohon.
- **Pohon RDR**: visualisasi pohon biner (kiri/merah = false, kanan/hijau = true), dengan jalur konsultasi terakhir disorot.
- **Daftar Rule**: seluruh rule dalam format `IF … THEN … BECAUSE OF […]`.
- **Riwayat Kasus**: setiap kasus beserta kesimpulan sistem, kesimpulan final, dan rule yang ditambahkan.
- Sidebar: unduh/muat KB (JSON), muat KB contoh, dan reset KB.

KB tersimpan otomatis di `kb.json` (tidak di-commit).

## Contoh pohon hasil simulasi (`examples/kb_demo.json`)

```
Rule #0  IF true → Latihan full-body 3x seminggu
└─ true:  Rule #1  IF bmi >= 30 → Kardio low-impact
          ├─ true:  Rule #2  IF cedera == lutut → Renang / aqua jogging
          └─ false: Rule #3  IF usia >= 60 → Jalan kaki + keseimbangan & stretching
                    └─ false: Rule #4  IF tujuan == bentuk_otot → Split upper/lower 4x
                              ├─ true:  Rule #5  IF fasilitas == rumah → Full-body bodyweight
                              └─ false: Rule #6  IF tujuan == stamina → Program lari 5K→10K
                                        └─ true: Rule #7  IF cedera == lutut → Renang interval
```

## Struktur repo

```
rdr/engine.py              # Condition, Node, KnowledgeBase (inferensi, daftar perbedaan, tambah rule, simpan/muat)
rdr/schema.py              # domain: atribut & kesimpulan default
app.py                     # UI Streamlit
examples/build_demo_kb.py  # simulasi sesi pakar (CLI)
examples/kb_demo.json      # KB contoh hasil simulasi
tests/test_engine.py       # unit test engine
```
