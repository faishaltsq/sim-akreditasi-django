# Analisis Gap — Modul Admisi Mandiri Multi-Kanal BPJS (APM-BPJS)

- **Tanggal:** 2026-11-19
- **Sumber kebutuhan:** `PRD_FSD_Modul_Admisi_Mandiri_APM_BPJS_ARima_Revisi.docx` (BL-01 s.d. BL-12, RSK-APM-01 s.d. 04)
- **Objek analisis:** repo `sim-akreditasi-django` @ `master` (ceef3e5)
- **Baseline terukur:** `pasien.tests_apm_{models,views,security,whatsapp,bpjs_tasks,queue,ui}` → **39 test, OK, 2.0 s** (`--keepdb`)
- **Status implementasi:** seluruh fase 0–11 sudah dieksekusi — bukti per fase ada di `docs/superpowers/plans/2026-11-19-apm-bpjs-multichannel.md` (§Execution ledger). Angka gate terakhir: **243 test APM OK**.

---

## 1. Ringkasan Eksekutif

Modul APM yang ada sekarang adalah **kiosk on-site** yang sudah solid secara fondasi: tiga gerbang pendaftaran (Pasien Baru / Pasien Lama / Check-In Barcode), alokasi nomor antrean harian yang aman dari race condition, estimasi jam periksa, tiket WhatsApp, struk thermal, pembatalan T-60, dan pencatatan 7 Task ID Antrean Online.

Dari 12 backlog PRD, **3 item (BL-01, BL-02, BL-03) belum ada sama sekali** karena menyangkut domain baru: **validasi rujukan BPJS**, **IGD Fast-Track yang benar-benar terisolasi**, dan **pemblokiran rujukan bermasalah**. Ini juga tiga item P0 yang menurut PRD harus selesai di Sprint 1.

Sisanya terbagi tiga: **(a)** sudah ada tapi belum sesuai spesifikasi (estimasi waktu tanpa `Delta_geser`/clamp, WhatsApp hanya 1 dari 3 templat dan meng-hardcode nama RS), **(b)** belum ada (portal mobile tanpa login, gerbang biometrik, eskalasi 3x gagal, rate limiting, masking, idle timeout global, `LOG_RISIKO_APM`), dan **(c)** ada tapi **cacat teknis** yang membuatnya tidak akan pernah jalan di mode live (lihat §3).

**Verdict:** jangan tulis ulang modul. Perluas `pasien` app dengan 4 permukaan baru (rujukan/kepatuhan, estimasi, biometrik, telemetri risiko) + 1 layanan bridging yang benar-benar sesuai kontrak VClaim 2.0. Estimasi realistis: 3 sprint, 11 fase kerja, ~28 task TDD.

---

## 2. Metode

1. Baca PRD/FSD lengkap (237 baris hasil ekstraksi).
2. Inventarisasi implementasi nyata: `pasien/apm_views.py`, `pasien/models.py` (APM block), `pasien/services/{whatsapp,bpjs_antrean,antrean}.py`, `pasien/bpjs.py`, `pasien/urls.py`, `templates/pasien/apm/*`, `config/settings.py`.
3. Trace setiap endpoint ke pemanggilnya (mencari kode mati dan mismatch kontrak).
4. Jalankan baseline suite APM untuk memastikan titik mulai hijau.
5. Bandingkan dengan model yang sudah ada di `akreditasi` (`RisikoUnit`) untuk menentukan titik integrasi risk register.

---

## 3. Temuan Teknis Kritis (Defect, bukan sekadar gap fitur)

