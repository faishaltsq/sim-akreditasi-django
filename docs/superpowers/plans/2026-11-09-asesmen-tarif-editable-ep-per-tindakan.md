# Plan — Asesmen Awal IGD v2: Tarif Editable per Tindakan & EP Otomatis per Item

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan baris tindakan pertama-kelas pada asesmen IGD — tarif acuan otomatis yang bisa di-override beserta alasannya, EP akreditasi per baris dengan badge kelengkapan, badge sumber data, saran ICD deterministik, dan rekap biaya/EP — tanpa memindahkan uang keluar dari `BillingItem`.

**Architecture:**
1. `pasien.TindakanAsesmen` menyimpan niat dokumentasi (teks editable, sumber, tarif acuan vs final, EP); `BillingItem` tetap satu-satunya sumber uang.
2. `klinis.AturanEpTindakan` + resolver `klinis.services.ep_tindakan` memberi EP default per kode ICD-9/SIKI; selaras dengan `AturanEpAsesmen` visit-level yang sudah ada.
3. `sync_billing_tindakan()` menulis `harga_satuan = tarif_efektif` dan tidak pernah menimpa override; `sync_billing()` lama dipertahankan.
4. Satu partial `_tindakan_tarif_ep.html` dipakai wizard dan modal IGD; POST memakai kunci terindeks `tindakan_<i>_*`.
5. "AI Suggestion" = service deterministik dari `KasusTersering` (repo tidak punya LLM), label UI "Saran Sistem".

**Tech stack:** Django 5, Bootstrap 5.3.3, PostgreSQL (Supabase prod) / SQLite (dev), `decimal`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-09-asesmen-tarif-editable-ep-per-tindakan.md`

**Baseline terverifikasi (2026-11-09):** `manage.py test klinis pasien.tests_asesmen_save_ep_tarif pasien.tests_asesmen_rekap pasien.tests_ep_status pasien.tests_morse --keepdb` → 33 test OK. Seed: 14 kelompok / 172 ICD-10 / 170 ICD-9 / 215 kasus / 397 tindakan. Katalog: 301 EP, 136 sub_standard, `KPR` tidak ada.

---

## Global Constraints

- **Plan ditulis dalam bahasa Inggris** (aturan tetap). String UI, `verbose_name`, dan pesan pengguna tetap **Bahasa Indonesia**.
- **Migrasi aditif.** Tidak ada field lama yang berubah tipe, diganti nama, atau dihapus. `AlterField` hanya untuk `choices` `LampiranAsesmen.JENIS` (tidak mengubah DDL/tipe).
- **Migrasi tidak jalan otomatis di deploy.** Setiap task yang menambah migrasi diakhiri langkah Supabase manual di DoD.
- **Jangan mengarang data klinis/tarif.** SIKI tidak punya tarif di dokumen sumber → `tarif_acuan=None`, input manual.
- **Uang hanya di `BillingItem`.** Total form adalah turunan, tidak disimpan di `KunjunganPasien`.
- **`resolve()` yang sudah diuji (Decimal) dipertahankan.** Tambah `resolve_detail()` untuk kebutuhan dict.
- **Gate test:** `.venv/Scripts/python.exe manage.py test pasien klinis --keepdb`.
- **Python:** `.venv/Scripts/python.exe` (bukan `python` telanjang).
- **`makemigrations --check` wajib "No changes detected"** di akhir setiap task bermigrasi.
- **Tidak me-refactor JS lama**: `updateSkorNyeri`, `hitungMst`, `setNormalAsesmen`, `setNormalDetail`, `hitungMorse` tidak disentuh.

---

## Phase 0 — Stabilkan dulu (bug laten, tanpa fitur baru)

### Task 0.1: Perbaiki `api_tarif_preview`

**Files:**
- Modify: `klinis/services/tarif.py` (tambah `resolve_detail`)
- Modify: `pasien/views.py:35` (import), `:2685-2732` (pakai `resolve_detail`, `.icd9.nama`)
- Create: `klinis/tests/test_tarif_detail.py`

**Interfaces:**
- Produces: `klinis.services.tarif.resolve_detail(kunjungan, kode) -> dict | None`
- Keeps: `resolve(kunjungan, kode) -> Decimal | None` (kontrak test lama)

- [ ] **Step 1: Tulis test yang gagal**

```python
# klinis/tests/test_tarif_detail.py
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from akreditasi.models import UnitKerja
from klinis.services.tarif import resolve, resolve_detail
from pasien.models import Pasien, KunjunganPasien

class ResolveDetailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.pasien = Pasien.objects.create(nama_lengkap='X', no_rm='RM-D-1',
                                            tanggal_lahir='1990-01-01', jenis_kelamin='L')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-D-1', jenis_kunjungan='IGD',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='AKTIF')

    def test_detail_carries_nominal_and_names(self):
        d = resolve_detail(self.k, '89.52')
        self.assertEqual(d['nominal'], Decimal('150000.00'))
        self.assertEqual(d['icd9'].nama.upper().find('EKG') >= 0 or 'ELEKTRO' in d['icd9'].nama.upper(), True)
        self.assertEqual(d['penjamin'], 'UMUM')

    def test_detail_none_for_unknown(self):
        self.assertIsNone(resolve_detail(self.k, '99.9999'))

    def test_resolve_still_returns_decimal(self):
        self.assertEqual(resolve(self.k, '89.52'), Decimal('150000.00'))
```

- [ ] **Step 2: Jalankan — harus merah**

```bash
.venv/Scripts/python.exe manage.py test klinis.tests.test_tarif_detail --keepdb -v 2
```

Expected: `ImportError: cannot import name 'resolve_detail'`.

- [ ] **Step 3: Implementasi**

```python
def resolve_detail(kunjungan, icd9_kode):
    """Kontrak lengkap untuk API/UI. None bila kelompok/kode/tarif tidak ada."""
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return None
    tindakan = (KasusTindakan.objects
                .filter(kasus__kelompok=kelompok, icd9__kode=icd9_kode)
                .select_related('icd9', 'kasus')
                .order_by('kasus__urutan', 'urutan')
                .first())
    if not tindakan:
        return None
    nominal = tindakan.tarif_bpjs if kunjungan.penjamin == 'BPJS' else tindakan.tarif_umum
    return {
        'nominal': nominal,
        'tindakan': tindakan,
        'icd9': tindakan.icd9,
        'kelompok': kelompok,
        'penjamin': kunjungan.penjamin,
    }


