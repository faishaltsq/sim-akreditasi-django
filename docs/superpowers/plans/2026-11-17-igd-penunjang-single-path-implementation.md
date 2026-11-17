# IGD Penunjang Single-Path Ordering — Implementation Plan

- **Date:** 2026-11-17
- **Analysis:** `docs/superpowers/specs/2026-11-17-igd-penunjang-single-path-gap-analysis.md`
- **Source requirement:** `perubahan menu di penunjang aplikasi ARima dengan alur cascading dropdown 17 11.docx`
- **Goal:** step 7 of the IGD assessment workflow carries exactly one penunjang surface — the 4-level cascading order menu — with the four legacy menus removed, historical records intact, and the catalogue actually orderable.
- **Non-goals:** dashboard order form (`igd_dashboard.html:691`), performing-service result UI, penunjang tariffs/billing.

## Decisions applied

| ID | Decision |
|---|---|
| D1 | Free-text order form is **kept but demoted** into a collapsed `<details>` ("Pemeriksaan di luar master katalog"), doctors only. Never the primary path. |
| D2 | Results are recorded through the performing-service worklist (`record_result`); EKG is routed to the IGD unit so IGD doctors qualify via `service_units()`. |
| D3 | The step-7 recap is deleted; order visibility survives in `clinical_snapshot['orders']`, step 9's professional panel, step 8's evidence panel and the printed resume. |
| D4 | Attachment model and upload endpoint stay; only the step-7 surface is removed. |
| D5 | L3 groups with zero active items are hidden behind `IGD_PENUNJANG_HIDE_EMPTY_BRANCHES` (default on). |

## Invariants (must hold at every phase boundary)

1. **No historical loss.** `penunjang_ekg` / `penunjang_hasil_kritis` keep their DB columns, keep appearing in `clinical_snapshot['visit']`, and keep printing on `igd_workflow_resume` and `cetak_asesmen_medis_igd.html:153-154`.
2. **Digest stability.** For a visit whose data does not change, `clinical_snapshot` output is byte-identical before and after Phase 1. No open draft becomes stale-signature because of this work.
3. **Single writer per fact.** Order creation stays `order_batch`; result creation stays `record_result`. No new code path writes `OrderPenunjang` fields directly.
4. **Server-side authority.** The cascade's legality is enforced in `klinis/services/penunjang_catalogue.py` and `pasien/services/penunjang_orders.py`; the browser only mirrors it.
5. **Green workspace.** Each phase ends with the affected test modules passing.

---

## Phase 0 — Safety net (no production behaviour change)

### 0.1 Record the baseline

```
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test \
  pasien.tests_clinical_expansion pasien.tests_penunjang_results pasien.tests_laboratorium \
  pasien.tests_igd_workflow_integration pasien.tests_revisi_asesmen_medis_igd \
  pasien.tests_wireframe_integration --keepdb --noinput
```

Expected: `Ran 57 tests … OK` (measured 2026-11-17, 17.7 s).

### 0.2 Write the failing tests first

New module `pasien/tests_igd_penunjang_single_path.py`:

| Test | Assertion |
|---|---|
| `test_step7_has_no_legacy_menus` | response body for `?step=7` contains none of: `Hasil EKG`, `Hasil Kritis Penunjang`, `Order &amp; Hasil Tercatat`, `Lampiran Hasil / Dokumen`, `id="igd-upload-form"`, `id="result-` |
| `test_step7_renders_cascade` | body contains `id="igd-ancillary"`, four `data-anc-level` selects, `id="anc-basket"` |
| `test_step7_has_no_save_buttons` | body for `?step=7` contains no `value="save"` / `value="next"`, and contains a link to `?step=8` |
| `test_step7_draft_empty_payload_accepted` | `POST /igd/<pk>/draft/7/` with `{"fields": {}, "version": v}` → 200, `last_step == 7` |
| `test_snapshot_keeps_retired_fields` | `clinical_snapshot(visit)` `['visit']` still has both keys |
| `test_resume_prints_retired_fields` | a FINAL revision whose snapshot has `penunjang_ekg='Sinus takikardi'` renders that string on the resume page |
| `test_catalogue_requires_specimen_is_orderable` | item with `preparation_schema={'required':['specimen']}` → `order_batch` succeeds when `preparation.specimen` is supplied, 400 when absent |
| `test_empty_branch_hidden` | L3 with zero active items is absent from `list_choices(parent=L2)` |

Run it: every test above must fail for the documented reason before any source change.

---

## Phase 1 — Retire the two step-7 fields without touching history

