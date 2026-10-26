# Kredensial & RKK (BAB KREDENSIAL) — Verified Gap Register and Completion Plan

> **For agentic workers:** Proposed work only. Producing this plan authorizes no implementation, migration, seed run, grant, commit, or deployment. Execute only after owner approval, using `superpowers:executing-plans` or `superpowers:subagent-driven-development`, one task at a time, RED → minimal implementation → GREEN.

**Goal:** Close the distance between `C:/Users/cubeb/Downloads/BAB KREDENSIAL.docx` and the six delivered Kredensial sub-menus so that every claimed artefact (white paper, RKK catalog, self-assessment, peer review, E-SP&amp;K/E-RKK, RME access control, clinical directory) exists as a working, printable, accreditation-linked feature rather than a partial model.

**Architecture:** Extend the existing `sdm` credentialing families (`KatalogTindakan`, `PengajuanKredensial`, `RincianKewenangan`, `PenilaianTindakan`, `KeputusanKredensial`, `PenugasanKlinis`, `PrivilegeSnapshot`, `ClinicalAccessCode`) instead of adding a parallel module. Add the missing reference layer (white paper + career grade binding), fix the broken issuance chain (`status_spk` is never written by any UI path), and add the document/export layer on top of data that is already authoritative.

**Tech Stack:** Existing Django 6.1 / templates / Bootstrap 5, SQLite and PostgreSQL, `qrcode[pil]`, `reportlab`, `openpyxl`. No new frontend framework, no paid signing provider, no WhatsApp vendor integration in the first release.

**Source:** `C:/Users/cubeb/Downloads/BAB KREDENSIAL.docx` (1,222 paragraphs, read in full).

---

## Global Constraints

- All UI copy is Bahasa Indonesia. Empty configuration reads `Belum dikonfigurasi`; insufficient source data reads `Belum dapat dihitung`; unreleased workflow reads `Belum diaktifkan`. Never render 100% or a green badge for missing data.
- Every list/detail/write/print/export boundary keeps a server-side capability **and** unit-scope check. Menu visibility is never the enforcement boundary.
- A printed SPK/RKK is an authenticated document with a validation code. It must never be labelled *tanda tangan elektronik tersertifikasi* — no signing provider exists in this stack.
- Do not hardcode EP numbers. The active catalogue is `STARKES Edisi 2022` (`akreditasi_framework` id=1, `is_active=1`, `lifecycle=ACTIVE`); the 2024 edition is staged and not active. Any EP reference is resolved at render time from the active framework, and an absent code renders as `Belum dipetakan`, not as a fabricated number.
- `PeristiwaSDM` is append-only and must record every state transition in this module. Do not add mutable audit rows.
- Preserve every existing route name in `sdm/urls.py` and every existing test in `sdm/tests/`.

---

## Verified baseline — what already exists

Read-only inspection on `master` at `d9bc2f5`. `python manage.py check` clean; `makemigrations --check` reports no drift; `sdm.tests.test_kredensial_bab + test_formasi + test_wisn + test_clinical_access` = **33 tests, OK**.

| Source requirement | Existing implementation | Status |
|---|---|---|
| Sub-menu 1 — Master catalog RKK with M/S/T | `sdm/models/katalog_rkk.py:38` `KatalogTindakan` (`kode`, `nama`, `jenjang`, `tingkat_supervisi` M/S/MT/T); `sdm/views.py:1158` `kredensial_katalog`; seeded by `sdm/management/commands/seed_katalog_rkk.py` | Partial |
| Profession & career-grade grouping | `MasterProfesiPegawai` (23 rows), `MasterJenjangProfesi` (19 professions with grades) | Partial |
| Sub-menu 2 — Self-service submission | `sdm/views.py:1547` `kredensial_pengajuan_sendiri`; `templates/sdm/kredensial/pengajuan_saya.html`; `PengajuanKredensial.jenis` AWAL/REKREDENSIAL/PENAMBAHAN | Partial |
| Sub-menu 3 — PSV & peer review | `VerifikasiSumber` (`sdm/models/kredensial.py:10`), `PenilaianTindakan` (`:245`, unique per request+line), `sdm/views.py:1585` `kredensial_panel_bestari` | Working |
| Sub-menu 4 — E-SPK & E-RKK issuance | `KeputusanKredensial` (immutable), `PenugasanKlinis`, `terbitkan_spk_lengkap` (`sdm/services/rekrutmen.py:265`), print views `:834`/`:969` with QR | **Broken chain** |
| Sub-menu 5 — RME access control | `PrivilegeSnapshot`, `ClinicalActionCode`, `require_clinical_action` (`sdm/services/clinical_access.py:59`), read-only view `sdm/views.py:1015` | Model only, no enforcement |
| Sub-menu 6 — Clinical directory | `sdm/views.py:1078` `kredensial_peta` + `templates/sdm/kredensial/peta.html` | Partial |
| OPPE/FPPE feed for re-credentialing | `EvaluasiPraktikKlinis`, `KasusFPPE` (`sdm/models/evaluasi_klinis.py`) | Model only, no UI |
| SPK expiry EWS | `PengingatSDM` + `sync_spk_reminders` (`sdm/models/pengingat.py:200`), bands LT_30/LT_90/EXPIRED | Partial |
| Audit evidence sheet | `sdm/views.py:996` `kredensial_bukti_audit` + `templates/sdm/kredensial/bukti_audit.html` | Working |
| Trainee/supervised action model | `TraineePlacement` (`sdm/models/clinical_access.py:11`) | Model only |

