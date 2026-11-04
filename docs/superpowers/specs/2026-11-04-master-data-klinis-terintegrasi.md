# Master Data Klinis Terintegrasi — Spec (ICD-10 × ICD-9-CM × Triase × ARIMA × SLA)

**Sumber:** `C:\Users\cubeb\Downloads\Master Data Klinis Lengkap.md.pdf` — "Master Data Klinis Lengkap", Versi Data 2026.V1.

**Tanggal analisis:** 2026-11-04. **Repo:** `sim-akreditasi-django` @ `master` (17d3ffc).

---

## 1. Isi dokumen sumber

Dokumen memetakan lima variabel SIMRS/RME ke satu baris data:

1. Diagnosis utama/sekunder (ICD-10)
2. Tindakan medis/prosedur (ICD-9-CM)
3. Kategori triase gawat darurat
4. Level risiko ARIMA
5. Indikator standar mutu & target waktu tanggap (SLA)

Katalog berisi **20 baris klinis** (spesialisasi, kode ICD-10, kode ICD-9-CM, triase, level risiko, SLA) dan **3 aturan manajemen risiko**:

| # | Aturan | Isi dokumen |
|---|--------|-------------|
| 1 | Trigger Alert Real-Time (SLA Breach Warning) | Apabila waktu pelayanan > 80% dari target (misal: EKG belum di-input menit ke-8 untuk STEMI), kirim peringatan otomatis ke Nurse Station |
| 2 | Validasi Silang Diagnosis & Prosedur | Prosedur invasif berisiko HIGH/CRITICAL secara otomatis mewajibkan verifikasi Informed Consent |
| 3 | Audit Otomatis Insiden Keselamatan Pasien (IKP) | Varians terhadap SLA atau ketidaksesuaian pasang diagnosis–tindakan langsung tercatat ke logbook analitik mutu internal secara otomatis |

Catatan ekstraksi: baris 20 dokumen rusak akibat konversi PDF (`O15.00 Eclampsia...` bercampur teks aturan). Nilai O15.00 (Eklampsia), ICD-9 `74.1` (Low cervical cesarean section / SC Cito), triase Merah, risiko CRITICAL, SLA "MgSO₄ ≤ 10 menit, Decision-to-Delivery SC Cito ≤ 30 menit" dipulihkan dari fragmen kalimat yang terlihat di baris 44–50.

---

## 2. Tabel katalog lengkap (sumber tunggal untuk Task implementasi)