Reuse the existing `LEGACY_STEP8_FIELDS` mechanism — do not invent a parallel registry.

### 1.1 `pasien/forms_igd_workflow.py`

- After `LEGACY_STEP8_FIELDS` (line 32) add:
  ```python
  LEGACY_STEP7_FIELDS = ('penunjang_ekg', 'penunjang_hasil_kritis')
  ```
- Line 22 → `7: ('Pemeriksaan Penunjang — Order', ()),`
- `snapshot_visit_fields()` (line 35) → union `LEGACY_STEP8_FIELDS | LEGACY_STEP7_FIELDS` so both retired groups stay in the snapshot and the digest is unchanged.

Verify: `modelform_factory(KunjunganPasien, fields=())` is legal and renders empty (confirmed empirically) — `form_for_step(7, …)` keeps working.

### 1.2 `pasien/igd_workflow_views.py`

- Generalise `legacy_step8_notes` (line 23) to `legacy_notes(source)` iterating `LEGACY_STEP7_FIELDS + LEGACY_STEP8_FIELDS`, keeping the "only if truthy" filter.
- Context key `legacy_step8_notes` → `legacy_notes` at both call sites (line 178 for the workflow page, line 355 for the resume page).
- Printed resume sections (line 351) skip steps with empty `names`, so step 7 would vanish. Append an explicit synthetic section:
  ```python
  sections.append({'number': 7, 'title': STEPS[7][0],
                   'rows': [{'label': KunjunganPasien._meta.get_field(n).verbose_name, 'value': saved.get(n)}
                            for n in LEGACY_STEP7_FIELDS]})
  ```
  Keep it after the loop so ordering stays 1..11 and the step-6 exclusion is unaffected.

### 1.3 Templates

- `templates/pasien/igd_workflow.html:49` — rename the context variable and the heading to "Catatan penunjang historis — hanya baca"; the block must render on step 7 only when `legacy_notes` is non-empty.
- `templates/pasien/igd_workflow_resume.html:10` — same rename.

### 1.4 Exit criteria

- `test_snapshot_keeps_retired_fields` and `test_resume_prints_retired_fields` pass.
- Diff of `clinical_snapshot()` for an unchanged visit: empty. `clinical_snapshot` feeds `content_digest` (`igd_finalization.py:59`) and the stale-signature fingerprint (`:159-163`), so this diff is what keeps open drafts valid.
- Finalization readiness is unaffected: `missing_sections()` (`igd_finalization.py:64-82`) keys `investigations` off `visit.order_penunjang.exists()`, never off the retired text fields.
- No migration created (`makemigrations --check` clean).

---

## Phase 2 — Step 7 becomes a single surface

Target DOM for `?step=7`, in order: **cascade → collapsed manual fallback → navigation**. No step form, no recap, no attachments.

### 2.1 `templates/pasien/_igd_workflow_operations.html`

Replace the whole step-7 block (lines 1–7) with a manual-fallback-only block:

```django
{% if step == 7 and not readonly and can_sign_medical %}
<details class="card card-body my-3">
  <summary>Pemeriksaan di luar master katalog</summary>
  <p class="form-text">Gunakan hanya bila pemeriksaan tidak tersedia pada pilihan bertingkat di atas.</p>
  {% include 'pasien/_igd_action_form.html' with operation_form=order_form operation='order' button_label='Kirim Order' %}
</details>
{% endif %}
```

Deleted: "Order & Hasil Tercatat" recap (line 3), the `order_result` "Catat hasil" form (line 4), the attachment list (line 5), the upload form (line 6).

### 2.2 `templates/pasien/igd_workflow.html`

- Wrap the step form so it is skipped on step 7 (the cascade carries its own `<form>`, and nested forms are invalid HTML):
  ```django
  {% if step != 7 %}<form id="igd-step-form" …> … </form>{% endif %}
  ```
- Add a step-7 navigation bar outside the form, mirroring step 9 (`:65`):
  ```django
  {% if step == 7 %}<div class="igd-actions">
    <a class="btn btn-outline-secondary" href="?step=6">Sebelumnya</a>
    <a class="btn btn-primary" href="?step=8">Lanjut ke Penetapan Diagnosis</a>
  </div>{% endif %}
  ```
- Keep `{% include 'pasien/_igd_ancillary_order.html' %}` where it is (it already renders only when `step == 7 and can_sign_medical and not readonly`).

`static/js/igd-assessment-workflow.js:4` already bails out when `#igd-step-form` is absent, and the cascade has its own dirty-guard via `watch()` in `static/js/igd-clinical-expansion.js`.

