# Professional Table Layout & Formatting for Laporan Lengkap Risiko Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the table layouts and text rendering across the "Laporan Lengkap Risiko" (ARIMA comprehensive risk report) to be clean, proportional, and professional per STARKES / PMKP standards, adding structured list formatting for action plans, sticky table headers, right-aligned monetary values, capitalized PIC names, and proportional column widths.

**Architecture:** 
1. A new template filter `render_structured_plan` in `akreditasi/templatetags/akreditasi_tags.py` to intelligently parse dense numbered/bulleted action plan and RTL strings into structured step blocks with bold prefixes and line spacing.
2. Comprehensive CSS enhancements in `templates/akreditasi/risiko_laporan_lengkap.html` providing dedicated column classes (`.col-masalah`, `.col-indikator`, `.col-tindakan`, `.col-waktu`, `.col-biaya`, `.col-pic`, `.col-aksi`), 1.5 line height, 10px 12px padding, sticky table headers, and word break.
3. Updated table headers and cell alignments in Table 3 (Penilaian Risiko Awal), Table 5 (Indikator Mutu), Table 6 (Rencana Aksi Mitigasi), Table 7 (Pelaksanaan Do), Table 8 (Monitoring & Evaluasi), and the single-risk view.

**Tech Stack:** Django 4.x, Bootstrap 5, Bootstrap Icons, Django Template Tags, CSS3.

**Spec:** `C:/Users/cubeb/Downloads/Lakukan Untuk membuat tampilan rapih.docx`

## Global Constraints

- Plans written in English.
- No new pip dependencies.
- No database model migrations — all enhancements are presentational (HTML, CSS, template tags).
- Preserve existing URLs and navigation anchors.
- All existing 67 tests in the suite must continue to pass without regression.
- Financial figures must be right-aligned (`text-end`) with monospace styling.
- PIC names must have capitalized display (`text-transform: capitalize;`).
- Numbered action items (e.g. `1. ... 2. ...`) must render as distinct structured points rather than single continuous blocks.

## Review Focus

- Long text without numbers or bullet points must render cleanly with `linebreaksbr` without being mangled by the parser.
- Empty or `None` values in action plans or costs must safely render as `—` without crashing or showing raw `None`.
- Table print layout (`@media print`) must remain crisp, hiding edit menus (`.no-print`) and resetting table heights for standard paper printing.
- Single-risk view (`is_single=True`) and multi-risk unit view (`is_single=False`) must both receive the typography and layout upgrades.
- Sticky table headers must not obscure content or break on small mobile viewports.

---

## File Structure & Map

| File | Modification |
|---|---|
| `akreditasi/templatetags/akreditasi_tags.py` | Add `render_structured_plan` filter for parsing and styling numbered/bulleted action steps |
| `templates/akreditasi/risiko_laporan_lengkap.html` | Update CSS styles (column widths, padding, sticky header, typography) and refactor Tables 3, 5, 6, 7, 8 + Single Risk table |
| `akreditasi/tests_perencanaan_risiko.py` | Add automated tests for `render_structured_plan` filter and verify right-alignment of financial costs in rendered HTML |

---

### Task 1: Implement `render_structured_plan` Template Filter

**Files:**
- Modify: `akreditasi/templatetags/akreditasi_tags.py`
- Test: `akreditasi/tests_perencanaan_risiko.py`

**Interfaces:**
- Consumes: Raw text strings containing numbered items (`1. `, `2. `) or multi-line bullets (`• `, `- `).
- Produces: Safe HTML (`mark_safe`) containing structured, nicely spaced step blocks with bold number badges and clean sub-items.

- [ ] **Step 1: Write failing unit tests in `akreditasi/tests_perencanaan_risiko.py`**