---

## Gap matrix

### P0 — the module cannot produce a valid RKK from the UI

| # | Gap | Evidence | Consequence |
|---|---|---|---|
| K1 | `RincianKewenangan.status_spk` is **never written by any application path**. Peer review writes `PenilaianTindakan` only. | Only reads at `sdm/services/rekrutmen.py:284`; only writes are in `sdm/tests/test_kredensial_bab.py:181,187`. | `terbitkan_spk_lengkap` skips every line → **an SPK can be issued with zero privilege snapshots**, so RME auto-mapping never activates. |
| K2 | The "Tambah Rincian Kewenangan" form posts free text only; `catalog_item` is never selected. | `templates/sdm/kredensial/detail.html:37-47` posts `kewenangan` + `catatan`; `sdm/views.py:1645` saves whatever arrives. | Privileges are unlinked to `KatalogTindakan`, so snapshots fall back to synthetic `EXT-{pk}` codes (`rekrutmen.py:283-286`) instead of `K-KPR-012`. The whole "auto-mapping access control RME" premise collapses. |
| K3 | **No career grade on `Pegawai`.** `Pegawai` has `profesi_master` but no `jenjang`. | `grep -c jenjang sdm/models/pegawai.py` → 0. | Catalog filtering by grade is impossible. `kredensial_akses_rme` (`sdm/views.py:1057`) filters `KatalogTindakan` by **profession only**, so a PK-I nurse is evaluated against PK-V privileges; `kredensial_peta` (`:1109`) builds a **global** `kode → tingkat_supervisi` map with no profession or grade filter at all. M/S accuracy is wrong for every graded profession. |
| K4 | **Dokter and Apoteker have an empty catalog.** 273 seeded actions cover only Perawat (19), Bidan (18) and 17 nakes-lain professions. | `_data_katalog_rkk.py:14` `PROFESI_TANPA_JENJANG` = DOKTER_SP, DOKTER_UMUM, DOKTER_GIGI, APOTEKER; DB: each has 0 jenjang and 0 tindakan. | The document's own example (`dr. Ahmad Dahlan, Sp.PD — 142 Mandiri`) is unreproducible. Komite Medis — the primary committee — has no catalog at all. |
| K5 | No white-paper layer. No minimum qualification (education, mandatory training, minimum case count, logbook) per grade. | No model, no route, no template. `KatalogTindakan` has only `catatan` (free text). | KPS "white paper" evidence cannot be produced; the catalog cannot justify why a grade holds an action. |
| K6 | **`tingkat_supervisi='T'` has zero rows** (207 M, 58 S, 8 MT, 0 T). | DB count on `sdm_katalogtindakan`. | The document's `Export PDF Katalisator RKK per Komite &amp; Jenjang` with three columns (Mandiri/Supervisi/Ditolak) has an empty third column; the "Tidak Diberikan" concept exists only at request level. |

### P1 — documents and controls the source promises but the app does not emit

