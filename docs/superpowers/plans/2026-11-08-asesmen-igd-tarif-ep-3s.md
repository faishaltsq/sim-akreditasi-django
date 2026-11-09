# Plan — Asesmen Awal IGD: Master ICD/Tarif, Korelasi EP, dan Katalog 3S

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the IGD initial assessment into a reimbursable, auditable record — ICD-10/ICD-9 selection that carries a verified tariff (Umum/BPJS), an accreditation EP correlation per assessment, an auto-derived SDKI→SLKI→SIKI chain, document attachments, and a recap table with view/edit/reset actions.

**Architecture:**
1. **New `klinis` app** — reference data only, never patient data: `KelompokLayanan`, `MasterIcd10`, `MasterIcd9`, `KasusTersering`, `KasusTindakan`, `SdkiDiagnosis`, `SlkiLuaran`, `SikiIntervensi`, `Pemetaan3S`, `AturanEpAsesmen`.
2. **Tariff lives on `KasusTindakan`** (kasus × ICD-9), not on `MasterIcd9` — the source document prices the same procedure differently per ward (`99.18` = 75k/100k/150k).
3. **Money never duplicates** — `klinis.services.tarif` writes idempotent `BillingItem(sumber='ASESMEN')`; the form total is a derived `SUM(subtotal)`.
4. **EP correlation** via `pasien.KorelasiEpAsesmen` → `akreditasi.StandardItem` (read-only FK), rules seeded in `AturanEpAsesmen`.
5. **Attachments** via `pasien.LampiranAsesmen` with server-side validation and an access-controlled download view.
6. **Recap table** with a route `/asesmen-igd/` — view / edit / reset (reset = clear assessment fields, never cascade-delete the visit).

**Tech Stack:** Django 5, Bootstrap 5.3.3, PostgreSQL (Supabase prod) / SQLite (dev), `decimal`, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-08-asesmen-igd-master-tarif-ep-3s.md`

---

## Global Constraints

- **Plans must always be written in English** (standing memory rule). User-facing strings, model verbose names, and UI labels stay **Bahasa Indonesia**.
- **Additive migrations only.** No field on an existing model may change type, be renamed, or be dropped. New fields are nullable or have a default.
- **Migrations do not run automatically on deploy.** Every task that adds a migration ends with the explicit Supabase step in DoD.
- **Never invent clinical data.** Where the source document is truncated or missing a value, store verbatim and set `perlu_verifikasi=True`. Never render a missing tariff as `Rp 0`.
- **`akreditasi` and `sdm` are read-only in this plan.** Only read `StandardItem`. Do not touch `KatalogTindakan`.
- **No `pasien` imports inside `klinis.models`.** Choices are duplicated locally to keep the dependency arrow one-way.
- **Gate every phase** with `.venv/Scripts/python.exe manage.py test pasien akreditasi klinis --keepdb`. The full suite seeds 110 hospital units on a fresh DB (~70–90s) — `--keepdb` keeps targeted runs under 2s.
- **Python is `.venv/Scripts/python.exe`** — bare `python` is not on the project's PYTHONPATH.
- Run **`makemigrations --check`** at the end of every migration-adding task; it must report "No changes detected".

---

## Phase 1 — Reference data foundation

### Task 1: `klinis` app skeleton and master models

**Files:**
- Create: `klinis/__init__.py`, `klinis/apps.py`, `klinis/models.py`, `klinis/admin.py`, `klinis/services/__init__.py`, `klinis/migrations/__init__.py`
- Modify: `config/settings.py:145-158` (add `'klinis'` to `INSTALLED_APPS`)

**Interfaces:**
- Produces: `klinis.models.{KelompokLayanan, MasterIcd10, MasterIcd9, KasusTersering, KasusTindakan, SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S, AturanEpAsesmen}`

- [ ] **Step 1: Create the app package**

```bash
cd /c/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django
.venv/Scripts/python.exe manage.py startapp klinis
```

Then delete the generated `klinis/models.py`, `klinis/tests.py`, `klinis/views.py` stubs and replace `models.py` with the real content in Step 2. Keep `apps.py` but set:

```python
class KlinisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'klinis'
    verbose_name = 'Katalog Klinis (ICD, Tarif, 3S)'
```

- [ ] **Step 2: Write `klinis/models.py`**

Implement exactly the ten models from spec §5.2. Local choices — do **not** import from `pasien`:

```python
TRIASE_CHOICES = [
    ('MERAH', 'Merah — Prioritas I (Kritis)'),
    ('KUNING', 'Kuning — Prioritas II (Urgent)'),
    ('HIJAU', 'Hijau — Prioritas III (Non-Urgent)'),
    ('HITAM', 'Hitam — Prioritas IV (Expectant)'),
]
RISIKO_CHOICES = [
    ('LOW', 'LOW'), ('MEDIUM', 'MEDIUM'), ('HIGH', 'HIGH'), ('CRITICAL', 'CRITICAL'),
]
```

`KasusTindakan.tarif_umum` / `tarif_bpjs` are `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`. `KasusTersering.kewenangan` is `CharField(max_length=10, blank=True)` to fit `'Sp.BTKV'` and `'Sp.PD-KEMD'`.

- [ ] **Step 3: Register the app**

`config/settings.py`, line ~157, after `'pasien',`:

```python
    'klinis',
```

- [ ] **Step 4: Generate and inspect the migration**

```bash
.venv/Scripts/python.exe manage.py makemigrations klinis
```

Expected: `klinis/migrations/0001_initial.py` created with all ten models. Read it and confirm no `ALTER TABLE` against any existing table — this migration must only `CREATE TABLE`.

- [ ] **Step 5: Apply locally and verify**

```bash
.venv/Scripts/python.exe manage.py migrate klinis
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

Expected: migrate OK; `--check` prints "No changes detected".

- [ ] **Step 6: Register admin (read-mostly)**

`klinis/admin.py` — register all models with `list_display` on the natural keys (`kode`, `nama`), `search_fields` on `kode`/`nama`, and `list_filter` on `kelompok` for `KasusTersering`. Mark `KasusTindakan` with `raw_id_fields = ('kasus', 'icd9')` to avoid a 400-row select.

---

### Task 2: Seed the clinical catalog from the master document

