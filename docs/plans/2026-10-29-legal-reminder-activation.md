# Plan: Aktivasi Reminder Legalitas STR/SIP

**Goal:** Menyambungkan `sync_legal_reminders` yang sudah ada ke jalur produksi `hc_reminders`, agar STR/SIP kedaluwarsa atau akan habis benar-benar memunculkan pengingat in-app.

**Context:** `sync_legal_reminders` (`sdm/services/legalitas.py:184`) hanya dipanggil dari test — nol pemanggil produksi. `sync_all_reminders` (`sdm/models/pengingat.py:295`) hanya menjalankan `sync_expiry_reminders`, `sync_task_reminders`, dan `sync_spk_reminders`, yang tidak memindai `IzinProfesiPegawai`. Akibatnya banner legalitas dan reminder yang diperbaiki di Task 3 tidak pernah aktif di runtime. Scheduler `hc_reminders` tidak ada di repo (`Procfile` hanya `web:`) dan sengaja di luar cakupan plan ini — itu keputusan deployment.

## Approach

### Step 1 — Tambah wrapper bulk di `sdm/services/legalitas.py`

Sisipkan setelah `sync_legal_reminders` (akhir file, sekitar baris 243):

```python
def sync_legal_reminders_all(*, as_of=None):
    """Bulk entry point: refresh legal reminders for every employee with an account.

    Mirrors the other bulk sync helpers in sdm.models.pengingat: one queryset
    plus per-employee delegation, returning an aggregate dict.
    """
    as_of = as_of or timezone.localdate()
    totals = {'created': 0, 'updated': 0, 'archived': 0}
    employees = Pegawai.objects.filter(
        akun__isnull=False, akun__is_active=True
    ).select_related('akun')
    for employee in employees:
        result = sync_legal_reminders(
            employee=employee, actor=None, as_of=as_of
        )
        for key in totals:
            totals[key] += result.get(key, 0)
    return totals
```

Ubah import di baris 10 file yang sama dari
`from sdm.models import IzinProfesiPegawai, PenugasanKlinis, PengingatSDM, VersiDokumen`
menjadi
`from sdm.models import IzinProfesiPegawai, Pegawai, PenugasanKlinis, PengingatSDM, VersiDokumen`.

Alasan: `legal_status` menjalankan 2 query per pegawai (`IzinProfesiPegawai` + `PenugasanKlinis`). Satu queryset pegawai dengan `select_related('akun')` menjaga pola yang sama dengan sync bulk lain dan menghindari query berulang. `akun__is_active=True` diperlukan karena pengingat in-app hanya berguna untuk akun aktif; pegawai tanpa akun sudah ditangani di dalam `sync_legal_reminders`.

### Step 2 — Persempit filter arsip di `sync_legal_reminders`

Di `sdm/services/legalitas.py`, ganti blok arsip terakhir:

```python
    archived = PengingatSDM.objects.filter(
        employee=employee, recipient=recipient, read_at__isnull=True,
        idempotency_key__startswith='DOCUMENT:',
    ).exclude(idempotency_key__in=urgent_keys).update(read_at=as_of)
```

menjadi:

```python
    archived = PengingatSDM.objects.filter(
        employee=employee, recipient=recipient, read_at__isnull=True,
        idempotency_key__contains=':legal:',
    ).exclude(idempotency_key__in=urgent_keys).update(read_at=as_of)
```

Alasan: filter lama (`startswith='DOCUMENT:'`) ikut mengarsipkan pengingat dokumen biasa milik pegawai yang sama — kunci dokumen berbentuk `DOCUMENT:<pegawai>:<version_pk>:<band>`, sedangkan kunci legalitas berbentuk `DOCUMENT:<pegawai>:legal:izin_profesi:<nomor>:<band>`. Filter `:legal:` hanya cocok dengan yang legalitas. Verifikasi kunci nyata: `PengingatSDM.build_key(employee_id='e', version_id='legal:izin_profesi:STR-1', band='LT_30')` menghasilkan `DOCUMENT:e:legal:izin_profesi:STR-1:LT_30`, versus `DOCUMENT:e:123:LT_30`.

