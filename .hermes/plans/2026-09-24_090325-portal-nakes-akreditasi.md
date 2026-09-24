# Rencana Implementasi: Akun Nakes & Portal Capaian Akreditasi Unit (SIK AP)

## 1. Goal
Menambahkan role `STAF_NAKES` pada sistem RBAC, membangun portal unit-aware bagi tenaga kesehatan untuk memantau capaian skor akreditasi unit kerjanya, mengakses SOP telusur surveior, mengunggah bukti pelaksanaan, **serta modul portofolio pribadi nakes (Bab KPS): unggah STR, SIP, dan sertifikat pelatihan wajib (Opsi B Lengkap)**.

---

## 2. Context & Riset Domain Akreditasi Rumah Sakit (STARKES / KARS)

### Mengapa Perlu Akun Khusus Tiap Nakes di RS?
Berdasarkan standar akreditasi rumah sakit Kementerian Kesehatan RI (STARKES 2022/2024) dan pedoman survei lembaga akreditasi (seperti KARS, LAM-KPRS, LARS, dll.):
1. **Keterlibatan Seluruh Staf (Hospital-Wide Engagement)**: Akreditasi bukan hanya tugas Tim Mutu/Admin RS, melainkan operasional harian seluruh Professional Pemberi Asuhan (PPA: Dokter DPJP, Perawat, Bidan, Apoteker, Nutrisionis, Penata Anestesi).
2. **Kesiapan Wawancara & Observasi Surveior (Metode RDWOS: W & O)**:
   - Surveior akreditasi melakukan kunjungan langsung (telusur) ke unit kerja (IGD, ICU, Rawat Inap, Kamar Bedah, Farmasi, dll.).
   - Surveior akan menguji nakes secara acak: *"Berapa kepatuhan cuci tangan di ruangan ini?", "Apa saja indikator mutu prioritas unit Anda?", "Mana SPO penanganan pasien kritis / code blue?"*.
   - Jika nakes tidak memiliki akses ke sistem, mereka tidak mengetahui posisi skor kepatuhan unit mereka dan gagap saat telusur surveior.
3. **Standar KPS (Kualifikasi dan Pendidikan Staf)**:
   - Standar KPS 1-17 mewajibkan pencatatan kredensial nakes (STR, SIP, RKK/SPK), pelatihan wajib (BHD/BLS, PPI, Keselamatan Pasien, K3RS), dan evaluasi kinerja (OPPE/FPPE).
4. **Pembagian Beban Pembuktian Dokumen (Crowdsourced Evidence)**:
   - Nakes di unit pelayanan adalah pihak yang menghasilkan bukti fisik harian (notulen morning report, checklist serah terima pasien SBAR, audit bundle IDO/ISK). Portal nakes memungkinkan mereka langsung melihat apa bukti yang kurang di unit mereka.

---

## 3. Asumsi & Kondisi Saat Ini
1. **Model RBAC Existing (`accounts/models.py`)**:
   - Memiliki 5 tier: `SUPER_ADMIN` (level 5), `ADMIN_RS` (4), `KOORDINATOR_POKJA` (3), `KEPALA_UNIT` (2), `ASESOR` (1).
   - `UserProfile` memiliki relasi `unit_kerja` (`ForeignKey` ke `akreditasi.UnitKerja`).
2. **Keterkaitan Data di Akreditasi (`akreditasi/models.py`)**:
   - `QualityRecord` menghubungkan `StandardItem` (EP) dengan `UnitKerja` (`unit`).
   - `QualityRecord` menyimpan baseline, skor (10, 5, 0), indikator mutu (Plan), catatan evaluasi (Check), dan action plan (Action).
   - `EvidenceReq` (kategori R/D/W/O/S) menampung `EvidenceFile` yang diunggah.
3. **Kekurangan Saat Ini**:
   - Nakes belum memiliki role khusus (hanya ada Kepala Unit atau Asesor).
   - Nakes tidak memiliki halaman dashboard ringkas yang langsung memfilter data hanya untuk unit kerja tempat dia bertugas. Jika nakes membuka matriks global, informasi terlalu luas dan membingungkan.

