# Rencana Formasi Ketenagaan (BAB MODUL RENCANA FORMASI KETENAGAAN) — Verified Gap Register and Completion Plan

> **For agentic workers:** Proposed work only. Producing this plan authorizes no implementation, migration, seed run, grant, commit, or deployment. Execute only after owner approval, using `superpowers:executing-plans` or `superpowers:subagent-driven-development`, one task at a time, RED → minimal implementation → GREEN.

**Goal:** Turn the existing activity-FTE planning slice into the six sub-menus the source document specifies — reference standards and effective working time, an integrated FTE/WISN calculator, a gap map with risk colouring, a unit submission form, a three-stage budget approval, and a recruitment execution tracker with EWS — and make the KPS 1 evidence printable.

**Architecture:** Extend `RencanaFormasi` / `AktivitasBebanKerja` / `HasilFormasi` (already immutable and versioned) with the missing reference layer and workflow stages. Keep `calculate_formasi` (activity FTE) and `calculate_wisn` strictly separate; do not merge them. Link an approved deficit to an existing `Lowongan` rather than building a second recruitment pipeline.

**Tech Stack:** Existing Django 6.1 / templates / Bootstrap 5, SQLite and PostgreSQL, `openpyxl`, `reportlab`. No predictive staffing, no payroll calculation.

**Source:** `C:/Users/cubeb/Downloads/BAB MODUL RENCANA FORMASI KETENAGAAN.docx` (210 paragraphs, read in full).

---

## Global Constraints

- All UI copy is Bahasa Indonesia. `Belum dikonfigurasi` for absent configuration, `Belum dapat dihitung` for insufficient source coverage, `Belum diaktifkan` for unreleased workflow. Never show `100%` or a green status on missing data.
- Decimal arithmetic end to end. FTE and headcount are different quantities and are never rendered from the same number.
- Approved `HasilFormasi` stays immutable. A recalculation creates a new plan version and supersedes the old one (`sdm/services/formasi.py:60-100` already does this — preserve it).
- Every route keeps a server-side capability **and** unit-scope check.
- Do not hardcode EP numbers; resolve from the active framework at render time (see the Kredensial plan, constraint 4).
- Demo, unclassified, and inactive employees never enter a production FTE denominator.

---

## Verified baseline — what already exists

Read-only inspection on `master` at `d9bc2f5`. `sdm.tests.test_formasi` = **13 tests**, `sdm.tests.test_wisn` = **5 tests**, all OK.

| Source requirement | Existing implementation | Status |
|---|---|---|
| Sub-menu 1 — Master reference standards | None. No regulation table, no ratio table, no effective-working-time master. | **Missing** |
| Sub-menu 2 — FTE/WISN calculator | `RencanaFormasi` + `AktivitasBebanKerja` + `calculate_formasi` (`sdm/models/formasi.py:186`); `BebanKerja` + `calculate_wisn` (`sdm/services/wisn.py:23`) | Partial — **WISN is wrong** |
| Sub-menu 3 — Staffing map & gap analysis | `HasilFormasi.gap_fte`, `sufficiency_pct`; rendered per plan in `templates/sdm/formasi/daftar.html` and `templates/sdm/dashboard.html:130-150` | Partial — no map, no colour coding, no surplus |
| Sub-menu 4 — New formation submission form | `RencanaFormasiForm` (`sdm/forms/formasi.py:9`) with unit, profession, period, method, effective minutes, allowance | Partial — no justification, no attachments, no qualification fields |
| Sub-menu 5 — Three-stage approval | `formasi_submit` (DRAFT→REVIEW) and `formasi_approve` (REVIEW→APPROVED) with self-approval ban | Partial — **one approval stage, no HRD/budget/director split** |
| Sub-menu 6 — Recruitment execution & tracking | `Lowongan`, `Lamaran`, `RiwayatSeleksi`, `hire_application` | Present but **not linked to any formation plan** |
| Print/export (4 artefacts) | None for this module | **Missing** |
| Audit trail | `PeristiwaSDM` on submit/approve/supersede | Working |

---

## Gap matrix

### P0 — the numbers are wrong or the workflow is unimplementable

