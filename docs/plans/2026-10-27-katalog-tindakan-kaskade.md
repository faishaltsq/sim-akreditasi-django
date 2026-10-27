# Plan tambahan: Kaskade pemilihan nakes & katalog tindakan klinis tertutup

Sumber (2026-10-27):

1. `~/Downloads/Alur pemilihan nakes dan Tindakan klinis sesuai level.docx` — alur kasade [Level Dokter] → [Spesialisasi/Subspesialisasi] → [Jenis Tindakan]; contoh Sp.JP, Sp.B, Sp.JP-FIHA, Sp.B-KBD.
2. `~/Downloads/Katalog tindakan klinis.docx` — katalog konkret siap pakai:
   - Tabel Dokter Umum: 10 butir (anamnesis, infus, kateter, NGT, RJP/BCLS, EKG dasar, hekting, gas darah, thoracocentesis, informed consent).
   - Tabel Dokter Spesialis: 16 spesialisasi (Sp.PD, Sp.B, Sp.A, Sp.OG, Sp.JP, Sp.S, Sp.An, Sp.Rad, Sp.PK, Sp.PA, Sp.OT, Sp.THT, Sp.M, Sp.KK, Sp.KJ, Sp.P) masing-masing 3–4 butir.
   - Tabel Dokter Subspesialis: 16 subspesialisasi (Nefrologi HD, Kardiologi, Bedah Digestif, Onkologi, Perinatologi, Respirologi anak Fetomaternal, Onkologi ginekologi, FIHA, Neurovaskular, Neuro-Onkologi, Intensive Care, Traumatologi, Otologi/Rinologi, Vitreoretina, Onkologi toraks).
   - Naratif nakes lain 18 profesi × level Pelaksana/Ahli (perawat PK I–IV, bidan, apoteker, elektromedis, sanitarian, gizi, TTK, perawat anestesi, PMIK, wicara, okupasi, ortotik-prostetik, fisioterapi, psikolog, radiografer, fisikawan medis, ATLM, K3).

## 1. Apa yang sudah ada (jangan bangun ulang)

| Kapabilitas | Status | Lokasi |
|---|---|---|
| `MasterProfesiPegawai`, `MasterJenjangProfesi` (+`fokus_kompetensi`, `preceptor_min_urutan`), `KatalogTindakan` | Ada | `sdm/models/katalog_rkk.py` |
| Filter katalog per profesi + jenjang di logbook, portal kredensial, detail kredensial | Ada (Fase R1 kemarin) | `sdm/forms/logbook.py`, `sdm/forms/level2_5.py`, `_detail_context` |
| Halaman katalog RKK dengan filter profesi/jenjang/pencarian | Ada | `kredensial_katalog` (sdm/views.py:1500) |
| Validasi `RincianKewenangan` terhadap jenjang | Ada | `kredensial_add_privilege` |
| Subspesialisasi bebas teks pada pengajuan? | **Belum** — `PengajuanKredensial` tidak punya kolom spesialisasi | `sdm/models/kredensial.py:57` |
| Katalog dokter butir | **Kosong** — seed kemarin baru jenjang naratif (0 baris `katalog dokter`) | seed `DOKTER_UMUM` lama |

Yang diminta dokumen ternyata melengkapi dua hal kecil tapi menentukan:

1. **Kaskade UI**: operator memilih jenjang dulu, baru katalog tersaring satu jenjang itu (sekarang dropdown katalog di detail menampilkan semua jenjang profesi sekaligus).
2. **Data katalog dokter tertutup**: daftar butir sudah diberikan — tidak lagi menunggu SK untuk RKK Tipe B ini.

## 2. Keputusan desain

- Spesialisasi/subspesialisasi dimodelkan sebagai **jenjang** di bawah `DOKTER_SP`/`DOKTER_UMUM(KONS)` — bukan tabel baru. `MasterJenjangProfesi` sudah unik per (profesi, kode) dan `KatalogTindakan` sudah menggantung di jenjang: kaskade level → spesialisasi → tindakan mengalir gratis dari struktur ini. Membuat model `Spesialisasi` terpisah akan menduplikasi seluruh alur filter yang sudah teruji.
- Kode jenjang spesialisasi = `SP-<singkatan>` (mis. `SP-PD`, `SP-JP`), subspesialisasi = `SUBSP-<singkatan>` (mis. `SUBSP-FIHA`). `urutan` = 2 (spesialis) / 3 (subspesialis) karena Dokter Umum = 1.
- Dokter Umum tetap satu jenjang `DU-UMUM` + katalog 10 butir.
- Katalog nakes lain 18 profesi dimasukkan sebagai **butir baru pada jenjang yang sudah ada** (kode baru berawalan `T-<PROF>-`), status mengikuti level (Pelaksana → 'S' kecuali butir eksplisit mandiri, Ahli → 'M'), karena dokumen memberi daftar per level tanpa status individual — konsisten dengan aturan `DEFAULT_STATUS_UNSET = 'S'` yang sudah ada. Butir yang nyata-nyata mandiri ("visite klinis mandiri", "manajemen mandiri") diberi 'M'.
- Status tabel dokter: semua butir `M` (dokter umum) sesuai rujukan SKDI 4A yang sudah tertulis di fokus kompetensi.

