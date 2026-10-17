# Dashboard Indicator Picker — Unit/RS Indicators Must Appear and Chart

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the main dashboard, choosing a category (IMU / IMRS / INM) must list every indicator in that category — including the ones with no measurements yet — and selecting one must draw its monthly chart. Today the indicator dropdown silently drops every indicator that has no `CatatanIndikator` row for the selected year, so a unit whose IMU indicators were never measured sees only INM and IMP-RS in the list, concludes the menu "doesn't exist", and cannot pick its own indicator at all.

**Architecture:** Two fixes in the data layer, one in the filter UI, one empty-state. (1) `mutu_indikator_choices` stops filtering on "has data" and instead annotates `punya_data` so the option text can say so. (2) `mutu_jenis_choices` becomes the three canonical tiers instead of all seven `JENIS_CHOICES`, so the dropdown stops offering both `IMU` and `IMP Unit (Legacy)` as separate, differently-behaving entries. (3) The category `<select>` triggers an AJAX repopulate of the indicator `<select>` (the `api_indikator_by_unit` endpoint already exists) instead of a full page reload that loses the selection. (4) A selected indicator with no rows renders an explicit "belum ada pengukuran" panel instead of a blank canvas. No migration, no new endpoint, no new dependency.

**Status:** Not started.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, Chart.js 4, vanilla JS.

