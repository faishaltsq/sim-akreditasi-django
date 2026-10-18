# INM Unit Access Matrix — Role-Based Unit Mapping, 5 Levels, Auto-Hide, Flagging

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Visibility and data entry for the 13 national quality indicators (INM) is restricted per unit through a stored mapping table, so a unit only sees and enters the INM it is genuinely involved in. Below-target units get an explicit red flag with a direct route into the PDCA cycle.

**Architecture:** One new through-model `IndikatorUnitTerlibat` (db table `inm_unit_mapping`) is the single source of truth for *which unit may see/input which INM*. `CatatanIndikator` gains a `unit` FK so several units can record a realisation of the same indicator. One queryset helper `indikator_qs_for_user()` decides access once and is used by every INM read path (dashboard, trend API, comparison API, catalogue API). Everything else — flagging, polarity, gap — already exists in `RisikoUnit.capaian_evaluasi` and `IndikatorMutu.arah_target` (shipped in `69d0440`).

**Status:** Not started. Analysis only — no code written yet.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, vanilla JS. Two migrations, no new pip package, no new endpoint beyond one admin matrix page.

**Spec:** `C:\Users\cubeb\Downloads\tambahan Tentang hak akses dan unit terlibat indicator mutu nasional 4.07.docx` — table 0 (involved/excluded unit matrix, 5 rows), table 1 (full 13-row INM table with PJ unit and involved units), section "Alur Visualisasi Level 1 – Level 5", section "Logika Backend untuk Restriksi Akses", section "Perubahan Workflow Operasional Pengguna".

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `1,5`; a single comma inside `<script>` kills the whole block (bugs `84c20ce`, `c4c2a3c`). Every template touched here must `{% load l10n %}` first — `risiko_monitoring_evaluasi.html` hit exactly this on 2026-10-18 (`Invalid filter: 'unlocalize'`).
- **Empty mapping must mean "unrestricted", not "nothing visible".** Production currently has zero mapping rows. A unit with no mapping must therefore see today's full list, or the whole INM menu disappears for every user the moment this ships. Auto-hide only applies once a mapping exists for that unit.
- **The mapping filters *visibility*; it must never silently widen authorization.** `profile.is_unit_scoped` keeps its meaning. An unmapped unit losing a menu item is the intended behaviour; a mapped unit gaining an edit right it did not have is not.
- **`CatatanIndikator.unit` backfill must be lossless.** 588 local / 432+156 production rows exist under `unique_together ('indikator','bulan','tahun')`. Every row backfills to `indikator.unit_id`; the migration must be idempotent and leave no `unit IS NULL` row that was previously valid.
- **Reuse the polarity resolver. Do not write a second status formula.** `RisikoUnit.capaian_evaluasi` (`akreditasi/risiko_models.py`) already owns `(target, arah, status, gap)`; `CatatanIndikator.tercapai` already honours `arah_target`. The flagging badge in this plan reads those, and adds no arithmetic of its own.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — baseline **159 tests, 2 pre-existing failures** (`tests_ai.EndpointAIIntegrationTest.test_anon_user_redirected` expects 302 but the view now returns 401; `tests_manajemen_risiko_515...test_api_ai_analisis_masalah_risiko_validation` expects 400 but the AI rate limiter returns 429). Neither is caused by this work; do not fix them here and do not let them hide a new failure — compare the failure list, not just the count.
- Work on `master`; commit after the last task.

## Verified code facts (read 2026-10-18)