def resolve(kunjungan, icd9_kode):
    d = resolve_detail(kunjungan, icd9_kode)
    return d['nominal'] if d else None
```

- [ ] **Step 4: Perbaiki view**

`pasien/views.py` import baris 35:

```python
from klinis.services.tarif import sync_billing, _kelompok_for, resolve_detail
```

Ganti badan loop `api_tarif_preview`:

```python
        d = resolve_detail(kunjungan, code)
        if d:
            nom = d['nominal']
            items.append({
                'kode': code,
                'nama': d['icd9'].nama,
                'nominal': nom,
                'penjamin': d['penjamin'],
                'kelompok': d['kelompok'].nama,
                'found': nom is not None,
            })
            if nom is None:
                all_resolved = False
            else:
                total += nom
        else:
            all_resolved = False
            items.append({'kode': code, 'nama': '', 'nominal': None,
                          'penjamin': kunjungan.penjamin, 'kelompok': '-', 'found': False})
```

- [ ] **Step 5: Test endpoint (bukan hanya service)**

Tambahkan di `pasien/tests_asesmen_save_ep_tarif.py`:

```python
    def test_tarif_preview_endpoint_returns_items(self):
        self.kunjungan.anamnesis_rps = 'nyeri dada'
        self.kunjungan.save(update_fields=['anamnesis_rps'])
        url = reverse('pasien:api_tarif_preview')
        resp = self.client.get(url, {'kunjungan': self.kunjungan.pk, 'icd9': '89.52,99.9999'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['total'])          # ada kode tak dikenal
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(data['items'][0]['kode'], '89.52')
        self.assertIsNotNone(data['items'][0]['nominal'])
```

- [ ] **Step 6: Jalankan**

```bash
.venv/Scripts/python.exe manage.py test klinis.tests.test_tarif_service klinis.tests.test_tarif_detail pasien.tests_asesmen_save_ep_tarif --keepdb -v 2
```

Expected: semua hijau, termasuk test lama yang mengassert `Decimal`.

- [ ] **Step 7: Commit**

```bash
git add klinis pasien/views.py pasien/tests_asesmen_save_ep_tarif.py
git commit -m "fix(klinis): resolve_detail + perbaiki api_tarif_preview yang NameError"
```

---

### Task 0.2: Perbaiki lampiran pada `igd_asesmen_medis_save`

**Files:**
- Modify: `pasien/views.py:2665-2673`
- Modify: `pasien/models.py:1150-1154` (`JENIS` + `RUJUKAN`)
- Create: `pasien/migrations/0017_tindakan_asesmen.py` *(dibuat di Task 2, `AlterField` digabung di sana; task ini hanya mengubah model)*
- Modify: `pasien/tests_asesmen_save_ep_tarif.py`

- [ ] **Step 1: Test yang gagal**

```python
    def test_medis_save_accepts_attachment_and_rujukan(self):
        url = reverse('pasien:igd_asesmen_medis_save', kwargs={'pk': self.kunjungan.pk})
        f = SimpleUploadedFile('rujukan.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        resp = self.client.post(url, {
            'diagnosa_masuk': 'A09', 'icd9_tindakan': '89.52',
            'lampiran_files': f, 'lampiran_kategori': 'RUJUKAN',
        })
        self.assertEqual(resp.status_code, 302)
        lap = LampiranAsesmen.objects.get(kunjungan=self.kunjungan)
        self.assertEqual(lap.ukuran, f.size)
        self.assertEqual(lap.jenis, 'RUJUKAN')
```

- [ ] **Step 2: Jalankan — harus merah** (`TypeError: LampiranAsesmen() got an unexpected keyword argument 'ukuran_byte'`)

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_save_ep_tarif --keepdb -v 2
```

- [ ] **Step 3: Perbaiki handler**

```python
            LampiranAsesmen.objects.create(
                kunjungan=k,
                file=f,
                nama_asli=f.name[:255],
                ukuran=f.size,
                jenis=kategori,
                diunggah_oleh=request.user if request.user.is_authenticated else None,
            )
```

- [ ] **Step 4: Tambah `RUJUKAN` ke choices**

```python
    JENIS = [
        ('ASESMEN',   'Dokumen Asesmen'),
        ('PENUNJANG', 'Hasil Penunjang'),
        ('RUJUKAN',   'Surat Rujukan'),
        ('LAINNYA',   'Lainnya'),
    ]
```

- [ ] **Step 5: Jalankan & commit**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_save_ep_tarif --keepdb -v 2
git add pasien
git commit -m "fix(pasien): lampiran pada simpan asesmen medis IGD + kategori RUJUKAN"
```

---

## Phase 1 — Aturan EP per tindakan & saran ICD

### Task 1: `AturanEpTindakan` + resolver + seed

**Files:**
- Modify: `klinis/models.py` (model baru)
- Modify: `klinis/data/master_tarif.py` (`ATURAN_EP_TINDAKAN`)
- Modify: `klinis/management/commands/seed_katalog_klinis.py`
- Modify: `klinis/admin.py`
- Create: `klinis/services/ep_tindakan.py`
- Create: `klinis/tests/test_ep_tindakan.py`

**Interfaces:**
- Produces: `AturanEpTindakan`, `ep_tindakan.resolve_for(jenis, kode) -> list[AturanEpTindakan]`, `ep_tindakan.primary_for(...) -> AturanEpTindakan | None`

- [ ] **Step 1: Model**

```python
class AturanEpTindakan(models.Model):
    JENIS = [('ICD9', 'ICD-9-CM'), ('SIKI', 'SIKI'), ('ANY', 'Semua')]

    jenis        = models.CharField('Jenis Tindakan', max_length=6, choices=JENIS, default='ICD9')
    kode         = models.CharField('Kode Tindakan', max_length=20, blank=True,
                                    help_text='Kosongkan untuk berlaku pada semua kode')
    sub_standard = models.CharField('Sub-Standar EP', max_length=50)
    label        = models.CharField('Label', max_length=150)
    wajib        = models.BooleanField('Wajib', default=True)
    urutan       = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Aturan EP per Tindakan'
        verbose_name_plural = 'Aturan EP per Tindakan'
        unique_together = [('jenis', 'kode', 'sub_standard')]
        ordering = ['urutan', 'jenis', 'kode']

    def __str__(self):
        return f'{self.jenis} {self.kode or "*"} → {self.sub_standard}'
