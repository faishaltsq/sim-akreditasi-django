# IGD Penunjang Single-Path Ordering — Gap Analysis

- **Date:** 2026-11-17
- **Source requirement:** `C:\Users\cubeb\Downloads\perubahan menu di penunjang aplikasi ARima dengan alur cascading dropdown 17 11.docx`
- **Repo:** `sim-akreditasi-django` (Django + Supabase)
- **Scope:** IGD assessment workflow, step 7 ("Pemeriksaan Penunjang — Order & Hasil")
- **Status:** implemented 2026-11-17 — see §8 for the closure of every gap and the evidence test. §2 and §3 describe the pre-change state and are kept as the audit trail.

---

## 1. Source requirement digest

The DOCX is 175 non-empty paragraphs. It has exactly two parts.

**Part A — deletion order (paragraphs 1–4), verbatim:**

> Masalah pemeriksaan penunjang di igd;
> Hapus menu ini:
> hasil ekg, hasil kritis penunjang, order dan hasil tercatat dan lampiran ahsil dokumen
> Ganti dengan menu berikut ini;

**Part B — replacement design (paragraphs 5–175):** a 4-level cascading order menu plus three mandatory metadata attributes.

| Element | Value from document |
|---|---|
| Level 1 (Kategori Utama) | 2 — Laboratorium, Penunjang Diagnostik |
| Level 2 (Sub-kategori / Instalasi) | 9 — Lab: Laboratorium Klinik, Patologi Anatomi, Bank Darah (BDRS), Rujukan Luar, Lainnya · PD: Radiologi & Pencitraan, Elektrofisiologi, Endoskopi / Teropong Saluran, Kedokteran Nuklir |
| Level 3 (Kelompok Jenis) | 27 |
| Level 4 (Item Tindakan) | 94 items, multiselect / checklist |
| Mandatory attributes (¶172–175) | Prioritas (Rutin / Cito) · Indikasi klinis + ICD-10 (wajib) · Catatan persiapan (puasa, alergi kontras, kehamilan, lokasi sampel) |

Requirement decomposition:

| ID | Requirement | Acceptance criterion |
|---|---|---|
| R1 | Remove "Hasil EKG" from step 7 | No editable EKG text field in step 7 for any role |
| R2 | Remove "Hasil Kritis Penunjang" from step 7 | No editable critical-result field in step 7 |
| R3 | Remove "Order & Hasil Tercatat" menu | No order recap card and no in-step "Catat hasil" form in step 7 |
| R4 | Remove "Lampiran Hasil / Dokumen" menu | No attachment list and no upload form in step 7 |
| R5 | Replace with one 4-level cascading order menu | Single surface; L1→L2→L3→L4 dependent selects; L4 multiselect basket; server rejects out-of-order or inactive selections |
| R6 | Metadata on every order | priority, indication (required, ≤4000), diagnosis (optional, visit-scoped), preparation (per item) |
| R7 | Accreditation/STARKES readiness | Every submitted order carries a frozen catalogue snapshot (path + source version) for audit |

---

## 2. Current state inventory

### 2.1 Data layer — already complete

`klinis/data/penunjang_catalogue.json` is a 1:1 transcription of Part B.

| Fact | Value |
|---|---|
| `version` | `DOCX-2026-11-13-STAGING` |
| `sha256` (prefix) | `a42f2b704625` |
| Nodes | 38 → level 1: 2, level 2: 9, level 3: 27 |
| Items | 94 |
| `jenis_order` | LAB 49, RADIOLOGI 24, LAINNYA 20, EKG 1 |
| `is_panel` | 7 |
| `tujuan` populated | 0 of 94 |
| `preparation_schema` / `variants` present in fixture | no — importer writes `{}` |
| Empty groups | `laboratorium-rujukan-luar` (0 items), `laboratorium-lainnya` (0 items) |