| # | Temuan | Bukti | Dampak | Severity |
|---|---|---|---|---|
| F1 | `buat_sep()` membaca `kunjungan.icd10_masuk`, field yang **tidak ada** di `KunjunganPasien` (yang ada: `diagnosa_masuk`) | `pasien/bpjs.py:156` vs `pasien/models.py:343` | Di mode live, `AttributeError` tertangkap `except Exception` → **selalu jatuh ke SEP simulasi**, tanpa error ke operator. SEP palsu bisa dicetak. | Kritis |
| F2 | Nomor SEP dicetak dari string rekayasa, bukan hasil VClaim | `pasien/views.py:1670` (`f"0123R001{today}000{pk}"`), tidak ada kolom `no_sep` di model | Ketidaksesuaian klaim; SEP yang dilihat pasien ≠ SEP di BPJS | Kritis |
| F3 | `ambil_antrean()` adalah **dead code** dan payload-nya tidak sesuai kontrak `addantrean` Antrean RS v2 (hanya 4 field; tidak ada `kodebooking`, `norm`, `nomorkartu`, `nik`, `kodedokter`, `jampraktek`, `jeniskunjungan`, `nomorrujukan`, `pasienbaru`) | `pasien/bpjs.py:183-228`; nol pemanggil (grep seluruh repo) | Sinkronisasi Antrean Online tidak pernah terjadi; nomor antrean BPJS tidak pernah terbit; Task ID 1/3 dikirim untuk `kodebooking` yang tidak terdaftar | Kritis |
| F4 | Tiket WhatsApp meng-hardcode identitas RS + tidak ada templat Check-In/SEP & pergeseran jadwal | `pasien/services/whatsapp.py:56` (`"RSU PKU MUHAMMADIYAH GOMBONG / RS ARima"`), hanya `format_tiket_wa` + `format_notifikasi_igd` | Modul multi-RS bocor nama RS lain; Templat 2 & 3 PRD tidak ada | Tinggi |
| F5 | Tidak ada retry 3x, tidak ada rate limit per nomor, tidak ada masking nomor tujuan di log | `pasien/services/whatsapp.py:85-142` | PRD §2B-3 dilanggar; ban gateway berisiko | Tinggi |
| F6 | Estimasi jam tidak punya `Delta_geser`, tidak ada clamp `T_tiba >= T_buka_rs`, tidak ada re-estimasi otomatis saat dokter terlambat | `pasien/models.py:1524-1531`; `pasien/services/whatsapp.py:45` menghitung `est-30` tanpa batas bawah | N=1 poli 08:00 → pasien diinstruksikan datang 07:30 saat RS belum buka; pergeseran jadwal tidak pernah dikomunikasikan | Tinggi |
| F7 | Tidak ada validasi rujukan, tidak ada model rujukan, tidak ada field `no_rujukan`/`ppk_rujukan`/`tgl_rujukan`/`diagnosa_awal` di `KunjunganPasien` | grep `rujukan` di `pasien/models.py` → 0 hasil; `pasien/bpjs.py` hanya `/peserta/nokartu` dan `/sep` | BL-02 & BL-03 mustahil dijalankan | Kritis |
| F8 | IGD Fast-Track masih butuh identitas diisi lebih dulu (form nama + tanggal lahir) dan berada di step 2, bukan beranda | `templates/pasien/apm/kiosk.html:20-24,49` | Target registrasi IGD ≤ 2 menit tidak realistis untuk pasien tidak sadar/keluarga panik → RSK-APM-01 terbuka | Tinggi |
| F9 | Idle timeout hanya berjalan setelah registrasi sukses (60 s) atau setelah check-in (30 s); tidak ada timer global per layar | `templates/pasien/apm/kiosk.html:130,135` | Layar publik bisa tertinggal menampilkan data pasien sebelumnya → RSK-APM-04 | Tinggi |
| F10 | Nol rate limiting di seluruh endpoint publik (`cari-pasien`, `jadwal-dokter`, `daftar`, `checkin`, `batal`) | grep `ratelimit|throttle` di `pasien` + `config` → 0 hasil | Enumerasi NIK/No. BPJS tanpa batas; PRD §3A dilanggar | Tinggi |
| F11 | Tidak ada pencatatan risiko otomatis; `LOG_RISIKO_APM` tidak ada | `akreditasi/risiko_models.py:19` hanya `RisikoUnit` (register manual PDCA) | BL-12 & RSK-APM-01..04 tidak punya penampung | Sedang |
| F12 | Tidak ada gerbang biometrik maupun eskalasi helpdesk | 0 hasil grep `biometrik` di seluruh app | BL-08 & BL-09 kosong | Tinggi |
| F13 | Tidak ada portal mobile tanpa login; hanya kiosk | `pasien/urls.py:122-131` | BL-04 kosong; seluruh nilai "daftar dari rumah" tidak terkirim | Kritis |

---

## 4. Matriks Gap per Backlog PRD

