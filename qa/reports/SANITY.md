# Laporan Sanity Testing — 1.295 Akun

**Tanggal:** 2026-10-23
**Fase:** Sanity (Tahap 3 dari 4)
**Endpoint:** 12 URL inti lintas modul, dengan assertion isi
**Sumber data:** `qa/shards/sanity/shard0.json` … `shard12.json`

---

## 1. Ringkasan

| Metrik | Nilai |
|---|---|
| Akun diuji | **1.295 / 1.295** |
| Shard | 13 / 13 |
| Request | 15.540 |
| HTTP 500 | **0** |
| Exception | **0** |
| Assertion isi gagal | **0** |
| Durasi | ~19 menit |

**Gate: LULUS.**

---

## 2. Distribusi Status

| Status | Jumlah | Porsi |
|---|---|---|
| 200 | 14.249 | 91,7% |
| 403 | 1.291 | 8,3% |
| 500 | 0 | 0% |

403 sebanyak 1.291 berasal dari `/human-capital/` yang ditolak untuk 4 role non-admin (F-3). 1.291 ≈ 876 akun × 1 URL + 415 dari role lain yang juga kena modul HC. Tidak ada 403 pada 11 endpoint lainnya untuk role yang berhak.

---

## 3. Assertion yang Dipakai

Assertion memakai `<title>` halaman, bukan teks bebas. Alasan: penanda seperti `'isiko'` muncul di sidebar **setiap** halaman, sehingga halaman yang isinya rusak tetap lolos (false pass). `<title>` unik per halaman dan hanya terender bila view mengirim konteks yang benar.

| URL | Assertion `<title>` |
|---|---|
| `/dashboard/` | `Aplikasi Terpadu Manajemen Risiko` |
| `/control/` | `Hospital Integrated Control` |
| `/control/risiko/` | `Integrated Risk & Patient Safety Control` |
| `/control/emr/` | `Smart EMR & Clinical Quality` |
| `/matriks/` | `Matriks PDCA` |
| `/risiko/` | `Daftar Risiko Unit` |
| `/rekap/` | `Rekapitulasi Akreditasi RS` |
| `/indikator-mutu/` | `Capaian Indikator Mutu` |
| `/laporan-mutu/` | `Laporan Capaian Indikator Mutu` |
| `/logbook/` | `Logbook Harian IGD` |
| `/pencarian/` | `Pencarian` |
| `/human-capital/` | `Arima Human Capital` |

Selain assertion positif, runner juga memeriksa **kebocoran**: body tidak boleh mengandung `Traceback (most recent call last)` atau `django.core.exceptions`. Nol pelanggaran.

---

## 4. Catatan Metodologi

**Iterasi 1 gagal secara senyap.** Assertion awal memakai potongan kata umum (`'isiko'`, `'ekap'`, `'ndikator'`). Hasilnya 0 temuan — yang terlihat seperti keberhasilan, tapi sebenarnya false pass: semua potongan itu ada di sidebar. Assertion diperketat ke `<title>`, dan hasilnya tetap 0 temuan. Perbedaan pentingnya: iterasi pertama **tidak membuktikan apa pun**, iterasi kedua membuktikan 12 halaman merender judul yang benar untuk 1.295 akun.

Verifikasi manual atas 12 halaman sebagai SUPER_ADMIN mengonfirmasi setiap `<title>` cocok dengan yang diharapkan, dan ukuran body berkisar 11 KB (`/control/`) sampai 1,6 MB (`/rekap/`) — tidak ada halaman kosong.

---

## 5. Temuan

Tidak ada temuan baru. F-2 (unit RAJAL/RANAP terkunci) dan F-3 (HC tertutup 4 role) sudah tercatat di `SMOKE.md`; fase sanity mengonfirmasi F-3 dengan angka pasti: 1.291 penolakan terkonsentrasi di `/human-capital/`.

---

## 6. Yang Tidak Dicakup

- Halaman dengan parameter (`/ep/<id>/detail/`, `/risiko/<id>/`) — butuh fixture per unit
- Interaksi JavaScript (chart, modal, sidebar collapse) — butuh browser, bukan test client
- Tampilan visual / layout — butuh screenshot diff
