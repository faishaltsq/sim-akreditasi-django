# Dependency Vulnerability Audit — sim-akreditasi-django

## Audit Command

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"

# Option 1: pip-audit (if installed)
pip install pip-audit -q
pip-audit -r <(pip freeze) 2>/dev/null || pip freeze > .audit-freeze.txt && pip-audit -r .audit-freeze.txt && rm -f .audit-freeze.txt

# Option 2: uv pip compile → then pip-audit on the compiled set
uv pip compile requirements.txt > /tmp/compiled.txt
pip-audit -r /tmp/compiled.txt
```

## Cadence

- Run before every deploy.
- Weekly at minimum during active development.

## Upgrade Procedure

1. Bump the pinned version in `requirements.txt`.
2. Run the full test suite: `python manage.py test`.
3. Deploy to Vercel and verify smoke checks (see below).

## CVE Override Decisions

| Date | Package | Frozen Version | Override Version | CVE | Reason |
|------|---------|---------------|-----------------|-----|--------|
| 2026-10-14 | _(none)_ | — | — | — | Initial pin; no HIGH/CRITICAL CVEs found in direct dependencies. |

## Pinned Versions (as of 2026-10-14)

```
django==6.1.2
psycopg2-binary==2.9.13
dj-database-url==3.1.2
django-crispy-forms==2.7
crispy-bootstrap5==2026.9
openpyxl==3.1.5
gunicorn==26.2.0
whitenoise==6.12.0
requests==2.34.2
python-decouple==3.8
reportlab==5.0.1
```

---

## 2026-10-14 Post-Hardening Production Verification

**Commit range:** `7457862` → `5900520` (3 commits: Task 1–3)

| Check | Result | Notes |
|-------|--------|-------|
| Vercel build | ✅ Building / Ready | Deployment `sim-akreditasi-django-2bj5qs4wn` |
| root `/` | HTTP 302 | Redirects to login — expected |
| `/accounts/login/` | HTTP 200 | Serves login form — expected |
| Railway mirror | HTTP 404 | Railway service not running (not 400 — host not rejected) |
| `tests_security` | 11/11 pass | All existing + new security tests green |
| Rate limiter XFF spoofing | ✅ blocked | Last-hop bucket fires correctly on test `test_rate_limit_keys_on_last_xff_hop` |
| ALLOWED_HOSTS wildcards | ✅ removed | `.vercel.app`, `.railway.app`, `.onrender.com`, `.pythonanywhere.com` gone |
| CSRF_TRUSTED_ORIGINS | ✅ explicit | Only `sim-akreditasi-django.vercel.app` + Railway explicit domain |
| Dependency pins | ✅ applied | `django==6.1.2`, 11 packages pinned via `uv pip compile` |
