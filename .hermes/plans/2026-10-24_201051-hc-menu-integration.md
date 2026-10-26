# Human Capital Menu Integration and Workflow Acceptance Plan

> **For agentic workers:** Read `2026-10-24_201051-hc-additions-roadmap.md` and the staff-intake companion first. Execute only after approval using `executing-plans` or `subagent-driven-development`. Every code increment is RED → minimal implementation → GREEN → review; commit only green checkpoints if authorized.

**Goal:** Make the ten Human Capital groups requested in the menu document visible, understandable, permission-correct, and connected to accepted operational workflows without losing existing features.

**Architecture:** Finish the existing `sdm/navigation.py` registry and render it through the context processor, shared navigation partial, and dashboard. Reuse real guarded route names; create only missing workflow UI around the existing models/services, with explicit disabled reasons for unreleased functionality. Own-profile access is a distinct object-bound path, and analytics/reports must use consistent current scope, period, and approved source data.

**Source:** `C:/Users/cubeb/Downloads/struktur menu ideal Human capital.docx`, SHA-256 `ef7651202ed97bb39ecfcbb0a799294c5ada0e101a4fe4cecf7d613ac3afda0d`. The source's final tree is the ordering authority. The earlier `docs/superpowers/plans/2026-10-24-human-capital-menu-workflows.md` retains domain contracts; its claims that these model files are NEW and that a 425-person census exists are not the current baseline.

## Current context and constraints

- `sdm/navigation.py` already defines `NavItem`, `NavGroup`, and `navigation_tree`, but most items have no route, `_url` is unused, and no runtime template/context processor consumes the tree.
- `templates/sdm/_navigasi.html` remains a row of buttons. `sdm/services/dashboard.py` still builds five level cards, `templates/sdm/dashboard.html` displays them, and `sdm/views.py:_hc_navigation` is a separate two-link list.
- `granted_capabilities` excludes null-unit hospital grants, despite the actual scope resolver supporting them. This must be fixed without giving unitless users implicit hospital scope.
- `portal_index` exists but its own-employee resolver relies on HR directory grants. Own-profile staff do not need broad `can_view_hc` access.
- Current K3 list/write routes require `hc_health_write`, not `hc_health_read`; do not advertise them as a read-only destination without adding a guarded read-only surface.
- Advanced models/services exist for shifts, trainee placement, clinical privileges, jobdesc, and OPPE/FPPE; UI and service presence do not prove acceptance. Local schema has not applied source migration `0025`.
- Keep all existing recruitment, orientation, training, talent/scenario, and report destinations. Do not remove functionality to fit the new grouping.
- Do not modify the Integrated Control shell, clinical patient writes, catalogue data, workforce census, or grants as navigation cleanup. Clinical access enforcement has its own accepted rollout gate.
- User-facing copy stays Indonesian; no numbered KPS compliance claim is published solely from the menu document. Confirm reviewed mappings to the actual active framework.

## Target navigation and complete source coverage

The manager view uses this order. Every group has a concise description, real permission-filtered links, and an explicit unavailable status for undelivered subfeatures. Regular staff see only the authorized own-profile subset.

| Order / group | Delivered routes to reuse now | Work still required / owner |
|---|---|---|
| 1. Dasbor & Analitik | `sdm:dashboard`, `sdm:analitik_dashboard` | EWS STR/SIP/SPK/contracts at 7/30/90 days; true professional/employment distribution; honest cohort/period metrics — M4 |
| 2. Perencanaan & Formasi Staf | `sdm:formasi_list`, `sdm:formasi_create`, `sdm:rekrutmen_list` | Workload master, accepted WISN, selected-unit/profession/period gap and recruitment link — M6a |
| 3. Database & e-File Kepegawaian | `sdm:pegawai_list`, `sdm:pegawai_create` | Complete intake/profile/legal/education/import — staff plan; trainee directory and supervised placement — M6b |
| 4. Presensi & Operasional Shift | No accepted UI routes in baseline | Roster, attendance/manual review, effective hours, optional remuneration export — M6f; initially unavailable |
| 5. Kredensialing & Kewenangan Klinis | `sdm:kredensial_list`, `sdm:kredensial_create`, existing detail/PSV/decision/SPK-print routes | Staff submission, committee/profession scope, actual RKK/SPK issuance/recredentialing — M6b |
| 6. Evaluasi Kinerja & Orientasi | `sdm:orientasi_list`, `sdm:kinerja_list`, `sdm:diklat_list` | Complete appraisal UI, annual learning, OPPE/FPPE cases — M4/M6c |
| 7. Uraian Tugas & Akses RME | No accepted UI routes in baseline | Existing jobdesc models → versions/acknowledgment UI; privilege-policy read view; separately approved clinical enforcement — M6d |
| 8. Kesehatan & Keselamatan Staf | `sdm:k3_list` for write-granted clinicians; existing MCU/immunization/incident forms | Read-only authorized clinician journey, personal due/fitness status, health-private review/follow-up — M6e |
| 9. Layanan Mandiri Pegawai | `sdm:portal_index`, `sdm:portal_request_create` | Own-only access, own files, notifications and review queue; optional leave approval — M3/M6f |
| 10. Laporan & Ekspor Akreditasi | `sdm:analitik_export`, `sdm:analitik_export_pdf`, `sdm:kps_report` | Staff-sample KPS pack, STR/SIP validity and annual-hours reports, scoped reviewed redaction/publication — M5 |