| # | Gap | Evidence |
|---|---|---|
| K7 | No public QR verification. The QR encodes `reverse('sdm:kredensial_detail')`, which is `@login_required` + capability-gated, so scanning it shows a login wall. No SHA-256 of (SPK data + RKK + issuer + timestamp), no verification model, no `/verify-credentials` route. | `sdm/views.py:850-862`; `config/urls.py:10-14`. |
| K8 | Zero export routes for the module. Missing: white paper print, catalog PDF per committee/grade, employee SPK+RKK summary PDF, catalog Excel, self-assessment form print, logbook/SKP portfolio PDF, document-completeness checklist PDF, submission tracking Excel, peer-review berita acara, verified-portfolio PDF, committee recommendation letter PDF, peer-review progress Excel, RME access log PDF, unit directory PDF. | 72 routes in `sdm/urls.py`; none matches. Only `kredensial_cetak_spk`, `kredensial_cetak_rkk`, `kredensial_bukti_audit` exist. |
| K9 | Approval chain is a single capability. Committee review, HRD verification, and director issuance all require `can_review_hc_credentials`. `issue_spk` never checks that the actor is the director. | `sdm/services/rekrutmen.py:212,265`; `sdm/views.py:813,878,900`. One user can submit, review, decide, and issue. |
| K10 | EWS is in-app only. `CHANNEL_CHOICES = [('IN_APP', ...)]`; SPK reminders emit LT_30 / LT_90 / EXPIRED and skip LT_60 although the model defines it; `hc_reminders` is not scheduled anywhere (no cron, no CI job — only invoked from a test). | `sdm/models/pengingat.py:29,200-241`; `sdm/tests/test_dashboard.py:226`. |
| K11 | Audit trail has no IP address and no request context. | `sdm/models/audit.py` fields: actor, jenis, target, statuses, alasan, `correlation_id` (always blank). |
| K12 | `kredensial_pengajuan_sendiri` requires `can_review_hc_credentials`. | `sdm/views.py:1549`. A staff member cannot file their own request without also gaining unit-wide reviewer visibility. |
| K13 | Silent 200-row truncation in the RME access picker. | `sdm/views.py:1067` `'employees': employees[:200]`. |
| K14 | No logbook upload path although the FK exists. | `PengajuanKredensial.logbook` → `VersiDokumen`; no form field in `pengajuan_saya.html` or `detail.html`. |
| K15 | Directory has no expiry-state colouring and no on-duty headcount. Only M/S/MT from the catalog is rendered. | `templates/sdm/kredensial/peta.html:94-96`; `sdm/views.py:1105-1150`. |
| K16 | OPPE/FPPE is not consumed by re-credentialing anywhere. | `EvaluasiPraktikKlinis` has no reader outside tests. |
| K17 | No "auto-link to EP" data. `PemetaanStandarSDM` = 0 rows, `AturanDokumen` = 0 rows, `EvidenceReq` = 0 rows. | DB counts. Nothing can be published as accreditation evidence yet. |

### Document corrections the owner must accept before implementation

| # | Claim in `BAB KREDENSIAL.docx` | Actual catalogue | Action |
|---|---|---|---|
| C1 | "KPS 19–20 (Tenaga Kesehatan Lainnya)" and "KPS 15–16 (Keperawatan)", "KPS 13" | Active framework has KPS 1–12, 14, 16, 17 only. **No KPS 13, 15, 18, 19, 20.** The staged 2024 fixture adds 8.1, 10.1, 15, 18, 19 — still no 13 or 20. | Rewrite the mapping table against real codes; treat "KPS 19–20" as aspirational and mark it `Belum dipetakan` in the UI. |
| C2 | "MI 2 (Manajemen Informasi Rekam Medis)" | No `MI` chapter exists. The equivalent is `MRMIK 2`. | Correct to `MRMIK 2`. |
| C3 | "KPS 10 = kredensial perawat", "KPS 12 = kredensial nakes lain" | True for the **2022** catalogue (active). The 2024 fixture renumbers: KPS 10 = medical staff bylaws, KPS 14/15/16 = nursing, KPS 17/18/19 = other health workers. | Any hardcoded EP string breaks at cutover. Resolve by code at render time. |
| C4 | "KPS 7 = white paper/kredensial" | Active KPS 7 = K3RS (occupational health). 2024 KPS 7 = new-staff orientation. | Do not map white paper to KPS 7. |
| C5 | Kode profesi example `K-SPD-001` | Seeder emits `K-{PROFESI_CODE}-{NNN}`, e.g. `K-KPR-001`. `DOKTER_SP` would produce `K-DOKTER_SP-001`. | Decide the display code convention before adding doctor catalogs. |
| C6 | "KPS 1 EP 1–4" (in the Formasi document) | Active KPS 1 has **one** EP. | Same fix: resolve from the active framework. |

