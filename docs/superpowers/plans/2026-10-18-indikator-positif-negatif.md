# Positive / Negative Indicators — Derive, Don't Duplicate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every place ARIMA shows or accepts a quality-indicator number must adapt to the indicator's polarity and measurement type: percentage indicators validate 0–100 and display `%`, negative-rate indicators display their real unit with helper text that a *low* value is success, and the target badge shows the correct comparator. Planned-in-perencanaan indicators must be the ones offered in monitoring/evaluation, filtered by the unit and the year.

**Architecture:** Nothing new is invented for polarity — `IndikatorMutu.arah_target` (`MIN`/`MAX`) already is the docx's `sifat_indikator`, and `operator_target` is a pure function of it, so it is rendered from the resolver, never stored. One genuinely new column is added, `tipe_pengukuran`, backfilled from the existing `satuan` free-text field, because the 0–100 validation rule needs a stable signal rather than a string comparison. The sync-from-planning behaviour is completed in `api_indikator_by_unit`, which already filters by unit and annotates `punya_data`.

**Status:** Not started. Analysis only — no code written yet.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, vanilla JS. One migration, no new pip package, no new endpoint.

**Spec:** `C:\Users\cubeb\Downloads\Perbaikan indictor mutu positif dan negative dalam arima.docx` — section 1 (schema: `sifat_indikator`, `tipe_pengukuran`, `operator_target`), section 2 (planning → evaluation sync), section 3 (positive vs negative achievement formulas), section 4 (dynamic input form, unit label, 0–100 validation, comparator badge).

## What the docx asks for, and what already exists

This is the central finding: **two of the three requested columns are already implemented, and storing the third would introduce a bug.**

| docx column | Existing equivalent | Verdict |
|---|---|---|
| `sifat_indikator` (`positif` / `negatif`) | `IndikatorMutu.arah_target` — `MIN` = higher is better, `MAX` = lower is better, with an explicit help_text (`akreditasi/risiko_models.py:573-578`), migration `0037`, wired through `RisikoUnit.capaian_evaluasi`, `CatatanIndikator.tercapai`, the monev table, all report/CSV exports, and the dashboard legend | **Already done.** Adding `sifat_indikator` would create a second source of truth for one fact. |
| `operator_target` (`>=` for positive, `<=` for negative) | A pure function of `arah_target`. Rendered as `&ge;` / `&le;` in the dashboard legend (`templates/akreditasi/dashboard.html:523,526,532,535`), the monev table, and the report banner | **Never store it.** A stored comparator will silently desync from `arah_target` — the exact class of bug this codebase just spent commit `69d0440` cleaning up. Render it. |
| `tipe_pengukuran` (`%` / `angka_absolut`) | Only implied by the free-text `satuan` CharField, `default='%'` (`akreditasi/risiko_models.py:568`) | **Genuinely new.** A free-text field cannot carry a validation rule. Add it. |

The repo has precedent on both sides of this decision: `RisikoUnit.jenis_dokumen_capaian` (migration `0039`) is a stored derived field, carrying a comment that its correctness depends on `jenis_risiko` staying in sync. For a one-to-one function of an existing enum, the lesson from that comment is to derive instead.

## Global Constraints

- **One source of truth for polarity.** Any task here that needs "is this indicator positive or negative" reads `arah_target`. Writing `if sifat == 'positif'` anywhere is a failure of this plan.
- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `1,5`; one comma inside `<script>` kills the whole block (bugs `84c20ce`, `c4c2a3c`). `indikator_dashboard.html` gained `{% load static l10n %}` for exactly this — keep it.
- **Do not change what a percentage is.** `CatatanIndikator.nilai_capaian` is `(numerator / denominator) * 100` and stays that way; a `tipe_pengukuran` of `absolut` changes the *label and the validation*, not the arithmetic. Changing the arithmetic would silently reinterpret every stored number.
- **Validation must be additive.** Existing rows are not re-validated on read. A percentage indicator showing 145% today must keep rendering; it should fail only at the next save.
- **This plan must not collide with `2026-10-18-inm-unit-access-matrix.md`.** That plan adds `IndikatorUnitTerlibat` (unit↔INM mapping) and a `CatatanIndikator.unit` column. Both plans touch `api_indikator_by_unit` and the indicator form. Sequence this plan *after* the access-matrix plan lands, or rebase onto its `0041`/`0042` migrations — do not create two competing `0041`s.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — baseline **161 tests, 0 failures** (the two pre-existing AI failures are fixed in the same push).
- Work on `master`; commit after the last task.

## Verified code facts (read 2026-10-18)

| Fact | Where |
|---|---|
| `arah_target` choices: `MIN` ("higher is better") / `MAX` ("lower is better, e.g. waktu tunggu"), help_text present | `akreditasi/risiko_models.py:545-548`, `:573-578` |
| `target_nilai` is `DecimalField(max_digits=5, decimal_places=2)` → max 999.99 | `akreditasi/risiko_models.py:567` |
| `satuan` is `CharField(max_length=20, default='%')`, free text, never validated | `akreditasi/risiko_models.py:568` |
| Polarity already read in the resolver, the note property, the monev table, 4 report/CSV paths, and the dashboard legend | `risiko_models.py:216,640,654`, `risiko_views.py`, `dashboard.html:523-535` |
| `indikator_input_capaian` validates only `den > 0`, file type and file size — **no 0–100 range check, no unit check** | `akreditasi/indikator_views.py:396-440` |
| Same function logs a hardcoded percent sign: `f'Capaian {kode} bulan {bulan}/{tahun}: {float(...):.1f}%'` | `akreditasi/indikator_views.py:436` |
| `api_indikator_by_unit` filters by `aktif`, `unit_id`, `jenis`, annotates `punya_data` | `akreditasi/risiko_views.py:170-205` |
| Same function contains the identical unit-fallback block **twice**, at `:193-196` and `:202-205` | `akreditasi/risiko_views.py` |
| No `sifat_indikator`, `tipe_pengukuran`, or `operator_target` symbol exists anywhere in the repo (grep over `*.py` + `*.html`, excluding venv) | — |
| `CatatanIndikator.nilai_capaian` is `(num / den) * 100`; `tercapai` already honours `arah_target` | `akreditasi/risiko_models.py:629-641` |
| Latest migration `0040_risikounit_arah_capaian`; the access-matrix plan claims `0041`/`0042` | `akreditasi/migrations/` |

