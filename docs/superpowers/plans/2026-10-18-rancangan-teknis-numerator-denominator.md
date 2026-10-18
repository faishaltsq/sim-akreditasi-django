# ARIMA v2.6 — Numerator / Denominator Model, Polarity Filter, and the Factor Multiplier

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every quality indicator compute, validate, and display its achievement by the measurement shape it actually has. A per-mille VAP rate of 5/1000 ventilator-days must read **5.0‰ — Tercapai**, not 0.5% — red. The evaluation form must let the user start from polarity (Positif / Negatif), see only matching indicators, and watch the achievement value compute live from numerator ÷ denominator before saving.

**Architecture:** One column plus one number decide the arithmetic: `tipe_pengukuran` (`persen` | `rate_absolut`) and `faktor_pengali` (1, 100, 1000, or 100000). `CatatanIndikator.nilai_capaian` stops hardcoding `* 100` and reads the indicator's shape instead. Polarity is *not* a new column — `IndikatorMutu.arah_target` is already the docx's `sifat_indikator`, and `operator_target` stays a rendered function of it. The evaluation form gains a polarity radio that drives `api_indikator_by_unit` through a new `sifat` query param, and a live numerator ÷ denominator preview engine.

**Status:** Analysis only — no code written.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, vanilla JS. One migration, no new pip package, one new query param on an existing endpoint.

**Spec:** `C:\Users\cubeb\Downloads\format rancangan teknis yang terstruktur model numerator dan denumerator.docx` (ARIMA v2.6) — §1 schema (`sifat_indikator`, `tipe_pengukuran`, `operator_target`), §2 polarity radio + cascading AJAX dropdown, §3 numerator/denominator input and the auto-calculation engine with **Faktor Pengali**, §4 automatic Tercapai / Tidak Tercapai.

## Reconciliation with the sibling plan

`2026-10-18-indikator-positif-negatif.md` (commit `82043fb`) already covers this spec's §1 and §4 from an earlier docx. Agreeing with it:

| docx ask | Existing | Verdict |
|---|---|---|
| `sifat_indikator` (`positif`/`negatif`) | `IndikatorMutu.arah_target` — `MIN` = higher is better, `MAX` = lower is better (`akreditasi/risiko_models.py:545-548`, `:573-578`), migration `0037`, read by `RisikoUnit.capaian_evaluasi` (`:215`), `CatatanIndikator.tercapai` (`:637-644`), the monev table, 4 report/CSV paths, the dashboard legend | **Done.** Adding it = second source of truth for one fact. |
| `operator_target` (`>=` / `<=`) | Pure function of `arah_target`, rendered as `&ge;`/`&le;` | **Render, never store.** A stored comparator desyncs silently. |
| §4 auto Tercapai/Tidak Tercapai | `CatatanIndikator.tercapai` + `RisikoUnit.capaian_evaluasi` | **Done** — except the arithmetic it compares is wrong for rates. See below. |
| §3 numerator/denominator **input** | `templates/akreditasi/indikator_input_capaian.html:69-80`, `akreditasi/indikator_views.py:396-440` (`CatatanIndikator.nilai_numerator` / `nilai_denominator`, `risiko_models.py:612-613`) | **Inputs exist.** What is missing is the live preview and the multiplier. |

**Where the sibling plan and this one conflict — and how it resolves.** Its Global Constraint says *"Do not change what a percentage is … Changing the arithmetic would silently reinterpret every stored number."* That constraint is right about percentages and incomplete about everything else: `CatatanIndikator.nilai_capaian` (`risiko_models.py:630-633`) is `(num / den) * 100` for **all** indicators, so a per-mille indicator is computed 10× too small. This plan keeps `persen` at ×100 (nothing reinterpreted) and gives non-percentage rows the factor their unit implies. That is not a reinterpretation of a percentage; it is the first correct reading of a rate.

## The one real decision: Faktor Pengali

`faktor_pengali` is a stored `DecimalField`, not derived from `satuan`. Derivation was considered and rejected: `satuan` is an unvalidated `CharField(max_length=20, default='%')` and the live values are `%` (199), `‰` (8), `Menit` (2), `Jam` (1) — `Menit` and `Jam` are **averages, not rates**, and they need factor 1, which no string rule states. The docx names two types; the data needs three behaviours, and `faktor_pengali` delivers all three without a third enum value:

| `satuan` | `tipe_pengukuran` | `faktor_pengali` | meaning |
|---|---|---|---|
| `%` or empty | `persen` | 100 | (N/D) × 100 |
| `‰` | `rate_absolut` | 1000 | (N/D) × 1000 |
| `Menit`, `Jam`, `Hari`, `Kasus` | `rate_absolut` | 1 | (N/D) × 1 — a mean or a count |

`faktor_pengali` is authoritative for the arithmetic; `satuan` stays the display label only. An operator who edits `satuan` does not move the arithmetic — the help_text says so.

## Global Constraints

- **One source of truth for polarity.** Anything here needing "positive or negative" reads `arah_target`. `if sifat == 'positif'` written anywhere is a plan failure.
- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `1,5`; one comma inside `<script>` kills the whole block (bugs `84c20ce`, `c4c2a3c`).
- **Percentage arithmetic is untouched.** `persen` keeps (N/D) × 100. Only `rate_absolut` changes, and only for the 11 rows whose `satuan` is not `%`.
- **Denominator of 0 is already rejected** (`indikator_views.py:411`) and stays rejected. The JS preview must show `—` and never `Infinity`/`NaN`.
- **Validation runs on save, never on read.** 588 stored `CatatanIndikator` rows must keep rendering exactly as they do today except where the multiplier now makes them correct.
- **Migration numbering.** Latest on disk here is `0040_risikounit_arah_capaian`. `2026-10-18-inm-unit-access-matrix.md` claims `0041`/`0042` but has not landed (no files). Take the next free number, then rebase — do not ship two competing `0041`s.
- **This plan supersedes the sibling plan's arithmetic task, not its validation task.** Its `tipe_pengukuran` field, 0–100 validation, and comparator badge all still apply; this plan adds the column's real payload.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Baseline: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — **159 tests, OK** (measured on `master` @ `82043fb`).
- Work on `master`; commit after the last task.

## Verified facts (read 2026-10-18, primary tree)

| Fact | Value |
|---|---|
| `IndikatorMutu` active | 210 |
| `satuan` distribution | `%` 199, `‰` 8, `Menit` 2, `Jam` 1 |
| **Rows needing a factor other than 100** | **11** |
| `arah_target` | `MIN` 116 / `MAX` 94 — already correct, not the all-`MIN` state commit `69d0440` found |
| `CatatanIndikator` rows | 588 |
| `sifat_indikator`, `tipe_pengukuran`, `operator_target`, `faktor_pengali` symbols in repo | none |
| `IndikatorMutu.numerator` / `denominator` | `CharField(300)` — indicator *definitions*, not numbers (`risiko_models.py:565-566`) |
| Numeric N/D live on | `CatatanIndikator.nilai_numerator` / `nilai_denominator`, `Decimal(10,2)` (`:612-613`) |
| `nilai_capaian` | `(num / den) * 100`, hardcoded (`:630-633`) |
| `api_indikator_by_unit` | `risiko_views.py:170`; filters `aktif`, `unit_id`, `jenis`; annotates `punya_data`; **unit-fallback block duplicated at `:191-194` and `:201-204`**; **no polarity param** |
| Eval-form indicator select | `templates/akreditasi/risiko_evaluasi.html:212` (`#link-indikator-select`), JS at `:639-703`, already reads `opt.dataset.arah` |
| Input form | `indikator_input_capaian.html:69-80` — two number inputs, no preview |
| `target_nilai` | `DecimalField(max_digits=5, decimal_places=2)` → max 999.99 |

**Concrete broken row.** `IMP-ICU-01 Angka Kejadian VAP`, `satuan='‰'`, `target_nilai=5.00`, `arah_target='MAX'`. Numerator 5, denominator 1000 ventilator-days: the true rate is 5.0‰ (target met exactly). `nilai_capaian` returns `0.5`, the comparison is `0.5 <= 5.00` → *Tercapai* by accident today, but every chart, every monev cell, every CSV export shows `0.5` where the unit says `‰`. Flip the numerator to 50 (a genuine 50‰ outbreak) and it still computes `5.0` — still *Tercapai*. **The false negative and the false positive are the same bug.** All 8 `‰` rows share it.