**Files:**
- Create: `klinis/data/__init__.py`, `klinis/data/master_tarif.py`, `klinis/management/__init__.py`, `klinis/management/commands/__init__.py`, `klinis/management/commands/seed_katalog_klinis.py`
- Create: `klinis/tests/__init__.py`, `klinis/tests/test_seed_katalog.py`

**Interfaces:**
- Produces: `klinis.data.master_tarif.KELOMPOK` (14 entries), `KASUS` (215 entries: 210 ICD-10 + 5 SDKI-only), `SDKI`, `SLKI`, `SIKI`, `PEMETAAN_3S`, `ATURAN_EP`
- Produces: `seed_katalog_klinis` management command, idempotent

- [ ] **Step 1: Write the data module shape first**

`klinis/data/master_tarif.py` — one list of dicts per source table. Shape:

```python
KELOMPOK = [
    # (kode, nama, unit_kerja_code, urutan)
    ('IGD',      'Instalasi Gawat Darurat',            'IGD',        1),
    ('JANTUNG',  'Rawat Inap Jantung & Kardiovaskular', 'ICCU',      2),
    ('PARU',     'Rawat Inap Paru & Respirologi',       'BANGSAL-DEWASA', 3),
    ('ENDOKRIN', 'Rawat Inap Endokrin & Ginjal',        'BANGSAL-DEWASA', 4),
    ('PD',       'Rawat Inap Penyakit Dalam',           'BANGSAL-DEWASA', 5),
    ('MATA',     'Perawatan & Bedah Mata',              'POLI-MATA',  6),
    ('MATA_PASCA','Perawatan Pascabedah Mata',          'POLI-MATA',  7),
    ('ORTO',     'Rawat Inap Orthopedi & Traumatologi', 'POLI-ORTHO', 8),
    ('ORTO_PASCA','Perawatan Pascabedah Orthopedi',     'POLI-ORTHO', 9),
    ('NIFAS',    'Rawat Inap Nifas',                    'RUANG-NIFAS',10),
    ('VK',       'Kamar Bersalin (VK)',                 'RUANG-BERSALIN-VK', 11),
    ('IBS',      'Kamar Operasi (IBS)',                 'IBS',       12),
    ('BEDAH',    'Rawat Inap Bedah Umum',               'BANGSAL-BEDAH', 13),
    ('ANAK',     'Rawat Inap Anak',                     'BANGSAL-ANAK',  14),
]
```

Note `MATA_PASCA` exists because the source has two Mata tables: one surgical (with tariffs) and one post-operative (no cost columns at all — spec §4 D4). Both map to `POLI-MATA`; `MATA_PASCA` rows carry `tanpa_tarif=True`.

Each `KASUS` entry:

```python
{
    'kelompok': 'IGD', 'urutan': 5,
    'icd10': ('I21.9', 'Infark Miokard Akut (STEMI / NSTEMI)'),
    'tindakan': [
        # (icd9_kode, icd9_nama, tarif_umum, tarif_bpjs, satuan)
        ('89.52', 'Elektrokardiogram 12 Lead', '150000', '120000', ''),
        ('99.10', 'Trombolitik / Alteplase',    '2500000', '2000000', ''),
        ('36.06', 'PCI Primer',                 '7500000', '6800000', ''),
    ],
    'tatalaksana': 'Protokol MONA, antiplatelet ganda ...',
    'kewenangan': 'Dokter Umum (Penanganan awal/MONA); Spesialis 1 (PCI)',
    'perlu_verifikasi': False,
    'catatan_sumber': '',
}
```

**Transcription rules, applied without exception:**
- Copy every nominal verbatim from the source extract. `Rp 500.000 / kantong` → `('500000', '400000', '/kantong')`.
- Truncated `tatalaksana` → copy the fragment as-is, append nothing, set `perlu_verifikasi=True`.
- `MATA_PASCA` rows → `tindakan` entries carry `None` for both tariffs.
- The five SDKI-only rows from the mis-titled first table (spec §4 D1) go under `kelompok='NIFAS'` with `'icd10': None`, `'sdki_kode'`, `'sdki_nama'`, `'tindakan': []`.
- `catatan_sumber` records the source heading so a reviewer can trace every row back.

- [ ] **Step 2: Write the 3S catalog and EP rules**

In the same module:

```python
SDKI = [('D.0077', 'Nyeri Akut'), ('D.0149', 'Risiko Perdarahan'), ...]   # superset of pasien.views.SDKI_CODES
SLKI = [('L.08066', 'Tingkat Nyeri'), ...]
SIKI = [('I.08238', 'Manajemen Nyeri'), ...]
PEMETAAN_3S = [('D.0077', 'L.08066', 'I.08238', 1), ...]
ATURAN_EP = [
    # (sub_standard, label, wajib, urutan)
    ('ARK 1', 'Skrining & Triage Pasien', True, 1),
    ('PAP 3', 'Pelayanan Pasien Risiko Tinggi & Gawat Darurat', True, 2),
    ('PAP 8', 'Peringatan Dini Klinis (EWS)', True, 3),
    ('SKP 1', 'Identifikasi Pasien dengan Benar', True, 4),
]
```

The 3S catalog must be a **superset** of `pasien/views.py:118-143` — every code already in use must exist in `SdkiDiagnosis`, or the migration of existing free-text values breaks. Add a test for this (Step 5).

- [ ] **Step 3: Write the seed command**

```python
class Command(BaseCommand):
    help = 'Seed katalog klinis (ICD-10/ICD-9/tarif/3S/EP) — idempoten.'

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. KelompokLayanan.update_or_create(kode=…)
        # 2. MasterIcd10.update_or_create(kode=…, defaults={nama, spesialisasi})
        # 3. MasterIcd9.update_or_create(kode=…, defaults={nama, invasif, requires_consent})
        # 4. KasusTersering.update_or_create(kelompok=…, urutan=…, defaults={…})
        # 5. KasusTindakan.update_or_create(kasus=…, icd9=…, urutan=…, defaults={…})
        # 6. SdkiDiagnosis/SlkiLuaran/SikiIntervensi/Pemetaan3S/AturanEpAsesmen
        #    — all update_or_create on their natural key
        # self.stdout.write(f'… {n_kasus} kasus, {n_tindakan} tindakan, {n_3s} pemetaan')
```

Never `create()` on a keyed row — re-running the command must not raise `IntegrityError`.

- [ ] **Step 4: Run the seed and read the console summary**

```bash
.venv/Scripts/python.exe manage.py seed_katalog_klinis
```

