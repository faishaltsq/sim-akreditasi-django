# Analisis — Peta Distribusi Filtering INM pada Dashboard ARIMA

Sumber: `Berikut adalah tabel usulan Peta Distribusi Indikator Nasional Mutu.docx` (13 INM, 3 catatan logika sistem).
Tanggal analisis: 2026-10-19. Basis kode: worktree `medaka`, commit `ba6d72c`, migrasi terakhir `0040_risikounit_arah_capaian`.

---

## 1. Ringkasan isi dokumen

| No | INM | Unit PJ | Cakupan unit terkait |
|----|-----|---------|----------------------|
| 1 | Kepatuhan Kebersihan Tangan (KKT) | Komite PPI | 13 unit klinis + penunjang + sanitasi |
| 2 | Kepatuhan Penggunaan APD | Komite PPI | 12 unit (tambah CSSD, Laundry, Limbah) |
| 3 | Kepatuhan Identifikasi Pasien | KMKP | 11 unit (tambah Kasir/Pendaftaran, Rehab Medik) |
| 4 | Waktu Tanggap SC Emergency ≤ 30 menit | IGD / VK | 7 unit (Rajal/Poli **tidak muncul**) |
| 5 | Waktu Tunggu Rawat Jalan ≤ 60 menit | IRJA | 4 kelompok (Ranap/ICU **tidak muncul**) |
| 6 | Penundaan Operasi Elektif < 5% | IBS | 5 unit (Non-bedah/Gizi **tidak muncul**) |
| 7 | Kepatuhan Waktu Visite Dokter ≥ 80% | Bidang Medis | Ranap, ICU/ICCU, HCU (Rajal/Penunjang **tidak muncul**) |
| 8 | Pelaporan Hasil Kritis Lab 100% | Instalasi Lab | 5 unit (Farmasi/Gizi/Kasir **tidak muncul**) |
| 9 | Kepatuhan Fornas / Formularium RS | Instalasi Farmasi | Farmasi, Komite Medik, **seluruh dokter DPJP** |
| 10 | Kepatuhan Clinical Pathway | Komite Medik | 3 bangsal + RM + Komite Mutu |
| 11 | Kepatuhan Pencegahan Risiko Pasien Jatuh | KMKP | Ranap, ICU/ICCU, IGD, Rehab, Radiologi |
| 12 | Kecepatan Respon Komplain | Humas | Humas/CS, **seluruh Kepala Instalasi/Ruangan** |
| 13 | Kepuasan Pasien dan Keluarga | Humas / Komite Mutu | Poli, Ranap, IGD, Farmasi, Kasir, Penunjang |

Tiga catatan logika sistem yang diminta:

1. **RBAC** — saat login sebagai Kepala Unit, sistem membaca ID Unit Kerja dan hanya menampilkan INM yang dipetakan.
2. **Auto-hide** — INM yang tidak relevan disembunyikan total (contoh: SC Emergency & Penundaan Operasi Elektif hilang dari Bangsal Anak).
3. **Penyatuan grafis** — tren bulanan + capaian target INM khusus unit tersebut, tanpa bercampur angka nasional/RS.

---

## 2. Kondisi kode saat ini (terverifikasi)