Models: `klinis/expansion_models.py:6` (`KategoriPenunjang`, levels 1–3) and `:28` (`ItemPenunjang`, with `destination`, `active`, `reviewed_by`, `preparation_schema`, `variants`, `is_panel`). Hierarchy is enforced in `clean()` at `:22` and `:50`.

### 2.2 Server ordering path — already complete

| Concern | Location |
|---|---|
| Cascade listing + pagination (50/page) | `klinis/services/penunjang_catalogue.py:38` `list_choices` |
| Orderability gate (active + reviewer + destination) | `penunjang_catalogue.py:31`, `:54` |
| Frozen snapshot (L1/L2/L3 path + source version) | `penunjang_catalogue.py:6` `item_snapshot` |
| Batch order writer | `pasien/services/penunjang_orders.py:9` `order_batch` |
| Preparation/variant allow-list + required-schema enforcement | `penunjang_orders.py:26`, `:34`, `:37` |
| Result writer (requesting doctor and performing service) | `pasien/services/penunjang_results.py:42` `record_result` |
| Result worklist scope (unit tree, LAB-BDRS fallback) | `penunjang_results.py:17`, `:28` |
| Endpoints | `pasien:igd_penunjang_catalogue` (cascade), action `order_batch`, action `order_result` |

`OrderPenunjang.JENIS_CHOICES` already contains `EKG` (`pasien/models.py:935-940`), so the single EKG catalogue item maps cleanly.

### 2.3 UI — pre-change state (the five step-7 surfaces)

`templates/pasien/_igd_workflow_operations.html` step-7 block (lines 1–7) renders, in order:

| Line | Surface | Type | Requirement |
|---|---|---|---|
| 2 | "Kirim Order Penunjang" — free-text `InvestigationForm` | editable | not in document; superseded by R5 |
| 3 | "Order & Hasil Tercatat" — recap cards | read-only | **R3 delete** |
| 4 | "Catat hasil / pembaruan operasional" (`order_result`) | editable | **R3 delete** |
| 5 | "Lampiran Hasil / Dokumen" — attachment list | read-only | **R4 delete** |
| 6 | "Unggah Lampiran" (`igd_upload-form`) | editable | **R4 delete** |

Plus the two model fields rendered by the generic field loop (`templates/pasien/igd_workflow.html:54`) from `STEPS[7]` (`pasien/forms_igd_workflow.py:22`):

| Field | Model | Verbose name |
|---|---|---|
| `penunjang_ekg` | `pasien/models.py:514` | Hasil EKG |
| `penunjang_hasil_kritis` | `pasien/models.py:515` | Hasil Kritis Penunjang |

The cascade itself already exists and matches the document's 4 levels exactly:

- `templates/pasien/_igd_ancillary_order.html` — 4 dependent selects (`:6`), indication (`:8`), diagnosis (`:9`), priority (`:10`), 3 preparation selects (`:11`), site (`:12`), variants (`:13`), basket (`:14-15`), submit (`:16`)
- `static/js/igd-clinical-expansion.js:100-131` — cascade loader, variant rendering, basket, `order_batch` submit; `:128` sends `diagnosis_id`
- Context: `pasien/igd_workflow_views.py:182` (`cascade_levels`), `:183` (`preparation_fields`)

---

## 3. Gap matrix