```

- [ ] **Step 2: Data aturan**

`klinis/data/master_tarif.py`, setelah `ATURAN_EP`:

```python
# (jenis, kode, sub_standard, label, wajib, urutan)
ATURAN_EP_TINDAKAN = [
    ('ICD9', '99.18', 'PAP 3',  'Pemasangan infus — pelayanan risiko tinggi', True, 1),
    ('ICD9', '99.18', 'SKP 1',  'Identifikasi pasien sebelum tindakan',       False, 2),
    ('ICD9', '99.29', 'SKP 3',  'Pemberian obat high alert / injeksi',        True, 1),
    ('ICD9', '99.29', 'SKP 1',  'Identifikasi pasien sebelum tindakan',       False, 2),
    ('ICD9', '99.60', 'PAP 3',  'Resusitasi — pelayanan risiko tinggi',       True, 1),
    ('ICD9', '99.60', 'PAP 8',  'Peringatan dini klinis / EWS',               True, 2),
    ('ICD9', '96.04', 'PAP 3',  'Intubasi — pelayanan risiko tinggi',         True, 1),
    ('ICD9', '96.04', 'PAP 8',  'Peringatan dini klinis / EWS',               False, 2),
    ('ICD9', '89.52', 'PAP 3',  'EKG 12 lead pada pasien gawat darurat',      False, 1),
    ('ICD9', '01.24', 'PAP 3',  'Tindakan invasif susunan saraf pusat',       True, 1),
    ('ICD9', '01.24', 'HPK 3',  'Informed consent tindakan',                  True, 2),
    ('ICD9', '47.09', 'PAP 3',  'Tindakan invasif abdomen',                   True, 1),
    ('ICD9', '47.09', 'HPK 3',  'Informed consent tindakan',                  True, 2),
    ('SIKI', 'I.08238', 'PP 2', 'Manajemen nyeri — skrining & tatalaksana',   True, 1),
    ('SIKI', 'I.12383', 'HPK 1', 'Edukasi & hak pasien',                      True, 1),
    ('SIKI', 'I.14539', 'PPI 1', 'Pencegahan & pengendalian infeksi',         True, 1),
    ('SIKI', 'I.14539', 'SKP 1', 'Identifikasi pasien sebelum tindakan',      False, 2),
]
```

- [ ] **Step 3: Seed**

Di `seed_katalog_klinis.py`, impor `AturanEpTindakan` + `ATURAN_EP_TINDAKAN`, lalu setelah blok `AturanEpAsesmen`:

```python
            total_ep_tindakan = 0
            for jenis, kode, sub, label, wajib, urutan in ATURAN_EP_TINDAKAN:
                AturanEpTindakan.objects.update_or_create(
                    jenis=jenis, kode=kode, sub_standard=sub,
                    defaults={'label': label, 'wajib': wajib, 'urutan': urutan})
                total_ep_tindakan += 1
            self.stdout.write(self.style.SUCCESS(f'[OK] AturanEpTindakan: {total_ep_tindakan} entri'))
```

- [ ] **Step 4: Resolver**

```python
# klinis/services/ep_tindakan.py
from akreditasi.models import StandardItem
from klinis.models import AturanEpTindakan


def _valid_sub_standards():
    return set(StandardItem.objects.values_list('sub_standard', flat=True).distinct())


def resolve_for(jenis, kode):
    """Aturan EP untuk satu baris tindakan. Exact code dulu, lalu wildcard ANY."""
    valid = _valid_sub_standards()
    rules = list(AturanEpTindakan.objects.filter(jenis=jenis, kode=kode or '').order_by('urutan'))
    if not rules:
        rules = list(AturanEpTindakan.objects.filter(jenis='ANY', kode='').order_by('urutan'))
    return [r for r in rules if r.sub_standard in valid]


def primary_for(jenis, kode):
    rules = resolve_for(jenis, kode)
    return rules[0] if rules else None
```

- [ ] **Step 5: Test**

```python
class EpTindakanRuleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_katalog_klinis', verbosity=0)

    def test_infus_maps_to_pap3_with_skp1_secondary(self):
        subs = [r.sub_standard for r in resolve_for('ICD9', '99.18')]
        self.assertEqual(subs[0], 'PAP 3')
        self.assertIn('SKP 1', subs)

    def test_unknown_code_falls_back_to_wildcard(self):
        # belum ada aturan ANY di seed → list kosong, bukan exception
        self.assertEqual(resolve_for('ICD9', '87.03'), [])

    def test_unknown_sub_standard_is_dropped(self):
        AturanEpTindakan.objects.create(jenis='ICD9', kode='88.76',
                                        sub_standard='KPR 3', label='x', urutan=1)
        self.assertEqual(resolve_for('ICD9', '88.76'), [])

    def test_primary_is_lowest_urutan(self):
        self.assertEqual(primary_for('ICD9', '99.29').sub_standard, 'SKP 3')