Expected: a count line. Record the numbers; they become the assertions in Step 5.

- [ ] **Step 5: Write the integrity tests**

`klinis/tests/test_seed_katalog.py`:

```python
class SeedIntegrityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_katalog_klinis', verbosity=0)

    def test_counts_match_data_module(self):
        self.assertEqual(KasusTersering.objects.count(), len(master_tarif.KASUS))
        self.assertEqual(KasusTindakan.objects.count(),
                         sum(len(k['tindakan']) for k in master_tarif.KASUS))

    def test_every_tindakan_has_icd9(self):
        self.assertFalse(KasusTindakan.objects.filter(icd9__isnull=True).exists())

    def test_no_negative_or_zero_tariff(self):
        bad = KasusTindakan.objects.filter(
            Q(tarif_umum__isnull=False, tarif_umum__lte=0)
            | Q(tarif_bpjs__isnull=False, tarif_bpjs__lte=0))
        self.assertFalse(bad.exists())

    def test_igd_tariff_ceiling(self):          # typo guard: 7.5jt vs 750rb
        for t in KasusTindakan.objects.filter(kasus__kelompok__kode='IGD'):
            self.assertLessEqual(t.tarif_umum or 0, Decimal('15000000'))

    def test_pascabedah_mata_has_no_tariff(self):
        qs = KasusTindakan.objects.filter(kasus__kelompok__kode='MATA_PASCA')
        self.assertTrue(qs.exists())
        self.assertFalse(qs.exclude(tarif_umum__isnull=True).exists())

    def test_seed_is_idempotent(self):
        before = (KasusTersering.objects.count(), KasusTindakan.objects.count())
        call_command('seed_katalog_klinis', verbosity=0)
        self.assertEqual(before, (KasusTersering.objects.count(), KasusTindakan.objects.count()))

    def test_truncated_rows_flagged(self):
        # every kasus whose tatalaksana came from a truncated source line
        for kode in ('PD', 'MATA', 'ORTO_PASCA', 'NIFAS', 'BEDAH', 'IGD'):
            last = KasusTersering.objects.get(kelompok__kode=kode, urutan=15)
            if last.tatalaksana and not last.tatalaksana.rstrip().endswith('.'):
                self.assertTrue(last.perlu_verifikasi, f'{kode}#15 not flagged')

    def test_sdki_catalog_superset_of_legacy(self):
        from pasien.views import SDKI_CODES
        codes = set(SdkiDiagnosis.objects.values_list('kode', flat=True))
        missing = {c for c, _ in SDKI_CODES} - codes
        self.assertFalse(missing, f'SKDKI codes missing from catalog: {missing}')

    def test_ep_rules_resolve_against_catalog(self):
        from akreditasi.models import StandardItem
        for rule in AturanEpAsesmen.objects.all():
            self.assertTrue(
                StandardItem.objects.filter(sub_standard=rule.sub_standard).exists(),
                f'{rule.sub_standard} not in accreditation catalog')
```

- [ ] **Step 6: Run**

```bash
.venv/Scripts/python.exe manage.py test klinis --keepdb -v 2
```

Expected: all green. If `test_truncated_rows_flagged` fails on a row that is genuinely complete, fix the flag in the data module — do not relax the test.

- [ ] **Step 7: Commit**

```bash
git add klinis config/settings.py
git commit -m "feat(klinis): katalog master ICD-10/ICD-9, tarif, 3S, dan aturan EP + seed"
```

---

## Phase 2 — Tariff service and assessment models

### Task 3: Tariff resolver and billing writer

**Files:**
- Create: `klinis/services/__init__.py` (empty), `klinis/services/tarif.py`
- Modify: `pasien/models.py:763-796` (`BillingItem` — add `sumber`)
- Create: `klinis/tests/test_tarif_service.py`

**Interfaces:**
- Produces: `klinis.services.tarif.resolve(kunjungan, icd9_kode) -> Decimal | None`
- Produces: `klinis.services.tarif.sync_billing(kunjungan, icd9_kodes, user=None) -> list[BillingItem]`
- Consumes: `KunjunganPasien.unit_kerja`, `KunjunganPasien.jenis_kunjungan`, `KunjunganPasien.penjamin`

- [ ] **Step 1: Write the failing test**

```python
class TarifResolveTest(TestCase):
    def test_bpjs_uses_bpjs_tariff(self): ...      # penjamin='BPJS' → tarif_bpjs
    def test_umum_uses_umum_tariff(self): ...      # penjamin='UMUM'  → tarif_umum
    def test_returns_none_when_not_found(self): ... # unknown code → None, not Decimal(0)
    def test_same_code_differs_per_kelompok(self): ... # 99.18 in IGD vs JANTUNG
```

For `test_same_code_differs_per_kelompok`, assert explicitly that resolving `'99.18'` under an IGD visit and under a JANTUNG visit returns two different numbers — this is the regression guard for spec §4 D6.

- [ ] **Step 2: Add `BillingItem.sumber`**

`pasien/models.py`, inside `BillingItem`:

```python
    SUMBER = [('MANUAL', 'Input Manual'), ('ASESMEN', 'Otomatis dari Asesmen')]
    sumber = models.CharField('Sumber', max_length=10, choices=SUMBER, default='MANUAL')
```

```bash
.venv/Scripts/python.exe manage.py makemigrations pasien --name billingitem_sumber
.venv/Scripts/python.exe manage.py migrate pasien
```

- [ ] **Step 3: Implement the resolver**

```python
def _kelompok_for(kunjungan):
    """Unit kerja eksplisit dulu; fallback ke kode jenis kunjungan. Tanpa heuristik nama."""
    KL = KelompokLayanan
    if kunjungan.unit_kerja_id:
        kl = KL.objects.filter(unit_kerja_id=kunjungan.unit_kerja_id).first()
        if kl:
            return kl
    return KL.objects.filter(kode=kunjungan.jenis_kunjungan.upper()).first()


def resolve(kunjungan, icd9_kode):
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return None
    tindakan = (KasusTindakan.objects
                .filter(kasus__kelompok=kelompok, icd9__kode=icd9_kode)
                .order_by('kasus__urutan', 'urutan')
                .first())
    if not tindakan:
        return None
    if kunjungan.penjamin == 'BPJS':
        return tindakan.tarif_bpjs          # may be None → UI shows "belum ditetapkan"
    return tindakan.tarif_umum
```

