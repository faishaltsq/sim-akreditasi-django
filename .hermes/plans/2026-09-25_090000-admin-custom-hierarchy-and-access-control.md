# Rencana Implementasi: Master Pusat Kontrol Admin — Kustomisasi Total Sistem Manajemen Akreditasi RS ("Sampai ke Akar-akarnya")

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun "Pusat Kontrol & Konfigurasi Sistem RS MonsisKami" terpadu di mana Administrator dapat mengustomisasi seluruh hierarki unit kerja (N-level fleksibel, reparenting, reordering, tipe unit, soft-archive), matriks hak akses & peran kustom (16 izin modular, custom role builder, user overrides), kustomisasi standar & ambang batas kelulusan akreditasi (passing grades), kustomisasi matriks risiko & IKP, konfigurasi kredensial KPS, identitas/branding tema visual, serta fitur Mode Kunci Survei (*Surveyor Read-Only Freeze*).

**Architecture:** 
1. Penambahan model konfigurasi terpusat: `SystemConfig` (menyimpan parameter global RS: ambang batas Paripurna/Utama/Madya, peringatan kedaluwarsa KPS, batas upload, survey freeze mode, dan tema warna), `RolePermissionConfig` (menyimpan izin 16 modul per peran bawaan & kustom), serta ekspansi model `UnitKerja` (dukungan N-level tanpa hardcode clamp, field `order`, `tipe_unit`, `is_active`).
2. Engine RBAC cerdas berbasis `UserProfile.has_permission(perm_code)` yang mengevaluasi hierarki: `is_superuser` -> `Survey Freeze Mode` -> `custom_permissions` (user override) -> `RolePermissionConfig` -> safe fallback.
3. Halaman terpadu `/accounts/kontrol/` dengan 5 tab interaktif:
   - **Tab 1: 🌳 Hierarki & Organisasi Unit** (Reparenting, urutan, klasifikasi, status aktif)
   - **Tab 2: 🛡️ Peran & Matriks Hak Akses** (Role customizer, matriks 16 izin, user override)
   - **Tab 3: 🎯 Standar, Pokja & Ambang Batas Akreditasi** (Passing grade thresholds, scoring scale, custom Pokja)
   - **Tab 4: ⚠️ Kebijakan Risiko, Insiden & KPS** (Risk matrix thresholds, SLA investigasi, alert window KPS)
   - **Tab 5: 🎨 Profil, Tema & Mode Survei** (Branding, kop surat, warna antarmuka, toggle freeze survei)

**Tech Stack:** Django 5.x, PostgreSQL / SQLite, Bootstrap 5.3.3, Vanilla JS / Fetch API, Django TestCase.

**Spec:** Kebutuhan pengguna: admin dapat mengustomisasi seluruh aspek sistem manajemen rumah sakit secara leluasa sampai ke akar-akarnya tanpa harus menyentuh kode program.

---

## 9 Domain Kustomisasi Total yang Dibuka untuk Admin

