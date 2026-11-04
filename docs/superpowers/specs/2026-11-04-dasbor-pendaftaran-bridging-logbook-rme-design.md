# Design Spec: Integrasi Dasbor Pendaftaran (Bridging NIK/DPJP, Logbook & Shift Staf, RME Ringkas & Antrean)

- **Tanggal**: 2026-11-04
- **Modul**: `pasien` (Pendaftaran & Admisi) & `templates/pasien/pendaftaran_dashboard.html`
- **Referensi Input**: `Tambahan menu di pendaftaran.docx`

---

## 1. Latar Belakang & Ringkasan Solusi

Pengguna menginginkan fitur-fitur dari dokumen `Tambahan menu di pendaftaran.docx` diintegrasikan ke sistem:
1. **Sidebar Kiri**: Tidak menambah menu terpisah di sidebar kiri; menu tetap tunggal `Pendaftaran & Admisi` (`pasien:pendaftaran_dashboard`).
2. **Dasbor Pendaftaran**: Menjadi pusat kendali tunggal (*one-stop registration desk*) yang memuat:
   - **Bridging API (V-Claim BPJS & SatuSehat Kemenkes)**: Auto-fetch identitas pasien berbasis 16 digit NIK dan penyaringan otomatis dokter DPJP sesuai poliklinik tujuan.
   - **Jadwal Dinas & Logbook Harian Staf Pendaftaran**: Pencatatan shift kerja (Pagi/Siang/Malam) dan catatan kegiatan/kendala operasional staf loket.
   - **RME Ringkas & Manajemen Antrean Loket**: Penapisan tanda-tanda vital (TTV) awal dan pemanggilan antrean loket langsung dari baris tabel kunjungan hari ini.

Prinsip perancangan: **YAGNI & Non-Redundant**. Field klinis dan antrean memanfaatkan model `KunjunganPasien` yang sudah ada, tanpa membuat duplikasi tabel.

---

## 2. Arsitektur Komponen

```
[Browser: Dasbor Pendaftaran]
   │
   ├─► [1] Input 16 Digit NIK ───► AJAX GET /pasien/api/v1/cek-nik/
   │                                   │
   │                                   └─► pasien.bridging_services.BPJSVClaimService / SatuSehatService
   │                                           └─► Auto-populate form Pasien Baru
   │
   ├─► [2] Pilih Poli Tujuan   ───► AJAX GET /pasien/api/v1/filter-dpjp/?poli=...
   │                                   │
   │                                   └─► Filter DPJP sesuai spesialisasi klinis
   │
   ├─► [3] Tab 8: Shift & Logbook ─► GET/POST /pasien/pendaftaran/ (Context + Modal Form)
   │                                   │
   │                                   ├─► JadwalDinasAdmission (Shift dinas loket)
   │                                   └─► LogbookHarianAdmission (Uraian kegiatan & kendala)
   │
   └─► [4] Tabel Kunjungan Hari Ini
           ├─► Modal "RME Awal" ──► AJAX POST /pasien/api/v1/kunjungan/<id>/rme/
           │                           └─► Simpan TTV (Sistole, Diastole, Nadi, Suhu, RR) ke KunjunganPasien
           └─► Tombol "Panggil" ──► AJAX POST /pasien/api/v1/kunjungan/<id>/antrean/
                                       └─► Update status antrean (MENUNGGU -> DIPANGGIL -> SELESAI)
```

---

## 3. Skema Data (Data Models)

### A. Model Baru di `pasien/models.py`

```python
class JadwalDinasAdmission(models.Model):
    """Pencatatan shift dinas petugas loket pendaftaran & admisi."""
    SHIFT_CHOICES = [
        ('PAGI', 'Shift Pagi (07:00 - 14:00)'),
        ('SIANG', 'Shift Siang (14:00 - 21:00)'),
        ('MALAM', 'Shift Malam (21:00 - 07:00)'),
    ]
    petugas = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='jadwal_admission')
    tanggal = models.DateField('Tanggal Dinas')
    shift = models.CharField('Shift Kerja', max_length=20, choices=SHIFT_CHOICES)
    status_kehadiran = models.CharField('Status Kehadiran', max_length=20, default='Hadir')
    catatan = models.CharField('Catatan / Keterangan', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Jadwal Dinas Pendaftaran'
        verbose_name_plural = 'Jadwal Dinas Pendaftaran'
        ordering = ['-tanggal', 'shift']


class LogbookHarianAdmission(models.Model):
    """Logbook akuntabilitas kinerja harian dan kendala staf loket pendaftaran."""
    petugas = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logbook_admission')
    tanggal = models.DateField('Tanggal Catatan', default=timezone.localdate)
    jam_aktivitas = models.TimeField('Jam Aktivitas', auto_now_add=True)
    kegiatan = models.TextField('Uraian Kegiatan Pelayanan')
    kendala = models.TextField('Kendala Operasional', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Logbook Harian Pendaftaran'
        verbose_name_plural = 'Logbook Harian Pendaftaran'
        ordering = ['-tanggal', '-jam_aktivitas']
```

### B. Model Eksisting (`pasien.KunjunganPasien`)
Memanfaatkan field native yang telah ada:
- `nomor_antrean` & `status_antrean` (`MENUNGGU`, `DIPANGGIL`, `SEDANG_DILAYANI`, `SELESAI`)
- `ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_suhu`, `ttv_rr`
- `catatan_admisi` & `diagnosa_masuk`