**Spec:** `C:\Users\cubeb\Downloads\Didasbor utama masalah untuk melihat grafik indikator, menu indikator mutu unit dan rs belum muncul.docx` — "Alur Sistem Pemilihan & Visualisasi Grafik Indikator Mutu": default params by role, category dropdown → AJAX load of indicators, indicator selection, year selection, explicit submit, chart render, plus the two "Perbaikan Teknis" items (no empty `mutu_indikator=`, dynamic dropdown chain).

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `85,0`; one comma inside `<script>` kills the block (bugs `84c20ce`, `c4c2a3c`).
- **Do not change what the chart draws when `mutu_indikator` is empty.** "Semua Indikator (Rata-rata)" is a real feature; it must keep working and keep its label.
- **`api_indikator_by_unit` already exists** at `/risiko/api/indikator-by-unit/` and returns `{id, kode, nama, jenis, jenis_code, target, satuan, unit_name, pj, preset_rencana_aksi}`. Extend it rather than adding a second endpoint.
- **Unit-scoped users must not gain visibility of other units.** `ind_qs` filtering by `unit_id__in=user_unit_ids` + `NASIONAL` stays exactly as it is; only the "has data" post-filter is removed.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1` — baseline **102/102 OK**.
- Work on `master`; commit after Task 5.

## Verified production facts (Supabase `gwaeuzbbdawbekrmrvfd`, read 2026-10-17)

| Fact | Value |
|---|---|
| Active indicators | 367 — `IMP_UNIT` 219, `IMP_RS` 108, `NASIONAL` 40 |
| `CatatanIndikator` 2026 | `IMP_RS` 432, `NASIONAL` 156 |
| `CatatanIndikator` 2026 by `IMP_UNIT` | **0 rows** |
| `CatatanIndikator` 2025 total | 54 rows |
| Unit 68 (Bangsal Dewasa / Rawat Inap) | has indicators, chain 68 → 66 → 45/26/37 |
| `IndikatorMutu.arah_target='MAX'` | **0 of 367** (see companion plan) |

**Local dev DB differs — measured 2026-10-17 (same code, smaller dataset):** `IndikatorMutu`
209 active (`IMP_RS` 98, `IMP_UNIT` 75, `NASIONAL` 36), `CatatanIndikator` 2026 = 588
(`IMP_RS` 432, `NASIONAL` 156), `IMP_UNIT` rows with 2026 data = 0, `UnitKerja` 218. The
proportions match production; the absolute counts do not. Tests must build their own fixtures.

Consequence: with `mutu_jenis=IMU&mutu_tahun=2026`, `_data_ids` is the empty set for that tier, so `_choices_qs` falls back to `ind_qs` — which is why the dropdown *does* populate on an admin account. But for a unit-scoped user the fallback resolves to `ind_qs` already narrowed to their unit, and once any INM/IMP-RS row exists for 2026 the `if _data_ids` branch wins and **every unit indicator is dropped from the list**. That is the reported symptom, and it is a filter bug, not a data gap.

## Two display bugs found while tracing (fix in Task 4)

1. `templates/akreditasi/dashboard.html:524` renders `{{ mutu_indikator_terpilih.arah_target }}{{ chart_mutu_target_val }}%` → literally `MIN85,0%`. Should be `≥ 85,0%` / `≤ 1,5‰`.
2. `dashboard.html:533-536` hardcodes `Tercapai (≥ {{ chart_mutu_target_val }}%)` and `Di bawah Target (< …)` regardless of `mutu_arah_target`, so a lower-is-better indicator shows the legend inverted.

---

### Task 1: Stop dropping indicators that have no measurements yet

**Files:**
- Modify: `akreditasi/views.py` (~line 158-167)
- Modify: `akreditasi/indikator_views.py` (~line 275-284)

**Why:** the "has data" post-filter makes the dropdown a lie — it presents itself as the list of indicators in the category, but hides the ones the user is most likely looking for (the unmeasured ones).

- [x] **Step 0: Add `{% load l10n %}` to both templates**

`dashboard.html` already has it (line 8). Add at the top of `templates/akreditasi/indikator_dashboard.html`, right after the existing `{% load static %}`:

```html
{% load static l10n %}
```

Reason: any `|unlocalize` below renders as an empty string unless the library is loaded — locale `id` emits `85,0` inside attributes otherwise.


- [x] **Step 1: Replace the filter with an annotation in `views.py`**

Current code, `akreditasi/views.py:158-167`:

```python
    # Dropdown choices: indicators that actually have measurements this year — an
    # indicator without data cannot be charted. Fallback to every active indicator
    # in the filter when the year holds no data at all, so the dropdown is never empty.
    _data_ids = set(
        CatatanIndikator.objects.filter(tahun=mutu_tahun, indikator__in=ind_qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    _choices_qs = ind_qs.filter(pk__in=_data_ids) if _data_ids else ind_qs
    mutu_indikator_choices = list(_choices_qs.order_by('jenis', 'kode_indikator'))
    selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)
```

Replace with:

```python
    # Setiap indikator pada filter tetap muncul di dropdown; yang belum punya
    # pengukuran tahun ini diberi penanda, bukan disembunyikan. Menyembunyikan
    # indikator tanpa data membuat unit mengira indikatornya tidak ada.
    _data_ids = set(
        CatatanIndikator.objects.filter(tahun=mutu_tahun, indikator__in=ind_qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    mutu_indikator_choices = list(
        ind_qs.annotate(
            punya_data=Exists(
                CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=mutu_tahun)
            )
        ).order_by('jenis', 'kode_indikator')
    )
    selected_indikator = next((i for i in mutu_indikator_choices if i.pk == mutu_indikator_id), None)
```

`_data_ids` stays — the empty-state panel in Task 4 uses it to tell "this indicator has no rows" from "this year has no rows at all".

Extend the existing import at `akreditasi/views.py:10`:

```python
from django.db.models import Count, Q, Sum, F, Avg, Exists, OuterRef
```

- [x] **Step 2: Same change in `indikator_views.py`**

Current code, `akreditasi/indikator_views.py:275-284`:

```python
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
```

Replace with:

```python
    # Semua indikator pada filter tetap ada di dropdown; yang belum diukur tahun
    # ini hanya diberi penanda. Menyembunyikannya membuat unit mengira indikator
    # miliknya belum terdaftar.
    data_ind_ids = set(
        CatatanIndikator.objects.filter(tahun=tahun_int, indikator__in=qs)
        .values_list('indikator_id', flat=True).distinct()
    )
    indikator_choices = list(
        qs.annotate(
            punya_data=Exists(
                CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=tahun_int)
            )
        ).order_by('jenis', 'kode_indikator')
    )
    selected_indikator = next((i for i in indikator_choices if i.pk == indikator_id), None)
```

Extend the existing import at `akreditasi/indikator_views.py:7`:

```python
from django.db.models import Avg, Count, Q, Sum, Exists, OuterRef
```

- [x] **Step 3: Mark the empty ones in both dropdowns**

`templates/akreditasi/dashboard.html:492-494`:

```html
                        {% for ind in mutu_indikator_choices %}
                        <option value="{{ ind.pk }}" title="[{{ ind.kode_indikator }}] {{ ind.nama_indikator }} — Target {{ ind.target_nilai|unlocalize }}{{ ind.satuan }} | PJ: {{ ind.pj|default:'-' }} | Dimensi: {{ ind.get_dimensi_mutu_display }}" {% if filter_mutu_indikator == ind.pk %}selected{% endif %}>
                            [{{ ind.kode_indikator }}] {{ ind.nama_indikator }}{% if not ind.punya_data %} — belum ada data {{ filter_mutu_tahun }}{% endif %}
                        </option>
                        {% endfor %}
```

`templates/akreditasi/indikator_dashboard.html:295-297`: same `{% if not ind.punya_data %}` suffix, and swap `{{ ind.target_nilai }}` for `{{ ind.target_nilai|unlocalize }}` in the `title` (it currently emits `85,00` inside an attribute — harmless, but inconsistent with the rest).

- [x] **Step 4: Confirm the count grows on a unit-scoped account**

```bash
.venv/Scripts/python.exe manage.py shell -c "
from django.test import Client
from django.contrib.auth import get_user_model
u = get_user_model().objects.filter(profile__is_unit_scoped=True).first()
print('unit-scoped user:', u)
c = Client(); c.force_login(u)
html = c.get('/?mutu_jenis=IMU&mutu_tahun=2026').content.decode()
import re
opts = re.findall(r'<option value=\"(\d+)\"[^>]*>\s*(\[[^\]]+\][^<]*)', html)
print('opsi indikator:', len(opts))
print(*opts[:8], sep='\n')
"
```

Expected: the option count equals the number of `IMP_UNIT` indicators reachable from that user's unit (plus `NASIONAL` rows that match the tier map), and at least one option carries the "belum ada data 2026" suffix.

---

### Task 2: Three canonical tiers in the category dropdown, not seven raw codes

**Files:**
- Modify: `akreditasi/views.py` (~line 303)
- Modify: `templates/akreditasi/dashboard.html` (~line 467-472)
- Modify: `akreditasi/indikator_views.py` (~line 322)

**Why:** `mutu_jenis_choices = IndikatorMutu.JENIS_CHOICES` offers `IMU`, `IMP Unit (Legacy)`, `IMRS`, `IMP Rumah Sakit (Legacy)`, `INM`, `Indikator Nasional Mutu (Legacy)`, `SNI`. Picking the legacy entry bypasses `_JENIS_MAP` and filters on the raw code alone, so `IMP Unit (Legacy)` returns only the 219 legacy rows while `IMU` returns `IMU` + `IMP_UNIT` — two menu entries that look like the same thing and behave differently. That is a direct cause of "menunya tidak muncul / datanya kosong".

- [x] **Step 1: Define the canonical tier list once, next to `_JENIS_MAP`**

```python
    # Tiga tier kanonik. Kode legacy (IMP_RS / IMP_UNIT / NASIONAL) tidak
    # ditawarkan terpisah: _JENIS_MAP sudah memetakannya ke tier yang sama,
    # dan dua entri dropdown yang berperilaku beda untuk hal yang sama
    # membingungkan pengguna.
    _TIER_CHOICES = [
        ('INM',  'INM — Indikator Nasional Mutu'),
        ('IMRS', 'IMRS — Indikator Mutu Rumah Sakit'),
        ('IMU',  'IMU — Indikator Mutu Unit'),
    ]
```

- [x] **Step 2: Expose it in the context**

`views.py` line ~303:

```python
        'mutu_jenis_choices': _TIER_CHOICES,
```

`indikator_views.py` line ~322:

```python
        'jenis_choices': [
            ('INM',  'INM — Indikator Nasional Mutu'),
            ('IMRS', 'IMRS — Indikator Mutu Rumah Sakit'),
            ('IMU',  'IMU — Indikator Mutu Unit'),
        ],
```

Leave `JENIS_CHOICES` on the model untouched — the indicator create/edit form legitimately needs all seven.

- [x] **Step 3: Fix the empty-value label so it matches what it does**

`dashboard.html:468`:

```html
                        <option value="">Semua Kategori (INM + IMRS + IMU)</option>
```

`indikator_dashboard.html:271`:

```html
            <option value="">Semua Kategori ({{ indikators|length }})</option>
```

The second one is already accurate. The first one previously said "INM / IMP" which does not match the legacy codes it actually includes.

---

### Task 3: Category change repopulates the indicator list without losing the page

**Files:**
- Modify: `akreditasi/risiko_views.py` (`api_indikator_by_unit`, ~line 170-208)
- Modify: `templates/akreditasi/dashboard.html` (~line 464-512)
- Modify: `akreditasi/urls.py` (add one route)

**Why:** every `<select>` in the toolbar is `onchange="this.form.submit()"`. Picking a category submits the form with whatever indicator was previously selected — which now belongs to a different category, so the server drops it and the chart reverts to the average. The spec explicitly asks for the dropdown chain to repopulate via AJAX.

- [x] **Step 1: Make `api_indikator_by_unit` accept `jenis` and `tahun`**

The function is at `akreditasi/risiko_views.py:170-208` and currently keys only on `unit_id`. Change the first half, keep the `rencana_aksi` preset logic and every existing key untouched:

```python
def api_indikator_by_unit(request):
    """AJAX: daftar IndikatorMutu aktif berdasarkan unit_id, jenis, dan tahun.

    Dipakai form risiko (unit_id) dan filter dashboard (jenis + tahun).
    Menyertakan penanda punya_data agar UI bisa membedakan indikator yang
    sudah diukur dari yang belum.
    """
    unit_id = request.GET.get('unit_id')
    jenis = request.GET.get('jenis', '')
    try:
        tahun = int(request.GET.get('tahun') or 0)
    except (ValueError, TypeError):
        tahun = 0

    qs = IndikatorMutu.objects.filter(aktif=True).select_related('unit')
    if unit_id:
        # Tampilkan indikator milik unit ini + indikator INM global (unit=null)
        qs = qs.filter(Q(unit_id=unit_id) | Q(unit__isnull=True))
    if jenis:
        _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
        qs = qs.filter(jenis__in=_JENIS_MAP.get(jenis, [jenis]))
    qs = qs.order_by('jenis', 'kode_indikator')

    # Fallback: jika unit ada tapi tidak punya indikator sama sekali,
    # tampilkan semua indikator NASIONAL (INM) sebagai indikator universal
    if unit_id and not qs.exists():
        qs = IndikatorMutu.objects.filter(aktif=True, jenis='NASIONAL').order_by('kode_indikator')

    if tahun:
        qs = qs.annotate(punya_data=Exists(
            CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=tahun)))