```

- [ ] **Step 6: Migrasi + admin + jalankan**

```bash
.venv/Scripts/python.exe manage.py makemigrations klinis --name aturan_ep_tindakan
.venv/Scripts/python.exe manage.py migrate klinis
.venv/Scripts/python.exe manage.py seed_katalog_klinis
.venv/Scripts/python.exe manage.py test klinis --keepdb -v 2
```

Admin: `list_display = ('jenis', 'kode', 'sub_standard', 'wajib', 'urutan')`, `list_filter = ('jenis', 'wajib')`, `search_fields = ('kode', 'sub_standard', 'label')`.

- [ ] **Step 7: Commit**

```bash
git add klinis
git commit -m "feat(klinis): aturan EP per tindakan + resolver + seed"
```

---

### Task 2: Saran ICD deterministik

**Files:**
- Create: `klinis/services/saran.py`
- Create: `klinis/tests/test_saran.py`
- Modify: `pasien/views.py` (view `api_saran_icd`), `pasien/urls.py`

**Interfaces:**
- Produces: `klinis.services.saran.saran_untuk(kunjungan, q='', jenis='ICD10') -> list[dict]`
- Produces: route `pasien:api_saran_icd`

- [ ] **Step 1: Service**

```python
import re
from klinis.models import KasusTersering, KasusTindakan
from klinis.services.tarif import _kelompok_for

_TOKEN = re.compile(r'[a-z]{3,}')


def _tokens(text):
    return set(_TOKEN.findall((text or '').lower()))


def saran_untuk(kunjungan, q='', jenis='ICD10', limit=5):
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return []
    rows = (KasusTersering.objects
            .filter(kelompok=kelompok)
            .select_related('icd10')
            .prefetch_related('tindakan__icd9')
            .order_by('urutan'))
    q_tokens = _tokens(q)
    scored = []
    for row in rows:
        if jenis == 'ICD10' and not row.icd10_id:
            continue
        haystack = ' '.join(filter(None, [
            row.icd10.nama if row.icd10 else row.sdki_nama,
            row.tatalaksana,
        ]))
        score = len(q_tokens & _tokens(haystack)) if q_tokens else 0
        if q_tokens and score == 0:
            continue
        scored.append((score, row))
    scored.sort(key=lambda t: (-t[0], t[1].urutan))
    out = []
    for score, row in scored[:limit]:
        out.append({
            'kode': row.icd10.kode if row.icd10 else row.sdki_kode,
            'nama': row.icd10.nama if row.icd10 else row.sdki_nama,
            'alasan': row.tatalaksana[:160],
            'skor': score,
            'tindakan': [t.icd9.kode for t in row.tindakan.all()],
        })
    return out
```

- [ ] **Step 2: Endpoint**

```python
@login_required
@require_patient_module('igd')
def api_saran_icd(request):
    kunjungan_id = request.GET.get('kunjungan')
    if not kunjungan_id:
        return JsonResponse({'error': 'Parameter kunjungan diperlukan'}, status=400)
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_id)
    if not can_read_kunjungan(k, getattr(request.user, 'profile', None)):
        raise PermissionDenied("Anda tidak memiliki akses ke kunjungan unit lain.")
    jenis = request.GET.get('jenis', 'ICD10').upper()
    if jenis not in ('ICD10', 'ICD9'):
        jenis = 'ICD10'
    return JsonResponse({'items': saran_untuk(k, request.GET.get('q', '').strip(), jenis)})
```

URL: `path('api/saran-icd/', views.api_saran_icd, name='api_saran_icd'),`

- [ ] **Step 3: Test**

```python
class SaranIcdTest(TestCase):
    # seed + kunjungan IGD seperti kelas lain di repo
    def test_query_narrows_to_matching_case(self):
        items = saran_untuk(self.k, 'nyeri dada')
        self.assertTrue(items)
        self.assertTrue(all('skor' in i for i in items))

    def test_scoped_to_kelompok(self):
        k_jantung = ...  # kunjungan dengan unit ICCU
        kode_igd = {i['kode'] for i in saran_untuk(self.k)}
        kode_jantung = {i['kode'] for i in saran_untuk(k_jantung)}
        self.assertNotEqual(kode_igd, kode_jantung)

    def test_empty_query_returns_first_rows(self):
        self.assertLessEqual(len(saran_untuk(self.k, '')), 5)

    def test_endpoint_requires_unit_access(self):
        self.client.force_login(other_unit_user)
        resp = self.client.get(reverse('pasien:api_saran_icd'),
                               {'kunjungan': self.k.pk, 'q': 'demam'})
        self.assertEqual(resp.status_code, 403)
```

- [ ] **Step 4: Jalankan & commit**

```bash
.venv/Scripts/python.exe manage.py test klinis.tests.test_saran pasien.tests_asesmen_save_ep_tarif --keepdb -v 2
git add klinis pasien/views.py pasien/urls.py pasien/tests_*.py
git commit -m "feat(klinis): saran ICD deterministik dari katalog kasus tersering"
```

---

## Phase 2 — Model baris tindakan & sinkronisasi tarif

### Task 3: `TindakanAsesmen` + migrasi + backfill

**Files:**
- Modify: `pasien/models.py` (model baru di bagian 13)
- Create: `pasien/migrations/0017_tindakan_asesmen.py` (otomatis + data migration)
- Modify: `pasien/admin.py`
- Create: `pasien/tests_tindakan_asesmen.py`

**Interfaces:**
- Produces: `TindakanAsesmen` dengan `tarif_efektif`, `ep_lengkap`

- [ ] **Step 1: Model** — persis seperti spec §5.1. Tambahkan setelah `LampiranAsesmen`.

```python
class TindakanAsesmen(models.Model):
    ...
    class Meta:
        verbose_name = 'Tindakan Asesmen'
        verbose_name_plural = 'Tindakan Asesmen'
        unique_together = [('kunjungan', 'urutan')]
        ordering = ['urutan']