### 2.3 `pasien/services/igd_assessment_workflow.py:88`

Harden the empty-payload guard for field-less steps so any legacy client that still posts an empty step-7 draft gets a version bump instead of a 400:

```python
if not payload and STEPS[step][1]:
    raise WorkflowValidation({'__all__': ['Tidak ada perubahan untuk disimpan.']})
```

`changed = []` then flows through harmlessly (visit save skipped, `last_step` set, version bumped).

### 2.4 `pasien/igd_workflow_views.py`

- Keep `order_form` in context (needed by 2.1).
- `orders` and `attachments` stay in context — step 9's professional panel and the resume still consume them; only the step-7 template stops rendering them.

### 2.5 Exit criteria

- `test_step7_has_no_legacy_menus`, `test_step7_renders_cascade`, `test_step7_has_no_save_buttons`, `test_step7_draft_empty_payload_accepted` pass.
- Manual check on a seeded episode: step 7 → order an item → "Lanjut ke Penetapan Diagnosis" → step 8 shows the order in "Dasar saran".
- `pasien/tests_igd_workflow_integration.py:25` updated from `save_step(..., 7, {'penunjang_ekg': …})` to an empty payload, with a new assertion that the retired field still lands in `clinical_snapshot`. Lines `:83`, `:88` (`order_result` action) and `:98` (`igd_workflow_upload` endpoint) must keep passing untouched — they are the regression guards for decisions D2 and D4.

---

## Phase 3 — Make the cascade able to order the whole catalogue

Server already accepts 9 preparation keys (`penunjang_orders.py:26`); the UI offers 3 (`igd_workflow_views.py:183`). Close that gap and make preparation per item.

### 3.1 Context — `pasien/igd_workflow_views.py:183`

Replace the 3-entry list with a declarative 9-entry one:

| key | label | kind |
|---|---|---|
| `fasting` | Status puasa | select (YES/NO/UNKNOWN/NA) |
| `pregnancy` | Kehamilan | select |
| `contrast_allergy` | Alergi kontras | select |
| `contrast` | Kontras / non-kontras | text |
| `specimen` | Jenis spesimen | text |
| `site` | Lokasi pengambilan sampel | text |
| `region` | Regio pemeriksaan | text |
| `side` | Sisi (kanan / kiri / bilateral) | text |
| `external_destination` | Laboratorium / RS rujukan | text |

### 3.2 Template — `_igd_ancillary_order.html:11-13`

Render `select` for `kind == 'select'` (keep `data-anc-prep`) and `<input class="form-control">` for `kind == 'text'` with `data-anc-text`. Both must carry `id="anc-{{ prep.key }}"` — the untracked probe `qa/igd_revision_browser.py:427-441` already selects `#anc-specimen` and `#anc-external-destination` and tolerates either tag (`evaluate('el=>el.tagName') == 'SELECT'`). Show a `required` marker when the selected L4 item lists the key in `preparation_schema.required`.

### 3.3 JavaScript — `static/js/igd-clinical-expansion.js:114-131`

- Capture both `[data-anc-prep]` and `[data-anc-text]` into `preparation` at "Tambah ke Daftar Order" (already snapshots per row — this fixes G8 by making the snapshot explicit and per item).
- On L4 change, read the item's `preparation_schema.required` and mark the matching inputs required; block `anc-add` with a specific message naming the missing key instead of letting the server answer 400.
- Keep `variants` rendering generic (`:114`) — it already drives `data-anc-variant`.

### 3.4 Tests

- `test_catalogue_requires_specimen_is_orderable` (from Phase 0).
- `test_cascade_payload_carries_nine_keys` — POST an `order_batch` with all 9 keys → stored `OrderPenunjang.preparation` equals the submitted dict.
- `test_variant_must_match_catalogue` — `variants={'contrast':['POLOS','KONTRAS']}` with `contrast='MAGNETIC'` → 400.
- Cross-check against the existing WIP fixture `qa/igd_revision_fixture.py:158` (`QAR-REFERRAL`, `preparation_schema={'required': ['specimen','external_destination']}`, `variants={'specimen': ['SYNTHETIC EDTA','SYNTHETIC Serum']}`) — after Phase 3 the probe at `qa/igd_revision_browser.py:425-441` must pass unmodified. That probe is the acceptance test for this phase.

### 3.5 Exit criteria

Every item can be ordered from the browser once activated with a schema; no client-side 400 surprises.

---