```

Then inside the existing `data.append({...})` block, add two keys after `'preset_rencana_aksi'`:

```python
            'punya_data': bool(getattr(ind, 'punya_data', False)) if tahun else None,
            'arah': getattr(ind, 'arah_target', 'MIN'),
```

Imports for that module — confirm `Exists`, `OuterRef`, and `CatatanIndikator` are available; `risiko_views.py` already imports `CatatanIndikator` for other views, add the two `django.db.models` names if missing:

```python
from django.db.models import Q, Min, Exists, OuterRef
```

- [x] **Step 2: Add the dashboard-specific route**

`akreditasi/urls.py`, next to the existing API route:

```python
    path('api/mutu-indikator/', views.api_mutu_indikator, name='api_mutu_indikator'),
```

- [x] **Step 3: Write the view it points at**

In `akreditasi/views.py`, after `_get_mutu_renstra_charts_context`:

```python
@login_required
def api_mutu_indikator(request):
    """AJAX: opsi dropdown Indikator Mutu untuk toolbar dashboard.

    Memakai ulang filter unit-scope yang sama dengan _get_mutu_renstra_charts_context
    agar pengguna unit tidak pernah melihat indikator unit lain.
    """
    from .risiko_models import IndikatorMutu, CatatanIndikator
    from django.db.models import Exists, OuterRef

    profile = getattr(request.user, 'profile', None)
    jenis = request.GET.get('jenis', '')
    try:
        tahun = int(request.GET.get('tahun') or 2026)
    except (ValueError, TypeError):
        tahun = 2026

    qs = IndikatorMutu.objects.filter(aktif=True)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        u = profile.unit_kerja
        unit_ids = list(UnitKerja.objects.filter(
            Q(pk=u.pk) | Q(parent=u) | Q(parent__parent=u)
        ).values_list('pk', flat=True))
        qs = qs.filter(Q(unit_id__in=unit_ids) | Q(jenis='NASIONAL'))
    if jenis:
        _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
        qs = qs.filter(jenis__in=_JENIS_MAP.get(jenis, [jenis]))

    qs = qs.annotate(punya_data=Exists(
        CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=tahun)
    )).order_by('jenis', 'kode_indikator')

    return JsonResponse({'indikator': [
        {'id': i.pk, 'kode': i.kode_indikator, 'nama': i.nama_indikator,
         'punya_data': bool(i.punya_data)}
        for i in qs
    ]})
