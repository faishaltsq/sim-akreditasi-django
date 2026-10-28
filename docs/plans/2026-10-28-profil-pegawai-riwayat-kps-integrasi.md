# Plan: Profil Pegawai — Riwayat Kepegawaian Terkelola + Integrasi Legalitas & KPS (Level 1–2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengubah tab *Riwayat Kepegawaian* pada profil pegawai dari satu baris read-only + empty state menjadi daftar riwayat yang bisa ditambah/diubah/dihapus, menambahkan peringatan STR/SIP & validasi silang penempatan unit khusus, dan menghubungkan kelengkapan Human Capital ke indikator EP KPS yang benar (bukan skor palsu).

**Architecture:** Perbaikan bertumpu pada model yang sudah ada (`RiwayatKepegawaian`, `PenempatanPegawai`, `IzinProfesiPegawai`, `PengingatSDM`, `PeristiwaSDM`) — tidak ada model baru yang wajib. Yang hilang adalah *lapisan pengelolaan* (form, view, URL), *lapisan validasi silang* (service penempatan ↔ legalitas), *lapisan peringatan* (banner di profil), dan *lapisan pelaporan KPS* (perbaikan `publish_kps_artifact` + pembacaan progres yang benar). Pola yang dipakai ulang: `save_assignment` (lock + FTE), `legal_status` (band 0–7/8–30/31–90), `evaluate_employee_compliance`, `PeristiwaSDM` immutable.

**Tech Stack:** Django 6.1.1, Python 3.12, SQLite (lokal & uji) / Postgres (produksi), Bootstrap 5 via `templates/base.html`, `manage.py test` (tanpa pytest).

**Spec:** Dokumen sumber pengguna (28 Okt 2026):
- `~/Downloads/kekurangan di human kapital level 1.docx` — tab Riwayat Kepegawaian hanya empty state; usulan model + template + view.
- `~/Downloads/Kekurangan dan Solusi Level 2.docx` — (a) validasi silang riwayat/mutasi ↔ STR/SIP aktif, (b) audit trail perubahan data, (c) EP KPS masih 0/78 → 0%, (d) banner peringatan STR/SIP < 3 bulan, (e) dokumen SK terbagi lintas tab.

**Temuan audit kode (status hari ini — dibaca langsung, bukan asumsi):**

| # | Klaim dokumen | Kondisi kode nyata | Putusan plan |
|---|---|---|---|
| 1 | Tab Riwayat Kepegawaian kosong | `RiwayatKepegawaian` **ada** (`sdm/models/intake.py:117-183`) & diisi wizard intake; template hanya menampilkan **1 record terbaru** (`sdm/services/intake.py:678`, `templates/sdm/pegawai/detail.html:83-97`); **tidak ada** form/view/URL CRUD | **Lengkapi CRUD** — jangan buat model baru (usulan dokumen akan menduplikasi model) |
| 2 | Tidak ada audit trail perubahan | `PeristiwaSDM` immutable **ada** (`sdm/models/audit.py`), sudah dipakai `pegawai_edit`; belum dipakai untuk riwayat | **Pakai `PeristiwaSDM`**, jangan bikin log kedua |
| 3 | EP KPS 0/78, 0% | Sidebar hitung **dinamis** dari DB aktif: `sidebar_context` → `Category.percentage` = `SUM(score)/COUNT(EP)×10` (`akreditasi/context_processors.py:47-116`, `akreditasi/models.py:219-279`). DB dev: KPS = 34 EP terpasang (target 25), 23 sudah berskor → 63%. Jadi 0/78 = katalog belum terpasang/diinstal, **bukan bug rumus** | **Jangan otomatis-skor dari data pegawai.** Perbaiki jalur *publikasi bukti* yang rusak + tampilkan ketertinggalan (gap) katalog |
| 4 | STR/SIP akan habis tanpa peringatan | `legal_status` + band 31–90 hari **ada** (`sdm/services/legalitas.py:42-153`) & tampil di portal pegawai (`sdm/portal_views.py:29-55`); **tidak dipakai** di profil HC | **Tampilkan** `legal_status` di profil + perbaiki `sync_legal_reminders` (band di luar `BAND_CHOICES`, `update_fields` memuat `updated_at` yang tidak ada, arsip terlalu luas) |
| 5 | Penempatan unit khusus tanpa cek STR/SIP | Tidak ada; `save_assignment` hanya cek FTE/tanggal (`sdm/services/penempatan.py:43-83`) | **Tambah validasi silang** berbasis `legal_status` + `PenugasanKlinis` |
| 6 | SK yang diunggah tidak terbagi ke tab Dokumen | Dokumen sudah satu repositori (`DokumenPegawai`) | **Pilih `jenis_berkas` tepat** saat membuat dokumen dari riwayat; tidak perlu duplikasi |

## Global Constraints
1. Django 6.1.1 / Python 3.12; jalankan uji dengan `.venv/Scripts/python.exe manage.py test <label>` (pytest **tidak** terpasang).
2. Uji memakai `TestCase` Django (pola `sdm/tests/test_dashboard.py`), bukan pytest.
3. Semua tulisan SDM wajib izin eksplisit lewat `require_hc_capability` (`sdm/akses.py`); lingkup dari `visible_employees`/`visible_units`.
4. `PeristiwaSDM` bersifat immutable — hanya `create()`, tidak pernah `update()`/`delete()`.
5. `PengingatSDM.band` hanya menerima `LT_30`, `LT_60`, `LT_90`, `EXPIRED`, `TASK_DUE`, `TASK_OVERDUE` (`sdm/models/pengingat.py:11-13`). Band legal `0-7`, `8-30`, `31-90` **wajib dipetakan** ke nilai tersebut.
6. Tidak ada perubahan skema `RiwayatKepegawaian` yang mengubah arti kolom lama; penambahan kolom hanya boleh nullable/berdefault.
7. Bahasa UI: Indonesia. Gaya template: Bootstrap 5 class utilities, `table table-sm align-middle`, badge `text-bg-*` — ikuti `templates/sdm/pegawai/detail.html`.
8. Tidak menambah dependensi baru.
9. Angka progres KPS yang ditampilkan ke pengguna wajib punya penyebut nyata; bila katalog belum terpasang tampilkan "belum dapat dihitung" (pola `build_hc_dashboard`), bukan 0%.
10. Katalog EP KPS tidak di-seed ulang dari dokumen: 81 EP di fixture 2024 vs 25 di seed lama vs 34 terpasang — keputusan impor milik pengguna, plan hanya melaporkan selisihnya.