## 3. Rencana kerja

### Fase K1 — Seed katalog dokter (data tertutup)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| K1.1 | Data literal: `KATALOG_DOKTER_UMUM` (10 butir, status M, jenjang DU-UMUM), `KATALOG_SPESIALIS` (16 spesialisasi, tiap entri (judul, [butir])), `KATALOG_SUBSPESIALIS` (16 subspesialisasi) di `_data_katalog_rkk.py` | `sdm/management/commands/_data_katalog_rkk.py` | file ter-parse |
| K1.2 | Seed: buat jenjang `SP-*` di bawah `DOKTER_SP`, `SUBSP-*` juga di bawah `DOKTER_SP` (urutan 3), butir katalog berkode `K-DOKSP-xxx`; katalog `K-DOKUM-1..10`; idempoten (get_or_create by kode) | `seed_katalog_rkk.py` | seed 2× = 0 baru; hitungan test update |
| K1.3 | `DOKTER_SP` keluar dari `PROFESI_TANPA_JENJANG` | data module | dry-run bersih |
| K1.4 | Regresi hitungan seed test | `sdm/tests/test_kredensial_bab.py` | angka baru eksplisit |

### Fase K2 — Kaskade pemilihan di UI

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| K2.1 | Detail kredensial: dropdown kaskade "Jenjang/Spesialisasi" (+ spesialisasi bebas teks bila butir manual) di atas dropdown katalog; pilihan menyaring `katalog_qs` via GET `?jenjang=` (server-side, tanpa JS = paling sedikit risiko) | `_detail_context`, template `detail.html` | pilih Spesialisasi Jantung hanya menampilkan 5 butir Sp.JP |
| K2.2 | Portal self-service (Sub-Menu 2): label jenjang pegawai tampil; katalog rincian kewenangan pada `pengajuan_saya` sudah tersaring per jenjang (R1) — pastikan pesan galat jelas bila kosong | `pengajuan_saya.html` | smoke |
| K2.3 | Halaman katalog RKK: tambah pilihan "hanya jenjang saya" untuk operator? Tidak — sudah cukup filter yang ada. Skip. | — | — |

### Fase K3 — Seed katalog nakes lain (18 profesi)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| K3.1 | Data literal `KATALOG_NAKES_TAMBAHAN: {profesi_code: {jenjang_kode: [(butir, status)]}}` untuk 18 profesi dari dokumen, dipetakan ke jenjang seed yang sudah ada (PRATAMA/MUDA/MADYA/UTAMA atau PK-I..V, BK-I..V) | `_data_katalog_rkk.py` | file parse |
| K3.2 | Seed menggabungkannya ke loop katalog dengan kode `T-<PROF>-xxx` kontinu per profesi; jangan menabrak kode K- yang lama | `seed_katalog_rkk.py` | seed idempoten; total katalog naik sesuai hitung |
| K3.3 | Penambahan `jenis_berkas`? Tidak ada kaitan dokumen. Skip. | — | — |

### Fase K4 — Spesialisasi pada pengajuan (bonus dari alur, tetap kecil)

| # | Langkah | Berkas | Bukti |
|---|---|---|---|
| K4.1 | `PengajuanKredensial.spesialisasi_teks` CharField blank (bebas teks, bukan FK — komite memutuskan label final saat PSV) | `sdm/models/kredensial.py`, migrasi | migrasi 1 kolom |
| K4.2 | Form portal & form HC menampilkan field bila `employee.jenjang_master.kode` berawalan `SP-`/`SUBSP-` | `PengajuanPortalForm`, form HC | test: tampil hanya untuk spesialis |
| K4.3 | Cetak di berita acara (`kredensial_berita_acara`) | template | smoke |

## 4. Urutan

1. K1 → K3 (semua data literal, satu seed).
2. K2 kaskade (kecil, murni view+template).
3. K4 terakhir (kolom + label).

## 5. Yang tidak dikerjakan

- Model/tabel spesialisasi baru — jenjang & katalog sudah cukup (Kasade = struktur yang ada).
- Bank biaya/narsum TOR — luar sistem.
- Mengubah status M/S butir nakes lain di luar yang eksplisit — komite yang menetapkan (default 'S' + catatan baku tetap).
- Notifikasi WhatsApp/async job baru.

## 6. Bukti sebelum selesai

| Fase | Bukti |
|---|---|
| K1 | `seed_katalog_rkk --apply` idempoten; katalog dokter = 10 + 16×~3–4 + 16×3 butir; halaman katalog RKK menampilkan grup Komite Medis per spesialisasi |
| K2 | Detail kredensial: memilih "Sp.JP" menyaring dropdown hanya 5 butir jantung; memilih lain kosong dengan pesan |
| K3 | Perawat PK I melihat butir "Pemasangan infus…" di portal; PK IV melihat "supervisi klinis…"; test filter jenjang tetap hijau |
| K4 | Pengajuan milik dokter spesialis menampilkan input spesialisasi; cetak berita acara memuatnya |