| Domain | Sebelum (Hardcoded) | Sesudah (Customizable oleh Admin) |
|---|---|---|
| **1. Hierarki Unit** | Terbatas 3 level, urutan statis, tanpa klasifikasi | N-level (bebas bertingkat), drag/select reparenting, custom sort order, 10 tipe unit, soft-archive |
| **2. Peran & Hak Akses** | 6 role fix, izin hardcoded di model | Tambah Role baru, toggle 16 modul izin per role, user permission override |
| **3. Ambang Kelulusan** | Fix: Paripurna 80%, Utama 70%, Madya 60% | Nilai ambang batas kelulusan (%) bisa disesuaikan target RS |
| **4. Skala Penilaian EP** | Fix 0, 5, 10 | Standar 0, 5, 10 + dukungan opsi TDD (Tidak Dapat Diterapkan / Exclude Denominator) |
| **5. Dokumen RDWOS** | Terbatas 5 kode (R, D, W, O, S) | Tambah jenis pembuktian kustom (Foto, Audit, Kuesioner), atur batas MB & ekstensi berkas |
| **6. Matriks Risiko 5x5** | Rentang skor risiko & warna fix di kode | Kustomisasi threshold skor band risiko & warna HEX, tambah kategori risiko (K3RS, IT, Finansial) |
| **7. Insiden Pasien (IKP)** | Jenis & alur statis | Kustomisasi target SLA investigasi (KTD, Sentinel) & disposisi notifikasi otomatis |
| **8. Kredensial Nakes** | Jenis sertifikat terbatas, notifikasi fix 90 hari | Tambah jenis dokumen KPS, atur jendela peringatan kedaluwarsa (30/60/90/180 hari) |
| **9. Branding & Keamanan** | Warna & kop surat statis, sistem selalu terbuka | Upload logo, kop surat, pilihan tema visual (Teal, Blue, Emerald, Navy), Mode Kunci Survei (*Freeze*) |

---

## Global Constraints & Security

- **Super Admin Lockout Prevention**: Role `SUPER_ADMIN` dan `is_superuser=True` tidak dapat dicabut izin vital manajemennya untuk mencegah admin terkunci dari sistem.
- **Survey Freeze Mode Protection**: Saat Mode Kunci Survei aktif, seluruh pengguna biasa dan koordinator pokja beralih ke *Read-Only*, mencegah manipulasi data saat survei KARS lapangan.
- **Anti-Circular Tree Validation**: Validasi ketat saat memindahkan unit agar unit tidak bisa dijadikan anak dari dirinya sendiri atau dari turunannya.
- **Zero Broken History**: Unit atau Pokja yang diarsip tidak boleh dihapus dari database agar integritas `QualityRecord`, `EvidenceFile`, dan `AuditLog` historis tetap utuh 100%.

---

## Rincian File yang Dibuat / Dimodifikasi

- **Create**:
  - `akreditasi/system_models.py`: Model `SystemConfig`, `RolePermissionConfig`, `CustomDocType`.
  - `templates/accounts/admin_control_center.html`: Template antarmuka pusat kontrol (5 tab modular).
  - `docs/07_PANDUAN_PUSAT_KONTROL_AKSES_DAN_HIERARKI.md`: Buku panduan operasional konfigurasi lengkap.
- **Modify**:
  - `akreditasi/models.py`: Buka clamp limit level pada `UnitKerja`, tambah `order`, `tipe_unit`, `is_active`.
  - `accounts/models.py`: Sambungkan `UserProfile.has_permission()` ke `RolePermissionConfig` & `SystemConfig`.
  - `akreditasi/views.py` & `akreditasi/risiko_views.py`: Baca threshold penilaian dan matriks risiko dari `SystemConfig`.
  - `accounts/views.py`: Controller 5 tab pusat kontrol dan API endpoints pembaruan dinamis.
  - `accounts/urls.py`: Daftarkan rute baru kontrol admin.
  - `templates/includes/sidebar.html`: Integrasikan menu Pusat Kontrol Admin.
  - `templates/base.html`: Pasang dukungan dynamic theme color dan banner info saat *Survey Freeze Mode* aktif.
  - `accounts/tests.py` & `akreditasi/tests.py`: Unit tests komprehensif seluruh domain kustomisasi.

---

## Step-by-Step Implementation Tasks

### Task 1: Model Konfigurasi Sistem Terpusat (`SystemConfig`)

**Files:**
- Create: `akreditasi/system_models.py`
- Modify: `akreditasi/models.py`
- Test: `akreditasi/tests.py`

**Interfaces:**
- Produces: Model `SystemConfig` (Singleton pattern) untuk ambang batas kelulusan, peringatan KPS, survey freeze mode, dan tema warna.

- [ ] **Step 1: Tulis test untuk `SystemConfig` di `akreditasi/tests.py`**