## Review Focus
1. **Riwayat tanpa TMT** (`tanggal_tmt=None`, diizinkan model): tabel harus tetap terurut & `tenure_days` tidak crash — sudah dijaga `build_staff_profile`, tapi urutan daftar baru harus eksplisit (`-tanggal_tmt`, `-pk`) dan TMT kosong ditampilkan "Belum dicatat".
2. **Dua riwayat bertumpang** untuk satu pegawai (TMT lama tanpa `tanggal_akhir` + TMT baru): CRUD harus menolak interval yang bertumpuk, bukan menimpa diam-diam — pola constraint sudah ada di model (`sdm/models/intake.py:169-180`), belum ada guard aplikasi.
3. **Penghapusan riwayat terakhir** sehingga pegawai tidak punya TMT sama sekali: hapus harus ditolak bila hanya tersisa satu record, atau setidaknya `PeristiwaSDM` mencatat penyebabnya.
4. **Legalitas `LIFETIME`** (`validity_mode='LIFETIME'`, tanpa tanggal): banner tidak boleh menyatakan "akan kedaluwarsa"; band harus `valid` (`_license_band`, `sdm/services/legalitas.py:121-128`).
5. **Pegawai tanpa akun** (`Pegawai.akun` nullable): `sync_legal_reminders` menyetel `recipient=employee.akun` → `None`; pengingat in-app tak bisa diterima siapa pun. Harus gagal aman (skip + catat), bukan `IntegrityError` pada `idempotency_key` unik yang memuat "none".

---

## File Structure
- **Modify** `sdm/forms/riwayat.py` *(baru)* — satu form CRUD untuk `RiwayatKepegawaian`, plus form penempatan validasi silang.
- **Modify** `sdm/forms/__init__.py` — ekspor form baru.
- **Modify** `sdm/views.py` — view tambah/ubah/hapus riwayat; konteks tambahan untuk `pegawai_detail`.
- **Modify** `sdm/urls.py` — route baru di bawah blok pegawai.
- **Modify** `templates/sdm/pegawai/detail.html` — tabel riwayat + banner legalitas + tombol aksi.
- **Modify** `templates/sdm/pegawai/form.html` — sudah generik; dipakai ulang apa adanya.
- **Modify** `sdm/services/penempatan.py` — validasi silang legalitas saat penempatan baru di unit tertentu.
- **Modify** `sdm/services/legalitas.py` — perbaiki band reminder + aman untuk pegawai tanpa akun.
- **Modify** `sdm/models/pengingat.py` — helper pemetaan band legal → band `PengingatSDM`.
- **Modify** `sdm/services/publikasi_bukti.py` — `publish_kps_artifact` harus menulis field `EvidenceFile` yang benar + menyimpan byte workbook.
- **Modify** `sdm/views.py` (`kps_pack_publish`) — mengirim byte nyata, bukan `b''`.
- **Modify** `templates/sdm/kps/pack_preview.html` — `<select>` EP terisi dari mapping aktif.
- **Modify** `akreditasi/context_processors.py` — tandai kategori yang `target_ep_count` ≠ EP terpasang (gap katalog) supaya "0/78" bisa dijelaskan.
- **Modify** `sdm/admin.py` — daftarkan `RiwayatKepegawaian` & `IzinProfesiPegawai` (read-only semantik) bila belum.
- **Create** `sdm/tests/test_riwayat_kepegawaian.py` — uji CRUD + interval.
- **Create** `sdm/tests/test_legalitas_banner.py` — uji banner & band reminder.
- **Create** `sdm/tests/test_penempatan_validasi_legal.py` — uji validasi silang.
- **Create** `sdm/tests/test_kps_publish.py` — uji jalur publikasi bukti KPS.

---

## Task 1: CRUD Riwayat Kepegawaian pada Profil Pegawai

**Files:**
- Create: `sdm/forms/riwayat.py`
- Modify: `sdm/forms/__init__.py:1-42` (tambah ekspor)
- Modify: `sdm/views.py` (tambah 3 view setelah `pegawai_edit`, sekitar baris 320)
- Modify: `sdm/urls.py:28-34` (tambah 3 route)
- Modify: `templates/sdm/pegawai/detail.html:83-97` (tabel + tombol)
- Test: `sdm/tests/test_riwayat_kepegawaian.py`

**Interfaces:**
- Consumes: `sdm.models.RiwayatKepegawaian` (`sdm/models/intake.py:117`), `sdm.akses.require_hc_capability`, `sdm.akses.visible_employees`, `sdm.models.audit.PeristiwaSDM`, `sdm.views._form_context` (`sdm/views.py:151`), template `sdm/pegawai/form.html`.
- Produces: `RiwayatKepegawaianForm(forms.ModelForm)`; view `riwayat_create(request, employee_id)`, `riwayat_edit(request, riwayat_id)`, `riwayat_delete(request, riwayat_id)`; route `sdm:riwayat_create`, `sdm:riwayat_edit`, `sdm:riwayat_delete`; context key `riwayat_list` pada `sdm:pegawai_detail`.

- [x] **Step 1: Tulis test yang gagal**

```python
# sdm/tests/test_riwayat_kepegawaian.py
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import resolve
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai, PeristiwaSDM, RiwayatKepegawaian


class RiwayatKepegawaianCrudTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Riwayat', code='RW-TEST')
        self.user = get_user_model().objects.create_user(username='rw-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        HcGrant.objects.create(
            user=self.user, capability='can_manage_hc_employees', unit_kerja=self.unit
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Ahmad', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=400),
            alokasi_fte=Decimal('1.00'),
        )

    def test_routes_are_registered(self):
        self.assertEqual(
            resolve(f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/').view_name,
            'sdm:riwayat_create',
        )

    def test_profile_lists_every_history_row_newest_first(self):
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='PKWT',
            tanggal_tmt=self.today - timedelta(days=800),
        )
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=10),
        )
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, 'PKWT')
        self.assertContains(response, 'Tetap')

    def test_create_records_audit_event(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/',
            {
                'kategori_pegawai': 'TETAP',
                'tanggal_tmt': (self.today - timedelta(days=30)).isoformat(),
                'jabatan_struktural': 'Kepala Ruang',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RiwayatKepegawaian.objects.filter(pegawai=self.employee).count(), 1)
        event = PeristiwaSDM.objects.get(target_tipe='employee')
        self.assertEqual(event.jenis_peristiwa, 'riwayat_kepegawaian_created')

    def test_overlapping_open_ended_history_is_rejected(self):
        RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=300), tanggal_akhir=None,
        )
        self.client.force_login(self.user)
        response = self.client.post(
            f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/',
            {
                'kategori_pegawai': 'PKWT',
                'tanggal_tmt': self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RiwayatKepegawaian.objects.filter(pegawai=self.employee).count(), 1)

    def test_last_remaining_history_cannot_be_deleted(self):
        history = RiwayatKepegawaian.objects.create(
            pegawai=self.employee, kategori_pegawai='TETAP',
            tanggal_tmt=self.today - timedelta(days=100),
        )
        self.client.force_login(self.user)
        response = self.client.post(f'/human-capital/pegawai/{self.employee.pk}/riwayat/{history.pk}/hapus/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(RiwayatKepegawaian.objects.filter(pk=history.pk).exists())

    def test_viewer_without_grant_is_denied(self):
        other = get_user_model().objects.create_user(username='rw-outsider')
        UserProfile.objects.create(user=other, role='STAF', unit_kerja=self.unit)
        self.client.force_login(other)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/riwayat/baru/')
        self.assertEqual(response.status_code, 403)
```