---

### Task 1: `tipe_pengukuran` + `faktor_pengali` and the corrected `nilai_capaian`

- [ ] **Step 1: Add both columns** on `IndikatorMutu`, immediately after `satuan` (`akreditasi/risiko_models.py:568`):

  ```python
  TIPE_PENGUKURAN_CHOICES = [
      ('persen',      'Persentase (%)'),
      ('rate_absolut', 'Angka absolut / rate (per mil, rerata, jumlah kasus)'),
  ]
  FAKTOR_PENGALI_CHOICES = [
      (Decimal('1'),      '× 1  (rerata / jumlah kasus)'),
      (Decimal('100'),    '× 100  (persentase)'),
      (Decimal('1000'),   '× 1000  (per mil ‰)'),
      (Decimal('100000'), '× 100.000  (per 100.000)'),
  ]
  ```

  ```python
  tipe_pengukuran = models.CharField(
      'Tipe Pengukuran', max_length=15, choices=TIPE_PENGUKURAN_CHOICES,
      default='persen',
      help_text='persen → (N/D) × 100, validasi 0–100. rate_absolut → '
                '(N/D) × faktor_pengali, tanpa batas atas.'
  )
  faktor_pengali = models.DecimalField(
      'Faktor Pengali', max_digits=7, decimal_places=0,
      default=Decimal('100'), choices=FAKTOR_PENGALI_CHOICES,
      help_text='Pengali pada rumus capaian. Autoritatif untuk aritmetika; '
                'kolom satuan hanya label tampilan dan tidak mengubah perhitungan.'
  )
  ```

- [ ] **Step 2: Migration with a `RunPython` backfill.** Branch on `satuan`: `''`/`%` → (`persen`, 100); `‰` → (`rate_absolut`, 1000); anything else → (`rate_absolut`, 1). Print a per-branch row count. `reverse` is a no-op — both fields carry defaults.

- [ ] **Step 3: Fix `nilai_capaian`** (`akreditasi/risiko_models.py:629-633`) to read the shape:

  ```python
  @property
  def nilai_capaian(self):
      if not self.nilai_denominator or self.nilai_denominator <= 0:
          return Decimal('0')
      ind = self.indikator
      if getattr(ind, 'tipe_pengukuran', 'persen') == 'persen':
          faktor = Decimal('100')
      else:
          faktor = getattr(ind, 'faktor_pengali', Decimal('100')) or Decimal('100')
      return (self.nilai_numerator / self.nilai_denominator) * faktor
  ```

  `persen` still resolves to 100 from the literal, not from the column — so a mis-set `faktor_pengali` can never alter a percentage. The `getattr` defaults keep old rows and fixture-built indicators working when the column is absent.

- [ ] **Step 4: Tests** in `akreditasi/tests_indikator_sifat.py` (new): `persen` still returns ×100; `‰` with factor 1000 returns 5.0 for 5/1000; `Menit` with factor 1 returns the raw mean; denominator ≤ 0 still returns `Decimal('0')`; a percentage with a deliberately wrong `faktor_pengali=1000` still returns ×100.

- [ ] **Step 5: Run the module and the full suite.**

  ```bash
  .venv/Scripts/python.exe manage.py test akreditasi.tests_indikator_sifat -v1
  .venv/Scripts/python.exe manage.py test akreditasi -v1
  ```

---

### Task 2: Audit command for the backfill

- [ ] **Step 1: Read-only command** `akreditasi/management/commands/audit_tipe_pengukuran.py` — same shape as the proven `audit_arah_target`. Print each row's `kode`, `satuan`, current `satuan`, proposed `tipe_pengukuran` + `faktor_pengali`, and its 2026 `CatatanIndikator` count so the operator sees how many stored values will change reading. `--apply` writes; without it, dry run only.

- [ ] **Step 2: Run against production and read the 11 rows before applying.**

  ```bash
  .venv/Scripts/python.exe manage.py audit_tipe_pengukuran
  .venv/Scripts/python.exe manage.py audit_tipe_pengukuran --apply
  ```

  Expected: 199 `persen`/100, 8 `rate_absolut`/1000, 3 `rate_absolut`/1. If any row lands in an unexpected bucket, fix it in the indicator form, not in the migration.

