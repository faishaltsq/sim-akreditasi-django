# ARIMA Human Capital and STARKES Improvement Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the existing ARIMA project against all three supplied documents, using verified current code/data rather than rebuilding implemented modules or inheriting stale completion claims.

**Architecture:** Three coordinated improvement tracks in the existing Django monolith: A — Human Capital navigation/operations, B — staff intake/e-file/activation, C — accreditation edition/archive/evidence integrity. A shared baseline and explicit ownership/dependency contracts prevent duplicate employee masters, duplicate document engines and conflicting catalogue migrations.

**Tech Stack:** Existing Django/templates/Bootstrap, SQLite local development, PostgreSQL/Supabase production architecture, private HC storage, openpyxl/reportlab and existing PDF parser. No microservices, SPA rewrite or paid platform is required.

**Spec:** The three DOCX source files and source hashes recorded in [Verified Baseline](2026-10-24-arima-improvement-baseline.md).

**Status:** Proposed improvement package for review. No application feature, schema, staff import, accreditation import, grant or deployment changed while preparing it.

## Global Constraints

- Plans are English for agent execution; UI and user-facing work summaries remain Bahasa Indonesia.
- Preserve current records, stable IDs, unit hierarchy, original files and unrelated untracked work.
- Existing modules are extended, not rebuilt. A feature having code/tests is distinct from configured data, complete UI, verified private storage and deployed acceptance.
- Real personnel and reviewed source data precede claims of workforce sufficiency, legal compliance, training coverage or active-2024 readiness.
- Production writes, migrations, seeding, grants, commits/pushes and deployment require a separate explicit execution instruction.
- Use the user's existing workflow if selected. Recommended default: subagent-driven implementation with independent review, one shared integration owner and real test output for each task.

## Review Focus

1. Seeded accounts/employees must not be promoted into a verified staff census through a blanket backfill.
2. A broad `CREDENTIAL` file cannot satisfy STR, SIP and SPK requirements interchangeably.
3. The local catalogue called 2022/version 2026 must not be assumed to have completed the previous 2024 rehearsal.
4. Historical scores/evidence must survive new edition activation and remain read-only under direct URL/API requests.
5. Navigation and extra modules must not ship ahead of their scoped permissions, working destinations and honest metric denominators.

## 1. Deliverables and reading order

All files are under `docs/superpowers/plans/`:

| Read | File | Purpose / scope |
|---|---|---|
| 1 | `2026-10-24-arima-improvement-roadmap.md` | This entry point: priorities, release order, ownership, decisions and acceptance |
| 2 | [2026-10-24-arima-improvement-baseline.md](2026-10-24-arima-improvement-baseline.md) | Current code/data evidence, source hashes, parser results and test baseline |
| 3 | [2026-10-24-staff-intake-efile.md](2026-10-24-staff-intake-efile.md) | Track B: eight tasks for census provenance, full fields, exact legal-document identity, five-step wizard, reviewed Excel import and optional activation |
| 4 | [2026-10-24-human-capital-menu-workflows.md](2026-10-24-human-capital-menu-workflows.md) | Track A: twelve tasks covering ten menu groups, trustworthy metrics, privileges, jobdesc, annual learning, OPPE/FPPE, K3, portal and optional operations |
| 5 | [2026-10-24-starkes-transition-hardening.md](2026-10-24-starkes-transition-hardening.md) | Track C: seven tasks for source reconciliation, edition identity, archive guards, semantic/evidence mapping, safe activation and UAT |

**27 implementation tasks in three tracks.** Each track contains current-state evidence, requirements, exact existing/new file ownership, proposed service contracts, task-level tests/acceptance, dependencies and release/rollback gates. Task counts were checked from the generated task headings, not estimated from prose.

## 2. What already exists — and what the data actually says