```

- [x] **Step 4: Wire the toolbar to it**

In `dashboard.html`, give the three selects ids and replace the two `onchange="this.form.submit()"` handlers on category and year with a JS function; leave the indicator select's own submit behaviour alone.

```html
                    <select name="mutu_jenis" id="filterMutuJenis" class="form-select form-select-sm">
```

```html
                    <select name="mutu_indikator" id="filterMutuIndikator" class="form-select form-select-sm" onchange="this.form.submit()">
```

```html
                    <select name="mutu_tahun" id="filterMutuTahun" class="form-select form-select-sm">
```

```javascript
    // Kategori / tahun berubah → muat ulang daftar indikator, kosongkan
    // pilihan indikator (indikator lama milik kategori lain), lalu submit
    // supaya grafik langsung menampilkan rata-rata kategori baru.
    function reloadIndikator(andSubmit) {
        const jenis = document.getElementById('filterMutuJenis');
        const tahun = document.getElementById('filterMutuTahun');
        const ind = document.getElementById('filterMutuIndikator');
        if (!jenis || !tahun || !ind) return;
        const url = "{% url 'akreditasi:api_mutu_indikator' %}?jenis="
            + encodeURIComponent(jenis.value) + "&tahun=" + encodeURIComponent(tahun.value);
        fetch(url).then(r => r.json()).then(data => {
            ind.innerHTML = '<option value="">Semua Indikator (Rata-rata)</option>';
            (data.indikator || []).forEach(function (i) {
                const o = document.createElement('option');
                o.value = i.id;
                o.textContent = '[' + i.kode + '] ' + i.nama + (i.punya_data ? '' : ' — belum ada data');
                ind.appendChild(o);
            });
            if (andSubmit) ind.form.submit();
        });
    }
    document.getElementById('filterMutuJenis')?.addEventListener('change', () => reloadIndikator(true));
    document.getElementById('filterMutuTahun')?.addEventListener('change', () => reloadIndikator(true));
