# Quality Indicator Dashboard Charts Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard quality-indicator charts analysable per single indicator: dropdown indicator filter, per-bar colour coding against the correct target, data labels, a multi-year trend tab, a monthly×yearly recap matrix, and click-to-PDCA drill-down from a bar into the risk form.

**Architecture:** All chart data stays server-computed in `_get_mutu_renstra_charts_context` (views.py) and is injected into `dashboard.html` as JSON — no new API endpoint, no new dependency. New filter (`mutu_indikator`) rides the existing GET form. Two new tabs (Tren Tahunan, Matriks Rekap) join the existing pills. Drill-down uses a Bootstrap modal (bundle already loaded in `base.html`) whose button links to `risiko_input` with `?indikator=&bulan=&tahun=`, and `risiko_input` pre-fills the risk form from those query params.

**Tech Stack:** Django 4.x templates + Chart.js (CDN, already loaded) + Bootstrap 5.3 bundle (already loaded). No new pip packages, no new CDN scripts, no migrations.

**Spec:** `C:\Users\cubeb\Downloads\Lakukan perubahan pada grafik indicator mutu dibawah ini.docx`

## Global Constraints

- No new pip dependency, no new CDN script; a small inline Chart.js plugin draws the value labels (`chartjs-plugin-datalabels` is NOT added).
- All JSON injected with `|safe` must come from `json.dumps` of server-computed numbers/strings; never inject user text into JS strings without `escapejs`.
- Keep existing element IDs and dataset labels (`chartMutuBulanan`, `chartRenstraTahunan`, `pills-bulanan-tab`, `pills-renstra-tab`, `Batas Target`, `Realisasi Capaian (%)`, `Target Renstra (%)`) — `akreditasi/tests_indikator_mutu_charts.py` asserts them.
- Colour contract: `#198754` = tercapai, `#dc3545` = di bawah target, `rgba(203, 213, 225, 0.4)` = belum ada data. `arah_target='MAX'` (lower is better) flips the comparison.
- Plans/docs in English; user-facing UI copy in Bahasa Indonesia.
- Test command: `python manage.py test akreditasi.tests_indikator_mutu_charts akreditasi.tests_evaluasi_indikator akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1`
- Work on `master`; commit after each task.

## Review Focus

- Indicator with `arah_target='MAX'` (e.g. waktu tanggap, lower is better): bar/label/matrix must flip — `capaian ≤ target` is green. The old average-mode code used `val >= target` unconditionally, so this is the most likely silent regression.
- `mutu_indikator` id that does not exist, or belongs to a unit/jenis filtered out by the other GET params: request must render 200 and fall back to the aggregate view (never 500, never empty chart).
- Indicator/year with zero `CatatanIndikator` rows, or a row with `nilai_denominator=0`: bars stay grey/`null`, data labels and matrix cells skip the month, no `NaN%` in the UI.
- Bar click when no single indicator is selected: the modal must still open but hide the PDCA button and show the "pick a specific indicator" hint — the drill-down URL needs an indicator id.
- `risiko_input` opened with prefill params by a unit-scoped user whose unit differs from the indicator's unit: the unit `<option>` may not exist in their queryset — prefill must degrade silently, not throw.

---

### Task 1: Backend — single-indicator selection, target-aware colours, multi-year series, recap matrix

**Files:**
- Modify: `akreditasi/views.py:121-225` (`_get_mutu_renstra_charts_context`)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: `IndikatorMutu` (fields `pk`, `kode_indikator`, `nama_indikator`, `jenis`, `target_nilai`, `arah_target`), `CatatanIndikator` (fields `indikator`, `bulan`, `tahun`, `nilai_numerator`, `nilai_denominator`).
- Produces (context keys consumed by Tasks 2–3):
  - `mutu_indikator_choices`: `list[IndikatorMutu]`
  - `filter_mutu_indikator`: `int` (0 = all)
  - `mutu_indikator_terpilih`: `IndikatorMutu | None`
  - `mutu_arah_target`: `str` (`'MIN'`/`'MAX'`)
  - `bulan_labels`: `list[str]` (12 short month names)
  - `chart_mutu_target_val`: `float`, `chart_mutu_target_val_json`, `chart_mutu_target_line_json`
  - `chart_mutu_labels_json`, `chart_mutu_data_json`, `chart_mutu_colors_json`
  - `chart_tahunan_years_json`: `list[int]` (current year − 4 … current year)
  - `chart_tahunan_data_json`: `list[float | None]`
  - `chart_tahunan_colors_json`: `list[str]`
  - `matrix_rows`: `list[{year: int, months: [{val: float|None, ok: bool|None} ×12], avg: float|None}]`, newest year first

- [ ] **Step 1: Write the failing tests**

Append to `akreditasi/tests_indikator_mutu_charts.py` inside class `IndikatorMutuChartsAndUploadTest`:

```python
    def test_dashboard_single_indicator_selection_and_colors(self):
        """Selecting one indicator charts its own monthly trend, target line and per-bar colours."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=2026,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'))
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=2026,
            nilai_numerator=Decimal('70'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={self.indikator.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()

        # Data of the single indicator: Jan=90.0, Feb=70.0 (target 85.00)
        self.assertIn('[90.0, 70.0', content)
        # Target line uses the indicator's own target, not the average of all
        self.assertIn('85.0', content)
        # Jan green, Feb red, remaining months grey
        self.assertIn('["#198754", "#dc3545"', content)

    def test_dashboard_arah_target_max_flips_bar_colors(self):
        """MAX indicators (lower is better) turn green when capaian <= target."""
        ind_max = IndikatorMutu.objects.create(
            nama_indikator='Waktu Tanggap Pelayanan IGD', kode_indikator='IMRS-99',
            unit=self.unit, jenis='IMRS', dimensi_mutu='EFISIEN',
            numerator='Jumlah kasus <= 5 menit', denominator='Total kasus',
            target_nilai=Decimal('5.00'), satuan='Menit', arah_target='MAX', aktif=True)
        CatatanIndikator.objects.create(
            indikator=ind_max, bulan=1, tahun=2026,
            nilai_numerator=Decimal('4'), nilai_denominator=Decimal('100'))  # 4% <= 5% -> green

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={ind_max.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('["#198754"', resp.content.decode())

        CatatanIndikator.objects.filter(indikator=ind_max, bulan=1, tahun=2026).update(
            nilai_numerator=Decimal('8'))  # 8% > 5% -> red
        resp = self.client.get(url)
        self.assertIn('["#dc3545"', resp.content.decode())

    def test_dashboard_multi_year_trend_and_matrix_tab(self):
        """Yearly trend JSON spans current year - 4, and matrix table renders."""
        for yr in (2024, 2025, 2026):
            CatatanIndikator.objects.create(
                indikator=self.indikator, bulan=1, tahun=yr,
                nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:dashboard') + f'?mutu_indikator={self.indikator.pk}&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()

        self.assertContains(resp, 'pills-tahunan-tab')
        self.assertContains(resp, 'pills-matriks-tab')
        self.assertContains(resp, 'chartTahunanMulti')
        self.assertContains(resp, 'tabelMatriksRekap')
        self.assertIn('[2022, 2023, 2024, 2025, 2026]', content)

    def test_dashboard_unknown_indikator_param_falls_back(self):
        """A bogus mutu_indikator id must not crash and must fall back to aggregate mode."""
        url = reverse('akreditasi:dashboard') + '?mutu_indikator=999999&mutu_tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chartMutuBulanan')

    def test_dashboard_chart_datalabels_and_drilldown_modal_markup(self):
        """Value-label plugin and the drill-down modal are rendered."""
        resp = self.client.get(reverse('akreditasi:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'modalDrilldownMutu')
        self.assertContains(resp, 'afterDatasetsDraw')
        self.assertContains(resp, 'dd-btn-pdca')
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: FAIL — `mutu_indikator` is ignored (average colours still used), no `chart_tahunan_*`, no `tabelMatriksRekap`, no modal.

- [ ] **Step 3: Replace `_get_mutu_renstra_charts_context`**

Replace the whole function at `akreditasi/views.py:121-225` with:

```python
def _get_mutu_renstra_charts_context(request, profile, db_roadmaps, renstra_years):
    """Aggregate monthly indicators (Jan-Dec), multi-year trend, recap matrix
    and 5-year Renstra data for Dashboard charts."""
    import json as _json
    from .risiko_models import IndikatorMutu, CatatanIndikator
    from .models import UnitKerja

    def _tercapai(val, target, arah):
        # MAX = lower is better (e.g. waktu tunggu); MIN = higher is better
        return val <= target if arah == 'MAX' else val >= target

    mutu_jenis = request.GET.get('mutu_jenis', '')
    mutu_unit = request.GET.get('mutu_unit', '')
    try:
        mutu_tahun = int(request.GET.get('mutu_tahun', '2026'))
    except (ValueError, TypeError):
        mutu_tahun = 2026
    try:
        mutu_indikator_id = int(request.GET.get('mutu_indikator') or 0)
    except (ValueError, TypeError):
        mutu_indikator_id = 0

    ind_qs = IndikatorMutu.objects.filter(aktif=True)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        user_unit_ids = list(UnitKerja.objects.filter(
            Q(pk=user_unit.pk) | Q(parent=user_unit) | Q(parent__parent=user_unit)
        ).values_list('pk', flat=True))
        ind_qs = ind_qs.filter(Q(unit_id__in=user_unit_ids) | Q(jenis='NASIONAL'))
    elif mutu_unit:
        ind_qs = ind_qs.filter(unit_id=mutu_unit)

    if mutu_jenis:
        ind_qs = ind_qs.filter(jenis=mutu_jenis)

    # Dropdown choices: every indicator matching the unit+jenis filters
    mutu_indikator_choices = list(ind_qs.order_by('jenis', 'kode_indikator'))
    selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)

    chart_qs = IndikatorMutu.objects.filter(pk=selected_indikator.pk) if selected_indikator else ind_qs
    filtered_ind_ids = list(chart_qs.values_list('id', flat=True))

    if selected_indikator:
        chart_target_val = round(float(selected_indikator.target_nilai), 1)
        arah_target = getattr(selected_indikator, 'arah_target', 'MIN')
    else:
        avg_target_raw = chart_qs.aggregate(avg=Avg('target_nilai'))['avg']
        chart_target_val = round(float(avg_target_raw), 1) if avg_target_raw else 80.0
        arah_target = 'MIN'

    BULAN_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

    # 1. Monthly combo chart (Jan - Des) for the selected filter set
    month_data_map = {}
    monthly_cat = CatatanIndikator.objects.filter(
        indikator_id__in=filtered_ind_ids, tahun=mutu_tahun
    ).values('bulan').annotate(
        sum_num=Sum('nilai_numerator'),
        sum_den=Sum('nilai_denominator')
    )
    for c in monthly_cat:
        if c['sum_den'] and c['sum_den'] > 0:
            month_data_map[c['bulan']] = round(float((c['sum_num'] / c['sum_den']) * 100), 1)

    chart_mutu_bulanan_data = []
    chart_mutu_colors = []
    has_monthly_data = False
    for m in range(1, 13):
        val = month_data_map.get(m)
        chart_mutu_bulanan_data.append(val)
        if val is None:
            chart_mutu_colors.append('rgba(203, 213, 225, 0.4)')
        else:
            has_monthly_data = True
            chart_mutu_colors.append('#198754' if _tercapai(val, chart_target_val, arah_target) else '#dc3545')

    # 2. Multi-year trend + recap matrix: current year and the 4 before it
    trend_years = list(range(mutu_tahun - 4, mutu_tahun + 1))
    yearly_map = {}
    matrix_map = {}
    yearly_rows = CatatanIndikator.objects.filter(
        indikator_id__in=filtered_ind_ids, tahun__in=trend_years
    ).values('tahun', 'bulan').annotate(
        sum_num=Sum('nilai_numerator'),
        sum_den=Sum('nilai_denominator')
    )
    for r in yearly_rows:
        if not (r['sum_den'] and r['sum_den'] > 0):
            continue
        pct = round(float((r['sum_num'] / r['sum_den']) * 100), 1)
        matrix_map[(r['tahun'], r['bulan'])] = pct
        yearly_map.setdefault(r['tahun'], []).append(pct)

    chart_tahunan_data = []
    chart_tahunan_colors = []
    for y in trend_years:
        vals = yearly_map.get(y, [])
        if vals:
            avg_y = round(sum(vals) / len(vals), 1)
            chart_tahunan_data.append(avg_y)
            chart_tahunan_colors.append('#198754' if _tercapai(avg_y, chart_target_val, arah_target) else '#dc3545')
        else:
            chart_tahunan_data.append(None)
            chart_tahunan_colors.append('rgba(203, 213, 225, 0.4)')

    matrix_rows = []
    for y in reversed(trend_years):
        cells = []
        for m in range(1, 13):
            v = matrix_map.get((y, m))
            cells.append({'val': v, 'ok': (None if v is None else _tercapai(v, chart_target_val, arah_target))})
        vals = [c['val'] for c in cells if c['val'] is not None]
        matrix_rows.append({
            'year': y,
            'months': cells,
            'avg': round(sum(vals) / len(vals), 1) if vals else None,
        })

    # 3. Renstra multi-year target vs realization (2026 - 2030)
    renstra_years_list = [2026, 2027, 2028, 2029, 2030]
    renstra_targets_map = {2026: 75.0, 2027: 80.0, 2028: 85.0, 2029: 90.0, 2030: 95.0}
    for rm in db_roadmaps:
        if rm.tahun in renstra_targets_map and getattr(rm, 'target_persen', None):
            renstra_targets_map[rm.tahun] = float(rm.target_persen)

    renstra_targets_series = [renstra_targets_map[yr] for yr in renstra_years_list]
    renstra_actual_series = []
    for yr in renstra_years_list:
        yr_stat = next((y for y in renstra_years if y['year'] == yr), None)
        if yr_stat and yr_stat['has_data']:
            renstra_actual_series.append(yr_stat['avg_capaian'])
        else:
            renstra_actual_series.append(None)

    current_year_stat = next((y for y in renstra_years if y['year'] == mutu_tahun), None)
    kpi_mutu_avg = current_year_stat['avg_capaian'] if current_year_stat else 0.0
    kpi_mutu_tercapai = current_year_stat['tercapai'] if current_year_stat else 0
    kpi_mutu_total = current_year_stat['total_catatan'] if current_year_stat else 0

    return {
        'filter_mutu_jenis': mutu_jenis,
        'filter_mutu_unit': mutu_unit,
        'filter_mutu_tahun': mutu_tahun,
        'filter_mutu_indikator': mutu_indikator_id,
        'mutu_tahun_choices': renstra_years_list,
        'mutu_jenis_choices': IndikatorMutu.JENIS_CHOICES,
        'mutu_units_choices': UnitKerja.objects.filter(is_active=True).order_by('code'),
        'mutu_indikator_choices': mutu_indikator_choices,
        'mutu_indikator_terpilih': selected_indikator,
        'mutu_arah_target': arah_target,
        'bulan_labels': BULAN_SHORT,
        'chart_mutu_labels_json': _json.dumps(BULAN_SHORT),
        'chart_mutu_data_json': _json.dumps(chart_mutu_bulanan_data),
        'chart_mutu_colors_json': _json.dumps(chart_mutu_colors),
        'chart_mutu_target_val': chart_target_val,
        'chart_mutu_target_val_json': _json.dumps(chart_target_val),
        'chart_mutu_target_line_json': _json.dumps([chart_target_val] * 12),
        'has_monthly_data': has_monthly_data,
        'chart_tahunan_years_json': _json.dumps(trend_years),
        'chart_tahunan_data_json': _json.dumps(chart_tahunan_data),
        'chart_tahunan_colors_json': _json.dumps(chart_tahunan_colors),
        'matrix_rows': matrix_rows,
        'chart_renstra_years_json': _json.dumps(renstra_years_list),
        'chart_renstra_targets_json': _json.dumps(renstra_targets_series),
        'chart_renstra_actuals_json': _json.dumps(renstra_actual_series),
        'kpi_mutu_avg': kpi_mutu_avg,
        'kpi_mutu_tercapai': kpi_mutu_tercapai,
        'kpi_mutu_total': kpi_mutu_total,
    }
