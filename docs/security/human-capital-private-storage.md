# Human Capital — Private Storage and Legacy Credential Runbook

Operational gates for `sdm` private personnel/health documents. Code paths are already implemented; the steps below are the external actions that cannot be performed from application code.

## 1. Required environment

| Variable | Purpose | Notes |
|---|---|---|
| `SUPABASE_URL` | Project origin used by the private storage client | Must be `https://` (or loopback in development) |
| `HC_PRIVATE_STORAGE_SERVICE_KEY` | Service-role key for private object operations | Never expose to templates, logs, or client bundles |
| `HC_PRIVATE_STORAGE_BUCKET` | Private bucket name (default `human-capital-private`) | Must not be a public bucket |

`SUPABASE_KEY` / `SUPABASE_BUCKET` (public evidence storage) are deliberately **not** reused. A missing private key fails closed with `PrivateStorageError`; there is no local-disk fallback.

## 1a. Backfill employee identities BEFORE deploying

The legacy KPS upload route now requires a `sdm.Pegawai` identity for the uploading
account. Accounts without one get a friendly error instead of a stored document, so
existing staff must be linked before the release is announced.

```bash
# Read-only preview
.venv/Scripts/python.exe manage.py backfill_hc_employees

# Apply (idempotent; never overwrites an existing link)
.venv/Scripts/python.exe manage.py backfill_hc_employees --apply
```

- Exact account match only. Duplicate or colliding employee numbers are blanked for
  manual review, never merged.
- Accounts already linked to an employee are skipped.
- Run this immediately after migrating and before inviting staff to upload credentials.

## 2. Provision the private bucket

1. Create the bucket as **private** (public access disabled) in the Supabase dashboard or with the CLI.
2. Keep the default object policy: no anonymous `SELECT`. Only the service key may read/write.
3. Do not enable a public bucket policy, CDN public path, or signed-URL caching at the edge.

## 3. Verify anonymous denial

```bash
.venv/Scripts/python.exe manage.py reconcile_hc_credentials --inventory --verify-anonymous-denial
```

Expected output shape:

```
INVENTORY total=<n> verified=<n> missing_or_mismatched=<n> anonymous_denied=<n> anonymous_exposed_or_error=0
```

- `anonymous_exposed_or_error` must be `0`. Any non-zero value means an object is publicly reachable **or** the probe failed; both block cutover.
- The command prints aggregate counts only — no employee IDs, filenames, or provider response bodies.

## 4. Inventory and checksum reconciliation

```bash
.venv/Scripts/python.exe manage.py reconcile_hc_credentials --inventory
```

`missing_or_mismatched` counts stored versions whose object is absent, truncated, or has a different SHA-256/size/MIME. Treat any non-zero value as a blocker before relying on those documents for compliance.

## 5. Reviewed legacy mapping

Dry-run (default, non-mutating):

```bash
.venv/Scripts/python.exe manage.py reconcile_hc_credentials --dry-run
```

Apply requires a reviewed mapping artifact with `schema_version`, `reviewed_by`, `reviewed_at` (timezone-aware), and per-credential `credential_id`, `employee_id`, `storage_key`, `original_filename`, `sha256`, `size_bytes`, `content_type`:

```bash
.venv/Scripts/python.exe manage.py reconcile_hc_credentials \
  --apply --mapping-artifact path/to/reviewed-mapping.json
```

Rules enforced by code:

- Only exact account-identity matches are linked. Ambiguous or colliding employee numbers stop that record for manual review; there is no fuzzy name matching.
- Repeated `--apply` is idempotent: already-linked credentials are reported, not duplicated.
- The private object is re-verified against the mapping hash/size/MIME before any row is written.
- Original `NakesCredential` rows, file references, IDs, and review status are preserved.

## 6. Sanitized rehearsal (required before production cutover)

1. Restore a sanitized copy of the production database and a representative object inventory into a non-production environment.
2. Set the private storage variables to the rehearsal project.
3. Run, in order:
   - `--inventory`
   - `--inventory --verify-anonymous-denial`
   - `--dry-run`
   - `--apply --mapping-artifact <reviewed artifact>`
   - `--inventory` again
4. Require: row reconciliation matches the reviewed artifact, `missing_or_mismatched=0`, `anonymous_exposed_or_error=0`, and an authorized download of one linked credential succeeds.
5. Record the counts and the artifact digest in the release evidence.

## 7. Privacy cutover for pre-existing public objects

Copying a legacy object into the private bucket does **not** make the original private. Before marking cutover complete:

1. List every legacy public object referenced by `NakesCredential.file_url`.
2. Obtain separate written approval for the bucket-policy/public-object remediation.
3. Move or delete the public objects, then re-run the anonymous-denial probe against each former URL.
4. Only after all probes deny access, mark the privacy cutover complete.

## 8. Rollback

- Do not delete private objects or reverse populated migrations.
- Disable Human Capital entry points and grants; the legacy KPS routes keep working for unresolved records.
- Archived/superseded versions remain readable to authorized reviewers, so approved history is never lost.