```

Place it in the existing `DOMContentLoaded` block at `dashboard.html:1041` area, before the Chart construction, so the handlers exist even when the canvas is absent.

- [x] **Step 5: Never submit an empty `mutu_indikator` when one was chosen**

The spec's "Validasi Form" item. Guard in the same handler:

```javascript
    document.querySelector('form[method="GET"]')?.addEventListener('submit', function (e) {
        const ind = document.getElementById('filterMutuIndikator');
        if (ind && ind.value === '') {
            // Kosong = "rata-rata", bukan error. Hapus parameter agar URL bersih.
            ind.disabled = true;
        }
    });
```

Disabling the control drops it from the query string entirely, which is the correct representation of "average" — better than `mutu_indikator=`.

---

### Task 4: Say *why* a chart is empty, and stop printing `MIN85,0%`

**Files:**
- Modify: `templates/akreditasi/dashboard.html` (~line 517-543, ~line 1044-1150)
- Modify: `templates/akreditasi/indikator_dashboard.html` (~line 495-501)

**Why:** the current empty state is an unlabelled blank canvas, which reads as "broken". The spec asks for the chart to update when data exists; when it doesn't, the page must say which of the two reasons applies — no measurements for this indicator, or no measurements for this whole year/tier.

Locale note: this project runs `LANGUAGE_CODE = 'id'`, so `{{ chart_mutu_target_val }}` renders `85,0`. That is correct for on-screen text and must stay localized — `|unlocalize` belongs only inside JS/CSS literals (Global Constraints). The bug is not the comma; it is that the raw choice code `MIN` is printed where a comparison symbol belongs.

- [x] **Step 1: Fix the header line at `dashboard.html:521-528`**

Current `:524` renders `(MIN85,0%)` — the raw choice code where a comparison symbol belongs. The `{% else %}` branch at `:527` is fine (no code leaked) but says nothing about polarity; give it the symbol too so the two branches read consistently.

```html
                                <strong class="text-danger font-monospace">({{ mutu_indikator_terpilih.arah_target }}{{ chart_mutu_target_val }}%)</strong>
```

→

```html
                                <strong class="text-danger font-monospace">({% if mutu_arah_target == 'MAX' %}&le;{% else %}&ge;{% endif %} {{ chart_mutu_target_val }}{{ mutu_indikator_terpilih.satuan }})</strong>
```

and `:527`:

```html
                                <strong class="text-danger font-monospace">({{ chart_mutu_target_val }}%)</strong>