| ID | Gap | Evidence | Severity |
|---|---|---|---|
| G1 | Step 7 still shows the four menus the document orders removed | `_igd_workflow_operations.html:3,4,5,6` | **Blocker for R1–R4** |
| G2 | "Hasil EKG" / "Hasil Kritis Penunjang" still editable | `forms_igd_workflow.py:22` | **Blocker for R1–R2** |
| G3 | Free-text order form still the most prominent path | `_igd_workflow_operations.html:2`, handler `igd_actions.order` | High (R5) |
| G4 | **Zero catalogue items are orderable after import** | `klinis/services/catalogue_import.py:31-36` writes `active=False`, `destination=None`, `reviewed_by=None`; gate at `penunjang_catalogue.py:31,54` | **Blocker for R5** |
| G5 | No bulk activation path — 94 items must be edited one-by-one in Django admin (`klinis/expansion_admin.py:24`), no filter by destination, no management command | `ls klinis/management/commands/` → only `import_*`, `seed_*` | **Blocker for R5** |
| G6 | UI sends 3 of 9 supported preparation keys; `specimen`, `region`, `side`, `contrast`, `external_destination` have no input | template `:11` + context `:183` vs allow-list `penunjang_orders.py:26`. Already proven by the WIP probe `qa/igd_revision_browser.py:427-441` + fixture `qa/igd_revision_fixture.py:158`, which demand `#anc-specimen` / `#anc-external-destination` and cannot pass against current templates | High |
| G7 | Items requiring `preparation_schema.required` can never be ordered from the UI — permanent 400 | `penunjang_orders.py:34-36` with no matching input | High |
| G8 | Preparation is captured once for the whole basket, not per item | `igd-clinical-expansion.js:124-126` reads global selects at "Tambah ke Daftar Order" | Medium |
| G9 | "Rujukan Luar" and "Lainnya" branches are dead ends — 0 items each | catalogue JSON; empty-state text at `igd-clinical-expansion.js:109` | Medium |
| G10 | Removing both fields empties `STEPS[7]`, and an empty payload is rejected → **step 7 can never be saved or advanced** | `igd_assessment_workflow.py:88-89` + `static/js/igd-assessment-workflow.js:20-42` always POSTs | **Blocker for R5** |
| G11 | Snapshot keys, printed resume rows and signature digests are derived from `STEPS` | `snapshot_visit_fields()` `forms_igd_workflow.py:35`; `clinical_snapshot` `igd_finalization.py:20-24`; resume `igd_workflow_views.py:350-351`; `cetak_asesmen_medis_igd.html:153-154` | **Blocker for R1–R2** |
| G12 | Deleting "Catat hasil" removes the only in-IGD result entry path for the requesting doctor | `record_result(requesting=True)` `penunjang_results.py:48-51`; worklist needs the destination inside the doctor's unit tree `:17-38` | High |
| G13 | 20 items are typed `LAINNYA`; nothing maps `LAINNYA` to a real unit, so destination assignment is manual for PA / BDRS / endoscopy / nuclear | `jenis_order` distribution; `destination` is a free FK to `akreditasi.UnitKerja` | Medium |
| G14 | Legacy third surface still writes/prints penunjang data outside the workflow | `pasien/views.py:2489-2493`, `igd_dashboard.html:691`, print `:152` | Low (out of scope) |

---

## 4. Blockers that must be resolved before this can ship

**B1 — Nothing is orderable (G4 + G5).** The cascade renders `— Pilih —` and the empty state "Belum ada item aktif/review pada cabang ini." for every branch. Deleting the free-text order form before activating the catalogue would leave IGD with **no way to order any penunjang at all**. Activation needs: `destination` per item (or per L3 group), `reviewed_by`, `active=True`, and a bulk command — 94 rows by hand is not an acceptable runbook.

**B2 — Step 7 cannot advance with an empty field set (G10).** Verified: `modelform_factory(KunjunganPasien, fields=())` is legal and renders nothing, but `save_step` rejects `{}` with "Tidak ada perubahan untuk disimpan." and the client always POSTs. The existing precedent is step 9 (`STEPS[9] = ('…', ())`), where the template suppresses the save buttons entirely (`igd_workflow.html:65`) and navigation is a plain link (`:66`). Step 7 must adopt the same contract.

**B3 — Historical integrity (G11).** `STEPS` is three registries at once: form fields, snapshot keys, and printed-resume rows. Removing `penunjang_ekg` / `penunjang_hasil_kritis` from `STEPS[7]` silently (a) drops the keys from every future `clinical_snapshot`, (b) removes the step-7 rows from the printed resume even for already-finalized episodes, and (c) changes the computed digest, marking open drafts as stale-signature. The repo already has the correct pattern: `LEGACY_STEP8_FIELDS` (`forms_igd_workflow.py:32`) keeps retired fields inside `snapshot_visit_fields()` and out of any step, surfaced read-only through `legacy_step8_notes()` (`igd_workflow_views.py:23`). Step 7 must reuse it, not invent a new mechanism. Database columns stay.

