# Arima Human Capital — Release Evidence

Module: `sdm` (Arima Human Capital). This document records what is implemented, what is verified, and what remains an external deployment gate. It is evidence, not a claim of production readiness.

## 1. Delivery status

| Level | Scope | Status |
|---|---|---|
| Level 1 | Direktori pegawai, e-file privat, kepatuhan dokumen, peta ketenagaan (FTE), pengingat, dasbor + kartu hub | Implemented and covered by automated tests |
| Level 2 | Rekrutmen, PSV, RKK/SPK, orientasi | Implemented at service + route level |
| Level 3 | Penilaian kinerja, TNA, diklat | Implemented at service + route level |
| Level 4 | Risiko/insiden K3, imunisasi/MCU, break-glass | Implemented at service + route level |
| Level 5 | Snapshot analitik, audit KPS, talent, skenario, ekspor | Implemented at service + route level |

"Implemented" means code, migration, and automated tests exist. It does not mean deployed, provisioned, or accepted by hospital stakeholders.

## 2. Criteria traceability

| ID | Requirement | Implementation | Automated coverage |
|---|---|---|---|
| HC-01 | FTE calculator with versioned assumptions | `sdm/models/formasi.py`, `sdm/services/formasi.py` | `sdm/tests/test_formasi.py` |
| HC-02 | Digital staff profile, search, pagination, filters | `sdm/views.py` (`pegawai_list`), `sdm/tests/test_directory.py` | `test_directory.py` |
| HC-03 | Mandatory-document panel with requirement matrix | `sdm/models/dokumen.py` (`AturanDokumen`), `sdm/services/kepatuhan.py` | `sdm/tests/test_dokumen.py` |
| HC-04 | Disjoint 30/60/90 expiry bands, idempotent reminders | `sdm/services/kepatuhan.py`, `sdm/models/pengingat.py` | `test_dokumen.py`, `test_dashboard.py` |
| HC-05 | Recruitment pipeline with history | `sdm/models/rekrutmen.py`, `sdm/services/rekrutmen.py` | `sdm/tests/test_rekrutmen.py` |
| HC-06 | PSV tied to an exact document version | `sdm/models/kredensial.py` (`VerifikasiSumber`) | `test_rekrutmen.py` |
| HC-07 | RKK, committee decision, numbered SPK | `sdm/models/kredensial.py`, `sdm/services/rekrutmen.py` | `test_rekrutmen.py` |
| HC-08 | Orientation tracker with sign-off | `sdm/models/orientasi.py` | `test_rekrutmen.py` |
| HC-09 | Versioned appraisal with finalized immutability | `sdm/models/kinerja.py`, `sdm/services/kinerja.py` | `sdm/tests/test_kinerja.py` |
| HC-10 | Provenance-backed TNA | `sdm/services/tna.py` | `test_kinerja.py` |
| HC-11 | Course calendar, attendance, evaluation, completion | `sdm/models/diklat.py`, `sdm/services/diklat.py` | `test_kinerja.py` |
| HC-12 | K3 hazard register linked to organizational risk | `sdm/models/k3.py` (`RisikoK3Pegawai`) | `sdm/tests/test_k3.py` |
| HC-13 | Occupational health with clinical boundary | `sdm/models/k3.py`, `sdm/services/k3.py` | `test_k3.py` |
| HC-14 | Staff incident intake through reviewed closure | `sdm/services/k3.py` | `test_k3.py` |
| HC-15 | Coverage-aware analytics snapshots | `sdm/models/analitik.py`, `sdm/services/analitik.py` | `sdm/tests/test_analitik.py` |
| HC-16 | Compliance audit + redacted export | `sdm/services/ekspor.py` | `test_analitik.py` |
| HC-17 | Versioned performance/competency talent assessment | `sdm/models/analitik.py` (`PenilaianTalent`) | `test_analitik.py` |
| HC-18 | Rule/scenario DSS with human approval | `sdm/models/analitik.py` (`SkenarioSDM`) | `test_analitik.py` |

## 3. Verification performed

Local, isolated test database only:

```bash
.venv/Scripts/python.exe manage.py test sdm
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

Recorded results (2026-10-23, local SQLite test database, no production access):

| Command | Result |
|---|---|
| `manage.py test sdm akreditasi accounts` | 701 tests, 0 failures |
| `manage.py test sdm` | 222 tests, 0 failures |
| Level suites (`test_rekrutmen`, `test_kinerja`, `test_k3`, `test_analitik`, `test_level_routes`, `test_level_actions`, `test_ekspor`) | 82 tests, 0 failures |
| `manage.py check` | no issues (1 pre-existing silenced check) |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py collectstatic --noinput` | 0 copied, 134 unmodified, 371 post-processed |