```python
from django.test import TestCase
from akreditasi.system_models import SystemConfig

class SystemConfigTestCase(TestCase):
    def test_default_system_config_singleton(self):
        cfg = SystemConfig.get_solo()
        self.assertEqual(cfg.threshold_paripurna, 80)
        self.assertEqual(cfg.threshold_utama, 70)
        self.assertEqual(cfg.threshold_madya, 60)
        self.assertEqual(cfg.kps_alert_days, 90)
        self.assertFalse(cfg.survey_freeze_mode)
        self.assertEqual(cfg.theme_color, 'teal')

    def test_custom_thresholds_and_branding(self):
        cfg = SystemConfig.get_solo()
        cfg.threshold_paripurna = 85
        cfg.theme_color = 'blue'
        cfg.survey_freeze_mode = True
        cfg.save()

        loaded = SystemConfig.get_solo()
        self.assertEqual(loaded.threshold_paripurna, 85)
        self.assertEqual(loaded.theme_color, 'blue')
        self.assertTrue(loaded.survey_freeze_mode)
```

- [ ] **Step 2: Jalankan test untuk memverifikasi kegagalan**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test akreditasi.tests.SystemConfigTestCase
```
Expected: FAIL dengan `ModuleNotFoundError: No module named 'akreditasi.system_models'`.

- [ ] **Step 3: Implementasikan model `SystemConfig` di `akreditasi/system_models.py`**

```python
from django.db import models

class SystemConfig(models.Model):
    THEME_CHOICES = [
        ('teal', 'Teal Medis (Default RS MonsisKami)'),
        ('blue', 'Hospital Royal Blue'),
        ('emerald', 'Emerald Green Health'),
        ('navy', 'Dark Navy Slate'),
    ]

    # --- Standar Ambang Kelulusan KARS (%) ---
    threshold_paripurna = models.PositiveSmallIntegerField('Minimal Paripurna (%)', default=80)
    threshold_utama = models.PositiveSmallIntegerField('Minimal Utama (%)', default=70)
    threshold_madya = models.PositiveSmallIntegerField('Minimal Madya (%)', default=60)
    threshold_dasar = models.PositiveSmallIntegerField('Minimal Dasar (%)', default=20)

    # --- Mode Survei & Keamanan ---
    survey_freeze_mode = models.BooleanField(
        'Mode Kunci Survei (Read-Only Freeze)',
        default=False,
        help_text='Saat aktif, hanya Super Admin yang bisa mengedit. Seluruh staf & pokja beralih ke Mode Baca Saja.'
    )
    survey_freeze_message = models.CharField(
        'Pesan Banner Mode Survei',
        max_length=255,
        default='Sistem sedang dalam Mode Survei Akreditasi Lapangan. Penambahan/perubahan dokumen dinonaktifkan sementara.'
    )

    # --- Kredensial Nakes (KPS) ---
    kps_alert_days = models.PositiveIntegerField('Peringatan Expired STR/SIP (Hari)', default=90)
    allow_nakes_self_upload = models.BooleanField('Izinkan Nakes Unggah Dokumen Mandiri', default=True)

    # --- Berkas Bukti RDWOS ---
    max_upload_size_mb = models.PositiveIntegerField('Batas Maksimal Berkas (MB)', default=15)
    allowed_extensions = models.CharField('Ekstensi Berkas Diizinkan', max_length=150, default='pdf,docx,xlsx,jpg,png,jpeg')

    # --- Matriks Risiko & Insiden ---
    risk_threshold_sangat_tinggi = models.PositiveSmallIntegerField('Skor Sangat Tinggi (Merah)', default=20)
    risk_threshold_tinggi = models.PositiveSmallIntegerField('Skor Tinggi (Oranye)', default=15)
    risk_threshold_sedang = models.PositiveSmallIntegerField('Skor Sedang (Kuning)', default=10)
    risk_threshold_rendah = models.PositiveSmallIntegerField('Skor Rendah (Hijau)', default=5)

    # --- Tema & Branding ---
    theme_color = models.CharField('Warna Tema Sistem', max_length=20, choices=THEME_CHOICES, default='teal')
    kop_surat_text = models.TextField('Teks Kop Surat Resmi', blank=True, default='PEMERINTAH DAERAH / YAYASAN KESEHATAN\nRS MONSISKAMI (TIPE B)\nJl. Kesehatan No. 1, Jakarta')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Konfigurasi Sistem'
        verbose_name_plural = 'Konfigurasi Sistem'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