---

## 4. Arsitektur & Pendekatan yang Diusulkan (Opsi B: Lengkap)
1. **Model RBAC & Profil Nakes (`accounts/models.py`)**:
   - Role baru: `('STAF_NAKES', 'Staf Nakes / Pelaksana Unit')` (Level 1).
   - Field `profesi` pada `UserProfile` (Pilihan: Dokter Umum, Dokter Spesialis, Perawat, Bidan, Apoteker, Tenaga Teknis Kefarmasian, Radiografer, Pranata Laboratorium, Fisioterapis, Nutrisionis, Perekam Medis).
   - Field `nip_nrp` pada `UserProfile`.
2. **Model Baru Kredensial & Kualifikasi Staf (`accounts.NakesCredential` atau `akreditasi.NakesDocument`)**:
   - Kategori dokumen KPS:
     - `STR` (Surat Tanda Registrasi)
     - `SIP` (Surat Izin Praktik)
     - `SPK_RKK` (Surat Penugasan Klinis & Rincian Kewenangan Klinis)
     - `PELATIHAN_BHD` (Bantuan Hidup Dasar / BLS - KPS 8)
     - `PELATIHAN_PPI` (Pencegahan & Pengendalian Infeksi - PPI/KPS)
     - `PELATIHAN_PMKP` (Peningkatan Mutu & Keselamatan Pasien - PMKP)
     - `PELATIHAN_K3RS` (K3 & Keselamatan Kebakaran / APAR - MFK/KPS)
     - `LAINNYA` (Sertifikat Keahlian Khusus: ACLS, ATLS, BTCLS, Resusitasi Neonatus, dll.)
   - Field: nomor dokumen, tanggal berlaku sampai (expiry date), status verifikasi (`PENDING`, `VERIFIED`, `EXPIRED`), file berkas (Supabase storage / Django file).
3. **Halaman Khusus: Portal Nakes (`akreditasi:portal_nakes`)**:
   - URL: `/portal-nakes/`.
   - Menampilkan 4 tab inti:
     - **Tab 1: Capaian Akreditasi Unit Saya** (Skor EP, persentase kepatuhan, baseline, dan catatan perbaikan).
     - **Tab 2: Pustaka SOP & Regulasi Ruangan** (Dokumen R yang wajib dipahami nakes untuk wawancara surveior).
     - **Tab 3: Kirim Bukti Pelaksanaan Ruangan** (Form upload cepat laporan/checklist ke EP ruangan).
     - **Tab 4: Portofolio KPS Saya (STR/SIP/Pelatihan)** (Daftar dokumen kompetensi pribadi nakes, indikator masa kedaluwarsa STR/SIP, form upload scan berkas).
4. **Halaman Verifikasi KPS bagi Admin RS / Kepala Ruangan**:
   - Admin RS & Kepala Unit dapat melihat rekapitulasi kepatuhan berkas KPS seluruh nakes di unitnya untuk pembuktian survei Bab KPS.
5. **Smart Dashboard Redirect**:
   - Staf nakes diarahkan otomatis ke `/portal-nakes/` saat membuka root `/`.

---

## 5. Rencana Tugas Bertahap (Step-by-Step Tasks)