## Phase 4 — Activation tooling (this is what makes B1 go away)

### 4.1 Data sidecar — `klinis/data/penunjang_activation.json`

Rules are matched by **longest matching `prefix`** against the level-3 group code, so 94 imported items need 12 rules rather than 94 entries.

```json
{
  "version": "DOCX-2026-11-13-STAGING",
  "destination_units": {"LAB": "LAB-BDRS", "PA": "LAB-BDRS", "BDRS": "LAB-BDRS", "RAD": "RAD", "EKG": "IGD", "ENDO": "IGD", "NUKLIR": "RAD"},
  "rules": [
    {"prefix": "laboratorium-rujukan-luar-", "unit": "LAB", "required": ["specimen", "external_destination"]},
    {"prefix": "laboratorium-", "unit": "LAB", "required": ["specimen"]},
    {"prefix": "penunjang-diagnostik-radiologi-pencitraan-ct-scan", "unit": "RAD", "required": ["contrast", "pregnancy"]},
    {"prefix": "penunjang-diagnostik-elektrofisiologi-", "unit": "EKG", "required": []}
  ]
}
```

Rule: EKG item → `IGD` (decision D2, so IGD doctors pass `service_units()`); lab → `LAB-BDRS`; imaging → the radiology unit code present in `UnitKerja`. Unit codes are overridable per environment with `--map KEY=KODE` instead of editing the file.

### 4.2 Management command — `klinis/management/commands/activate_penunjang_catalogue.py`

```
manage.py activate_penunjang_catalogue --reviewer <username> --sidecar klinis/data/penunjang_activation.json [--dry-run] [--map KEY=KODE] [--allow-missing]
```

Behaviour as built:
- Loads the sidecar; validates `rules` and `destination_units` are non-empty.
- Resolves `destination` by `UnitKerja.code`; aborts listing every unresolved code rather than partially applying (`--allow-missing` downgrades that to a warning).
- Sets `destination`, `reviewed_by`, `preparation_schema`, `active=True`, then calls `full_clean()` per row (which enforces `expansion_models.py:52`) inside one transaction — any validation failure rolls the whole run back.
- Refuses preparation keys outside the 9-key allow-list (`pasien/services/penunjang_orders.py:26`), so a typo in the sidecar fails loudly instead of producing an unsendable item.
- `--dry-run` prints the planned changes and writes nothing.
- Idempotent: re-running produces no diff.
- Emits a per-unit activated count plus the unmatched/skipped code lists.

### 4.3 Admin — `klinis/expansion_admin.py:24`

As built:
- `list_filter = ('active','jenis_order','destination','group__parent__parent')`, `list_select_related = ('destination','group')`, `search_fields = ('kode','nama')`.
- Bulk action `activate_selected` sets `active=True` + `reviewed_by=request.user`, runs `full_clean()` per row and reports the rejected codes — no intermediate form, because the sidecar command owns the bulk path.

### 4.4 Runbook (documented in the plan, executed once per environment)

1. Confirm the destination units exist: `UnitKerja.objects.filter(code__in=[...])` → all present, else create them first.
2. `--dry-run`, review the diff.
3. Apply.
4. Walk the API: for each of the 9 L2 nodes, call `list_choices(parent=<L3>)` and assert ≥1 active item — script it, print a table, fail loudly on an empty branch (except the two hidden ones).
5. Log in as an IGD doctor, order one item per branch, confirm the worklist of the destination unit sees it.

### 4.5 Exit criteria

Fresh test DB + `import_penunjang_catalogue` + `activate_penunjang_catalogue` → the cascade returns items on every branch; ordering works end to end.

---

## Phase 5 — Result path after the in-step form is gone

1. **Data:** the EKG item's `destination` is the IGD unit (Phase 4 sidecar).
2. **Worklist:** IGD doctors open `pasien:service_orders`, which now includes IGD-destined orders because `service_units()` accepts `DOKTER_UMUM` with a unit assignment (`penunjang_results.py:17-38`).
3. **Visibility without a menu:** step 8's evidence panel already renders `recommendation_context.investigations` with `status` + "Hasil tersedia" (`igd_workflow.html:43`); verify it flips after a result is recorded. Step 9's professional panel keeps the read-only "Obat & penunjang — status operasional" list.
4. **Tests (as built):**
   - `pasien/tests_penunjang_results.py::test_igd_doctor_records_ekg_result_routed_to_igd_unit` — doctor with the IGD unit sees the EKG order in `?jenis=EKG` worklist and records `SELESAI`; `result_recorded_by` set, `AuditLog` row written.
   - `pasien/tests_igd_workflow_integration.py::test_step7_draft_rejects_retired_fields` — the in-step form cannot come back through the draft endpoint.

