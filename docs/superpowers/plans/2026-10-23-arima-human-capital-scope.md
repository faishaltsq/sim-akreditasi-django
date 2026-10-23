# Arima Human Capital — Product Scope and Source Traceability

**Status:** Proposed scope, not implemented.
**Source:** `C:\Users\cubeb\Downloads\manajemen sdm di arima.docx`.
**Source SHA-256:** `3fc60665cd5e64baaece56f9e949169b185e6fd68162971c795b5ae8e7a4ee76`.
**Implementation plan:** `2026-10-23-arima-human-capital.md` in this directory.

## 1. Product placement and naming

The visible product name must be exactly **Arima Human Capital**, including capitalization and spacing. Add it as the fourth module card on the main `/control/` hub, alongside Risk, EMR, and Accreditation Documents. Use the same name for the Human Capital page title, hero, navigation entry, and breadcrumb. Preserve the overall ARIMA Hospital Integrated Control name and existing module titles. Also expose a permission-filtered shortcut on the legacy accreditation dashboard; do not rename the entire hospital dashboard to the HR product name.

Proposed entry point: `/human-capital/`, URL namespace `sdm`, route name `sdm:dashboard`.

Card subtitle: `Perencanaan tenaga, kepegawaian, kredensial, diklat, dan kesehatan kerja`.
Card action: `Buka Arima Human Capital`.

The five levels are functional maturity groups, not account roles, subscription tiers, or organizational levels. All groups are visible to authorized users once delivered; an undelivered group must not present a working-looking button or invented metric.

## 2. Navigation and page composition

| Group | Visible menus | Primary output |
|---|---|---|
| Ringkasan | Dasbor SDM, Notifikasi & Tugas | Actionable aggregate metrics and pending work |
| Level 1 — Perencanaan & Kepegawaian | Peta Ketenagaan, Kalkulator FTE, Direktori Pegawai, e-File Kepegawaian | Staffing needs, actual allocation, gaps, complete staff files |
| Level 2 — Rekrutmen & Kredensial | Rekrutmen & Seleksi, Verifikasi Sumber Utama, Kredensial & RKK/SPK, Orientasi | Recruitment pipeline, documented PSV, approved privileges, orientation progress |
| Level 3 — Kinerja & Pengembangan | Penilaian Kinerja, Kebutuhan Pelatihan (TNA), Kalender Diklat, Kehadiran & Sertifikasi | Appraisal history, justified training needs, attendance and credit history |
| Level 4 — Kesehatan & Keselamatan Kerja | Risiko K3 Staf, Imunisasi & MCU, Insiden K3 & Tindak Lanjut | Workplace risk controls and restricted occupational-health records |
| Level 5 — Analitik & Kepatuhan | Analitik Ketenagaan, Audit Kepatuhan KPS, Talent Pool & Suksesi, Rekomendasi SDM | Explainable workforce decisions and evidence-ready reporting |

Dashboard layout:

1. Hero `Arima Human Capital`; hospital name, selected unit, period, refresh timestamp.
2. Filter row: unit, profession, employment status, period. Server-side authorization limits every choice and every result.
3. KPI cards: active employees; staffing sufficiency; required-file completeness; documents expiring within 30 days; mandatory-training coverage; overdue orientation. Each card drills into its filtered underlying records.
4. Staffing requirement-versus-actual table and chart by unit/profession.
5. Work queue: pending PSV, credential committee reviews, unfinished orientations, appraisals due, training expirations. Show only work the current user may access.
6. Five functional-level entry cards, responsive and keyboard accessible.
7. Compliance summary and training calendar. Occupational-health details never appear on this general dashboard.

No-data text: `Belum ada data`. Unknown denominator: `Belum dapat dihitung`. Not applicable: `Tidak berlaku`. Do not display a green 100% for an empty requirement set. Charts must have table equivalents; badges must include text, not color alone. At narrow widths, retain all navigation and horizontally scroll wide matrices.

## 3. Source requirements and acceptance criteria

