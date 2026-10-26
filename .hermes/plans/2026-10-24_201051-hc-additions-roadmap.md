# Human Capital User Additions — Reconciled Delivery Plan

> **For agentic workers:** Read this baseline before either companion plan. Use `executing-plans` or `subagent-driven-development` only after the user approves execution. This planning task changes plan documents only; it authorizes no implementation, import, grants, migration, email, commit, push, or deployment.

**Goal:** Deliver the staff-input and ideal Human Capital menu requirements from the supplied documents by completing and connecting the existing implementation rather than rebuilding it.

**Architecture:** Preserve `sdm.Pegawai`, its UUID identity, effective-dated placements, typed documents, private storage, existing services, and the `sdm` route namespace. Complete staff onboarding as a working vertical slice, then connect the existing navigation registry to real routes and unify its authorization with the UI and destination guards. Advanced clinical and workforce features remain explicit gated deliverables rather than apparently working links to incomplete code.

**Stack:** Existing Django/templates/Bootstrap, Inter/Manrope, openpyxl, PostgreSQL/Supabase deployment, isolated SQLite test configuration; no new frontend framework or paid service.

## Plan package and precedence

1. `2026-10-24_201051-hc-additions-roadmap.md` — this source register, evidence, decisions, release order, and overall acceptance.
2. `2026-10-24_201051-staff-intake-completion.md` — five-step staff input, real attachments, import UI, activation, and digital staff profile.
3. `2026-10-24_201051-hc-menu-integration.md` — ten functional menu groups, real destinations, own-profile access, truthful analytics, and advanced-feature gates.

All three files are in `.hermes/plans/`. Plan instructions are English; quoted Indonesian UI strings are literal product copy and must not be translated during execution.

The earlier plans `docs/superpowers/plans/2026-10-24-staff-intake-efile.md` and `2026-10-24-human-capital-menu-workflows.md` describe these same documents. Their source hashes are unchanged. This is **not a new version of the requirements**: it is an execution addendum correcting their stale baseline and incomplete integration. The existing model/service families have already been committed in `ae0ccb6`; do not execute their old create-from-scratch steps again. Use the new package for sequencing and verified gaps; retain compatible domain contracts from the earlier plans.

The Integrated Control readability/registration plan at `.hermes/plans/2026-10-24_185444-control-readability-emr-registration.md` is a different workstream. Its target code is now modified and has a local QA report. This package does not repeat, revert, commit, or redeploy those changes.

## Source register

| Input | Verified SHA-256 | Scope |
|---|---|---|
| `C:/Users/cubeb/Downloads/Input Data Staf.docx` | `7688458b28949f7b15ffd3121ea689e69ffad08d191fb91ccf55726b48ce3940` | Two intake methods, five form steps, digital staff profile, account onboarding, supporting documents, audit |
| `C:/Users/cubeb/Downloads/struktur menu ideal Human capital.docx` | `ef7651202ed97bb39ecfcbb0a799294c5ada0e101a4fe4cecf7d613ac3afda0d` | Ten final navigation groups, EWS, staffing, e-file, shifts, clinical privileges, evaluation, job descriptions, staff health, self-service, reports; trainees nested under e-file |
| `C:/Users/cubeb/AppData/Local/Temp/orca-paste-1792847426314-a4b558c7-369a-4b0a-bec6-9f8cabb1e49f.png` | Not hashed; visually inspected through the image tool | Reference for existing Integrated Control styling, not evidence of hidden HC behavior |

Both DOCX packages were read completely and contain no embedded media. The menu document discusses eleven numbered topics but its final tree has ten top-level groups: trainees are a subcategory of e-file.

### Screenshot interpretation

The screenshot shows `/control/`, a navy/indigo masthead, the formal product name, a large white `Unit Contoh` selector with `HUMAS-CS`, and a four-metric strip. The masthead uses substantial vertical space and has an unused right-hand area; metric descriptions are visibly smaller than the title/body. It does **not** show the HC menu, staff-input form, or a registration failure. Retain its brand language for HC, but do not infer new screens, remove the unit selector, change the displayed business metrics, or redesign the entire shell based on this image alone. The existing control readability work remains separately owned.

## Current evidence: source, schema, and data are separate

Read-only inspection on `master` at `4e47a14` found:

| Area | Evidence | Consequence |
|---|---|---|
| HC foundation | Commit `ae0ccb6` includes intake, import/invitation services, navigation, WISN, clinical privilege, jobdesc, evaluation, portal, presence, and KPS files | Existing code is partial delivery, not absent infrastructure |
| Navigation | `sdm/navigation.py` defines ten groups, but production templates/context/dashboard still use booleans, button rows, `_hc_navigation`, and `_level_cards` | Integrate the registry; do not add a second registry |
| Routes | `sdm/urls.py` includes the wizard but no Excel-import, shift, jobdesc, or OPPE/FPPE UI routes; `accounts/urls.py` has no activation endpoint | Services and models alone do not satisfy user journeys |
| Wizard | `wizard.html:58` and `wizard_finalize.html:33` reverse a route with the wrong argument count; step five uses an anchor rather than submitting data | Fix navigation and save behavior before adding visual decoration |
| Documents | `IntakeStep5Form` has metadata only, the view omits `request.FILES`, and the finalizer creates no file version | Real uploads remain required |
| Account choice | Step four is read, but ignored by the finalizer; `create_account` defaults to true; invitation service exists without a public acceptance page | Make the requested onboarding outcome reachable and explicit |
| Finalization | Checks required steps 1/2 only; version comes from a freshly loaded server object; no row lock/result link; idempotency argument unused; direct placement create bypasses `save_assignment` | Add a tested transaction/idempotency boundary |
| Import | Service exists; parser uses `data_only=True`, does not enforce its ZIP budget constant, and loads every organizational unit | Harden parser/scope and expose template → preview → apply → result |
| Profile | Personal/employment/license tables exist, but their existence does not establish complete detail/edit/self-service UI | Finish Digital Staff Profile, not just a success redirect |
| Own portal | `_own_employee` depends on `visible_employees`, requiring HR grants even for the account's linked employee | Implement a separate own-only boundary, never grant staff directory access to fix this |
| Analytics | Dashboard no longer has the old first-200 cap, but compliance population ignores profession/status filters; historical resolver starts with today's visibility; turnover/BOR remain incorrectly scoped | Preserve fixed behavior; target remaining defects with contradictory fixtures |
| Operational local database | SQLite opened with URI `mode=ro` and `PRAGMA query_only=ON` | No normal ORM application initialization or writes were used |
| Latest recorded HC migration | `0024_add_evaluasi_klinis`; source also has `0025_add_presensi_models` | Presence schema is not installed locally; do not claim full applied schema |
| Local row counts | `Pegawai=0`, personal profiles=0, intake drafts=0, import batches=0, invitations=0, document versions=0; HC grants=0, document rules=0, mappings=0; units=154 | Earlier baseline's 425 staff, 219 units, and 5,256 grants are **not current local facts**; do not seed them back or infer deletion/history |
| Presence tables | `sdm_shiftdinas` and `sdm_peristiwapresensi` absent | Keep presence unavailable until schema and workflow gates pass |
| Working tree | Modified control files/assets plus unrelated seed commands; untracked prior plans/catalogue/HC templates | Preserve all user work; read existing untracked templates before editing |

These facts describe the local workspace, not production. No live database/bucket/email endpoint was inspected, and no current automated tests or migrations were executed in this planning turn. The historical QA reports do not prove this package's missing flows pass.

## Design decisions and tradeoffs

1. **Extend rather than replace.** Keep current IDs, models, forms/routes, audit, and storage. Completing integration takes more careful compatibility tests than rebuilding screens, but avoids two staff masters and duplicated authorization.
2. **Deliver core onboarding first.** HR must be able to add a person, upload actual files, preview imports, and open a useful profile before advanced analytics are advertised. Advanced features remain in the roadmap and must not be silently dropped.
3. **Use activation links, not emailed passwords.** The document's automatic-login outcome is retained via an expiring, single-use link and user-chosen password. Account creation is selectable and separate from employment existence; HR data entry alone must not grant administrator access.
4. **Ten groups, honest availability.** Keep all ten source groups represented for an authorized HC manager, with explicit noninteractive unavailable states where no accepted journey exists. Unauthorized groups are hidden; delivered features link to real guarded routes. Staff see only their own portal, not the manager's ten-group workspace.
5. **Keep terminology honest.** Activity FTE is not WISN; a printable SPK is not a certified electronic signature; any-course completion is not twenty annual clock hours; a location submission is not verified attendance; an EP number is not an approved mapping merely because a document lists it.
6. **No automatic operational setup.** The zero-row local database is an observed state, not authorization to create employees, grants, requirement rules, or privileged accounts. Setup uses reviewed source data and a separately approved environment target.

