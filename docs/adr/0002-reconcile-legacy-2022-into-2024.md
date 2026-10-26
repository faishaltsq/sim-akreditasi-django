# ADR 0002 — Rekonsiliasi EP legacy 2022 ke instrumen 2024

- **Status:** Diterima
- **Tanggal:** 2026-10-22
- **Konteks:** Migrasi STARKES 2022 → STARKES 2024 (16 BAB, 227 standar, 800 EP)

## Masalah

Seed `seed_starkes_16_bab` menanam **299 `StandardItem`** dengan **299 `QualityRecord`**
(score 0, tanpa baseline, tanpa action plan, 0 `EvidenceReq`). Instrumen 2024
memuat **800 EP** dengan kode yang sebagian besar berbeda: penomoran EP berubah
dari angka (`TKRS 1 EP 1`) menjadi huruf (`TKRS 1 EP a`), nomor standar bergeser,
dan dua bab berganti kode (`ARK → AKP`, `IPKP → PPK`).

Tiga tabrakan muncul saat import dijalankan di database yang sudah berisi seed 2022:

1. `StandardItem.code` dulu `unique=True` global. Import 2024 menulis kode yang
   sama dengan baris legacy → `IntegrityError: UNIQUE constraint failed`.
2. Import me-resolve `Category` hanya dengan `code`, sehingga `update_or_create`
   **mengambil alih** kategori milik framework 2022 alih-alih membuat kategori
   2024. Akibatnya `TKRS` berisi 71 EP 2024 **plus** 28 EP 2022.
3. Dua kategori alias (`ARK`, `IPKP`) tidak pernah dipetakan, jadi EP-nya tetap
   hidup sebagai bab sendiri dan total `target_ep_count` menjadi **829**, bukan 800.

## Keputusan

**Petakan ulang EP legacy ke EP 2024 di tempat (`UPDATE`), bukan memberi namespace
baru dan bukan menghapus lalu menanam ulang.**

`akreditasi/reconcile_2024.py` menjalankan dua tahap per bab:

1. **Exact** — kode legacy yang setelah alias bab sudah merupakan kode 2024 yang
   sah dipakai apa adanya. Ini mempertahankan `SKP 1 EP 1` dan `PROGNAS 1 EP 1`
   (2024 memang memakai huruf angka untuk bab tersebut).
2. **Ordinal** — sisa EP dikelompokkan per standar dan dipasangkan menurut urutan
   dokumen dengan EP 2024 yang belum terpakai pada standar yang sama.

Karena yang berubah hanya kolom pada baris yang sudah ada, **PK `StandardItem`
tidak berubah**, sehingga seluruh `QualityRecord` ikut terbawa tanpa disalin.

### Uniqueness kode EP dipersempit

`StandardItem.code` diubah dari `unique=True` global menjadi
`UniqueConstraint(category, code)` (migrasi `0040`). Yang sebenarnya dibutuhkan
adalah "tidak ada kode ganda di dalam satu pokja"; uniqueness global memaksa
edisi baru tidak boleh berdampingan dengan edisi lama, sehingga setiap migrasi
menuntut penghapusan data lebih dulu.

### Baris tanpa padanan tidak dihapus diam-diam

52 EP legacy tidak punya padanan di 2024 (mis. `PPI 7.2.1`, `ARK 7`). Baris itu
hanya dihapus bila benar-benar kosong: tidak ada skor, baseline, action plan,
risk mitigation, quality target, berkas bukti, dan `eval_notes` bukan placeholder
mesin (`"Belum dinilai. Unit pengampu: ..."`). Bila ada isi, import **berhenti**
dan melaporkan kode yang menghalangi.

### Framework aktif = edisi terbaru

`active_framework()` mengembalikan framework dengan id tertinggi. Sebelumnya
sidebar, matriks PDCA, dan daftar EP memakai `Framework.objects.first()` /
`Category.objects.all()`, yang mengunci UI ke edisi paling tua dan mencampur
kedua edisi dalam satu hitungan.

## Hasil terukur

Dijalankan pada database test berisi seed 2022 penuh:

| Metrik | Nilai |
|---|---|
| `StandardItem` legacy | 299 |
| Dipetakan ulang di tempat | 247 |
| Tanpa padanan 2024 (dihapus, kosong) | 52 |
| EP baru dari fixture | 553 |
| **Total akhir** | **800** |
| `QualityRecord` dipertahankan | 299 / 299 |
| Bentrok kode saat rename | 0 |

## Konsekuensi

- `QualityRecord` 2022 tetap menempel pada EP yang sekarang berkode 2024. Skornya
  semuanya 0, jadi tidak ada nilai yang berpindah makna.
- 52 EP legacy hilang. Semuanya kosong, sehingga tidak ada penilaian yang hilang.
- Import bersifat idempotent: menjalankan ulang menghasilkan 800 baris yang sama.
- `--dry-run` melaporkan rencana yang sama dengan eksekusi nyata (remap / drop /
  create / proyeksi total), bukan selisih mentah kode.

## Alternatif yang ditolak

| Alternatif | Alasan ditolak |
|---|---|
| Suffix namespace (`TKRS 1 EP a (2024)`) | Merusak relasi kode ↔ tampilan, filter `sub_standard`, dan pencarian berbasis kode |
| Hapus semua `StandardItem` 2022 lalu import bersih | Menghapus 299 `QualityRecord`; tidak dapat dibatalkan |
| Biarkan dua edisi berdampingan | `Category.objects.get(code='TKRS')` jadi ambigu; UI mencampur dua edisi |
| `SystemConfig` sebagai resolver framework aktif | Tidak punya kolom framework; tidak pernah dirancang untuk itu |