---

## 4. Layanan Bridging & API Endpoints

### A. `pasien/bridging_services.py`
1. `BPJSVClaimService`:
   - Method `cek_peserta_by_nik(nik)`:
     - Jika format NIK 16 digit valid, kembalikan simulasi payload standar BPJS V-Claim:
       - `nama`: auto-generate atau lookup berbasis data acuan
       - `noKartu`: format BPJS 13 digit
       - `sex`: `L` / `P`
       - `tglLahir`: `YYYY-MM-DD`
       - `hakKelas`: `{"keterangan": "Kelas 1 / Kelas 2 / Kelas 3"}`
       - `statusPeserta`: `{"keterangan": "AKTIF"}`
2. `SatuSehatService`:
   - Method `get_patient_by_nik(nik)`:
     - Mengembalikan format FHIR Patient resource (`identifier`, `name`, `gender`, `birthDate`).

### B. Endpoint API di `pasien/views.py` & `pasien/urls.py`
1. `GET /pasien/api/v1/cek-nik/?nik=...`:
   - Validasi panjang NIK (16 digit).
   - Cari di lokal database dulu; jika belum ada, panggil `BPJSVClaimService.cek_peserta_by_nik(nik)`.
   - Mengembalikan JSON: `status: 'success' | 'not_found' | 'error'`, `nama_lengkap`, `no_bpjs`, `tanggal_lahir`, `jenis_kelamin`, `kelas_bpjs`.
2. `GET /pasien/api/v1/filter-dpjp/?poli=...`:
   - Menerima kode/nama poliklinik (misal `POLI_JANTUNG`, `POLI_ANAK`, dll).
   - Mengembalikan daftar dokter spesialis yang relevan dari `DPJP_CHOICES` / `Pegawai`.
3. `POST /pasien/api/v1/kunjungan/<id>/rme/`:
   - Menerima payload JSON/Form: `ttv_sistole`, `ttv_diastole`, `ttv_nadi`, `ttv_suhu`, `ttv_rr`, `catatan_admisi`.
   - Menyimpan ke instance `KunjunganPasien`.
4. `POST /pasien/api/v1/kunjungan/<id>/antrean/`:
   - Menerima parameter `status` (`DIPANGGIL` / `SELESAI`).
   - Memperbarui `status_antrean` pada `KunjunganPasien`.
5. `POST /pasien/pendaftaran/logbook/tambah/`:
   - Menyimpan entri logbook harian staf pendaftaran.
6. `POST /pasien/pendaftaran/jadwal/tambah/`:
   - Menyimpan jadwal dinas shift pendaftaran.

---

## 5. Perubahan Antarmuka (UI) di `pendaftaran_dashboard.html`

1. **Kotak 2 (Pasien Baru)**:
   - Event listener pada `#id_nik_baru`: ketika 16 digit terisi, tampilkan mini spinner dan jalankan request ke `/pasien/api/v1/cek-nik/`.
   - Berikan feedback visual badge "Terverifikasi V-Claim BPJS" dan auto-fill kolom Nama Lengkap, Tanggal Lahir, Jenis Kelamin, dan No. BPJS. Penjamin otomatis diset ke `BPJS`.
2. **Dropdown Poliklinik & DPJP Dinamis**:
   - Pilihan poliklinik memicu penyaringan opsi dropdown DPJP sehingga hanya menampilkan dokter spesialis terkait (dengan opsi "Semua Dokter" tetap tersedia).
3. **Tab 8: Shift & Logbook Staf**:
   - Ditambahkan sebagai tab ke-8 di navigasi dasbor pendaftaran.
   - Kolom kiri: Tabel Jadwal Dinas Hari Ini + tombol modal tambah jadwal.
   - Kolom kanan: Tabel Logbook Harian Staf + tombol modal tambah logbook.
4. **Tabel Kunjungan Pasien Hari Ini**:
   - Kolom **Status & Aksi** ditambahkan:
     - Tombol `[RME Awal]` bertanda badge TTV jika sudah diisi. Klik membuka modal input TTV (Sistole/Diastole, Nadi, Suhu, RR, Catatan).
     - Tombol `[Panggil Antrean]` yang memperbarui status antrean menjadi `DIPANGGIL` secara real-time.

---

## 6. Verifikasi & Pengujian

1. **Unit Test Bridging Service**:
   - Cek format respon V-Claim & SatuSehat saat NIK 16 digit valid dan invalid.
2. **Integration Test API Endpoint**:
   - `GET /pasien/api/v1/cek-nik/` menghasilkan HTTP 200 dengan data demografi.
   - `GET /pasien/api/v1/filter-dpjp/` mengembalikan daftar dokter sesuai poli.
   - `POST /pasien/api/v1/kunjungan/<id>/rme/` berhasil menyimpan TTV.
   - `POST /pasien/api/v1/kunjungan/<id>/antrean/` berhasil mengubah status antrean.
3. **Regression Test**:
   - Menjalankan seluruh test suite `pasien/tests_revisi_pendaftaran_dua_kotak.py` dan `pasien/tests_revisi_pendaftaran_formulir.py` untuk memastikan form Kotak 1 & Kotak 2 tetap bekerja 100%.