| # | Gap | Evidence | Consequence |
|---|---|---|---|
| F1 | **WISN available working time is dimensionally wrong.** | `sdm/services/wisn.py:49-54`: `weeks = hari_per_minggu / 7`, then `available_hours = jam_per_hari × weeks × days_in_period / 7`. The `/7` is applied twice. Measured on a 30-day period with 8 h/day and 5 days/week: **24.49 hours** available, where the correct answer is 171.43 hours. | `required_fte` is inflated ~7×. A plan that needs 5 FTE reports 37.73. Any WISN figure produced today is unusable and must not be shown to a committee. |
| F2 | **No reference-standard layer.** No table for regulatory ratios (ICU nurse:patient per shift, minimum DPJP per hospital type, pharmacist ratio), no effective-working-time master (annual working days minus leave, sickness, public holidays, 20 h/yr training), no standard-workload master. | No model, no route. `effective_minutes_per_employee` is typed by hand per plan (`sdm/forms/formasi.py:26`). | Two units can enter different effective minutes for the same year; results are not comparable and cannot be defended to a surveyor. This is exactly what KPS 1 asks for. |
| F3 | **No gap-analysis map.** No unit grid, no red/yellow/green/blue risk coding, no surplus detection, no hospital-wide view. | `templates/sdm/formasi/daftar.html` is a flat per-plan table; `dashboard.html` shows the same rows. `HasilFormasi` has no status field. | The document's four-colour risk model (Defisit Kritis / Marginal / Ideal / Surplus) does not exist. Management cannot see which unit is dangerous. |
| F4 | **Approval is one step, not three.** | `sdm/views.py:531` `formasi_submit` → REVIEW; `:548` `formasi_approve` → APPROVED. Both gated by `can_plan_hc_workforce`. No budget check, no finance actor, no director actor. | The submitter's own unit head can approve the request that they themselves created (only self-approval by the same user is blocked, `sdm/services/formasi.py:52`). There is no budget gate at all, so the document's `HR Budgeting Report` has no meaning. |
| F5 | **Formation is not linked to recruitment.** | `RencanaFormasi` has no `lowongan` FK; `Lowongan` has no `rencana_formasi` FK. | An approved deficit produces nothing actionable. `hire_application` never reduces a gap, so `actual_fte` only changes when a `PenempatanPegawai` happens to be created elsewhere. |

### P1 — the promised artefacts and controls

| # | Gap | Evidence |
|---|---|---|
| F6 | No submission justification fields: reason (new service / replacement / regulation / FTE deficit), qualification requirements (education, STR, mandatory certificates such as ICU/BTCLS), supporting attachments. | `RencanaFormasiForm` fields: unit, profesi, periode, metode, effective_minutes, support_allowance_pct only. |
| F7 | No budget simulation. Nothing computes salary/allowance impact against an HR ceiling. | No model, no field, no view. |
| F8 | No recruitment progress dashboard with target date and stage, and no EWS for a deficit past its due date. | `Lamaran.STATUS_CHOICES` exists but is per-vacancy, not per-formation; `PengingatSDM.TARGET_CHOICES` has no `FORMASI`. |
| F9 | Zero exports. | 72 routes; none for this module. |
| F10 | No `BebanKerja` admin or UI. The model exists (`sdm/models/beban_kerja.py`) and `calculate_wisn` reads it, but nothing creates a row. | `grep BebanKerja sdm/admin.py` → none; `grep BebanKerja sdm/views.py` → only the activity-FTE model. |
| F11 | `RencanaFormasi.METHOD_CHOICES` has only `ACTIVITY_FTE`; `BebanKerja.METODE_CHOICES` has `WISN`. | `sdm/models/formasi.py:24` vs `sdm/models/beban_kerja.py:22`. Two parallel plan tables with no bridge. |
| F12 | `support_allowance_pct` is a single percentage with no breakdown (leave, sickness, training, public holiday). | `sdm/models/formasi.py:46`. The document's JKE factor list cannot be entered or evidenced. |
| F13 | Dashboard staffing rows show every approved plan for a unit, including superseded periods, without period selection. | `sdm/services/dashboard.py:104-119` filters `status='APPROVED'` only — `SUPERSEDED` is excluded correctly, but two different professions/periods render side by side with no as-of filter. |
| F14 | No unit-descendant roll-up. A head of a parent unit sees child-unit plans as separate rows with no aggregate. | `visible_units` supports `include_descendants`, but the formasi views never aggregate. |

### Document corrections the owner must accept

