# Per-Indicator Quality Charts (INM tier) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make both mutu dashboards chart ONE selected indicator instead of an average across all of them, and make the category → indicator cascade actually work, so choosing category INM offers the 13 INM indicators that have measurement data.

**Architecture:** All chart data stays server-computed and injected as JSON — no new endpoint, no new dependency, no migration. `/indikator-mutu/` gains an `indikator` GET param riding its existing filter form; `/` already has `mutu_indikator` but its `mutu_jenis` filter compares canonical codes (`INM`) against DB codes (`NASIONAL`), so the dropdown collapses. Both pages adopt the same selection rule: **an indicator is offered when it has at least one `CatatanIndikator` for the selected year**, falling back to every active indicator in the tier when none do.

**Tech Stack:** Django 4.x templates + Chart.js 4 (CDN, already loaded) + Bootstrap 5.3 bundle (already loaded). No new pip packages, no new CDN scripts, no migrations.

**Spec:** `C:\Users\cubeb\Downloads\Lakukan perubahan pada grafik indicator mutu dibawah ini.docx` (section 1 "Pemisahan Grafik per Indikator Mutu Spesifik")

## Global Constraints

- No new pip dependency, no new CDN script; the value-label plugin is inline (no `chartjs-plugin-datalabels`).
- Every float that reaches JavaScript must come from `json.dumps(...)` server-side, injected with `|safe`. **Never** render a bare `{{ float }}` inside `<script>` — locale `id` emits `85,0` and a single comma kills the entire script block (this exact bug caused outages fixed in `84c20ce` and `c4c2a3c`). Strings use `escapejs`.
- Keep existing element IDs and dataset labels (`chartTrenCapaian`, `chartJenisBulan`, `chartMutuBulanan`, `chartRenstraTahunan`, `Batas Target`, `Realisasi Capaian (%)`, `Target Renstra (%)`, `pills-bulanan-tab`, `pills-renstra-tab`) — `akreditasi/tests_indikator_mutu_charts.py` asserts them.
- Aggregate (no indicator selected) behaviour of both pages must stay byte-identical to today: `/indikator-mutu/` `[57.6, 59.5, 59.8, 60.6, 62.6, 61.4, 62.4, 56.9, 61.9, 61.9, 62.9, 63.2]`, `/?mutu_jenis=NASIONAL` unchanged.
- Colour contract: `#198754` = tercapai, `#dc3545` = di bawah target, `rgba(203, 213, 225, 0.4)` = belum ada data. `arah_target='MAX'` (lower is better) flips the comparison.
- Plans/docs in English; user-facing UI copy in Bahasa Indonesia.
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts akreditasi.tests_evaluasi_indikator akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1` (baseline 81/81 OK).
- Work on `master`; commit after each task.

## Reference data (verified, local + Supabase production identical)

| Tier (canonical) | DB `jenis` codes | Active rows | With 2026 catatan |
|---|---|---|---|
| INM  | `INM`, `NASIONAL` | 36 | **13** (`INM-01`…`INM-13`; `INM-14` + 22 `BAB-*` empty) |
| IMRS | `IMRS`, `IMP_RS`  | 98 | 36 |
| IMU  | `IMU`, `IMP_UNIT` | 75 | 0 → fallback to 75 |

## Review Focus

- A tier where **no** indicator has data for the selected year (IMU today): the dropdown must fall back to every active indicator in that tier, never render empty.
- `arah_target='MAX'` indicator selected: bars turn green when `capaian ≤ target`, and the card's legend text must not keep claiming "≥".
- A stale or foreign `indikator` pk (deleted, or belonging to another tier): page must render 200 and fall back to aggregate — never 500, never a blank canvas.
- A catatan with `nilai_denominator=0`: `nilai_capaian` returns 0, so the bar must read `0.0`, never `NaN`.
- Locale `id`: every injected float must be `85.0`, not `85,0`.

---

### Task 1: `/indikator-mutu/` backend — `indikator` param, data-bearing choices, per-indicator series

**Files:**
- Modify: `akreditasi/indikator_views.py:130-289` (view `indikator_dashboard`)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: `IndikatorMutu` (`pk`, `kode_indikator`, `nama_indikator`, `jenis`, `target_nilai`, `satuan`, `arah_target`), `CatatanIndikator` (`indikator`, `bulan`, `tahun`, `nilai_capaian` property).
- Produces (context keys consumed by Task 2):
  - `indikator_choices`: `list[IndikatorMutu]`
  - `filter_indikator`: `int` (0 = aggregate)
  - `indikator_terpilih`: `IndikatorMutu | None`
  - `has_indikator`: `bool`
  - `chart_indikator_data_json`: `list[float | None]` × 12
  - `chart_indikator_colors_json`: `list[str]` × 12
  - `chart_indikator_target_json`: `float`
  - `chart_indikator_target_line_json`: `list[float]` × 12
  - `chart_indikator_satuan`: `str`
  - `chart_indikator_arah`: `str` (`'MIN'`/`'MAX'`)

- [x] **Step 1: Write the failing tests**

Append to `akreditasi/tests_indikator_mutu_charts.py` (add `import re` at the top of the file):

```python
    # ── Per-indicator charts on /indikator-mutu/ ───────────────────────────

    def test_mutu_dashboard_dropdown_lists_only_data_bearing_indicators(self):
        """Choosing tier INM offers exactly the indicators that have catatan for the year."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))

        empty = IndikatorMutu.objects.create(
            nama_indikator='Belum Ada Data', kode_indikator='INM-99',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get('/indikator-mutu/?jenis=INM&tahun=2026')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        m = re.search(r'<select name="indikator".*?</select>', html, re.S)
        self.assertIsNotNone(m, 'dropdown indikator tidak dirender')
        opts = re.findall(r'<option value="(\d+)"', m.group(0))
        self.assertIn(str(self.indikator.pk), opts)
        self.assertNotIn(str(empty.pk), opts)

    def test_mutu_dashboard_empty_tier_falls_back_to_all_indicators(self):
        """A tier with zero catatan still lists its active indicators."""
        IndikatorMutu.objects.create(
            nama_indikator='Unit Tanpa Data', kode_indikator='IMU-99',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get('/indikator-mutu/?jenis=IMU&tahun=2026')
        self.assertEqual(resp.status_code, 200)
        m = re.search(r'<select name="indikator".*?</select>', resp.content.decode(), re.S)
        self.assertIsNotNone(m)
        self.assertIn('IMU-99', m.group(0))

    def test_mutu_dashboard_single_indicator_series_and_colors(self):
        """Selecting one indicator charts its own monthly capaian, not the average."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'))
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=2026,
            nilai_numerator=Decimal('70'), nilai_denominator=Decimal('100'))

        url = f'/indikator-mutu/?jenis=INM&tahun=2026&indikator={self.indikator.pk}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertIn('const indData = [90.0, 70.0, null', html)
        self.assertIn('const indTarget = 85.0;', html)
        self.assertIn('const indColors = ["#198754", "#dc3545"', html)

    def test_mutu_dashboard_max_indicator_flips_colors(self):
        """arah_target='MAX' (lower is better) is green when capaian <= target."""
        ind_max = IndikatorMutu.objects.create(
            nama_indikator='Waktu Tunggu IGD', kode_indikator='IMRS-98',
            unit=self.unit, jenis='IMP_RS', dimensi_mutu='EFISIEN',
            numerator='jumlah kasus', denominator='total kasus',
            target_nilai=Decimal('5.00'), satuan='Menit', arah_target='MAX', aktif=True)
        CatatanIndikator.objects.create(
            indikator=ind_max, bulan=1, tahun=2026,
            nilai_numerator=Decimal('4'), nilai_denominator=Decimal('100'))

        url = f'/indikator-mutu/?jenis=IMRS&tahun=2026&indikator={ind_max.pk}'
        self.assertIn('const indColors = ["#198754"', self.client.get(url).content.decode())

        CatatanIndikator.objects.filter(indikator=ind_max, bulan=1, tahun=2026).update(
            nilai_numerator=Decimal('8'))
        self.assertIn('const indColors = ["#dc3545"', self.client.get(url).content.decode())

    def test_mutu_dashboard_unknown_indicator_falls_back(self):
        """A bogus or foreign indikator pk must render 200 in aggregate mode."""
        resp = self.client.get('/indikator-mutu/?jenis=INM&tahun=2026&indikator=999999')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('const hasInd = false;', resp.content.decode())
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: FAIL — `dropdown indikator tidak dirender` and `assertIn('const indData = [90.0, ...')` on a page that has no such markup.

- [x] **Step 3: Implement the backend**

In `akreditasi/indikator_views.py`, inside `indikator_dashboard`, insert this block immediately **before** `ctx = {` (after `chart_jenis_json = _json.dumps(chart_jenis_datasets)` at line 267 — `_json` is already imported at line 223 and `qs` is in scope):

```python
    # ── Grafik per-indikator tunggal (bukan rata-rata semua indikator) ──────
    try:
        indikator_id = int(request.GET.get('indikator') or 0)
    except (ValueError, TypeError):
        indikator_id = 0

    # Dropdown: hanya indikator yang punya catatan di tahun terpilih — indikator
    # tanpa data tidak bisa digrafikkan. Fallback ke semua indikator tier tersebut
    # bila belum ada satu pun yang berdata (mis. IMU), agar dropdown tak pernah kosong.
    data_ind_ids = set(
        CatatanIndikator.objects.filter(tahun=tahun_int, indikator__in=qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    choices_qs = qs.filter(pk__in=data_ind_ids) if data_ind_ids else qs
    indikator_choices = list(choices_qs.order_by('jenis', 'kode_indikator'))
    selected_indikator = next((i for i in indikator_choices if i.pk == indikator_id), None)

    ind_data, ind_colors = [], []
    ind_target, ind_arah = 0.0, 'MIN'
    if selected_indikator:
        ind_target = round(float(selected_indikator.target_nilai), 1)
        ind_arah = getattr(selected_indikator, 'arah_target', 'MIN')
        ind_cat = {
            c.bulan: float(c.nilai_capaian)
            for c in CatatanIndikator.objects.filter(
                indikator=selected_indikator, tahun=tahun_int)
            if 1 <= c.bulan <= 12
        }
        for m in range(1, 13):
            v = ind_cat.get(m)
            ind_data.append(v)
            if v is None:
                ind_colors.append('rgba(203, 213, 225, 0.4)')
            else:
                ok = (v <= ind_target) if ind_arah == 'MAX' else (v >= ind_target)
                ind_colors.append('#198754' if ok else '#dc3545')
```

Then add these keys to the `ctx` dict (after `'chart_jenis_json': chart_jenis_json,`):

```python
        'indikator_choices': indikator_choices,
        'filter_indikator': indikator_id,
        'indikator_terpilih': selected_indikator,
        'has_indikator': bool(selected_indikator),
        'chart_indikator_data_json': _json.dumps(ind_data),
        'chart_indikator_colors_json': _json.dumps(ind_colors),
        'chart_indikator_target_json': _json.dumps(ind_target),
        'chart_indikator_target_line_json': _json.dumps([ind_target] * 12),
        'chart_indikator_satuan': (selected_indikator.satuan if selected_indikator else '%'),
        'chart_indikator_arah': ind_arah,
```

- [x] **Step 4: Run tests to verify the backend half passes**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: the four data assertions pass; `test_mutu_dashboard_dropdown_lists_only_data_bearing_indicators` still FAILS on `dropdown indikator tidak dirender` (template not written yet — Task 2).

- [x] **Step 5: Commit**

```bash
git add akreditasi/indikator_views.py akreditasi/tests_indikator_mutu_charts.py
git commit -m "feat(mutu): per-indicator series context for /indikator-mutu/ charts"
```

---

### Task 2: `/indikator-mutu/` template — dropdown, per-indicator bar chart, value labels

**Files:**
- Modify: `templates/akreditasi/indikator_dashboard.html:235-272` (filter form), `:203-215` (card title), `:471-545` (chart 1 JS)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: every context key produced by Task 1.
- Produces: `<select name="indikator">` markup and the JS constants `hasInd`, `indData`, `indColors`, `indTarget`, `indTargetLine`, `indSatuan`, `indArah` — asserted verbatim by Task 1's tests.

- [x] **Step 1: Add the dropdown to the filter form**

In `templates/akreditasi/indikator_dashboard.html`, insert between the unit select's closing `</div>` (line 260) and the button row (line 262):

```html
        <div class="col-12 col-md-3">
          <label class="form-label small text-muted mb-1">Pilih Indikator Mutu</label>
          <select name="indikator" class="form-select form-select-sm" onchange="this.form.submit()">
            <option value="">Semua Indikator (Rata-rata)</option>
            {% for ind in indikator_choices %}
            <option value="{{ ind.pk }}" {% if filter_indikator == ind.pk %}selected{% endif %}>
              [{{ ind.kode_indikator }}] {{ ind.nama_indikator|truncatechars:40 }}
            </option>
            {% endfor %}
          </select>
        </div>
```

Widen the button row from `col-12 col-md-3` to `col-12 col-md-2` so the four controls fit one line.

- [x] **Step 2: Make the card title follow the selection**

Replace lines 207-209 (the `<span class="fw-bold text-dark" ...>` block) with:

```html
          <span class="fw-bold text-dark" style="font-size:.84rem;">
            {% if indikator_terpilih %}
              Tren [{{ indikator_terpilih.kode_indikator }}] {{ indikator_terpilih.nama_indikator }} ({{ filter_tahun }})
            {% else %}
              Tren Rata-Rata Capaian Indikator Mutu (Tahun {{ filter_tahun }})
            {% endif %}
          </span>
```

- [x] **Step 3: Branch chart 1 on the selection**

In the `{% block extra_js %}` script, replace the constant block at lines 475-477 with:

```javascript
    const labels   = {{ chart_labels|safe }};
    const capaian  = {{ chart_capaian|safe }};
    const jenisDS  = {{ chart_jenis_json|safe }};

    // Per-indikator mode
    const hasInd   = {{ has_indikator|yesno:"true,false" }};
    const indData  = {{ chart_indikator_data_json|safe }};
    const indColors = {{ chart_indikator_colors_json|safe }};
    const indTarget = {{ chart_indikator_target_json|safe }};
    const indTargetLine = {{ chart_indikator_target_line_json|safe }};
    const indSatuan = {{ chart_indikator_satuan|escapejs }};
    const indArah   = {{ chart_indikator_arah|escapejs }};

    // Label nilai di atas setiap bar (inline, tanpa plugin CDN)
    const valueLabelsPlugin = {
        id: 'valueLabels',
        afterDatasetsDraw(chart) {
            const c = chart.ctx;
            c.save();
            chart.data.datasets.forEach((ds, di) => {
                if (ds.type !== 'bar') return;
                chart.getDatasetMeta(di).data.forEach((el, i) => {
                    const v = ds.data[i];
                    if (v === null || v === undefined) return;
                    c.fillStyle = '#334155';
                    c.font = '600 10px Inter, sans-serif';
                    c.textAlign = 'center';
                    c.fillText(v.toFixed(1) + (indSatuan || '%'), el.x, el.y - 4);
                });
            });
            c.restore();
        }
    };
```

Then wrap the existing line chart: change `if (ctx1) {` (line 481) to `if (ctx1 && !hasInd) {`, and immediately before that `if`, insert the per-indicator branch:

```javascript
    if (ctx1 && hasInd) {
        new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        type: 'line',
                        label: `Target ${indTarget} ${indSatuan}`,
                        data: indTargetLine,
                        borderColor: 'rgba(239, 68, 68, 0.75)',
                        borderDash: [6, 3],
                        borderWidth: 1.5,
                        pointRadius: 0,
                        fill: false,
                        order: 1
                    },
                    {
                        type: 'bar',
                        label: `Capaian (${indSatuan})`,
                        data: indData,
                        backgroundColor: indColors,
                        borderRadius: 4,
                        maxBarThickness: 38,
                        order: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 11, family: 'Inter, sans-serif' }, boxWidth: 12 } },
                    tooltip: {
                        callbacks: {
                            label: function(c) {
                                if (c.raw === null) return ' Belum ada data pengukuran';
                                return ` ${c.dataset.label}: ${c.raw.toFixed(1)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: v => v + (indSatuan || '%'), font: { size: 10 } }, grid: { color: 'rgba(0,0,0,0.05)' } },
                    x: { grid: { display: false }, ticks: { font: { size: 10 } } }
                }
            },
            plugins: [valueLabelsPlugin]
        });
    }