| Fakta | Lokasi |
|---|---|
| Tidak ada model mapping INM↔unit sama sekali (`IndikatorUnitTerlibat` / `inm_unit_mapping` = 0 hits) | grep `akreditasi/**` |
| `IndikatorMutu.unit` = **1 FK tunggal** (nullable) ke `UnitKerja` | `akreditasi/risiko_models.py:562` |
| `CatatanIndikator` **tanpa kolom `unit`**, `unique_together ('indikator','bulan','tahun')` | `akreditasi/risiko_models.py:606-624` |
| `CatatanIndikator.tercapai` sudah menghormati `arah_target` MIN/MAX | `akreditasi/risiko_models.py:636-641` |
| `CatatanIndikator.save()` auto-membuat draft `RisikoUnit` saat di bawah target (idempotent per indikator+unit) | `akreditasi/risiko_models.py:652+` |
| Filter unit hari ini: `Q(unit_id__in=unit_ids) \| Q(jenis='NASIONAL')` → **semua unit melihat SEMUA indikator NASIONAL** | `akreditasi/indikator_views.py:169`, `akreditasi/views.py:378` |
| Logika subtree unit **di-copy 3×**, kedalaman maksimal 2 (`pk=u \| parent=u \| parent__parent=u`) | `indikator_views.py:167`, `views.py:147`, `views.py:376` |
| `_is_manager` = SUPER_ADMIN / ADMIN_RS / KOORDINATOR / KEPALA_UNIT | `indikator_views.py:122-127` |
| `profile.is_unit_scoped` = bukan superuser/SUPER_ADMIN/ADMIN_RS/DIREKTUR **dan** punya `unit_kerja` | `accounts/models.py:177-181` |
| `UnitKerja` = tree `parent`/`level`, `tipe_unit`, 219 unit aktif, kedalaman 1–5 | `akreditasi/models.py:33-60` |
| Halaman terkait: `indikator_dashboard` (`templates/akreditasi/indikator_dashboard.html`, 970 baris), `indikator_input_capaian`, `api_indikator_tren`, `api_indikator_komparasi_unit`, `views.api_mutu_indikator`, `views.dashboard` | `akreditasi/urls.py` |

### 2.1 Data katalog INM di DB (lokal, identik struktur dengan produksi)

```
jenis        count
IMP_RS        98
IMP_UNIT      76
NASIONAL      36   ← 14 kanonik INM-01..INM-14 + 22 duplikat per-bangsal
```

Contoh duplikasi yang akan langsung terlihat di dropdown bila mapping tidak membedakan:

```
INM-01                  Kepatuhan Kebersihan Tangan (KKT)            unit=48
BAB-HD-INM-01           Kepatuhan Kebersihan Tangan (≥ 85%)          unit=23
BAB-INTERNA-INM-01      Kepatuhan Kebersihan Tangan (≥ 85%)          unit=218
BAB-KARDIOLOGI-INM-02   Kepatuhan Kebersihan Tangan (≥ 85%)          unit=217
BAB-MATA-INM-02         Kepatuhan Kebersihan Tangan (≥ 85%)          unit=215
BAB-NEUROLOGI-INM-02    Kepatuhan Kebersihan Tangan (≥ 85%)          unit=216
BAB-NIFAS-INM-02        Kepatuhan Kebersihan Tangan (≥ 85%)          unit=135
BAB-ORTHOPEDI-INM-02    Kepatuhan Kebersihan Tangan (≥ 85%)          unit=214
BAB-RANAP-BEDAH-INM-01  Kepatuhan Kebersihan Tangan (≥ 85%)          unit=128
```

**Artinya: mekanisme input per-unit sudah ada** — berupa baris indikator turunan `BAB-*-INM-*` yang masing-masing punya `unit_id` dan punya `CatatanIndikator` sendiri. Yang belum ada hanyalah **relasi eksplisit** antara baris turunan dan INM induknya, sehingga dashboard memperlakukannya sebagai 8 indikator berbeda, bukan 1 INM dengan 8 realisasi unit.

### 2.2 Ketidaksesuaian nomor & nama docx vs DB

| Docx | Isi docx | Baris DB | Status |
|---|---|---|---|
| #1 | KKT | `INM-01` | cocok |
| #2 | APD | `INM-02` | cocok |
| #3 | Identifikasi Pasien | `INM-03` | cocok |
| #4 | **Waktu Tanggap SC Emergency ≤30 mnt** | `INM-04` = *Waktu Tanggap Gawat Darurat ≤5 mnt* — **beda indikator** | SC hanya ada sebagai `BAB-VK-INM-01` |
| #5 | Waktu Tunggu Rajal ≤60 mnt | `INM-06` | nomor geser |
| #6 | Penundaan Operasi Elektif <5% | `INM-05` | nomor geser |
| #7 | **Waktu Visite Dokter ≥80%** | **tidak ada** | harus dibuat |
| #8 | Hasil Kritis Lab 100% | `INM-12` | nomor geser |
| #9 | Fornas | `INM-07` | nomor geser |
| #10 | Clinical Pathway | `INM-08` | nomor geser |
| #11 | Risiko Jatuh | `INM-09` | nomor geser |
| #12 | Respon Komplain | `INM-10` | nomor geser |
| #13 | Kepuasan Pasien | `INM-11` | nomor geser |
| — | — | `INM-13` SBAR/TBK, `INM-14` Surgical Safety Checklist | ada di DB, tidak di docx |

