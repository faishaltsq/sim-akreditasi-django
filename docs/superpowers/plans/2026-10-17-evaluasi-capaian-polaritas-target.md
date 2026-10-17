# Evaluation & Monitoring — Capability Polarity, Target Source, and Gap Display

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Section G.1 of the risk evaluation page, the Monitoring & Evaluation table, and every report/export must judge achievement with the indicator's real polarity and real target — not a hardcoded `≥ 100%`. A Phlebitis rate of 1.0‰ against a target of ≤ 1.5‰ must read **Tercapai**, and the gap must be shown as a signed number.

**Architecture:** One resolver in `akreditasi/risiko_models.py` (`RisikoUnit.capaian_evaluasi`) becomes the single source of truth for *(target, arah, status, gap)*. Every render path and both CSV exports read that property instead of re-deriving with `or 100`. One new nullable field `arah_capaian` stores polarity for risks whose indicator is not linked to the master catalogue (migration `0040`). The plan-stage target input gains a polarity selector so the value is captured when the risk is created, not guessed later. A read-only management command audits the 327 master indicators whose polarity is currently wrong.

**Status:** Not started.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, vanilla JS. One migration, no new pip package, no new endpoint.

**Spec:** `C:\Users\cubeb\Downloads\Ini perbaikan di menu evaluasi dan monitoring 3.40.docx` — section 1 (flowchart: linked vs unlinked branch), section 2 (Tahap A auto-mapping, Tahap B string-parser fallback, Tahap C status & gap formulas), section 3 (reference `hitung_evaluasi_indikator`).

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `1,5`; a single comma inside `<script>` kills the whole block (bugs `84c20ce`, `c4c2a3c`). Every template touched here already has `{% load l10n %}` — keep it.
- **No behaviour change for risks that are already correct.** 102 of 128 production risks are linked; their rendered status must stay byte-identical unless their polarity is genuinely wrong. Verify with a render-diff, not by eye.
- **Do not silently rewrite production polarity.** The audit command reports candidates; a human applies them. 367 indicators × a heuristic rename is exactly the kind of change that must be reviewable.
- **POST acceptance stays permissive.** The new field is display logic, not authorization.
- **The resolver is named `capaian_evaluasi`, not `evaluasi_capaian`.** `RisikoUnit` already has a `TextField` named `evaluasi_capaian` (`akreditasi/risiko_models.py:160`), rendered as free text at `templates/akreditasi/risiko_monitoring_evaluasi.html:277`. Naming the new property `capaian_evaluasi` keeps the narrative field and the computed status separate; renaming it back would shadow the field and break the monitoring page.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1` — baseline **102/102 OK**.
- Work on `master`; commit after Task 5.

## Verified production facts (Supabase `gwaeuzbbdawbekrmrvfd`, read 2026-10-17)

| Fact | Value |
|---|---|
| `akreditasi_indikatormutu` active | 367 |
| `arah_target = 'MAX'` | **0** |
| `arah_target = 'MIN'` | **367** |
| by jenis | `IMP_UNIT` 219, `IMP_RS` 108, `NASIONAL` 40 |
| `CatatanIndikator` 2026 | `IMP_RS` 432, `NASIONAL` 156 — no `IMP_UNIT` rows |

**Local dev DB differs — measured 2026-10-17 (same code, smaller dataset):** `IndikatorMutu`
209 active (`IMP_RS` 98, `IMP_UNIT` 75, `NASIONAL` 36), `arah_target` `MIN` 209 / `MAX` 0,
`RisikoUnit` 448 rows / 100 linked to an indicator, `CatatanIndikator` 2026 = 588
(`IMP_RS` 432, `NASIONAL` 156, `IMP_UNIT` 0), `UnitKerja` 218. Do not size queries or write
assertions against these counts: tests build their own fixtures, and the production numbers
above are what the audit command will report.

The polarity column is populated but uniformly wrong. Concrete rows that are lower-is-better yet stored `MIN`:

| id | kode | target | arah stored | should be |
|---|---|---|---|---|
| 17 | IMP-RANAP-01 Re-admisi < 30 hari | 3.00 | MIN | MAX |
| 18 | IMP-RANAP-02 Dekubitus baru | 0.00 | MIN | MAX |
| 227 | IMP-UNIT-RANAP-02 Phlebitis (≤ 1,5‰) | 1.50 | MIN | MAX |

With `MIN`, `capaian >= target` is `1.0 >= 1.5` → false → the row renders red. That is the exact false-negative the spec complains about, and **the code path in `views.py:128` and `risiko_models.py:585` is already correct** — it is the data that is wrong. So this plan fixes three things: the data audit, the two render paths that ignore polarity entirely, and the inability to record polarity for an unlinked indicator.

---

### Task 1: `arah_capaian` field + migration `0040`

**Files:**
- Modify: `akreditasi/risiko_models.py` (after `target_capaian_indikator`, ~line 106)
- Create: `akreditasi/migrations/0040_risikounit_arah_capaian.py`

**Why:** `target_capaian_indikator` is `DecimalField(max_digits=5, decimal_places=2)`. It physically cannot hold `"<1,5"`, so an unlinked risk has no way to record that its target is a ceiling. Without this field, the fallback branch in the spec (Tahap B) can only guess.

- [x] **Step 1: Add the field**

```python
    target_capaian_indikator = models.DecimalField(
        'Target Capaian Indikator (%)', max_digits=5, decimal_places=2,
        null=True, blank=True
    )
    # Polaritas untuk risiko yang indikatornya belum ditautkan ke master.
    # Kosong = ikut master (atau MIN bila master tidak ada). Hanya dipakai
    # bila target_capaian_indikator diisi manual tanpa indikator_mutu_terkait.
    arah_capaian = models.CharField(
        'Arah Target Capaian', max_length=3, blank=True, default='',
        choices=[('', 'Ikuti Master'), ('MIN', '≥ Target (makin besar makin baik)'),
                 ('MAX', '≤ Target (makin kecil makin baik)')],
        help_text='Hanya berlaku bila indikator mutu belum ditautkan ke master.'
    )