- [ ] **Step 4: Implement the billing sync (idempotent both ways)**

```python
def sync_billing(kunjungan, icd9_kodes, user=None):
    """Reconcile ASESMEN-sourced BillingItem rows with the current selection."""
    wanted = [k for k in icd9_kodes if k]
    keep = []
    for kode in wanted:
        nominal = resolve(kunjungan, kode)
        if nominal is None:
            continue                        # never write Rp 0
        icd9 = MasterIcd9.objects.filter(kode=kode).first()
        item, _ = BillingItem.objects.update_or_create(
            kunjungan=kunjungan, kategori='JASA_MEDIS', kode_icd=kode, sumber='ASESMEN',
            defaults={'nama_item': icd9.nama if icd9 else kode,
                      'harga_satuan': nominal, 'kuantitas': Decimal('1'),
                      'dicatat_oleh': user})
        keep.append(item.pk)
    BillingItem.objects.filter(kunjungan=kunjungan, sumber='ASESMEN').exclude(pk__in=keep).delete()
    return list(BillingItem.objects.filter(pk__in=keep))
```

Wrapped in `transaction.atomic` at the call site.

- [ ] **Step 5: Run**

```bash
.venv/Scripts/python.exe manage.py test klinis --keepdb -v 2
```

- [ ] **Step 6: Commit**

```bash
git add klinis pasien/models.py pasien/migrations
git commit -m "feat(klinis): resolver tarif per kelompok layanan + sinkronisasi BillingItem idempoten"
```

---

### Task 4: EP correlation, attachments, and new assessment fields

**Files:**
- Modify: `pasien/models.py` (three new fields on `KunjunganPasien`; two new models)
- Create: `pasien/migrations/00XX_asesmen_ep_lampiran.py` (generated)
- Modify: `pasien/admin.py`

**Interfaces:**
- Produces: `pasien.models.KorelasiEpAsesmen`, `pasien.models.LampiranAsesmen`
- Produces: `KunjunganPasien.skrining_jatuh_detail`, `.asesmen_catatan_waktu`, `.status_ep_ringkas` (property)

- [ ] **Step 1: Add the fields and models**

On `KunjunganPasien`, after `skrining_gizi_mst`:

```python
    skrining_jatuh_detail = models.JSONField('Detail Skrining Jatuh (Morse)', default=dict, blank=True)
```

after `petugas_handover_dokter_jam`:

```python
    asesmen_catatan_waktu = models.TextField('Catatan / Penyesuaian Waktu Pelayanan', blank=True)
```

Then the two models from spec §5.3 verbatim, plus this property on `KunjunganPasien`:

```python
    @property
    def status_ep_ringkas(self):
        rules = set(AturanEpAsesmen.objects.filter(wajib=True).values_list('sub_standard', flat=True))
        if not rules:
            return '-'
        rows = self.korelasi_ep.select_related('standard_item')
        terpenuhi = {r.standard_item.sub_standard for r in rows if r.status == 'TERPENUHI'}
        if rules <= terpenuhi:
            return 'TERPENUHI'
        return 'SEBAGIAN' if terpenuhi & rules else 'BELUM'
```

`AturanEpAsesmen` lives in `klinis`, so import it **inside** the property (`from klinis.models import AturanEpAsesmen`) — top-level import would create `pasien → klinis → (nothing back)`, which is acceptable, but the function-local import keeps `pasien.models` loadable if `klinis` is ever removed from `INSTALLED_APPS` during a partial deploy.

- [ ] **Step 2: Migrate and verify the migration is purely additive**

```bash
.venv/Scripts/python.exe manage.py makemigrations pasien --name asesmen_ep_lampiran
.venv/Scripts/python.exe manage.py sqlmigrate pasien <number> | grep -i "alter table.*drop\|alter table.*type"
```

Expected: **no output** from the grep. Two `CREATE TABLE`, one `ALTER TABLE ... ADD COLUMN` × 3, nothing else.

```bash
.venv/Scripts/python.exe manage.py migrate pasien
```

- [ ] **Step 3: Register in admin** with `KorelasiEpAsesmen` inline on a visit and `LampiranAsesmen` read-only (`has_add_permission = False`).

- [ ] **Step 4: Write the status test**

```python
class StatusEpTest(TestCase):
    def test_belum_when_no_rows(self): ...
    def test_sebagian_when_partial(self): ...
    def test_terpenuhi_when_all_mandatory(self): ...
    def test_na_does_not_count_as_terpenuhi(self): ...
```

- [ ] **Step 5: Run and commit**

```bash
.venv/Scripts/python.exe manage.py test pasien --keepdb -v 2
git add pasien
git commit -m "feat(pasien): korelasi EP asesmen, lampiran asesmen, field Morse & catatan waktu"
```

---

## Phase 3 — Save path wiring

### Task 5: Tariff + EP + attachments on the assessment save

**Files:**
- Modify: `pasien/views.py:1971` (`igd_asesmen_awal_save`), `pasien/views.py:2236` (`igd_asesmen_medis_save`)
- Modify: `pasien/urls.py` (attachment upload/download routes)
- Create: `pasien/tests_asesmen_tarif_ep.py`

**Interfaces:**
- Consumes: `klinis.services.tarif.sync_billing`, `AturanEpAsesmen`, `KorelasiEpAsesmen`, `LampiranAsesmen`
- Produces: view names `asesmen_lampiran_upload`, `asesmen_lampiran_download`, `asesmen_lampiran_hapus`

- [ ] **Step 1: Extend the save handlers**

In both handlers, after the existing `k.save()`:

```python
        # ── Tarif otomatis (ICD-9 → BillingItem, sumber='ASESMEN') ──
        kode_list = [c.strip().split(' - ')[0]
                     for c in request.POST.getlist('icd9_kode') if c.strip()]
        if not kode_list and request.POST.get('icd9_tindakan'):
            kode_list = [request.POST['icd9_tindakan'].strip().split(' - ')[0]]
        with transaction.atomic():
            sync_billing(k, kode_list, user=request.user)

        # ── Korelasi EP ──
        for rule in AturanEpAsesmen.objects.all():
            status = request.POST.get(f'ep_status_{rule.pk}')
            if status not in ('TERPENUHI', 'BELUM', 'NA'):
                continue
            KorelasiEpAsesmen.objects.update_or_create(
                kunjungan=k, standard_item=StandardItem.objects.filter(
                    sub_standard=rule.sub_standard).first(),
                defaults={'status': status,
                          'catatan': request.POST.get(f'ep_catatan_{rule.pk}', '').strip(),
                          'diverifikasi_oleh': request.user,
                          'diverifikasi_pada': timezone.now()})

        # ── Catatan waktu ──
        if 'asesmen_catatan_waktu' in request.POST:
            k.asesmen_catatan_waktu = request.POST['asesmen_catatan_waktu'].strip()
            k.save(update_fields=['asesmen_catatan_waktu'])
```