| ID | Source location | Requirement and acceptance criterion | Delivery |
|---|---|---|---|
| HC-01 | Level 1; FTE Calculator | Record effective working time, service volume, activity standards, patient/workload context, equipment assumptions, and qualifications. Produce reproducible needs/actual/gap per unit and profession, with reviewer approval and versioned assumptions. | Level 1 |
| HC-02 | Level 1; Digital Staff Profile | Search and paginate all employees, including non-PPA and employees without login accounts; filter unit/profession/employment status. Preserve employment, assignment, job-description and education histories. | Level 1 |
| HC-03 | Level 1; mandatory-document panel | Manage diploma, transcript, STR, SIP, job description, contract and certificate files. Apply a versioned requirement matrix by profession/assignment; distinguish missing, pending, rejected, valid, expiring, expired and not applicable. | Level 1 |
| HC-04 | Levels 1 and 3; expiry badges | Display overdue and non-overlapping 30/60/90-day expiry bands; lifetime/not-applicable documents do not receive expiry alerts. Duplicate notification runs do not duplicate reminders. | Level 1 |
| HC-05 | Level 2; recruitment Kanban | Authorized users move applications through Lamaran Masuk → Seleksi Administrasi → Tes Kompetensi → Wawancara → Diterima/Ditolak with transition history and keyboard alternatives. Hiring creates/links one employee transactionally. | Level 2 |
| HC-06 | Level 2; PSV | Preserve issuer, document version, reference, verifier, date, method, outcome and evidence of primary-source verification. Start with manual official-source recording; an API outage must never imply successful verification. | Level 2 |
| HC-07 | Level 2; clinical privileging | Submit RKK, committee review, recommend privileges, authorize SPK, print a numbered/versioned output, and support expiry/recredentialing. A document-verification flag alone never grants privileges. | Level 2 |
| HC-08 | Level 2; orientation tracker | Assign general and unit-specific programs on hiring/rotation; track due dates, required activities, assessor sign-off and completion percentage. Preserve prior-unit history. | Level 2 |
| HC-09 | Level 3; appraisal | Version appraisal periods, targets, behavioral/professional criteria, reviewer decisions and acknowledgments. Show historical scores without overwriting finalized evaluations. | Level 3 |
| HC-10 | Level 3; TNA | Trace each suggested training need to authorized PMKP results, patient-safety trends, safety-culture survey input, appraisal gaps or MFK findings. Manual provenance-backed input remains available where a source module does not exist. HR approves proposals. | Level 3 |
| HC-11 | Level 3; L&D calendar | Schedule BHD/BLS, PPI, K3RS and configurable courses; register participants, capture QR/class attendance, evaluate outcomes, and track JP and participation/professional credits separately. Completion requires the configured attendance/evaluation conditions. | Level 3 |
| HC-12 | Level 4; K3 risk register | Map biological, chemical/B3, ergonomic and violence hazards by workplace, with owners, control measures, risk assessments and review dates. Reuse/link the existing organizational risk register rather than duplicate it. | Level 4 |
| HC-13 | Level 4; employee occupational health | Record vaccination schedules/history, MCU results and exposure follow-up/counseling. Separate medical files and clinical notes from ordinary HR access; expose only authorized fitness/due-status summaries. | Level 4 |
| HC-14 | Level 4; K3 incident reporting | Report needle-stick injuries, musculoskeletal injury and other staff incidents; assign investigation, actions, evidence and closure review. Keep staff K3 and patient-safety incident classifications distinct. | Level 4 |
| HC-15 | Level 5; executive analytics | Display sourced workforce/BOR relationships, turnover, productivity and unit trends with formula, period, coverage and freshness metadata. Show unavailable when historical sources are insufficient. | Level 5 |
| HC-16 | Level 5; compliance audit | Calculate completeness/validity against applicable requirements and reviewed active-edition KPS mappings. Generate a permission-filtered one-click report with traceable evidence; never automatically change accreditation scores. | Level 5 |
| HC-17 | Level 5; talent pool | Build versioned performance-versus-competency 9-box assessments, explain thresholds, record review decisions and succession candidates. Restrict individual ratings to explicitly authorized reviewers. | Level 5 |
| HC-18 | Level 5; DSS | Suggest rotation, training budgets and specialist-shortage mitigation using explicit assumptions and provenance. Human review is mandatory; no automatic staffing/privilege decisions. Start with rules/scenarios before predictive models. | Level 5 |

## 4. Calculation contracts

### Workforce planning

Use one approved calculation method per planning version. Initial activity-based FTE:

`required_fte = sum(activity_volume * standard_minutes_per_activity) / effective_minutes_per_employee_in_the_same_period`.

For separately recorded support time, apply an explicit documented allowance once; never count the same allowance inside both effective time and a multiplier. Positive effective time and non-negative volumes/durations are required. Equipment and service categories classify activities/constraints, not unexplained multipliers. Store raw values and calculation version. Use Decimal arithmetic; round required headcount upward only after computing FTE. A WISN-specific workflow is a separately validated method, not an interchangeable label for a simple FTE calculator.

`actual_fte = sum(active_assignment_fraction_for_unit_and_profession_at_period_end)`.
`gap_fte = required_fte - actual_fte` (positive = shortage).
`staffing_sufficiency_pct = actual_fte / required_fte * 100`, only for positive requirement and matching scope/period.

Preserve both FTE and integer headcount. Employees assigned to multiple units must not count as full-time in each unit; overlapping fractions must not exceed their employment FTE.