```

→

```html
                                <strong class="text-danger font-monospace">({% if mutu_arah_target == 'MAX' %}&le;{% else %}&ge;{% endif %} {{ chart_mutu_target_val }}%)</strong>
```

Note `mutu_indikator_terpilih.satuan` replaces the hardcoded `%`: several indicators use `‰` or `hari`, and the current line prints `%` for all of them.

- [x] **Step 2: Make the legend badges polarity-aware at `:532-537`**

These are hardcoded `≥` / `<`, so for a `MAX` indicator (lower is better) the legend states the opposite of what the chart colours mean. Same conditional as Step 1:

```html
                            <span class="badge bg-success-subtle text-success border border-success-subtle me-1" style="font-size:0.7rem;">
                                <i class="bi bi-square-fill me-1"></i>Tercapai ({% if mutu_arah_target == 'MAX' %}&le;{% else %}&ge;{% endif %} {{ chart_mutu_target_val }}%)
                            </span>
                            <span class="badge bg-danger-subtle text-danger border border-danger-subtle" style="font-size:0.7rem;">
                                <i class="bi bi-square-fill me-1"></i>Di luar Target ({% if mutu_arah_target == 'MAX' %}&gt;{% else %}&lt;{% endif %} {{ chart_mutu_target_val }}%)
                            </span>
```

- [x] **Step 3: Replace the dead `hasMutuData` with a real empty-state panel**

`hasMutuData` at line 1048 is assigned and never read — dead code. Use it. Do **not** build the panel by string-concatenating a `yesno` filter inside JS: nested quotes break the script block and one syntax error kills every chart on the page. Put the two variants in markup and let JS toggle visibility.

Markup — add as a sibling of the canvas, right after `<canvas id="chartMutuBulanan" ...></canvas>`:

```html
                    <div id="mutuEmpty" class="h-100 d-none flex-column align-items-center justify-content-center text-center px-3">
                        <i class="bi bi-bar-chart text-secondary" style="font-size:2rem;"></i>
                        {% if mutu_indikator_terpilih %}
                        <span class="fw-semibold text-dark mt-2" style="font-size:.85rem;">Belum ada pengukuran {{ filter_mutu_tahun }}</span>
                        <span class="text-muted" style="font-size:.72rem;">
                            Indikator ini belum punya catatan bulanan. Input capaian lewat menu Indikator Mutu.
                        </span>
                        {% else %}
                        <span class="fw-semibold text-dark mt-2" style="font-size:.85rem;">Belum ada catatan untuk kategori ini</span>
                        <span class="text-muted" style="font-size:.72rem;">
                            Pilih indikator lain, ganti kategori, atau ganti tahun.
                        </span>
                        {% endif %}
                        <a href="{% url 'akreditasi:indikator_dashboard' %}?tahun={{ filter_mutu_tahun }}"
                           class="btn btn-sm btn-outline-primary mt-2">
                            <i class="bi bi-box-arrow-up-right me-1"></i>Buka Indikator Mutu
                        </a>
                    </div>