Guard the EP block: if `StandardItem.objects.filter(sub_standard=rule.sub_standard).first()` is `None`, `continue` and log a warning — this is the `PAP 2.1` case (spec §4 D8). Never let it raise.

- [ ] **Step 2: Attachment upload view**

```python
LAMPIRAN_EKSTENSI = {'.pdf', '.xls', '.xlsx', '.doc', '.docx'}
LAMPIRAN_MAKS_BYTE = 10 * 1024 * 1024

@login_required
@require_POST
def asesmen_lampiran_upload(request, pk):
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if not can_read_kunjungan(k, getattr(request.user, 'profile', None)):
        raise PermissionDenied(...)
    f = request.FILES.get('file')
    if not f:
        messages.error(request, 'Tidak ada berkas yang dipilih.'); return redirect(...)
    ext = Path(f.name).suffix.lower()
    if ext not in LAMPIRAN_EKSTENSI:
        messages.error(request, f'Format {ext} tidak diizinkan.'); return redirect(...)
    if f.size > LAMPIRAN_MAKS_BYTE:
        messages.error(request, 'Ukuran berkas melebihi 10 MB.'); return redirect(...)
    LampiranAsesmen.objects.create(
        kunjungan=k, jenis=request.POST.get('jenis', 'ASESMEN'),
        file=f, nama_asli=f.name, ukuran=f.size, diunggah_oleh=request.user)
    AuditLog.objects.create(...)
```

`safe_filename`-style sanitisation: `upload_to='asesmen/%Y/%m/'` plus Django's `get_valid_name`; store the original in `nama_asli` for display only.

- [ ] **Step 3: Download view — never expose the media URL**

```python
@login_required
def asesmen_lampiran_download(request, pk, lampiran_id):
    lap = get_object_or_404(LampiranAsesmen, pk=lampiran_id, kunjungan_id=pk)
    if not can_read_kunjungan(lap.kunjungan, getattr(request.user, 'profile', None)):
        raise PermissionDenied(...)
    resp = FileResponse(lap.file.open('rb'), as_attachment=True, filename=lap.nama_asli)
    resp['Content-Type'] = 'application/octet-stream'
    return resp
```

- [ ] **Step 4: URLs**

```python
    path('kunjungan/<int:pk>/asesmen/lampiran/upload/', views.asesmen_lampiran_upload, name='asesmen_lampiran_upload'),
    path('kunjungan/<int:pk>/asesmen/lampiran/<int:lampiran_id>/', views.asesmen_lampiran_download, name='asesmen_lampiran_download'),
    path('kunjungan/<int:pk>/asesmen/lampiran/<int:lampiran_id>/hapus/', views.asesmen_lampiran_hapus, name='asesmen_lampiran_hapus'),
```

- [ ] **Step 5: Tests** — one class per concern:

```python
class TarifOtomatisTest(TestCase):
    def test_saves_billingitem_for_selected_icd9(self): ...
    def test_bpjs_visit_uses_bpjs_tariff(self): ...
    def test_reselecting_same_code_does_not_duplicate(self): ...
    def test_removing_code_removes_billing_row(self): ...
    def test_unknown_code_writes_nothing(self): ...

class KorelasiEpSaveTest(TestCase):
    def test_saves_status_per_rule(self): ...
    def test_missing_standard_item_is_skipped_not_500(self): ...

class LampiranTest(TestCase):
    def test_rejects_wrong_extension(self): ...
    def test_rejects_oversize(self): ...
    def test_accepts_pdf(self): ...
    def test_download_requires_unit_access(self): ...   # 403 for other-unit user
```

- [ ] **Step 6: Run the whole `pasien` suite**

```bash
.venv/Scripts/python.exe manage.py test pasien klinis --keepdb -v 2
```

Expected: 0 failures. Any pre-existing baseline failure must be named explicitly before and after — do not let a new failure hide behind "some were already red".

- [ ] **Step 7: Commit**

```bash
git add pasien
git commit -m "feat(pasien): tarif otomatis, korelasi EP, dan lampiran pada simpan asesmen"
```

---

## Phase 4 — UI

### Task 6: Kalkulator Morse otomatis — tambah saja, tanpa refactor

**Prinsip:** JS yang sudah jalan (`updateSkorNyeri`, `hitungMst`, `setNormalAsesmen`, `setNormalDetail`, `updateSkorNyeriDetail`, `hitungMstDetail`) **tidak disentuh, tidak dipindah, tidak digabung**. Task ini hanya menambahkan satu fungsi baru ke pola inline yang sudah ada.

**Files:**
- Modify: `templates/pasien/_asesmen_awal_wizard.html` (6 item Morse + blok `<script>` baru di akhir blok Tab Diagnosa & Risiko)
- Modify: `templates/pasien/igd_dashboard.html` (6 item Morse di dalam `modalAsesmenAwal` + fungsi `hitungMorse` di blok `<script>` yang sudah ada)

**Interfaces:**
- Produces: `hitungMorse(modalEl)` — dipanggil dari `change` tiap select Morse dan dari `shown.bs.modal`
- Consumes: field baru `KunjunganPasien.skrining_jatuh_detail` (Task 4)

- [ ] **Step 1: Tambahkan 6 item Morse di samping field skor yang sudah ada**

Field `skrining_jatuh_skor` dan `skrining_jatuh_grade` **tetap dipertahankan** (jangan diganti) karena sudah dipakai tabel IGD, tooltip, dan print. Tambahkan 6 select di atasnya:

```html
<div class="row g-1" data-morse-group>
    <div class="col-6">
        <label class="form-label small mb-0">Riwayat jatuh</label>
        <select name="jatuh_riwayat" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Tidak pernah</option><option value="1">Ya (dalam 3 bulan)</option>
        </select>
    </div>
    <div class="col-6">
        <label class="form-label small mb-0">Diagnosis sekunder</label>
        <select name="jatuh_diagnosis" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Tidak ada</option><option value="1">Ya (&ge;2 diagnosis)</option>
        </select>
    </div>
    <div class="col-6">
        <label class="form-label small mb-0">Alat bantu jalan</label>
        <select name="jatuh_alat" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Tidak ada / tirah baring / dibantu perawat</option>
            <option value="1">Kruk / tongkat / walker</option>
            <option value="2">Berpegangan pada furnitur</option>
        </select>
    </div>
    <div class="col-6">
        <label class="form-label small mb-0">Terpasang infus</label>
        <select name="jatuh_infus" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Tidak</option><option value="1">Ya</option>
        </select>
    </div>
    <div class="col-6">
        <label class="form-label small mb-0">Cara berjalan</label>
        <select name="jatuh_jalan" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Normal / tirah baring / kursi roda</option>
            <option value="1">Lemah</option><option value="2">Gangguan / tidak mampu</option>
        </select>
    </div>
    <div class="col-6">
        <label class="form-label small mb-0">Status mental</label>
        <select name="jatuh_mental" class="form-select form-select-sm" onchange="hitungMorse(this.closest('.modal, form'))">
            <option value="0">Oriented (sadar akan kemampuan diri)</option>
            <option value="1">Overestimasi / lupa keterbatasan</option>
        </select>
    </div>
</div>
<div class="mt-1">
    <span class="badge bg-success" data-morse-result>0 — Risiko Rendah</span>
    <span class="small text-muted ms-1">Skor &amp; grade terisi otomatis</span>
</div>
```

Label dan bobot mengikuti Morse Fall Scale baku: riwayat jatuh 25, diagnosis sekunder 15, alat bantu 0/15/30, infus 20, cara berjalan 0/10/20, status mental 15.

- [ ] **Step 2: Tambahkan fungsi `hitungMorse`**

Sisipkan ke dalam blok `<script>` yang **sudah ada** di masing-masing template (jangan buat blok baru di `igd_dashboard.html`; untuk wizard tambahkan satu blok `<script>` kecil di akhir partial):

```javascript
function hitungMorse(scope) {
    var bobot = {
        jatuh_riwayat:  [0, 25],
        jatuh_diagnosis:[0, 15],
        jatuh_alat:     [0, 15, 30],
        jatuh_infus:    [0, 20],
        jatuh_jalan:    [0, 10, 20],
        jatuh_mental:   [0, 15],
    };
    var total = 0;
    Object.keys(bobot).forEach(function (name) {
        var el = scope.querySelector('[name="' + name + '"]');
        if (!el || el.value === '') return;
        var idx = parseInt(el.value, 10);
        if (!isNaN(idx) && bobot[name][idx] !== undefined) total += bobot[name][idx];
    });
    var skor = scope.querySelector('[name="skrining_jatuh_skor"]');
    var grade = scope.querySelector('[name="skrining_jatuh_grade"]');
    if (skor) skor.value = total;
    if (grade) grade.value = total >= 45 ? 'TINGGI' : (total >= 25 ? 'SEDANG' : 'RENDAH');
    var badge = scope.querySelector('[data-morse-result]');
    if (badge) {
        badge.className = 'badge ' + (total >= 45 ? 'bg-danger' : total >= 25 ? 'bg-warning text-dark' : 'bg-success');
        badge.innerText = total + ' — ' + (total >= 45 ? 'Risiko Tinggi' : total >= 25 ? 'Risiko Sedang' : 'Risiko Rendah');
    }
}
window.hitungMorse = hitungMorse;
```

- [ ] **Step 3: Tambahkan `setNormalAsesmen` tetap seperti sekarang, plus reset Morse**

Di `igd_dashboard.html`, di dalam `setNormalAsesmen(pk)` yang sudah ada, **tambahkan** satu baris di akhir — jangan ubah baris lain:

```javascript
        var m = document.getElementById('modalAsesmenAwal' + pk);
        if (m) { m.querySelectorAll('[data-morse-group] select').forEach(function (s) { s.value = '0'; }); hitungMorse(m); }
```

- [ ] **Step 4: Simpan detail Morse**

Di `igd_asesmen_awal_save` dan `igd_asesmen_medis_save`, tambahkan setelah blok skrining risiko yang sudah ada:

```python
        detail = {}
        for key in ('jatuh_riwayat', 'jatuh_diagnosis', 'jatuh_alat',
                    'jatuh_infus', 'jatuh_jalan', 'jatuh_mental'):
            val = request.POST.get(key, '').strip()
            if val.isdigit():
                detail[key] = int(val)
        if detail:
            k.skrining_jatuh_detail = detail
```

Jangan menghapus penanganan `skrining_jatuh_skor`/`grade` yang sudah ada — nilainya tetap diterima dari hidden field yang diisi `hitungMorse`.

- [ ] **Step 5: Regresi tiga kelas test UX yang sudah hijau**

```bash
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_awal_ux pasien.tests_revisi_asesmen_awal pasien.tests_igd_modal_scroll --keepdb -v 2
```

Expected: hijau **tanpa perubahan test**. Bila ada yang merah, yang salah adalah Task 6, bukan test-nya — perbaiki kode, jangan test.

- [ ] **Step 6: Test baru untuk Morse**

```python
class MorseAutoScoreTest(TestCase):
    def test_all_zero_saves_low_risk(self): ...
    def test_max_items_saves_high_risk(self): ...      # 25+15+30+20+20+15 = 125 → TINGGI
    def test_threshold_25_is_sedang(self): ...
    def test_detail_json_persisted(self): ...
```

- [ ] **Step 7: Commit**

```bash
git add templates/pasien pasien/views.py pasien/tests_asesmen_morse.py
git commit -m "feat(pasien): kalkulator skor Morse otomatis pada asesmen awal IGD"
```

---

### Task 7: Tab Diagnosa & Tarif + kartu EP + lampiran

**Files:**
- Modify: `templates/pasien/_asesmen_awal_wizard.html:568+` (Tab Diagnosa & Risiko)
- Modify: `templates/pasien/igd_dashboard.html:1902-1920` (modal diagnosis section)
- Modify: `pasien/views.py:324` (`kunjungan_asesmen_awal` context) and the IGD dashboard context — add `ep_pilihan` (semua sub_standard katalog), `ep_default`, `kelompok_opsi`, `lampiran`