Trainees stay within group three, not an eleventh top-level menu. Remuneration is an optional **export bridge**, not payroll calculation. Digital SPK may be validated with an approved audit/hash mechanism, but must not be labeled a certified electronic signature without an actual signing provider.

## UI specification

- Retain ARIMA navy/indigo, light cards, Inter body and Manrope headings. Do not copy Integrated Control's large decorative masthead into every HR form.
- A compact HC header shows product name, readable active scope, and two primary actions: `Tambah staf` / `Impor Excel` only when allowed and delivered.
- Desktop dashboard groups are two columns with consistent 20–24px padding, 16px gaps, 18px headings, 14px descriptions, and >=44px clickable targets. At <=767px use one column.
- Shared navigation uses native `<details>/<summary>` for each functional group or an equally accessible Bootstrap disclosure. Every active leaf has exactly one `aria-current="page"`; unavailable items are text, not `href="#"` or a disabled-looking real link.
- Body/fields 16px, labels/explanations >=14px, compact metadata >=13px; no fixed-height text cards or ellipsis on essential route/group names.
- Present operational status, expiry band, configuration availability, and source coverage separately. Empty employee data is not “100% compliance”; unavailable configuration reads `Belum dikonfigurasi`, insufficient source reads `Belum dapat dihitung`, and unreleased workflow reads `Belum diaktifkan`.
- Scope labels distinguish all granted units, a selected unit, and an own-only employee view. Missing unit assignment is not a hospital grant.

## File inventory

Modify:
- `sdm/navigation.py`, `sdm/context_processors.py`, `sdm/akses.py`, `sdm/portal_views.py`, relevant dashboard/report handlers in `sdm/views.py`.
- `sdm/services/dashboard.py`, `metric_scope.py`, `legalitas.py`, `kepatuhan.py`, `analitik.py`, `publikasi_bukti.py`, relevant reminders and signals.
- `templates/sdm/_navigasi.html`, `_responsive.html`, `dashboard.html`, existing portal/report templates.
- Existing suites `sdm/tests/test_navigation.py`, `test_dashboard.py`, `test_staff_portal.py`, `test_akses.py`, `test_analitik.py`, `test_ekspor.py`, `test_legalitas.py`, `test_dokumen.py`, and `accounts/tests_sidebar_visibility.py` where assertions actually reference changed affordances.

Create during implementation:
- `sdm/tests/test_navigation_render.py`, `sdm/tests/test_metric_filter_parity.py`, `sdm/tests/test_kps_pack_scope.py`, `sdm/tests/test_staff_self_access.py`.
- `templates/sdm/_menu_groups.html`, `static/css/hc-workspace.css`, `docs/qa/hc-menu-workflow-verification.md`.

M6 lists separate owner-specific files for advanced acceptance increments. Register new URLs in `sdm/urls.py`, export new models through `sdm/models/__init__.py`, and generate migrations against the real graph only when a task actually requires them. No duplicate registry, workforce model, or generic privilege engine.

## M0 — Baseline and affordance inventory

- [ ] Record `git status --short`, branch/commit, current interpreter version, model/migration graph, and source hashes from the roadmap. Protect the current uncommitted control and unrelated work.
- [ ] Read all tests that name `level_cards`, `_level_cards`, `_hc_navigation`, `nav_items`, `nav_pegawai`, and `nav_k3` before changing them. Search source and tests with `search_files`; record the exact assertions to update. Do not delete a behavior while leaving its tests/consumers to fail only at the final gate.
- [ ] During execution run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_navigation sdm.tests.test_dashboard sdm.tests.test_staff_portal sdm.tests.test_akses sdm.tests.test_level_routes sdm.tests.test_level_actions accounts.tests_sidebar_visibility akreditasi.tests_kontrol_dasbor --verbosity 1
```

Expected: record real baseline and any unrelated failures. No assumed test count and no claim that SQLite tests prove production readiness.

## M1 — Correct grant discovery and complete the existing registry

**Modify:** `sdm/context_processors.py`, `sdm/navigation.py`; extend `sdm/tests/test_navigation.py`, add render suite in M2.

- [ ] Add this RED test inside existing `NavigationTests`:

```python
    def test_hospital_grants_are_discoverable_without_unit_grant(self):
        from sdm.context_processors import granted_capabilities
        HcGrant.objects.filter(user=self.manager).delete()
        HcGrant.objects.create(
            user=self.manager, capability='can_view_hc', unit_kerja=None,
        )
        self.assertIn('can_view_hc', granted_capabilities(self.manager))