```python
def test_render_structured_plan_numbered(self):
    """Ensure render_structured_plan parses '1. Step one 2. Step two' into structured items."""
    from akreditasi.templatetags.akreditasi_tags import render_structured_plan
    raw_text = "1. Lakukan audit cepat alur triase 2. Revisi dan perbarui SOP Triase IGD"
    html = render_structured_plan(raw_text)
    self.assertIn('step-badge', html)
    self.assertIn('1', html)
    self.assertIn('2', html)
    self.assertIn('Lakukan audit cepat', html)
    self.assertIn('Revisi dan perbarui', html)

def test_render_structured_plan_bullets(self):
    """Ensure render_structured_plan parses bulleted multiline text."""
    from akreditasi.templatetags.akreditasi_tags import render_structured_plan
    raw_text = "• Penempelan alur Door-to-ECG\n• Penyediaan EKG mobile"
    html = render_structured_plan(raw_text)
    self.assertIn('<ul', html)
    self.assertIn('Door-to-ECG', html)
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
source .venv/Scripts/activate
python manage.py test akreditasi.tests_perencanaan_risiko.PerencanaanRisikoTests.test_render_structured_plan_numbered -v2
```
Expected: `ImportError: cannot import name 'render_structured_plan'`.

- [ ] **Step 3: Implement `render_structured_plan` in `akreditasi/templatetags/akreditasi_tags.py`**

Add filter:
```python
@register.filter(is_safe=True)
def render_structured_plan(value):
    """Render dense action plans (1. ... 2. ...) or bulleted lists into structured, readable steps."""
    import re
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not value or not str(value).strip():
        return mark_safe('<span class="text-muted fst-italic">—</span>')

    text = str(value).strip()

    # Detect numbered list: 1. ... 2. ...
    num_pattern = r'(?:^|\s+)(?=\d+[\.\)]\s+)'
    parts = [p.strip() for p in re.split(num_pattern, text) if p.strip()]

    if len(parts) > 1 or re.match(r'^\d+[\.\)]\s+', text):
        out = ['<div class="action-plan-container d-flex flex-column gap-2">']
        for p in parts:
            m = re.match(r'^(\d+)[\.\)]\s*(.*)', p, re.DOTALL)
            if m:
                step_num, content = m.group(1), m.group(2).strip()
            else:
                step_num, content = "", p

            # Split sub-sentences or sub-bullets if present
            sub_bullets = [s.strip() for s in re.split(r'\n+|\r\n+|;\s*', content) if s.strip()]
            
            out.append(
                f'<div class="plan-step-item d-flex align-items-start gap-2" style="font-size:0.8rem; line-height:1.5;">'
            )
            if step_num:
                out.append(
                    f'<span class="badge bg-teal-subtle text-teal fw-bold border border-teal-subtle step-badge px-1.5 py-0.5" '
                    f'style="font-size:0.7rem; min-width:24px; text-align:center;">{step_num}</span>'
                )
            if len(sub_bullets) > 1:
                out.append('<div class="flex-grow-1">')
                out.append(f'<div class="fw-semibold text-dark mb-1">{escape(sub_bullets[0])}</div>')
                out.append('<ul class="mb-0 ps-3 text-muted" style="font-size:0.77rem; list-style-type:circle;">')
                for sub in sub_bullets[1:]:
                    clean_sub = re.sub(r'^[•\-\*]\s*', '', sub).strip()
                    if clean_sub:
                        out.append(f'<li>{escape(clean_sub)}</li>')
                out.append('</ul>')
                out.append('</div>')
            else:
                out.append(f'<div class="flex-grow-1 text-dark">{escape(content)}</div>')
            out.append('</div>')
        out.append('</div>')
        return mark_safe("".join(out))

    # Detect bullet points: • or -
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) > 1 and any(l.startswith(('•', '-', '*')) for l in lines):
        out = ['<ul class="mb-0 ps-3" style="font-size:0.8rem; line-height:1.5;">']
        for line in lines:
            clean_line = re.sub(r'^[•\-\*]\s*', '', line).strip()
            if clean_line:
                out.append(f'<li class="mb-1 text-dark">{escape(clean_line)}</li>')
        out.append('</ul>')
        return mark_safe("".join(out))

    # Default fallback with proper line breaks & line height
    return mark_safe(f'<div style="font-size:0.8rem; line-height:1.5; word-break:break-word;">{escape(text)}</div>')
```