```

- [x] **Step 2: Generate and inspect the migration**

```bash
.venv/Scripts/python.exe manage.py makemigrations akreditasi --name risikounit_arah_capaian
.venv/Scripts/python.exe manage.py sqlmigrate akreditasi 0040
```

Expected: a single `ALTER TABLE ... ADD COLUMN "arah_capaian" varchar(3) NOT NULL DEFAULT ''`. No data migration, no destructive statement.

- [x] **Step 3: Apply locally and confirm the suite is untouched**

```bash
.venv/Scripts/python.exe manage.py migrate akreditasi
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator -v1
```

Expected: 16/16 OK. A new column with a default cannot break existing assertions.

---

### Task 2: `RisikoUnit.capaian_evaluasi` — one resolver for target, polarity, status, gap

**Files:**
- Modify: `akreditasi/risiko_models.py` (replace `capaian_persen_display`, ~line 198)

**Why:** the status rule is currently written four times (view, two templates, two exports) with three different target fallbacks. Every divergence is a bug waiting to happen — the monev template already ignores polarity, and the CSV export already invents `100`.

- [x] **Step 1: Add the resolver and keep `capaian_persen_display` as a thin wrapper**

```python
    @property
    def capaian_evaluasi(self):
        """Satu sumber kebenaran untuk (target, arah, status, gap) capaian risiko.

        Urutan target: target rencana (diisi di tahap Plan) -> target master
        indikator -> None. Arah: arah_capaian manual -> master -> 'MIN'.
        Return dict; nilai None berarti belum bisa dievaluasi.
        """
        ind = self.indikator_mutu_terkait
        arah = (self.arah_capaian
                or (getattr(ind, 'arah_target', '') if ind else '')
                or 'MIN')
        satuan = (getattr(ind, 'satuan', '') if ind else '') or '%'

        if self.target_capaian_indikator is not None:
            target, sumber = float(self.target_capaian_indikator), 'rencana'
        elif ind is not None and ind.target_nilai is not None:
            target, sumber = float(ind.target_nilai), 'master'
        else:
            target, sumber = None, 'tidak_ada'

        capaian = float(self.capaian_nilai) if self.capaian_nilai is not None else None
        if capaian is None or target is None:
            return {'target': target, 'arah': arah, 'satuan': satuan,
                    'sumber': sumber, 'capaian': capaian,
                    'tercapai': None, 'gap': None, 'gap_abs': None}

        tercapai = capaian <= target if arah == 'MAX' else capaian >= target
        # Gap selalu bertanda "seberapa baik": positif = margin aman,
        # negatif = seberapa jauh di luar target. Simetris untuk kedua arah.
        gap = (target - capaian) if arah == 'MAX' else (capaian - target)
        return {'target': target, 'arah': arah, 'satuan': satuan,
                'sumber': sumber, 'capaian': capaian, 'tercapai': tercapai,
                'gap': round(gap, 2), 'gap_abs': round(abs(gap), 2)}

    @property
    def capaian_persen_display(self):
        """Format tampilan persen capaian indikator."""
        if self.capaian_nilai is not None:
            return f"{self.capaian_nilai:.1f}%"
        return "—"

    @property
    def capaian_status_label(self):
        ev = self.capaian_evaluasi
        if ev['tercapai'] is None:
            return None
        return 'Tercapai' if ev['tercapai'] else 'Belum Tercapai'