```

Run:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_navigation.NavigationTests.test_hospital_grants_are_discoverable_without_unit_grant --verbosity 2
```

Expected RED: the capability is missing because the current query requires nonnull units. These deletes are test-fixture operations only, not operational grant changes.

- [ ] Replace the current grant-query restriction with an OR scope predicate:

```python
grants = HcGrant.objects.filter(
    user_id=user.pk,
    is_active=True,
    valid_from__lte=today,
).filter(
    Q(unit_kerja__isnull=True) | Q(unit_kerja__is_active=True),
).filter(
    Q(valid_until__isnull=True) | Q(valid_until__gte=today),
).values_list('capability', flat=True)
```

Keep existing inactive-user, date, and role-config permission checks. A profile with no unit and no explicit grant still gets nothing.

- [ ] Add RED registry tests: real `href` for every enabled item, inactive/expired/revoked grants, foreign selected unit, hospital-scope grant, missing profile, unauthorized manager subgroups, independent orientation/training/recruitment capability, and no fake `#`/silently broken reverse.
- [ ] Extend `NavItem` with `href: str | None`, `active: bool=False`, and a clear availability state/reason. Add `active: bool=False` to `NavGroup`. Extend `navigation_tree` with `current_url_name=None` while preserving its existing unit/employee keyword API. Resolve each enabled route once through `_url`; a configured-but-missing route in a delivered item must fail a test and be disabled with an explicit reason, not silently treated as delivered.
- [ ] Use one item per destination/capability, rather than multi-feature labels pointing to one partial page. Concrete initial mapping:

| Leaf | Route | Capability |
|---|---|---|
| Summary | `dashboard` | `can_view_hc` |
| Analytics/talent/scenarios | `analitik_dashboard` | `can_view_hc_analytics` |
| Staffing plans | `formasi_list` | `can_plan_hc_workforce` |
| Recruitment | `rekrutmen_list` | `can_manage_hc_recruitment` |
| Directory/profiles/legal history | `pegawai_list` | `can_view_hc` |
| Add staff | `pegawai_create` | `can_manage_hc_employees` plus destination prerequisites |
| Excel import | `pegawai_import` after staff plan S5 | `can_manage_hc_employees` plus destination prerequisites |
| Credential desk | `kredensial_list` | `can_review_hc_credentials` |
| Orientation | `orientasi_list` | `can_manage_hc_orientation` |
| Appraisal | `kinerja_list` | `can_manage_hc_appraisals` |
| Learning/TNA | `diklat_list` | `can_manage_hc_training` |
| K3 clinical write desk | `k3_list` | `hc_health_write` only |
| Own profile | `portal_index` after M3 | exact active account/employee ownership, not HR grant |
| Own requests | `portal_request_create` after M3 | same own-only boundary |
| Aggregate XLSX/PDF | `analitik_export`, `analitik_export_pdf` | `can_export_hc` |
| KPS sample pack | `kps_report` after M5 | `can_export_hc` and object scope |

Use the actual destination's combined prerequisites where required. Document export routes are download links, not a stand-in UI for every report feature.

- [ ] Authorized managers see text-only subitems for unreleased presence, trainee UI, jobdesc, clinical enforcement, OPPE/FPPE, and unaccepted WISN. Bind availability to explicit server release settings such as `HC_RELEASED_WORKFLOWS`, defaulting to existing accepted route groups; route existence alone does not mean accepted delivery. Unauthorized users do not see planning placeholders for capabilities they lack.
- [ ] Change `_authorized` so an unavailable item can still be disclosed to an authorized manager as text; do not return false solely because `disabled_reason` is set. Keep denied scope/capabilities hidden. Ensure a group marked unavailable cannot emit working-looking child anchors.
- [ ] GREEN: rerun `sdm.tests.test_navigation` and `sdm.tests.test_akses`. Expect `OK`; registry item authorization matches destination tests, not merely group count.

## M2 — Render one ten-group navigation and retire duplicated UI