```

- [x] **Step 4: Verify the page renders and the inline JS parses**

Run:
```bash
.venv/Scripts/python.exe manage.py shell -c "import re; from django.test import Client; from django.contrib.auth import get_user_model; U=get_user_model(); c=Client(); c.force_login(U.objects.filter(is_superuser=True).first()); h=c.get('/indikator-mutu/?jenis=INM&tahun=2026').content.decode(); s=re.findall(r'<script>(.*?)</script>', h, re.S); open(r'C:/Users/cubeb/AppData/Local/hermes/cache/scratch/mutu_dash.js','w',encoding='utf-8').write(s[-1]); print('EXTRACTED', len(s[-1]))"
node --check C:/Users/cubeb/AppData/Local/hermes/cache/scratch/mutu_dash.js
```
Expected: `EXTRACTED <n>` then no output from `node --check` (exit 0). Any `SyntaxError` means a float or string reached the template unescaped.

- [x] **Step 5: Run the tests**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: PASS (all Task 1 tests now green).

- [x] **Step 6: Commit**

```bash
git add templates/akreditasi/indikator_dashboard.html
git commit -m "feat(mutu): indicator dropdown and per-indicator bar chart on /indikator-mutu/"
```

---

### Task 3: `/` dashboard — repair the category → indicator cascade

**Files:**
- Modify: `akreditasi/views.py:153-158` (`_get_mutu_renstra_charts_context`)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: `IndikatorMutu`, `CatatanIndikator` (imported at `views.py:125`).
- Produces: `mutu_indikator_choices` narrowed to data-bearing indicators; `mutu_jenis` accepts both canonical (`INM`) and legacy (`NASIONAL`) values.

- [x] **Step 1: Write the failing test**

Append to `akreditasi/tests_indikator_mutu_charts.py`:

```python
    def test_dashboard_jenis_canonical_lists_data_bearing_indicators(self):
        """Category INM must resolve to the legacy NASIONAL rows and offer only those with data."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))
        empty = IndikatorMutu.objects.create(
            nama_indikator='Belum Ada Data', kode_indikator='INM-98',
            unit=self.unit, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='a', denominator='b', target_nilai=Decimal('80.00'), aktif=True)

        resp = self.client.get(reverse('akreditasi:dashboard') + '?mutu_jenis=INM&mutu_tahun=2026')
        self.assertEqual(resp.status_code, 200)
        m = re.search(r'<select name="mutu_indikator".*?</select>', resp.content.decode(), re.S)
        self.assertIsNotNone(m)
        opts = re.findall(r'<option value="(\d+)"', m.group(0))
        self.assertIn(str(self.indikator.pk), opts)
        self.assertNotIn(str(empty.pk), opts)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts.IndikatorMutuChartsAndUploadTest.test_dashboard_jenis_canonical_lists_data_bearing_indicators -v1`
Expected: FAIL — `jenis=INM` matches no rows, so the dropdown holds zero options and `assertIn(str(self.indikator.pk), opts)` fails.

- [x] **Step 3: Fix the mapping and narrow the choices**

In `akreditasi/views.py`, replace lines 153-158:

```python
    if mutu_jenis:
        ind_qs = ind_qs.filter(jenis=mutu_jenis)

    # Dropdown choices: every indicator matching the unit+jenis filters
    mutu_indikator_choices = list(ind_qs.order_by('jenis', 'kode_indikator'))
```

with:

```python
    if mutu_jenis:
        # Canonical tier codes (INM/IMRS/IMU) must reach the legacy rows the DB actually stores
        _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
        ind_qs = ind_qs.filter(jenis__in=_JENIS_MAP.get(mutu_jenis, [mutu_jenis]))

    # Dropdown choices: indicators that actually have measurements this year — an
    # indicator without data cannot be charted. Fallback to every active indicator
    # in the filter when the year holds no data at all, so the dropdown is never empty.
    _data_ids = set(
        CatatanIndikator.objects.filter(tahun=mutu_tahun, indikator__in=ind_qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    _choices_qs = ind_qs.filter(pk__in=_data_ids) if _data_ids else ind_qs
    mutu_indikator_choices = list(_choices_qs.order_by('jenis', 'kode_indikator'))
```

- [x] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: PASS — including the pre-existing `test_dashboard_single_indicator_selection_and_colors`, `test_dashboard_arah_target_max_flips_bar_colors`, `test_dashboard_filtered_by_category_and_unit` and `test_dashboard_unknown_indikator_param_falls_back`, whose indicators all carry catatan.

- [x] **Step 5: Commit**

```bash
git add akreditasi/views.py akreditasi/tests_indikator_mutu_charts.py
git commit -m "fix(dashboard): map canonical tier codes to legacy jenis rows and list only data-bearing indicators"
```

---

### Task 4: End-to-end verification

**Files:**
- No source changes; verification only.

- [x] **Step 1: Confirm the 13 INM choices against real data**

Run:
```bash
.venv/Scripts/python.exe manage.py shell -c "
import re
from django.test import Client
from django.contrib.auth import get_user_model
c = Client(); c.force_login(get_user_model().objects.filter(is_superuser=True).first())
for url in ['/indikator-mutu/?jenis=INM&tahun=2026', '/?mutu_jenis=INM&mutu_tahun=2026']:
    h = c.get(url).content.decode()
    name = 'indikator' if url.startswith('/indikator-mutu') else 'mutu_indikator'
    m = re.search(r'<select name=\"%s\".*?</select>' % name, h, re.S)
    opts = re.findall(r'<option value=\"(\d+)\"', m.group(0)) if m else []
    print(url, '->', len(opts), 'pilihan indikator')
"
```
Expected: both lines print `13`.

- [x] **Step 2: Confirm the aggregate chart is untouched**

Run: `.venv/Scripts/python.exe manage.py shell -c "import re; from django.test import Client; from django.contrib.auth import get_user_model; c=Client(); c.force_login(get_user_model().objects.filter(is_superuser=True).first()); h=c.get('/indikator-mutu/?tahun=2026').content.decode(); print(re.search(r'const capaian\s*=\s*(\[[^\]]*\])', h).group(1))"`
Expected: `[57.6, 59.5, 59.8, 60.6, 62.6, 61.4, 62.4, 56.9, 61.9, 61.9, 62.9, 63.2]` — byte-identical to the pre-change baseline.

- [x] **Step 3: Run the full suite**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts akreditasi.tests_evaluasi_indikator akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1 && .venv/Scripts/python.exe manage.py check`
Expected: 86/86 OK (81 baseline + 5 new), `check` reports 0 issues. The known pre-existing failure `tests_ai.EndpointAIIntegrationTest.test_anon_user_redirected` is outside this suite and stays unfixed.

- [x] **Step 4: Confirm query count stays sane**

Run: `.venv/Scripts/python.exe manage.py shell -c "from django.test import Client; from django.test.utils import CaptureQueriesContext; from django.db import connection; from django.contrib.auth import get_user_model; c=Client(); c.force_login(get_user_model().objects.filter(is_superuser=True).first()); [print(u, len(CaptureQueriesContext(connection, lambda: c.get(u)).captured_queries) if False else '') for u in []]"` — instead use the existing probe:
```bash
.venv/Scripts/python.exe manage.py shell -c "exec(open(r'C:/Users/cubeb/AppData/Local/hermes/cache/scratch/prof_pages.py', encoding='utf-8').read())"
```
Expected: `/indikator-mutu/` stays at or below ~35 queries (baseline 30 warm / 32 cold) — the two extra aggregates (data-bearing ids, per-indicator catatan) must not reintroduce N+1.

- [x] **Step 5: Commit the verification note and push**

```bash
git add -A
git commit -m "docs: record per-indicator chart verification" --allow-empty
git push origin master
```