| ID | Kebutuhan PRD | Kondisi Kode | Bukti | Gap |
|---|---|---|---|---|
| BL-01 (P0) | IGD Fast-Track di beranda, lolos validasi rujukan & biometrik, ≤ 2 menit, catat RSK-APM-01 | **Sebagian** | `apm_views.py:231-255` (flag MERAH, antrean IGD, WA IGD), `kiosk.html:49` | Tombol masih di step 2 setelah identitas; tidak ada jalur "identitas darurat minimal"; tidak ada pengukuran durasi registrasi; tidak ada log risiko |
| BL-02 (P0) | Scan QR/barcode/OCR/19 digit rujukan → `Rujukan/Peserta` | **Tidak ada** | `bpjs.py` hanya `cek_eligibilitas()` | Tidak ada endpoint rujukan, tidak ada parser nomor rujukan, tidak ada OCR rujukan, tidak ada model penyimpan hasil validasi |
| BL-03 (P0) | Blokir SEP reguler untuk rujukan > 90 hari / beda PPK / tidak ditemukan | **Tidak ada** | — | Butuh mesin aturan + alasan blokir terstruktur + jalur alternatif (umum/loket) |
| BL-04 (P1) | Portal mobile tanpa login (NIK/No. BPJS + tgl lahir + No. WA) + Kode Booking + QR Check-In | **Tidak ada** | `urls.py:122-131` (hanya `/pasien/apm/`) | Butuh sub-app/route terpisah, sesi capability bertanda tangan, QR, halaman tiket |
| BL-05 (P1) | `T_periksa = T_mulai + (N-1)×D_rata + Delta_geser`, `T_tiba = T_periksa - 30` clamp `T_buka_rs`, re-estimasi dinamis | **Sebagian** | `models.py:1524`, `whatsapp.py:45` | `Delta_geser` tidak ada; clamp tidak ada; tidak ada re-estimasi & notifikasi saat shift ≥ 15 menit |
| BL-06 (P1) | 3 templat WhatsApp variabel dinamis, retry 3x, rate limit, masking | **Sebagian (1 dari 3)** | `whatsapp.py:22-142` | Templat 2 & 3, `{{nama_rs}}` dari `RumahSakitProfile`, `{{nama_pasien_masked}}`, blok peringatan biometrik kondisional, retry, throttle |
| BL-07 (P1) | SEP/2.0/insert + Antrean Online + field ICD-10/faskes/rujukan read-only + idempotency | **Rusak/parsial** | F1, F2, F3 | Endpoint 2.0, payload lengkap, kolom `no_sep` + unique constraint idempotency, field terkunci di UI |
| BL-08 (P1) | Mandatory gate biometrik per poli (konfigurabel + pengecualian usia/status) | **Tidak ada** | — | Butuh model konfigurasi poli biometrik, adapter perangkat, gate di alur kiosk |
| BL-09 (P1) | Eskalasi 3x gagal → tiket prioritas helpdesk BPJS + `LOG_BIOMETRIK` + RSK-APM-03 | **Tidak ada** | — | Butuh penghitung percobaan per sesi kiosk + tiket prioritas |
| BL-10 (P2) | Masking, rate limiting, idle timeout 60–90 s global | **Sebagian** | `kiosk.html:130,135` | Timer global, masking di API response & WA, throttle |
| BL-11 (P2) | Fallback saat bridging timeout, tanpa SEP ganda | **Tidak ada** | `bpjs.py:111-128` (swallow error) | Butuh `BridgingUnavailable`, status gangguan eksplisit, jalur loket, tanpa fallback diam-diam ke simulasi |
| BL-12 (P3) | `LOG_RISIKO_APM` RSK-APM-01..04 + indikator mutu (SEP ≤ 3 mnt, IGD ≤ 2 mnt, kepatuhan biometrik) | **Tidak ada** | `akreditasi/risiko_models.py:19` | Model log + agregasi + dasbor + tautan ke register risiko unit |

---

## 5. Model Data yang Harus Ditambah

Ringkas — detail kolom ada di plan fase 1.