- [ ] Add a new `NavigationRenderTests` using the same real profile/config/grant setup as `NavigationTests`. Test rendered dashboard and a non-dashboard HC page, not only the registry function. Required RED checks: `hc_menu_groups` context, matching group identifiers, delivered links reverse, unavailable leaves lack anchors, exactly one active leaf, and no `Level 1`–`Level 5` maturity UI.
- [ ] Add `hc_menu_groups` in `hc_navigation(request)` using the existing request-local cache. Pass current resolved route name from `request.resolver_match.view_name`, selected unit only after scope resolution, and the exact own employee where available. Preserve legacy `nav_*` flags temporarily as values derived from the tree for consumers that still use them; remove the old independent query logic when the last consumer is updated.
- [ ] The structural leaf contract consumed by templates is:

```python
{
    'key': 'database_tambah_staf',
    'label': 'Tambah staf',
    'href': '/human-capital/pegawai/baru/',
    'active': False,
    'disabled_reason': '',
}
```

This is an interface example, not a hardcoded href to store. Generate the href using the registered named route. Dataclass attributes may supply the same template contract; do not convert back and forth into a second registry.

- [ ] Create `templates/sdm/_menu_groups.html` with this full loop, using group/item attributes already defined by M1:

```django
<div class="hc-menu-groups">
  {% for group in hc_menu_groups %}
  <details class="hc-menu-group" data-hc-group="{{ group.key }}" {% if group.active %}open{% endif %}>
    <summary><i class="bi {{ group.icon }}" aria-hidden="true"></i> {{ group.label }}</summary>
    <ul class="hc-menu-items">
      {% for item in group.items %}
      <li>
        {% if item.href and not item.disabled_reason and not group.disabled_reason %}
        <a href="{{ item.href }}" {% if item.active %}aria-current="page"{% endif %}>{{ item.label }}</a>
        {% else %}
        <span class="hc-menu-unavailable">{{ item.label }} <small>{{ item.disabled_reason|default:group.disabled_reason }}</small></span>
        {% endif %}
      </li>
      {% endfor %}
    </ul>
  </details>
  {% empty %}
  <p class="text-muted">Belum ada menu Human Capital yang dapat diakses.</p>
  {% endfor %}
</div>
```

- [ ] Replace `_navigasi.html` button-row body with a single named nav wrapping the shared partial. In `dashboard.html`, remove the old level-card loop and duplicated bottom `Menu` list, and render the registry once near the existing filters/KPI area. Do not include both old and new menus or render the same active leaf twice.
- [ ] Remove `_level_cards` from `sdm/services/dashboard.py` and its `level_cards` return entry, `_hc_navigation` from `sdm/views.py`, and its `nav_items` context only after all consumers/tests found by M0 have replacements. Preserve metric calculations in this presentation task.
- [ ] Add `static/css/hc-workspace.css`, referenced through `{% static %}` by `templates/sdm/_responsive.html` while retaining that partial's current tablet topbar rules. Style `.hc-menu-groups` as two columns/one mobile column, disclosure summary and links >=44px, headings 18px, item/body 16px, metadata 13px, 16px gaps, visible focus. Rules must be HC-scoped and must not alter the globally expanded desktop sidebar or mobile offcanvas.
- [ ] Add primary staff/import actions to HC dashboard only when delivered and authorized. `can_manage_hc_employees` alone does not imply upload, export, committee, or health authority.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_navigation sdm.tests.test_navigation_render sdm.tests.test_dashboard sdm.tests.test_level_routes sdm.tests.test_level_actions accounts.tests_sidebar_visibility akreditasi.tests_kontrol_dasbor --verbosity 1
```

Expected: `OK`; all previously delivered destinations remain accessible, control hub remains no-sidebar, no duplicate navigation or broken route reverse. Conditional green commit message: `feat(hc): connect permission-aware functional navigation`.

## M3 — Own-profile staff portal without directory grants

**Coordinate serially with staff plan S6.** No new general `can_view_hc` grant is created during activation.

- [ ] In new `sdm/tests/test_staff_self_access.py`, create an active account linked to one employee and placement but no `HcGrant`. Pin: own portal 200; another employee detail remains 403/404; directory remains 403; own notification list cannot include coworkers; role/unit/verification fields rejected on self-service POST.
- [ ] Add `own_employee(user)` in `sdm/akses.py`, returning the linked `Pegawai` for an authenticated active account or raising `PermissionDenied`. It must query `Pegawai.objects.get(akun_id=user.pk)` directly and never pass through today's directory-grant resolver. Return only the owner, not a queryset of the unit's staff.
- [ ] Update `_own_employee` in `sdm/portal_views.py` to consume that boundary, or replace all its callers with the shared function. Update the own-request service and document access checks with the same explicit ownership; do not bypass health restrictions or allow self-verification.
- [ ] Render own personal data, permits, SPK/RKK downloads, private document status, learning history, and notifications with explicit own-file download/upload endpoints. Staff may submit contact/document corrections for review; employment, account roles, placement, verified status, and committee decisions remain operator-only.
- [ ] A selected `employee_id`/unit query parameter cannot change the owner. With no employee link show a clear unavailable/pending-link message; do not fall back to all employees. Technical admins without a staff link can still use their separately granted manager views, not a fabricated staff profile.
- [ ] Do not call global report/audit functions from the personal portal. General HR/clinical health records remain separate. Own medical visibility requires explicit hospital policy and is not implied by personnel ownership.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_staff_self_access sdm.tests.test_staff_portal sdm.tests.test_layanan_mandiri sdm.tests.test_private_documents sdm.tests.test_akses accounts.tests_staff_activation --verbosity 2
```