**Konsekuensi:** seeding berdasarkan urutan nomor akan salah total. Seeding wajib berbasis pencocokan nama/kata kunci, dengan laporan baris yang tidak cocok — jangan pernah mengarang.

### 2.3 Kualitas data yang ikut terbawa

- `arah_target` tidak konsisten: `BAB-INTERNA-INM-02` (Risiko Jatuh, target 100) diberi `MAX`, seharusnya `MIN`. `BAB-VK-INM-01` (SC Emergency ≤30 mnt, target 80) diberi `MIN`, seharusnya `MAX` (semakin cepat semakin baik).
- `INM-09` Risiko Jatuh target 100 `MIN` benar, tetapi `BAB-*-INM-02` untuk indikator yang sama memakai `MAX` → dua formula berbeda untuk satu INM.
- 22 baris `BAB-*` memakai `jenis='NASIONAL'`, bukan `IMU`, sehingga tercampur ke katalog nasional.

### 2.4 Struktur pohon unit yang tidak seragam

```
PELAKSANA-TEKNIS
├── IRIN (lvl 2)          → 12 anak bangsal (BANGSAL-ANAK, BANGSAL-DEWASA, ...)
└── IRJ  (lvl 2)          → 7 anak poli (POLI-PD, POLI-BEDAH, ...)

BID-YAN
├── RANAP (lvl 3)         ← "Instalasi Rawat Inap" versi lain, TIDAK di bawah IRIN
├── IGD   (lvl 3)
├── VK    (lvl 3)
└── RAJAL (lvl 3)         ← "Instalasi Rawat Jalan" versi lain, TIDAK di bawah IRJ
```

- "Instalasi Rawat Inap" pada dokumen **bukan satu node**, melainkan gabungan subtree `IRIN` + subtree `RANAP`.
- "IRJA" pada dokumen harus dipetakan ke `IRJ` + `RAJAL` (+ `POLI-*` sebagai turunan).
- Unit level 4–5 (mis. `RUANG-PRIA-KELAS2` di bawah `RUANG-PRIA`) **tidak akan pernah** terjangkau oleh resolver kedalaman-2 yang ada sekarang.
- `HUMAS-CS` berada di level 1 tanpa induk — tidak akan terjangkau resolver berbasis subtree mana pun kecuali dipetakan langsung.

### 2.5 Dua baris docx bersifat role-based, bukan unit-based

- #9 Fornas → "seluruh dokter DPJP Rawat Inap & Rawat Jalan"
- #12 Respon Komplain → "seluruh Kepala Instalasi / Kepala Ruangan"

Keduanya tidak bisa dinyatakan sebagai daftar unit. Perlu mekanisme grant tambahan berbasis role, atau diperlakukan sebagai unit-wide (semua unit) — keputusan ini harus eksplisit, bukan tersirat.

---

## 3. Gap terhadap kebutuhan dokumen

| Kebutuhan dokumen | Kondisi sekarang | Gap |
|---|---|---|
| Filter INM per unit | Semua unit melihat semua `jenis='NASIONAL'` | **Belum ada** — inilah inti pekerjaan |
| Auto-hide INM tidak relevan | Tidak ada mekanisme | Belum ada |
| Capaian INM **khusus unit** | 1 angka per indikator per bulan; angka "unit" hanya ada pada baris `BAB-*` | Perlu relasi induk→turunan agar terbaca sebagai satu INM |
| Grafik tren tanpa campur data RS | Dashboard menampilkan agregat seluruh indikator terfilter | Perlu pemisahan agregat RS vs realisasi unit |
| RBAC tidak memperlebar otorisasi | `is_unit_scoped` sudah ada | Harus dipertahankan, mapping hanya memfilter visibilitas |

---

## 4. Risiko implementasi