| # | Claim in the source document | Actual | Action |
|---|---|---|---|
| C1 | "KPS 1 EP 1 … EP 4" (four EPs across sub-menus 1–6) | Active framework: **KPS 1 has exactly one EP** (`KPS 1 EP 1`). The 2024 fixture has six. | Map the whole module to `KPS 1 EP 1` today; do not print EP 2–4. |
| C2 | "KPS 1 & TKRS 3" for the approval sub-menu | Active framework has `TKRS 3.1` and `TKRS 3.2`, **no `TKRS 3`**. | Use `TKRS 3.1`. |
| C3 | `Kebutuhan Staf = Total Beban Kerja / JKE + Faktor Koreksi` | The `+ Faktor Koreksi` term is dimensionally wrong when the factor is a percentage; it must be a multiplier on the numerator or a divisor adjustment. | Define the formula explicitly in the reference master and document it on screen, so the printed report matches the calculation. |
| C4 | "Koding warna 🔴/🟡/🟢/🔵" | Not implemented. | Build it from thresholds stored in the reference master, never hardcoded in a template. |

---

## Task F-A1 — Fix WISN before anything consumes it (P0) — ✅ DONE 2026-10-26

**Depends on:** nothing. **Blocks F-A3, F-A6.**

- [x] Add RED tests that pin the arithmetic against a hand-computed worksheet: 30-day period, 8 h/day, 5 days/week → available time ≈ 171.43 h; a 31-day period; a 7-day service (ICU) → 8 h × 31; `required_fte` for 1,600 visits × 30 min × 1.155 allowance over that denominator.
- [x] Correct `sdm/services/wisn.py`: available working time = `jam_per_hari × hari_operasional_per_minggu × (days_in_period / 7)`. Remove the duplicate `/7`. Bump `WISN_CALC_VERSION` to `wisn-v2` and record the version on every result.
- [x] Add a `coverage_complete` reason string whenever any input is missing, and refuse to return a number in that case (the current code raises, which is correct — keep it, and add the same behaviour for `hari_operasional_per_minggu > 7`).
- [x] GREEN gate: `test_wisn` green with the corrected expectations; `test_formasi` untouched and green.

**Delivered:** `sdm/services/wisn.py` (+39/−16), `sdm/tests/test_wisn.py` (12 tests). Reference case now returns **5.39 FTE**, previously **37.73** — the `wisn-v1` formula applied the weekly factor twice. Result payload now carries `days_in_period`, `operating_days_in_period`, `available_hours`, and every raw input so the worksheet is reproducible in a printed report. Guards added for `hari_operasional_per_minggu` outside `(0, 7]`. No production caller existed (`grep calculate_wisn` → only `test_wisn.py`), so the change is inert until F-A8 exposes a UI. `python manage.py check` clean, `makemigrations --check` clean, `test_formasi + test_wisn` = 25 tests OK.

## Task F-A2 — Reference standards and effective working time (P0)

**Depends on:** nothing.

- [ ] Add RED tests: an approved reference version is immutable; a plan referencing a retired standard still renders its historical value; a missing ratio renders `Belum dikonfigurasi`; effective minutes derived from the factor breakdown equals the sum of the components.
- [ ] Add `StandarKetenagaan` (unit type / profession / `jenis` ∈ rasio_regulasi | standar_waktu | faktor_koreksi, `nilai`, `satuan`, `sumber_regulasi`, `berlaku_mulai`, `is_active`, `reviewed_by`, `reviewed_at`) and `JamKerjaEfektif` (tahun, hari_kerja, cuti_tahunan, hari_sakit_rata2, libur_nasional, jam_pelatihan, `hasil_menit_efektif` computed, `is_approved`).
- [ ] Compute `effective_minutes_per_employee` from the approved `JamKerjaEfektif` for the plan's year; keep manual override available but flag the plan as `override manual` in the UI and in the printed report.
- [ ] **Corrected during implementation:** do NOT split `support_allowance_pct` into `cuti`/`sakit`/`pelatihan`/`libur`. Those four are already subtracted inside `JamKerjaEfektif`; adding them again as a percentage double counts and inflates the requirement. The breakdown belongs to `JamKerjaEfektif`; `support_allowance_pct` covers indirect/support activity only (documentation, handover, meetings, coordination). The printed report shows both blocks separately so the arithmetic stays visible without counting anything twice.
- [ ] Seed **only** what the owner supplies. Empty is `Belum dikonfigurasi`.
- [ ] GREEN gate: immutability enforced in `save()` mirroring `HasilFormasi`; `test_formasi` green.