```
Import `SystemConfig` di `akreditasi/models.py`.

- [ ] **Step 4: Buat dan terapkan migrasi database**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py makemigrations akreditasi --name create_system_config
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py migrate akreditasi
```

- [ ] **Step 5: Verifikasi kelulusan test**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test akreditasi.tests.SystemConfigTestCase
```
Expected: PASS (OK).

- [ ] **Step 6: Commit Task 1**

```bash
git add akreditasi/system_models.py akreditasi/models.py akreditasi/tests.py akreditasi/migrations/
git commit -m "feat(config): buat model SystemConfig terpusat untuk kustomisasi total sistem"
```

---

### Task 2: Ekstensi Hierarki Unit Bebas (N-Level Depth, Ordering, Tipe Unit, Soft-Archive)

**Files:**
- Modify: `akreditasi/models.py`
- Test: `akreditasi/tests.py`

**Interfaces:**
- Menghapus pembatasan statis 3 level pada `UnitKerja.save()` sehingga mendukung hierarki kedalaman bebas (N-level: L1 Direksi, L2 Bidang, L3 Bagian, L4 Instalasi, L5 Ruangan/Depo).
- Menambahkan field `order`, `tipe_unit`, dan `is_active`.

- [ ] **Step 1: Tulis unit test untuk N-level hierarchy di `akreditasi/tests.py`**

```python
class NLevelHierarchyTestCase(TestCase):
    def test_n_level_depth_support(self):
        l1 = UnitKerja.objects.create(name="Direksi", code="DIR", order=1, tipe_unit="DIREKTORAT")
        l2 = UnitKerja.objects.create(name="Bidang Medis", code="BID-MED", parent=l1, tipe_unit="BAGIAN")
        l3 = UnitKerja.objects.create(name="Instalasi Rawat Inap", code="IRNA", parent=l2, tipe_unit="INSTALASI")
        l4 = UnitKerja.objects.create(name="Ruang Melati", code="RG-MELATI", parent=l3, tipe_unit="RUANGAN")
        l5 = UnitKerja.objects.create(name="Depo Farmasi Melati", code="DEPO-MELATI", parent=l4, tipe_unit="DEPO")

        self.assertEqual(l1.level, 1)
        self.assertEqual(l2.level, 2)
        self.assertEqual(l3.level, 3)
        self.assertEqual(l4.level, 4)  # Melewati limit lama (3)
        self.assertEqual(l5.level, 5)  # Melewati limit lama (3)
        self.assertIn("DIR > BID-MED > IRNA > RG-MELATI > DEPO-MELATI", l5.get_full_hierarchy())
```

- [ ] **Step 2: Jalankan test untuk memverifikasi kegagalan**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test akreditasi.tests.NLevelHierarchyTestCase
```
Expected: FAIL (karena `level` saat ini dibatasi `min(..., 3)`).

- [ ] **Step 3: Update `UnitKerja.save()` dan field model di `akreditasi/models.py`**

```python
    order = models.PositiveIntegerField('Urutan Tampilan', default=0)
    tipe_unit = models.CharField('Jenis / Kategori Unit', max_length=40, choices=TIPE_UNIT_CHOICES, blank=True, default='LAINNYA')
    is_active = models.BooleanField('Unit Aktif', default=True)

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1  # Mendukung N-Level dinamis tanpa clamp statis
        else:
            self.level = 1
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Migrasi database**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py makemigrations akreditasi --name n_level_unit_customization
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py migrate akreditasi
```