- [ ] **Step 1: ICD-9 sebagai picker — tanpa membuang input lama**

Tambah `<input list="globalIcd9List">` + tombol "Tambah" yang menyisipkan kode terpilih ke hidden `icd9_kode` dan merender chip yang bisa dihapus. Isi `globalIcd9List` dari `klinis.models.MasterIcd9`, dibatasi ke kode yang muncul di `KasusTindakan` untuk kelompok kunjungan — 500 baris datalist tidak terpakai.

Field lama `icd9_tindakan` **tetap ada dan tetap disimpan** (readonly, menampilkan gabungan chip). Alasan: data kunjungan lama menyimpan teks bebas di kolom itu, dan print `cetak_asesmen_medis_igd.html` membacanya. Menghapusnya akan memutus riwayat.

- [ ] **Step 2: Tariff preview strip**

```html
<div class="alert alert-light border py-2 px-3 mb-0" id="tarifPreview">
    <span class="small text-muted">Tarif otomatis (<strong>{{ k.get_penjamin_display }}</strong>):</span>
    <strong class="ms-2" id="tarifTotal">Rp —</strong>
    <a href="#" class="small ms-2" onclick="...">rincian</a>
</div>
```

Populate from a JSON endpoint `api_tarif_preview?kunjungan=<pk>&icd9=<kode>` that calls the **same** `resolve()` — no tariff arithmetic in JavaScript. If any selected code resolves to `None`, show `Tarif belum ditetapkan untuk <kode>` in text-warning instead of a total.

- [ ] **Step 3: Kartu EP — pilih bebas dari katalog, 4 default tercentang**

Dokumen meminta "Pilih Bab / Standar Akreditasi" dengan autolink, jadi kontrolnya adalah **dropdown berisi seluruh `sub_standard`** di `akreditasi.StandardItem` (di-`group` per `Category.name`), bukan daftar tertutup. Saat form dibuka, baris dari `AturanEpAsesmen` sudah tercentang. Setiap baris terpilih punya tiga radio (Terpenuhi / Belum / NA), field catatan, dan menampilkan `StandardItem.code` + potongan `description` (160 karakter) agar petugas tahu apa yang diattestasi.

Jika `sub_standard` yang dikirim tidak ada di katalog (kasus `PAP 2.1`, spec §4 D8), render baris peringatan `Standar <kode> tidak ditemukan di katalog akreditasi` dan lewati saat simpan — jangan 500, jangan hilang diam-diam.

- [ ] **Step 4: Attachment list**

Existing files render as `nama_asli` + formatted `ukuran` + upload date + download/delete buttons; the upload form is `enctype="multipart/form-data"` posting to `asesmen_lampiran_upload`, `accept=".pdf,.xls,.xlsx,.doc,.docx"`.

- [ ] **Step 5: Catatan waktu textarea** bound to `asesmen_catatan_waktu`.

- [ ] **Step 6: Template smoke test**

```python
class AsesmenTabRenderTest(TestCase):
    def test_dropdown_lists_all_sub_standards(self): ...
    def test_default_ep_rules_prechecked(self): ...
    def test_unresolved_sub_standard_renders_warning_not_500(self): ...
    def test_tarif_preview_endpoint_returns_null_for_unknown(self): ...
    def test_icd9_choices_limited_to_kelompok(self): ...
    def test_legacy_icd9_text_still_rendered(self): ...
```

- [ ] **Step 7: Commit**

```bash
git add templates/pasien pasien/views.py
git commit -m "feat(pasien): tab diagnosa & tarif, kartu EP, dan panel lampiran asesmen"
```

---

### Task 8: Recap table with view / edit / delete

**Files:**
- Create: `templates/pasien/asesmen_rekap.html`
- Modify: `pasien/views.py` (three views), `pasien/urls.py`
- Modify: `templates/includes/sidebar.html`

**Interfaces:**
- Produces: `asesmen_rekap`, `asesmen_detail`, `asesmen_hapus`

- [ ] **Step 1: List view — hanya kunjungan yang punya asesmen**

```python
@login_required
@require_patient_module('igd')
def asesmen_rekap(request):
    qs = (scope_kunjungan_qs(request.user)
          .filter(jenis_kunjungan='IGD')
          .exclude(anamnesis_rps='')                    # punya asesmen = ada anamnesis
          .select_related('pasien', 'unit_kerja')
          .annotate(tarif_asesmen=Sum(
              'billing__subtotal',
              filter=Q(billing__sumber='ASESMEN')))
          .order_by('-tanggal_masuk'))
    # filters: q (no RM / nama), penjamin, ep_status, tanggal_from / tanggal_to
```

Filter `exclude(anamnesis_rps='')` adalah yang membuat entri hilang dari daftar setelah dihapus. Jangan ganti dengan filter lain yang lebih longgar.

Columns exactly as the user's wireframe: `No | No. RM & Pasien | Diagnosis (ICD-10 / SDKI) | Jenis Pasien | Tarif (Rp) | Status EP | Aksi`.

Tarif column comes from the `Sum` annotation — **not** a Python loop over rows (this view will hold thousands of visits). Tampilkan `—` bila `tarif_asesmen` is `None`, bukan `Rp 0`.

- [ ] **Step 2: Detail view** — read-only, mirrors the print form plus the EP grid and the attachment list. This is the 👁️ action.

- [ ] **Step 3: Delete view — menghapus data asesmen, sesuai dokumen**

Dokumen 2 meminta: *"Hapus (🗑️): Menghapus data asesmen yang keliru dari database dengan sistem pengamanan konfirmasi (safety prompt) agar data penting tidak terhapus secara tidak sengaja."*

