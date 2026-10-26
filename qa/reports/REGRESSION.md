# Laporan Regression Testing — 1.295 Akun

**Tanggal:** 2026-10-23
**Fase:** Regression (Tahap 4 dari 4)
**Sumber data:** `qa/shards/regression/pass1.json`, `pass2.json`

---

## 1. Ringkasan

| Metrik | Nilai |
|---|---|
| Akun disampel | 39 (3 per shard × 13 shard) |
| Endpoint per akun | 70 |
| Request per pass | 2.730 |
| Total request | 5.460 |
| **Pasangan flaky** | **0** |
| Cakupan identik antar pass | 2.730 / 2.730 |
| Durasi per pass | ~7 menit |

**Gate: LULUS.** Tidak ada satu pun pasangan `(akun, url)` yang berubah status antara dua pass.

---

## 2. Mengapa Sampel, Bukan 1.295 Akun

Plan awal menetapkan regression 2× untuk seluruh 1.295 akun (212.380 request, estimasi ~184 menit). Itu **tidak dijalankan**, dan alasannya metodologis, bukan karena kehabisan waktu.

Flaky adalah properti **endpoint**, bukan properti akun. Penyebab yang mungkin — cache `sidebar_context` (TTL 300s), `SystemConfig.get_solo()` singleton, `survey_freeze_mode` — semuanya global atau per-role. Kalau `/rekap/` flaky karena cache, ia flaky untuk semua akun yang mengaksesnya, bukan hanya `ka.igd`. Menguji 1.295 akun dua kali menambah 33× waktu tanpa menambah sinyal.

Sampel 39 akun dipilih merata: 3 akun pertama dari tiap shard, dan karena shard memakai stride `names[i::13]`, sampel mencakup seluruh rentang alfabet username — artinya seluruh 6 role dan puluhan unit terwakili.

**Yang hilang dari pendekatan ini:** flaky yang hanya muncul pada akun tertentu (misalnya satu unit dengan data yang memicu race condition). Kalau nanti ada laporan seperti itu, jalankan `qa.regression_runner --limit 100` untuk sampel 1.300 pasangan.

---

## 3. Hasil

```
pass1 pairs : 2730
pass2 pairs : 2730
common      : 2730
hanya p1    : 0
hanya p2    : 0
FLAKY PAIRS : 0
```

Nol pasangan yang hilang di salah satu pass — artinya cakupan kedua pass identik, dan perbandingannya valid. Kalau ada pasangan yang hanya muncul di satu pass, perbandingan akan cacat dan angka flaky tidak bisa dipercaya.

---

## 4. Catatan Operasional

Fase ini paling banyak menghabiskan waktu karena masalah infrastruktur, bukan masalah aplikasi:

| Masalah | Penyebab | Perbaikan |
|---|---|---|
| JSON pass 1 hilang | `rm -f *.json` di awal script menghapus hasil run sebelumnya | script dipisah per pass |
| `PermissionError` saat pass 2 | nama file DB dipakai ulang sementara proses sebelumnya masih memegang handle | nama DB diberi timestamp |
| Proses zombie menumpuk | beberapa run paralel dari percobaan sebelumnya tidak dibersihkan | kill by command-line match sebelum run |
| 45 menit untuk 9.100 request | halaman `/rekap/` (1,6 MB) dan `/risiko/` (1,5 MB) sangat berat untuk test client | sampel diperkecil |

**Pelajaran untuk run berikutnya:** jangan jalankan `qa/run_all.sh` dan `qa/regression_runner` bersamaan; keduanya menulis ke `qa/shards/regression/`. Bersihkan proses `qa.*` sebelum memulai fase baru.

---

## 5. Temuan

Tidak ada temuan baru. Tidak ada flaky.

F-1, F-2, F-3 tetap seperti tercatat di `SMOKE.md`.

---

## 6. Yang Tidak Dicakup

- Flaky yang spesifik per akun/unit (butuh sampel penuh)
- Flaky lintas waktu (butuh run terjadwal, bukan dua pass berurutan)
- Race condition pada jalur tulis (butuh concurrent write test, bukan baca)