**Delivered:** `sdm/models/referensi.py` (`JamKerjaEfektif`, `StandarKetenagaan`), `RencanaFormasi.jam_kerja_efektif` FK + `resolve_effective_minutes()`, migration `0033_*`, `sdm/tests/test_referensi.py`.

## Task F-A3 — Gap map with risk coding (P0) — ✅ DONE 2026-10-26

**Depends on:** F-A1, F-A2.

- [x] Add RED tests: deficit beyond the critical threshold → `Defisit Kritis`; between thresholds → `Ketercukupan Marginal`; within tolerance → `Ideal`; negative gap → `Surplus`; a plan without an approved result renders `Belum dapat dihitung` and is never coloured green; a parent unit aggregates its descendants once, without double counting.
- [x] Add `HasilFormasi.status_risiko` computed at approval time (immutable), with thresholds read from `StandarKetenagaan`; store the threshold values used in the result row so the colour is reproducible.
- [x] Add a gap-map view: unit × profession grid, colour badge, existing / required FTE / headcount / gap / sufficiency, as-of period selector, and a "hanya defisit" filter. One query set with `select_related`, no per-row queries.
- [x] Link each deficit row to a "Buat usulan formasi" action that pre-fills the submission form with the unit, profession, period, and computed gap.
- [x] GREEN gate: page renders under 200 employees and 200 units without N+1 (assert query count in the test).

**Delivered:** `sdm/services/risiko.py` (`classify_risiko`, `resolve_ambang_risiko`, `gap_rows`, `gap_totals`), `sdm/views.py:formasi_peta`, `sdm/urls.py` route `sdm:formasi_peta`, `templates/sdm/formasi/peta.html`, migration `0034_*`, `sdm/tests/test_risiko_formasi.py` (23 tests). Thresholds are `StandarKetenagaan` rows of `jenis=AMBANG_RISIKO` named `Ambang Ketercukupan Marginal` / `Ambang Defisit Kritis`; unit-specific wins over hospital-wide. Boundary semantics: exactly at the critical threshold is `MARGINAL`, not critical. The N+1 guard asserts the query count is identical with 1 and 5 approved plans.

## Task F-A4 — Submission form with justification and attachments (P1)

**Depends on:** F-A3.

- [ ] Add RED tests: a submission without a reason is rejected; a reason of `hasil FTE` requires a linked approved result; attachments are private (no public URL, no anonymous download); an attachment belonging to another unit is refused.
- [ ] Add fields to `RencanaFormasi`: `alasan` (choices: layanan_baru / replacement / regulasi_baru / defisit_fte), `alasan_catatan`, `kualifikasi_pendidikan`, `sertifikat_wajib` (JSON list), `target_pemenuhan` (date), `lowongan` (nullable FK).
- [ ] Add `LampiranFormasi` (plan, `VersiDokumen`, keterangan) reusing the private-storage path from `sdm/storage.py`.
- [ ] GREEN gate: `test_dokumen`/`test_private_documents` patterns reused; no signed URL leaks into a list response.

## Task F-A5 — Three-stage approval with a budget gate (P0)

**Depends on:** F-A4.

- [ ] Add RED tests: unit head submits → HRD verifies → finance verifies → director approves, each stage refusing an out-of-order transition; the submitter cannot perform any later stage; finance rejection returns the plan to `REVIEW` with a reason and does not destroy the result; an approved plan cannot be re-approved; every transition writes exactly one `PeristiwaSDM`.
- [ ] Extend `RencanaFormasi.STATUS_CHOICES` to `DRAFT → REVIEW_HRD → REVIEW_ANGGARAN → REVIEW_DIREKSI → APPROVED` (+ `DITOLAK`, `SUPERSEDED`). Migrate existing `REVIEW` rows to `REVIEW_HRD` in a data migration that reports the count.
- [ ] Add two capabilities: `can_verify_hc_formasi_budget` (finance) and `can_approve_hc_formasi` (director). Keep `can_plan_hc_workforce` for submission only.
- [ ] Add `AnggaranFormasi` (plan, `biaya_tahunan`, `sumber_anggaran`, `plafon_tersedia`, `sisa_setelah`, `catatan_keuangan`) entered at the finance stage; refuse approval when `sisa_setelah < 0`.
- [ ] Keep the existing self-approval guard and extend it to every stage (`created_by` can never act on their own plan).
- [ ] GREEN gate: `test_formasi` approval tests rewritten for the new states; supersede logic preserved.