| Fact | Where |
|---|---|
| `IndikatorMutu.unit` is a **single nullable FK** to `UnitKerja` — one PIC unit, not many | `akreditasi/risiko_models.py:562` |
| `IndikatorMutu.jenis` choices include `INM`, `IMRS`, `IMU` plus legacy `IMP_RS`, `IMP_UNIT`, `NASIONAL` | `akreditasi/risiko_models.py:534-543` |
| `IndikatorMutu.arah_target` choices: `MIN` (higher is better) / `MAX` (lower is better) | `akreditasi/risiko_models.py:545-548` |
| `CatatanIndikator` has **no unit column**; `unique_together ('indikator','bulan','tahun')` | `akreditasi/risiko_models.py:606-624` |
| `CatatanIndikator.tercapai` already reads `arah_target` | `akreditasi/risiko_models.py:636-641` |
| `profil_unit_id` does **not** exist anywhere in this repo (grep over `*.py` excluding venv/migrations: 0 hits) | — |
| No `ManyToManyField` exists in `models.py` or `risiko_models.py` | `akreditasi/models.py`, `akreditasi/risiko_models.py` |
| `UnitKerja` is a self-referencing tree (`parent`, `level`), typed by `tipe_unit` (`PIMPINAN`, `DIREKTURAT`, `KOMITE`, `SPI`, `BAGIAN`, `INSTALASI`, `KSM`, `RUANGAN`, `DEPO`, `LAINNYA`) | `akreditasi/models.py:20-49` |
| Unit scoping today is role-based: `Profile.is_unit_scoped` = not superadmin/`SUPER_ADMIN`/`ADMIN_RS`/`DIREKTUR` and has `unit_kerja` | `accounts/models.py:177-182` |
| INM read paths: `indikator_views.indikator_dashboard`, `api_indikator_tren`, `api_indikator_komparasi_unit`, `views.api_mutu_indikator`, `views.dashboard` | `akreditasi/urls.py:11,98,103,104,75` |
| Latest migration is `0040_risikounit_arah_capaian` | `akreditasi/migrations/` |

**The structural gap the docx exposes:** the spec's Level 3/4 model assumes each involved unit types its own realisation for a shared INM (e.g. Kepatuhan Kebersihan Tangan is measured in every clinical unit). With `unique_together ('indikator','bulan','tahun')` and no `unit` on the note, only one number per indicator per month is possible, owned by the indicator's single PIC unit. A mapping table alone would therefore hide indicators without ever letting the right units enter data. Both are required, and the note change is the riskier half.

## Production numbers (read 2026-10-17, Supabase `gwaeuzbbdawbekrmrvfd`)

| Fact | Value |
|---|---|
| `akreditasi_indikatormutu` active | 367 (`IMP_UNIT` 219, `IMP_RS` 108, `NASIONAL` 40) |
| `arah_target` | `MIN` 367, `MAX` 0 — uniformly wrong, audit command in `69d0440` reports candidates |
| `CatatanIndikator` 2026 | 588 (`IMP_RS` 432, `NASIONAL` 156) |
| `RisikoUnit` | 448 rows / 100 linked to an indicator (local dev) |
| `UnitKerja` | 218 (local dev) |

Do not size queries or write assertions against these counts: tests build their own fixtures.

---

### Task 1: `IndikatorUnitTerlibat` mapping model + `inm_unit_mapping`

Create the through-model the spec asks for, next to the indicator catalogue.

- [ ] **Step 1: Add the model**
  In `akreditasi/risiko_models.py`, after `CatatanIndikator`:

  ```python
  class IndikatorUnitTerlibat(models.Model):
      """Pemetaan INM vs Unit Terlibat (spec 4.07: tabel `inm_unit_mapping`).

      Menentukan unit mana yang boleh melihat dan menginput suatu INM.
      Baris kosong berarti belum dipetakan → perilaku tidak berubah (lihat
      Global Constraints: auto-hide hanya aktif setelah mapping ada).
      """

      indikator = models.ForeignKey(
          IndikatorMutu, on_delete=models.CASCADE, related_name='unit_terlibat'
      )
      unit = models.ForeignKey(
          UnitKerja, on_delete=models.CASCADE, related_name='indikator_terlibat',
          verbose_name='Unit Terlibat'
      )
      is_pic_utama = models.BooleanField(
          'Unit PJ', default=False,
          help_text='Unit penanggung jawab master data untuk INM ini.'
      )
      boleh_input = models.BooleanField('Boleh Input Capaian', default=True)
      created_at = models.DateTimeField(auto_now_add=True)

      class Meta:
          verbose_name = 'Unit Terlibat Indikator'
          verbose_name_plural = 'Unit Terlibat Indikator'
          unique_together = [('indikator', 'unit')]
          ordering = ['indikator_id', 'unit_id']

      def __str__(self):
          return f"{self.indikator.kode_indikator} — {self.unit.code}"
  ```