| Baseline | Observed current state | Consequence |
|---|---|---|
| HC implementation | Staff/placement, private e-file, FTE, recruitment, PSV/RKK/SPK, orientation, appraisal/TNA/training, K3 and analytics code exists | Do not rebuild these domains from the menu document |
| Staff/account data | 1,343 accounts; 425 employee records; all 425 employee numbers match seeder convention; all categorized PPA | These are not a verified staffing distribution or proof that the hospital has 425 actual clinical staff |
| Placements | 425, all beginning 2026-10-23 | Opening/backfill dates are not actual TMT or historical headcount |
| HC configuration | Zero canonical documents, rules and reviewed KPS mappings; no operational workforce/training/credential/K3 data in inspected tables | Configure/import reviewed real data; empty compliance is not 100% |
| Legacy credentials | 13 metadata rows, no file references; their owners lack employee links | Reconcile exact identities and missing evidence before canonical migration |
| Accreditation | One active local framework named 2022, version `2026`; 1,053 EP | Edition conflict and environment state must be resolved before cutover |
| Existing assessments | 298 positive-score records; 276 with evaluation notes | Do not relocate/delete them merely because a new EP code matches |
| Source/parser state | Decree emits 794 parsed unique EP; survey instrument emits 732; fixture has 783 entries but only 700 unique keys and lacks PROGNAS | Review sources/full text/RDWOS; no live import from current fixture |

All counts refer to **local `db.sqlite3`**, opened read-only. They do not assert current production state. The prior runbook's rehearsal and the earlier HC release record remain historical evidence, not a replacement for this current baseline.

## 3. Approach selection

| Approach | Result | Tradeoff |
|---|---|---|
| **Recommended: integrity-first incremental improvements** | Reuse working code; repair census/document/edition correctness, then complete core journeys, then optional operations | Early visible work includes configuration and guardrails, not only new menus; least data-integrity risk |
| Menu-only redesign | Faster presentation change | Leaves incomplete intake, false compliance matching, sampled metrics and unsafe archive/cutover behavior unresolved |
| Full HRIS/catalogue rewrite | New system and broad redesign | Duplicates identity/files/history, increases migration/deployment cost and discards existing verified work; not justified by the supplied requirements |

## 4. Prioritized findings

| Priority | Finding | Owner / fix | Verification |
|---|---|---|---|
| P0 | Current employee/account matrix includes deterministic seeded data | B1 provenance + reviewed reconciliation | No destructive cleanup; approved real/demo classification and exact ID preservation |
| P0 | Broad document-kind matching can reuse one CREDENTIAL for distinct licenses | B3 exact typed identity/context | STR cannot satisfy SIP/SPK; photo cannot satisfy KTP; external SIP cannot satisfy local site |
| P0 | Source fixture/parser inventories conflict and truncate content | C1 manifests/full text/review | Source hashes/pages, duplicate-free reviewed inventory, page provenance and complete RDWOS |
| P0 | Code-only score relocation and incomplete cutover atomicity | C2/C4/C5 | Old score FK/payload unchanged, reviewed lineage, failure-safe staging/activation |
| P0 | Archived catalogue not write-protected; mixed-edition reads/cache | C3/C6 | Direct write denial, nonmutating GET and exact same-edition totals |
| P0 | HC metrics sample 200 staff or use wrong period/unit data | A1 | 201+ staff regression, scoped historical BOR/turnover or explicit unavailable result |
| P1 | Intake misses source fields/import/account workflow | B2/B4–B8 | Five-step journey + preview/apply + optional single-use activation |
| P1 | Functional navigation/urgent legal EWS/reports incomplete | A2/A3/A5/A9 portal/A11 | Real authorized destinations, 7-day urgency, typed site/legal/report data |
| P2 | Jobdesc acceptance, clinical privilege enforcement, OPPE/FPPE and annual hours require completion | A6–A8 | Reviewed clinical rollout, versioned acknowledgment, separate clock hours/JP/SKP and K3 confidentiality |
| P3 | Shifts/geofencing/leave/remuneration bridge newly expand the old scope | A9 leave/A10 | Separate approval, attendance/leave concurrency and export reconciliation; no payroll |

P0 is a correctness/data-protection release blocker, P1 is core requested workflow, P2 is subsequent clinical/development completion, P3 is optional operational expansion. These are priorities, not claims of deployed incidents.

## 5. Sequencing and independent work

```text
B1 Census provenance ── B2 Personal/employment data ── B4 Wizard ── B6 Activation
       │                       │                         │
       └── B3 Exact e-file ─────┴── B5 Import ────────────┴── B7/B8 Readiness
                    │
                    ├── A1 Correct metrics ── A2/A3 Navigation & EWS
                    │                            ├── A4/A5 Workforce & privileges
                    │                            └── A9 Own portal
                    │
C1 Sources ── C2 Identity ── C3 Archive ── C4 Mapping ── C5 Activation ── C6/C7
                    │                                      │
                    └────────────────── A11 KPS reports ───┘
A5 privileges ── A6 Jobdesc/RME ── A7 OPPE/FPPE/training ── A8 K3 acceptance
A9 optional leave ── A10 optional roster/presence/export
```

