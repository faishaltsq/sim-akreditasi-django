# 🏥 DOKUMENTASI SISTEM INFORMASI MANAJEMEN AKREDITASI RS MONSISKAMI
### *Aplikasi Dokumen Manajemen & Akreditasi Rumah Sakit Tipe B — Standar KARS / STARKES*

---

## 📌 Indeks Modul Panduan Pengguna

Dokumentasi ini disusun secara terpisah per sub-sistem agar mudah dipelajari oleh setiap unit/staf dan dapat di-update secara independen saat ada rilis fitur baru:

| No | Modul / Dokumen | Target Pengguna | Isi Ringkas |
|:--:|---|---|---|
| **01** | [**01. Panduan Mulai Cepat (Quickstart)**](01_PANDUAN_MULAI_CEPAT.md) | Semua Pengguna & Pegawai Baru | Cara login, 13 role demo, tata letak dashboard & ganti kata sandi |
| **02** | [**02. Manajemen Dokumen Akreditasi RDWOS**](02_MANAJEMEN_POKJA_DAN_RDWOS.md) | Koordinator Pokja, Asesor | Standar bukti R-D-W-O-S, upload file Supabase, verifikasi dokumen |
| **03** | [**03. Matriks PDCA & Auto-Scoring KARS**](03_MATRIKS_PDCA_DAN_SCORING.md) | Direktur, Komite Mutu, Pokja | Pengisian Plan-Do-Check-Action, formula auto-scoring, cetak PDF resmi |
| **04** | [**04. Manajemen Risiko & Laporan Insiden**](04_MANAJEMEN_RISIKO_DAN_INSIDEN.md) | Tim KPRS, Komite Mutu, Seluruh Staf | Register risiko matriks 5×5, evaluasi RCA/PDCA, lapor insiden anonim |
| **05** | [**05. Struktur Organisasi & Portal Nakes**](05_STRUKTUR_ORGANISASI_DAN_NAKES.md) | SDM, Dokter, Perawat, Nakes | 65 Unit Kerja RS Tipe B, 14 KSM, kredensial STR/SIP & SPK/RKK |
| **06** | [**06. SOP Update Fitur & Dokumentasi**](06_STANDAR_OPERASIONAL_UPDATE_FITUR.md) | Developer & Tim IT SIMRS | Tata cara wajib menambah section dokumentasi saat rilis fitur baru |
| **WEB** | [**Portal Dokumentasi Interaktif (HTML)**](PANDUAN_LENGKAP_RS_MONSISKAMI.html) | Pembaca Browser / Offline | Single-page UI teal-white dengan pencarian real-time & menu responsif |

---

## 🌐 Informasi Lingkungan Sistem

- **URL Production:** [https://sim-akreditasi-web-production.up.railway.app](https://sim-akreditasi-web-production.up.railway.app)
- **Repository Source Code:** [https://github.com/faishaltsq/sim-akreditasi-django](https://github.com/faishaltsq/sim-akreditasi-django)
- **Basis Standar Akreditasi:** Standar Akreditasi Rumah Sakit Kemenkes (STARKES) / KARS 2023–2026.
- **Penyimpanan Berkas Bukti:** Cloud Object Storage (Supabase Storage) ber-enkripsi SSL.
- **Status Database:** 65 Unit Kerja RS Tipe B, 16 Pokja Akreditasi, 792 Elemen Penilaian (EP).