```

JS — in the `DOMContentLoaded` block, immediately after the `const mutuEl = ...` line and **before** `new Chart(...)`:

```javascript
        if (!hasMutuData) {
            // Tidak ada catatan bulanan: ganti canvas dengan penjelasan sebabnya.
            const empty = document.getElementById('mutuEmpty');
            mutuEl.classList.add('d-none');
            if (empty) { empty.classList.remove('d-none'); empty.classList.add('d-flex'); }
        } else {
```

and close the `else` after the `new Chart(...)` statement.

`hasMutuData` is already wired to the server at `:1048`: `const hasMutuData = {{ has_monthly_data|yesno:"true,false" }};`. Keep the server value — it is computed from the filtered queryset including `jenis`, `unit`, and the unit-scope gate, which the JS cannot see. Do not re-derive it from the data array.

- [x] **Step 4: Point the empty list state at a page the user can actually open**

`templates/akreditasi/indikator_dashboard.html:495-501`. `indikator_tambah` is manager-only, so gate the link — a unit-scoped account clicking a 403 is worse than no link:

```html
          {% empty %}
          <tr>
            <td colspan="8" class="text-center py-5 text-muted">
              <i class="bi bi-inbox fs-1 d-block mb-2 text-secondary"></i>
              <span class="d-block fw-semibold text-dark">Tidak ada indikator pada filter ini</span>
              <span class="d-block small mt-1">
                {% if filter_jenis %}
                  Belum ada indikator terdaftar untuk kategori <strong>{{ filter_jenis }}</strong>{% if filter_unit %} di unit yang dipilih{% endif %}.
                {% else %}
                  Belum ada indikator mutu aktif di sistem.
                {% endif %}
              </span>
              {% if is_manager %}
              <a href="{% url 'akreditasi:indikator_tambah' %}" class="btn btn-sm btn-outline-primary mt-2">
                <i class="bi bi-plus-lg me-1"></i>Tambah Indikator Mutu
              </a>
              {% endif %}
            </td>
          </tr>
```

Note: with Task 1 in place this branch only renders when the tier genuinely holds no indicators at all, not when they merely lack data.

---

### Task 5: Regression tests

**Files:**
- Modify: `akreditasi/tests_indikator_mutu_charts.py`

**Why:** the "has data" filter was introduced deliberately (an indicator with no rows cannot be charted), so a future reader will be tempted to re-add it. The test has to pin the distinction: the option must be present, and the chart must say why it is empty.

- [x] **Step 0: Rewrite the two existing tests that pin the behaviour this plan removes**

Task 1 deliberately deletes the "has data" filter, and two tests in this module assert that filter. They will go red on a correct implementation — update them in the same commit, do not "fix" the production code to keep them green.

`akreditasi/tests_indikator_mutu_charts.py:252` — `test_mutu_dashboard_dropdown_lists_only_data_bearing_indicators` asserts `assertNotIn(str(empty.pk), opts)`. That is the old contract. Replace the body's last two assertions with:

```python
        # Kontrak baru: indikator tanpa data tetap muncul, hanya ditandai.
        self.assertIn(str(self.indikator.pk), opts)
        self.assertIn(str(empty.pk), opts)
        self.assertIn('belum ada data', m.group(0))
```

and rename the method to `test_mutu_dashboard_dropdown_lists_all_indicators_and_flags_empty`.

`akreditasi/tests_indikator_mutu_charts.py:273` — `test_mutu_dashboard_empty_tier_falls_back_to_all_indicators` keeps passing unchanged (with no filter, `IMU-99` is listed). Leave it.

`akreditasi/tests_indikator_mutu_charts.py:410` — `test_dropdown_options_show_full_name_and_title_attr` matches `Target 85` on the `title` attribute and only checks that the name appears somewhere; the added suffix and `|unlocalize` do not break either. Leave it.

- [x] **Step 1: Add the new tests**

```python
class IndikatorDropdownTanpaDataTest(TestCase):
    """Indikator tanpa pengukuran tetap muncul di dropdown, dengan penanda."""

    def setUp(self):
        self.user = User.objects.create_superuser('admin_dd', 'dd@rs.id', 'secret123')
        self.unit = UnitKerja.objects.create(name='Bangsal Dropdown', code='DD-01', tipe_unit='RUANGAN')
        self.ind_kosong = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Identifikasi Pasien', kode_indikator='DD-IMU-01',
            unit=self.unit, jenis='IMP_UNIT', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('100.00'), satuan='%',
        )
        self.ind_berisi = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan Kebersihan Tangan', kode_indikator='DD-INM-01',
            unit=None, jenis='NASIONAL', dimensi_mutu='AMAN',
            numerator='n', denominator='d', target_nilai=Decimal('85.00'), satuan='%',
        )
        CatatanIndikator.objects.create(
            indikator=self.ind_berisi, tahun=2026, bulan=1,
            nilai_numerator=Decimal('90'), nilai_denominator=Decimal('100'),
        )
        self.client.force_login(self.user)

    def test_indikator_tanpa_data_tetap_ada_di_dropdown(self):
        html = self.client.get('/?mutu_jenis=IMU&mutu_tahun=2026').content.decode()
        self.assertIn('DD-IMU-01', html)
        self.assertIn('belum ada data', html)

    def test_kategori_legacy_tidak_ditawarkan(self):
        html = self.client.get('/?mutu_tahun=2026').content.decode()
        self.assertNotIn('IMP Unit (Legacy)', html)
        self.assertNotIn('IMP Rumah Sakit (Legacy)', html)

    def test_api_mutu_indikator_menghormati_jenis(self):
        r = self.client.get('/api/mutu-indikator/?jenis=IMU&tahun=2026')
        kode = [i['kode'] for i in r.json()['indikator']]
        self.assertIn('DD-IMU-01', kode)
        self.assertNotIn('DD-INM-01', kode)

    def test_arah_target_dirender_sebagai_simbol(self):
        self.ind_berisi.arah_target = 'MAX'
        self.ind_berisi.save(update_fields=['arah_target'])
        html = self.client.get(f'/?mutu_indikator={self.ind_berisi.pk}&mutu_tahun=2026').content.decode()
        # Simbol perbandingan, bukan kode arah mentah; angkanya tetap ter-lokalisasi.
        self.assertNotRegex(html, r'MIN[\d,\.]')
        self.assertIn('&le;', html)