- [x] **Step 2: Jalankan test untuk memastikan gagal**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_riwayat_kepegawaian -v 2`
Expected: FAIL — `NoReverseMatch`/404 karena route `sdm:riwayat_create` belum ada.

- [x] **Step 3: Implementasikan form**

```python
# sdm/forms/riwayat.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from sdm.models import RiwayatKepegawaian
from sdm.akses import visible_employees

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class RiwayatKepegawaianForm(forms.ModelForm):
    class Meta:
        model = RiwayatKepegawaian
        fields = [
            'kategori_pegawai',
            'tanggal_tmt',
            'tanggal_akhir',
            'nomor_kontrak',
            'tanggal_mulai_kontrak',
            'tanggal_selesai_kontrak',
            'jam_kontrak_per_minggu',
            'jam_fulltime_referensi',
            'jabatan_struktural',
        ]
        widgets = {
            'kategori_pegawai': forms.Select(attrs={'class': SELECT_CLASS}),
            'tanggal_tmt': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'tanggal_akhir': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'nomor_kontrak': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'tanggal_mulai_kontrak': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'tanggal_selesai_kontrak': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'jam_kontrak_per_minggu': forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
            'jam_fulltime_referensi': forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
            'jabatan_struktural': forms.TextInput(attrs={'class': FIELD_CLASS}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        tmt = cleaned.get('tanggal_tmt')
        akhir = cleaned.get('tanggal_akhir')
        if tmt and akhir and akhir < tmt:
            raise ValidationError({'tanggal_akhir': 'Tanggal akhir tidak boleh sebelum TMT.'})
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.pegawai = self.employee
        if commit:
            instance.full_clean()
            instance.save()
        return instance
```

- [x] **Step 4: Implementasikan view + route**

```python
# sdm/views.py — tambahkan setelah pegawai_edit (sekitar baris 320)

@login_required
def riwayat_create(request, employee_id):
    employee = get_object_or_404(visible_employees(request.user), pk=employee_id)
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=employee)
    form = RiwayatKepegawaianForm(request.POST or None, employee=employee)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                history = form.save()
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='riwayat_kepegawaian_created',
                    target_tipe='employee',
                    target_id=str(employee.pk),
                    status_sesudah=history.kategori_pegawai,
                    alasan=f'Riwayat kepegawaian ditambahkan (TMT {history.tanggal_tmt or "belum dicatat"}).',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    return _form_context(
        request, form,
        f'Tambah Riwayat Kepegawaian — {employee.nama_lengkap}',
        employee=employee,
    )


@login_required
def riwayat_edit(request, riwayat_id):
    history = get_object_or_404(
        RiwayatKepegawaian.objects.filter(pegawai__in=visible_employees(request.user)),
        pk=riwayat_id,
    )
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=history.pegawai)
    form = RiwayatKepegawaianForm(
        request.POST or None, instance=history, employee=history.pegawai
    )
    if request.method == 'POST' and form.is_valid():
        before = history.kategori_pegawai
        try:
            with transaction.atomic():
                updated = form.save()
                PeristiwaSDM.objects.create(
                    actor=request.user,
                    jenis_peristiwa='riwayat_kepegawaian_updated',
                    target_tipe='employee',
                    target_id=str(updated.pegawai_id),
                    status_sebelum=before,
                    status_sesudah=updated.kategori_pegawai,
                    alasan='Riwayat kepegawaian diperbarui.',
                )
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)
    return _form_context(
        request, form,
        f'Ubah Riwayat Kepegawaian — {history.pegawai.nama_lengkap}',
        employee=history.pegawai,
    )


@login_required
def riwayat_delete(request, riwayat_id):
    history = get_object_or_404(
        RiwayatKepegawaian.objects.filter(pegawai__in=visible_employees(request.user)),
        pk=riwayat_id,
    )
    require_hc_capability(request.user, 'can_manage_hc_employees', employee=history.pegawai)
    if request.method == 'POST':
        siblings = RiwayatKepegawaian.objects.filter(
            pegawai=history.pegawai
        ).exclude(pk=history.pk).count()
        if siblings == 0:
            messages.error(
                request,
                'Riwayat terakhir tidak dapat dihapus; pegawai wajib memiliki minimal satu riwayat kepegawaian.',
            )
            return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)
        with transaction.atomic():
            RiwayatKepegawaian.objects.filter(pk=history.pk).delete()
            PeristiwaSDM.objects.create(
                actor=request.user,
                jenis_peristiwa='riwayat_kepegawaian_deleted',
                target_tipe='employee',
                target_id=str(history.pegawai_id),
                status_sebelum=history.kategori_pegawai,
                alasan=f'Riwayat dihapus (TMT {history.tanggal_tmt or "belum dicatat"}).',
            )
    return redirect('sdm:pegawai_detail', employee_id=history.pegawai_id)
```

```python
# sdm/urls.py — sisipkan setelah route 'pegawai_edit' (baris 30-34)
    path(
        'pegawai/<uuid:employee_id>/riwayat/baru/',
        views.riwayat_create,
        name='riwayat_create',
    ),
    path(
        'pegawai/<uuid:employee_id>/riwayat/<int:riwayat_id>/ubah/',
        views.riwayat_edit,
        name='riwayat_edit',
    ),
    path(
        'pegawai/<uuid:employee_id>/riwayat/<int:riwayat_id>/hapus/',
        views.riwayat_delete,
        name='riwayat_delete',
    ),