```

- [x] **Step 2: Verify the resolver against the three production rows by hand**

```bash
.venv/Scripts/python.exe manage.py shell -c "
from akreditasi.risiko_models import RisikoUnit
for pk in (139, 140):
    r = RisikoUnit.objects.select_related('indikator_mutu_terkait').get(pk=pk)
    print(pk, r.indikator_mutu_terkait, r.capaian_evaluasi)
"
```

Expected for a Phlebitis risk with `capaian_nilai=1.0` and `arah='MAX'`: `tercapai=True`, `gap=0.5`. With `arah='MIN'`: `tercapai=False`, `gap=-0.5`.

---

### Task 3: Plan-stage polarity selector so unlinked risks record their own direction

**Files:**
- Modify: `templates/akreditasi/risiko_form.html` (~line 478, the Target Capaian input)
- Modify: `akreditasi/risiko_views.py` (~line 321 and ~line 404 create; ~line 557 and ~line 631 edit)

**Why:** the spec's Tahap B wants a string parser on free text. A parser on a `type=number` field is dead code — the browser rejects `<1,5` before submit. A two-option selector next to the number captures the same information exactly, with no regex guesswork and no ambiguity when the value is `100` (which is both `≥100` and `≤100` depending on intent).

- [x] **Step 1: Widen the input and add the polarity select**

```html
                                <div class="col-md-3">
                                    <label class="form-label" style="font-size:.8rem; font-weight:600;">
                                        <i class="bi bi-bullseye text-success me-1"></i>Target Capaian
                                    </label>
                                    <div class="input-group input-group-sm">
                                        <select name="arah_capaian" id="arah_capaian" class="form-select" style="max-width:120px;">
                                            <option value="">Ikuti Master</option>
                                            <option value="MIN">&ge; Target</option>
                                            <option value="MAX">&le; Target</option>
                                        </select>
                                        <input type="number" name="target_capaian_indikator" id="target_capaian_indikator"
                                               class="form-control form-control-sm" placeholder="cth: 100.00"
                                               min="0" max="1000" step="0.01">
                                    </div>
                                    <small class="text-muted" style="font-size:.65rem;">
                                        Pilih &le; Target untuk indikator risiko (mis. Phlebitis &le; 1,5&permil;).
                                    </small>
                                </div>
```

`max` moves from `100` to `1000` because `target_capaian_indikator` is `max_digits=5` and a rate per-mille can exceed 100.

- [x] **Step 2: Persist it on create and edit**

In the create block (`risiko_views.py` ~line 404) and the edit block (~line 631), alongside the existing `target_capaian_indikator` assignment:

```python
                arah_capaian=(request.POST.get('arah_capaian') or '').strip()[:3],
```

- [x] **Step 3: Confirm the edit-form prefill carries it**

The edit JSON payload already ships `target_capaian_indikator`; add `arah_capaian` to the same serializer so the JS at `risiko_form.html:1846` restores it:

```python
        'arah_capaian': risiko.arah_capaian or '',