- [ ] **Step 4: Run unit test to verify pass**

```bash
python manage.py test akreditasi.tests_perencanaan_risiko.PerencanaanRisikoTests.test_render_structured_plan_numbered -v2
```
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add akreditasi/templatetags/akreditasi_tags.py akreditasi/tests_perencanaan_risiko.py
git commit -m "feat(templates): add render_structured_plan filter for structured action items"
```

---

### Task 2: Implement Comprehensive Table Layout & CSS Styles

**Files:**
- Modify: `templates/akreditasi/risiko_laporan_lengkap.html:8-170` (in `{% block extra_css %}`)

**Interfaces:**
- Consumes: Standard HTML markup in tables.
- Produces: Visual styles according to the consultant specification in `integrasi system arima.docx` and `Lakukan Untuk membuat tampilan rapih.docx`.

- [ ] **Step 1: Inspect and enhance `{% block extra_css %}` in `templates/akreditasi/risiko_laporan_lengkap.html`**

Add CSS rules matching consultant's recommendations:
```css
/* Table Layout & Sticky Header */
.table-sticky-wrapper {
    max-height: 80vh;
    overflow-y: auto;
    overflow-x: auto;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-bottom: 1.5rem;
}
.table-formal, .table-report {
    width: 100%;
    margin-bottom: 0;
    border-collapse: collapse;
    table-layout: fixed;
    word-break: break-word;
    overflow-wrap: break-word;
}
.table-formal th, .table-formal td,
.table-report th, .table-report td {
    vertical-align: top;
    padding: 10px 12px;
    line-height: 1.5;
    border: 1px solid #94a3b8;
    word-break: break-word;
    overflow-wrap: break-word;
}
.table-formal thead th,
.table-report thead th {
    position: sticky;
    top: 0;
    z-index: 5;
    background-color: #f1f5f9 !important;
    color: #0f172a;
    font-weight: 700;
    text-align: center;
    vertical-align: middle;
    box-shadow: inset 0 -2px 0 #94a3b8;
}

/* Specific Column Widths & Alignments */
.col-no { width: 4%; min-width: 40px; text-align: center; }
.col-masalah { width: 20%; min-width: 220px; text-align: left; }
.col-indikator { width: 16%; min-width: 160px; text-align: left; }
.col-tindakan { width: 32%; min-width: 280px; text-align: left; }
.col-waktu { width: 9%; min-width: 90px; text-align: center; }
.col-biaya { width: 10%; min-width: 110px; text-align: right; }
.col-pic { width: 10%; min-width: 100px; text-align: center; text-transform: capitalize; }
.col-aksi { width: 9%; min-width: 85px; text-align: center; }

/* Financial formatting */
.col-biaya-val {
    text-align: right !important;
    font-family: var(--bs-font-monospace, monospace);
    font-size: 0.8rem;
    padding-right: 14px !important;
}

