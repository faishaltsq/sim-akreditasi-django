# STARKES Edition Transition and Historical Evidence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the 2022-to-2024 transition described in `Cara melakukan perubahan sal.docx` with verified instrument sources, intact historical assessments, enforceable read-only archive, reviewed evidence reuse and consistent edition-scoped dashboards.

**Architecture:** Harden the existing importer, cutover wrapper and `Framework.active()` rather than starting another catalogue system. Separate instrument edition, accreditation target year, catalogue installation and activation; stage reviewed 2024 content before one controlled activation. Preserve old assessment/evidence rows in place and create explicit reviewed cross-edition lineage instead of relocating scores solely by matching a code string.

**Tech Stack:** Existing Django/SQLite/PostgreSQL monolith, existing `pypdf` parser, JSON fixtures/manifests, current evidence and audit models, Django templates/cache and existing regression suites. Pin parser dependency through the reviewed requirements workflow; do not install packages or import a live catalogue while planning.

**Spec:** `C:/Users/cubeb/Downloads/Cara melakukan perubahan sal.docx`; baseline `2026-10-24-arima-improvement-baseline.md`. HC integration consumes the rule/document contracts in track B and report contracts in track A, not a replacement KPS catalogue.

## Global Constraints

- Plan only. Production migration/import/cutover, backup operations, grant changes, commit/push/deploy require explicit execution approval.
- Preserve 298 existing `QualityRecord` rows and their populated text/budget/owner relationships; preserve the existing evidence file and all requirements/IDs. Do not delete/reseed or silently repoint historical assessment rows.
- Same EP code does **not** prove unchanged meaning, score equivalence or RDWOS applicability. Automatic candidate suggestions are allowed; activation/score/evidence decisions require reviewed mappings.
- Keep the original archive readable with original source identity and content. `is_active=False` alone is not an archive write guard.
- Source text must not be truncated to a preview string during ingestion. Summaries are presentation-only; retain full reviewed EP text and page provenance.
- Use the same selected framework across sidebar, dashboard, matrices, lists, exports, evidence, score budgets, unit maps and HC reports. Invalid framework selection fails closed; old bookmarked object IDs remain readable but not writable.
- An inactive candidate catalogue is not an archived published catalogue: explicit lifecycle distinguishes `DRAFT/VALIDATED/ACTIVE/ARCHIVED`. Only controlled catalogue tools may modify staged candidates; normal scoring/upload routes may write only to the approved active edition.
- UI text is Bahasa Indonesia. A target/accreditation year is not the instrument edition. Keep existing stable PK-based URLs and add explicit framework/edition context.
- No automatic changes to patient clinical content, risk scores, quality-indicator weights or HC grants on catalogue activation.
- Do not fabricate a required official EP count from a prior parser total. Counts below are measured **parser inventories**, not signed-off interpretation of the legal source.

## Review Focus

1. A valid PDF with incomplete/duplicated parsing, mismatched hash or wrong decree/instrument type must fail before changing any catalogue row.
2. A same-code EP with changed meaning, split/merged successor or preexisting target assessment must never overwrite or erase historical scores/notes.
3. Archived EPs must reject direct score/edit/upload/link/unlink/delete/auto-score requests even for ordinary platform admins; GET must not create missing assessment rows.
4. Mixed editions and warmed cache must not double-count EP, documents, budget or compliance, or show legacy categories under an active-2024 heading.
5. Failure during any chapter, mapping report generation, verification or concurrent activation must leave the previous active catalogue usable and produce a recoverable audit outcome.

## Source evidence — freshly measured, read-only

Both PDFs were located in the user's Downloads and read by the existing `parse_pdf` function without any database import. Their first pages identify different documents:

| Asset | Identity / provenance | Current-parser inventory |
|---|---|---|
| `starkes 2024.pdf` | KMK `HK.01.07/MENKES/1596/2024`; 356 pages; SHA-256 `22d2247e6a2b272789141536ca4539f99ebb825ad6c7bfe61106d065aa453116` | 224 extracted standard headings; 794 unique EP; 16 chapter prefixes; 792 EP without extracted RDWOS; 27 descriptions exactly 300 characters |
| `instrumen standar survey akreditasi  rs 2024.pdf` | Dirjen `HK.02.02/D/47104/2024`; 415 pages; SHA-256 `fde4091e97bd4b9de944994e3764a125bdc83f07d3fba680ecb5023bb478dd80` | 218 extracted standard headings; 732 unique EP; 16 chapter prefixes; 105 EP without extracted RDWOS; 338 descriptions exactly 300 characters |
| `fixtures/standar_akreditasi_2024.json` | SHA-256 `6ea5400d457ae734ddabd5f773b0d412522888e51e7e4e87ec2970408646f936`; no source manifest observed | 194 entries, 783 EP entries but only 700 unique EP keys; 15 chapter prefixes, PROGNAS absent; 179 EP entries without evidence types |

These results disagree. The decree's 794 unique parsed EP does **not** validate its RDWOS coverage; 792 have no evidence-type extraction. The fixture's 783 entries do **not** mean 783 unique requirements. The instrument's lower parser count is a signal to inspect page/table boundaries, not a basis to delete unmatched decree requirements or force a remembered total.

The parser hard-caps descriptions at 300 characters (`import_instrumen_2024.py:137,158`) and looks for standalone RDWOS letters only in the first 200 characters (`141,161`). Those are demonstrable extraction constraints. The existing PDF sources are the appropriate inputs for a reviewed reconciliation, not an instruction to trust current automatic output.

## Current-state contradictions and root causes

| Claim / desired behavior | Current evidence | Required correction |
|---|---|---|
| 2024 is installed/active after earlier work | Current SQLite contains one framework named `STARKES Edisi 2022 / Kemenkes RI`, version `2026`, 1,053 EP | Record installed state per environment; normalize edition separately from target year with reviewed provenance |
| Versioning needs a new arbitrary `version_year` | `Framework.version`, `is_active` and `active()` already exist | Extend existing edition identity/lifecycle; do not introduce a disconnected selection flag |
| Guarded dry-run fully validates import | `starkes_2024_cutover.py:49-55` only runs preflight and returns; it never invokes parser dry-run | Validate source/hash/content and proposed change plan without writes |
| Guarded apply is one auditable all-or-nothing operation | Wrapper invokes importer, clears cache and runs postflight with no enclosing transaction (`63-74`); importer commits per chapter (`296`) | Stage immutable reviewed import then atomically activate under lock; failures must not partially retire/reassign data |
| Archive preserves historical assessment | `_replace` moves the original `QualityRecord.standard_item` to the new row (`438-464`) | Retain original row/FK; approved successor assessments are distinct rows with lineage |
| Same-code matching is safe mapping | `_replace` resolves target by bare code (`423-430`), without semantic/requirement approval | Reviewed `UNCHANGED/CHANGED/SPLIT/MERGED/RETIRED/NEW/UNRESOLVED` decisions with explicit source/target identities |
| Old labels correctly say 2022 | `_retire_legacy_codes` uses `framework.version`, so current `2026` becomes `[2026]` (`407-411`) | Stop destructive label-renaming; canonical edition identity resolves independently |
| Regular import cannot damage old catalogue | `_import` uses globally unique `code` in `update_or_create` and can reassign category (`320-329`) even without replacement | Reject collision/reparenting before mutation; edition-scoped natural identity |
| Sidebar means all pages are edition-scoped | Sidebar resolves active framework, but global dashboard uses `Category.objects.all()`, all EP/requirements/records and fixed `dashboard_global_context` (`views.py:533-578`) | One selected-framework context and edition-aware cache/aggregations across all consumers |
| Inactive catalogue is read-only | `_can_modify_ep` has no lifecycle test (`views.py:87-109`); quick-score/inline/upload/link paths lack archive policy | Central lifecycle + authorization guard before side effects, including administrative/automatic routes |
| Evidence automatically carries forward correctly | Importer touches `EvidenceReq` but never remaps `EvidenceFile`; repository clone copies `status` directly (`views.py:908-925`) | Reviewed requirement-specific lineage and target review status; source files preserved |
| Viewing edit page is nonmutating | `ep_edit` creates a missing `QualityRecord` before checking POST (`1091-1095`) | Separate read-only GET from explicit authorized creation/update |