```

and in the JS prefill block next to the target assignment:

```javascript
        if (editData.arah_capaian !== undefined) {
            const el = document.querySelector('[name="arah_capaian"]');
            if (el) el.value = editData.arah_capaian;
        }
```

---

### Task 4: G.1 banner and live badge read the resolver, not a template guess

**Files:**
- Modify: `akreditasi/risiko_views.py` (~line 872, the `target_nilai_display` block)
- Modify: `templates/akreditasi/risiko_evaluasi.html` (~line 194 banner, ~line 630 JS block)

**Why:** `target_nilai_display = target_nilai_display or 100` is the literal source of the `≥ 100%` the spec complains about. And the banner picks `≤`/`≥` from `risiko.indikator_mutu_terkait.arah_target`, which is empty for an unlinked risk — so it always shows `≥`.

- [x] **Step 1: Replace the three-line fallback with the resolver**

```python
    _ev = risiko.capaian_evaluasi
    target_nilai_display = _ev['target']
    arah_nilai_display = _ev['arah']
    satuan_nilai_display = _ev['satuan']
```

Keep `target_nilai_display` as the variable name — the template and the JS block already read it, so nothing downstream changes shape.

- [x] **Step 2: Point the banner at the resolved values**

```html
                                    <span class="text-muted d-block" style="font-size:.68rem;">
                                        Target Standar Mutu:
                                        {% if _ev.sumber == 'rencana' %}<span class="badge bg-info-subtle text-info border" style="font-size:.6rem;">Rencana</span>{% endif %}
                                    </span>
                                    <span class="badge bg-success fs-6 fw-bold">
                                        {% if arah_nilai_display == 'MAX' %}&le;{% else %}&ge;{% endif %}
                                        {{ target_nilai_display|default_if_none:"—"|unlocalize }} {{ satuan_nilai_display }}
                                    </span>
```

- [x] **Step 3: Feed the live JS the resolved polarity**

Replace `let arahTarget = "{{ risiko.indikator_mutu_terkait.arah_target|default:'MIN' }}";` with:

```javascript
    let arahTarget = "{{ arah_nilai_display|default:'MIN' }}";
```

and replace the `targetVal` initialiser's `|| 100` with a null-safe read:

```javascript
    let targetVal = parseFloat("{{ target_nilai_display|default_if_none:''|unlocalize }}".replace(',', '.'));
    if (isNaN(targetVal)) targetVal = null;
```

`evaluateCapaian()` already branches on `MAX` correctly (`risiko_evaluasi.html:673`); it only needs a null target guard so it shows "target belum diisi" instead of comparing against `NaN`:

```javascript
        if (targetVal === null) {
            statusBadge.className = 'badge bg-light text-muted border';
            statusBadge.innerHTML = '<i class="bi bi-dash-circle me-1"></i>Target belum diisi';
            return;
        }
```

---

### Task 5: Monitoring table and both CSV exports use the same resolver

**Files:**
- Modify: `templates/akreditasi/risiko_monitoring_evaluasi.html` (~line 255 target badge, ~line 264–274 status badge)
- Modify: `akreditasi/risiko_views.py` (~line 1063 monev CSV, ~line 1596 laporan lengkap, ~line 1698 laporan CSV, ~line 2013 laporan view)

**Why:** `risiko_monitoring_evaluasi.html:269` compares `r.capaian_nilai >= r.target_capaian_indikator|default:100` with no polarity at all — every lower-is-better indicator in that table is wrong today. And four report paths each carry their own `or 100`.

- [x] **Step 1: Rewrite the monev target + status cell**

```html
                                <span class="badge bg-secondary-subtle text-secondary" style="font-size:.68rem;">
                                    Target: {% if r.capaian_evaluasi.arah == 'MAX' %}&le;{% else %}&ge;{% endif %}{{ r.capaian_evaluasi.target|default_if_none:"—"|unlocalize }}{{ r.capaian_evaluasi.satuan }}
                                </span>