```

- [ ] **Step 4: Run the backend tests**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: the 3 backend tests of this task PASS; the two template tests (`multi_year_trend_and_matrix_tab`, `datalabels_and_drilldown_modal_markup`) still FAIL (templates not touched yet). That is expected — Task 2 and 3 close them.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/views.py akreditasi/tests_indikator_mutu_charts.py
git commit -m "feat(dashboard): per-indicator chart context with target-aware colors, multi-year series and recap matrix"
```

---

### Task 2: Dashboard filter dropdown + two new tabs + recap matrix table

**Files:**
- Modify: `templates/akreditasi/dashboard.html:454-490` (filter toolbar), `:438-538` (tab nav + panes)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: `mutu_indikator_choices`, `filter_mutu_indikator`, `mutu_indikator_terpilih`, `bulan_labels`, `matrix_rows`, `chart_mutu_target_val` (Task 1).
- Produces: element ids `pills-tahunan-tab`, `pills-tahunan`, `pills-matriks-tab`, `pills-matriks`, `tabelMatriksRekap`, `chartTahunanMulti` (Task 3 binds to them).

- [ ] **Step 1: Add the indicator dropdown to the GET filter form**

In `templates/akreditasi/dashboard.html`, inside the filter `<form method="GET">` (starts line 454), change the Kategori column to `col-12 col-md-3` (already 3), change the Unit column wrapper from `col-12 col-md-4` to `col-12 col-md-3`, and insert this block immediately after the Unit column's `{% endif %}`:

```html
                <div class="col-12 col-md-3">
                    <label class="form-label mb-0 small text-muted fw-semibold">Indikator Mutu</label>
                    <select name="mutu_indikator" class="form-select form-select-sm" onchange="this.form.submit()">
                        <option value="">Semua Indikator (Rata-rata)</option>
                        {% for ind in mutu_indikator_choices %}
                        <option value="{{ ind.pk }}" {% if filter_mutu_indikator == ind.pk %}selected{% endif %}>
                            [{{ ind.kode_indikator }}] {{ ind.nama_indikator|truncatechars:42 }}
                        </option>
                        {% endfor %}
                    </select>
                </div>
```

Then change the Tahun column wrapper from `col-12 col-md-3` to `col-12 col-md-2` and the button column from `col-12 col-md-2` to `col-12 col-md-1`, with the button becoming icon-only:

```html
                <div class="col-12 col-md-1 d-flex align-items-end">
                    <a href="{% url 'akreditasi:indikator_dashboard' %}?tahun={{ filter_mutu_tahun }}"
                       class="btn btn-sm btn-outline-primary w-100 px-1" title="Input &amp; Detail Indikator">
                        <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                </div>
```

- [ ] **Step 2: Update the monthly tab subtitle for single-indicator mode**

Replace the `<span class="small text-muted">…</span>` inside `#pills-bulanan` (lines 498-501) with:

```html
                            <span class="small text-muted">
                                {% if mutu_indikator_terpilih %}
                                Tren capaian <strong class="font-monospace">[{{ mutu_indikator_terpilih.kode_indikator }}]</strong>
                                {{ mutu_indikator_terpilih.nama_indikator }} per bulan vs garis target
                                <strong class="text-danger font-monospace">({{ mutu_indikator_terpilih.arah_target }}{{ chart_mutu_target_val }}%)</strong>.
                                {% else %}
                                Realisasi rata-rata per bulan vs garis target standar minimal
                                <strong class="text-danger font-monospace">({{ chart_mutu_target_val }}%)</strong>.
                                {% endif %}
                            </span>
```

- [ ] **Step 3: Add the two new tab buttons**

Inside `<ul class="nav nav-pills" id="pills-mutu-tab">`, after the `pills-renstra-tab` `<li>` (line 444-448), append:

```html
                <li class="nav-item" role="presentation">
                    <button class="nav-link py-1.5 px-3 rounded-pill fw-semibold small" id="pills-tahunan-tab" data-bs-toggle="pill" data-bs-target="#pills-tahunan" type="button" role="tab">
                        <i class="bi bi-calendar-range me-1"></i>Tren Tahunan
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link py-1.5 px-3 rounded-pill fw-semibold small" id="pills-matriks-tab" data-bs-toggle="pill" data-bs-target="#pills-matriks" type="button" role="tab">
                        <i class="bi bi-table me-1"></i>Matriks Rekap
                    </button>
                </li>
```

- [ ] **Step 4: Add the two new tab panes**

Inside `<div class="tab-content" id="pills-mutu-tabContent">`, after the `#pills-renstra` pane's closing `</div>` (line 537), append:

```html
                <!-- TAB 3: MULTI-YEAR TREND -->
                <div class="tab-pane fade" id="pills-tahunan" role="tabpanel">
                    <div class="row align-items-center mb-2 px-2">
                        <div class="col-12 col-md-7">
                            <span class="small text-muted">
                                Rata-rata capaian tahunan
                                {% if mutu_indikator_terpilih %}[{{ mutu_indikator_terpilih.kode_indikator }}] {{ mutu_indikator_terpilih.nama_indikator }}{% else %}(semua indikator terfilter){% endif %}
                                — tahun berjalan dan 4 tahun sebelumnya.
                            </span>
                        </div>
                        <div class="col-12 col-md-5 text-md-end">
                            <span class="badge bg-success-subtle text-success border border-success-subtle me-1" style="font-size:0.7rem;">
                                <i class="bi bi-square-fill me-1"></i>Tercapai
                            </span>
                            <span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:0.7rem;">
                                <i class="bi bi-square-fill me-1"></i>Di bawah Target
                            </span>
                        </div>
                    </div>
                    <div style="position: relative; height: 260px; width: 100%;">
                        <canvas id="chartTahunanMulti"></canvas>
                    </div>
                </div>

                <!-- TAB 4: MONTHLY x YEARLY RECAP MATRIX -->
                <div class="tab-pane fade" id="pills-matriks" role="tabpanel">
                    <div class="px-2 mb-2">
                        <span class="small text-muted">
                            Matriks capaian per bulan × tahun ({{ bulan_labels|length }} bulan) untuk filter aktif.
                            Warna hijau = tercapai, merah = di bawah target ({{ chart_mutu_target_val }}%).
                        </span>
                    </div>
                    <div class="table-responsive" style="max-height: 320px;">
                        <table class="table table-sm table-bordered align-middle mb-0" id="tabelMatriksRekap" style="font-size:0.78rem;">
                            <thead class="table-light sticky-top">
                                <tr>
                                    <th class="text-center" style="min-width:64px;">Tahun</th>
                                    {% for bln in bulan_labels %}
                                    <th class="text-center">{{ bln }}</th>
                                    {% endfor %}
                                    <th class="text-center bg-light">Rata²</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for row in matrix_rows %}
                                <tr>
                                    <th class="text-center font-monospace">{{ row.year }}</th>
                                    {% for c in row.months %}
                                    <td class="text-center font-monospace {% if c.val is None %}text-muted{% elif c.ok %}text-success{% else %}text-danger fw-semibold{% endif %}">
                                        {% if c.val is None %}–{% else %}{{ c.val }}{% endif %}
                                    </td>
                                    {% endfor %}
                                    <td class="text-center font-monospace fw-bold bg-light">
                                        {% if row.avg is None %}–{% else %}{{ row.avg }}%{% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
```

- [ ] **Step 5: Run the tests**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: `test_dashboard_multi_year_trend_and_matrix_tab` PASSES. `test_dashboard_chart_datalabels_and_drilldown_modal_markup` still FAILS (Task 3).

- [ ] **Step 6: Commit**

```bash
git add templates/akreditasi/dashboard.html
git commit -m "feat(dashboard): add indicator filter dropdown, multi-year trend tab and recap matrix tab"
```

---

### Task 3: Chart JS — value labels plugin, multi-year chart, click-to-PDCA modal

**Files:**
- Modify: `templates/akreditasi/dashboard.html` (body: modal markup before `{% block extra_js %}`; JS block lines 856-1013)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: `chart_mutu_*_json`, `chart_tahunan_*_json`, `filter_mutu_indikator`, `mutu_indikator_terpilih`, `mutu_arah_target`, `filter_mutu_tahun` (Task 1); element ids from Task 2; URL name `akreditasi:risiko_input`.
- Produces: JS functions `openDrilldown(idx, val)`; modal ids `modalDrilldownMutu`, `dd-bulan-label`, `dd-indikator-nama`, `dd-nilai`, `dd-status`, `dd-target`, `dd-gap`, `dd-hint-null`, `dd-btn-pdca`.

- [ ] **Step 1: Add the drill-down modal markup**

Immediately before `{% block extra_js %}` (line 816) in `templates/akreditasi/dashboard.html`, insert:

```html
<!-- DRILL-DOWN MODAL: bulan → Analisis Masalah & Form PDCA -->
<div class="modal fade" id="modalDrilldownMutu" tabindex="-1" aria-labelledby="dd-modal-title" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header py-2">
                <h6 class="modal-title fw-bold" id="dd-modal-title">
                    <i class="bi bi-graph-up-arrow text-primary me-1"></i>Detail Capaian <span id="dd-bulan-label"></span>
                </h6>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Tutup"></button>
            </div>
            <div class="modal-body">
                <div id="dd-indikator-nama" class="small text-muted mb-2"></div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="fw-bold fs-4 font-monospace" id="dd-nilai"></span>
                    <span class="badge" id="dd-status"></span>
                </div>
                <div class="small text-muted mb-3">
                    Target: <strong id="dd-target"></strong>% &middot; Selisih: <strong id="dd-gap"></strong>
                </div>
                <div class="alert alert-warning py-2 small mb-2 d-none" id="dd-hint-null">
                    Pilih satu indikator spesifik pada filter di atas untuk membuka Analisis Masalah &amp; Form PDCA.
                </div>
                <a href="#" id="dd-btn-pdca" class="btn btn-sm btn-danger w-100 d-none">
                    <i class="bi bi-clipboard2-pulse me-1"></i>Buka Analisis Masalah &amp; Form PDCA
                </a>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Add the value-labels plugin and drill-down JS**

At the top of the `DOMContentLoaded` callback (line 819, right after `document.addEventListener('DOMContentLoaded', function() {`), insert:

```js
    // ── Shared chart helpers: value labels + drill-down ──────────────────
    const MUTU_IND_ID   = "{{ filter_mutu_indikator|default:'' }}";
    const MUTU_IND_NAMA = "{{ mutu_indikator_terpilih.nama_indikator|escapejs|default:'' }}";
    const MUTU_IND_KODE = "{{ mutu_indikator_terpilih.kode_indikator|escapejs|default:'' }}";
    const MUTU_TAHUN    = {{ filter_mutu_tahun }};
    const MUTU_ARAH     = "{{ mutu_arah_target }}";
    const MUTU_TARGET   = {{ chart_mutu_target_val_json|safe }};
    const PDCA_URL_BASE = "{% url 'akreditasi:risiko_input' %}";
    const NAMA_BULAN = ['Januari','Februari','Maret','April','Mei','Juni',
                        'Juli','Agustus','September','Oktober','November','Desember'];

    // Inline plugin: draws "74.2%" above every non-null bar (dataset index 1)
    const valueLabelsPlugin = {
        id: 'valueLabels',
        afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            const meta = chart.getDatasetMeta(1);
            const data = chart.data.datasets[1].data;
            ctx.save();
            ctx.font = "600 10px 'JetBrains Mono', monospace";
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            meta.data.forEach(function (bar, i) {
                const v = data[i];
                if (v === null || v === undefined) return;
                ctx.fillStyle = '#334155';
                ctx.fillText(v.toFixed(1) + '%', bar.x, bar.y - 3);
            });
            ctx.restore();
        }
    };

    function openDrilldown(idx, val) {
        const modalEl = document.getElementById('modalDrilldownMutu');
        if (!modalEl) return;
        const below = (MUTU_ARAH === 'MAX') ? (val > MUTU_TARGET) : (val < MUTU_TARGET);
        document.getElementById('dd-bulan-label').textContent = NAMA_BULAN[idx] + ' ' + MUTU_TAHUN;
        document.getElementById('dd-indikator-nama').textContent = MUTU_IND_ID
            ? '[' + MUTU_IND_KODE + '] ' + MUTU_IND_NAMA
            : 'Rata-rata semua indikator terfilter';
        document.getElementById('dd-nilai').textContent = val.toFixed(1) + '%';
        document.getElementById('dd-target').textContent = MUTU_TARGET;
        const gap = val - MUTU_TARGET;
        document.getElementById('dd-gap').textContent = (gap >= 0 ? '+' : '') + gap.toFixed(1) + '%';
        const st = document.getElementById('dd-status');
        st.textContent = below ? 'Di bawah Target' : 'Tercapai';
        st.className = 'badge ' + (below
            ? 'bg-danger-subtle text-danger border border-danger-subtle'
            : 'bg-success-subtle text-success border border-success-subtle');
        const btn = document.getElementById('dd-btn-pdca');
        const hint = document.getElementById('dd-hint-null');
        if (MUTU_IND_ID) {
            btn.href = PDCA_URL_BASE + '?indikator=' + MUTU_IND_ID +
                       '&bulan=' + (idx + 1) + '&tahun=' + MUTU_TAHUN;
            btn.classList.remove('d-none');
            hint.classList.add('d-none');
        } else {
            btn.classList.add('d-none');
            hint.classList.remove('d-none');
        }
        new bootstrap.Modal(modalEl).show();
    }
```

- [ ] **Step 3: Wire the plugin + click handler into the monthly chart**

In the monthly chart config (lines 867-934): add `plugins: [valueLabelsPlugin],` as a sibling of `type: 'bar',`, and add this to `options` (after `interaction:`):

```js
                onClick: function (evt, elements) {
                    if (!elements.length) return;
                    const el = elements[0];
                    if (el.datasetIndex !== 1) return;
                    const val = mutuData[el.index];
                    if (val === null || val === undefined) return;
                    openDrilldown(el.index, val);
                },
```

Also change the bar dataset's cursor hint by adding `onHover: function (evt, elements) { evt.native.target.style.cursor = elements.length ? 'pointer' : 'default'; }` to `options` (same level as `onClick`).

- [ ] **Step 4: Add the multi-year trend chart**

After the monthly chart block (after the `if (mutuEl) { … }` closing brace at line 935), insert:

```js
    // 2b. Chart Tren Tahunan (Multi-Year Bar + Target Line)
    let chartTahunan = null;
    const tahunanEl = document.getElementById('chartTahunanMulti');
    if (tahunanEl) {
        const thYears  = {{ chart_tahunan_years_json|safe }};
        const thData   = {{ chart_tahunan_data_json|safe }};
        const thColors = {{ chart_tahunan_colors_json|safe }};

        chartTahunan = new Chart(tahunanEl.getContext('2d'), {
            type: 'bar',
            plugins: [valueLabelsPlugin],
            data: {
                labels: thYears.map(y => `Tahun ${y}`),
                datasets: [
                    {
                        type: 'line',
                        label: `Batas Target (${MUTU_TARGET}%)`,
                        data: thYears.map(() => MUTU_TARGET),
                        borderColor: '#dc3545',
                        borderWidth: 2,
                        borderDash: [6, 4],
                        pointRadius: 0,
                        fill: false,
                        order: 1
                    },
                    {
                        type: 'bar',
                        label: 'Rata-rata Capaian Tahunan (%)',
                        data: thData,
                        backgroundColor: thColors,
                        borderRadius: 5,
                        maxBarThickness: 46,
                        order: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { boxWidth: 14, usePointStyle: true,
                                  font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                if (ctx.raw === null || ctx.raw === undefined) {
                                    return `${ctx.dataset.label}: Belum ada data`;
                                }
                                return `${ctx.dataset.label}: ${ctx.raw}%`;
                            }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, max: 105, ticks: { stepSize: 20, callback: v => v + '%' },
                         grid: { color: 'rgba(226, 232, 240, 0.7)' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }
```

- [ ] **Step 5: Include the new chart in the resize listener**

Replace the resize block (lines 1008-1013) with:

```js
    document.querySelectorAll('#pills-mutu-tab button[data-bs-toggle="pill"]').forEach(function(pill) {
        pill.addEventListener('shown.bs.tab', function() {
            if (chartMutu) chartMutu.resize();
            if (chartRenstra) chartRenstra.resize();
            if (chartTahunan) chartTahunan.resize();
        });
    });
```

- [ ] **Step 6: Run the tests**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: all 8 tests in the file PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/akreditasi/dashboard.html
git commit -m "feat(dashboard): bar value labels, multi-year trend chart and click-to-PDCA drill-down modal"
```

---

### Task 4: Pre-fill `risiko_input` from the drill-down link

**Files:**
- Modify: `akreditasi/risiko_views.py:14` (imports), `:441-452` (context of `risiko_input`)
- Modify: `templates/akreditasi/risiko_form.html:689-750` (indicator loader + init)
- Test: `akreditasi/tests_indikator_mutu_charts.py`

**Interfaces:**
- Consumes: query params `indikator`, `bulan`, `tahun` (produced by Task 3's `dd-btn-pdca` href).
- Produces: context keys `prefill_indikator_id` (int), `prefill_unit_id` (int|None), `prefill_bulan` (int), `prefill_tahun` (int), `prefill_target` (float), `prefill_masalah` (str) — all absent when params are missing/invalid. JS global `window._pendingIndikatorId` consumed inside `loadIndikatorByUnit`.

- [ ] **Step 1: Write the failing test**

Append to `akreditasi/tests_indikator_mutu_charts.py`:

```python
    def test_risiko_input_prefill_from_chart_drilldown(self):
        """Drill-down link params pre-fill the risk form (indicator, unit, problem text)."""
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=8, tahun=2026,
            nilai_numerator=Decimal('60'), nilai_denominator=Decimal('100'))

        url = reverse('akreditasi:risiko_input') + f'?indikator={self.indikator.pk}&bulan=8&tahun=2026'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('prefill_indikator_id', content)
        self.assertIn('60.0', content)
        self.assertIn('Capaian', content)

        # Bogus params must not crash
        bad = reverse('akreditasi:risiko_input') + '?indikator=999999&bulan=99&tahun=abc'
        self.assertEqual(self.client.get(bad).status_code, 200)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts.IndikatorMutuChartsAndUploadTest.test_risiko_input_prefill_from_chart_drilldown -v2`
Expected: FAIL — `prefill_indikator_id` not in the rendered page.

- [ ] **Step 3: Add the prefill context in `risiko_input`**

In `akreditasi/risiko_views.py` line 14, extend the import:

```python
from .risiko_models import RisikoUnit, TindakLanjutRisiko, InsidenKeselamatan, IndikatorMutu, CatatanIndikator
```

Then in `risiko_input`, replace the final context block (lines 444-451) with:

```python
    # ── Pre-fill from dashboard drill-down: ?indikator=&bulan=&tahun= ────────
    prefill_ctx = {}
    try:
        pf_ind_id = int(request.GET.get('indikator') or 0)
        pf_bulan = int(request.GET.get('bulan') or 0)
        pf_tahun = int(request.GET.get('tahun') or 0)
    except (ValueError, TypeError):
        pf_ind_id = pf_bulan = pf_tahun = 0

    if pf_ind_id and 1 <= pf_bulan <= 12 and pf_tahun:
        pf_ind = IndikatorMutu.objects.filter(pk=pf_ind_id, aktif=True).first()
        pf_cat = CatatanIndikator.objects.filter(
            indikator_id=pf_ind_id, bulan=pf_bulan, tahun=pf_tahun
        ).first() if pf_ind else None
        if pf_ind:
            capaian_txt = f"{float(pf_cat.nilai_capaian):.1f}" if pf_cat else 'belum ada data'
            prefill_ctx = {
                'prefill_indikator_id': pf_ind.pk,
                'prefill_unit_id': pf_ind.unit_id,
                'prefill_bulan': pf_bulan,
                'prefill_tahun': pf_tahun,
                'prefill_target': float(pf_ind.target_nilai),
                'prefill_masalah': (
                    f"Capaian {pf_ind.nama_indikator} bulan {pf_bulan}/{pf_tahun} sebesar "
                    f"{capaian_txt}{pf_ind.satuan or '%'} (target "
                    f"{'≤' if pf_ind.arah_target == 'MAX' else '≥'} {pf_ind.target_nilai}{pf_ind.satuan or '%'}). "
                    f"Lakukan analisis akar masalah dan susun rencana PDCA."
                ),
            }

    ctx = {
        'units': units,
        'default_unit_id': default_unit_id,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'strategi_choices': RisikoUnit.STRATEGI_CHOICES,
        'indikator_list': indikator_list,
    }
    ctx.update(prefill_ctx)
    return render(request, 'akreditasi/risiko_form.html', ctx)
```

- [ ] **Step 4: Consume the prefill in `risiko_form.html`**

In `templates/akreditasi/risiko_form.html`, inside the DOMContentLoaded callback, immediately BEFORE the `if (unitSelect) {` init block (line 738), insert:

```js
    // ── Pre-fill dari drill-down dashboard (?indikator=&bulan=&tahun=) ────
    {% if prefill_indikator_id %}
    (function () {
        const PF_IND_ID = "{{ prefill_indikator_id }}";
        const PF_UNIT_ID = "{{ prefill_unit_id|default:'' }}";
        const PF_MASALAH = `{{ prefill_masalah|escapejs }}`;
        const PF_TARGET = "{{ prefill_target|default:'' }}";

        if (PF_UNIT_ID && unitSelect) {
            const hasOpt = Array.prototype.some.call(
                unitSelect.options, o => o.value === PF_UNIT_ID);
            if (hasOpt) unitSelect.value = PF_UNIT_ID;
        }
        window._pendingIndikatorId = PF_IND_ID;

        const masalahEl = document.getElementById('input_masalah');
        if (masalahEl && !masalahEl.value) masalahEl.value = PF_MASALAH;
        if (targetInp && PF_TARGET && !targetInp.value) {
            targetInp.value = parseFloat(PF_TARGET).toFixed(2);
        }
    })();
    {% endif %}
```

Then inside `loadIndikatorByUnit`'s `.then(function(data) { … })`, right after the `data.indikator.forEach(...)` loop closes (line 731, before `})`), insert:

```js
                // Apply pending pre-fill selection once options exist (drill-down / edit)
                if (window._pendingIndikatorId) {
                    indikatorSel.value = window._pendingIndikatorId;
                    indikatorSel.dispatchEvent(new Event('change'));
                    window._pendingIndikatorId = null;
                }
```

- [ ] **Step 5: Run the tests**

Run: `python manage.py test akreditasi.tests_indikator_mutu_charts -v1`
Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add akreditasi/risiko_views.py templates/akreditasi/risiko_form.html akreditasi/tests_indikator_mutu_charts.py
git commit -m "feat(risiko): pre-fill risk form from dashboard chart drill-down params"
```

---

### Task 5: Full regression, live check, plan close-out

**Files:**
- Modify: `docs/superpowers/plans/2026-10-15-grafik-indikator-mutu-perubahan.md` (checkbox tick)

- [ ] **Step 1: Run the full regression suite**

Run:
```bash
python manage.py test akreditasi.tests_indikator_mutu_charts akreditasi.tests_evaluasi_indikator akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1
```
Expected: exit 0, all tests PASS (was 75, now ~81).

- [ ] **Step 2: Django system check**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Manual smoke of the new URLs against the dev server (optional, if a server is running)**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8000/akreditasi/"
```
Expected: `302` (login redirect) — confirms no import-time crash. Skip if no local server is running; the test suite already renders the dashboard.

- [ ] **Step 4: Mark every checkbox in this plan `[x]`**

Use `patch` to flip `- [ ]` to `- [x]` throughout this plan file.

- [ ] **Step 5: Commit and push**

```bash
git add docs/superpowers/plans/2026-10-15-grafik-indikator-mutu-perubahan.md
git commit -m "docs: mark grafik indikator mutu plan tasks completed"
git push origin master
```

- [ ] **Step 6: Verify the deploy**

Run: `curl -sI https://sim-akreditasi-django.vercel.app/ | head -1`
Expected: `HTTP/2 302` (or 200) — Vercel healthy after push.

---

## Self-Review

**1. Spec coverage** (docx item → task):
- 1a "Dropdown Pilih Indikator Mutu" → Task 1 (`mutu_indikator` param) + Task 2 (dropdown).
- 1b "Dinamika warna bar per capaian" → Task 1 (per-bar `chart_mutu_colors`, `_tercapai` with `arah_target`). Note: aggregate mode already coloured bars; the fix is that single-indicator mode now colours against the indicator's own target and respects `MAX`.
- 1c "Data labels di atas bar" → Task 3 (`valueLabelsPlugin`, no new dependency).
- 2a "Bar/Line chart antar-tahun" → Task 1 (`chart_tahunan_*`) + Task 2 (tab) + Task 3 (chart).
- 2b "Toggle Grafik Bulanan / Tren Tahunan / Matriks Rekap" → Task 2 (two new pill tabs alongside existing Bulanan + Renstra).
- 3 "Layout filter [Unit][Kategori][Indikator][Tahun]" → Task 2 (grid re-balanced; mode switch = existing pills).
- 4 "Click-to-PDCA drill-down" → Task 3 (modal + click handler) + Task 4 (prefilled risk form).

**2. Placeholder scan:** no TBD/TODO; every code step carries the actual code.

**3. Type consistency:** context key names in Task 1's return dict match every `{{ … }}`/`{% if … %}` used in Tasks 2–3 and every JS const in Task 3; element ids created in Task 2 (`chartTahunanMulti`, `tabelMatriksRekap`) are the ids Task 3 binds to; `prefill_*` keys defined in Task 4 Step 3 are exactly the ones read in Task 4 Step 4; `_tercapai(val, target, arah)` signature identical in both usages.

**4. Review Focus coverage:** MAX flip → `test_dashboard_arah_target_max_flips_bar_colors`; unknown id → `test_dashboard_unknown_indikator_param_falls_back` + bogus-params half of `test_risiko_input_prefill_from_chart_drilldown`; empty/zero-denominator months → grey colour path asserted in `test_dashboard_single_indicator_selection_and_colors` (months 3-12 stay grey) plus `nilai_denominator` guard in the view; click without single indicator → hint/button branch in `openDrilldown`; unit-scoped prefill with a foreign unit → `hasOpt` guard in Task 4 Step 4.