This diagram shows primary dependencies, not permission to modify shared files concurrently. Track C source parsing and B1 census reconciliation can proceed independently. B2 and B3 may be developed with agreed schema ownership but merge serially. A11 must not activate KPS labels before C's source/mapping approval.

| Release gate | Included work | Working output | Blocking evidence |
|---|---|---|---|
| R0 — Trustworthy baseline | B1–B3, C1–C3, A1 | Reviewed staff/source identity; precise documents; archive/write/query integrity | Real census/source decisions, migration rehearsal and RED/GREEN regressions |
| R1 — Core HC usable | B4–B8, A2–A5 core, A9 own portal, A11 base | Complete individual/import intake, operational e-file, legal EWS, scoped staffing and reports | Private storage, mail activation, owner-reviewed rules, role/UAT acceptance |
| R2 — 2024 and clinical completion | C4–C7, A6–A8, A11 evidence packs | Approved 2024 transition with archive, evidence reuse, jobdesc/privilege workflows, OPPE/FPPE and K3 | Accreditation/clinical sign-off, PostgreSQL/failure/rollback rehearsal, deployment read-back |
| R3 — Optional manpower operations | A9 leave, A10 | Leave/shift/presence and external remuneration inputs | Approved entitlement/rest/geofence policies and event-hour reconciliation |

Do not wait for optional geofencing or remuneration to ship core intake/legal/archive fixes. WISN is a separately validated method within A4; existing activity-FTE improvements can ship first without mislabelling the method.

## 6. Decisions to approve before the owning task executes

These are explicit implementation gates, not missing-context guesses or blank implementation tasks:

| Decision | Recommended default | Tradeoff / owner |
|---|---|---|
| Workforce source and classification | Approved HR census; keep current seeder data separate and preserve it | No automatic role-account promotion; HR owns reviewed mapping |
| Identity and account | Employee independent of login; optional expiring activation link | Supports non-account staff; avoids emailing passwords |
| Legal document policy | Typed license/site/version and individually approved lifetime status | More metadata than one generic upload; prevents false compliance |
| 2024 authority | Decree as standards identity plus reviewed survey-instrument evidence instructions | Requires discrepancy reconciliation rather than trusting a single parser count |
| Historical scores | Preserve originals; new edition defaults unassessed; carry only with explicit owner approval | New dashboard may initially show incomplete assessment but history remains valid |
| Clinical enforcement rollout | Report-only rehearsal, reviewed staff/action coverage, controlled per-unit/action activation | Avoids changing clinical authority before committees validate mappings |
| Training target | Source's 20 clock hours/year as configurable approved policy, JP/SKP separate | Hospital confirms eligibility/exemptions/proration; do not infer legal universality |
| Optional operations | Separate release for leave/shifts/geofencing and remuneration export | Core scope ships sooner; no automatic payroll expansion |

## 7. Definition of done

- [ ] Every source requirement is mapped to a task and actual accepted UI/service journey; undelivered optional scope is labelled accurately.
- [ ] Existing UUID/account/unit/assessment/evidence history is preserved and lineage is reproducible.
- [ ] Scoped permissions hold for list/detail/direct POST/export/download; no health/private files leak into general HR/accreditation views.
- [ ] Targeted tests, migrated constraints on SQLite/PostgreSQL, browser critical journeys and failure/rollback scenarios have recorded real output.
- [ ] Source/census/rule/mapping owners approve exact versioned artifacts; empty/unreviewed data never masquerades as compliance.
- [ ] After separate deployment authorization: backup/restore, explicit migrations, private storage/mail/scheduler, tracked static assets and exact environment read-back pass.
- [ ] Release evidence names what is implemented, configured, installed, accepted and deployed separately.

## 8. Verification of this planning deliverable

Completed read-only source/code/data inspection, document hashing/package inspection, PDF parser inventory and isolated test baseline. **246 existing HC/STARKES tests passed**, with no system-check issues apart from one existing silenced check. Project Python is 3.12.10; installed Django 6.1.1 differs from pinned 6.1.2 and must be aligned during an approved implementation environment setup.

No feature implementation, schema/data migration, staff/catalogue import or deployment was performed. Plans should be reviewed before selecting and executing R0. The initial independent audit delegation was unavailable; final findings above were checked directly against local code/data instead of relying on an unreturned review.