- [ ] **Step 5: Verifikasi kelulusan test**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test akreditasi.tests.NLevelHierarchyTestCase
```
Expected: PASS (OK).

- [ ] **Step 6: Commit Task 2**

```bash
git add akreditasi/models.py akreditasi/tests.py akreditasi/migrations/
git commit -m "feat(unit): dukung hierarki N-level tanpa batas, kustomisasi urutan, tipe unit, dan soft-archive"
```

---

### Task 3: Matriks Hak Akses Peran Dinamis & Custom Role Engine

**Files:**
- Modify: `accounts/models.py`
- Test: `accounts/tests.py`

**Interfaces:**
- Produces: Model `RolePermissionConfig` untuk 16 izin modular per peran.
- Method `UserProfile.has_permission(perm_code)` yang memperhitungkan *Survey Freeze Mode* dan *User Permission Overrides*.

- [ ] **Step 1: Tulis unit test untuk dynamic RBAC dan survey freeze di `accounts/tests.py`**

```python
class DynamicRBACAndFreezeTestCase(TestCase):
    def setUp(self):
        self.u_admin = User.objects.create_superuser('sa', 'sa@rs.id', 'pass')
        self.p_admin = UserProfile.objects.create(user=self.u_admin, role='SUPER_ADMIN')

        self.u_nakes = User.objects.create_user('nakes1', 'nakes@rs.id', 'pass')
        self.p_nakes = UserProfile.objects.create(user=self.u_nakes, role='STAF_NAKES')

    def test_permission_customization_per_role(self):
        cfg = RolePermissionConfig.get_config_for_role('STAF_NAKES')
        self.assertFalse(self.p_nakes.has_permission('can_edit_pdca'))

        # Admin kustomisasi peran Staf Nakes agar boleh edit PDCA
        cfg.can_edit_pdca = True
        cfg.save()
        self.assertTrue(self.p_nakes.has_permission('can_edit_pdca'))

    def test_survey_freeze_mode_blocks_edit_for_non_superadmin(self):
        sys_cfg = SystemConfig.get_solo()
        sys_cfg.survey_freeze_mode = True
        sys_cfg.save()

        # Nakes terblokir edit saat freeze mode aktif
        self.assertFalse(self.p_nakes.has_permission('can_edit_pdca'))
        # Superadmin tetap bisa edit
        self.assertTrue(self.p_admin.has_permission('can_edit_pdca'))
```

- [ ] **Step 2: Jalankan test untuk memverifikasi kegagalan**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test accounts.tests.DynamicRBACAndFreezeTestCase
```
Expected: FAIL.

- [ ] **Step 3: Implementasikan `RolePermissionConfig` dan update `UserProfile` di `accounts/models.py`**

Tambahkan 16 field izin modular, method `get_config_for_role()`, `reset_to_defaults()`, dan integrasikan dengan `SystemConfig.get_solo().survey_freeze_mode`.

- [ ] **Step 4: Migrasi database**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py makemigrations accounts --name dynamic_role_permissions
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py migrate accounts
```

- [ ] **Step 5: Verifikasi test**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test accounts.tests.DynamicRBACAndFreezeTestCase
```
Expected: PASS (OK).

- [ ] **Step 6: Commit Task 3**

```bash
git add accounts/models.py accounts/tests.py accounts/migrations/
git commit -m "feat(auth): implementasi matriks izin dinamis per peran dan proteksi survey freeze mode"
```

---

### Task 4: Dinamisasi Ambang Batas Akreditasi & Matriks Risiko pada View dan Model

**Files:**
- Modify: `akreditasi/models.py` (`Category.status_level`)
- Modify: `akreditasi/risiko_models.py` (`RisikoUnit.risk_level`, `RisikoUnit.risk_color`)
- Modify: `akreditasi/views.py` (`auto_scoring_pokja`)