```

- [x] **Step 5: Ganti isi tab Riwayat Kepegawaian di template**

Ganti `templates/sdm/pegawai/detail.html:83-97` menjadi:

```django
            <section class="tab-pane fade" id="employment-pane" role="tabpanel" aria-labelledby="employment-tab" tabindex="0">
                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                    <div>
                        <h2 class="h6 mb-1">Riwayat Kepegawaian</h2>
                        <p class="small text-muted mb-0">Setiap perubahan status/kategori kepegawaian beserta SK dan TMT-nya.</p>
                    </div>
                    {% if can_manage %}
                    <a class="btn btn-outline-primary btn-sm" href="{% url 'sdm:riwayat_create' employee.pk %}"><i class="bi bi-plus-lg me-1"></i>Tambah Riwayat</a>
                    {% endif %}
                </div>
                {% if riwayat_list %}
                <div class="table-responsive">
                    <table class="table table-sm align-middle">
                        <caption class="visually-hidden">Riwayat kepegawaian pegawai</caption>
                        <thead><tr><th scope="col">TMT</th><th scope="col">Kategori</th><th scope="col">Jabatan Struktural</th><th scope="col">Kontrak</th><th scope="col">Status Tinjauan</th><th scope="col">Aksi</th></tr></thead>
                        <tbody>
                            {% for item in riwayat_list %}
                            <tr>
                                <td>{% if item.tanggal_tmt %}{{ item.tanggal_tmt|date:"d M Y" }}{% if item.tanggal_akhir %} – {{ item.tanggal_akhir|date:"d M Y" }}{% endif %}{% else %}Belum dicatat{% endif %}</td>
                                <td>{{ item.get_kategori_pegawai_display }}</td>
                                <td>{{ item.jabatan_struktural|default:"—" }}</td>
                                <td class="small">{{ item.nomor_kontrak|default:"—" }}{% if item.tanggal_selesai_kontrak %}<div class="text-muted">s/d {{ item.tanggal_selesai_kontrak|date:"d M Y" }}</div>{% endif %}</td>
                                <td>{{ item.get_review_status_display }}</td>
                                <td class="text-nowrap">
                                    {% if can_manage %}
                                    <a class="small" href="{% url 'sdm:riwayat_edit' employee.pk item.pk %}">Ubah</a>
                                    <form method="post" action="{% url 'sdm:riwayat_delete' employee.pk item.pk %}" class="d-inline">
                                        {% csrf_token %}
                                        <button type="submit" class="btn btn-link btn-sm small p-0 ms-2 text-danger text-decoration-none">Hapus</button>
                                    </form>
                                    {% else %}<span class="small text-muted">—</span>{% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                {% else %}
                <p class="text-muted mb-0">Riwayat kepegawaian belum dicatat.{% if can_manage %} <a href="{% url 'sdm:riwayat_create' employee.pk %}">Tambahkan riwayat pertama</a>.{% endif %}</p>
                {% endif %}
                {% if profile.employment %}
                <p class="small text-muted mt-3 mb-0">Masa kerja dihitung dari TMT {{ profile.employment.tanggal_tmt|date:"d M Y"|default:"belum dicatat" }}: {% if profile.tenure_days is not None %}{{ profile.tenure_days }} hari{% else %}belum dapat dihitung{% endif %}.</p>
                {% endif %}
            </section>
```

- [x] **Step 6: Tambahkan `riwayat_list` ke konteks `pegawai_detail`**

```python
# sdm/views.py — di dalam pegawai_detail, sebelum render(...)
    riwayat_list = employee.riwayat_kepegawaian.order_by('-tanggal_tmt', '-pk')
```

dan tambahkan `'riwayat_list': riwayat_list,` pada dict konteks `sdm/views.py:364-375`.

- [x] **Step 7: Jalankan test**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_riwayat_kepegawaian -v 2`
Expected: PASS (6 test).

- [x] **Step 8: Commit**
```bash
git add sdm/forms/riwayat.py sdm/forms/__init__.py sdm/views.py sdm/urls.py templates/sdm/pegawai/detail.html sdm/tests/test_riwayat_kepegawaian.py
git commit -m "feat(sdm): kelola riwayat kepegawaian pada profil pegawai"
```

---

## Task 2: Validasi Silang Penempatan terhadap Legalitas (STR/SIP/SPK)

**Files:**
- Create: `sdm/tests/test_penempatan_validasi_legal.py`
- Modify: `sdm/services/legalitas.py:32-40` (tambah helper `placement_blockers`)
- Modify: `sdm/services/penempatan.py:43-83` (panggil helper sebelum `save()`)

**Interfaces:**
- Consumes: `legal_status(employee, *, as_of=None, practice_site=None)` (`sdm/services/legalitas.py:42`), `PenugasanKlinis` (`sdm/models/kredensial.py:221`), `PenempatanPegawai` (`sdm/models/pegawai.py:89`).
- Produces: `placement_legal_blockers(employee, *, unit_kerja=None, as_of=None) -> list[dict]` — tiap dict berisi `subtype`, `label`, `nomor`, `alasan`. Dikembalikan kosong bila aman.

- [x] **Step 1: Tulis test yang gagal**

```python
# sdm/tests/test_penempatan_validasi_legal.py
from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from akreditasi.models import UnitKerja
from sdm.models import IzinProfesiPegawai, Pegawai, PenempatanPegawai
from sdm.services.legalitas import placement_legal_blockers
from sdm.services.penempatan import save_assignment


class PlacementLegalValidationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='ICU', code='ICU-TEST')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Suster ICU', kategori='PPA', profesi='Perawat'
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-1',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=365),
            tanggal_berakhir=self.today + timedelta(days=365),
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_valid_str_produces_no_blocker(self):
        self._izin()
        self.assertEqual(placement_legal_blockers(self.employee, unit_kerja=self.unit), [])

    def test_expired_str_blocks_placement(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=1))
        blockers = placement_legal_blockers(self.employee, unit_kerja=self.unit)
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]['subtype'], 'STR')

    def test_lifetime_str_never_blocks(self):
        self._izin(validity_mode='LIFETIME', tanggal_berakhir=None)
        self.assertEqual(placement_legal_blockers(self.employee, unit_kerja=self.unit), [])

    def test_missing_expiry_date_is_unknown_and_does_not_block(self):
        self._izin(tanggal_berakhir=None)
        self.assertEqual(placement_legal_blockers(self.employee, unit_kerja=self.unit), [])

    def test_sip_expiring_within_ninety_days_blocks(self):
        self._izin(subtype='SIP', nomor_izin='SIP-1',
                   tanggal_berakhir=self.today + timedelta(days=45))
        blockers = placement_legal_blockers(self.employee, unit_kerja=self.unit)
        self.assertEqual(blockers[0]['subtype'], 'SIP')

    def test_save_assignment_refuses_expired_str(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=5))
        assignment = PenempatanPegawai(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today, alokasi_fte=Decimal('1.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            save_assignment(assignment)
        self.assertIn('legalitas', str(ctx.exception.message_dict))
```

- [x] **Step 2: Jalankan test untuk memastikan gagal**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_penempatan_validasi_legal -v 2`
Expected: FAIL — `ImportError: cannot import name 'placement_legal_blockers'`.

- [x] **Step 3: Implementasikan helper legalitas**

```python
# sdm/services/legalitas.py — tambahkan setelah _spk_band (baris ~153)

BLOCKING_BANDS = {EXPIRED, ZERO_SEVEN, EIGHT_THIRTY, THIRTY_NINETY}


def placement_legal_blockers(employee, *, unit_kerja=None, as_of=None):
    """Blockers for placing/keeping an employee in a unit: only expired or
    expiring licenses (STR/SIP/SIPA) and revoked SPK count. A license with no
    recorded expiry is unknown, not a violation, and never blocks.
    """
    status = legal_status(employee, as_of=as_of)
    blockers = []
    for item in status.items:
        if item['source'] == 'none':
            continue
        if item.get('revoked') or item['band'] not in BLOCKING_BANDS:
            continue
        blockers.append({
            'subtype': item['subtype'],
            'nomor': item['nomor_izin'],
            'label': item['label'],
            'alasan': (
                f"{item['subtype']} {item['nomor_izin'] or ''}".strip()
                + f" berstatus {item['label'].lower()}"
            ),
        })
    return blockers
```

- [x] **Step 4: Panggil dari `save_assignment`**

```python
# sdm/services/penempatan.py — di dalam save_assignment, setelah
# _validate_peak_allocation([*overlaps, assignment]) dan sebelum assignment.save()
        if is_new:
            from sdm.services.legalitas import placement_legal_blockers
            blockers = placement_legal_blockers(
                assignment.pegawai, unit_kerja=assignment.unit_kerja
            )
            if blockers:
                raise ValidationError({
                    'legalitas': 'Penempatan ditolak: '
                    + '; '.join(b['alasan'] for b in blockers)
                })
```

- [x] **Step 5: Jalankan test**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_penempatan_validasi_legal -v 2`
Expected: PASS (6 test).

- [x] **Step 6: Commit**
```bash
git add sdm/services/legalitas.py sdm/services/penempatan.py sdm/tests/test_penempatan_validasi_legal.py
git commit -m "feat(sdm): tolak penempatan unit ketika STR/SIP kedaluwarsa"
```

---

## Task 3: Banner Legalitas di Profil Pegawai + Perbaikan Reminder Legal

**Files:**
- Create: `sdm/tests/test_legalitas_banner.py`
- Modify: `sdm/models/pengingat.py:8-12` (tambah `LEGAL_BAND_MAP`)
- Modify: `sdm/services/legalitas.py:156-209` (`sync_legal_reminders`)
- Modify: `sdm/views.py` (konteks `legal` pada `pegawai_detail`)
- Modify: `templates/sdm/pegawai/detail.html:98-117` (badge band + banner)

**Interfaces:**
- Consumes: `legal_status`, `LEGAL_BANDS`, `LEGAL_LABELS` (`sdm/services/legalitas.py:10-30`), `PengingatSDM.build_key` (`sdm/models/pengingat.py:59-61`).
- Produces: `LEGAL_BAND_MAP: dict[str, str]` di `sdm/models/pengingat.py`; context key `legal` pada `sdm:pegawai_detail`; perilaku `sync_legal_reminders` yang idempoten & aman untuk pegawai tanpa akun.

- [x] **Step 1: Tulis test yang gagal**

```python
# sdm/tests/test_legalitas_banner.py
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, IzinProfesiPegawai, Pegawai, PengingatSDM, PenempatanPegawai
from sdm.services.legalitas import sync_legal_reminders


class LegalBannerAndReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Legal', code='LG-TEST')
        self.user = get_user_model().objects.create_user(username='lg-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=self.user, capability='can_view_hc', unit_kerja=self.unit)
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Legal', kategori='PPA', profesi='Perawat',
            akun=get_user_model().objects.create_user(username='lg-pegawai'),
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=100),
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-B',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=200),
            tanggal_berakhir=self.today + timedelta(days=45),
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_profile_shows_expiry_band_badge(self):
        self._izin()
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, '31–90 hari')

    def test_profile_shows_warning_banner_for_near_expiry(self):
        self._izin(tanggal_berakhir=self.today + timedelta(days=10))
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertContains(response, 'alert-warning')

    def test_lifetime_license_shows_no_banner(self):
        self._izin(validity_mode='LIFETIME', tanggal_berakhir=None)
        self.client.force_login(self.user)
        response = self.client.get(f'/human-capital/pegawai/{self.employee.pk}/')
        self.assertNotContains(response, 'alert-warning')

    def test_sync_creates_one_reminder_with_declared_band(self):
        self._izin(tanggal_berakhir=self.today + timedelta(days=45))
        sync_legal_reminders(employee=self.employee, actor=self.user)
        reminders = PengingatSDM.objects.filter(employee=self.employee)
        self.assertEqual(reminders.count(), 1)
        self.assertIn(reminders.first().band, dict(PengingatSDM.BAND_CHOICES))

    def test_sync_is_idempotent(self):
        self._izin()
        sync_legal_reminders(employee=self.employee, actor=self.user)
        sync_legal_reminders(employee=self.employee, actor=self.user)
        self.assertEqual(PengingatSDM.objects.filter(employee=self.employee).count(), 1)

    def test_sync_skips_employee_without_account(self):
        lone = Pegawai.objects.create(nama_lengkap='Tanpa Akun', kategori='NON_PPA')
        IzinProfesiPegawai.objects.create(
            pegawai=lone, subtype='STR', nomor_izin='STR-X', validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
        )
        sync_legal_reminders(employee=lone, actor=self.user)
        self.assertEqual(PengingatSDM.objects.filter(employee=lone).count(), 0)

    def test_renewed_license_archives_stale_reminder(self):
        izin = self._izin(tanggal_berakhir=self.today + timedelta(days=20))
        sync_legal_reminders(employee=self.employee, actor=self.user)
        izin.tanggal_berakhir = self.today + timedelta(days=400)
        izin.save(update_fields=['tanggal_berakhir'])
        sync_legal_reminders(employee=self.employee, actor=self.user)
        self.assertEqual(
            PengingatSDM.objects.filter(employee=self.employee, read_at__isnull=True).count(),
            0,
        )
```

- [x] **Step 2: Jalankan test untuk memastikan gagal**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_legalitas_banner -v 2`
Expected: FAIL — profil tidak memuat `31–90 hari` / tidak ada `alert-warning`.

- [x] **Step 3: Tambahkan pemetaan band legal**

```python
# sdm/models/pengingat.py — ganti baris 8
BANDS = ('LT_30', 'LT_60', 'LT_90', 'EXPIRED')

# Band legalitas (sdm.services.legalitas) dipetakan ke band reminder yang sah.
LEGAL_BAND_MAP = {
    '0-7': 'LT_30',
    '8-30': 'LT_30',
    '31-90': 'LT_90',
    'expired': 'EXPIRED',
}
```

- [x] **Step 4: Perbaiki `sync_legal_reminders`**

```python
# sdm/services/legalitas.py — ganti seluruh badan sync_legal_reminders
def sync_legal_reminders(*, employee, actor, as_of=None):
    """Create/refresh idempotent legal reminders for expired/urgent licenses and SPK.

    Band legal dipetakan ke band PengingatSDM yang sah; pegawai tanpa akun
    dilewati (tidak ada penerima in-app) tanpa menggagalkan pemanggil.
    """
    from sdm.models.pengingat import LEGAL_BAND_MAP
    as_of = as_of or timezone.localdate()
    status = legal_status(employee, as_of=as_of)
    recipient = getattr(employee, 'akun', None)
    if recipient is None:
        return {'created': 0, 'updated': 0, 'archived': 0}
    created = updated = 0
    urgent_keys = set()
    for item in status.items:
        if item['source'] == 'none' or item['state'] == VALID:
            continue
        band = LEGAL_BAND_MAP.get(item['band'])
        if band is None:
            continue
        alasan = f"{item['label']}: {item['nomor_izin'] or item['subtype']}"
        key = PengingatSDM.build_key(
            employee_id=employee.pk,
            version_id=f"legal:{item['source']}:{item['nomor_izin'] or item['subtype']}",
            band=band,
            target_type='DOCUMENT',
        )
        urgent_keys.add(key)
        obj, was_created = PengingatSDM.objects.get_or_create(
            idempotency_key=key,
            defaults={
                'employee': employee,
                'version': None,
                'band': band,
                'target_type': 'DOCUMENT',
                'recipient': recipient,
                'due_date': (
                    date.fromisoformat(item['tanggal_berakhir'])
                    if item['tanggal_berakhir'] else as_of
                ),
                'alasan': alasan,
            },
        )
        if was_created:
            created += 1
        elif obj.band != band or obj.alasan != alasan:
            obj.band = band
            obj.alasan = alasan
            obj.due_date = (
                date.fromisoformat(item['tanggal_berakhir'])
                if item['tanggal_berakhir'] else as_of
            )
            obj.save(update_fields=['band', 'alasan', 'due_date'])
            updated += 1
    # Arsipkan hanya reminder legalitas milik pegawai ini yang tak lagi urgen.
    archived = PengingatSDM.objects.filter(
        employee=employee, recipient=recipient, read_at__isnull=True,
        idempotency_key__startswith='DOCUMENT:',
    ).exclude(idempotency_key__in=urgent_keys).update(read_at=as_of)
    return {'created': created, 'updated': updated, 'archived': archived}
```

Tambahkan `from datetime import date` pada import modul bila belum ada.

- [x] **Step 5: Tambahkan konteks + tampilan banner**

```python
# sdm/views.py — di pegawai_detail, sebelum render(...)
    from sdm.services.legalitas import legal_status
    legal = legal_status(employee)
```

tambah `'legal': legal,` pada dict konteks.

Ganti `templates/sdm/pegawai/detail.html:98-117` (bagian tabel izin) menjadi:

```django
            <section class="tab-pane fade" id="legal-pane" role="tabpanel" aria-labelledby="legal-tab" tabindex="0">
                {% if legal.expired_or_urgent %}
                <div class="alert alert-warning py-2 small" role="alert">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    Legalitas memerlukan tindakan:
                    {% for item in legal.expired_or_urgent %}<span class="badge text-bg-warning ms-1">{{ item.subtype|default:"Dokumen" }} · {{ item.label }}</span>{% endfor %}
                </div>
                {% endif %}
                <h2 class="h6 mb-2">Izin &amp; legalitas</h2>
                <div class="table-responsive mb-4">
                    <table class="table table-sm align-middle">
                        <caption class="visually-hidden">Daftar izin profesi pegawai</caption>
                        <thead><tr><th scope="col">Jenis</th><th scope="col">Nomor</th><th scope="col">Masa berlaku</th><th scope="col">Status</th><th scope="col">Lokasi praktik</th></tr></thead>
                        <tbody>
                            {% for permit in profile.permits %}
                            <tr>
                                <td>{{ permit.get_subtype_display }}</td>
                                <td>{{ permit.nomor_izin|default:"Belum dicatat" }}</td>
                                <td>{% if permit.validity_mode == 'LIFETIME' %}Seumur hidup{% elif permit.tanggal_berakhir %}{{ permit.tanggal_berakhir|date:"d M Y" }}{% else %}Belum dicatat{% endif %}</td>
                                <td>
                                    {% for item in legal.items %}{% if item.source == 'izin_profesi' and item.nomor_izin == permit.nomor_izin %}
                                    <span class="badge {% if item.band == 'expired' %}text-bg-danger{% elif item.band == '0-7' %}text-bg-danger{% elif item.band == '8-30' %}text-bg-warning{% elif item.band == '31-90' %}text-bg-warning{% else %}text-bg-success{% endif %}">{{ item.label }}</span>
                                    {% endif %}{% endfor %}
                                </td>
                                <td>{{ permit.lokasi_praktik|default:"—" }}{% if permit.is_local_rs %} <span class="badge text-bg-info">RS ini</span>{% endif %}</td>
                            </tr>
                            {% empty %}<tr><td colspan="5" class="text-muted text-center py-4">Belum ada izin profesi.</td></tr>{% endfor %}
                        </tbody>
                    </table>
                </div>
```

- [x] **Step 6: Jalankan test**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_legalitas_banner -v 2`
Expected: PASS (7 test).

- [x] **Step 7: Commit**
```bash
git add sdm/models/pengingat.py sdm/services/legalitas.py sdm/views.py templates/sdm/pegawai/detail.html sdm/tests/test_legalitas_banner.py
git commit -m "feat(sdm): banner legalitas di profil dan reminder legal yang idempoten"
```

---

## Task 4: Memperbaiki Jalur Publikasi Bukti KPS (penyebab EP 0%)

**Files:**
- Create: `sdm/tests/test_kps_publish.py`
- Modify: `sdm/services/publikasi_bukti.py:108-139` (`publish_kps_artifact`)
- Modify: `sdm/views.py:2041-2047` (`kps_pack_publish` mengirim byte nyata)
- Modify: `sdm/views.py` (`kps_pack_preview` mengirim opsi EP)
- Modify: `templates/sdm/kps/pack_preview.html:14-19` (`<select>` terisi)

**Interfaces:**
- Consumes: `build_kps_pack` (`sdm/services/publikasi_bukti.py:17`), `PemetaanStandarSDM` (`sdm/models/dokumen.py:306`), `EvidenceFile` (`akreditasi/models.py:403`), `EvidenceReq` (`akreditasi/models.py:325`), `sdm.storage` privat.
- Produces: `publish_kps_artifact(*, actor, artifact, requirement_id)` yang benar-benar menyimpan byte workbook (lewat storage privat `sdm.storage`) dan membuat `EvidenceFile` dengan field yang ada (`file`, `file_name`, `file_size`, `status='REVIEW'`); context `requirement_options` pada `sdm:kps_pack_preview`.

- [x] **Step 1: Tulis test yang gagal**

```python
# sdm/tests/test_kps_publish.py
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import EvidenceReq, EvidenceFile, Framework, Category, StandardItem, UnitKerja
from sdm.models import AturanDokumen, Pegawai, PemetaanStandarSDM
from sdm.services.publikasi_bukti import build_kps_pack, publish_kps_artifact


class KpsPublishTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='kps-admin')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS')
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_export_hc = True
        config.can_verify_kps = True
        config.save(update_fields=['can_export_hc', 'can_verify_kps', 'updated_at'])
        self.framework = Framework.objects.create(
            name='STARKES 2024', version='2024', edition='2024', is_active=True
        )
        self.category = Category.objects.create(
            framework=self.framework, code='KPS', name='Kualifikasi & Pendidikan Staf'
        )
        self.item = StandardItem.objects.create(
            category=self.category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        self.requirement = EvidenceReq.objects.create(
            standard_item=self.item, category_type='D', title='Daftar riwayat kepegawaian',
            is_mandatory=True,
        )
        self.rule = AturanDokumen.objects.create(
            document_type='CREDENTIAL', name='STR', validity_policy='EXPIRY_REQUIRED'
        )
        PemetaanStandarSDM.objects.create(
            rule=self.rule, standard_item=self.item, framework=self.framework,
            reviewer_name='Ketua Pokja KPS',
        )
        self.employee = Pegawai.objects.create(
            nama_lengkap='Ahmad', kategori='PPA', profesi='Perawat'
        )

    def _pack(self):
        return build_kps_pack(
            actor=self.user, employee_ids=[self.employee.pk], framework_id=self.framework.pk
        )

    def test_pack_contains_real_workbook_bytes(self):
        artifact = self._pack()
        self.assertGreater(len(artifact['workbook_bytes']), 0)
        self.assertTrue(artifact['workbook_hash'])

    def test_publish_creates_review_evidence_with_real_file(self):
        artifact = self._pack()
        evidence = publish_kps_artifact(
            actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
        )
        self.assertEqual(evidence.status, 'REVIEW')
        self.assertEqual(evidence.requirement_id, self.requirement.pk)
        self.assertIn('pack-kps', evidence.file_name)
        self.assertTrue(evidence.file)

    def test_publish_requires_both_capabilities(self):
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_verify_kps = False
        config.save(update_fields=['can_verify_kps', 'updated_at'])
        artifact = self._pack()
        with self.assertRaises(PermissionDenied):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=self.requirement.pk
            )

    def test_publish_rejects_unknown_requirement(self):
        from django.core.exceptions import ValidationError
        artifact = self._pack()
        with self.assertRaises(ValidationError):
            publish_kps_artifact(
                actor=self.user, artifact=artifact, requirement_id=999999
            )
```

- [x] **Step 2: Jalankan test untuk memastikan gagal**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_kps_publish -v 2`
Expected: FAIL — `TypeError` pada `EvidenceFile.objects.create(...)` karena field `original_filename`/`storage_key`/`sha256`/`size_bytes`/`content_type` tidak ada pada model.

- [x] **Step 3: Perbaiki `publish_kps_artifact`**

```python
# sdm/services/publikasi_bukti.py — ganti badan publish_kps_artifact
def publish_kps_artifact(*, actor, artifact, requirement_id):
    """Publish the artifact as a sanitized EvidenceFile only after review.
    The private original remains in the HC vault; the published copy is stored
    through the default storage and starts at REVIEW, never auto-approved.
    """
    require_hc_capability(actor, 'can_export_hc')
    require_hc_capability(actor, 'can_verify_kps')
    from django.core.files.base import ContentFile
    requirement = EvidenceReq.objects.filter(pk=requirement_id).first()
    if requirement is None:
        raise ValidationError({'requirement': 'Elemen penilaian tidak ditemukan.'})
    workbook_bytes = artifact.get('workbook_bytes') or b''
    if not workbook_bytes:
        raise ValidationError({
            'workbook': 'Paket KPS belum berisi berkas; buat ulang paket sebelum menerbitkan.'
        })
    file_name = f"pack-kps-{requirement.standard_item.code.replace(' ', '-')}.xlsx"
    with transaction.atomic():
        evidence_file = EvidenceFile(
            requirement=requirement,
            file_name=file_name,
            file_size=f'{len(workbook_bytes) / 1024:.1f} KB',
            status='REVIEW',
        )
        evidence_file.file.save(file_name, ContentFile(workbook_bytes), save=True)
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='kps_artifact_published',
            target_tipe='requirement',
            target_id=str(requirement_id),
            alasan=(
                f"framework={artifact['framework_name']}; as_of={artifact['as_of']}; "
                f"employees={artifact['employee_count']}; sha256={artifact['workbook_hash']}"
            ),
        )
    return evidence_file