| Model / field | Tujuan |
|---|---|
| `RujukanBpjs` | Menyimpan hasil validasi `Rujukan/Peserta`: `no_rujukan` (19 digit, unik), `tgl_rujukan`, `tgl_kunjungan`, `ppk_rujukan`, `ppk_tujuan`, `diagnosa_awal`, `poli_tujuan`, `jenis_rujukan` (FKTP/antar-FKRTL/kontrol), `status_validasi`, `alasan_tolak`, `raw_response`, `divalidasi_pada` |
| `KunjunganPasien` + `no_sep`, `rujukan` (FK), `delta_geser_menit`, `estimasi_versi`, `biometrik_status`, `registrasi_mulai_at`, `registrasi_selesai_at` | Jejak SEP asli, kaitan rujukan, estimasi adaptif, SLA pengukuran IGD |
| `KonfigurasiBiometrikPoli` | `poliklinik`, `wajib_biometrik`, `batas_usia_min/max`, `pengecualian_status` (JSON), `aktif` |
| `LogBiometrik` | `kunjungan`, `percobaan_ke`, `metode` (FINGERPRINT/FACE), `hasil`, `skor`, `perangkat_id`, `waktu` |
| `LogRisikoApm` | `kode_risiko` (RSK-APM-01..04), `kunjungan`, `kanal` (MOBILE/KIOSK/LOKET), `pemicu`, `detail` (JSON), `severity`, `waktu` |
| `KonfigurasiApm` (atau perluas `SystemConfig`) | `t_buka_rs`, `buffer_tiba_menit` (30), `ambang_geser_notif_menit` (15), `idle_timeout_detik` (60–90), `biometrik_maks_percobaan` (3) |
| `WhatsAppLog` + pilihan `JENIS` baru | `KONFIRMASI_BOOKING`, `CHECKIN_SEP`, `PERGESERAN_JADWAL`, `ESKALASI_BIOMETRIK`; kolom `percobaan`, `provider`, `idempotency_key` |

---

## 6. Keputusan Arsitektur

| ID | Keputusan | Alasan |
|---|---|---|
| D1 | Semua integrasi BPJS lewat **satu service** `pasien/services/bpjs_vclaim.py`; `pasien/bpjs.py` dipertahankan sebagai shim yang men-delegasi (hindari patah kontrak pada pemanggil lama) | Menghapus file berisiko memutus `views.py:3153-3166`; shim membuat migrasi bertahap dan test lama tetap hijau |
| D2 | Kanal **mobile** adalah route terpisah dengan capability token bertanda tangan (`django.core.signing`, salt `apm-mobile`, `max_age` = jam tutup poli), bukan sesi login | PRD melarang login; pola sama sudah terbukti untuk struk thermal (`apm_views.py:449`) |
| D3 | Estimasi waktu dihitung **satu fungsi murni** `hitung_estimasi(t_mulai, n, d_rata, delta, t_buka_rs, buffer=30)` di `pasien/services/estimasi.py`, dipakai mobile, kiosk, struk, dan WA | Satu sumber kebenaran formula; sekarang formula tersebar di model + formatter WA |
| D4 | Biometrik diimplementasikan sebagai **adapter** `BiometricGateway` (mode `simulated` default, `device` bila protokol perangkat tersedia) | Protokol perangkat biometrik & lisensi BPJS bersifat vendor/RS-spesifik — tidak boleh di-hardcode (lihat §7) |
| D5 | WhatsApp lewat **provider abstraction** (`FonnteProvider`, `WabaCloudProvider`), retry 3x backoff, throttle per nomor | PRD menyebut WhatsApp Business API resmi; implementasi sekarang hanya Fonnte |
| D6 | Gangguan bridging **fail-closed**: tidak ada SEP, status `BRIDGING_DOWN` ditampilkan, log RSK-APM-04, arahkan ke loket | Fallback diam-diam ke simulasi (perilaku sekarang) berbahaya di produksi |
| D7 | `LogRisikoApm` adalah tabel append-only; agregasi ke `RisikoUnit` dilakukan **manual/terjadwal**, tidak menulis ke register PDCA secara otomatis | Register PDCA butuh periode, unit, dan penanggung jawab; auto-insert akan merusak data akreditasi |
| D8 | Konfigurasi dinamik (poli biometrik, jam buka, ambang geser) disimpan di DB, bukan `settings`/hardcode | PRD §2D eksplisit: "dikelola melalui konfigurasi admin dinamis (bukan hardcode)" |

---

## 7. Asumsi & Pertanyaan Terbuka (harus dikonfirmasi sebelum produksi)