Expected: `OK`; no new grant rows created as a side effect. Conditional green commit: `fix(hc): separate own staff access from HR directory scope`.

## M4 — Truthful EWS and filter/period-consistent analytics

**Files:** dashboard, metric-scope, analytics, legal-status and reminder services; existing tests plus `sdm/tests/test_metric_filter_parity.py`.

- [ ] RED fixtures must deliberately contradict each other: two professions with opposite compliance, active/inactive employees, two units with different beds/admissions, a past transfer, DEMO versus reviewed staff, annual training in different years, and more than 200 employees with a failing final record.
- [ ] Make compliance population use the same `unit`, `profesi`, `status`, and provenance policy as the visible dashboard cohort. No silent cap; use batching/prefetch/aggregations rather than hiding records to meet performance budgets. Keep percent of fully compliant employees separate from percent of satisfied document requirements.
- [ ] Correct historical population resolution so authorization scope comes from grants and employee placements as of the requested date; do not start by excluding everyone who moved out today. Decide and test whether report scope is exact unit or authorized descendants; match the UI label.
- [ ] Use `legal_status` for typed STR/SIP/SPK and employment contract EWS. Bands: expired, 0–7, 8–30, 31–90, valid, unknown. Today's expiry stays valid through the defined local end date; missing expiry is unknown unless the **individual permit** explicitly has approved lifetime validity. Avoid duplicate reminders as records move bands or are superseded/revoked.
- [ ] Fix document compliance before enabling claims: `_latest_version` currently sorts versions across document objects and can select a superseded/newer-numbered file from the wrong permit/site. Bind exact artifact/permit/practice site and current accepted revision. An expiring-but-unexpired verified document remains valid with an urgency flag; it is not automatically invalid merely because the current `RequirementResult.is_satisfied` recognizes only `VALID`.
- [ ] Add boundary cases 7/8/30/31/90/91 days, two SIP practice sites, lifetime STR with dated SIP, replacement version, rejected/superseded file, one STR presented as SIP, and no requirement configuration. General HR reminders must not contain health diagnoses or file URLs.
- [ ] Use dated `RiwayatKepegawaian` for turnover over the requested period, with documented average-headcount calculation and provenance; otherwise return unavailable. Fix BOR to actual authorized unit-room mapping and same-period effective bed capacity; if source coverage is absent, return unavailable instead of hospital totals. Require exact or explicitly reviewed compatible staffing/bed periods.
- [ ] Annual learning reports count accepted nonduplicated clock minutes in the selected year. Keep clock hours, JP, and SKP separate; completion of one course is not fulfillment of the requested twenty-hour target. Eligibility/proration policy must be approved and included in report metadata.
- [ ] Update cache keys/invalidation for all filter/period/grant-validity/rule/source-revision inputs; do not cache signed URLs or private profile objects. Run revocation/expiry checks even when a cache entry exists.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_metric_filter_parity sdm.tests.test_dashboard sdm.tests.test_analitik sdm.tests.test_legalitas sdm.tests.test_dokumen sdm.tests.test_ekspor --verbosity 2
```

Expected: `OK`; changing one scope/year changes only its matching result, null coverage is unavailable, no demo-account census is presented as real clinical staffing. Record actual query counts rather than inventing a target or loosening old budgets.

## M5 — Staff-sample reports and protected accreditation output

**Files:** `sdm/services/publikasi_bukti.py`, `sdm/services/analitik.py`, report views/templates; new `sdm/tests/test_kps_pack_scope.py`.

- [ ] RED cases: export-granted actor selects foreign employee UUID, mixed visible/foreign selection, inactive/archived or wrong framework, mapping to a standard in a different framework, missing review, private key in export, formula-leading spreadsheet name, and replayed/tampered publication artifact.
- [ ] Fix `build_kps_pack`: it currently checks a general export capability and then uses `Pegawai.objects.filter(pk__in=employee_ids)` without employee scope. Resolve requested UUIDs through `visible_employees(actor, capability='can_export_hc')` and recheck every selected employee. Reject the whole unauthorized selection without disclosing names; do not silently drop foreign staff and report success.
- [ ] Use the canonical active-framework resolver and verify each active reviewed mapping's `standard_item.framework_id == mapping.framework_id`. Keep unreviewed source-document KPS numbering out of accepted output. A missing mapping/configuration is explicit, never an invented “STARKES ready” badge.
- [ ] Separate exports: sampled file-compliance/status pack; local-practice STR/SIP inventory; annual training hours; approved unit staffing gap. Every report includes scope, as-of/period, denominator, source coverage, and method/version; escape spreadsheet formula-leading user strings.
- [ ] Treat public publication as a separate reviewed workflow: an ordinary export permission does not imply `can_verify_kps`. The current `require_hc_capability(actor, 'can_verify_kps')` cannot succeed because that code is not in `HcGrant.CAPABILITY_CHOICES`. Use the existing accreditation verification permission through the profile permission API **plus** HC export/object scope and immutable reviewed artifact identity; do not bypass approval or add a broad HC grant accidentally.
- [ ] Review/publish a server-generated artifact ID and digest, not untrusted posted workbook bytes/metadata. Publish only the approved sanitized derivative, never original private attachments, personal identifiers, diagnoses, signed URLs, or storage keys. Record source/version references in private audit only.
- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_kps_pack_scope sdm.tests.test_ekspor sdm.tests.test_dokumen sdm.tests.test_akses --verbosity 2
```