---

## 5. Decisions required

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Keep the free-text "Kirim Order Penunjang" as a fallback for items outside the master catalogue, or delete it? | **Keep, collapsed** (`<details>`), doctors-only, labelled "Pemeriksaan di luar master katalog". Deleting it makes B1 fatal on any deployment where activation is incomplete, and the document's target is the *primary* path. If the user insists on deletion, it becomes a separate step gated on B1 being closed. |
| D2 | Where does the requesting doctor record results after "Catat hasil" is removed? | Route it through the performing-service worklist (`pasien:service_orders`), which already supports `record_result`. Requires the EKG item's `destination` to be the IGD unit so IGD doctors pass the `service_units()` check (`penunjang_results.py:17`). Add a read-only "hasil tersedia" counter to step 8's evidence panel so the doctor still sees status without a menu. |
| D3 | What happens to "Order & Hasil Tercatat" information? | Nothing is lost: `clinical_snapshot` already stores `orders` (`igd_finalization.py:29`), step 9's professional panel already lists order status, and the printed resume carries it. Delete the step-7 recap as ordered. |
| D4 | What happens to attachments after "Lampiran Hasil / Dokumen" is removed? | Keep the upload endpoint and the `LampiranAsesmen` model untouched; the assessment wizard and `asesmen_detail` still upload attachments. Only the step-7 surface is removed. |
| D5 | `Rujukan Luar` / `Lainnya` (0 items) — populate or hide? | Hide the two empty L3 groups behind a config flag until real items exist; do not ship clickable dead ends. |

---

## 6. Out of scope

- `igd_dashboard.html:691` free-text order form and `pasien/views.py:2489-2493` legacy writers (`penunjang_ekg`, `penunjang_hasil_kritis`, `penunjang_radiologi_checklist`). They are a different surface (dashboard, not the assessment workflow). Deleting the fields there would break the print template at `cetak_asesmen_medis_igd.html:152-154`.
- Result entry UI of the performing services (`pasien/ancillary_views.py`) — already canonical, unchanged.
- Tariff/billing for penunjang orders — no requirement in the document.

---

## 7. Verification baseline

Command:

```
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test \
  pasien.tests_clinical_expansion pasien.tests_penunjang_results pasien.tests_laboratorium \
  pasien.tests_igd_workflow_integration pasien.tests_revisi_asesmen_medis_igd \
  pasien.tests_wireframe_integration --keepdb --noinput
```

Result: **57 tests, OK, 17.7 s** (2026-11-17). Local `db.sqlite3` is stale — `klinis_kategoripenunjang` / `klinis_itempenunjang` do not exist there, so all verification runs against the test database.

Tests that will need to change because they exercise the removed step-7 field:

| Test | Reason |
|---|---|
| `pasien/tests_igd_workflow_integration.py:25` | `save_step(..., 7, {'penunjang_ekg': 'Hasil eksternal'}, 0)` — the field is no longer owned by step 7, so the call raises `WorkflowValidation` |

Tests that keep passing unchanged and therefore act as regression guards:

| Test | Why it survives |
|---|---|
| `pasien/tests_igd_workflow_integration.py:83`, `:88` | exercise the `order_result` **action**, which is retained as an API even though its step-7 form is removed (decision D2) |
| `pasien/tests_igd_workflow_integration.py:98` | exercises the `igd_workflow_upload` **endpoint**, retained per decision D4 |
| `pasien/tests_revisi_asesmen_medis_igd.py:107` | posts to the **legacy** `igd_asesmen_medis_save` view, not the workflow; unaffected (out of scope, §6) |