```

- [x] **Step 2: Run the module, then the full suite**

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_mutu_charts -v1
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1
```

Expected: 21 + 4 = 25 in the module (one existing test rewritten, none deleted), 106/106 total across the seven modules.

- [x] **Step 3: `node --check` the inline JS**

```bash
.venv/Scripts/python.exe manage.py shell -c "
import re
html = open('templates/akreditasi/dashboard.html', encoding='utf-8').read()
js = re.search(r'{% block extra_js %}(.*?){% endblock %}', html, re.S).group(1)
open(r'$TMPDIR/dash.js','w',encoding='utf-8').write(js)
" && node --check "$TMPDIR/dash.js"
```

- [x] **Step 4: Render-diff `/` for an admin account before and after**

Expected differences: the category `<option>` list shrinks from seven to four (blank + three tiers), the indicator `<option>` text gains `— belum ada data 2026` suffixes, the header/legend gain `≥`/`≤`, and the JS gains the fetch block. No chart data array may change.

- [ ] **Step 5: Commit, push, confirm deploy**

```bash
git add akreditasi/views.py akreditasi/indikator_views.py akreditasi/risiko_views.py akreditasi/urls.py \
        templates/akreditasi/dashboard.html templates/akreditasi/indikator_dashboard.html \
        akreditasi/tests_indikator_mutu_charts.py \
        docs/superpowers/plans/2026-10-17-dashboard-indikator-picker.md
git commit -m "fix(dashboard): list every indicator in the chosen tier and explain empty charts

The indicator dropdown was filtered to indicators that already had a
CatatanIndikator row for the selected year, so a unit whose IMU indicators
were never measured saw only INM and IMP-RS and concluded the menu did not
exist. The filter is gone; options now carry a 'belum ada data' marker, the
category list offers the three canonical tiers instead of seven raw codes,
changing tier or year repopulates the list via /api/mutu-indikator/ without
losing the page, and an empty chart states which of the two reasons applies.
Also fixes the literal 'MIN85.0%' target label and the hardcoded >= legend."
git push origin master
sleep 80 && gh api repos/faishaltsq/sim-akreditasi-django/commits/$(git rev-parse --short HEAD)/status --jq '.state, .statuses[].description'
```

Expected: `success` / `Deployment has completed`.

---

## Review Focus

- **`Exists` subquery per option is a correlated subquery.** 367 rows × one indexed lookup on `(indikator_id, tahun)` is fine; if the dropdown ever gets slow, replace with a single `values_list('indikator_id')` set and a Python-side `hasattr`. Do not reach for `prefetch_related` here — it loads every `CatatanIndikator` row to answer a yes/no question.
- **`mutu_indikator` empty is not an error.** It means "average". The submit guard disables the control rather than injecting a sentinel value, so the URL stays clean and bookmarks keep working.
- **`api_indikator_by_unit` is shared with the risk form.** Every key it returns today must survive; `risiko_form.html:695` builds the indicator `<option>`s from `id`, `kode`, `nama`, `target`, `satuan`, `preset_rencana_aksi`. The new keys are additive.
- **Unit scoping is duplicated in two views.** `api_mutu_indikator` re-implements the three-level ancestor walk from `_get_mutu_renstra_charts_context`. If a third caller appears, extract it — for two, duplicating eight lines is cheaper than an abstraction.
- **The chart still needs at least one indicator in `filtered_ind_ids`.** With `mutu_indikator` empty and `ind_qs` empty (e.g. a unit with zero indicators), `chart_qs` is empty and every month is `None` — `hasMutuData` is `False`, which is exactly the case the new panel covers.
- **Do not apply this plan's `arah_target` display fix without the companion plan.** The badge will read `≤` while the underlying `arah_target` is still `MIN` on all 367 rows; the symbol would then contradict the colour, which is worse than the current literal. Land `2026-10-17-evaluasi-capaian-polaritas-target.md` Task 6 first, or land both together.