- [ ] **Step 1: Hubungkan `status_level` di `Category` dengan `SystemConfig`**

```python
    @property
    def status_level(self):
        from .system_models import SystemConfig
        cfg = SystemConfig.get_solo()
        pct = self.percentage
        if pct >= cfg.threshold_paripurna:
            return {'label': 'PARIPURNA (A)', 'badge': 'success'}
        elif pct >= cfg.threshold_utama:
            return {'label': 'UTAMA (B)', 'badge': 'primary'}
        elif pct >= cfg.threshold_madya:
            return {'label': 'MADYA (C)', 'badge': 'warning'}
        return {'label': 'BELUM MEMENUHI', 'badge': 'danger'}
```

- [ ] **Step 2: Hubungkan `risk_level` dan `risk_color` di `RisikoUnit` dengan `SystemConfig`**

```python
    @property
    def risk_level(self):
        from .system_models import SystemConfig
        cfg = SystemConfig.get_solo()
        skor = self.skor_inherent
        if skor >= cfg.risk_threshold_sangat_tinggi:
            return 'SANGAT_TINGGI'
        if skor >= cfg.risk_threshold_tinggi:
            return 'TINGGI'
        if skor >= cfg.risk_threshold_sedang:
            return 'SEDANG'
        if skor >= cfg.risk_threshold_rendah:
            return 'RENDAH'
        return 'SANGAT_RENDAH'
```

- [ ] **Step 3: Update `auto_scoring_pokja` di `akreditasi/views.py`**

Ambil target batas kelulusan langsung dari database agar prediksi kelulusan rumah sakit selalu akurat terhadap kustomisasi admin.

- [ ] **Step 4: Verifikasi dengan Django check**