| No | Spesialisasi | ICD-10 | Diagnosis | ICD-9-CM | Prosedur | Triase | Risiko | SLA |
|----|--------------|--------|-----------|----------|----------|--------|--------|-----|
| 1 | Kardiovaskular | I21.0 | Acute transmural MI of anterior wall (STEMI Anterior) | 89.52 | Electrocardiogram (ECG) | MERAH | CRITICAL | Door-to-ECG ≤ 10 mnt; Door-to-Needle/PCI ≤ 90 mnt |
| 2 | Kardiovaskular | I20.0 | Unstable angina | 89.54 | ECG monitoring | KUNING | HIGH | Perekaman EKG ≤ 15 mnt; bedside monitor aktif |
| 3 | Kardiovaskular | I50.9 | Heart failure unspecified (CHF) | 88.72 | Echocardiography | KUNING | HIGH | Oksigenasi & tirah baring; LoS IGD < 6 jam |
| 4 | Kardiovaskular | R57.0 | Cardiogenic shock | 99.60 | CPR / Resusitasi | MERAH | CRITICAL | Response 0 mnt (resusitasi langsung) |
| 5 | Neurologi | I63.9 | Cerebral infarction unspecified (Stroke Iskemik) | 89.15 | Neurologic exam / non-contrast CT head | MERAH | CRITICAL | Door-to-CT ≤ 25 mnt; interpretasi ≤ 45 mnt |
| 6 | Neurologi | I61.9 | Intracerebral hemorrhage | 01.59 | Craniotomy | MERAH | CRITICAL | Konsul Sp.BS ≤ 30 mnt; preparation OK cito ≤ 60 mnt |
| 7 | Neurologi | G40.9 | Epilepsy unspecified (Status Epileptikus) | 99.29 | Injeksi terapeutik/profilaksis | MERAH | HIGH | Antikonvulsan IV ≤ 5 mnt |
| 8 | Respirasi | J45.901 | Asthma with acute exacerbation | 93.94 | Nebulisasi | KUNING | MEDIUM | Nebulisasi pertama ≤ 15 mnt; evaluasi SpO2 post-nebul |
| 9 | Respirasi | J18.9 | Pneumonia unspecified organism | 87.44 | Routine chest x-ray | KUNING | MEDIUM | Foto thorax ≤ 60 mnt; abx pertama ≤ 4 jam |
| 10 | Respirasi | J96.00 | Acute respiratory failure unspecified | 96.04 | Intubasi ETT | MERAH | CRITICAL | Amankan airway ≤ 5 mnt; persiapan ventilator |
| 11 | Digestif | K35.30 | Acute appendicitis with localized peritonitis | 47.09 | Appendektomi laparoskopis/open | KUNING | HIGH | Abx profilaksis pre-op ≤ 60 mnt; operasi ≤ 24 jam |
| 12 | Digestif | K92.2 | GI hemorrhage unspecified | 44.13 | Gastroscopy / Endoscopy | KUNING | HIGH | Cek Hb & respons transfusi darah cito |
| 13 | Digestif | K80.20 | Calculus of gallbladder without cholecystitis | 51.23 | Laparoscopic cholecystectomy | HIJAU | LOW | Perioperatif checklist; edukasi diet rendah lemak |
| 14 | Trauma & Bedah | S72.301A | Unspecified fracture shaft right femur | 79.35 | ORIF femur | KUNING | HIGH | Pembidaian & analgetik ≤ 30 mnt; cek pulsasi distal |
| 15 | Trauma & Bedah | T07 | Unspecified multiple injuries (Multiple Trauma) | 86.59 | Suturing | MERAH | CRITICAL | Primary survey (ABCDE) ≤ 5 mnt |
| 16 | Infeksi & Tropis | A91 | Dengue hemorrhagic fever (DBD) | 99.18 | Injeksi/infus elektrolit | KUNING | MEDIUM | Serial lab hematokrit & trombosit per 6–12 jam |
| 17 | Infeksi & Tropis | A41.9 | Sepsis unspecified organism | 99.21 | Injeksi antibiotik | MERAH | CRITICAL | Sepsis bundle 1 jam (kultur darah, laktat, abx broad spectrum) |
| 18 | Endokrin & Metabolik | E11.65 | Type 2 DM with hyperglycemia (Krisis Hiperglikemia) | 99.17 | Injeksi insulin | KUNING | HIGH | Cek GDS cito; protokol rehidrasi & reval insulin |
| 19 | Nefrologi & Urologi | N18.6 | End stage renal disease (ESRD stage 5) | 39.95 | Hemodialisis | KUNING | MEDIUM | Monitoring akses AV shunt; monitoring tanda uremia |
| 20 | Maternal & Obstetri | O15.00 | Eclampsia in pregnancy unspecified trimester | 74.1 | Low cervical cesarean section (SC cito) | MERAH | CRITICAL | Pemberian MgSO₄ ≤ 10 mnt; decision-to-delivery SC cito ≤ 30 mnt |

---

## 3. Temuan audit codebase (probe sebelum menulis plan)

Semua temuan di bawah diverifikasi lewat grep/read langsung pada repo, bukan inferensi.

### 3.1 Yang sudah ada dan harus dipakai ulang