1. **Protokol perangkat biometrik.** PRD menyebut "pemindai sidik jari optik standar BPJS + kamera face recognition terhubung aplikasi validasi BPJS". Tidak ada spesifikasi API di dokumen. Perlu dokumen vendor/kontrak BPJS untuk mode `device`. Sampai itu ada, gate berjalan dengan verifikasi lokal + audit `LogBiometrik` (mode `simulated`) dan **tidak boleh** dipakai sebagai bukti kepatuhan biometrik di UAT.
2. **Kredensial produksi VClaim & Antrean.** `config/settings.py:326-331` masih default dev (`apijkn-dev`). Tanpa Cons-ID/Secret/User-Key prod, semua jalur live tidak teruji.
3. **Kode PPK RS** (`BPJS_KODE_PPK` default `0000000`). Aturan "beda kode PPK tujuan" butuh nilai nyata.
4. **Pemetaan poli lokal ↔ kode poli BPJS.** `POLIKLINIK_CHOICES` (models.py:226) memakai kode internal (`POLI_JANTUNG`), bukan kode poli BPJS. Wajib ada tabel mapping sebelum `addantrean`/SEP bisa valid.
5. **Master ICD-10.** `KunjunganPasien` menyimpan diagnosis sebagai teks bebas; PRD menuntut field ICD-10 terkunci read-only dari rujukan. Perlu diputuskan: simpan kode + label hasil bridging sebagai string immutable, atau tambah FK ke master ICD.
6. **Provider WhatsApp.** Fonnte vs WABA resmi: menentukan biaya, template approval Meta, dan format pesan (WABA mewajibkan template terdaftar).
7. **Definisi "hari kunjungan" untuk booking dari rumah.** Apakah booking H+1..H+7 diizinkan? Saat ini `KunjunganPasien.tanggal_masuk` dipakai sebagai tanggal kunjungan, sehingga booking masa depan akan membuat baris kunjungan bertanggal masa depan dan memengaruhi filter "hari ini" di banyak view. Butuh keputusan produk.

---

## 8. Risiko Proyek & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Bridging BPJS tidak bisa diuji end-to-end (kredensial dev/prod tidak ada) | Fase 2 & 3 lolos test tapi gagal di produksi | Contract test terhadap fixture JSON respons VClaim asli + gate UAT eksplisit "live credential smoke test" sebelum go-live |
| Biometrik tidak punya spesifikasi API | BL-08/09 berhenti | Adapter + `simulated` mode; gate UAT ditandai **belum terpenuhi** sampai dokumen vendor ada |
| Booking masa depan merusak filter "hari ini" | Regresi lintas modul (pendaftaran, IGD, display antrean) | Fase 2 memisahkan `tanggal_kunjungan` (DateField) dari `tanggal_masuk` (DateTimeField) dan mengaudit setiap query `tanggal_masuk__date` |
| Perubahan payload SEP memutus alur pendaftaran manual yang sudah jalan | Pasien tidak bisa daftar | Shim D1 + suite `pasien.tests_pendaftaran_integrasi` dijadikan regression gate setiap fase |
| Retry WhatsApp memicu pesan ganda | Pasien menerima 2 tiket | `idempotency_key` unik per (kunjungan, jenis_pesan, versi_estimasi) di `WhatsAppLog` |
| Idle timeout agresif memutus pasien lansia di tengah input | Keluhan layanan | Timer global 90 s dengan peringatan visual 15 s terakhir + tombol "Saya masih di sini" |

---

## 9. Rekomendasi Urutan Eksekusi

| Sprint (PRD) | Fase di plan | Alasan urutan |
|---|---|---|
| Sprint 1 | Fase 0–4 | P0: kerangka data (rujukan, konfigurasi, log risiko) dulu, lalu IGD Fast-Track terisolasi, lalu validasi & blokir rujukan. Tanpa skema rujukan, BL-02/03 tidak mungkin ditulis. |
| Sprint 2 | Fase 5–9 | P1: estimasi murni → portal mobile → WA 3 templat → SEP 2.0 + Antrean Online → gerbang biometrik & eskalasi. Urutan ini menjaga agar setiap fitur punya data yang sudah benar. |
| Sprint 3 | Fase 10–11 | P2/P3: masking + rate limit + idle timeout, fallback bridging, lalu `LOG_RISIKO_APM` + dasbor indikator mutu, menjelang UAT-01..07. |

Detail task, file, dan kriteria penerimaan ada di `docs/superpowers/plans/2026-11-19-apm-bpjs-multichannel.md`.