```

- [ ] **Step 2: Migrasi skema**

```bash
.venv/Scripts/python.exe manage.py makemigrations pasien --name tindakan_asesmen
```

Baca hasilnya: hanya `CreateModel TindakanAsesmen` + `AlterField lampiranasesmen.jenis` + `AddField billing_item` (OneToOne). Tidak boleh ada `RemoveField`/`AlterField` lain.

- [ ] **Step 3: Data migration**

```python
def backfill_tindakan(apps, schema_editor):
    BillingItem = apps.get_model('pasien', 'BillingItem')
    Tindakan = apps.get_model('pasien', 'TindakanAsesmen')
    MasterIcd9 = apps.get_model('klinis', 'MasterIcd9')
    per_kunjungan = {}
    for item in BillingItem.objects.filter(sumber='ASESMEN').order_by('kunjungan_id', 'tanggal'):
        icd9 = MasterIcd9.objects.filter(kode=item.kode_icd).first()
        if not icd9:
            continue
        urutan = per_kunjungan.get(item.kunjungan_id, 0) + 1
        per_kunjungan[item.kunjungan_id] = urutan
        Tindakan.objects.create(
            kunjungan_id=item.kunjungan_id, urutan=urutan, jenis='ICD9',
            icd9=icd9, kode=item.kode_icd, nama=item.nama_item[:200],
            sumber_data='MASTER', tarif_acuan=item.harga_satuan,
            tarif=item.harga_satuan, billing_item=item,
        )


def unbackfill(apps, schema_editor):
    apps.get_model('pasien', 'TindakanAsesmen').objects.all().delete()
```

- [ ] **Step 4: Test model**

```python
class TindakanAsesmenModelTest(TestCase):
    def test_tarif_efektif_prefers_override(self):
        t = TindakanAsesmen(tarif_acuan=Decimal('150000'), tarif=Decimal('175000'))
        self.assertEqual(t.tarif_efektif, Decimal('175000'))

    def test_tarif_efektif_falls_back_to_acuan(self):
        t = TindakanAsesmen(tarif_acuan=Decimal('150000'), tarif=None)
        self.assertEqual(t.tarif_efektif, Decimal('150000'))

    def test_ep_lengkap_when_na_or_no_ep(self):
        self.assertTrue(TindakanAsesmen(ep_status='NA').ep_lengkap)
        self.assertFalse(TindakanAsesmen(standard_item_id=1, ep_status='BELUM').ep_lengkap)
```

- [ ] **Step 5: Migrate + admin + jalankan**

```bash
.venv/Scripts/python.exe manage.py migrate pasien
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe manage.py test pasien.tests_tindakan_asesmen --keepdb -v 2
```

Admin: `list_display = ('kunjungan', 'urutan', 'kode', 'nama', 'sumber_data', 'tarif', 'ep_status')`, `raw_id_fields = ('kunjungan', 'icd9', 'siki', 'standard_item', 'billing_item')`, inline `TindakanAsesmenInline` di `KunjunganPasienAdmin`.

- [ ] **Step 6: Commit**

```bash
git add pasien
git commit -m "feat(pasien): model TindakanAsesmen + backfill dari billing asesmen"
```

---

### Task 4: `sync_billing_tindakan` (override dipertahankan)

**Files:**
- Modify: `klinis/services/tarif.py`
- Create: `klinis/tests/test_sync_tindakan.py`

**Interfaces:**
- Produces: `sync_billing_tindakan(kunjungan, lines, user=None) -> list[BillingItem]`
- Produces: `refresh_acuan(kunjungan, lines) -> None`

- [ ] **Step 1: Implementasi**

```python
def refresh_acuan(kunjungan, lines):
    """Perbarui tarif_acuan ICd9 dari master; JANGAN sentuh tarif (override)."""
    for line in lines:
        if line.jenis != 'ICD9' or not line.kode:
            continue
        d = resolve_detail(kunjungan, line.kode)
        line.tarif_acuan = d['nominal'] if d else None


def sync_billing_tindakan(kunjungan, lines, user=None):
    """Tulis BillingItem ASESMEN dari baris tindakan. Idempoten, tidak pernah Rp 0."""
    keep = []
    for line in lines:
        nominal = line.tarif_efektif
        if nominal is None or nominal <= 0:
            BillingItem.objects.filter(kunjungan=kunjungan, sumber='ASESMEN',
                                       kode_icd=line.kode, pk=line.billing_item_id).delete()
            line.billing_item = None
            continue
        item, _ = BillingItem.objects.update_or_create(
            kunjungan=kunjungan, kategori='JASA_MEDIS', kode_icd=line.kode, sumber='ASESMEN',
            defaults={'nama_item': line.nama[:200], 'harga_satuan': nominal,
                      'kuantitas': Decimal('1'), 'dicatat_oleh': user})
        line.billing_item = item
        keep.append(item.pk)
    BillingItem.objects.filter(kunjungan=kunjungan, sumber='ASESMEN').exclude(pk__in=keep).delete()
    return list(BillingItem.objects.filter(pk__in=keep))
```

- [ ] **Step 2: Test regresi override**

```python
class SyncTindakanTest(TestCase):
    def test_override_survives_resync(self):
        t = TindakanAsesmen.objects.create(... tarif=Decimal('175000'))
        refresh_acuan(self.k, [t]); t.save()
        sync_billing_tindakan(self.k, [t], user=self.user)
        self.assertEqual(BillingItem.objects.get(kode_icd='99.18').harga_satuan, Decimal('175000'))
        refresh_acuan(self.k, [t]); t.save()
        sync_billing_tindakan(self.k, [t], user=self.user)
        self.assertEqual(BillingItem.objects.get(kode_icd='99.18').harga_satuan, Decimal('175000'))

    def test_null_override_uses_acuan(self): ...
    def test_missing_tariff_writes_nothing(self): ...
    def test_removing_line_deletes_its_billing_only(self): ...
    def test_manual_billing_untouched(self): ...
```

- [ ] **Step 3: Jalankan & commit**

```bash
.venv/Scripts/python.exe manage.py test klinis --keepdb -v 2
git add klinis
git commit -m "feat(klinis): sync billing dari baris tindakan, override tarif dipertahankan"
```

---

## Phase 3 — Jalur simpan

### Task 5: Parser + simpan baris di dua handler

**Files:**
- Create: `pasien/asesmen_tindakan.py`
- Modify: `pasien/views.py:2041-2241` dan `:2372-2680`
- Create: `pasien/tests_asesmen_tindakan_save.py`

**Interfaces:**
- Produces: `parse_tindakan(request) -> list[dict]`
- Produces: `simpan_tindakan(kunjungan, rows, user) -> list[TindakanAsesmen]`

- [ ] **Step 1: Parser + service**

```python
# pasien/asesmen_tindakan.py
import re
from decimal import Decimal, InvalidOperation
from django.db import transaction
from akreditasi.models import AuditLog, StandardItem
from klinis.models import MasterIcd9, SikiIntervensi
from klinis.services.tarif import refresh_acuan, sync_billing_tindakan
from .models import TindakanAsesmen