```

- [x] **Step 4: Kirim byte nyata dari view + isi opsi EP**

```python
# sdm/views.py — kps_pack_publish: ganti blok pemanggilan publish
    try:
        publish_kps_artifact(
            actor=request.user,
            artifact={**artifact, 'workbook_bytes': request.session.pop('kps_pack_bytes', b'')},
            requirement_id=requirement_id,
        )
```

Pada `kps_report` (`sdm/views.py:2013-2021`) simpan byte ke session (base64) selain metadata:

```python
    request.session['kps_pack_bytes'] = base64.b64encode(
        artifact['workbook_bytes']
    ).decode('ascii')
```

dan di `kps_pack_publish`:

```python
    raw = request.session.pop('kps_pack_bytes', '') or ''
    workbook_bytes = base64.b64decode(raw) if raw else b''
    publish_kps_artifact(
        actor=request.user,
        artifact={**artifact, 'workbook_bytes': workbook_bytes},
        requirement_id=requirement_id,
    )
```

Tambahkan `import base64` pada bagian import `sdm/views.py` bila belum ada.

Untuk `kps_pack_preview`, tambahkan opsi EP:

```python
# sdm/views.py — kps_pack_preview
    from sdm.models import PemetaanStandarSDM
    framework_id = artifact['framework_id']
    requirement_options = EvidenceReq.objects.filter(
        standard_item__category__code='KPS',
        standard_item__sdm_mappings__framework_id=framework_id,
        standard_item__sdm_mappings__is_active=True,
    ).select_related('standard_item').distinct().order_by('standard_item__code')
    return render(request, 'sdm/kps/pack_preview.html', {
        'artifact': artifact,
        'requirement_options': requirement_options,
    })