/* PIC Capitalization */
.col-pic-val {
    text-align: center;
    text-transform: capitalize;
    font-size: 0.8rem;
}
```

- [ ] **Step 2: Verify template compilation**

```bash
python manage.py check
```
Expected: 0 issues.

---

### Task 3: Refactor Tables in `risiko_laporan_lengkap.html`

**Files:**
- Modify: `templates/akreditasi/risiko_laporan_lengkap.html`

**Key changes:**
1. **Load custom tags**: ensure `{% load akreditasi_tags %}` is at the top of the template.
2. **Table 3 (Penilaian Risiko Awal)**:
   - Apply `.col-no`, `.col-masalah`, `.col-score-param`, `.col-skor`, `.col-grade`, `.col-aksi`.
   - Wrap in `.table-sticky-wrapper`.
3. **Table 5 (Indikator Mutu Terkait Risiko)**:
   - Apply `.col-no`, `.col-masalah`, `.col-indikator`, `.col-target`, `.col-jenis`, `.col-aksi`.
   - Wrap in `.table-sticky-wrapper`.
4. **Table 6 (Rencana Aksi Mitigasi Risiko)**:
   - Apply `.col-no`, `.col-masalah`, `.col-indikator`, `.col-tindakan`, `.col-waktu`, `.col-biaya`, `.col-pic`, `.col-aksi`.
   - Wrap in `.table-sticky-wrapper`.
   - Apply `row.rencana_aksi|render_structured_plan`.
   - Change `Biaya` cell from `text-center small` to `col-biaya-val`.
   - Change `tfoot` total cell from `text-center` to `col-biaya-val`.
   - Change `PJ` cell to `col-pic-val`.
5. **Table 7 (Pelaksanaan Do)**:
   - Apply `.col-tindakan` and `row.pelaksanaan_do|render_structured_plan`.
   - Change `Biaya` cell to `col-biaya-val` (right-aligned).
   - Change `tfoot` total cell to `col-biaya-val`.
   - Change `PJ` cell to `col-pic-val`.
   - Wrap in `.table-sticky-wrapper`.
6. **Table 8 (Monitoring & Evaluasi)**:
   - Apply `row.rtl|render_structured_plan`.
   - Apply `text-transform: capitalize;` to PIC RTL.
   - Wrap in `.table-sticky-wrapper`.
7. **Single Risk View (Fase 2 Do table at line 385)**:
   - Update table padding, right-align costs, capitalize PIC.

- [ ] **Step 1: Apply changes to `templates/akreditasi/risiko_laporan_lengkap.html`**
- [ ] **Step 2: Run `python manage.py check` to verify template tags and syntax**
- [ ] **Step 3: Run existing tests to ensure no regressions**

```bash
python manage.py test akreditasi.tests_perencanaan_risiko -v2 2>&1 | grep -E "^Ran|^OK|FAIL"
```
Expected: PASS.

- [ ] **Step 4: Commit Task 3**

```bash
git add templates/akreditasi/risiko_laporan_lengkap.html
git commit -m "feat(ui): update table layouts, alignments, and sticky headers in risiko_laporan_lengkap"
```

---

### Task 4: Automated Verification & Full Test Suite

**Files:**
- Modify: `akreditasi/tests_perencanaan_risiko.py`

- [ ] **Step 1: Add assertions in `test_laporan_lengkap_unit_view` for new CSS classes & alignments**

```python
# Verify right-aligned cost styling exists in rendered report
self.assertIn('col-biaya-val', content)
self.assertIn('col-pic-val', content)
self.assertIn('table-sticky-wrapper', content)
```

- [ ] **Step 2: Run all test suites across the project**

```bash
python manage.py test akreditasi.tests_unit_kerja akreditasi.tests_perencanaan_risiko akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_mutu_charts akreditasi.tests_indikator_alur_integrasi -v2 2>&1 | grep -E "^Ran|^OK|FAIL"
```
Expected: All 68+ tests PASS.

- [ ] **Step 3: Commit Task 4**

```bash
git add akreditasi/tests_perencanaan_risiko.py
git commit -m "test: add assertions for table alignment and sticky layout in laporan lengkap"
```

---

### Task 5: Deploy & Verification on Vercel

- [ ] **Step 1: Push changes to GitHub master**

```bash
git push origin master
```

- [ ] **Step 2: Verify live deployment response**

```bash
curl -sI https://sim-akreditasi-django.vercel.app/ | grep "HTTP/"
```
Expected: `HTTP/2 200` or `302`.

- [ ] **Step 3: Mark plan complete in `docs/superpowers/plans/`**