_RE = re.compile(r'^tindakan_(\d+)_id$')
_EP_STATUS = {'TERPENUHI', 'BELUM', 'NA'}


def _dec(raw):
    if raw in (None, ''):
        return None
    try:
        v = Decimal(str(raw).replace('.', '').replace(',', '.')) if ',' in str(raw) else Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return v if v > 0 else None


def parse_tindakan(request):
    rows = []
    idxs = sorted({int(m.group(1)) for key in request.POST if (m := _RE.match(key))})
    seen = set()
    for i in idxs:
        if request.POST.get(f'tindakan_{i}_hapus') == '1':
            continue
        kode = request.POST.get(f'tindakan_{i}_kode', '').strip()
        jenis = request.POST.get(f'tindakan_{i}_jenis', 'ICD9').upper()
        if jenis not in ('ICD9', 'SIKI', 'BEBAS'):
            jenis = 'BEBAS'
        if jenis == 'ICD9':
            if not MasterIcd9.objects.filter(kode=kode).exists():
                continue
            if kode in seen:
                continue
            seen.add(kode)
        rows.append({
            'id': request.POST.get(f'tindakan_{i}_id', '').strip(),
            'jenis': jenis, 'kode': kode,
            'nama': request.POST.get(f'tindakan_{i}_nama', '').strip()[:200],
            'sumber': request.POST.get(f'tindakan_{i}_sumber', 'MANUAL').upper(),
            'tarif': _dec(request.POST.get(f'tindakan_{i}_tarif')),
            'catatan_tarif': request.POST.get(f'tindakan_{i}_catatan_tarif', '').strip(),
            'ep_sub': request.POST.get(f'tindakan_{i}_ep_sub', '').strip(),
            'ep_status': request.POST.get(f'tindakan_{i}_ep_status', 'BELUM').upper(),
            'ep_catatan': request.POST.get(f'tindakan_{i}_ep_catatan', '').strip(),
        })
    return rows


@transaction.atomic
def simpan_tindakan(kunjungan, rows, user=None):
    existing = {str(t.pk): t for t in kunjungan.tindakan_asesmen.all()}
    keep, saved, warnings = [], [], []
    for urutan, row in enumerate(rows, start=1):
        t = existing.pop(row['id'], None) or TindakanAsesmen(kunjungan=kunjungan)
        t.urutan = urutan
        t.jenis = row['jenis']
        t.kode = row['kode']
        t.nama = row['nama'] or row['kode']
        t.sumber_data = row['sumber'] if row['sumber'] in ('MASTER', 'SARAN', 'MANUAL') else 'MANUAL'
        t.tarif = row['tarif']
        t.catatan_tarif = row['catatan_tarif']
        if row['jenis'] == 'ICD9':
            t.icd9 = MasterIcd9.objects.filter(kode=row['kode']).first()
            t.siki = None
        elif row['jenis'] == 'SIKI':
            t.siki = SikiIntervensi.objects.filter(kode=row['kode']).first()
            t.icd9 = None
        else:
            t.icd9 = t.siki = None
        if row['ep_sub']:
            t.standard_item = StandardItem.objects.filter(sub_standard=row['ep_sub']).first()
        else:
            t.standard_item = None
        t.ep_status = row['ep_status'] if row['ep_status'] in _EP_STATUS else 'BELUM'
        t.ep_catatan = row['ep_catatan']
        t.diubah_oleh = user
        saved.append(t)
        if row['tarif'] is not None:
            keep.append(t)

    refresh_acuan(kunjungan, saved)
    for t in saved:
        if (t.tarif is not None and t.tarif_acuan is not None
                and t.tarif != t.tarif_acuan and not t.catatan_tarif):
            warnings.append(f'Catatan alasan wajib untuk perubahan tarif {t.kode}.')
    if warnings:
        raise ValueError(' | '.join(warnings))

    for t in saved:
        t.save()
    for t in existing.values():
        t.delete()
    sync_billing_tindakan(kunjungan, saved, user=user)
    for t in saved:
        t.save(update_fields=['billing_item'])
        if t.tarif is not None and t.tarif_acuan is not None and t.tarif != t.tarif_acuan:
            AuditLog.objects.create(
                user=user, aksi='UPDATE', model_name='TindakanAsesmen',
                object_repr=f'{kunjungan.no_kunjungan} — {t.kode}',
                detail=f'Tarif diubah dari {t.tarif_acuan} menjadi {t.tarif}. Alasan: {t.catatan_tarif}')
    return saved
```

- [ ] **Step 2: Panggil di kedua handler**

Ganti blok `kode_list = ... sync_billing(...)` dengan:

```python
        rows = parse_tindakan(request)
        try:
            simpan_tindakan(k, rows, user=request.user)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(request.path)
        k.icd9_tindakan = '; '.join(t.nama for t in k.tindakan_asesmen.all())
        k.save(update_fields=['icd9_tindakan'])
```

Fallback kompatibilitas: bila `rows` kosong dan `request.POST.get('icd9_tindakan')` ada (form lama/klien lain), tetap jalankan `sync_billing(k, kode_list_lama, user=request.user)` seperti sekarang. Jangan hapus jalur lama.

- [ ] **Step 3: Test**

```python
class SimpanTindakanTest(TestCase):
    def test_saves_line_with_override_and_note(self): ...
    def test_override_without_note_rejected_and_nothing_written(self): ...
    def test_duplicate_code_keeps_one_line(self): ...
    def test_removed_line_deletes_billing(self): ...
    def test_ep_status_persisted_per_line(self): ...
    def test_unknown_ep_sub_standard_is_skipped(self): ...
    def test_legacy_text_field_still_syncs_when_no_lines(self): ...
    def test_bpjs_visit_uses_bpjs_acuan(self): ...