```python
# Field → nilai kosong. JSONField wajib kembali ke default-nya, bukan None.
ASESMEN_DELETE_NILAI = {
    **{f: '' for f in (
        'keadaan_umum', 'kesadaran', 'nyeri_karakteristik', 'fungsional_adl',
        'anamnesis_rps', 'anamnesis_rpd', 'anamnesis_rpk', 'anamnesis_obat',
        'fisik_airway', 'fisik_breathing', 'fisik_circulation', 'fisik_disability',
        'fisik_exposure', 'status_psikososial', 'status_spiritual',
        'skrining_jatuh_grade', 'diagnosa_keperawatan_sdki',
        'luaran_keperawatan_slki', 'intervensi_keperawatan_siki',
        'diagnosa_masuk', 'icd9_tindakan', 'asesmen_catatan_waktu',
    )},
    'fisik_head_to_toe': {},
    'skrining_jatuh_detail': {},
    'skrining_jatuh_skor': None,
    'skrining_gizi_mst': None,
}

@login_required
@require_POST
@require_patient_module('igd')
def asesmen_hapus(request, pk):
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if not can_read_kunjungan(k, getattr(request.user, 'profile', None)):
        raise PermissionDenied(...)
    if request.POST.get('konfirmasi', '').strip().upper() != 'HAPUS':   # safety prompt
        messages.error(request, 'Ketik HAPUS untuk mengonfirmasi penghapusan.')
        return redirect('pasien:asesmen_rekap')
    with transaction.atomic():
        # 1. hapus artefak asesmen dari database
        k.korelasi_ep.all().delete()
        k.lampiran_asesmen.all().delete()
        BillingItem.objects.filter(kunjungan=k, sumber='ASESMEN').delete()
        # 2. kosongkan field asesmen
        for field, nilai in ASESMEN_DELETE_NILAI.items():
            setattr(k, field, nilai)
        k.save(update_fields=list(ASESMEN_DELETE_NILAI))
        AuditLog.objects.create(...)     # actor, kunjungan, aksi='HAPUS_ASESMEN'
    messages.success(request, f'Data asesmen {k.pasien.nama_lengkap} dihapus.')
    return redirect('pasien:asesmen_rekap')
```

Batas yang disengaja: yang **tidak** dihapus adalah `KunjunganPasien`, `CPPT`, `OrderPenunjang`, dan `BillingItem(sumber='MANUAL')`. Menghapus kunjungan akan meng-cascade keempatnya dan menghapus rekam medis pasien — itu bukan yang diminta dokumen. Yang dihapus adalah *data asesmen*, dan barisnya hilang dari tabel rekap.

- [ ] **Step 4: Tests**

```python
class AsesmenHapusTest(TestCase):
    def test_requires_post(self): ...
    def test_requires_konfirmasi_token(self): ...
    def test_clears_assessment_fields(self): ...
    def test_row_disappears_from_rekap(self): ...
    def test_deletes_ep_and_lampiran_rows(self): ...
    def test_deletes_asesmen_billing_keeps_manual(self): ...
    def test_keeps_visit_cppt_orders(self): ...
    def test_writes_audit_log(self): ...
    def test_denied_for_other_unit(self): ...

class AsesmenRekapTest(TestCase):
    def test_scoped_to_user_unit(self): ...
    def test_only_rows_with_assessment(self): ...
    def test_ep_status_column_reflects_rows(self): ...
    def test_tarif_column_sums_only_asesmen_source(self): ...
    def test_missing_tariff_renders_dash_not_zero(self): ...
```

- [ ] **Step 5: Sidebar entry** under the IGD group, label `Rekap Asesmen IGD`.

- [ ] **Step 6: Run and commit**

```bash
.venv/Scripts/python.exe manage.py test pasien --keepdb -v 2
git add pasien templates
git commit -m "feat(pasien): tabel rekap asesmen IGD dengan aksi lihat, edit, dan reset aman"
```

---

## Phase 5 — Release

### Task 9: Supabase migration and static artifacts

- [ ] **Step 1: Full suite, no `--keepdb`, from scratch**

```bash
.venv/Scripts/python.exe manage.py test pasien akreditasi klinis sdm -v 2
```

Record any failure. Only pre-existing, previously-known failures are acceptable, and each must be named in the delivery note.

- [ ] **Step 2: Apply migrations to Supabase manually** (they never run on deploy)

```bash
# with DATABASE_URL exported for Supabase
.venv/Scripts/python.exe manage.py migrate klinis
.venv/Scripts/python.exe manage.py migrate pasien
.venv/Scripts/python.exe manage.py seed_katalog_klinis
```

Verify afterwards against the live DB, not the local SQLite:

```bash
.venv/Scripts/python.exe manage.py shell -c "from klinis.models import KasusTersering, KasusTindakan; print(KasusTersering.objects.count(), KasusTindakan.objects.count())"
```

- [ ] **Step 3: Rebuild static artifacts and commit them** (`staticfiles/` is tracked for Vercel)

```bash
.venv/Scripts/python.exe manage.py collectstatic --noinput
git add staticfiles static
git commit -m "chore(static): collectstatic untuk JS asesmen IGD"
```

Commit the hash-named artefacts **and** `staticfiles.json` together — a partial commit leaves production pointing at a missing hash.

- [ ] **Step 4: Push**

```bash
git push origin master
```

---

## Definition of Done

- [ ] `klinis` registered in `INSTALLED_APPS`, `makemigrations --check` clean.
- [ ] Seed produces ≥ 14 kelompok, 215 kasus (210 ICD-10 + 5 SDKI-only), ≥ 380 `KasusTindakan`, zero rows with a non-positive tariff, `MATA_PASCA` rows all null-tariff, every truncated row flagged `perlu_verifikasi`.
- [ ] `seed_katalog_klinis` is idempotent — second run changes no counts.
- [ ] Saving an assessment with a selected ICD-9 produces exactly one `BillingItem(sumber='ASESMEN')` per code; re-saving produces no duplicate; deselecting deletes the row; a manual `BillingItem` survives both.
- [ ] BPJS visit reads `tarif_bpjs`, UMUM visit reads `tarif_umum`, both verified by test.
- [ ] EP correlation saves per rule; an unresolved `sub_standard` renders a warning and never raises.
- [ ] Attachments: `.pdf/.xls/.xlsx/.doc/.docx` accepted, others rejected, >10 MB rejected, download gated by unit access.
- [ ] Morse score and grade are derived from the six items, not typed.
- [ ] Recap table renders with all six columns, is unit-scoped, and its tarif column sums only `sumber='ASESMEN'`.
- [ ] Reset requires POST + confirm token, clears assessment + EP + asesmen billing, keeps visit/CPPT/orders/manual billing, writes `AuditLog`.
- [ ] Existing suites green: `pasien`, `akreditasi`, `sdm` — with any pre-existing failure named.
- [ ] Migrations applied to Supabase **manually** and verified against the live DB.
- [ ] `staticfiles/` collected and committed with `staticfiles.json` in the same commit.