The previous runbook's 31 moved/267 unmatched is a prior rehearsal result, **not** a result reproduced on this database. Existing `akreditasi/tests_starkes_2024.py:100-142` actually asserts code-only score relocation, so that test must change when the safer archive contract is implemented.

### Overlap and non-goals

`2026-10-14-reimport-complete-2024-accreditation-standards.md` planned ingestion from the survey instrument. `docs/security/starkes-2024-cutover.md` describes a decree-based replacement rehearsal; current code implements parts of it. **This plan does not execute those legacy cutover instructions unchanged.** It reconciles both sources, hardens their real code and supersedes unsafe automatic relocation behavior for future transitions. Preserve old artifacts as historical evidence, but update the runbook to point to the approved flow.

The previous HC plan's KPS mapping is not source authority. Track B owns personnel/document identity; track A owns report UX and clinical/staff operations. This plan owns edition identity, archival guards and approved cross-edition references. Unrelated patient forms, indicator threshold redesign, risk methodology changes and generic credential cleanup: **do not implement, do not fix while here**.

## Architecture decisions and tradeoffs

| ADR | Decision | Tradeoff |
|---|---|---|
| ST-01 | Explicit catalogue lifecycle and reviewed source manifest on existing Framework | More metadata/validation than a year flag; prevents ambiguous `2026` label and accidental activation |
| ST-02 | Edition-aware natural keys; preserve source EP code | Requires auditing bare-code lookups; avoids destructive legacy code renaming and global collisions |
| ST-03 | Preserve original assessments; no automatic score transfer | New edition starts unassessed until review; history remains genuine instead of disappearing from archived views |
| ST-04 | Immutable reviewed cross-edition mappings and evidence lineage | Owner review costs time; same-number-but-different-content errors become visible |
| ST-05 | Stage and validate import, then atomic lock-protected activation | More steps than a single `--replace`; resumable import and predictable rollback |
| ST-06 | Reuse evidence object references only after review, not duplicate uploaded bytes | Requires tracking source version/hash and invalidation; avoids unnecessary file reupload |

## File ownership map

Modify existing:

- `akreditasi/models.py`: Framework lifecycle/edition/source metadata, scoped natural-key constraints, record assessment state and immutability policy as needed.
- `akreditasi/management/commands/import_instrumen_2024.py`, `starkes_2024_cutover.py`: parser/staging/manifest/review/activation controls; retain command names but reject unsafe legacy execution modes with an actionable message.
- `akreditasi/views.py`, `forms.py`, `urls.py`, `context_processors.py`, `kontrol_views.py`, `kontrol_data.py`: selected-edition reads, write guards and UI.
- `akreditasi/ep_sync.py`; bare-code resolvers in `management/commands/seed_clinical_risk_indicators.py`, `seed_indikator_mutu_renstra.py`; inspect other `setup_*`/seed/import users before scoped-key migration.
- Existing `templates/akreditasi/dashboard.html`, `matriks_pdca.html`, `ep_list.html`, `ep_detail.html`, `ep_form.html`, `dokumen_hub.html`; `templates/includes/sidebar.html`.
- `sdm/models/dokumen.py` and `sdm/services/analitik.py` only for approved framework/requirement integration, coordinated with A11/B3.
- `akreditasi/tests_starkes_2024.py`, `tests_security.py`, `tests_upload_bukti.py`, `tests_ep_sync.py`, `tests_kontrol_dasbor.py`; `sdm/tests/test_analitik.py` and `test_ekspor.py` through track-A integration.
- `docs/security/starkes-2024-cutover.md`, `docs/qa/arima-human-capital-release.md` for corrected boundary/status references.

Create NEW:

- `akreditasi/catalogue.py`: selected-framework read context and central catalogue-write guard.
- `akreditasi/catalogue_models.py` (re-export from existing models): `SumberKatalog`, `PemetaanEdisi`, `TautanAsesmenLintasEdisi`, `TautanBuktiLintasEdisi`, `AktivasiKatalog`.
- `akreditasi/catalogue_services.py`: reviewed import staging, mapping review, link creation and activation.
- `akreditasi/catalogue_views.py`; `templates/akreditasi/katalog/{daftar,pemetaan,validasi,pengumuman}.html`.
- `akreditasi/tests_catalogue_sources.py`, `tests_catalogue_identity.py`, `tests_catalogue_archive.py`, `tests_catalogue_mapping.py`, `tests_catalogue_activation.py`, `tests_catalogue_scope.py`.
- Reviewed source/expected-inventory manifests under `fixtures/catalogue_2024/` and full-text parsed artifacts with page references; `docs/qa/starkes-2024-validation.md`.
- Generated additive migrations under `akreditasi/migrations/`, with actual graph-derived filenames, and tracked collected-static artifacts if UI assets change.

## New service contracts

- `resolve_catalogue(user, *, framework_id=None) -> Framework`: explicit permitted archive selection or validated active catalogue; no unscoped fallback for malformed/unknown input.
- `require_catalogue_write(user, *, item, operation) -> None`: checks lifecycle plus existing role/unit permission; rejects archived/staged ordinary writes before touching rows/files/audit state.
- `validate_catalogue_source(*, path, manifest) -> dict`: verifies hash, document identity/pages, full-text extraction, reviewed expected inventory and extraction anomalies. Reads no live personnel data.
- `stage_catalogue(*, actor, source_manifest, reviewed_artifact) -> Framework`: import into inactive DRAFT candidate, idempotent by source+artifact digest, never reparent old rows.
- `review_edition_mapping(*, actor, source_item_ids, target_item_ids, classification, evidence_rule_map, score_policy, reason) -> PemetaanEdisi`: immutable approved identities/version/text hashes and reviewer stamp.
- `link_reviewed_evidence(*, actor, mapping, source_file, target_requirement) -> TautanBuktiLintasEdisi`: creates distinct target `EvidenceFile` in `REVIEW` plus lineage, referencing existing bytes only when authorized and classification permits; never auto-sets VALID.
- `activate_catalogue(*, actor, framework, reviewed_plan_hash, backup_reference, expected_previous_id) -> AktivasiKatalog`: lock, revalidate, switch once, immutable run metadata and post-commit cache namespace rotation.

`score_policy` defaults `REASSESS`; reviewed `CARRY_ASSESSMENT` is optional only for explicitly unchanged content and owner approval. It creates a distinct target assessment with source lineage; it never repoints the original row. A new `assessment_state=UNASSESSED/ASSESSED/REVIEW_REQUIRED` distinguishes untouched zero from an explicitly assessed zero. Existing populated assessments are migrated to a state only through reviewed provenance; numeric positivity alone does not prove review.

## Task C1 — Source manifests and full-text extraction audit (P0)

- [ ] Add RED source tests using deterministic small PDF/text fixtures and recorded page/table examples: repeated headings, repeated letters, numeric SKP/PROGNAS, page breaks, multiline RDWOS, long text, duplicated EP and missing chapter. Copy the existing `SimpleTestCase` parser idiom from `tests_starkes_2024.py:18-71`.
- [ ] Implement `validate_catalogue_source` and source manifests with legal identifier, document type (`STANDARD_DECREE` versus `SURVEY_INSTRUMENT`), SHA-256, pages, extractor version and page-linked content hashes. Remove ingestion-time 300-character truncation; separate EP text from evidence-instruction text.
- [ ] Reconcile the decree against the survey instrument at reviewed standard/EP identity, preserving differences and unresolved items. Do not force either extraction to 794 or reuse the defective 783-entry fixture as truth. Use source-specific parser profiles/table handling and a reviewed golden inventory; reject duplicates, empty placeholders and missing required chapters before import.
- [ ] Produce owner-review pages for all discrepancies plus full KPS and risk/EMR-relevant chapters. Store full-text source/page provenance and RDWOS instruction/action, not merely single-letter generic `Bukti R` labels. The existing fixture is quarantined from approved installation until replaced by a source-linked reviewed artifact.
- [ ] GREEN gate: source hashes/page counts match manifests; inventory has no duplicate composite keys; all required chapters and reviewed EP/evidence entries are reconciled, or documented unresolved entries explicitly block activation. Add `pypdf` to a reviewed pinned dependency set only during implementation and verify on the project interpreter.

Example current parser regression that should fail before removing truncation:

```python
text = 'A' * 350
items = _extract_ep_items('Elemen Penilaian KPS 1\na) ' + text + '\n')
self.assertEqual(items[0]['description'], text)
```

## Task C2 — Edition identity and non-destructive natural keys (P0)

**Depends on:** C1 reviewed source identity.

- [ ] Add RED tests creating the same canonical chapter/EP code in two frameworks without modifying either original, and duplicate chapter/EP within one framework being rejected. Also test current name-2022/version-2026 conflict, multiple active flags and malformed edition selection.
- [ ] Extend existing Framework with reviewed immutable edition/source identity and lifecycle, retaining legacy `version` only as a compatibility display field until consumers migrate. Store hospital accreditation target year on its existing hospital profile, not as catalogue identity. Do not infer 2022 solely from a name string without an approved normalization artifact.
- [ ] Add `Category` uniqueness `(framework, code)` and replace global EP code uniqueness with `(category, code)`. Enforce canonical code prefix matching its category in model/service/form/import validation; logical identity is framework + chapter + canonical EP code. Validate existing duplicates/conflicts before adding constraints. Existing IDs and source/display codes remain unchanged; no `[2026]` suffix retirement.
- [ ] Implement `resolve_catalogue` and edition-aware EP resolver. Update importer lookups to `category` plus code. Audit all bare-code usages before changing uniqueness, including `ep_sync.py:345`, `seed_clinical_risk_indicators.py:443`, `seed_indikator_mutu_renstra.py:599,634`, all setup/seed commands, forms/admin and test fixtures; record every discovered consumer and update it to explicit framework/category context. Reject unscoped ambiguous lookups.
- [ ] GREEN gate: empty/populated SQLite and PostgreSQL migration rehearsal; no row/FK/text/score/file count loss. An import collision cannot reparent a legacy EP, with or without legacy `--replace` flags. Preserve old numeric-ID links.

## Task C3 — Enforce archive read-only and eliminate mutating GET (P0)

**Depends on:** C2 lifecycle/resolver.

- [ ] Add RED archive tests for each actual writer role, including SUPER_ADMIN/ADMIN_RS, coordinator, unit head, staff and assessor: quick score, inline PDCA, EP edit/create/delete, AJAX/regular upload, repository linking/unlinking, auto-scoring and admin bulk actions. GET detail/export must remain usable without creating rows.
- [ ] Implement `require_catalogue_write` before normal role shortcuts. Centralize active-edition/lifecycle checks; staged catalogue editing belongs only to controlled catalogue maintenance, not ordinary scoring/upload routes. Add explicit authorization for **both source and target** in document linking and for all administrative/automation paths.
- [ ] Move `ep_edit` assessment creation inside authorized POST/transaction; GET no longer invokes `get_or_create`. Prevent a hand-edited old URL or supplied foreign framework/category from bypassing archive policy. Preserve authorized read-only archive exports.
- [ ] Add archive selector/badges and remove/disable write affordances with explanatory text. Update JavaScript to clear stale category/substandard/requirement selections when edition changes; server validation remains authoritative for handcrafted requests.
- [ ] GREEN gate: archive mutation attempts return consistent 403/409, no changed row/file count/hash, no storage upload call, and no fabricated success. Management imports are covered by C5's separate guarded path; a general platform role alone never overrides archive immutability.

## Task C4 — Reviewed semantic mapping, assessment lineage and evidence reuse (P0/P1)

**Depends on:** C1 source artifacts, C2 identities and C3 archive guard.