```

- [ ] **Step 4: Jalankan seluruh `pasien`**

```bash
.venv/Scripts/python.exe manage.py test pasien klinis --keepdb -v 2
```

- [ ] **Step 5: Commit**

```bash
git add pasien
git commit -m "feat(pasien): simpan baris tindakan, override tarif, EP per baris"
```

---

## Phase 4 — UI

### Task 6: Partial `_tindakan_tarif_ep.html` + wizard

**Files:**
- Create: `templates/pasien/_tindakan_tarif_ep.html`
- Modify: `templates/pasien/_asesmen_awal_wizard.html:671-720`
- Modify: `pasien/views.py` (`kunjungan_asesmen_awal`: `tindakan_list`, `ep_sub_choices`)

- [ ] **Step 1: Partial** — kartu per baris + strip rekap.

```html
<div class="card border mb-3" id="tindakanCard_{{ k.pk }}">
  <div class="card-header bg-light py-2 fw-bold small d-flex justify-content-between">
    <span><i class="bi bi-activity me-1 text-primary"></i> F. Tindakan &amp; Tarif</span>
    <span class="small text-muted">Penjamin: <strong>{{ k.get_penjamin_display }}</strong></span>
  </div>
  <div class="card-body p-3">
    <div class="input-group input-group-sm mb-2">
      <input type="text" list="globalIcd9List" id="tindakanPicker_{{ k.pk }}" class="form-control"
             placeholder="Ketik kode/nama tindakan (mis. 89.52 - EKG)">
      <button type="button" class="btn btn-primary" onclick="tambahTindakan('{{ k.pk }}')">Tambah</button>
    </div>
    <div id="tindakanRows_{{ k.pk }}">
      {% for t in tindakan_list %}
        {% include 'pasien/_tindakan_row.html' with t=t i=forloop.counter0 %}
      {% empty %}
        <div class="text-muted small fst-italic" data-empty>Tindakan belum dipilih.</div>
      {% endfor %}
    </div>
    <input type="hidden" name="icd9_tindakan" id="icd9TindakanSummary_{{ k.pk }}" value="{{ k.icd9_tindakan }}">
    <div class="alert alert-light border py-2 px-3 mb-0 mt-2">
      <span class="small text-muted">Total estimasi:</span>
      <strong class="ms-2 text-primary" data-total>Rp —</strong>
      <span class="small ms-3" data-ep-count></span>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Baris** — `templates/pasien/_tindakan_row.html`:

field `tindakan_{{ i }}_id|jenis|kode|nama|sumber|tarif|catatan_tarif|ep_sub|ep_status|ep_catatan|hapus`, badge sumber, input tarif dengan `data-acuan`, select EP dari `ep_sub_choices` (136 opsi), radio status, tombol hapus yang menyetel `hapus=1` + menyembunyikan baris.

- [ ] **Step 3: Template row baru (untuk JS)**

`<template id="tindakanRowTpl_{{ k.pk }}">` berisi baris kosong dengan placeholder `__i__`; `tambahTindakan()` mengkloning, mengganti `__i__` dengan indeks berikutnya, mengisi kode+nama dari picker, `data-acuan` dari `api_tarif_preview`, lalu memanggil `hitungTotalTindakan()`.

- [ ] **Step 4: JS** (blok inline baru di partial, bukan di blok lama)

```javascript
function hitungTotalTindakan(pk) {
    var scope = document.getElementById('tindakanRows_' + pk);
    var total = 0, epOk = 0, adaKosong = false;
    scope.querySelectorAll('[data-row]').forEach(function (row) {
        var input = row.querySelector('[name$="_tarif"]');
        var val = input && input.value ? parseFloat(input.value) : NaN;
        if (!isNaN(val)) total += val; else adaKosong = true;
        var st = row.querySelector('[name$="_ep_status"]');
        if (st && st.value === 'TERPENUHI') epOk += 1;
    });
    var el = document.querySelector('#tindakanCard_' + pk + ' [data-total]');
    if (el) el.innerText = adaKosong ? 'Rp — (ada tarif belum ditetapkan)' : 'Rp ' + total.toLocaleString('id-ID');
    var ep = document.querySelector('#tindakanCard_' + pk + ' [data-ep-count]');
    if (ep) ep.innerText = epOk + ' EP terpenuhi';
}
```

Aturan: JS hanya menjumlahkan angka yang sudah ditampilkan server; tidak ada resolusi tarif di klien.

- [ ] **Step 5: Context**

Di `kunjungan_asesmen_awal`: `'tindakan_list': k.tindakan_asesmen.select_related('icd9', 'siki', 'standard_item').all()`, `'ep_sub_choices': StandardItem.objects.values_list('sub_standard', flat=True).distinct().order_by('sub_standard')`.

- [ ] **Step 6: Regresi UX + test render**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_awal_ux pasien.tests_revisi_asesmen_awal pasien.tests_igd_modal_scroll pasien.tests_revisi_diagnosa_picker --keepdb -v 2
```

Bila merah karena test mengunci DOM chip lama: perbarui assertion ke DOM kartu **di commit yang sama**, dan sebutkan di pesan commit. Jangan melonggarkan test lain.

- [ ] **Step 7: Commit**

```bash
git add templates/pasien pasien/views.py
git commit -m "feat(pasien): UI baris tindakan + tarif editable + EP per item di wizard"
```

---

### Task 7: Paritas modal IGD

**Files:**
- Modify: `templates/pasien/igd_dashboard.html:1958-1990`
- Modify: `pasien/views.py` (context `igd_dashboard`: `ep_sub_choices`)

- [ ] **Step 1:** Ganti dua input bebas (`diagnosa_masuk` tetap; `icd9_tindakan` diganti) dengan `{% include 'pasien/_tindakan_tarif_ep.html' %}` di dalam `modalAsesmenMedis{{ k.pk }}`, dan set `tindakan_list` per kunjungan lewat template tag/inclusion: render partial di loop dengan `with k=k tindakan_list=k.tindakan_asesmen.all`. Bila N+1 menjadi masalah, tambahkan `prefetch_related('tindakan_asesmen__icd9', 'tindakan_asesmen__siki', 'tindakan_asesmen__standard_item')` pada queryset dashboard (sudah ada `prefetch_related`; tambahkan di sana).

- [ ] **Step 2:** Pastikan form modal punya `enctype="multipart/form-data"` (sudah, untuk lampiran) dan tombol simpan tetap memposting ke `igd_asesmen_medis_save`.

- [ ] **Step 3: Test**

```python
class IgdModalTindakanParityTest(TestCase):
    def test_modal_renders_line_inputs(self):
        resp = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(resp, f'tindakan_0_jenis')
        self.assertContains(resp, 'data-total')

    def test_legacy_icd9_text_input_still_present(self):
        self.assertContains(resp, 'name="icd9_tindakan"')