Expected: `OK`; cross-unit exports denied and public derivatives contain no private key/URL/raw identity fields. Enable report menu destinations only after their own tests pass.

## M6 — Advanced workflow gates retained from the source

These are separate implementation increments, not optional omissions from overall source coverage. They may remain disabled in the initial core release. Before an advanced increment begins, inspect its existing models/services and write the specified failing journey tests; extend current objects, never rerun the old model-creation tasks. Each checkbox below is a small preparation/test/implementation/review step; the complete capability normally spans several such increments.

### M6a: Workload/FTE/WISN and formation/recruitment

Owner files: `sdm/models/beban_kerja.py`, `sdm/services/wisn.py`, `sdm/services/formasi.py`, `sdm/forms/formasi.py`, `sdm/views.py`, `sdm/urls.py`, `templates/sdm/formasi/`, existing `sdm/tests/test_wisn.py`, `test_formasi.py`, `test_rekrutmen.py`.

- [ ] Pin period/unit/profession selection, real employment capacity, approved workload-source coverage, missing data, decimal boundaries, and plan-to-recruitment linkage in failing tests.
- [ ] Expose workload entry/review, activity FTE output and staffing gap via existing formasi pages. Draft/review/approval preserve immutable input/result version and source coverage.
- [ ] Review the current WISN formula against an approved hospital worksheet before enabling it. The present `weeks = days_per_week / 7` followed by another period division and multiplication of allowance factors is not validated merely by the function name. Keep WISN visibly unavailable until reference-value tests and policy review pass.
- [ ] GREEN command: run `sdm.tests.test_formasi sdm.tests.test_wisn sdm.tests.test_rekrutmen`. Expected `OK` with independent worksheet fixtures and no duplication of recruitment records.

### M6b: Credential committees, SPK/RKK, and supervised trainees

Owner files: `sdm/models/clinical_access.py`, `sdm/models/kredensial.py`, `sdm/services/clinical_access.py`, `sdm/services/rekrutmen.py`, `sdm/forms/level2_5.py`, credential handlers/URLs, `templates/sdm/kredensial/`; tests `sdm/tests/test_clinical_access.py`, `test_rekrutmen.py`, new `sdm/tests/test_credential_journeys.py`.

- [ ] RED self-submission versus committee/issuer tests: no self-approval, profession/case/unit scope, PSV required, expired/revoked grants, immutable approved RKK, repeat issuance, supervisor qualification/expiry, trainee end dates and actions.
- [ ] Complete staff application, committee queue, decision → controlled action snapshot → numbered SPK/RKK download, recredentialing/revocation and scoped trainee list/edit. Trainees remain a category under Database/e-File and cannot inflate independent qualified staffing.
- [ ] Correct effective privilege/revocation semantics and require a real current qualified supervisor/countersignature record. A truthy `encounter.diajukan_oleh` is not proof of countersignature. Revoke authority immediately under a documented date/time boundary; do not leave same-day revoked actions valid accidentally.
- [ ] GREEN command: run `sdm.tests.test_clinical_access sdm.tests.test_rekrutmen sdm.tests.test_credential_journeys`. Expected `OK`; label authentication/print validation accurately, not certified e-signature.