---

### Task 3: Polarity radio + cascading dropdown in the evaluation form

- [ ] **Step 1: Add a `sifat` param to `api_indikator_by_unit`** (`akreditasi/risiko_views.py:170`), accepting `min`/`max`, applied *after* the unit filter and *before* the `punya_data` annotation so every returned item keeps the marker.

- [ ] **Step 2: De-duplicate the unit-fallback block** — the identical code sits at `:191-194` and `:201-204`. Keep the second. The first fires and replaces `qs` before `if tahun:` annotates, so deleting either keeps `punya_data` intact; keeping the later one leaves the annotate where a reader expects it. Do not move the fallback above the annotate — that is the one ordering that would ship a list without the marker the dashboard consumes.

- [ ] **Step 3: Add the radio** above `#link-indikator-select` in `templates/akreditasi/risiko_evaluasi.html:207`:

  ```html
  <div class="btn-group btn-group-sm w-100" role="group" aria-label="Sifat indikator">
    <input type="radio" class="btn-check" name="sifat_filter" id="sf-positif" value="min">
    <label class="btn btn-outline-success" for="sf-positif"><i class="bi bi-arrow-up-circle me-1"></i>Positif</label>
    <input type="radio" class="btn-check" name="sifat_filter" id="sf-negatif" value="max">
    <label class="btn btn-outline-danger" for="sf-negatif"><i class="bi bi-arrow-down-circle me-1"></i>Negatif</label>
  </div>
  ```

  Values are `min`/`max` — the wire format of `arah_target`. Labeling the *buttons* positif/negatif while the *value* stays `MIN`/`MAX` is the whole point: the docx's vocabulary reaches the UI without a second enum entering the database.

- [ ] **Step 4: Wire the filter in JS** next to the existing `linkSelect` handler (`risiko_evaluasi.html:639`): on radio change, refetch with `?sifat=`, repopulate, clear the selection, and re-run `evaluateCapaian()`. Keep the existing `opt.dataset.arah` read (`:655`) so the target comparator follows the choice.

- [ ] **Step 5: Reset the indicator dropdown when the radio changes** — a user who filtered to Negatif must not be able to submit a Positif indicator that was selected before the filter was applied.

- [ ] **Step 6: Tests** — `sifat=min` returns only `MIN` rows; `sifat=max` only `MAX`; the param is ignored by the risk form that does not send it (regression); switching the radio empties the select.

---

### Task 4: The auto-calculation engine

- [ ] **Step 1: Live preview on the input form** (`templates/akreditasi/indikator_input_capaian.html:69-80`). Replace the static form-text at `:79` with a computed preview card driven by `{{ ind.tipe_pengukuran|unlocalize }}` and `{{ ind.faktor_pengali|unlocalize }}` injected once into a JS constant. Formula shown to the user mirrors the server exactly: `persen` → `Capaian = (N / D) × 100`; `rate_absolut` → `Capaian = (N / D) × {{ faktor }}`.

- [ ] **Step 2: Guard the denominator.** On empty or `<= 0`, the preview shows `—` and the save button stays enabled only if the server would also reject — the form already posts `min="0.01"`, so the JS guard is display-only, not a second validation layer.

- [ ] **Step 3: Unit-aware output.** The preview value carries `{{ ind.satuan }}`, not a hardcoded `%`.

- [ ] **Step 4: Server-side validation matches the preview** in `indikator_input_capaian` (`akreditasi/indikator_views.py:396-440`): reject a `persen` indicator whose computed value falls outside 0–100, naming the actual number; apply **no** upper bound to `rate_absolut` — a per-mille rate or an outage count has no ceiling, and inventing one is how a valid production entry gets refused.

- [ ] **Step 5: Fix the hardcoded `%` in the audit log** at `akreditasi/indikator_views.py:436` — use the indicator's `satuan` so the log agrees with the screen.