### Task 1: Menambahkan Role `STAF_NAKES`, Profesi, & Model `NakesCredential` di `accounts/models.py`
- **File**: `accounts/models.py`
- **Tujuan**: Mendaftarkan role Nakes dan wadah portofolio dokumen KPS (STR, SIP, Pelatihan, SPK/RKK).
- **Implementasi**:
  1. Tambah `STAF_NAKES` ke `ROLE_CHOICES` & `ROLE_HIERARCHY`.
  2. Tambah `PROFESI_CHOICES` (`DOKTER_SPESIALIS`, `DOKTER_UMUM`, `PERAWAT`, `BIDAN`, `APOTEKER`, `TTK`, `ANALIS_LAB`, `RADIOGRAFER`, `NUTRISIONIS`, `FISIOTERAPIS`, `PEREKAM_MEDIS`, `LAINNYA`).
  3. Tambah field `profesi` & `nip_nrp` di `UserProfile`.
  4. Buat model `NakesCredential`:
     ```python
     class NakesCredential(models.Model):
         DOC_TYPE_CHOICES = [
             ('STR', 'Surat Tanda Registrasi (STR)'),
             ('SIP', 'Surat Izin Praktik (SIP)'),
             ('SPK_RKK', 'Surat Penugasan Klinis & RKK'),
             ('PELATIHAN_BHD', 'Pelatihan BHD / BLS (KPS 8)'),
             ('PELATIHAN_PPI', 'Pelatihan PPI Dasar (PPI/KPS)'),
             ('PELATIHAN_PMKP', 'Pelatihan Mutu & Keselamatan Pasien'),
             ('PELATIHAN_K3RS', 'Pelatihan K3RS & APAR/Disaster'),
             ('PELATIHAN_LAIN', 'Sertifikat Kompetensi Khusus'),
         ]
         STATUS_CHOICES = [
             ('PENDING', 'Menunggu Verifikasi'),
             ('VERIFIED', 'Terverifikasi Tim Mutu/KPS'),
             ('REJECTED', 'Ditolak / Perlu Perbaikan'),
             ('EXPIRED', 'Kedaluwarsa'),
         ]
         user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='credentials')
         doc_type = models.CharField('Jenis Dokumen', max_length=30, choices=DOC_TYPE_CHOICES)
         title = models.CharField('Nama / Judul Dokumen', max_length=250)
         document_number = models.CharField('Nomor Dokumen/Sertifikat', max_length=100, blank=True)
         issued_date = models.DateField('Tanggal Terbit / Pelaksanaan', null=True, blank=True)
         valid_until = models.DateField('Masa Berlaku Sampai', null=True, blank=True)
         file_url = models.URLField('URL Dokumen (Cloud/Supabase)', max_length=500, blank=True)
         file = models.FileField('Berkas Scan', upload_to='kps/%Y/%m/', null=True, blank=True)
         status = models.CharField('Status Verifikasi', max_length=20, choices=STATUS_CHOICES, default='PENDING')
         verification_notes = models.TextField('Catatan Verifikator', blank=True)
         created_at = models.DateTimeField(auto_now_add=True)
     ```
- **Verifikasi**:
  ```bash
  python manage.py makemigrations accounts
  python manage.py migrate accounts
  ```

### Task 2: Update Form Pengguna & Form Portofolio KPS di `accounts/forms.py`
- **File**: `accounts/forms.py`
- **Tujuan**:
  - `UserProfileForm`: input `profesi`, `nip_nrp`, `unit_kerja`.
  - `NakesCredentialForm`: form upload mandiri berkas STR, SIP, sertifikat pelatihan nakes.

### Task 3: Buat View Portal Nakes & Upload Kredensial di `akreditasi/views.py` & `accounts/views.py`
- **File**: `akreditasi/views.py`, `accounts/views.py`, `akreditasi/urls.py`
- **Tujuan**:
  - View `portal_nakes(request)`:
    - Agregasi data EP spesifik `unit_kerja` nakes.
    - Hitung capaian kepatuhan unit (%).
    - Pustaka SOP ruangan (kategori R).
    - Portofolio kredensial user (`NakesCredential.objects.filter(user_profile=user.profile)`).
  - View `upload_kredensial(request)`:
    - Nakes upload STR/SIP/Sertifikat via Supabase storage.
  - View `rekap_kps_unit(request)`:
    - Kepala Unit / Tim Mutu memantau kelengkapan kredensial staf di unitnya.

