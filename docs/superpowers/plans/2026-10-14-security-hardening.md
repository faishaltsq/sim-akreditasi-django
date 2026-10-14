# Security Hardening Implementation Plan — sim-akreditasi-django

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the findings from the October 14, 2026 security assessment of the ARIMA (sim-akreditasi-django) production app: spoofable client-IP extraction in the rate limiter, over-broad `ALLOWED_HOSTS` platform wildcards, and unpinned dependencies.

**Architecture:** Three independent, small hardening tasks on an existing Django 5 app deployed to Vercel (Python 3.12, `config/wsgi.py`, region icn1) with a Supabase Postgres backend via `DATABASE_URL`. Each task is a self-contained TDD cycle: failing test → implementation → passing test → commit. No schema changes, no new dependencies except the optional `pip-audit` dev tool.

**Tech Stack:** Django 5 (>=5.0,<7.0), Django test framework (`RequestFactory`), git-bash on Windows, Vercel deploy from git push.

**Spec:** Findings from the assessment chat of 2026-10-14 (summarized inline in each task's context; the authoritative detail lives in this document).

## Global Constraints

- Repo root: `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`
- Do NOT change database schema, Supabase config, or Vercel routing (`vercel.json` stays untouched except nothing).
- All existing tests must keep passing: `python manage.py test akreditasi.tests_security`
- App always sits behind a trusted reverse proxy (Vercel edge in production; runserver locally). This assumption is load-bearing for the IP extraction fix.
- Rate limiter response contract must not change: HTTP 429, JSON for `/ai/`+`/api/`+XHR paths, HTML otherwise.
- `SECRET_KEY`, `DEBUG`, `DATABASE_URL` handling stays exactly as-is (it is correct today).
- Commit style follows repo history: `feat(scope): ...` / `fix(scope): ...` conventional commits.

## Review Focus

The five failure modes most likely to bite a real user after these changes:

1. **User behind a corporate proxy with a multi-hop XFF chain** — must still be throttled under their *edge-observed* IP (last hop), never their claimed first hop. Pinned by Task 1's `test_rate_limit_keys_on_last_xff_hop`.
2. **Direct non-proxied request (local dev, health checks)** — no XFF at all must fall back cleanly to `X-Real-IP` then `REMOTE_ADDR`, and existing per-IP tests (`REMOTE_ADDR='192.168.1.100'`) must still pass. Pinned by Task 1 keeping all existing tests green.
3. **Legitimate access via the Railway mirror domain** — after tightening `ALLOWED_HOSTS`, `sim-akreditasi-web-production.up.railway.app` must still serve HTTP 200/302 (not 400). Pinned by Task 2's explicit-host test.
4. **A stale/moved dependency breaking the Vercel build after pinning** — pinned versions must be exactly the versions currently resolving (generated from a fresh install, never hand-guessed). Pinned by Task 3's generation procedure.
5. **Rate-limit contract regression (429 JSON vs HTML)** — the throttled response shape must not change for API vs HTML paths. Pinned by re-running the full existing `tests_security.py` suite in every task.

---

### Task 1: Trusted client-IP extraction in the rate limiter (fixes spoofable `X-Forwarded-For` first hop)

**Context:** `akreditasi/security_utils.py` lines 43–44 currently key the rate-limit bucket on `X-Forwarded-For` hop **first**:

```python
xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', 'unknown')
```

A client can send `X-Forwarded-For: <random-ip>` with every brute-force attempt against `POST /accounts/login/` (limit is 8/60s) and rotate a fresh bucket each request. Standard reverse-proxy behavior (Vercel included) *appends* the edge-observed client IP to the end of the chain, so the **last** hop is the only trustworthy one.

**Files:**
- Modify: `akreditasi/security_utils.py` (add helper above `rate_limit`; change 2 lines inside `wrapper`)
- Test: `akreditasi/tests_security.py` (add tests to `RateLimiterTest`)

**Interfaces:**
- Produces: `extract_client_ip(request) -> str` — module-level function in `akreditasi/security_utils.py`. Consumed only by `rate_limit` today; importable for future audit logging.

- [ ] **Step 1: Write the failing tests**

Append inside the existing `RateLimiterTest` class in `akreditasi/tests_security.py`:

```python
    def _view(self):
        calls = {'n': 0}

        @rate_limit(max_calls=3, window=60, scope='ip-test')
        def view(request):
            calls['n'] += 1
            return HttpResponse('ok')

        return view, calls

    def test_rate_limit_keys_on_last_xff_hop(self):
        """Spoofed first-hop XFF entries share one bucket keyed on the edge-observed last hop."""
        view, calls = self._view()
        # 3 requests, each with a DIFFERENT spoofed first hop but the same real last hop
        for spoofed in ['6.6.6.6', '7.7.7.7', '8.8.8.8']:
            request = self.factory.get(
                '/api/test/',
                HTTP_X_FORWARDED_FOR=f'{spoofed}, 36.86.50.10',
                REMOTE_ADDR='10.0.0.1',
            )
            response = view(request)
            self.assertEqual(response.status_code, 200)
        # 4th request with yet another spoofed first hop -> throttled (same last-hop bucket)
        request = self.factory.get(
            '/api/test/',
            HTTP_X_FORWARDED_FOR='9.9.9.9, 36.86.50.10',
            REMOTE_ADDR='10.0.0.1',
        )
        self.assertEqual(view(request).status_code, 429)

    def test_extract_client_ip_fallback_chain(self):
        from akreditasi.security_utils import extract_client_ip
        # multi-hop: last hop wins
        r = self.factory.get('/', HTTP_X_FORWARDED_FOR='6.6.6.6, 36.86.50.10', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(extract_client_ip(r), '36.86.50.10')
        # no XFF: X-Real-IP wins
        r = self.factory.get('/', HTTP_X_REAL_IP='36.86.50.11', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(extract_client_ip(r), '36.86.50.11')
        # neither header: REMOTE_ADDR
        r = self.factory.get('/', REMOTE_ADDR='192.168.1.100')
        self.assertEqual(extract_client_ip(r), '192.168.1.100')
        # empty XFF string: falls through, must not return ''
        r = self.factory.get('/', HTTP_X_FORWARDED_FOR='', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(extract_client_ip(r), '10.0.0.2')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
python manage.py test akreditasi.tests_security.RateLimiterTest -v 2
```

Expected: FAIL — `ImportError: cannot import name 'extract_client_ip'` (or the last-hop test counting 4 buckets and returning 200 on the 4th request).

- [ ] **Step 3: Implement the helper and rewire `rate_limit`**

In `akreditasi/security_utils.py`, add directly above the `rate_limit` decorator function:

```python
def extract_client_ip(request) -> str:
    """
    Return the client IP as observed by the trusted edge proxy.

    Behind Vercel/Railway the edge APPENDS the real client IP to the end of
    X-Forwarded-For, so the LAST hop is the only client-untrusted-proof value.
    Earlier hops are client-supplied and spoofable. Falls back to X-Real-IP,
    then REMOTE_ADDR (direct/non-proxied requests, local dev).
    """
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        hops = [h.strip() for h in xff.split(',') if h.strip()]
        if hops:
            return hops[-1]
    real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()
    if real_ip:
        return real_ip
    return request.META.get('REMOTE_ADDR', 'unknown')
```

Then replace the two lines inside `wrapper` (currently lines 43–44):

```python
            if getattr(request, 'user', None) and request.user.is_authenticated:
                client_key = f"{_RATE_PREFIX}{scope}:u:{request.user.id}"
            else:
                client_key = f"{_RATE_PREFIX}{scope}:ip:{extract_client_ip(request)}"
```

- [ ] **Step 4: Run the full security suite to verify all pass**

```bash
python manage.py test akreditasi.tests_security -v 2
```

Expected: PASS — new tests pass AND all pre-existing tests (`test_rate_limit_allows_under_threshold`, per-IP tests using `REMOTE_ADDR`, header tests, login brute-force tests) stay green.

- [ ] **Step 5: Commit**

```bash
git add akreditasi/security_utils.py akreditasi/tests_security.py
git commit -m "fix(security): rate limiter keys on last XFF hop (edge-observed IP), blocks first-hop spoofing"
```

---

### Task 2: Tighten `ALLOWED_HOSTS` — drop platform-wide wildcards

**Context:** `config/settings.py` lines 26 and 33–38 currently append blanket wildcards:

```python
ALLOWED_HOSTS += ['.onrender.com', '.railway.app', '.pythonanywhere.com', '.vercel.app']
CSRF_TRUSTED_ORIGINS += [
    'https://sim-akreditasi-django.vercel.app',
    'https://*.onrender.com',
    ...
]
```

A wildcard host like `*.vercel.app` means ANY Vercel deployment on the platform could be used for host-header injection (password-reset poisoning via `Host`/`X-Forwarded-Host`, cache poisoning) against this app if the edge ever routes it there. Only the app's actual domains are needed. Env-driven logic (`DJANGO_ALLOWED_HOSTS`, `RENDER_EXTERNAL_HOSTNAME`, `RAILWAY_*`) stays — it only activates when those env vars exist.

**Files:**
- Modify: `config/settings.py` (lines 21–38 region: the `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` static appends)
- Test: `akreditasi/tests_security.py` (new `AllowedHostsTest` class)

**Interfaces:**
- Consumes: nothing from Task 1. Independent.
- Produces: production host allow-list exactly `{localhost, 127.0.0.1, sim-akreditasi-django.vercel.app, sim-akreditasi-web-production.up.railway.app}` plus env-provided hosts.

- [ ] **Step 1: Write the failing test**

Append a new test class at the end of `akreditasi/tests_security.py`:

```python
class AllowedHostsTest(TestCase):
    """A05/A02: foreign Host headers must be rejected with 400 (host-header injection)."""

    def test_foreign_host_rejected(self):
        from django.conf import settings
        self.assertNotIn('.vercel.app', settings.ALLOWED_HOSTS)
        self.assertNotIn('.railway.app', settings.ALLOWED_HOSTS)
        self.assertNotIn('.onrender.com', settings.ALLOWED_HOSTS)
        self.assertNotIn('.pythonanywhere.com', settings.ALLOWED_HOSTS)
        self.assertIn('sim-akreditasi-django.vercel.app', settings.ALLOWED_HOSTS)
        self.assertIn('sim-akreditasi-web-production.up.railway.app', settings.ALLOWED_HOSTS)

    def test_legit_domains_accepted(self):
        for host in ('sim-akreditasi-django.vercel.app',
                     'sim-akreditasi-web-production.up.railway.app'):
            response = self.client.get('/accounts/login/', HTTP_HOST=host, secure=True)
            self.assertNotEqual(response.status_code, 400)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test akreditasi.tests_security.AllowedHostsTest -v 2
```

Expected: FAIL — `assertNotIn('.vercel.app', ...)` trips because the wildcard is currently present.

- [ ] **Step 3: Implement**

In `config/settings.py`, replace line 26:

```python
ALLOWED_HOSTS += ['.onrender.com', '.railway.app', '.pythonanywhere.com', '.vercel.app']
```

with:

```python
# Domain produksi eksplisit — TANPA wildcard platform (host-header injection hardening).
ALLOWED_HOSTS += [
    'sim-akreditasi-django.vercel.app',
    'sim-akreditasi-web-production.up.railway.app',
]
```

Then, inside the `CSRF_TRUSTED_ORIGINS += [...]` block (lines 33–38), remove the `'https://*.onrender.com'` entry and any other platform wildcard origins (`https://*.vercel.app`, `https://*.railway.app` if present), keeping the explicit `'https://sim-akreditasi-django.vercel.app'` line. If a `https://sim-akreditasi-web-production.up.railway.app` origin is not present, add it.

- [ ] **Step 4: Run the full suite to verify all pass**

```bash
python manage.py test akreditasi.tests_security -v 2
```

Expected: PASS — all green.

- [ ] **Step 5: Commit**

```bash
git add config/settings.py akreditasi/tests_security.py
git commit -m "fix(security): explicit ALLOWED_HOSTS/CSRF origins, drop platform wildcards"
```

---

### Task 3: Pin direct dependencies + dependency vulnerability audit (OWASP A03)

**Context:** `requirements.txt` uses open ranges (`django>=5.0,<7.0` etc.). A future `vercel deploy` could silently pull a new major/minor with a known CVE. Pin the **direct** dependencies to the versions that currently resolve, and add a repeatable audit command.

**Files:**
- Modify: `requirements.txt`
- Create: `docs/security/dependency-audit.md` (one-page runbook)
- Test: none (config task) — verification is the audit run + Vercel deploy health check

**Interfaces:**
- Consumes: nothing from Tasks 1–2.
- Produces: fully pinned `requirements.txt`; documented `pip-audit` procedure.

- [ ] **Step 1: Generate exact pins from a fresh resolve**

```bash
cd "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django"
python -m venv .venv-audit
source .venv-audit/Scripts/activate   # git-bash on Windows
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip freeze | grep -iE '^(django|psycopg2-binary|dj-database-url|django-crispy-forms|crispy-bootstrap5|openpyxl|gunicorn|whitenoise|requests|python-decouple|reportlab)=='
```

Expected output: 11 pinned lines, e.g. `Django==5.2.6`, `psycopg2-binary==2.9.10`, ... (exact versions are whatever today's resolver produced — that is the point; do NOT hand-pick versions).

- [ ] **Step 2: Run pip-audit against the resolved set**

```bash
pip install pip-audit -q
pip-audit -r <(pip freeze) 2>/dev/null || pip freeze > .audit-freeze.txt && pip-audit -r .audit-freeze.txt
rm -f .audit-freeze.txt
```

Expected: either `No known vulnerabilities found`, or a short list of CVEs — if any HIGH/CRITICAL appears in a *direct* dependency, choose the lowest minor/patch bump that clears it and use THAT version in Step 3 instead of the frozen one; document the override in the runbook.

- [ ] **Step 3: Overwrite `requirements.txt` with the pinned set**

Replace the entire content of `requirements.txt` with the pinned lines from Step 1 (keep the same 11 package names, `==` instead of `>=`), plus a header comment:

```
# Pinned direct dependencies — security hardening 2026-10-14 (OWASP A03).
# Regenerate via: pip freeze | grep -iE '^(django|psycopg2-binary|...)=='
```

- [ ] **Step 4: Write the runbook**

Create `docs/security/dependency-audit.md` documenting: the exact audit command from Step 2, the cadence (run before every deploy; weekly is acceptable), the upgrade procedure (bump pin → run test suite → deploy), and any CVE override decisions from Step 2.

- [ ] **Step 5: Verify install from pins works cleanly**

```bash
deactivate
rm -rf .venv-audit
python -m venv .venv-verify
source .venv-verify/Scripts/activate
pip install -r requirements.txt -q && python -c "import django; print(django.get_version())"
deactivate && rm -rf .venv-verify
```

Expected: installs with no dependency-resolution errors; prints the pinned Django version.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt docs/security/dependency-audit.md
git commit -m "fix(security): pin direct dependencies, add pip-audit runbook (A03)"
```

---

### Task 4: Deploy and verify against production

**Files:**
- None modified (verification only).

**Interfaces:**
- Consumes: all three prior tasks committed to `main`.

- [ ] **Step 1: Push and watch the Vercel build**

```bash
git push origin main
```

Vercel auto-deploys from the connected repo (Python 3.12 runtime, region icn1). Wait for "Ready" in the Vercel dashboard.

- [ ] **Step 2: Production smoke checks (non-destructive)**

```bash
T="https://sim-akreditasi-django.vercel.app"
# App serves normally
curl -s -o /dev/null -w "root: %{http_code}\n" "$T"
# Foreign Host still routed correctly by Vercel (App Router handles Host) — app must NOT 400 for its own domains
curl -s -o /dev/null -w "login: %{http_code}\n" "$T/accounts/login/"
# Rate limiter live check: 10 rapid logins with random XFF first hops should all still return
# 200 (login page) until the EDGE-OBSERVED bucket fills, then 429 — same bucket regardless of spoofing
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "attempt $i -> %{http_code}\n" -X POST "$T/accounts/login/" \
    -H "X-Forwarded-For: $((RANDOM)).$((RANDOM)).$((RANDOM)).$((RANDOM))" \
    -d "username=smoke_probe_x&password=WrongPass"
done
```

Expected: after ~8 rapid attempts, HTTP 429 — **even though every attempt used a different spoofed XFF first hop** (this is the Task 1 fix proven live). Note: the live test may also return 403 (CSRF) uniformly; in that case the earlier CSRF-blocked behavior means the limiter is exercised only after a valid token fetch — acceptable, report what you see. Do NOT hammer more than 15 requests total.

- [ ] **Step 3: Verify Railway mirror still serves**

```bash
curl -s -o /dev/null -w "railway: %{http_code}\n" "https://sim-akreditasi-web-production.up.railway.app/"
```

Expected: 200/302 (not 400). If 400, Task 2's allow-list missed the actual Railway domain — check the real domain in the Railway dashboard and re-add explicitly.

- [ ] **Step 4: Record results**

Append a short "2026-10-14 hardening verification" section to `docs/security/dependency-audit.md` with the smoke-check outputs above.

- [ ] **Step 5: Commit the verification note**

```bash
git add docs/security/dependency-audit.md
git commit -m "docs(security): record post-hardening production verification"
git push origin main
```

---

## Accepted Risks (documented, NOT in scope of this plan)

- **In-memory rate-limit fallback is per-process** — on Vercel serverless each lambda instance has its own `_rate_store_fallback`, so the fallback path is best-effort only. The primary path is `DatabaseCache` (Supabase Postgres) and works cross-instance. Acceptable.
- **`RENDER_EXTERNAL_HOSTNAME` env-driven allow-list logic** kept as-is — it only activates if that env var exists; removing it is cosmetic.
- **Single-entry spoofed XFF in local dev** — with no edge proxy, a locally supplied XFF single entry is honored. Dev-only, no production exposure.

## Self-Review

- Spec coverage: finding #1 (spoofable IP) → Task 1; finding #3 (wildcard hosts) → Task 2; finding #4 (unpinned deps) → Task 3; production proof → Task 4. Finding #2 was re-classified during planning as *correct behavior with a documented limitation* (Accepted Risks), not a bug. Finding #5 (info-level) → no action required, noted.
- Placeholder scan: none — every code step carries its full content; version pins in Task 3 are deliberately generated at execution time (documented procedure, not a guess).
- Type consistency: `extract_client_ip(request) -> str` defined in Task 1, referenced only there and in tests; no cross-task interfaces to drift.
- Review Focus: all five failure modes have pinning tests — items 1, 2 in Task 1; item 3 in Task 2 (legit-domains test) and Task 4 Step 3; item 4 in Task 3 Steps 1/5; item 5 in every task's full-suite run plus Task 4 Step 2.