## Delivery order

| Release gate | Deliverable | Owner |
|---|---|---|
| R0 | Record current regression baseline, preserve working tree, confirm source and migration graph | Both companion plans' preparation step |
| R1 | Wizard navigation/version/state fixes; canonical finalization; complete staff profile | Staff plan, tasks S1–S3 |
| R2 | Actual typed private uploads and resumable failure handling | Staff plan, task S4 |
| R3 | Versioned Excel template, scoped preview/apply, full field parity | Staff plan, task S5 |
| R4 | Optional post-commit invitation, acceptance page, resend, own-only portal | Staff plan S6; menu plan M3 |
| R5 | Ten-group registry integrated across HC navigation/dashboard, existing destinations retained | Menu plan M1–M2 |
| R6 | Consistent EWS, cohort/period metrics, scoped staff sample reports | Menu plan M4–M5 |
| R7 | Advanced jobdesc/OPPE/FPPE/privilege/trainee and shift workflows, accepted independently | Menu plan M6; old owner tasks retained, not marked finished |
| R8 | Browser acceptance, PostgreSQL migration rehearsal, private-storage/email staging verification, release report | Both plans' final gate |

Implement sequentially where files or contracts overlap. A worker on S6 and a worker on M3 both touch own-profile/account boundaries; schedule them serially. Staff/model/schema work owns `sdm/models/intake.py`, `sdm/intake_views.py`, import/invitation services and `accounts/urls.py`. Menu work owns `sdm/navigation.py`, `sdm/context_processors.py`, HC dashboard/navigation templates, and metric/report integration. Coordinate shared edits to `sdm/urls.py`, `sdm/akses.py`, `sdm/views.py`, and storage; never apply stale patches from two workers.

## Acceptance criteria

- [ ] Both source documents have requirement-to-task coverage in the companion plans.
- [ ] HR can complete all five steps, resume/backtrack, attach actual files, finalize once, and open a useful Digital Staff Profile.
- [ ] Excel preview creates no canonical employees; confirmation creates reviewed valid records once, with row-level errors and scope enforcement.
- [ ] Optional account activation works end to end without temporary passwords or elevated-role delegation.
- [ ] Staff can see their own profile/documents and requests without permission to browse coworkers.
- [ ] All ten menu groups have correct visibility and an honest real-route or unavailable-state contract; earlier recruitment/training/analytics entry points remain reachable.
- [ ] Dashboard/report filters describe the same employee population and period; insufficient source/configuration is explicit, never invented compliance/FTE.
- [ ] Private personnel/health data stays private; general HR and accreditation exports do not acquire K3 clinical access.
- [ ] Advanced groups are separately acceptance-tested before enablement; no false claim of full functional completion based solely on menu count.
- [ ] Fresh tests, browser evidence, schema rehearsal, and environment-specific verification are recorded separately.
- [ ] No production import, grant change, email delivery, push, or deployment occurs without explicit approval.

## Open policy inputs — not blockers for core UI fixes

- Hospital employee-number pattern and sequence scope; until configured, allow valid manual NIP and never invent an institutional format.
- Full-time weekly hours and retirement-age policy by staff category; show computed age/tenure only from known dates and do not invent retirement rules.
- Delegable system roles and account-active policy for nonclinical staff; do not map a visual HR/unit-head selector to elevated system access automatically.
- Reviewed FTE/WISN worksheet and annual training/exemption policy; the source's twenty hours is a requested target, not independently validated regulatory text.
- Committee/issuer authority, accepted clinical action map, supervision/countersignature policy, and accredited source edition for numbered KPS mappings.
- Presence/leave/shift approval policy and optional remuneration export format. No payroll engine or continuous location tracking is included.

## Execution handoff

Start with the staff plan's R0/S1 failing tests, then finish one complete onboarding journey before enabling new navigation links. Prefer native implementation with focused review for the tightly coupled wizard/storage/import path; independent menu/metric tasks may use separate workers only after their dependencies are fixed. Do not execute the older plans wholesale, restore their historical row counts, or interpret this plan as production authorization.
