# Staff Intake / e-File / Activation — Release Evidence

Module: `sdm` (Arima Human Capital), Track B. This document records what is
implemented, verified, and what remains an external deployment gate. Evidence,
not a claim of production readiness.

## 1. Delivery status

| Task | Scope | Status | Tests |
|---|---|---|---|
| B1 | Staff census provenance (`data_origin`, `reconcile_hc_staff` dry-run/apply) | Implemented | `sdm/tests/test_staff_reconciliation.py` |
| B2 | Personal/employment/qualification fields + `validate_personal_data` | Implemented | `sdm/tests/test_intake.py` (via service contract) |
| B3 | Exact document/requirement matching (`jenis_berkas`), 5 MiB intake limit | Implemented | `sdm/tests/test_dokumen.py`, `test_private_documents.py`, `test_storage_backend.py`, `test_legacy_credentials.py` |
| B4 | Five-step resumable intake wizard + `finalize_staff_intake` | Implemented | `sdm/tests/test_directory.py` (updated), `sdm/intake_views.py` |
| B5 | Versioned Excel template, preview, explicit import decisions | Implemented | `sdm/tests/test_staff_import.py` |
| B6 | Optional login activation without privilege escalation | Implemented | `sdm/tests/test_staff_invitation.py` |
| B7 | Reviewable self-service corrections (`LayananMandiri`) | Implemented | `sdm/tests/test_layanan_mandiri.py` |
| B8 | Controlled configuration, reconciliation and release (this gate) | In progress | — |

"Implemented" means code, migration, and automated tests exist. It does not mean
deployed, provisioned, or accepted by hospital stakeholders.

## 2. New data contracts (additive, no existing rows altered)

- `Pegawai.data_origin` — `UNCLASSIFIED/DEMO/VERIFIED_IMPORT/MANUAL`; existing rows default to `UNCLASSIFIED`.
- `MasterProfesiPegawai` — reviewed profession master (MEDIS/KEPERAWATAN_KEBIDANAN/NAKES_LAIN/NON_KLINIS).
- `DokumenPegawai.jenis_berkas` — exact file-identity discriminator (KTP/FOTO/IJAZAH/TRANSKRIP/STR/SIP/SIPA/KONTRAK/SK_PENGANGKATAN/SPK_RKK/URAIAN_TUGAS/SERTIFIKAT/OTHER).
- `AturanDokumen.jenis_berkas_wajib` — required exact file identity per requirement rule.
- `ProfilPribadiPegawai`, `RiwayatKepegawaian`, `RiwayatPendidikanPegawai`, `IzinProfesiPegawai` — extended personal/employment/qualification records.
- `UrutanNomorPegawai` — configured, row-locked NIP numbering (never `count()+1`).
- `DrafInputPegawai` — persisted resumable draft (no file bytes/raw NIK in cookies/URLs).
- `BatchImporPegawai` — preview/apply batch with idempotency key, hash, and row decisions.
- `UndanganAkunPegawai` — single-use, expiring activation link (no password in email).
- `LayananMandiri` — reviewable self-service request (profile correction/training/leave/document).

## 3. Behavior contracts enforced

- Exact matching: verified STR cannot satisfy SIP/SPK; photo cannot satisfy KTP; diploma cannot satisfy transcript; external-clinic SIP cannot satisfy local-RS SIP; rejected version does not win arbitrarily.
- Compliance completeness counts requirements and fully-complete employees as distinct metrics; empty/unreviewed data never masquerades as 100%.
- Intake attachment limit 5,242,880 bytes enforced in form/service/storage backend; fake MIME/signature and oversize rejected; existing PNG downloads unaffected.
- Five-step wizard: drafts resumable, expired/concurrent tab/revoked-grant handled; no half-employee, leaked upload, or account.
- Import: preview creates zero canonical rows/placements/accounts; apply is idempotent; repeat apply returns same batch; display-name match never authorizes merge; stale preview rejected.
- Activation: accounts inactive/unusable until acceptance; expiring single-use link; replay/expired/changed-email denied; no health/global grant created by intake operator; mail failure leaves `Profil tersimpan; undangan belum terkirim` with resend.
- Self-service: actor may only submit for own linked employee; reviewer requires scoped `can_manage_hc_employees`; no self-service writes to NIP/NIK, profession, category, unit/FTE, role, verified-document flags, or SPK authority.

## 4. Verification performed

Local, isolated test database only:

| Command | Result |
|---|---|
| `manage.py test sdm` | 260 tests, 0 failures |
| `manage.py check` | no issues (1 pre-existing silenced check) |
| `manage.py makemigrations --check --dry-run` | No changes detected |

New test modules added:
- `sdm/tests/test_staff_reconciliation.py`
- `sdm/tests/test_staff_import.py`
- `sdm/tests/test_staff_invitation.py`
- `sdm/tests/test_layanan_mandiri.py`
- `sdm/tests/test_dokumen.py` (RED matching cases — GREEN)
- `sdm/tests/test_directory.py` (updated to wizard flow)

No production database, bucket, mail server, or deployment was touched.

## 5. External gates (NOT completed — require explicit execution instruction)

1. **Django version alignment** — installed Django 6.1.1 differs from pinned `requirements.txt` 6.1.2. Alignment requires an approved implementation-environment setup (not silently changed in planning).
2. **Private bucket provisioning** — `HC_PRIVATE_STORAGE_BUCKET` private bucket; `SUPABASE_URL` and `HC_PRIVATE_STORAGE_SERVICE_KEY` configured.
3. **Anonymous-denial verification** — private objects must not be publicly accessible.
4. **Legacy credential reconciliation rehearsal** — run `reconcile_hc_staff` dry-run on a sanitized copy; 13 metadata-only legacy credentials remain metadata-only until reviewed.
5. **Employee backfill / reviewed census** — B1 `reconcile_hc_staff --apply` requires an explicit reviewed artifact JSON; no approximate-name matching or silent identifier blanking.
6. **PostgreSQL migration rehearsal** — migrations validated on SQLite only; apply from empty and populated PostgreSQL databases before release.
7. **Scheduler/mail provisioning** — `hc_reminders` and activation mail delivered via approved external infrastructure, not request threads.
8. **Stakeholder acceptance** — HR/accreditation owner approval of profession master, document rules, and reviewed census artifact.

## 6. Rollback

- Disable new intake/import/invitation menu destinations via `HcGrant`/feature settings.
- Preserve all canonical staff, files, audit, and existing routes; do not reverse populated migrations destructively.
- Archived/superseded document versions remain readable to authorized reviewers.