### Step 3 — Panggil dari `sync_all_reminders`

Di `sdm/models/pengingat.py`, ganti:

```python
def sync_all_reminders(*, as_of=None):
    return (
        sync_expiry_reminders(as_of=as_of)
        + sync_task_reminders(as_of=as_of)
        + sync_spk_reminders(as_of=as_of)
    )
```

menjadi:

```python
def sync_all_reminders(*, as_of=None):
    created = (
        sync_expiry_reminders(as_of=as_of)
        + sync_task_reminders(as_of=as_of)
        + sync_spk_reminders(as_of=as_of)
    )
    # Legalitas (STR/SIP/SPK) dipindai per pegawai oleh service legalitas;
    # import ditunda di dalam fungsi karena modul itu mengimpor modul ini.
    from sdm.services.legalitas import sync_legal_reminders_all
    created += sum(sync_legal_reminders_all(as_of=as_of).values())
    return created
```

Alasan: import ditunda di dalam badan fungsi untuk menghindari circular import — `sdm/services/legalitas.py` mengimpor `sdm.models.pengingat` (untuk `LEGAL_BAND_MAP`), jadi `pengingat` tidak boleh mengimpor `legalitas` di level modul. Jumlahkan ketiga nilai dict (`created`, `updated`, `archived`) supaya keluaran `hc_reminders` tetap satu integer seperti sebelumnya. Jangan pisahkan target_type legalitas dari `DOCUMENT`: `PengingatSDM.TARGET_CHOICES` tidak punya anggota `LICENSE`, dan menambah anggota baru berarti migrasi plus perubahan tampilan portal.

### Step 4 — Tes

Buat `sdm/tests/test_legal_reminder_activation.py`:

```python
from datetime import timedelta
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO
from sdm.models import (
    IzinProfesiPegawai,
    Pegawai,
    PengingatSDM,
)
from sdm.services.legalitas import sync_legal_reminders_all


class LegalReminderActivationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.today = timezone.localdate()
        self.user = get_user_model().objects.create_user(username='legal-act')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Aktif', kategori='PPA', profesi='Perawat',
            akun=self.user,
        )

    def _izin(self, **kwargs):
        defaults = dict(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-ACT',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
            is_local_rs=True,
        )
        defaults.update(kwargs)
        return IzinProfesiPegawai.objects.create(**defaults)

    def test_command_creates_reminder_for_urgent_str(self):
        self._izin()
        out = StringIO()
        call_command('hc_reminders', stdout=out)
        reminder = PengingatSDM.objects.get(employee=self.employee)
        self.assertEqual(reminder.band, 'LT_30')
        self.assertIn('STR-ACT', reminder.alasan)

    def test_command_is_idempotent(self):
        self._izin()
        call_command('hc_reminders', stdout=StringIO())
        call_command('hc_reminders', stdout=StringIO())
        self.assertEqual(PengingatSDM.objects.filter(employee=self.employee).count(), 1)

    def test_expired_str_maps_to_expired_band(self):
        self._izin(tanggal_berakhir=self.today - timedelta(days=3))
        sync_legal_reminders_all()
        self.assertEqual(
            PengingatSDM.objects.get(employee=self.employee).band, 'EXPIRED'
        )

    def test_employee_without_account_is_skipped(self):
        lone = Pegawai.objects.create(nama_lengkap='Tanpa Akun', kategori='NON_PPA')
        IzinProfesiPegawai.objects.create(
            pegawai=lone, subtype='STR', nomor_izin='STR-LONE',
            validity_mode='DATED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=20),
            is_local_rs=True,
        )
        sync_legal_reminders_all()
        self.assertEqual(PengingatSDM.objects.filter(employee=lone).count(), 0)

    def test_inactive_account_is_skipped(self):
        from django.contrib.auth import get_user_model
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self._izin()
        sync_legal_reminders_all()
        self.assertEqual(PengingatSDM.objects.filter(employee=self.employee).count(), 0)

    def test_document_reminder_survives_legal_sync(self):
        from sdm.models import DokumenPegawai, VersiDokumen
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL',
            jenis_berkas='STR', title='STR Dokumen', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='str.pdf',
            storage_key='act-test/str.pdf', sha256='0' * 64, size_bytes=1024,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=15),
        )
        self._izin()
        call_command('hc_reminders', stdout=StringIO())
        keys = set(
            PengingatSDM.objects.filter(
                employee=self.employee, read_at__isnull=True
            ).values_list('idempotency_key', flat=True)
        )
        self.assertEqual(len(keys), 2, keys)
        self.assertTrue(any(':legal:' in k for k in keys))
        self.assertTrue(any(k.endswith(':LT_30') and ':legal:' not in k for k in keys))
```