---

## Task K-A1 — Bind career grade to the employee record (P0)

**Depends on:** nothing. Blocks K-A2, K-A5, K-A7.

- [ ] Add RED tests: a PK-I nurse and a PK-V nurse in the same unit resolve different `KatalogTindakan` sets; an employee with no grade renders `Belum dikonfigurasi` and never falls back to the whole profession; a grade belonging to another profession is rejected.
- [ ] Add `Pegawai.jenjang` FK → `MasterJenjangProfesi` (`null=True`, `blank=True`, `on_delete=PROTECT`) with a `clean()` guard that `jenjang.profesi_id == profesi_master_id`. Migration `0033_*`.
- [ ] Expose the field in the intake wizard, `pegawai_edit`, and the Excel importer template; add a reconciliation command that reports graded-profession employees missing a grade.
- [ ] Backfill nothing silently. Existing rows stay `NULL` and surface as a data-quality count.
- [ ] GREEN gate: `test_kredensial_bab`, `test_intake`, `test_staff_import`, `test_pegawai_models` pass; no employee row is mutated by the migration.

## Task K-A2 — Make the catalog authoritative for every privilege line (P0)

**Depends on:** K-A1.

- [ ] Add RED tests: posting a privilege without `catalog_item` is rejected; posting a catalog item from another profession or a higher grade is rejected; a line whose catalog grade exceeds the employee grade is rejected; issuing an SPK produces snapshots keyed by the **catalog code** (`K-KPR-012`), never `EXT-*`.
- [ ] Replace the free-text privilege form with a catalog picker filtered by `employee.profesi_master` + `employee.jenjang`, grouped by committee. Keep `kewenangan` as a denormalised snapshot of `catalog_item.nama` for historical readability.
- [ ] Make `RincianKewenangan.catalog_item` required for new rows via form/service validation (leave the column nullable for legacy rows; never infer an entitlement from free text).
- [ ] GREEN gate: `test_kredensial_bab.TerbitkanSPKTests` updated to assert real catalog codes; `test_clinical_access` still passes.

## Task K-A3 — Fix the peer-review → issuance handoff (P0)

**Depends on:** K-A2.

- [ ] Add RED tests: after a peer-review POST, each reviewed line carries a persisted verdict that `terbitkan_spk_lengkap` consumes; an SPK issued after a complete review creates exactly N snapshots; an SPK issued with zero reviewed lines is refused with a clear message; `TIDAK_DIBERIKAN` lines create no snapshot and still print.
- [ ] In `kredensial_panel_bestari`, persist `RincianKewenangan.rekomendasi` and `status_spk` in the same transaction as `PenilaianTindakan` (mapping MANDIRI→`DISETUJUI_MANDIRI`, SUPERVISI→`DISETUJUI_SUPERVISI`, DITOLAK→`TIDAK_DIBERIKAN`).
- [ ] In `terbitkan_spk_lengkap`, refuse issuance when any privilege line lacks a verdict, and log the refusal to `PeristiwaSDM`.
- [ ] GREEN gate: a full happy path from submission → PSV → review → decision → issuance creates snapshots for exactly the approved lines.

## Task K-A4 — White paper and qualification requirements (P0 for KPS evidence)

**Depends on:** K-A1.

- [ ] Add RED tests: a grade without a white paper renders `Belum dikonfigurasi`; a requirement with `min_kasus` and `min_logbook` is displayed on the catalog page; editing an approved white paper creates a new version instead of mutating the old one.
- [ ] Add `MasterWhitePaper` (profession, grade, version, `is_active`, `reviewed_by`, `reviewed_at`, `berlaku_mulai`) and `SyaratWhitePaper` (white paper, jenis syarat ∈ pendidikan/pelatihan/kasus/logbook/sertifikasi, deskripsi, nilai minimum, satuan, wajib).
- [ ] Render the requirements next to each catalog group in `kredensial_katalog`, and gate the self-assessment picker on satisfied requirements where the data exists.
- [ ] Seed **only** what the source document states; leave the rest empty with `Belum dikonfigurasi`. Do not invent thresholds.
- [ ] GREEN gate: white paper version immutability enforced in the model `save()`, mirroring `HasilFormasi` (`sdm/models/formasi.py:170`).