Migrations applied to a local copy of `db.sqlite3`: `sdm.0001`–`sdm.0011` all OK.

Runtime smoke (local server, seeded local database, then fixtures removed):

- `/human-capital/`, `/pegawai/`, `/formasi/`, `/rekrutmen/`, `/kredensial/`, `/orientasi/`, `/kinerja/`, `/diklat/`, `/k3/`, `/analitik/` → 200 for a granted user.
- Same routes → 403 for an ungranted user.
- `/control/` shows the fourth card for a granted user and hides it otherwise, with the three existing cards and no sidebar intact.
- `/human-capital/analitik/ekspor/` returns a valid xlsx workbook.
- `reconcile_hc_credentials --dry-run` → `credentials=13 linked=0 eligible=0 unresolved=13` (no mutation).
- `reconcile_hc_credentials --inventory` fails closed because no private storage credentials are configured — the intended behaviour.
- `hc_reminders --dry-run` → `pending_reminders=0`.

No production database, bucket, or deployment was touched.

### 3.1 Added after the first verification pass

| Gap | Resolution | Coverage |
|---|---|---|
| No create routes for Level 2–5 | `rekrutmen_create`, `rekrutmen_add_application`, `kredensial_create`, `kredensial_add_privilege`, `kredensial_psv`, `orientasi_create`, `orientasi_complete`, `kinerja_finalize`, `diklat_create`, `diklat_certificate`, `k3_report` | `sdm/tests/test_level_actions.py` |
| PSV had no UI | PSV form on the credential detail page | `test_level_actions.py` |
| QR token never consumed | `check_in_by_token` (session-bound, expiry-checked) | `sdm/tests/test_ekspor.py` |
| No training certificate | `SertifikatDiklat` + `issue_certificate` (requires passing evaluation) | `test_ekspor.py` |
| `PemetaanStandarSDM` unused | `compliance_audit` reports unmapped requirements separately | `sdm/tests/test_analitik.py` |
| No BOR | `compute_bor` derives occupancy from admissions; `staffing_bor_comparison` refuses mismatched periods | `test_ekspor.py` |
| No PDF export | `export_audit_pdf` via reportlab | `test_analitik.py` |
| Dashboard missing 2 KPIs and 5 level cards | training coverage, overdue orientation, five level cards, KPI drill-down links | `sdm/tests/test_dashboard.py` |
| Dashboard had no cache | versioned per-identity/permission key + signal invalidation | `test_dashboard.py` (`DashboardCacheTests`) |
| Reminders covered documents only | `sync_task_reminders` adds orientation/appraisal due and overdue bands | `test_dashboard.py` (`ReminderTargetTests`) |
| Admin covered 2 models | 11 additional registrations, snapshot read-only | `sdm/tests/test_admin.py` |
| No forms for Level 2–5 | `sdm/forms/level2_5.py` with scoped querysets | `test_level_actions.py` |

## 4. External gates (NOT completed)

These require credentials, approvals, or infrastructure that application code cannot supply:

1. **Private bucket provisioning** — create `HC_PRIVATE_STORAGE_BUCKET` as a private bucket; set `SUPABASE_URL` and `HC_PRIVATE_STORAGE_SERVICE_KEY`. See `docs/security/human-capital-private-storage.md`.
2. **Anonymous-denial verification** — `manage.py reconcile_hc_credentials --inventory --verify-anonymous-denial` must report `anonymous_exposed_or_error=0`.
3. **Legacy public-object remediation** — separate written approval before moving/deleting existing public credential objects.
4. **Sanitized rehearsal** — restore a sanitized database copy, run inventory → dry-run → apply → inventory, and confirm counts.
5. **Employee backfill** — run `manage.py backfill_hc_employees --apply` right after
   migrating. Without it, accounts with no `sdm.Pegawai` cannot upload legacy KPS
   credentials (the route fails closed with a message rather than storing a file).
6. **PostgreSQL migration rehearsal** — migrations were validated on SQLite only. Apply from empty and populated PostgreSQL databases before release.
7. **Scheduler provisioning** — `hc_reminders` must be scheduled externally. Vercel request processes are not persistent workers.
8. **Hospital-approved retention/access policy** for occupational health records.
9. **Stakeholder acceptance** — KPS mapping review by the accreditation owner; clinical committee sign-off for privileging.

## 5. Rollback

- Disable the Human Capital hub card and revoke `HcGrant` rows; existing accreditation routes and legacy KPS portal remain functional.
- Do not reverse populated migrations destructively and do not delete private objects.
- Archived/superseded document versions remain readable to authorized reviewers, so approved history survives rollback.