Catatan: `test_document_reminder_survives_legal_sync` adalah regresi guard untuk Step 2 — dengan filter arsip lama, pengingat dokumen akan terarsipkan dan tes gagal.

### Step 5 — Commit

```bash
git add sdm/services/legalitas.py sdm/models/pengingat.py sdm/tests/test_legal_reminder_activation.py
git commit -m "feat(sdm): aktifkan sinkron reminder legalitas pada hc_reminders"
```

## Verification

Dari root repo:

```bash
.venv/Scripts/python.exe manage.py test sdm.tests.test_legal_reminder_activation sdm.tests.test_legalitas sdm.tests.test_legalitas_banner sdm.tests.test_dashboard -v 2
```

Expected: `OK`, 0 failures. `sdm/tests/test_dashboard.py:226` memakai `call_command('hc_reminders', stdout=output)` sehingga menutup integrasi command end-to-end.

Bukti perilaku baru (end-to-end, bukan hanya suite):

```bash
.venv/Scripts/python.exe manage.py shell -c "
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.management import call_command
from sdm.models import Pegawai, IzinProfesiPegawai, PengingatSDM
from io import StringIO
u = get_user_model().objects.create_user(username='smoke-legal')
e = Pegawai.objects.create(nama_lengkap='Smoke Legal', kategori='PPA', profesi='Perawat', akun=u)
IzinProfesiPegawai.objects.create(pegawai=e, subtype='SIP', nomor_izin='SIP-SMOKE', validity_mode='DATED', tanggal_terbit=timezone.localdate()-timedelta(days=50), tanggal_berakhir=timezone.localdate()+timedelta(days=25), is_local_rs=True)
out = StringIO(); call_command('hc_reminders', stdout=out)
print(out.getvalue().strip())
for r in PengingatSDM.objects.filter(employee=e):
    print(r.band, '|', r.alasan, '|', r.target_type)
"
```

Expected: baris `REMINDERS created=N` dengan `N >= 1`, lalu satu baris `LT_30 | 8–30 hari: SIP-SMOKE | DOCUMENT`. Jalankan shell yang sama dua kali untuk konfirmasi `created` tidak bertambah (idempoten).

Bersihkan data smoke setelah verifikasi: hapus `PengingatSDM`, `IzinProfesiPegawai`, `PenempatanPegawai`, `PenugasanOrientasi` milik pegawai smoke, lalu `Pegawai`, lalu user — urutannya wajib karena FK `PROTECT`. `PeristiwaSDM` bersifat immutable dan tidak dapat dihapus; biarkan.

## Assumptions

- Scheduler `hc_reminders` tidak masuk plan ini (keputusan deployment: cron eksternal). Setelah plan ini, sinkron legalitas berjalan setiap kali `hc_reminders` dipanggil — belum otomatis sampai scheduler ada.
- Pengingat legalitas memakai `target_type='DOCUMENT'` yang sudah ada, bukan anggota `TARGET_CHOICES` baru, agar tidak perlu migrasi dan tanpa perubahan tampilan portal.
- `sync_legal_reminders_all` mengembalikan dict agregat, bukan integer, karena perlu membedakan `created` dari `updated`/`archived` saat diagnosis; `sync_all_reminders` yang menjumlahkannya ke integer.