### Compliance, learning and analytics

- Required-file completeness = valid, verified, currently applicable employee-document requirements / all currently applicable employee-document requirements. Count requirements, not uploaded files; duplicates never inflate the numerator. Show upload completeness and verified validity separately.
- Expiry: expired if expiry < local today; due today belongs to the 0–30-day band; 31–60 and 61–90 form the other disjoint bands. Use Asia/Jakarta local dates. A missing expiry is valid only when the document's explicit validity policy permits it.
- Training coverage = eligible active employees completing the configured course requirements / eligible active employees. Exemptions require reason, approver and validity dates.
- Orientation progress = completed required activities / assigned required activities; no assigned activities means not configured, not 100%.
- Turnover = departures in the reporting period / average active headcount over that period. Record the sampling convention and history coverage before enabling the metric.
- BOR = occupied bed-days / available bed-days for the same scope/period. Never derive historical BOR from today's bed snapshot or silently join hospital-wide BOR to a unit-only workforce number.
- Productivity requires a named output and staffing/time denominator. Do not equate login activity with clinical productivity.
- Budget scenarios use Decimal currency, course costs and approved participant counts. Talent axes and thresholds are versioned; absent/contested ratings remain unclassified rather than being assigned a low box.

## 5. Access boundaries

Use the existing accounts and role-configuration infrastructure, plus explicit Human Capital permissions and unit-scoped grants. Job title/unit name is not an authorization rule. Absence of a unit or grant must not imply global access.

| Actor | Allowed scope | Restricted material |
|---|---|---|
| HR administrator | Authorized hospital workforce planning and employment files | Raw MCU, vaccination and exposure clinical details |
| Unit head | Assigned unit and explicitly granted descendants; operational staffing and reviews | Other units, unrestricted personnel documents, unrelated health records |
| Employee | Own profile, permitted uploads, own orientation/training | Other employees and reviewer-only notes |
| Credential committee | Assigned profession/application and reviewer actions | Unrelated HR/health/talent data |
| Diklat operator | Course, attendance, certification and approved TNA work | Medical records and unrelated confidential employment documents |
| K3 clinician | Explicit occupational-health caseload and medical files | No automatic broad access merely from a K3 unit name |
| Director/executive | Authorized aggregate workforce views | Individual medical files; individual talent access needs a separate grant |
| Assessor | Time-bound, approved read-only redacted evidence scope | Raw employee/health files and unapproved exports |
| Technical superuser | Existing platform administration remains compatible | No Human Capital health grant by default; audited break-glass access only |

Audit sensitive reads, downloads, exports and workflow changes without logging medical content. Data-retention periods and consent/legal-basis configuration require hospital policy approval before production import; do not invent a duration.

## 6. Standards mapping and integrations

The attachment's KPS numbers are source claims, not a verified accreditation instrument. The current local catalogue includes KPS 10.1, 14–19 and 8.1 as well as KPS 1–12. Existing setup code and the attachment are not identical mappings. Resolve the active framework/edition and review the actual EP text with the KPS owner before publishing compliance labels. Store FK-based reviewed mappings to existing `StandardItem`/`EvidenceReq`, edition, reviewer and review date. Never seed a replacement accreditation catalogue as part of this feature.

Reuse existing organizational units, risk/incident/indicator sources and evidence workflows through explicit references. TNA consumes aggregate/authorized data, not patient identities or raw incident narratives. Safety-culture survey and MFK sources must be discovered before promising live connectors; where absent, capture approved manual findings with provenance. New HR evidence is published into the existing accreditation workflow only after approval, with a sanitized artifact and no private source-file URL.

## 7. Delivery priorities and exclusions

**MVP:** Level 1 plus the working dashboard/hub card, private storage, access control, safe legacy credential reconciliation, staffing calculations and document reminders.

**Next releases:** Level 2, then Level 3, then restricted Level 4, then Level 5 analytics and decision support. Rule-based TNA and scenario analytics precede optional AI and prediction.

Not in this scope: payroll/tax/BPJS calculation, shifts/rosters, biometric attendance hardware, leave/overtime payroll, a public applicant self-service portal, automatic external credential scraping, a new patient EMR, an accreditation catalogue replacement, automatic employment decisions, or an HR microservice rewrite. Recruitment begins as an authenticated internal operator portal. New public intake or external API integration requires its own approved scope.

## 8. Release-level acceptance

The module is complete only when all HC-01 through HC-18 criteria have working implementations and execution evidence. An MVP release is explicitly labeled Level 1 only. Production readiness requires tested migrations on SQLite and PostgreSQL, account/unit isolation, private-file access tests, core workflow E2E, audited/redacted exports, source mapping review, static collection, a verified deployment and a documented rollback. No application code or schema was changed while producing this scope.