- [ ] Add RED mapping tests: same code/different wording, equivalent text/different numbering, one-to-many split, many-to-one merge, retired/new/unresolved EP, mismatched RDWOS type, existing target score, missing/changed source file and permission denial.
- [ ] Add mapping models with explicit source/target framework+PK+text hashes, classification, reviewer/date/reason and separate evidence/score policies. Add `TautanAsesmenLintasEdisi` referencing preserved source and distinct target assessment; default target state is UNASSESSED/REVIEW_REQUIRED, not inherited score 10.
- [ ] Replace `_replace` code-only relocation. Preserve all 298 old assessment PKs/FKs/payloads unchanged. Auto-suggest mapping candidates by code/text similarity if useful, but do not approve them automatically. For approved carry policy, copy the reviewed payload into a distinct target assessment with audit lineage; target conflict blocks overwrite.
- [ ] Implement `link_reviewed_evidence` using current `EvidenceFile` references and lineage rather than reuploading bytes. Target review starts REVIEW regardless of source VALID; a reviewer accepts the exact applicable requirement/type/version. Unmatched or unsuitable documents stay accessible in the archive; metadata-only/missing-file records are reported, not invented.
- [ ] GREEN gate: source payload/attachments remain identical before/after, repeats create no duplicate target links, target edits cannot mutate source history, retired/unresolved items appear in owner work queue. HC private documents enter only through A11's sanitized publication, never raw private URL reuse.

## Task C5 — Staged import, reviewed preview and atomic activation (P0)

**Depends on:** C1–C4.

- [ ] Add RED command/service tests for no-apply dry-run, malformed/wrong source, duplicate/missing EP, category-only partial replacement, backup acknowledgment without a verified reference, stale preview hash, chapter failure, postflight failure, report-write failure and concurrent activation.
- [ ] Make guarded dry-run parse/validate source and emit an exact proposed import/mapping/coverage report without writes. Reject activation with unresolved source inventory or incomplete chapter subset. Add `--reviewed-manifest`, `--reviewed-plan`, `--expected-plan-sha256`, `--backup-reference` to the existing wrapper; these flags are **new proposed interfaces**, not currently usable commands.
- [ ] `stage_catalogue` imports an inactive candidate with transactional, idempotent batches and resumable status. No legacy retire/reparent or score move occurs during staging. Only a completely validated candidate becomes VALIDATED. Report storage must be durable/verified and ledgered before readiness; a local file success is not a committed activation receipt.
- [ ] `activate_catalogue` locks the catalogue control row, verifies expected previous active ID, source/artifact/mapping digests, approved unresolved-retirement decisions and backup/restore reference, then atomically archives old and activates validated candidate. Assert exactly one active catalogue and manifest inventory inside the controlled transaction. Rotate edition/cache namespace only on commit; do not call global `cache.clear()` mid-operation.
- [ ] GREEN gate: failure leaves the previous active framework unchanged; success read-back matches active ID, source/plan hash, expected EP/requirement inventory, lineage and old record/file counts. Do not retain a bypass named `--skip-backup-check` as proof of a backup. An operator-provided reference must correspond to a verified backup/restore rehearsal recorded in the activation run.

Proposed preview syntax **after** these flags exist, staging/sanitized environment only:

```bash
.venv/Scripts/python.exe manage.py starkes_2024_cutover \
  --pdf-path "C:/Users/cubeb/Downloads/starkes 2024.pdf" \
  --reviewed-manifest fixtures/catalogue_2024/source-manifest.json \
  --reviewed-plan var/starkes-2024-reviewed-plan.json
```

No `--apply` command is prescribed against the current database by this planning task. The implementation runbook must record actual approved artifact digests and environment backup reference, not template values.

## Task C6 — Edition-scoped UI, integrations and test expectation migration (P1)

**Depends on:** C2–C5. **Owns all references broken by changing global uniqueness/legacy relocation behavior.**

- [ ] Create a two-edition fixture with distinct category/EP/score/requirement/file/budget values using the existing `ReplaceCatalogueTests.setUp` model-creation idiom, and RED assertions for sidebar, dashboard global/unit modes, matrix, EP list/detail, repository, recap, exports, control hub, auto-score and HC audit. Warm cache before switching edition.
- [ ] Pass `resolve_catalogue` result through every query/context/aggregate. Use framework ID plus catalogue/source revision and user/scope in cache keys. Scope numerators and denominators, requirements and distinct uploaded counts identically. Include assessment-state coverage; zero unassessed is not a completed score.
- [ ] Map organizational `standar_terkait` aliases/references through reviewed edition mapping, preserving original historical unit maps. Update risk/quality/EMR evidence references explicitly by FK/approved linkage; never silently rewrite indicator values, weights, clinical notes or risk scores.
- [ ] Replace current assertion `self.assertEqual(self.record.standard_item, new_item)` in `tests_starkes_2024.py:137` with the archive-preservation contract `self.assertEqual(self.record.standard_item, self.old_item)`; add distinct target-assessment lineage assertions for approved carry policy. Replace `.version` substring archive assertions with lifecycle assertions. Update all bare-code test fixtures/selectors/copy consumers identified in C2 and retain unaffected scoring assertions.
- [ ] GREEN gate: archive and active results are separated under cached and uncached reads; unknown edition returns controlled failure; old bookmarks select correct immutable history; chart/table/export totals reconcile with exact same scoped query. `sdm.PemetaanStandarSDM` can reference a reviewed active EP without requiring an existing `QualityRecord`.