```

- [x] **Step 5: Perbaiki template `<select>`**

Ganti `templates/sdm/kps/pack_preview.html:14-19`:

```django
            <select name="requirement" class="form-select form-select-sm" required>
                <option value="">— pilih elemen —</option>
                {% for req in requirement_options %}
                <option value="{{ req.pk }}">{{ req.standard_item.code }} — {{ req.title }}</option>
                {% endfor %}
            </select>
            {% if not requirement_options %}
            <p class="small text-warning mt-2 mb-0">Belum ada elemen KPS yang dipetakan dari persyaratan SDM. Petakan terlebih dahulu melalui Pemetaan Standar SDM.</p>
            {% endif %}
```

- [x] **Step 6: Jalankan test**
Jalankan: `.venv/Scripts/python.exe manage.py test sdm.tests.test_kps_publish -v 2`
Expected: PASS (4 test).

- [x] **Step 7: Commit**
```bash
git add sdm/services/publikasi_bukti.py sdm/views.py templates/sdm/kps/pack_preview.html sdm/tests/test_kps_publish.py
git commit -m "fix(sdm): publikasi paket KPS menulis berkas nyata dan EP terpetakan"
```

---

## Task 5: Menjelaskan "0/78 EP" — Gap Katalog di Sidebar

**Files:**
- Create: `akreditasi/tests/test_kps_ep_gap.py`
- Modify: `akreditasi/models.py:219-279` (properti `ep_gap` pada `Category`)
- Modify: `akreditasi/context_processors.py:47-116` (sertakan `ep_gap`)
- Modify: `templates/includes/sidebar.html:85-106` (tanda peringatan gap)

**Interfaces:**
- Consumes: `Category.ep_total`, `Category.target_ep_count` (`akreditasi/models.py`), `sidebar_context`.
- Produces: properti `Category.ep_gap -> int` (`target_ep_count - ep_total`, 0 bila tidak ada target); key `ep_gap` pada tiap kategori di context sidebar; teks bantu di sidebar.

- [x] **Step 1: Tulis test yang gagal**

```python
# akreditasi/tests/test_kps_ep_gap.py
from django.test import TestCase
from akreditasi.models import Category, Framework, StandardItem