### M6c: Orientation, appraisal, OPPE/FPPE, and learning

Owner files: `sdm/models/evaluasi_klinis.py`, `sdm/models/kinerja.py`, `sdm/services/kinerja.py`, `sdm/services/diklat.py`, `sdm/views.py`, `sdm/urls.py`, `templates/sdm/kinerja/`, `templates/sdm/diklat/`; tests `sdm/tests/test_kinerja.py`, new `sdm/tests/test_oppe_fppe_journeys.py`, `sdm/tests/test_annual_training.py`.

- [ ] RED create/edit/assess/finalize/acknowledge cases plus OPPE period, FPPE restricted trigger/review/follow-up, annual hours and duplicate attendance.
- [ ] Build missing operator forms around existing objects; make OPPE/FPPE visibly distinct from a generic appraisal. Finalized results and committee recommendations are immutable reviewed records, not automated sanctions.
- [ ] GREEN command: run `sdm.tests.test_kinerja sdm.tests.test_oppe_fppe_journeys sdm.tests.test_annual_training sdm.tests.test_level_actions`. Expected `OK`, source period and units explicit, protected clinical narrative not leaked into general HR.

### M6d: Versioned job descriptions and separately approved RME enforcement

Owner files: existing `sdm/models/uraian_tugas.py`, `sdm/services/clinical_access.py`; create `sdm/jobdesc_views.py`, `templates/sdm/uraian_tugas/{list,detail,form}.html`; extend `sdm/urls.py`, `sdm/tests/test_uraian_tugas.py`; separate proposed clinical suite `pasien/tests_clinical_privileges.py`.

- [ ] RED jobdesc version/position/unit/profession applicability, approval, exact revision acknowledgment, revision renewal, and foreign-object access.
- [ ] Build the scoped master/list/detail/acknowledgment views around existing models and publish real navigation routes only after tests pass. Show read-only policy status where RME enforcement is not enabled.
- [ ] Before adding runtime clinical guards, enumerate actual patient write/signing routes and approved encounter-to-unit resolution, preserve existing module/object authorization, and rehearse a report-only coverage audit. Do not assume the current encounter object exposes `.unit_kerja` or add a clinical guard as menu cleanup.
- [ ] Enable per-action enforcement only after clinical-owner approval, effective privilege/supervision tests and a separately reviewed emergency policy. General admin access is not clinical signing authority.
- [ ] GREEN commands: run `sdm.tests.test_uraian_tugas sdm.tests.test_clinical_access`; if enforcement is approved, also `pasien.tests_clinical_privileges` and existing patient-route suites. Expected `OK`, legitimate read paths and historical records preserved.

### M6e: Staff occupational health and safety

Owner files: `sdm/models/k3.py`, `sdm/services/k3.py`, `sdm/forms/k3.py`, current K3 handlers/URLs/templates; extend `sdm/tests/test_k3.py`, create `sdm/tests/test_k3_journeys.py`.

- [ ] RED read-only health clinician, write clinician, ordinary HR denial, exposure report/follow-up/closure, individual status, and expired break-glass cases.
- [ ] Add a protected read-only K3 surface for `hc_health_read`; do not advertise the current write-only desk to a read-only clinician. Complete existing MCU, immunization, incident, and follow-up forms without duplicate health tables.
- [ ] General HR dashboard may show approved due/fitness state and aggregate coverage, not diagnosis/test/exposure details. Keep attachment reads/exports protected and audited independently of staffing roles.
- [ ] GREEN command: run `sdm.tests.test_k3 sdm.tests.test_k3_journeys sdm.tests.test_private_documents sdm.tests.test_akses`. Expected `OK`; no ordinary admin health access added.

### M6f: Shifts, presence, personal requests, and optional remuneration bridge

Owner files: existing `sdm/models/presensi.py`, `sdm/services/presensi.py`, `sdm/models/layanan_mandiri.py`, `sdm/services/layanan_mandiri.py`, `sdm/portal_views.py`; create `sdm/presensi_views.py`, `templates/sdm/presensi/{jadwal,presensi,koreksi}.html`, `sdm/tests/test_presensi.py`, `sdm/tests/test_leave_journeys.py`; capability wiring in `accounts/models.py`, `sdm/models/akses.py`, and grant administration only if explicitly approved.