**The docx's "Terencana" status does not exist.** Section 2 asks for `Status indikator = Terencana`. There is no status field on `IndikatorMutu` and no perencanaan-side indicator list to be *in* — the planning module tracks risks (`RisikoUnit`), not indicators. The docx's intent (only show indicators the unit actually planned) is served today by `IndikatorMutu.unit` plus `punya_data`, and properly served by the `IndikatorUnitTerlibat` mapping in the access-matrix plan. This plan should not add a third parallel concept.

---

### Task 1: `tipe_pengukuran` field + backfill

- [ ] **Step 1: Add the field** in `akreditasi/risiko_models.py`, right after `satuan`:

  ```python
  TIPE_PENGUKURAN_CHOICES = [
      ('persen', 'Persentase (%)'),
      ('absolut', 'Angka absolut / rate'),
  ]
  ```

  ```python
  tipe_pengukuran = models.CharField(
      'Tipe Pengukuran', max_length=10, choices=TIPE_PENGUKURAN_CHOICES,
      default='persen',
      help_text='persen → tampilan %, validasi 0–100. absolut → tampilan satuan '
                'sebenarnya (per mil, per hari, jumlah kasus), tanpa batas atas.'
  )
  ```

- [ ] **Step 2: Migration `0043`** with a `RunPython` backfill — `persen` where `satuan == '%'` or empty, `absolut` otherwise. Print a summary of how many rows took each branch. The reverse function is a no-op (the field has a default).

- [ ] **Step 3: Expose it in the admin/matrix page** if one exists for indicators, alongside `arah_target`.

- [ ] **Step 4: Tests** in a new `akreditasi/tests_indikator_sifat.py`:
  - `test_backfill_marks_percent_satuan_as_persen`
  - `test_backfill_marks_permil_satuan_as_absolut`
  - `test_default_is_persen_for_new_indicator`

---

### Task 2: Validation and labelling in the input form

- [ ] **Step 1: Range validation, only for percentage indicators**
  In `indikator_input_capaian`, after computing the capaian, reject a percentage whose computed value is outside 0–100 with a message naming the actual number and the unit. Do **not** apply an upper bound to `absolut` — a per-mil rate has no ceiling, and inventing one is how a valid entry gets rejected in production.

- [ ] **Step 2: Fix the hardcoded percent in the audit log**
  `akreditasi/indikator_views.py:436` appends `%` regardless of the indicator's unit. Use the indicator's `satuan`, or reuse the resolver's `satuan` so the log and the screen agree.

- [ ] **Step 3: Dynamic form behaviour**
  When the chosen indicator is `absolut`, show the real unit in the input label and a helper line — "nilai rendah menandakan keberhasilan" — driven by `arah_target`. When it is `persen`, keep `%` and the 0–100 hint.

- [ ] **Step 4: Comparator badge on the target widget**
  The spec's "widget hijau di kanan atas" must show `≥` for `MIN` and `≤` for `MAX`. Render from `arah_target`; do not add an `operator_target` column.

- [ ] **Step 5: Tests** — one assertion that a percentage of 145 is rejected, one that a per-mil rate above 100 is accepted, one that the badge renders `&le;` for a `MAX` indicator.

---

### Task 3: Planning → evaluation sync

- [ ] **Step 1: De-duplicate `api_indikator_by_unit`**
  The identical unit-fallback block appears twice (`akreditasi/risiko_views.py:193-196` and `:202-205`). Keep one.

- [ ] **Step 2: Keep the ordering that makes the fallback safe**
  The fallback must not run *before* `punya_data` is annotated, otherwise the fallback list ships without the marker the dashboard depends on.

- [ ] **Step 3: Tests** — a unit with no indicators of its own still receives the national set, with `punya_data` present on every item.

---

### Task 4: Render-polarity audit

- [ ] **Step 1: Grep every render path for a hardcoded comparator**
  `grep -n "≥\|&ge;\|>=" templates/akreditasi/*.html` and confirm each occurrence derives from `arah_target`. Plan B already fixed the dashboard legend and the report banner; this step is the belt-and-braces pass that finds any the earlier plans missed.

- [ ] **Step 2: Run the full suite, tick every checkbox, commit**

---

## Review Focus

- **The temptation this spec creates is the bug.** Three new columns are requested; two of them restate an existing enum and one restates a function of it. The plan resists all three and adds exactly one column, with the reasoning above recorded so the next reader does not "helpfully" add the other two.
- **Percentage validation must not reject historical data.** It runs on save, never on read, and never on the aggregate queries that render charts.
- **Migration numbering depends on the access-matrix plan.** `0043` assumes `0041`/`0042` are taken. If the other plan has not landed, take the next free number rather than leaving a gap or a collision.
- **`tipe_pengukuran` is derived from `satuan` once, at migration time.** After that they can drift, since `satuan` stays editable. The field becomes authoritative for behaviour; `satuan` remains the display label. Say so in the help_text so an operator editing `satuan` does not expect validation to follow.