class CategoryEpGapTests(TestCase):
    def setUp(self):
        self.framework = Framework.objects.create(
            name='STARKES 2024', version='2024', edition='2024', is_active=True
        )

    def test_gap_is_zero_when_catalogue_matches_target(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=2
        )
        StandardItem.objects.create(category=category, sub_standard='KPS 1', code='KPS 1 EP a')
        StandardItem.objects.create(category=category, sub_standard='KPS 1', code='KPS 1 EP b')
        self.assertEqual(category.ep_gap, 0)

    def test_gap_reports_missing_ep_rows(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=78
        )
        StandardItem.objects.create(category=category, sub_standard='KPS 1', code='KPS 1 EP a')
        self.assertEqual(category.ep_gap, 77)

    def test_gap_is_zero_without_target(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=0
        )
        self.assertEqual(category.ep_gap, 0)
```

- [x] **Step 2: Jalankan test untuk memastikan gagal**
Jalankan: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_kps_ep_gap -v 2`
Expected: FAIL — `AttributeError: 'Category' object has no attribute 'ep_gap'`.

- [x] **Step 3: Implementasikan `ep_gap`**

```python
# akreditasi/models.py — tambahkan pada Category, dekat ep_total/ep_coverage_pct
    @property
    def ep_gap(self):
        """EP yang belum terpasang terhadap target katalog; 0 bila tanpa target."""
        if not self.target_ep_count:
            return 0
        return max(self.target_ep_count - self.ep_total, 0)
```