| Kapabilitas | Lokasi | Status |
|---|---|---|
| Pilihan ICD-10 | `pasien/views.py:29` `ICD10_CODES` — 83 kode | **83 kode terdaftar; 11 dari 18 kode PDF belum ada** (I21.0, I20.0, J45.901, J96.00, K35.30, K80.20, S72.301A, T07, A41.9, E11.65, N18.6, O15.00 — 12 kode) |
| Kode ICD-9-CM | **Tidak ada list terpusat.** Field `KunjunganPasien.icd9_tindakan` = `CharField(max_length=300)` teks bebas, placeholder hardcoded di template | Perlu katalog terstruktur |
| Triase | `KunjunganPasien.TRIASE_KATEGORI_CHOICES` (`pasien/models.py:443`) | Ada; kategori MERAH/KUNING/HIJAU/HITAM |
| Waktu SLA | `KunjunganPasien.waktu_asesmen_dokter`, `waktu_disposisi` — **`CharField(max_length=10)` string WIB**, bukan `DateTimeField` | Ada tapi tidak bisa dihitung delta-nya secara andal |
| Level risiko | `akreditasi/risiko_models.py` `RisikoUnit` (skor FMEA + ambang `SystemConfig`), `InsidenKeselamatan` | Ada; level dihitung dari skor, bukan dari enum PDF |
| Indikator mutu | `IndikatorMutu` (akreditasi/risiko_models.py:586) + `CatatanIndikator` | Ada; sudah punya `arah_target`, `target_nilai`, `faktor_pengali` |
| Logbook | `akreditasi/logbook_models.py` `LogbookHarian` + `LogbookKejadian` (FK ke `InsidenKeselamatan`, method `sync_ke_ikp()` idempoten) | **Aturan 3 PDF sebagian besar sudah terimplementasi** |
| Consent | `pasien/models.py:983` `GeneralConsentRawatInap` (rawat inap; checkbox STARKES) | Ada untuk ranap; **tidak ada consent untuk tindakan invasif IGD** |
| Dasbor IGD | `pasien/views.py:1003` `igd_dashboard` + `templates/pasien/igd_dashboard.html` | Ada; sudah punya `ews_data`, `critical_orders`, `pemeriksaan_presets` |
| Dasbor kontrol | `akreditasi/kontrol_data.py` (snapshot 60 detik, `SNAPSHOT_CACHE_VERSION='v3'`) | Ada; read-only, tanpa tulis DB |

### 3.2 Yang belum ada

1. **Tidak ada SLA clock.** Tidak ada `DateTimeField` untuk door time / EKG time / needle time. Semua waktu adalah string `HH:MM` — perhitungan "menit ke-8" tidak mungkin dilakukan benar.
2. **Tidak ada katalog ICD-9-CM terstruktur.** `icd9_tindakan` free-text; pasangan diagnosis–prosedur (aturan 2) tidak bisa divalidasi.
3. **Tidak ada alert otomatis.** Tidak ada model notifikasi, tidak ada scheduler (grep `cron|celery|APScheduler` = kosong; satu-satunya job terjadwal adalah GitHub Actions `.github/workflows/hc-reminders.yml` yang memanggil `manage.py hc_reminders` — pola yang sudah mapan).
4. **Tidak ada consent tindakan invasif** — `GeneralConsentRawatInap` hanya untuk rawat inap, bukan untuk tindakan IGD.
5. **Tidak ada audit otomatis variance SLA** — `LogbookKejadian.sync_ke_ikp()` menulis insiden dari logbook manual, tapi tidak ada deteksi otomatis dari data kunjungan.

### 3.3 Baseline pengujian

`python manage.py test pasien akreditasi` — **993 test, 1 failure pre-existing** (tidak terkait pekerjaan ini):

```
FAIL: test_subdasbor_setelah_cache_hangat (akreditasi.tests_kontrol_dasbor.KontrolQueryBudgetTest)
AssertionError: 16 not less than or equal to 12 : 16 query, anggaran 12
```

Ini query-budget dasbor kontrol yang sudah meleset sebelum pekerjaan ini mulai. Tidak diperbaiki di plan ini — dicatat sebagai risiko terpisah.

---

## 4. Keputusan arsitektur (dengan tradeoff)