| # | Risiko | Dampak | Mitigasi |
|---|---|---|---|
| R1 | Mapping kosong dianggap "tidak ada akses" | Seluruh menu INM hilang di produksi (0 baris mapping saat ini) | Mapping kosong untuk unit user = **tidak dibatasi** (degradasi anggaran), diuji eksplisit |
| R2 | Mengubah `unique_together` `CatatanIndikator` | Menyentuh 588 baris 2026; `unit NULL` vs unique index berbeda antar-engine (SQLite vs Postgres) | **Tidak perlu diubah** — pakai relasi induk→turunan yang sudah punya `unit_id` sendiri |
| R3 | Seeding berdasarkan nomor | Salah petakan 8 dari 13 INM | Seed berbasis nama + laporan baris tak cocok, tidak mengarang |
| R4 | Duplikasi dropdown (`INM-01` + 8 `BAB-*`) | Operator bingung, angka dobel | Katalog hanya `inm_induk IS NULL`; turunan muncul sebagai realisasi unit |
| R5 | `float` masuk `<script>` tanpa `|unlocalize` | Locale `id` menulis `1,5` → seluruh blok JS mati (bug `84c20ce`, `c4c2a3c`) | Wajib `{% load l10n %}` + `|unlocalize` di setiap template yang disentuh |
| R6 | Resolver kedalaman-2 dipertahankan | Unit level 4–5 kehilangan akses | Ganti dengan walk `UnitKerja.parent` rekursif di satu helper |
| R7 | Dua formula status | Laporan berbeda antara dashboard dan evaluasi | Hanya pakai `CatatanIndikator.tercapai` / `RisikoUnit.capaian_evaluasi`, tanpa aritmetika baru |

---

## 5. Keputusan desain yang diusulkan

**D1 — Tabel mapping tunggal sebagai sumber kebenaran.**
`InmUnitMapping(indikator, unit, is_pj, boleh_input, role_scope)`. Satu baris = satu hak lihat/input.

**D2 — Relasi induk→turunan, bukan kolom `unit` di `CatatanIndikator`.**
Tambah `IndikatorMutu.inm_induk` (self-FK, nullable). Baris `BAB-*-INM-*` di-backfill menunjuk ke `INM-*` kanonik. Ini memanfaatkan struktur yang sudah ada, menghindari migrasi berisiko pada 588 baris capaian.

**D3 — Resolver tunggal `inm_qs_for_user(profile, qs)`** dipakai oleh kelima read path, menggantikan tiga salinan logika subtree.

**D4 — Degradasi anggaran.** Unit tanpa mapping = tidak dibatasi. Auto-hide hanya aktif setelah mapping unit tersebut ada.

**D5 — Dua INM baru** dibuat agar docx terpenuhi: `INM-15` Waktu Visite Dokter, `INM-16` Waktu Tanggap SC Emergency; `BAB-VK-INM-01` dijadikan turunan `INM-16`.

**D6 — Role grant untuk baris #9 dan #12** ditangani lewat kolom `role_scope` pada mapping (mis. `DPJP`, `KEPALA_UNIT`) sehingga tidak memaksa mendaftar 200+ unit.

---

## 6. Rekomendasi urutan eksekusi

1. **Fase 1 (aman, tanpa sentuh data capaian):** model mapping + resolver + auto-hide + seed 13 baris. Menjawab 90% kebutuhan dokumen.
2. **Fase 2:** `inm_induk` + backfill 22 baris `BAB-*` + agregasi induk di dashboard. Menjawab "capaian khusus unit".
3. **Fase 3:** role grant, halaman admin matriks, perbaikan `arah_target` yang salah.

Detail langkah ada di `docs/superpowers/plans/2026-10-19-inm-distribution-filter.md`.

---

## 7. Catatan tambahan

- Dokumen ini **tidak** menghapus `INM-04`, `INM-13`, `INM-14` yang tidak tercantum di docx; docx adalah usulan distribusi, bukan daftar definitif. Yang dilakukan hanya menambah `INM-15` dan `INM-16` yang memang belum ada.
- Nama unit pada docx memakai singkatan lokal (IRJA vs `IRJ`, ICU/ICCU, VK/Kebidanan). Tabel pemetaan eksplisit nama→kode unit ada di plan, bukan diasumsikan.
- Jumlah unit aktif 219 dengan kedalaman sampai 5 level; setiap perluasan mapping harus lewat subtree, bukan daftar manual.
