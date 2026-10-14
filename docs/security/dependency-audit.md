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