---

## Phase 6 — No dead-end branches

- `klinis/services/penunjang_catalogue.py` `list_choices`: when `settings.IGD_PENUNJANG_HIDE_EMPTY_BRANCHES` is on, annotate non-leaf results with `Exists(orderable_items().filter(group=OuterRef('pk')))` and drop zero-count children. Built as a single `orderable_items()` gate shared with `resolve_items`, so "visible in the cascade" and "actually orderable" can never drift apart.
- Default `True` in settings; the two empty groups (`Rujukan Luar`, `Lainnya`) disappear from the cascade until they own real items.
- Test: `test_empty_branch_hidden_from_cascade` proves both the hidden and the shown direction by flipping the setting.

---

## Phase 7 — QA probes and documentation

| File | Change |
|---|---|
| `qa/clinical_expansion_browser.py:70-78` | no change — already drives the cascade by label |
| `qa/igd_revision_browser.py:222-232` | no change — cascade journey stays valid |
| `qa/igd_revision_browser.py:425-441` | becomes the Phase-3 acceptance probe; must pass unmodified after Phase 3 |
| `qa/igd_revision_browser.py` (step-7 entry) | **done** — new scenario `step7_single_path` (`SCENARIOS` entry + method): asserts no legacy surface, no submit button and no `penunjang_*` input in step 7, 4 cascade selects + 9 preparation inputs present, then clicks "Lanjut ke Penetapan Diagnosis" and asserts the URL is `?step=8` with zero recorded `/aksi/` POSTs |
| `docs/superpowers/plans/2026-11-16-igd-ancillary-integration-completion.md` | add a "superseded by 2026-11-17 single-path plan" note on the free-text-fallback decision |
| `docs/superpowers/specs/2026-11-17-igd-penunjang-single-path-gap-analysis.md` | mark G1–G13 closed with the phase that closed them |

---

## Verification matrix

| Requirement | Test | Manual |
|---|---|---|
| R1 Hasil EKG gone | `test_step7_has_no_legacy_menus` | step 7 shows no EKG textarea |
| R2 Hasil Kritis gone | `test_step7_has_no_legacy_menus` | — |
| R3 Order & Hasil Tercatat gone | `test_step7_has_no_legacy_menus` | order still visible on step 8 / step 9 |
| R4 Lampiran gone | `test_step7_has_no_legacy_menus` | upload still works from the assessment wizard |
| R5 single cascade | `test_step7_renders_cascade`, `test_catalogue_requires_specimen_is_orderable` | 4 dependent selects, basket, submit |
| R6 metadata | `test_cascade_payload_carries_nine_keys`, `test_variant_must_match_catalogue` | priority / indication / diagnosis / preparation per item |
| R7 audit snapshot | `test_snapshot_keeps_retired_penunjang_fields` + existing `item_snapshot` tests | `OrderPenunjang.catalogue_snapshot` carries the full L1→L3 path |

Full gate:

```
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test \
  pasien klinis --keepdb --noinput
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

## Rollback

| Phase | Rollback |
|---|---|
| 1 | Revert the three files; columns were never dropped, so data is untouched |
| 2 | Restore `_igd_workflow_operations.html` step-7 block from git; the cascade was never removed |
| 3 | UI-only revert; server already accepted 9 keys before this work |
| 4 | `activate_penunjang_catalogue` has no inverse by design — deactivate through the admin bulk action; no schema change |
| 5 | Data-only (destination assignment) |
| 6 | Flip `IGD_PENUNJANG_HIDE_EMPTY_BRANCHES = False` |

## Risk register

| Risk | Mitigation |
|---|---|
| Activation runbook is skipped in an environment → cascade empty and (with D1) doctors fall back to free text | Phase 4 step 4 (API walk) is a release gate, not optional; the empty state message names the admin path |
| Doctors cannot record EKG results because the destination is not their unit | Phase 5 step 1 pins EKG → IGD; `test_igd_doctor_records_result_via_worklist` guards it |
| Open drafts get stale signatures from the field retirement | Phase 1.1 keeps both keys in `snapshot_visit_fields()`; digest-diff check is an exit criterion |
| Historical resume loses step-7 rows | Phase 1.2 synthetic section + `test_resume_prints_retired_fields` |
| 20 `LAINNYA` items land in the wrong unit | Sidecar is explicit per item code; unknown codes abort the whole run |