Browser probes: `qa/clinical_expansion_browser.py:70-78` and `qa/igd_revision_browser.py:222-232` already drive the cascade and need no change; `qa/igd_revision_browser.py:425-441` encodes the Phase-3 target DOM (`#anc-specimen`, `#anc-external-destination`) and cannot pass today. All three QA files are currently **untracked** (`git status` → `?? qa/…`).

---

## 8. Closure status (2026-11-17)

Every gap below is closed in code and covered by a passing test. `R1`–`R7` are satisfied by the same changes.

| Gap | Closed by | Evidence |
|---|---|---|
| G1 — four legacy menus in step 7 | `_igd_workflow_operations.html` — recap + "Catat hasil" + attachment list + upload form removed from the step-7 block | `test_step7_has_no_legacy_menus` |
| G2 — "Hasil EKG" / "Hasil Kritis" editable | `forms_igd_workflow.py` — `STEPS[7] = ('Pemeriksaan Penunjang', ())`; fields moved to `LEGACY_STEP7_FIELDS` | `test_step7_draft_rejects_retired_fields` |
| G3 — free-text form was the prominent path | demoted into `<details><summary>Pemeriksaan di luar master katalog</summary>`, cascade is the primary surface | `test_step7_renders_cascade` |
| G4 — nothing orderable after import | `activate_penunjang_catalogue` sets `active`/`destination`/`reviewed_by`/`preparation_schema` in one transaction | `test_activation_makes_items_orderable_with_longest_prefix_rule` |
| G5 — no bulk activation path | management command + sidecar (`klinis/data/penunjang_activation.json`) + admin bulk action `activate_selected` | `test_dry_run_writes_nothing`, `test_missing_unit_blocks_activation`, `test_unmatched_item_blocks_activation`, `test_reviewer_is_mandatory` |
| G6 — only 3 of 9 preparation keys reachable | 9 `preparation_fields` in `igd_workflow_views.py`, rendered as `select`/`input` per `prep.kind` with `id="anc-<key>"` | `test_cascade_payload_carries_nine_keys`, QA probe `qa/igd_revision_browser.py:425-441` |
| G7 — required preparation always 400 | `markRequired()` + payload assembly + `missing` validation before POST; server allow-list unchanged | `test_catalogue_requires_specimen_is_orderable`, `test_cascade_payload_carries_nine_keys` |
| G8 — preparation captured once for the whole basket | preparation is read per basket entry at "Tambah ke Daftar Order" and stored per order row | `test_cascade_payload_carries_nine_keys` |
| G9 — "Rujukan Luar" / "Lainnya" dead ends | `IGD_PENUNJANG_HIDE_EMPTY_BRANCHES` (default on) hides L3 groups with no orderable item | `test_empty_branch_hidden_from_cascade` |
| G10 — empty step 7 could never advance | guard relaxed to `if not payload and STEPS[step][1]`; save buttons suppressed; navigation is a plain `?step=8` link | `test_step7_draft_empty_payload_accepted`, `test_step7_has_no_save_buttons` |
| G11 — snapshot/print/digest derived from `STEPS` | `snapshot_visit_fields()` unions `STEPS` ∪ `LEGACY_STEP8_FIELDS` ∪ `LEGACY_STEP7_FIELDS`; history surfaced read-only via `legacy_notes()` | `test_snapshot_keeps_retired_penunjang_fields` |
| G12 — no in-IGD result entry after removal | EKG catalogue items route to the IGD unit, so IGD doctors pass `service_units()` and record from the worklist | `test_igd_doctor_records_ekg_result_routed_to_igd_unit` |
| G13 — `LAINNYA` items had no destination mapping | sidecar `destination_units` maps every `jenis_order` family to a real unit code; `--map KEY=KODE` per environment | `test_activation_makes_items_orderable_with_longest_prefix_rule` |
| G14 — legacy dashboard surface | untouched, still out of scope (§6) | — |

`B1` is closed only after the activation command has run in an environment; the command and its runbook are in place. `B2` and `B3` are closed in code.

### 8.1 Activation runbook (once per environment)

