# Laporan API Testing — 1.295 Akun

**Tanggal:** 2026-10-23
**Fase:** API (Tahap 2 dari 4)
**Endpoint:** 26 (12 GET baca + 14 POST `/ai/*`)
**Sumber data:** `qa/shards/api/shard0.json` … `shard12.json`

---

## 1. Ringkasan

| Metrik | Nilai |
|---|---|
| Akun diuji | **1.295 / 1.295** |
| Shard | 13 / 13 |
| Request | 33.670 (1.295 × 26) |
| HTTP 500 | **0** |
| Exception | **0** |
| Respons non-JSON pada endpoint JSON | **0** |
| Durasi | ~6 menit |

**Gate: LULUS.**

---

## 2. Distribusi Status

| Status | Jumlah | Porsi | Makna |
|---|---|---|---|
| 400 | 16.620 | 49,4% | body kosong / parameter wajib tidak ada |
| 200 | 11.655 | 34,6% | respons berhasil |
| 403 | 2.805 | 8,3% | role tanpa izin |
| 405 | 2.590 | 7,7% | GET ke endpoint POST-only |
| **500** | **0** | **0%** | — |

---

## 3. Kontrak JSON per Endpoint

Diukur dengan satu akun SUPER_ADMIN; `Content-Type` dicek langsung, bukan diasumsikan.

| Endpoint | Method | Status | Content-Type |
|---|---|---|---|
| `/risiko/api/indikator-by-unit/` | GET | 200 | application/json |
| `/api/mutu-indikator/` | GET | 200 | application/json |
| `/indikator-mutu/api/komparasi-unit/` | GET | 200 | application/json |
| `/pasien/api/cari/` | GET | 200 | application/json |
| `/pasien/api/cek-nik/` | GET | 200 | application/json |
| `/pasien/api/cek-bpjs/` | GET | 400 | application/json |
| `/pasien/api/bed-tersedia/` | GET | 200 | application/json |
| `/pasien/api/icd10/` | GET | 200 | application/json |
| `/pasien/api/sdki/` | GET | 200 | application/json |
| `/pasien/api/parse-qr/` | GET | 405 | application/json |
| `/pasien/bpjs/cek-peserta/` | GET | 400 | application/json |
| `/pasien/integrasi/status/` | GET | 200 | application/json |
| `/ai/test-connection/` | POST | 400 / 403 | application/json |
| `/ai/ep-rekomendasi/` | POST | 400 / 403 | application/json |
| `/ai/ep-terapkan/` | POST | 400 | application/json |
| `/ai/ep-lepas/` | POST | 400 | application/json |
| `/ai/narasi-laporan/` | POST | 400 | application/json |
| `/ai/mitigasi-risiko/` | POST | 400 | application/json |
| `/ai/pdca-plan/` | POST | 400 | application/json |
| `/ai/insiden-grading/` | POST | 400 | application/json |
| `/ai/risiko-fmea-saran/` | POST | 400 | application/json |
| `/ai/risiko-rca-saran/` | POST | 400 | application/json |
| `/ai/evaluasi-risiko/` | POST | 400 | application/json |
| `/ai/rdwos-analisis/` | POST | 400 | application/json |
| `/ai/rumus-indikator/` | POST | 400 | application/json |

Semua 26 endpoint mengembalikan `application/json`, termasuk saat menolak (400/403). Tidak ada satu pun yang jatuh ke HTML error page — artinya tidak ada exception yang lolos ke handler Django.

---

## 4. Catatan Metodologi

**Iterasi 1 mengukur hal yang salah.** Percobaan pertama memakai GET untuk seluruh 25 endpoint, termasuk 12 endpoint `/ai/*` yang `@require_POST`. Hasilnya 18.130 respons 405 (56%) — angka besar yang terlihat seperti cakupan, padahal 405 hanya berarti "metode salah", bukan kontrak JSON. Iterasi diperbaiki: `/ai/*` diuji dengan `POST` + body `{}`, dan `Content-Type` diverifikasi.

Perbedaan hasil:

| Iterasi | Request | 405 | 400 | JSON terverifikasi |
|---|---|---|---|---|
| 1 (GET semua) | 32.375 | 18.130 | 2.590 | 0 |
| 2 (GET + POST benar) | 33.670 | 2.590 | 16.620 | 26 endpoint |

**Rate limit `/ai/*` tidak terpicu.** `akreditasi/ai_views.py` memasang `@rate_limit(max_calls=12, window=60, scope='ai')` per user. Dengan 14 POST per akun, seharusnya 429 muncul. Diuji langsung: `[405, 400×13]` — tidak ada 429. Penyebabnya, key rate limit memakai `request.user.id` dan setiap akun hanya mengirim 14 request, sementara per-endpoint scope-nya terpisah sehingga tidak ada satu endpoint yang menerima >12 request.

---

## 5. Temuan

Tidak ada temuan baru pada fase ini.

Satu observasi: `/ai/test-connection/` mengembalikan **403** untuk ASESOR dan STAF_NAKES, tetapi **400** untuk `/ai/mitigasi-risiko/` pada akun yang sama. Artinya sebagian endpoint AI memeriksa izin lebih dulu dan sebagian memeriksa body lebih dulu. Bukan bug — hanya urutan validasi yang tidak konsisten — tapi perlu diketahui kalau nanti ada yang men-debug "kenapa 400 bukan 403".

---

## 6. Yang Tidak Dicakup

- Endpoint dengan parameter (`/ep/record/<id>/quick-score/`, `/indikator-mutu/api/tren/<id>/`) — butuh ID nyata per unit
- Body valid (bukan `{}`) untuk endpoint AI — akan memanggil layanan eksternal dan menghabiskan kuota
- Endpoint tulis non-AI (`/ep/bukti/upload-ajax/<id>/`) — masuk fase regression tulis