Run:
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py check
```
Expected: `System check identified no issues (0 silenced)`.

- [ ] **Step 5: Commit Task 4**

```bash
git add akreditasi/models.py akreditasi/risiko_models.py akreditasi/views.py
git commit -m "feat(scoring): integrasikan ambang kelulusan dan matriks risiko dengan konfigurasi admin dinamis"
```

---

### Task 5: Backend Controllers Pusat Kontrol Admin (5 Tab Modular)

**Files:**
- Modify: `accounts/views.py`
- Modify: `accounts/urls.py`
- Test: `accounts/tests.py`

**Interfaces:**
- View utama: `admin_control_center(request)` (`/accounts/kontrol/`)
- API endpoints:
  - `/accounts/kontrol/unit/<int:unit_id>/update-hierarchy/`
  - `/accounts/kontrol/permissions/update/`
  - `/accounts/kontrol/permissions/reset/`
  - `/accounts/kontrol/user/<int:user_id>/permissions/`
  - `/accounts/kontrol/system/update/` (Update ambang batas, KPS alert, kop surat, tema)
  - `/accounts/kontrol/system/toggle-freeze/` (Toggle Survey Freeze Mode)

- [ ] **Step 1: Tulis unit test untuk seluruh endpoints kontrol di `accounts/tests.py`**
- [ ] **Step 2: Implementasikan views di `accounts/views.py` dengan validasi ketat anti-circular dependency & Super Admin protection**
- [ ] **Step 3: Daftarkan routes di `accounts/urls.py`**
- [ ] **Step 4: Jalankan test untuk memverifikasi seluruh endpoint berfungsi (HTTP 200)**
- [ ] **Step 5: Commit Task 5**

---

### Task 6: Template Antarmuka Pusat Kontrol Admin (`admin_control_center.html`) & Dynamic Theme

**Files:**
- Create: `templates/accounts/admin_control_center.html`
- Modify: `templates/base.html`
- Modify: `templates/includes/sidebar.html`

**Interfaces:**
- 5 Tab Navigasi Berdesain Modern RS MonsisKami:
  1. 🌳 **Hierarki & Struktur Unit** (Drag/select parent, ubah urutan, ubah tipe unit, toggle aktif/arsip, modal tambah).
  2. 🛡️ **Matriks Hak Akses Peran** (Grid switch interaktif 16 izin untuk 6 peran + tombol reset KARS).
  3. 👤 **Kustomisasi Akses Pengguna** (Pencarian user, unit kerja, akses pokja, checklist override izin).
  4. 🎯 **Standar & Ambang Akreditasi** (Form slider/input % Paripurna, Utama, Madya, Dasar, batas upload).
  5. 🎨 **Profil, Kop Surat & Mode Kunci Survei** (Branding, pilihan tema warna live, tombol besar status Survei Freeze).
- Pada `templates/base.html`: Pasang banner peringatan kuning di atas navbar jika `survey_freeze_mode = True`.
- Pada `templates/includes/sidebar.html`: Tambahkan menu "Pusat Kontrol Sistem" di panel admin.

- [ ] **Step 1: Implementasikan `admin_control_center.html` lengkap dengan visual feedback, live search, dan AJAX toggle**
- [ ] **Step 2: Update `base.html` untuk dynamic theme CSS class & survey freeze warning banner**
- [ ] **Step 3: Update `sidebar.html` dengan ikon `bi-sliders2-vertical`**
- [ ] **Step 4: Jalankan verifikasi rendering template**
- [ ] **Step 5: Commit Task 6**

---

### Task 7: Dokumentasi Lengkap & Panduan Kustomisasi Sistem

**Files:**
- Create: `docs/07_PANDUAN_PUSAT_KONTROL_AKSES_DAN_HIERARKI.md`
- Modify: `docs/README.md`
- Modify: `docs/PANDUAN_LENGKAP_RS_MONSISKAMI.html`
- Modify: `docs/06_STANDAR_OPERASIONAL_UPDATE_FITUR.md`

- [ ] **Step 1: Tulis buku panduan `docs/07_PANDUAN_PUSAT_KONTROL_AKSES_DAN_HIERARKI.md` (tutorial step-by-step 9 domain kustomisasi)**
- [ ] **Step 2: Update indeks modul di `docs/README.md`**
- [ ] **Step 3: Update portal interaktif `docs/PANDUAN_LENGKAP_RS_MONSISKAMI.html`**
- [ ] **Step 4: Catat rilis versi di `docs/06_STANDAR_OPERASIONAL_UPDATE_FITUR.md`**
- [ ] **Step 5: Commit Task 7**

---

### Task 8: QA Otomasi & Deployment Production

**Files:**
- Test: Seluruh test suite lokal

- [ ] **Step 1: Eksekusi seluruh test suite lokal**
```bash
DJANGO_DEBUG=True DATABASE_URL=sqlite:///db.sqlite3 python manage.py test accounts akreditasi
```
Expected: Semua test PASS (100% OK).

- [ ] **Step 2: Push git origin master dan deploy Railway**
```bash
git push origin master
railway up --detach
```

- [ ] **Step 3: Verifikasi live production melalui script otomatis (login, akses /accounts/kontrol/, uji simpan konfigurasi)**

---

## Ringkasan Eksekutif Kustomisasi

Dengan arsitektur ini, Rumah Sakit MonsisKami tidak lagi bergantung pada pengaturan statis program:
1. **Organisasi:** Dari RS sederhana hingga RS Pendidikan multi-kampus dengan 5+ kedalaman hierarki dapat dikonfigurasi langsung.
2. **Keamanan:** Setiap peran dan setiap dokter/perawat/staf dapat diatur izinnya hingga ke level detail (siapa yang boleh skor, siapa yang boleh upload, siapa yang boleh hapus).
3. **Standar Mutu:** Ambang kelulusan dan rumus matriks risiko dapat disesuaikan dengan regulasi terbaru Kemenkes / KARS / JCI.
4. **Saat Akreditasi:** Mode Kunci Survei melindungi data dari kecelakaan edit oleh staf selama survei lapangan berlangsung.