## Task F-A6 — Formation → recruitment link and progress tracking (P1)

**Depends on:** F-A5.

- [ ] Add RED tests: approving a plan with a deficit offers a one-click vacancy creation with the same unit/profession/headcount; hiring through `hire_application` reduces the plan's outstanding gap on the next recalculation but never mutates the approved `HasilFormasi`; a plan whose target date passed and whose gap is still open raises exactly one EWS reminder; a filled plan closes its reminders.
- [ ] Add `Lowongan.rencana_formasi` FK (nullable) and `RencanaFormasi.lowongan`. Creation is explicit, never automatic.
- [ ] Add `PengingatSDM.TARGET_CHOICES += ('FORMASI', 'Formasi &amp; Rekrutmen')` and a `sync_formasi_reminders()` using the same idempotency-key pattern as `sync_spk_reminders` (`sdm/models/pengingat.py:200`). Bands: `TASK_DUE` at target−7, `TASK_OVERDUE` at target+1.
- [ ] Add a progress dashboard: per plan, target date, vacancy state, applications per stage, days remaining, EWS badge.
- [ ] GREEN gate: repeat `hc_reminders` runs create no duplicate keys.

## Task F-A7 — Exports (P1)

**Depends on:** F-A1…F-A6. One commit per artefact, each with a RED test asserting capability + unit scope, a `PeristiwaSDM` write, content type, and filename.

- [ ] `Cetak Dokumen Rencana Ketenagaan Tahunan` PDF — executive summary, method statement, per-unit workload analysis, EP reference resolved from the active framework.
- [ ] `Export PDF Berkas Usulan &amp; Rekapitulasi Formasi Unit` — all submissions with approval status, budget recommendation, required qualifications.
- [ ] `Export PDF Matriks Gap Analysis &amp; Peta Ketenagaan` — the coloured map with the threshold values printed in the legend.
- [ ] `Export Excel Rencana Anggaran SDM` — projection for the finance team, one row per approved plan, explicit currency formatting.

## Task F-A8 — WISN plan creation UI and method honesty (P1)

**Depends on:** F-A1, F-A2.

- [ ] Add RED tests: a `BebanKerja` with `metode='WISN'` and no `JamKerjaEfektif` for its year cannot be approved; a plan cannot switch method after approval; the UI never labels an activity-FTE result as WISN.
- [ ] Add `BebanKerja` admin plus a create/edit view scoped to `can_plan_hc_workforce`, with an explicit approval step (`is_approved`, `approved_by`, `approved_at` already exist).
- [ ] Render the WISN worksheet (available time, standard workload, category allowance, individual allowance, required FTE) next to the result so the arithmetic is auditable.
- [ ] GREEN gate: `test_wisn` green; the two plan tables never produce a single merged "FTE" number.

---

## Delivery order

1. **F-A1** alone, first commit. Every downstream number depends on it.
2. **F-A2 → F-A3** (reference layer, then the map). These make the module defensible.
3. **F-A4 → F-A5** (submission, then the three-stage gate). This is the workflow KPS 1 actually asks for.
4. **F-A6** (recruitment link + EWS).
5. **F-A7** (exports).
6. **F-A8** (WISN UI).

## Acceptance

- A unit head submits a formation request with a justification and an attachment; HRD verifies; finance enters the budget and confirms it fits the ceiling; the director approves; the result is frozen with a reproducible threshold snapshot.
- The gap map shows all four risk colours, and a unit with no approved plan reads `Belum dapat dihitung` rather than green.
- WISN on a 30-day, 8 h/day, 5 day/week period returns ≈171.43 available hours, not 24.49.
- A deficit past its target date raises exactly one EWS reminder, and filling the vacancy closes it.
- All four export artefacts download with the correct scope and write an audit event.
- `python manage.py test sdm` green; `makemigrations --check` clean; `python manage.py check` clean.
- Every EP reference resolves from the active framework; `KPS 1 EP 2/3/4` is never printed while the active framework has one EP.