| Keputusan | Alasan | Tradeoff yang diterima |
|---|---|---|
| **Model katalog terpisah** (`MasterIcd10`, `MasterIcd9`, `MasterSla`) di app baru `klinis` | Katalog dipakai lintas app (pasien, akreditasi, kontrol); menaruhnya di `pasien` akan membuat `akreditasi` import dari app lebih rendah | Satu app baru; migrasi baru. Alternatif (menaruh di `pasien`) ditolak karena coupling terbalik |
| **Jam klinis pakai `DateTimeField` baru**, tidak mengubah `waktu_asesmen_dokter` yang sudah ada | Field lama `CharField` dipakai luas di template (`{{ k.waktu_asesmen_dokter }}`); mengubah tipe = migrasi data + risiko regresi | Ada dua sumber waktu (lama string untuk tampilan, baru datetime untuk hitungan). Diterima karena tampilan dan hitung memang kebutuhan berbeda |
| **SLA breach dihitung on-demand di view + snapshot**, bukan scheduler | Repo tidak punya scheduler apa pun; GitHub Actions hanya dipakai untuk `hc_reminders` yang butuh jaringan eksternal. Menambah Celery/APScheduler = dependency baru + worker baru | Alert hanya muncul saat halaman dibuka. Untuk peringatan "push" perlu scheduler — **dijadwalkan di luar scope plan ini** |
| **Katalog SLA satu baris per aturan**, bukan per pasien | SLA adalah master data (target menit), bukan catatan pasien. Evaluasi per pasien adalah derived | Butuh model evaluasi terpisah untuk menyimpan hasil perhitungan per kunjungan |
| **ICD-9-CM dipetakan sebagai teks + kode terpisah**, bukan mengganti `icd9_tindakan` | Field lama sudah dipakai 5 tempat (dashboard, cetak resume, cetak asesmen). Menambah field `icd9_kode` bersifat additive | Data lama tidak punya kode; backfill opsional |
| **Consent tindakan invasif = model baru**, tidak memperluas `GeneralConsentRawatInap` | `GeneralConsentRawatInap` OneToOne dengan kunjungan; tindakan bisa banyak per kunjungan | Dua model consent berdampingan |

---

## 5. Rencana induk (3 plan terpisah)

Plan dipecah per subsistem. Setiap plan harus bisa berdiri sendiri dan menghasilkan software yang bisa diuji.

| Plan | File | Subsistem | Dependensi |
|---|---|---|---|
| P1 | `docs/superpowers/plans/2026-11-04-master-data-klinis-katalog.md` | Katalog master (ICD-10/ICD-9/SLA) + seed 20 baris PDF | Tidak ada |
| P2 | `docs/superpowers/plans/2026-11-04-master-data-klinis-sla-clock.md` | Jam klinis + evaluasi SLA + alert real-time di dasbor IGD | P1 (katalog SLA) |
| P3 | `docs/superpowers/plans/2026-11-04-master-data-klinis-consent-audit.md` | Consent tindakan invasif + validasi silang + audit otomatis IKP | P1 (katalog ICD/risiko) |

**Urutan wajib:** P1 → P2 → P3. P2 dan P3 mengedit berkas berbeda (views/template berbeda) dan bisa berjalan paralel setelah P1 selesai.

---

## 6. Acceptance criteria keseluruhan

1. 20 baris katalog PDF tersimpan sebagai master data terstruktur, idempoten, bisa di-seed berulang kali.
2. Kode ICD-10 dari PDF (12 kode baru) muncul di picker `ICD10_CODES` IGD.
3. Untuk pasien IGD dengan kunjungan STEMI: EKG yang di-input lewat form existing menghasilkan delta menit, dan jika > 8 menit (80% dari target 10) tampil peringatan SLA breach.
4. Prosedur berisiko HIGH/CRITICAL yang dipilih memunculkan keharusan verifikasi consent sebelum tindakan bisa disimpan.
5. Varians SLA tercatat sebagai `InsidenKeselamatan` (via jalur `LogbookKejadian`-compatible) tanpa duplikasi.
6. Seluruh suite `pasien` + `akreditasi` tetap hijau kecuali 1 failure baseline yang sudah ada.
7. Tidak ada endpoint baru yang menulis data tanpa `@login_required` + validasi input.

---

## 7. Di luar scope (eksplisit)

- Push notification ke perangkat/nurse station (butuh scheduler/websocket — tidak ada di repo).
- Integrasi BPJS V-Claim / SatuSehat nyata (tetap simulasi, lihat plan dasbor pendaftaran).
- Backfill data lama: `icd9_tindakan` lama tetap teks bebas, tidak di-parse retroaktif.
- Memperbaiki `KontrolQueryBudgetTest` yang sudah gagal sebelum pekerjaan ini.
- Migrasi `waktu_asesmen_dokter` dari `CharField` ke `DateTimeField` (breaking; butuh plan terpisah + backup data).