- [ ] **Step 6: `node --check` on every touched `<script>` block.**

  ```bash
  .venv/Scripts/python.exe manage.py shell -c "
  import re
  for f in ('templates/akreditasi/indikator_input_capaian.html',
            'templates/akreditasi/risiko_evaluasi.html'):
      html = open(f, encoding='utf-8').read()
      js = '\n'.join(re.findall(r'<script>(.*?)</script>', html, re.S))
      open('/tmp/_chk.js','w',encoding='utf-8').write(js)
      print(f)
  " && node --check /tmp/_chk.js
  ```

- [ ] **Step 7: Tests** — 145% rejected for a `persen` indicator; 150 accepted for a `‰` indicator; the preview renders `5.0` for 5/1000 at factor 1000; denominator 0 leaves the preview blank and the POST fails with the existing message.

---

### Task 5: Target label and comparator badge

- [ ] **Step 1:** The target widget on both forms shows `{{ operator }} {{ target_nilai }} {{ satuan }}` with `operator` derived from `arah_target` (`&ge;` for `MIN`, `&le;` for `MAX`) — never from a column.

- [ ] **Step 2: The green badge the docx asks for** sits top-right of the indicator summary and reads `Tercapai` / `Belum Tercapai` live, reusing the existing `evaluateCapaian()` in `risiko_evaluasi.html:664` and adding the same read-only badge to `indikator_input_capaian.html`.

- [ ] **Step 3: Tests** — a `MAX` indicator renders `&le;` and computes `Tercapai` at exactly the target; a `MIN` indicator at exactly the target also renders `Tercapai` (the boundary is inclusive on both sides).

---

### Task 6: Commit and deploy

- [ ] **Step 1:** Full suite, then render-diff one `‰` indicator's detail page before and after — the only expected change is the capaian number and its status.

- [ ] **Step 2:**

  ```bash
  git add akreditasi/risiko_models.py akreditasi/indikator_views.py akreditasi/risiko_views.py \
          akreditasi/migrations/0041_*.py akreditasi/management/commands/audit_tipe_pengukuran.py \
          templates/akreditasi/indikator_input_capaian.html templates/akreditasi/risiko_evaluasi.html \
          akreditasi/tests_indikator_sifat.py docs/superpowers/plans/2026-10-18-rancangan-teknis-numerator-denominator.md
  git commit -m "fix(indikator): compute rate indicators with their real multiplier

  nilai_capaian multiplied every indicator by 100, so the 8 per-mille rows
  (VAP, ISK, Phlebitis, UGD mortality) read 10x too small on every chart,
  monev cell and CSV export, and a 50-per-mille outbreak still rendered
  Tercapai. tipe_pengukuran + faktor_pengali now carry the shape: percent
  keeps x100, per-mille uses x1000, means and counts use x1. The evaluation
  form gains a polarity radio driving api_indikator_by_unit, and the input
  form previews the capaian live in the indicator's own unit."
  git push origin master
  ```

---

## Review Focus

- **The multiplier is the whole risk surface.** 588 stored readings are rendered through `nilai_capaian`. Before Task 1 Step 3 lands, capture the current rendered value of the 8 `‰` indicators; after, every one of them must be exactly 10× larger and nothing else may move.
- **`persen` must resolve its factor from the literal `100`, not the column.** A stored `faktor_pengali` on a percentage row is display metadata, not arithmetic.
- **The two-column split is deliberate.** `tipe_pengukuran` decides *which branch*; `faktor_pengali` decides *by how much*. Merging them into one enum would need a new value for every future unit (`per 10.000`, `per hari rawat`) — exactly the churn the field exists to avoid.
- **`Menit` and `Jam` are averages, not rates.** They get `rate_absolut` with factor 1. Anyone "simplifying" the backfill to treat non-`%` as per-mille will corrupt 3 rows.
- **The polarity radio must not become a second polarity store.** It sends `min`/`max`; it never writes. If a task here starts writing `sifat` to the model, it is wrong.
- **`api_indikator_by_unit` serves two callers** — the risk form and the dashboard filter. The new `sifat` param must be optional and ignored by the caller that omits it.
- **The sibling plan's remaining tasks still apply** — 0–100 validation, the comparator badge, the render-polarity audit. This plan supplies the arithmetic those tasks assume is correct.