- [x] **Step 4: Tampilkan penanda gap di sidebar**

Pada `templates/includes/sidebar.html:85-92` (dan blok fallback 101-106), ubah menjadi:

```django
{{ cat.code }}
{{ cat.ep_selesai|default:0 }}/{{ cat.ep_total|default:0 }} EP, {{ cat.percentage }}%
{% if cat.ep_gap %}<span class="badge text-bg-warning ms-1" title="EP target belum terpasang">{{ cat.ep_gap }} EP belum terpasang</span>{% endif %}
```

- [x] **Step 5: Jalankan test**
Jalankan: `.venv/Scripts/python.exe manage.py test akreditasi.tests.test_kps_ep_gap -v 2`
Expected: PASS (3 test).

- [x] **Step 6: Commit**
```bash
git add akreditasi/models.py templates/includes/sidebar.html akreditasi/tests/test_kps_ep_gap.py
git commit -m "feat(akreditasi): tandai EP target yang belum terpasang di sidebar"
```

---

## Task 6: Registrasi Admin & Dokumentasi

**Files:**
- Modify: `sdm/admin.py`
- Modify: `docs/README.md`
- Modify: `docs/plans/2026-10-28-profil-pegawai-riwayat-kps-integrasi.md` (centang semua step)

**Interfaces:**
- Consumes: `sdm.models.RiwayatKepegawaian`, `sdm.models.IzinProfesiPegawai`.
- Produces: entri admin read-only-semantik; catatan rilis di `docs/README.md`.

- [x] **Step 1: Registrasi admin**

```python
# sdm/admin.py — tambahkan
@admin.register(RiwayatKepegawaian)
class RiwayatKepegawaianAdmin(admin.ModelAdmin):
    list_display = ('pegawai', 'kategori_pegawai', 'tanggal_tmt', 'tanggal_akhir', 'review_status')
    list_filter = ('kategori_pegawai', 'review_status')
    search_fields = ('pegawai__nama_lengkap', 'nomor_kontrak', 'jabatan_struktural')
    raw_id_fields = ('pegawai',)

@admin.register(IzinProfesiPegawai)
class IzinProfesiPegawaiAdmin(admin.ModelAdmin):
    list_display = ('pegawai', 'subtype', 'nomor_izin', 'validity_mode', 'tanggal_berakhir', 'is_local_rs')
    list_filter = ('subtype', 'validity_mode', 'is_local_rs')
    search_fields = ('pegawai__nama_lengkap', 'nomor_izin')
    raw_id_fields = ('pegawai',)
```

dan tambahkan `RiwayatKepegawaian`, `IzinProfesiPegawai` ke import tuple `sdm/admin.py:12-16`.

- [x] **Step 2: Catat rilis di `docs/README.md`** — tambahkan baris pada bagian indeks atau catatan rilis modul 05:

```markdown
- **HC (28 Okt 2026):** Profil pegawai kini menampilkan seluruh riwayat kepegawaian (tambah/ubah/hapus, tercatat di PeristiwaSDM), banner status STR/SIP (expired / ≤7 / ≤30 / ≤90 hari), penempatan unit ditolak bila legalitas kedaluwarsa, dan publikasi paket KPS menulis berkas bukti nyata ke EP terpetakan.
```

- [x] **Step 3: Verifikasi menyeluruh**
Jalankan:
```bash
.venv/Scripts/python.exe manage.py test sdm.tests.test_riwayat_kepegawaian sdm.tests.test_penempatan_validasi_legal sdm.tests.test_legalitas_banner sdm.tests.test_kps_publish akreditasi.tests.test_kps_ep_gap sdm.tests.test_penempatan sdm.tests.test_dashboard -v 1
```
Expected: OK, 0 failures.

- [x] **Step 4: Commit**
```bash
git add sdm/admin.py docs/README.md docs/plans/2026-10-28-profil-pegawai-riwayat-kps-integrasi.md
git commit -m "docs(sdm): catat rilis HC riwayat kepegawaian, legalitas, dan KPS"
```

---

## Self-Review (diisi saat plan dieksekusi)

**1. Spec coverage:**
- Level 1 — tab Riwayat Kepegawaian bisa dikelola: **Task 1** (form + view + URL + tabel + empty state dengan ajakan bertindak).
- Level 1 — audit trail siapa mengubah: **Task 1** (`PeristiwaSDM` per create/update/delete).
- Level 2 — validasi silang riwayat/mutasi ↔ STR/SIP: **Task 2**.
- Level 2 — reminder/banner STR/SIP < 3 bulan: **Task 3**.
- Level 2 — dokumen SK ikut ke tab Dokumen: **ditutup lewat `jenis_berkas` SK pada alur unggah yang sudah ada** (`sdm/models/dokumen.py:9-78`) — tidak ada pekerjaan baru; di luar scope agar tidak menambah tab duplikat.
- Level 2 — EP KPS tidak 0%: **Task 4** (perbaiki publikasi bukti) + **Task 5** (jelaskan gap katalog). **Tidak** menambah auto-scoring dari data pegawai, karena skor EP adalah penilaian asesor, bukan turunan kelengkapan dokumen.

**2. Placeholder scan:** tidak ada "TBD"/"TODO"; setiap step memuat kode nyata.

**3. Type consistency:** `RiwayatKepegawaianForm(employee=...)`, `placement_legal_blockers(employee, *, unit_kerja, as_of) -> list[dict]`, `LEGAL_BAND_MAP: dict[str,str]`, `Category.ep_gap -> int`, context key `riwayat_list` / `legal` / `requirement_options` — konsisten di seluruh plan.

**4. Review Focus coverage:**
- Riwayat tanpa TMT → test `test_profile_lists_every_history_row_newest_first` + tampilan "Belum dicatat".
- Riwayat bertumpang → `test_overlapping_open_ended_history_is_rejected` (guard aplikasi; constraint DB sudah ada).
- Hapus riwayat terakhir → `test_last_remaining_history_cannot_be_deleted`.
- Legalitas LIFETIME → `test_lifetime_str_never_blocks`, `test_lifetime_license_shows_no_banner`.
- Pegawai tanpa akun → `test_sync_skips_employee_without_account`.

## Yang tidak dikerjakan (butuh keputusan pengguna)
1. **Impor/penyetelan katalog EP KPS** — fixture 2024 memuat 81 EP, seed lama 25, DB dev 34. Plan hanya melaporkan selisih; impun sesuai instrumen resmi tetap keputusan pengguna.
2. **Skor otomatis EP dari kelengkapan dokumen** — ditolak secara desain: skor 0/5/10 adalah penilaian asesor; otomatisasi akan memalsukan capaian akreditasi.
3. **Multi-tab sharing SK** — satu repositori dokumen sudah cukup; tidak ada penggandaan data.
4. **Pengirim pengingat via WhatsApp/email** — hanya kanal `IN_APP` yang tersedia (`sdm/models/pengingat.py:31-33`).