- [ ] RED own versus foreign shift assignment, duplicate events/idempotency, cross-actor key replay, overnight shift, timezones, overlapping schedules, declined/inaccurate location, correction approval and effective minutes.
- [ ] Rehearse source migration `0025` and subsequent changes in disposable PostgreSQL; do not enable this menu group while its schema is absent. Add explicit scoped operational capabilities rather than using `can_view_hc` as permission to record any colleague's attendance.
- [ ] Complete roster publish/assign, staff check-in/out, supervisor correction queue and approved hours. Recheck assignment ownership, event sequence, current published shift and time window. Geofencing is optional event-time evidence with accuracy/manual review, not continuous tracking or fraud-proof verification.
- [ ] Personal leave/training/correction requests need actual scoped review/approve/reject/cancel flows, idempotency and conflict handling; a submitted JSON row alone is not a leave system. No automatic pay calculation; optional approved-hours/KPI export remains a bridge.
- [ ] GREEN command: run `sdm.tests.test_presensi sdm.tests.test_leave_journeys sdm.tests.test_layanan_mandiri sdm.tests.test_staff_self_access`. Expected `OK`, approved minutes do not double-count duplicate events or unresolved manual-review records.

## M7 — Browser, assets, and release evidence

- [ ] Run the core regression suite after M1–M5:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test sdm.tests.test_navigation sdm.tests.test_navigation_render sdm.tests.test_staff_self_access sdm.tests.test_staff_portal sdm.tests.test_dashboard sdm.tests.test_metric_filter_parity sdm.tests.test_kps_pack_scope sdm.tests.test_analitik sdm.tests.test_ekspor sdm.tests.test_akses accounts.tests_sidebar_visibility akreditasi.tests_kontrol_dasbor --verbosity 1
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django check
git diff --check
```

Expected: `OK`, no system-check errors, whitespace exit code 0. Add only the M6 suites whose workflows were actually implemented; never mark unimplemented groups done because the core suite passed.

- [ ] Use `django-layout-verification` and the actual synthetic-role browser fixtures. Required roles: hospital-granted manager, unit head, employee without HR grants, assessor, committee actor, health read/write clinician, technical superuser without health grant, expired/revoked grant, inactive account.
- [ ] Test 1440×900, 1366×768, 768×1024, and 360×800. Verify keyboard disclosures, one active leaf, complete long labels, minimum text/control sizes, no page overflow, default expanded desktop sidebar unchanged, and working mobile offcanvas. Screenshot dashboard, expanded groups, own portal, and one accepted operational destination.
- [ ] Test actual links and direct URLs: unauthorized access stays denied even when the menu is hidden; accepted leaves return the expected page/file; unavailable leaves have no anchor. A screenshot of ten group headings is not proof of ten operational modules.
- [ ] Collect static assets using production storage with DB overridden before setup, validate manifest entries and generated CSS/font references, rerender with collected assets. Do not overwrite or stage unrelated generated control assets from the other workstream.
- [ ] Write `docs/qa/hc-menu-workflow-verification.md`: fresh test commands/results, route coverage, role/scope matrix, browser metrics/screenshots, source/schema/data evidence, migration/staging status, released groups and explicit remaining advanced gates. No production-deployed claim without exact environment readback.
- [ ] If commits are authorized, stage explicit reviewed files per green checkpoint and verify staged diff. No broad add, no unrelated code cleanup, no push/deploy.

## Risks and open decisions

- Ten groups do not mean every feature is enabled. Keep per-workflow acceptance and honest unavailable states; otherwise this change creates a convincing but misleading shell.
- The working tree contains parallel control and template work. Read before editing, serialize shared-file changes, and never restore stale baselines from old plans.
- Domain approvals remain necessary for WISN worksheet, training policy, clinical action/supervision, privacy/retention, and presence/leave processes. Preserve clear default-disabled boundaries until those decisions exist.
- Numbered KPS references in the source are requirements context, not verified current instrument mappings. Existing active catalogue ownership remains separate.
- The current local database has no staff/grants/rules, so a blank operational screen may correctly reflect setup state. Do not seed fictitious “real staff” to make a dashboard look complete.
- This plan does not infer HC behavior from the supplied Integrated Control screenshot or commit/deploy the earlier UI changes.

## Definition of done

All requested groups have one permission-correct source of navigation, existing routes remain reachable, core staff/import/own-portal flows are working, and metric/report claims match tested scope and source coverage. Advanced features are independently tested and enabled or explicitly recorded as not yet released; they are never silently counted as complete. Evidence distinguishes implemented code, applied schema, installed personnel/rules, browser verification, and deployment.