## Task C7 — Rehearsal, owner validation, go-live announcement and rollback (P0 gate)

- [ ] Run source parser regression, full reviewed inventory reconciliation and read-only preflight on a sanitized populated SQLite copy, then empty and populated PostgreSQL databases. Snapshot old assessment payload/file references and compare them after staging/activation; do not rely on total count alone.
- [ ] Have accreditation owners review all changed/split/merged/unresolved mappings and KPS/RDWOS coverage; spot-check remaining chapters including risk/EMR integration. Record reviewed artifact/manifest hashes and approvals in `docs/qa/starkes-2024-validation.md`. Approval is a deployment dependency, not a placeholder permission for automatic same-code carry.
- [ ] Run `akreditasi.tests_starkes_2024`, all new catalogue modules, existing security/upload/EP-sync/control tests, HC mapping/report tests, then full isolated `akreditasi sdm accounts pasien` regression and browser archived-write/active-scoring/report journeys. Record actual outputs and package versions.
- [ ] For authorized go-live: verified backup/restore, approved source/plan, immutable activation receipt, explicit migrations, validated staged import, controlled activation and exact read-back. Add Bahasa Indonesia announcement `ARIMA menggunakan Standar Akreditasi 2024` only after the current active framework's reviewed edition is 2024; make it versioned/dismissible, with archive/read-only instructions and per-user acknowledgment.
- [ ] Rollback switches to the previous **recorded framework ID**, not `version__startswith='2022'` (which fails on this local version-2026 record). Rotate caches and disable the 2024 announcement. Since original assessments/evidence were never moved, archive history remains intact; keep new-2024 work preserved and read-only until reviewed. Test this exact rollback on a restored copy.

## Verification commands and isolation

Current measured baseline is **246 tests passing** for `sdm` plus `akreditasi.tests_starkes_2024`, using an external scratch bootstrap that sets SQLite `:memory:`, locmem mail/cache and scratch media before Django setup. That is not proof that new source/archival requirements already pass.

During implementation, use the same explicit isolation principles. Run new test modules through Django's runner; do not import production settings and assume the connection is local. Parser calls used in preparing this plan performed no catalogue import. All future source fixture validation must record observed versus reviewed expected inventory, not an invented pass count.

## Acceptance against the attached transition document

| Requested outcome | Owner | Evidence required |
|---|---|---|
| Full 2024 master/versioning | C1/C2/C5 | Reviewed legal source + full-text/RDWOS manifest, installed candidate, exact activation receipt |
| Read-only 2022 archive | C3/C4 | Original assessment/file payloads preserved and every write boundary denied |
| No repeat upload of reusable documents | C4 | Reviewed target requirement linkage and original source lineage/bytes retained |
| Updated EP labels and RDWOS instructions | C1/C6 | Reviewed source text/page references and consistent active-edition UI |
| Risk/mutu/EMR integration | C6 | Explicit FK/reference review; no silent clinical/score/weight mutation |
| Staging simulation and scores/charts | C5/C6/C7 | Failure injection, isolated integration tests and reconciled same-scope totals |
| Owner validation | C1/C4/C7 | Signed-off discrepancy/mapping artifact and sample review evidence |
| Production release and announcement | C7 | Read-back active identity, source hash, deployment health and correct announcement |

**Execution handoff:** Approve the source/edition and archive-preservation policy before running the importer. Recommended execution is subagent-driven with source/parser, data-integrity and authorization reviews, while one integration owner serializes shared models/views and activation changes. This deliverable contains no applied catalogue operation or completed implementation task.