```

```html
                                {% if r.capaian_evaluasi.tercapai is not None %}
                                    {% if r.capaian_evaluasi.tercapai %}
                                    <span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:.65rem;">
                                        Tercapai &middot; margin {{ r.capaian_evaluasi.gap_abs|unlocalize }}
                                    </span>
                                    {% else %}
                                    <span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:.65rem;">
                                        Belum Target &middot; gap {{ r.capaian_evaluasi.gap_abs|unlocalize }}
                                    </span>
                                    {% endif %}
                                {% endif %}
```

Note `is not None` — Django templates treat `False` and `None` alike in `{% if %}`, so `{% if r.capaian_evaluasi.tercapai %}` alone would silently drop the red badge.

- [x] **Step 2: Replace every `or 100` in the report paths**

At `risiko_views.py:1063`, `:1596`, `:1698`, `:2013` the pattern is the same. Replace with:

```python
        _ev = r.capaian_evaluasi
        if _ev['target'] is not None:
            target_str = f"{_ev['target']:.1f}{_ev['satuan']}"
        else:
            target_str = '—'
```

and for the monev CSV indicator column specifically:

```python
        ind_text = (f"{r.indikator_mutu_terkait.nama_indikator} "
                    f"(Target: {'≤' if _ev['arah'] == 'MAX' else '≥'}{_ev['target']:.1f}{_ev['satuan']})"
                    if r.indikator_mutu_terkait and _ev['target'] is not None
                    else (r.indikator_mutu_terkait.nama_indikator if r.indikator_mutu_terkait else '—'))
```

- [x] **Step 3: Add a status column to the monev CSV so the export matches the screen**

Append `'Status Capaian'` to the header row at `:1044` and the corresponding value in the body loop:

```python
        writer.writerow([... , r.capaian_status_label or 'Belum Dievaluasi'])
```

---

### Task 6: `audit_arah_target` — read-only polarity audit for the 367 master rows

**Files:**
- Create: `akreditasi/management/commands/audit_arah_target.py`

**Why:** the code can honour polarity all it likes; with `arah_target='MAX'` on zero rows the display stays wrong. The audit must be a reviewable list, not an UPDATE — 219 `IMP_UNIT` rows include both "Kepatuhan …" (higher-is-better) and "Angka Kejadian …" (lower-is-better), and a regex over Indonesian indicator names will get some wrong.

- [x] **Step 1: Write the command**

```python
from django.core.management.base import BaseCommand
from akreditasi.risiko_models import IndikatorMutu

LOWER_IS_BETTER = (
    'kejadian', 'angka ', 'insiden', 'infeksi', 'ido', 'isk', 'phlebitis',
    'jatuh', 'dekubitus', 're-admisi', 'readmisi', 'kematian', 'mortalitas',
    'waktu tunggu', 'keterlambatan', 'komplain', 'keluhan', 'kesalahan',
    'error', 'drop out', 'putus obat', 'lost to follow',
)
HIGHER_IS_BETTER = ('kepatuhan', 'ketaatan', 'kelengkapan', 'cakupan', 'kepuasan', 'keberhasilan')


class Command(BaseCommand):
    help = 'Audit arah_target indikator mutu (read-only). Tidak mengubah data.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Terapkan perubahan untuk baris yang yakin (bukan tebakan).')

    def handle(self, *args, **opts):
        rows = IndikatorMutu.objects.filter(aktif=True).order_by('jenis', 'kode_indikator')
        salah, ragu, benar = [], [], 0
        for ind in rows:
            nama = (ind.nama_indikator or '').lower()
            low = any(k in nama for k in LOWER_IS_BETTER)
            high = any(k in nama for k in HIGHER_IS_BETTER)
            if low and not high:
                if ind.arah_target != 'MAX':
                    salah.append(ind)
            elif high and not low:
                if ind.arah_target != 'MIN':
                    salah.append(ind)
            elif low and high:
                ragu.append(ind)
            else:
                benar += 1

        self.stdout.write(f'Total aktif: {rows.count()} | sudah benar: {benar} | '
                          f'perlu diperbaiki: {len(salah)} | ambigu: {len(ragu)}')
        for ind in salah:
            self.stdout.write(f'  FIX  [{ind.kode_indikator}] {ind.nama_indikator[:70]} '
                              f'arah={ind.arah_target} target={ind.target_nilai}')
        for ind in ragu:
            self.stdout.write(f'  RAGU [{ind.kode_indikator}] {ind.nama_indikator[:70]}')

        if opts['apply'] and salah:
            for ind in salah:
                nama = (ind.nama_indikator or '').lower()
                ind.arah_target = 'MAX' if any(k in nama for k in LOWER_IS_BETTER) else 'MIN'
            IndikatorMutu.objects.bulk_update(salah, ['arah_target'])
            self.stdout.write(self.style.SUCCESS(f'Diterapkan ke {len(salah)} baris.'))
        elif salah:
            self.stdout.write(self.style.WARNING('Dry run. Jalankan dengan --apply untuk menerapkan.'))