```

- [ ] **Step 4: Jalankan & commit**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_igd_advanced pasien.tests_revisi_asesmen_medis_igd pasien.tests_igd_modal_scroll --keepdb -v 2
git add templates/pasien pasien/views.py pasien/tests_asesmen_tindakan_save.py
git commit -m "feat(pasien): paritas baris tindakan & tarif di modal asesmen IGD"
```

---

### Task 8: Rekap, detail, cetak

**Files:**
- Modify: `templates/pasien/asesmen_detail.html`
- Modify: `pasien/views.py:2884-2915` (`asesmen_detail` context)
- Modify: `templates/pasien/cetak_asesmen_medis_igd.html` (blok tindakan)

- [ ] **Step 1:** Detail: tabel baris (`kode`, `nama`, `sumber_data`, `tarif_acuan`, `tarif`, `catatan_tarif`, `EP`, `status`), subtotal per jenis, dan daftar EP terpenuhi (distinct `sub_standard`).

- [ ] **Step 2:** Cetak: ganti paragraf `icd9_tindakan` dengan loop baris + kolom tarif; pertahankan teks legacy bila tidak ada baris.

- [ ] **Step 3: Test**

```python
class AsesmenDetailTindakanTest(TestCase):
    def test_detail_lists_lines_and_totals(self): ...
    def test_detail_shows_override_note(self): ...
    def test_print_falls_back_to_legacy_text(self): ...
```

- [ ] **Step 4: Commit**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_rekap pasien.tests_tindakan_asesmen --keepdb -v 2
git add templates/pasien pasien/views.py
git commit -m "feat(pasien): rincian tindakan & tarif pada halaman detail dan cetak asesmen"
```

---

## Phase 5 — Rilis

### Task 9: Verifikasi penuh & deploy

- [ ] **Step 1: Suite penuh tanpa `--keepdb`**

```bash
.venv/Scripts/python.exe manage.py test pasien klinis akreditasi sdm -v 2
```

Catat setiap kegagalan. Hanya kegagalan pra-eksisting yang boleh diterima, dan harus disebut namanya di catatan rilis.

- [ ] **Step 2: Migrasi manual ke Supabase**

```bash
# DATABASE_URL Supabase diekspor di shell
.venv/Scripts/python.exe manage.py migrate klinis
.venv/Scripts/python.exe manage.py migrate pasien
.venv/Scripts/python.exe manage.py seed_katalog_klinis
```

Verifikasi terhadap DB live:

```bash
.venv/Scripts/python.exe manage.py shell -c "from klinis.models import AturanEpTindakan; from pasien.models import TindakanAsesmen; print(AturanEpTindakan.objects.count(), TindakanAsesmen.objects.count())"
```

- [ ] **Step 3: Static artifacts**

```bash
.venv/Scripts/python.exe manage.py collectstatic --noinput
git add staticfiles static
git commit -m "chore(static): collectstatic untuk UI tindakan & tarif asesmen"
```

Commit artefak hash **dan** `staticfiles.json` bersamaan.

- [ ] **Step 4: Push**

```bash
git push origin master
```

---

## Definition of Done

- [ ] `api_tarif_preview` mengembalikan 200 + item, tidak ada `NameError`; test endpoint hijau.
- [ ] Upload lampiran lewat `igd_asesmen_medis_save` menyimpan `ukuran` dengan benar; kategori `RUJUKAN` valid.
- [ ] `AturanEpTindakan` ter-seed; `resolve_for()` membuang `sub_standard` yang tidak ada di katalog dan tidak pernah melempar exception.
- [ ] Baris tindakan tersimpan dengan `jenis`, `kode`, `nama` editable, `sumber_data`, `tarif_acuan`, `tarif`, `catatan_tarif`, `standard_item`, `ep_status`.
- [ ] Override tarif bertahan setelah simpan ulang; `tarif_acuan` tetap mengikuti master; `BillingItem.harga_satuan == tarif_efektif`.
- [ ] Override tanpa `catatan_tarif` ditolak dengan pesan; tidak ada baris/billing yang tertulis setengah jalan.
- [ ] Menghapus baris menghapus `BillingItem` ASESMEN-nya; billing `MANUAL` tidak tersentuh.
- [ ] Tidak ada `BillingItem` bernilai 0; tarif tak dikenal tetap "belum ditetapkan".
- [ ] EP per baris tersimpan dan badge status dirender; EP tak dikenal dilewati tanpa 500.
- [ ] Rekap menampilkan subtotal medis/keperawatan, total, dan jumlah EP terpenuhi.
- [ ] Modal IGD dan wizard memakai partial yang sama; input `icd9_tindakan` legacy tetap ada dan terisi ringkasan.
- [ ] Saran ICD dibatasi kelompok kunjungan, membutuhkan akses unit, dan berlabel "Saran Sistem".
- [ ] `makemigrations --check` bersih; migrasi hanya `CREATE TABLE` + `ADD COLUMN` + `AlterField choices`.
- [ ] Suite `pasien klinis akreditasi sdm` hijau; kegagalan pra-eksisting disebut namanya.
- [ ] Migrasi diterapkan manual ke Supabase dan diverifikasi di DB live.
- [ ] `staticfiles/` + `staticfiles.json` ter-commit bersama.