### Task 4: Desain Template Portal Nakes 4-Tab (`templates/akreditasi/portal_nakes.html`)
- **File**: `templates/akreditasi/portal_nakes.html`
- **Fitur 4 Tab**:
  - **Tab 1: Capaian Unit Saya**: Scorecard EP unit, badge nilai (10/5/0), catatan evaluasi asesor.
  - **Tab 2: Pustaka SOP & Regulasi**: Dokumen R untuk siap telusur wawancara surveior.
  - **Tab 3: Kirim Bukti Ruangan**: Upload checklist / laporan harian unit.
  - **Tab 4: Portofolio KPS Saya**: Status STR/SIP (peringatan kedaluwarsa H-90 hari), daftar sertifikat pelatihan wajib (BHD, PPI, PMKP, K3RS), dan form unggah scan sertifikat.

### Task 5: Sidebar Navigasi, Redirect Cerdas, & Middleware Role
- **File**: `templates/includes/sidebar.html`, `akreditasi/views.py`
- **Tujuan**:
  - Di sidebar: tampilkan menu "Portal Nakes Saya" dan "Portofolio KPS".
  - Di `dashboard()`: jika role `STAF_NAKES`, redirect ke `akreditasi:portal_nakes`.

### Task 6: Data Uji & Seeding Akun Nakes Lengkap
- **File**: `akreditasi/management/commands/seed_nakes.py`
- **Tujuan**: Menyediakan contoh akun nakes dengan kredensial STR, SIP, dan sertifikat BHD terisi.

---

## 6. Rencana Pengujian (Test & Validation Plan)

### Automated Test Cases (`accounts/tests.py` & `akreditasi/tests.py`):
1. `test_user_profile_staf_nakes_role`:
   - Buat user dengan role `STAF_NAKES`.
   - Pastikan property `role_level` bernilai 1.
   - Pastikan `can_manage_users` bernilai `False`.
2. `test_portal_nakes_login_required`:
   - Anonymous user mengakses `/portal-nakes/` -> redirect ke login.
3. `test_portal_nakes_unit_filtering`:
   - Buat 2 unit: IGD dan ICU.
   - Buat nakes A di IGD, nakes B di ICU.
   - Login nakes A: pastikan data EP yang tampil hanya dari unit IGD.
4. `test_nakes_upload_evidence`:
   - Nakes mengunggah file bukti ke requirement EP unit kerjanya -> tersimpan dengan status DRAFT atau REVIEW.
5. `test_nakes_credential_create`:
   - Nakes membuat `NakesCredential` tipe STR -> tersimpan status `PENDING`.
6. `test_nakes_credential_expiry_warning`:
   - Credential dengan `valid_until` < 90 hari dari sekarang -> ditandai warning di portal.
7. `test_rekap_kps_admin_only`:
   - Nakes mengakses `/rekap-kps/` -> 403. Admin RS / Kepala Unit -> berhasil.

---

## 7. Risiko, Tradeoff, & Pertimbangan Keamanan

| Risiko / Isu | Mitigasi |
| :--- | :--- |
| **Akses Data Sensitif** | Nakes hanya baca skor & SOP unitnya. Menu pengaturan RS, audit log global, manajemen user ditutup via decorator `@login_required` + role check. |
| **Nakes Belum Terdaftar di Unit Kerja** | Tampilkan empty state informatif (*"Akun Anda belum ditautkan ke Unit Kerja. Hubungi Kepala Ruangan / Tim Mutu."*). |
| **Kinerja Loading** | `select_related` dan `prefetch_related` pada query EP unit. |
| **File KPS Sensitif (STR/SIP)** | Supabase storage bucket `kps/` diset private. Akses via signed URL sementara (expiry 1 jam). Hanya pemilik + admin yang bisa melihat. |
| **STR/SIP Kedaluwarsa** | Cron / scheduled check untuk auto-update status `NakesCredential` dari `VERIFIED` ke `EXPIRED` saat `valid_until < today`. Untuk MVP: cek saat portal dimuat. |

---

## 8. Keputusan User

**Opsi B (Lengkap dengan KPS) dipilih.**
Fitur mencakup: Portal Capaian Unit + Pustaka SOP + Upload Bukti + Portofolio Pribadi Nakes (STR, SIP, Sertifikat Pelatihan) + Rekap KPS Unit untuk Admin/Kepala Unit.