```

- [x] **Step 2: Run it against production and read the list before applying**

```bash
.venv/Scripts/python.exe manage.py audit_arah_target
```

Expected: roughly 100–150 rows in the FIX bucket (every "Angka Kejadian…", "…Infeksi…", "Phlebitis", "Dekubitus", "Re-admisi", "waktu tunggu" indicator), a handful in RAGU (names containing both "kepatuhan" and "kejadian"). Apply only after reading the FIX list.

- [x] **Step 3: Apply, then re-run to confirm zero FIX rows remain**

```bash
.venv/Scripts/python.exe manage.py audit_arah_target --apply
.venv/Scripts/python.exe manage.py audit_arah_target
```

---

### Task 7: Regression tests

**Files:**
- Modify: `akreditasi/tests_evaluasi_indikator.py`

**Why:** the polarity rule is the whole point of the spec and currently has no test that would fail if someone re-hardcoded `>=`.

- [x] **Step 1: Add the resolver tests**

```python
class EvaluasiCapaianPolaritasTest(TestCase):
    """Polaritas + gap harus benar untuk kedua arah, dengan dan tanpa master."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin_pol', 'pol@rs.id', 'secret123')
        self.unit = UnitKerja.objects.create(name='Bangsal Pol', code='POL-01', tipe_unit='RUANGAN')
        self.ind_max = IndikatorMutu.objects.create(
            nama_indikator='Angka Kejadian Phlebitis', kode_indikator='POL-MAX',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('1.50'),
            satuan='‰', arah_target='MAX',
        )

    def _mk(self, **kw):
        base = dict(unit=self.unit, jenis_risiko='KLINIS', tahun=2026,
                    dampak=3, probabilitas=3, strategi_mitigasi='MITIGASI',
                    rencana_aksi='x', pj_mitigasi='x')
        base.update(kw)
        return RisikoUnit.objects.create(**base)

    def test_lower_is_better_di_bawah_target_tercapai(self):
        r = self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('1.00'))
        ev = r.capaian_evaluasi
        self.assertTrue(ev['tercapai'])
        self.assertAlmostEqual(ev['gap'], 0.5)

    def test_lower_is_better_di_atas_target_tidak_tercapai(self):
        r = self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('2.50'))
        ev = r.capaian_evaluasi
        self.assertFalse(ev['tercapai'])
        self.assertAlmostEqual(ev['gap'], -1.0)

    def test_arah_manual_menimpa_master_saat_belum_tertaut(self):
        r = self._mk(arah_capaian='MAX', target_capaian_indikator=Decimal('1.50'),
                     capaian_nilai=Decimal('0.80'))
        ev = r.capaian_evaluasi
        self.assertTrue(ev['tercapai'])
        self.assertEqual(ev['sumber'], 'rencana')

    def test_tanpa_target_tidak_dianggap_gagal(self):
        r = self._mk(capaian_nilai=Decimal('90'))
        ev = r.capaian_evaluasi
        self.assertIsNone(ev['tercapai'])
        self.assertIsNone(r.capaian_status_label)

    def test_target_rencana_menang_atas_master(self):
        r = self._mk(indikator_mutu_terkait=self.ind_max,
                     target_capaian_indikator=Decimal('0.50'),
                     capaian_nilai=Decimal('1.00'))
        ev = r.capaian_evaluasi
        self.assertFalse(ev['tercapai'])
        self.assertEqual(ev['sumber'], 'rencana')
```

- [x] **Step 2: Add a render test for the monev table**

```python
    def test_monev_menampilkan_le_bukan_ge_untuk_indikator_max(self):
        self._mk(indikator_mutu_terkait=self.ind_max, capaian_nilai=Decimal('1.00'))
        self.client.force_login(self.user)
        html = self.client.get('/risiko/monitoring-evaluasi/?tahun=2026').content.decode()
        self.assertIn('&le;', html)
        self.assertIn('Tercapai', html)
```

- [x] **Step 3: Run the module, then the full suite**

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator -v1
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1
```

Expected: 21/21 module (16 + 5 resolver + 1 render = 22 if all land), then 108/108 suite.

- [x] **Step 4: `node --check` on the touched JS**

```bash
.venv/Scripts/python.exe manage.py shell -c "
import re
html = open('templates/akreditasi/risiko_evaluasi.html', encoding='utf-8').read()
js = re.search(r'{% block extra_js %}(.*?){% endblock %}', html, re.S).group(1)
open(r'$TMPDIR/eval.js','w',encoding='utf-8').write(js)
" && node --check "$TMPDIR/eval.js"
```

- [x] **Step 5: Render-diff against the pre-change baseline**

Render the same risk (`EV_MODE=pk:140`) before and after, then diff. Expected differences: only the target badge and status badge lines. No `<script>` line may differ except the two changed JS initialisers.

- [ ] **Step 6: Commit, push, confirm deploy**

```bash
git add akreditasi/risiko_models.py akreditasi/migrations/0040_risikounit_arah_capaian.py \
        akreditasi/risiko_views.py akreditasi/management/commands/audit_arah_target.py \
        templates/akreditasi/risiko_form.html templates/akreditasi/risiko_evaluasi.html \
        templates/akreditasi/risiko_monitoring_evaluasi.html akreditasi/tests_evaluasi_indikator.py \
        docs/superpowers/plans/2026-10-17-evaluasi-capaian-polaritas-target.md
git commit -m "fix(risiko): evaluate capability against real indicator polarity and target

Monitoring & evaluation judged every indicator with capaian >= target and a
hardcoded 100 fallback, so lower-is-better indicators (Phlebitis, Dekubitus,
re-admission) always rendered red. One resolver on RisikoUnit now owns
(target, arah, status, gap); the G.1 banner, the monev table and all four
report/export paths read it. Unlinked risks can record their own polarity
(arah_capaian), and audit_arah_target reports the 367 master rows whose
arah_target is uniformly MIN."
git push origin master
sleep 80 && gh api repos/faishaltsq/sim-akreditasi-django/commits/$(git rev-parse --short HEAD)/status --jq '.state, .statuses[].description'
```

Expected: `success` / `Deployment has completed`.

---

## Review Focus

- **`capaian_evaluasi` is a property, so it runs per row.** The monev view loads `risiko_list` with `select_related('unit', 'indikator_mutu_terkait')` already — confirm that stays, otherwise the table becomes N+1. The report loops at `:1596`, `:1698`, `:2013` iterate plain querysets; add `select_related('indikator_mutu_terkait')` if not already present.
- **`{% if r.capaian_evaluasi.tercapai %}` treats `False` as falsy but also `None`.** Every branch must test `is not None` first, or "belum diisi" renders as red.
- **Gap sign convention.** For `MAX`, `gap = target - capaian`; for `MIN`, `gap = capaian - target`. Positive always means "safe margin". The badge shows `gap_abs` with the word `margin` vs `gap`, so the sign never has to be read off a number.
- **Applying `--apply` is a production write.** Run the dry run, read the FIX list, then apply. If a row is genuinely ambiguous (both keywords), leave it in RAGU and fix it in the indicator form by hand.
- **Migration 0040 is additive with a default**, so it applies to Supabase without a data backfill and cannot fail on existing rows.
- Existing 16 tests must pass unchanged — none of them assert `100` as a target.