## Task K-A5 — Complete the Dokter / Apoteker catalog (P0, owner-supplied data)

**Depends on:** committee-approved source data. **This task cannot be completed from the document alone** — the document gives no per-grade breakdown for these four professions.

- [ ] Produce a reviewed worksheet (owner + Komite Medis + Komite Farmasi) listing, per grade, the actions and M/S/T status. Store it under `docs/kredensial/` and reference its hash in the seed command docstring.
- [ ] Extend `_data_katalog_rkk.py` with DOKTER_SP, DOKTER_UMUM, DOKTER_GIGI, APOTEKER, and add explicit `T` rows for actions that are structurally out of scope at a grade.
- [ ] Extend `seed_katalog_rkk` to remain idempotent and to report `tindakan_baru` per profession.
- [ ] GREEN gate: DB has non-zero catalog rows for all 23 professions; `T` rows exist; `test_kredensial_bab.SeedKatalogTests.test_seed_is_idempotent_across_two_runs` still passes.

## Task K-A6 — Public SPK/RKK verification (P1)

**Depends on:** K-A3.

- [ ] Add RED tests: the QR target resolves anonymously; an unknown token returns 404 with no data leak; a revoked SPK shows `Dicabut`; an expired SPK shows `Kedaluwarsa`; the page exposes only name, unit, profession, validity window, and privilege counts — never NIK, STR number, or health data.
- [ ] Add `VerifikasiSpk` (assignment OneToOne, `token` unique 64-hex, `payload_digest`, `created_at`) computed as SHA-256 over a canonical JSON of (nomor_spk, versi, employee id, unit code, validity window, approved privilege codes, issuer id, issued_at).
- [ ] Add a **public, unauthenticated** route `/human-capital/verifikasi-spk/<token>/` outside the `sdm` login wall, rate-limited, `noindex`, and never listing other records.
- [ ] Point the existing QR at that URL. Keep the current in-app link as a secondary "buka detail internal" button.
- [ ] GREEN gate: `reconcile_hc_credentials --verify-anonymous-denial` still passes for all private routes while the new verification route is intentionally public.

## Task K-A7 — Segregate duties across the three approval stages (P1)

**Depends on:** K-A3.

- [ ] Add RED tests: the submitter cannot peer-review their own request; the reviewer cannot issue the SPK; a user with only `can_review_hc_credentials` cannot issue; issuance requires an explicit director capability; a revoked grant mid-flow blocks the next stage.
- [ ] Introduce two capabilities in `HC_CAPABILITY_CHOICES`: `can_issue_hc_spk` (director) and `can_verify_hc_credentials_admin` (HRD/PSV). Keep `can_review_hc_credentials` for committee/peer review.
- [ ] Enforce stage order server-side: PSV verified → peer review complete → committee decision → director issuance. Each refusal writes `PeristiwaSDM` with the blocking reason.
- [ ] GREEN gate: existing `test_kredensial_bab` role fixtures updated; no route becomes reachable by a broader audience than before.

## Task K-A8 — Self-service portal without reviewer visibility (P1)

**Depends on:** K-A2.

- [ ] Add RED tests: an employee with no HC grant can open their own submission page, file one request, and cannot list any other employee's request; the reviewer list still requires the committee capability.
- [ ] Replace `_own_employee` (`sdm/portal_views.py:22`) dependency on `visible_employees` with an object-bound resolver keyed on `user.pegawai_hc`; reuse it in `kredensial_pengajuan_sendiri` and drop the `can_review_hc_credentials` requirement there.
- [ ] Add the logbook upload field to the self-assessment form (a `VersiDokumen` of type `LOGBOOK`, private storage, no public URL).
- [ ] GREEN gate: `test_staff_portal`, `test_kredensial_bab`, `test_akses` pass; an anonymous or unrelated user gets 403/404, never another employee's data.

## Task K-A9 — Export and print layer (P1)

**Depends on:** K-A1…K-A6.

One task per artefact, each with a RED test asserting (a) capability + unit scope, (b) `PeristiwaSDM` write, (c) content-type and filename, (d) no secret field in the payload.