```
# 0. Know which database you are touching: this checkout's .env has DATABASE_URL="" so
#    manage.py falls back to the local db.sqlite3. Export a URL to target Postgres/Supabase.

# 1. Units must exist first — the command refuses to guess
.venv/Scripts/python.exe manage.py shell -c "from akreditasi.models import UnitKerja; print(list(UnitKerja.objects.filter(code__in=['LAB-BDRS','RAD','IGD']).values_list('code',flat=True)))"

# 2. Review the plan, write nothing (add --map for units whose code differs in this environment)
.venv/Scripts/python.exe manage.py activate_penunjang_catalogue --reviewer <username> --dry-run --map RAD=RAD-IMAGING --map NUKLIR=RAD-IMAGING

# 3. Apply (same flags as step 2)
.venv/Scripts/python.exe manage.py activate_penunjang_catalogue --reviewer <username> --map RAD=RAD-IMAGING --map NUKLIR=RAD-IMAGING

# 4. Re-run step 3: no diff, no new writes (idempotent)
```

The `--map` flags are environment-specific. The dev database has `LAB-BDRS`, `IGD` and `RAD-IMAGING`
(no unit literally coded `RAD`), so `RAD` and `NUKLIR` must be redirected to `RAD-IMAGING` there.
An environment that does define `RAD` needs no flags.

### 8.2 Verification actually run (2026-11-17)

```
manage.py test pasien.tests_igd_workflow_integration pasien.tests_wireframe_integration \
  pasien.tests_revisi_asesmen_medis_igd pasien.tests_igd_workflow pasien.tests_igd_lifecycle \
  pasien.tests_3s_cascade pasien.tests_penunjang_results klinis.tests_penunjang_activation --keepdb
→ Ran 71 tests in 25.172s — OK

manage.py test pasien.tests_clinical_expansion pasien.tests_laboratorium --keepdb
→ Ran 28 tests in 4.982s — OK

manage.py makemigrations --check --dry-run
→ No changes detected

manage.py check
→ System check identified no issues (1 silenced)

node --check static/js/igd-clinical-expansion.js
→ JS_OK
```

No migration is required: the retired fields stay in the database, only their step ownership changed.

### 8.3 Activation applied — dev database (2026-11-17)

`B1` is now closed in the dev environment, not only in code.

```
manage.py migrate --no-input
→ exit 0, pasien.0027 … pasien.0032 applied

manage.py import_penunjang_catalogue --apply
→ {"created": 132, "counts": {"nodes": 38, "items": 94}, "source_sha256": "a42f2b70…"}

manage.py activate_penunjang_catalogue --reviewer monsiskami --dry-run --map RAD=RAD-IMAGING --map NUKLIR=RAD-IMAGING
→ Dry run: 94 item akan diaktifkan, 0 tanpa aturan, 0 dilewati.

manage.py activate_penunjang_catalogue --reviewer monsiskami --map RAD=RAD-IMAGING --map NUKLIR=RAD-IMAGING
→ 94 item katalog penunjang aktif.  IGD: 17  LAB-BDRS: 49  RAD-IMAGING: 28

orderable_items().count() / ItemPenunjang.objects.count()
→ 94 / 94
```

Before the command ran, the same database answered
`CommandError: Unit kerja tujuan tidak ditemukan: RAD=RAD, NUKLIR=RAD` — the fail-closed
behaviour, not a silent partial activation.

Browser proof on a disposable database (same code, same sidecar) confirmed the full single path:
four cascade levels, nine preparation inputs, zero legacy menus, zero submit buttons inside
`#igd-step-form`, an `OrderPenunjang` row written with `jenis=LAB status=ORDERED dest=LAB-BDRS
preparation.specimen=Sputum`, and the step-8 link advancing to `?step=8` with no `/aksi/` POST.
Step 8 renders that order by name:
`Penunjang: Tes Cepat Molekuler (TCM / GeneXpert TBC) — ORDERED · Belum ada hasil yang dapat dipakai`.