- [ ] **Step 2: Migration `0041`**
  `.venv/Scripts/python.exe manage.py makemigrations akreditasi -n inm_unit_mapping`
  Then add a `RunPython` backfill that mirrors `IndikatorMutu.unit` into the mapping so no existing indicator starts out invisible:

  ```python
  def seed_pic_units(apps, schema_editor):
      IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')
      IndikatorUnitTerlibat = apps.get_model('akreditasi', 'IndikatorUnitTerlibat')
      rows = IndikatorMutu.objects.exclude(unit_id=None).values_list('pk', 'unit_id')
      IndikatorUnitTerlibat.objects.bulk_create(
          [
              IndikatorUnitTerlibat(indikator_id=i, unit_id=u, is_pic_utama=True)
              for i, u in rows
          ],
          batch_size=500,
      )
  ```

  Name it `inm_unit_mapping` via `db_table` only if you prefer the spec's table name literally; otherwise keep Django's default and note the difference in the migration docstring. Do not hand-rename an existing table later.

- [ ] **Step 3: Tests**
  New `akreditasi/tests_inm_unit_akses.py`:
  - `test_pic_backfill_creates_one_row_per_indicator_with_unit`
  - `test_unique_together_blocks_duplicate_unit`
  - `test_indicator_without_unit_creates_no_mapping_row`

  Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_inm_unit_akses -v1`.

- [ ] **Step 4: Tick the checkboxes in this file and mark Task 1 done**

---

### Task 2: `CatatanIndikator.unit` + unique key change

The hard part. Without it a shared INM can only ever carry one unit's number.

- [ ] **Step 1: Add the field and relax the key**

  ```python
  unit = models.ForeignKey(
      UnitKerja, on_delete=models.SET_NULL, null=True, blank=True,
      verbose_name='Unit Penginput',
      help_text='Unit yang mencatat realisasi INM ini. Kosong = milik unit PIC indikator (baris lama).'
  )
  ```

  `Meta.unique_together` becomes `[('indikator', 'unit', 'bulan', 'tahun')]`. In SQLite and Postgres a NULL column does not collide with another NULL under a unique index, so legacy `unit NULL` rows stay valid — verify rather than assume (see Step 3).

- [ ] **Step 2: Migration `0042`**
  `AddField` first, `AlterUniqueTogether` second, then a `RunPython` backfill:

  ```python
  def backfill_catatan_unit(apps, schema_editor):
      CatatanIndikator = apps.get_model('akreditasi', 'CatatanIndikator')
      CatatanIndikator.objects.filter(unit=None).update(
          unit_id=models.F('indikator__unit_id')
      )
  ```

  The reverse function must be a no-op: reverting would destroy information. Say so in the migration.

- [ ] **Step 3: Prove the NULL-safe uniqueness**
  A test that inserts two rows with the same `(indikator, bulan, tahun)` and `unit=None` must raise `IntegrityError` under the new key **or** be explicitly tolerated — whichever the DB does. If SQLite and Postgres differ, the plan must record the difference, because production is Postgres (Supabase) and CI/dev may not be.

- [ ] **Step 4: Thread `unit` through the input path**
  `indikator_views.indikator_input_capaian` writes the note; it must record `unit=request.user.profile.unit_kerja` when the user is unit-scoped, else fall back to `indikator.unit`. Existing callers that pass no unit keep working because the field is nullable and backfilled.

- [ ] **Step 5: Update fixtures and any test asserting the old key**
  `.venv/Scripts/python.exe manage.py test akreditasi -v1` and compare the failure list against the baseline of the two known AI failures. Expect churn in `tests_indikator_alur_integrasi` and `tests_indikator_mutu_charts` — fix the fixtures, not the assertions, unless an assertion encoded the one-number-per-indicator assumption.

---

### Task 3: `indikator_qs_for_user()` — one access resolver for every INM read path

- [ ] **Step 1: Write the resolver** in `akreditasi/indikator_views.py` (importable by `akreditasi/views.py`):

  ```python
  def indikator_qs_for_user(profile, qs=None):
      """INM yang boleh dilihat user ini.

      Tier 1 (Direksi/Komite/Auditor) → semua.
      Tier 2/3/4 → INM yang memetakan unit user atau salah satu anak turunannya.
      Mapping kosong untuk unit user → tidak dibatasi (degradasi anggun).
      """
  ```

  Subtree resolution must walk `UnitKerja.parent`, not a recursive CTE — 218 rows locally, a recursive query buys nothing and costs portability.

- [ ] **Step 2: Apply it to all five read paths**
  `views.dashboard`, `indikator_views.indikator_dashboard`, `api_indikator_tren`, `api_indikator_komparasi_unit`, `views.api_mutu_indikator`. Each currently builds its own `IndikatorMutu.objects.filter(...)`; they all call the resolver instead.

- [ ] **Step 3: Tests**
  - `test_tier_one_sees_unmapped_inm`
  - `test_unit_scoped_user_without_mapping_sees_everything` (the degradation guarantee)
  - `test_unit_scoped_user_with_mapping_sees_only_mapped`
  - `test_child_unit_inherits_parent_mapping`
  - `test_api_tren_and_komparasi_apply_the_same_filter` — the two APIs must not diverge from the dashboard.

---

### Task 4: Level 3/4 dropdown + flagging badge

- [ ] **Step 1: Filter the dropdown by mapping, keep the `punya_data` marker**
  `indikator_dashboard` currently annotates `punya_data` so unmeasured indicators stay visible with a marker. That annotation stays; the mapping filter is applied *on top* of it. Do not regress to hiding unmeasured indicators — that was a deliberate decision recorded in the same file.

- [ ] **Step 2: Red flag + callout**
  Reuse `CatatanIndikator.tercapai` / `RisikoUnit.capaian_evaluasi`. When false:
  - badge `[!] Belum Memenuhi Standar` on the unit card,
  - a warning callout with a direct link to the risk evaluation/PDCA page for that indicator,
  - the link target must be the existing route, not a new one.

- [ ] **Step 3: `node --check` the inline JS on the rendered page**
  The raw template contains `{{ }}` inside `<script>`, so extract `<script>` blocks from a rendered response first and check those — checking the template file itself cannot pass.

---

### Task 5: Level 5 — restrict RCA / corrective-action form to flagged units

- [ ] **Step 1: Gate the corrective-action form**
  A unit that is mapped but currently meets target must not see the RCA form for that INM. Enforcement belongs in the view (`risiko_views`), not only in the template.
- [ ] **Step 2: Test both directions** — flagged unit can open it; non-flagged mapped unit gets 403; unmapped unit cannot even see the menu (Task 3).

---

### Task 6: Seed the 13-row matrix + admin page

- [ ] **Step 1: `seed_inm_matrix` management command**
  Seed from the docx table 1 (13 INM with PJ unit and involved units), matching by `kode_indikator` / name against `IndikatorMutu` with `jenis='NASIONAL'`, and by `code`/`name` against `UnitKerja`. Any row that cannot be matched is printed as a warning and skipped — never invented.
- [ ] **Step 2: Admin matrix page** for operators to maintain the mapping, since the spec makes the operator responsible for maintaining it.
- [ ] **Step 3: Run the full suite, tick every checkbox, commit**

---

## Review Focus

- **The empty-mapping guarantee is the one thing that can break production on deploy.** It needs an explicit test, not a comment, because the natural implementation (`if not mapped: exclude everything`) fails closed and silently empties every dashboard.
- **`unique_together` with a nullable `unit` is a DB portability trap.** Two `unit NULL` rows for the same indicator/month must not collide, or every legacy row and every new row collide. Test it against the same engine production uses.
- **Two status formulas must not exist.** If any task here feels the need to compare `nilai >= target`, it is wrong — `69d0440` already owns that logic.
- **The two pre-existing AI test failures are not this plan's.** Track the failure list across runs so they cannot mask a real regression.