- [ ] White paper PDF (per profession/grade, watermark, `Belum dikonfigurasi` sections explicit).
- [ ] Catalog PDF + Excel per committee and grade, three columns M/S/T.
- [ ] Employee SPK+RKK summary PDF (batch by unit, current active SPK only).
- [ ] Self-assessment form print (blank form with the employee's catalog subset).
- [ ] Logbook + SKP portfolio PDF.
- [ ] Document completeness checklist PDF (Folder B/C mapping).
- [ ] Submission tracking Excel (filters preserved).
- [ ] Peer-review berita acara PDF with reviewer signature blocks.
- [ ] Verified portfolio PDF (PSV + review, single file).
- [ ] Committee recommendation letter PDF (draft, unsigned, marked `DRAF`).
- [ ] Peer-review progress Excel per unit.
- [ ] RME access log PDF (landscape, auto-lock events, pending co-signature).
- [ ] Clinical directory PDF per unit with expiry colouring.

## Task K-A10 — RME enforcement rollout (P1 design, P2 activation)

**Depends on:** K-A3 (real catalog codes), clinical owner sign-off.

- [ ] Add RED tests: a MANDIRI code opens the form; a SUPERVISI code requires a countersignature before finalisation; a code absent from the snapshot is refused with the exact Indonesian message from the source document; a trainee without an active placement is refused.
- [ ] Wire `require_clinical_action` into the patient-module clinical writes (`pasien/views.py:393` CPPT, `:536` resep) behind a settings flag, default off.
- [ ] Replace `sdm/views.py:1067` `employees[:200]` with a paginated/autocompleted picker.
- [ ] GREEN gate: `test_clinical_access` plus a new `test_clinical_enforcement` pass with the flag on and off; `pasien` tests unchanged with the flag off.

## Task K-A11 — EWS scheduling and channel honesty (P1)

**Depends on:** nothing.

- [ ] Add RED tests: H-90/H-60/H-30 produce exactly one reminder per band per assignment; repeat runs create nothing; a revoked or superseded SPK archives its unread reminders; a completed re-credentialing closes the old reminders.
- [ ] Add the missing `LT_60` band to `sync_spk_reminders`.
- [ ] Add `RECRUITMENT`/`FORMASI` targets and archive-on-resolve semantics to `PengingatSDM`.
- [ ] Either schedule `hc_reminders` in the deployment (cron/worker) or mark WhatsApp/Email as `Belum diaktifkan` in the UI. Do not display a channel the system cannot deliver.
- [ ] GREEN gate: `hc_reminders --dry-run` is non-mutating; two consecutive real runs produce no duplicate keys.

## Task K-A12 — EP linkage data (P1, blocks any accreditation claim)

**Depends on:** owner-reviewed mapping.

- [ ] Add RED tests: an unmapped requirement renders `Belum dipetakan`; a mapping to an inactive framework is not displayed; changing the active framework does not silently re-point an existing mapping.
- [ ] Create `AturanDokumen` rows for the credentialing artefacts and `PemetaanStandarSDM` rows pointing at **codes that exist in the active framework**, with `reviewer_name` and `reviewed_at`.
- [ ] Add a management command that reports unmapped requirements and stale framework references.
- [ ] GREEN gate: `build_kps_pack` produces a non-empty `mapped_ep` for every mapped rule; the report lists every unmapped one explicitly.

---

## Delivery order

1. **K-A1 → K-A2 → K-A3** (one branch, three commits). Without these the module issues empty SPKs; nothing else is worth building first.
2. **K-A4, K-A5** (reference data). Can run in parallel with K-A6.
3. **K-A6, K-A7, K-A8** (verification, segregation, self-service).
4. **K-A9** (exports, one commit per artefact).
5. **K-A10** (enforcement, flag-gated, needs clinical sign-off).
6. **K-A11, K-A12** (operations and evidence).

## Acceptance

- An employee files a request with a logbook, HRD records PSV, the committee records per-line M/S/T, the director issues an SPK, and exactly the approved lines become `PrivilegeSnapshot` rows keyed by catalog code.
- Scanning the SPK QR code on a phone, logged out, shows validity, unit, and privilege counts — and no personal identifiers.
- Every one of the 13 export artefacts downloads with the correct scope and writes an audit event.
- `python manage.py test sdm` is green; `makemigrations --check` clean; `python manage.py check` clean.
- Every EP shown in the UI resolves from the active framework, and every unresolvable reference reads `Belum dipetakan`.
