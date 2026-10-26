# Integrated Control: branded gradient workspace and direct module access

> Execution mode: implement in small TDD increments. This document is a plan, not authorization to change production, push, or deploy. All commands below are for the implementation phase. Planning performed read-only repository inspection and wrote only this document.

## Goal

Redesign ARIMA Integrated Control as a professional navy–indigo gradient workspace with prominent, permission-aware links directly into the existing operational modules.

## Current context / assumptions

- Workspace: `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`; Django with server-rendered templates. At inspection, `master` points to `a3dbb5b`; recheck before execution.
- The working tree contains unrelated modified seed commands and untracked STARKES, HC, QA, fixture, and template work. Do not stash, delete, stage, format, or commit those files. Do not use `git add .` or `git add -A`.
- Live entry point: `https://sim-akreditasi-django.vercel.app/control/`. Anonymous retrieval exposes the authentication page, not the authenticated dashboard. This plan is grounded in the repository; it does not claim a completed authenticated production visual audit.
- Routes are already implemented in `akreditasi/urls.py`: `kontrol_hub`, `kontrol_risiko`, `kontrol_emr`, `kontrol_dokumen`, and `kontrol_layanan`. The first three dashboard destinations are accompanied by a conditional Human Capital card targeting `sdm:dashboard`.
- `akreditasi/kontrol_views.py` owns `SUBDASHBOARDS`, `_common_context`, `_resolve_unit`, `_can_view_human_capital`, and the five page views. Keep `_resolve_unit` as the authority for the selected unit; never build links using an unchecked `request.GET['unit']`. Portal metadata uses `url_name`, and the HC key is exactly `human_capital`.
- `templates/akreditasi/kontrol/base_kontrol.html` is a standalone shell, not `templates/base.html`. It currently has a dark decorative backdrop, a hospital illustration, and global application navigation. Do not add the main application sidebar to this shell.
- `static/css/kontrol.css` owns existing chart, matrix, table, and layout primitives. `static/css/v3-tokens.css` establishes the actual application brand: navy `#14213D`, indigo `#4F5BD5`, stronger indigo `#37429E`, and violet tint `#F0EDFF`; Inter and Manrope are already self-hosted.
- Existing document/risk drill-downs mostly sit near the bottom. EMR intentionally removed an indiscriminate generic module strip. Keep that protection: new shortcuts must be contextual, not a resurrection of the old generic strip.
- Relevant tests: `akreditasi/tests_kontrol_dasbor.py`, `akreditasi/tests_kontrol_render.py`, and `akreditasi/tests_layanan_unit.py`. The first contains a warm-cache query ceiling of 12. Preserve that ceiling. The render test currently depends on seeded users and must become self-contained.
- Preserve the formal existing portal titles, displayed metrics, null-versus-zero semantics, clinical unit mapping, AI endpoint contract, cache behavior, and access restrictions. This is a presentation/navigation change, not a schema or analytics project.
- Human Capital scope: retain its authorized card and link to its existing workspace; do not redesign the entire HC application or invent `/control/hc/`.
- New visible interface strings below are intentional Indonesian literals. The implementation instructions are English; do not translate existing application copy or change the literal labels accidentally.

## Proposed approach

Keep Django views and the snapshot layer, add one small pure navigation builder, and share navigation/header/action partials across the control pages. Use a scoped presentation stylesheet after the existing control stylesheet so chart primitives remain intact, with a white data surface and restrained brand gradient in the masthead rather than a new UI framework. Existing named routes remain the integration boundary: normal same-tab anchors open modules directly, without an intermediate application home page, iframe, SPA router, or new redirect endpoint.

### Non-negotiable visual specification

| Element | Required implementation |
|---|---|
| Page background | Light neutral with a subtle lavender-to-neutral linear gradient; no dark full-screen scene. |
| Masthead | `linear-gradient(112deg, #14213D 0%, #27366B 55%, #37429E 100%)`; white title, muted white supporting text. |
| Data surfaces | White, `#E2E7F0` borders, one restrained shadow, 14–16px radius. Never glassmorphism or neon borders. |
| Typography | Self-hosted Inter for body, Manrope for headings; body 14–15px, portal headings 28–34px, hub title at most 40px, metric values 28px with tabular numerals. |
| Grid | 1200px maximum content width; hub two columns at desktop even when HC is visible, one column at <=767px. Four cards must not become cramped four-column tiles. |
| Spacing | 8px rhythm; desktop page gutter 32px, mobile 16px; section gaps 24px; card padding 24px, mobile 20px. |
| Interaction | At least 44px-high actionable controls, visible keyboard focus, descriptive text labels; 120ms hover transition, no entrance animation or animated counters. |
| Semantics | Indigo for navigation. Green/amber/red only for real status or risk meaning. Do not change risk-matrix severity colors into brand colors. |
| Imagery | Remove the decorative hospital SVG, orbs, generated skyline, oversized decorative icons, and hover glows. Keep the real ARIMA brand and small Bootstrap Icons. |
| Content | One main heading per page, one primary module link, optional secondary links, one unit selector, compact update metadata, and real existing metrics. No invented badges, statistics, or marketing claims. |
| AI panel | Keep existing functionality and selectors; make it visually secondary, after operational data. Do not add AI copy, new prompts, or automatic AI requests. |

### Screen structure

```text
ARIMA / Integrated Control                     application link / user
Hub | Risk | EMR | Documents | Human Capital (authorized only)

[Branded gradient masthead]
Page title and concise existing subtitle             Active unit selector

[Module access toolbar, subpages only]
Primary direct module link | related direct links    scope labels

[Existing KPI strip]
[Existing charts / matrix / clinical data / evidence]
[Existing unit services block and restrained AI panel]
```

On the hub, replace the action toolbar with the existing unit overview and a two-column portal-card grid. Keep the formal portal names so existing business naming and tests do not drift. Each card has one clear affordance; do not nest an anchor or button inside its existing card anchor.

### Verified navigation contracts

| Control page | Direct destination | Supported query/context | Visibility / scope |
|---|---|---|---|
| Risk | `akreditasi:risiko_daftar` | `unit=<resolved unit.pk>` | Primary; selected-unit filter supported. |
| Risk | `akreditasi:risiko_monev` | `unit=<resolved unit.pk>&tahun=<snapshot year>` | Unit and year supported; use the snapshot year, not a new year picker. |
| Risk | `akreditasi:risiko_fmea_rca` | `unit=<resolved unit.pk>` | Selected-unit filter supported. |
| Risk | `akreditasi:insiden_daftar` | `unit=<resolved unit.pk>` | Selected-unit filter supported. |
| Risk | `akreditasi:indikator_dashboard` | `tahun=<snapshot year>` | Do not append `unit`; route has no selected-unit query contract. Mark scope as role-based. |
| Documents | `akreditasi:dokumen_hub` | None | Primary. Existing application scope; do not claim a selected-unit filter. |
| Documents | `akreditasi:rekap` | None | Only when `_is_manager_role(request.user)` is true; route redirects other roles. |
| Documents | `akreditasi:laporan_mutu_daftar` | `tahun=<snapshot year>` | Existing profile-based scope; no invented `unit` filter. |
| EMR, mapped outpatient leaf | `pasien:rajal_dashboard` | `poli=<POLIKLINIK_CHOICES label>` | Require `rajal` in the actual profile module set; derive choice through `POLI_UNIT_CODE`. |
| EMR, IGD | `pasien:igd_dashboard` | None | Require module `igd`; explicitly label hospital/IGD scope rather than pretending it accepts `unit`. |
| EMR, bed-owning unit | `pasien:bed_management` | None | Require module `ranap` and `snapshot.layanan.owns_beds`; explicitly mark hospital-wide scope. |
| EMR, unmapped/no eligible module | No fabricated destination | None | Render an explanation, not a misleading all-hospital patient link or a disabled fake button. The unit services page remains available. |
| Human Capital card / tab | `sdm:dashboard` | Retain the current no-query destination | Gate with `_can_view_human_capital`; leave HC's own grant-based scope resolution intact. |

Do not copy target-page permission logic into a new role table. Reuse `_is_manager_role`, `get_allowed_patient_modules`, and the existing HC visibility predicate. Shortcut visibility does not replace target-page authorization.

## Step-by-step implementation tasks

Each numbered task is intended as a 2–5 minute focused increment using the supplied code. Run the named RED check before its production change and GREEN check after it. Commit checkpoints group adjacent increments only after their combined tests pass; never commit failing intermediate states.

### 1. Establish an isolated UI test harness

Files: new `config/control_test_settings.py`; edit `akreditasi/tests_kontrol_render.py`.

1. Inspect `git status --short` and `git branch --show-current`; record unrelated paths and do not stage them.
2. Create the test-only settings below first, then run the existing render test before changing its fixture setup: `DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_render --verbosity 2`. Its seed-dependent setup can fail or skip coverage on the empty database; record that RED result rather than relying on existing local users.
3. These settings must never become the production `DJANGO_SETTINGS_MODULE`.

```python
# config/control_test_settings.py
from .settings import *

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
}}
MIGRATION_MODULES = {
    'accounts': None,
    'akreditasi': None,
    'pasien': None,
    'sdm': None,
}
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'control-workspace-tests',
}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
```

4. In `akreditasi/tests_kontrol_render.py`, import `UnitKerja` and replace only `KontrolRenderTest.setUpTestData` with this implementation; retain the three existing test methods.

```python
@classmethod
def setUpTestData(cls):
    User = get_user_model()
    unit = UnitKerja.objects.create(
        code='KTRL-RENDER', name='Control render fixture',
        level=2, is_active=True,
    )
    cls.users = {}
    for role, _label in UserProfile.ROLE_CHOICES:
        user = User.objects.create_user(username='control-render-' + role.lower())
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        cls.users[role] = user
    cls.superuser = User.objects.create_superuser(
        username='control-render-superuser', email='control-render@example.test',
    )
    UserProfile.objects.create(
        user=cls.superuser, role='SUPER_ADMIN', unit_kerja=unit,
    )
```

5. The superuser has an unusable password; tests use `force_login`, not a real login credential.

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_render akreditasi.tests_kontrol_dasbor akreditasi.tests_layanan_unit --verbosity 1
```

Expected: `OK`, no seed-dependent skipped subdashboard coverage. If the isolated baseline has unrelated failures, identify the exact failure and stop before presenting later GREEN results as a complete application gate. Migration-disabled tests demonstrate UI behavior, not migration readiness.

### 2. Add the pure operational-link builder: risk and documents

Files: new `akreditasi/kontrol_navigation.py`; new `akreditasi/tests_kontrol_navigation.py`.

Write these tests first. The function imports stay inside methods so the first RED is a missing feature, not an unrelated module collection failure.

```python
# akreditasi/tests_kontrol_navigation.py
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase
from django.urls import reverse


class ModuleActionsTest(SimpleTestCase):
    def setUp(self):
        self.unit = SimpleNamespace(pk=71, code='POLI-PD')

    def actions(self, portal, **kwargs):
        from akreditasi.kontrol_navigation import module_actions
        return module_actions(portal, unit=self.unit, year=2026, **kwargs)

    def test_risk_preserves_resolved_unit(self):
        action = self.actions('risiko')[0]
        self.assertEqual(urlsplit(action['href']).path,
                         reverse('akreditasi:risiko_daftar'))
        self.assertEqual(parse_qs(urlsplit(action['href']).query), {'unit': ['71']})

    def test_monev_preserves_year_and_unit(self):
        action = next(a for a in self.actions('risiko') if a['key'] == 'monev')
        self.assertEqual(parse_qs(urlsplit(action['href']).query),
                         {'unit': ['71'], 'tahun': ['2026']})

    def test_rekap_requires_manager(self):
        self.assertNotIn('rekap', [a['key'] for a in self.actions('dokumen')])
        self.assertIn('rekap', [a['key'] for a in
                              self.actions('dokumen', is_manager=True)])

    def test_no_fake_unit_filter_on_documents(self):
        self.assertEqual(self.actions('dokumen')[0]['href'],
                         reverse('akreditasi:dokumen_hub'))

    def test_no_unit_means_no_actions(self):
        from akreditasi.kontrol_navigation import module_actions
        self.assertEqual(module_actions('risiko', unit=None, year=2026), [])

    def test_unknown_portal_has_no_actions(self):
        self.assertEqual(self.actions('unknown'), [])
```

RED/GREEN command:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation --verbosity 2
```

RED: import/feature failure. Implement this complete starting module, then expect all six tests to pass:

```python
# akreditasi/kontrol_navigation.py
from urllib.parse import urlencode

from django.urls import reverse


def _action(key, label, route, *, scope, **query):
    href = reverse(route)
    if query:
        href += '?' + urlencode(query)
    return {'key': key, 'label': label, 'href': href, 'scope': scope}


def module_actions(portal, *, unit, year, is_manager=False,
                   allowed_patient_modules=None, layanan=None):
    if unit is None:
        return []
    if portal == 'risiko':
        return [
            _action('risiko', 'Buka daftar risiko', 'akreditasi:risiko_daftar',
                    scope='Unit aktif', unit=unit.pk),
            _action('monev', 'Monitoring dan evaluasi', 'akreditasi:risiko_monev',
                    scope='Unit aktif', unit=unit.pk, tahun=year),
            _action('fmea', 'FMEA / RCA', 'akreditasi:risiko_fmea_rca',
                    scope='Unit aktif', unit=unit.pk),
            _action('insiden', 'Laporan insiden', 'akreditasi:insiden_daftar',
                    scope='Unit aktif', unit=unit.pk),
            _action('indikator', 'Indikator mutu', 'akreditasi:indikator_dashboard',
                    scope='Sesuai akses', tahun=year),
            _action('laporan', 'Laporan mutu', 'akreditasi:laporan_mutu_daftar',
                    scope='Sesuai akses', tahun=year),
        ]
    if portal == 'dokumen':
        actions = [
            _action('dokumen', 'Buka dokumen akreditasi', 'akreditasi:dokumen_hub',
                    scope='Sesuai akses'),
        ]
        if is_manager:
            actions.append(_action('rekap', 'Rekap dan scoring', 'akreditasi:rekap',
                                   scope='Sesuai akses'))
        actions.append(_action('laporan', 'Laporan mutu', 'akreditasi:laporan_mutu_daftar',
                               scope='Sesuai akses', tahun=year))
        return actions
    return []
```

### 3. Add eligible clinical actions without restoring generic shortcuts

Files: `akreditasi/kontrol_navigation.py`, `akreditasi/tests_kontrol_navigation.py`, `akreditasi/tests_layanan_unit.py`.

1. Add these methods to `ModuleActionsTest` and run the same command. RED: the EMR list is empty.

```python
def test_outpatient_uses_canonical_choice_label(self):
    actions = self.actions('emr', allowed_patient_modules={'rajal'})
    self.assertEqual(len(actions), 1)
    self.assertEqual(urlsplit(actions[0]['href']).path,
                     reverse('pasien:rajal_dashboard'))
    self.assertEqual(parse_qs(urlsplit(actions[0]['href']).query),
                     {'poli': ['Poli Penyakit Dalam (Interna)']})

def test_igd_requires_igd_module(self):
    self.unit.code = 'IGD'
    self.assertEqual(self.actions('emr', allowed_patient_modules={'rajal'}), [])
    actions = self.actions('emr', allowed_patient_modules={'igd'})
    self.assertEqual(actions[0]['href'], reverse('pasien:igd_dashboard'))

def test_beds_require_ownership_and_ranap_permission(self):
    self.unit.code = 'BANGSAL-DEWASA'
    self.assertEqual(self.actions('emr', allowed_patient_modules={'ranap'},
                                  layanan={'owns_beds': False}), [])
    actions = self.actions('emr', allowed_patient_modules={'ranap'},
                           layanan={'owns_beds': True})
    self.assertEqual(actions[0]['href'], reverse('pasien:bed_management'))
    self.assertEqual(actions[0]['scope'], 'Seluruh RS')

def test_unmapped_unit_has_no_generic_patient_shortcuts(self):
    self.unit.code = 'KOMITE-MUTU'
    self.assertEqual(self.actions('emr', allowed_patient_modules={'rajal', 'igd', 'ranap'},
                                  layanan={'owns_beds': False}), [])

def test_outpatient_without_permission_has_no_action(self):
    self.assertEqual(self.actions('emr', allowed_patient_modules=set()), [])
```

2. Add this branch immediately before the final `return []` of `module_actions`. The dictionaries and choices are existing public source data, not new unit-name heuristics. This builder executes no database query.

```python
    if portal == 'emr':
        from pasien.models import POLIKLINIK_CHOICES
        from .layanan_unit import POLI_UNIT_CODE

        allowed = set(allowed_patient_modules or ())
        layanan = layanan or {}
        choices = dict(POLIKLINIK_CHOICES)
        actions = []
        if 'rajal' in allowed:
            for choice, code in POLI_UNIT_CODE.items():
                if code and code == unit.code:
                    actions.append(_action(
                        'rajal', 'Buka poli', 'pasien:rajal_dashboard',
                        scope='Poli aktif', poli=choices[choice],
                    ))
                    break
        if unit.code == 'IGD' and 'igd' in allowed:
            actions.append(_action('igd', 'Buka IGD', 'pasien:igd_dashboard',
                                   scope='IGD RS'))
        if layanan.get('owns_beds') and 'ranap' in allowed:
            actions.append(_action('beds', 'Manajemen tempat tidur',
                                   'pasien:bed_management', scope='Seluruh RS'))
        return actions
```

3. Keep `LayananBlockTemplateTest.test_generic_strip_is_gone` in `akreditasi/tests_layanan_unit.py`. New labels intentionally do not recreate its forbidden generic strip or indiscriminate clinical links. Add an integration assertion later proving the eligible `Buka poli` action is rendered instead. Do not remove that regression wholesale.
4. GREEN: all 11 navigation tests pass; existing layanan tests remain green.

Checkpoint A, after Tasks 1–3 pass:

```bash
git add -- config/control_test_settings.py akreditasi/tests_kontrol_render.py akreditasi/kontrol_navigation.py akreditasi/tests_kontrol_navigation.py
git diff --cached --check && git diff --cached --stat
git commit -m "feat(control): define contextual operational shortcuts"
```

### 4. Bind filtered navigation and actions to the resolved request context

Files: `akreditasi/kontrol_navigation.py`, `akreditasi/kontrol_views.py`, new `akreditasi/tests_kontrol_workspace.py`.

1. Write the integration tests below first. RED must identify missing context/toolbar, not authentication or missing fixture data.

```python
# akreditasi/tests_kontrol_workspace.py
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.models import UnitKerja


class ControlWorkspaceTest(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = UnitKerja.objects.create(
            code='POLI-PD', name='Poliklinik Penyakit Dalam',
            level=3, is_active=True,
        )
        self.other = UnitKerja.objects.create(
            code='KTRL-OTHER', name='Other unit', level=3, is_active=True,
        )
        self.user = get_user_model().objects.create_user(username='control-workspace')
        UserProfile.objects.create(
            user=self.user, role='KEPALA_UNIT', unit_kerja=self.unit,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def test_navigation_uses_resolved_unit_not_untrusted_query(self):
        res = self.client.get(reverse('akreditasi:kontrol_risiko'),
                              {'unit': self.other.pk})
        self.assertEqual(res.status_code, 200)
        for item in res.context['portal_navigation']:
            self.assertNotIn('unit=' + str(self.other.pk), item['href'])
        self.assertIn('unit=' + str(self.unit.pk),
                      res.context['module_actions'][0]['href'])

    def test_human_capital_is_not_advertised_without_permission(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertNotIn('human_capital', [item['key'] for item in res.context['portal_navigation']])

    def test_emr_links_directly_to_eligible_poli(self):
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertContains(res, 'Buka poli')
        self.assertContains(res, reverse('pasien:rajal_dashboard'))

    def test_risk_has_one_primary_direct_module_action_above_kpis(self):
        body = self.client.get(reverse('akreditasi:kontrol_risiko')).content.decode()
        self.assertIn('data-module-primary', body)
        self.assertLess(body.index('data-module-primary'), body.index('kontrol-kpis'))

    def test_layanan_page_retains_control_navigation(self):
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertContains(res, 'aria-label="Navigasi Integrated Control"')

    def test_light_workspace_stylesheet_and_main_landmark(self):
        res = self.client.get(reverse('akreditasi:kontrol_hub'))
        self.assertContains(res, 'kontrol-workspace.css')
        self.assertContains(res, 'id="kontrol-main"')
        self.assertNotContains(res, 'kontrol-backdrop')
```

2. Add this complete helper to `akreditasi/kontrol_navigation.py`:

```python
def portal_navigation(portals, *, unit, active_portal, can_view_hc):
    items = []
    labels = {'risiko': 'Risiko', 'emr': 'EMR', 'dokumen': 'Dokumen',
              'human_capital': 'Human Capital'}
    hub = reverse('akreditasi:kontrol_hub')
    suffix = '?' + urlencode({'unit': unit.pk}) if unit is not None else ''
    items.append({'key': 'hub', 'label': 'Ringkasan', 'href': hub + suffix,
                  'active': active_portal == 'hub'})
    for portal in portals:
        if portal['key'] == 'human_capital' and not can_view_hc:
            continue
        href = reverse(portal['url_name'])
        if portal['key'] != 'human_capital':
            href += suffix
        items.append({'key': portal['key'], 'label': labels[portal['key']],
                      'href': href, 'active': active_portal == portal['key']})
    return items
```

3. In `akreditasi/kontrol_views.py`, import the two navigation builders. The current `_common_context(request, unit, profile)` does not receive a snapshot or portal key. Replace that function with the complete implementation below, then update its callers exactly as listed. This passes the already-built snapshot rather than generating it twice.

```python
from .kontrol_navigation import module_actions, portal_navigation
```

```python
def _common_context(request, unit, profile, *, snapshot=None, active_portal='hub'):
    from django.utils import timezone
    from .views import _is_manager_role

    units = list(sample_units(12))
    if profile is not None and profile.is_unit_scoped and profile.unit_kerja:
        units = [profile.unit_kerja]
    elif unit and unit not in units:
        units = [unit] + units
    can_view_hc = _can_view_human_capital(request.user)
    allowed = (profile.get_allowed_patient_modules()
               if profile and active_portal == 'emr' else set())
    year = snapshot['year'] if snapshot else timezone.localdate().year
    return {
        'unit': unit,
        'unit_options': units,
        'profile': profile,
        'subdashboards': SUBDASHBOARDS,
        'is_unit_scoped': bool(profile and profile.is_unit_scoped),
        'can_view_hc': can_view_hc,
        'active_portal': active_portal,
        'portal_navigation': portal_navigation(
            SUBDASHBOARDS, unit=unit, active_portal=active_portal,
            can_view_hc=can_view_hc,
        ),
        'module_actions': module_actions(
            active_portal, unit=unit, year=year,
            is_manager=_is_manager_role(request.user),
            allowed_patient_modules=allowed,
            layanan=snapshot.get('layanan', {}) if snapshot else {},
        ),
        'portal_meta': next((p for p in SUBDASHBOARDS
                             if p['key'] == active_portal), None),
    }
```

Update every caller as follows:

- In `kontrol_hub`, immediately after its existing `snapshot = ...` assignment, add `ctx = _common_context(request, unit, profile, snapshot=snapshot, active_portal='hub')`. In its card loop, replace `not _can_view_human_capital(request.user)` with `not ctx['can_view_hc']`. Replace `**_common_context(request, unit, profile)` in its render dictionary with `**ctx`; preserve every existing metrics/card calculation.
- Replace `_briefing` with the complete function below. Change `_portal` to call `_briefing(request, unit, profile, portal_key)`; remove its now-redundant `ctx['active_portal'] = portal_key` assignment.
- In `kontrol_layanan`, replace its context call with `_common_context(request, unit, profile, snapshot=snapshot, active_portal='layanan')`; remove the later `'active_portal': 'emr'` dictionary member so the standalone services page does not falsely highlight the EMR tab. Preserve all date/status filtering.

```python
def _briefing(request, unit, profile, portal_key):
    snapshot = snapshot_cached(unit, profile) if unit else None
    return {
        **_common_context(request, unit, profile, snapshot=snapshot,
                          active_portal=portal_key),
        'snapshot': snapshot,
    }
```

4. Do not evaluate patient-module permissions on risk/document/hub requests. HC visibility must not be looked up separately for every navigation item. Do not cache personalized navigation in a shared non-user cache.
5. Run the context-only tests first; the markup assertions remain RED until Tasks 5–6. Keep these dependent increments uncommitted until all workspace tests pass.

### 5. Introduce shared navigation and action partials

Files: new `templates/akreditasi/kontrol/_portal_nav.html`, `_module_actions.html`, `_portal_header.html`; edit `templates/akreditasi/kontrol/base_kontrol.html`, `risiko.html`, `emr.html`, `dokumen.html`, `layanan.html`.

Use this complete navigation partial:

```django
<nav class="kontrol-portal-nav" aria-label="Navigasi Integrated Control">
  {% for item in portal_navigation %}
    <a href="{{ item.href }}"{% if item.active %} aria-current="page"{% endif %}>
      {{ item.label }}
    </a>
  {% endfor %}
</nav>
```

Use this complete actions partial:

```django
{% if unit %}
<section class="kontrol-module-access" aria-label="Akses modul operasional">
  <div class="kontrol-module-access-label">Akses modul</div>
  {% if module_actions %}
  <div class="kontrol-module-actions">
    {% for action in module_actions %}
    <a href="{{ action.href }}" class="kontrol-module-link{% if forloop.first %} is-primary{% endif %}"
       {% if forloop.first %}data-module-primary{% endif %}>
      <span>{{ action.label }}</span><small>{{ action.scope }}</small>
      <i class="bi bi-arrow-up-right" aria-hidden="true"></i>
    </a>
    {% endfor %}
  </div>
  {% else %}
  <p class="kontrol-note">Tidak ada pintasan operasional untuk akses dan unit ini.</p>
  {% endif %}
</section>
{% endif %}
```

Use this complete common header partial:

```django
<header class="kontrol-header">
  <div class="kontrol-header-main">
    <p class="kontrol-eyebrow">Integrated Control</p>
    <h1 class="kontrol-title kontrol-title-sm">{{ portal_meta.title }}</h1>
    <p class="kontrol-lead">{{ portal_meta.subtitle }}</p>
  </div>
  {% include 'akreditasi/kontrol/_unit_switch.html' %}
</header>
{% include 'akreditasi/kontrol/_module_actions.html' %}
```

Integration instructions:

1. Add `kontrol-workspace` to the existing body class, retaining `kontrol-body`.
2. Add the new stylesheet immediately after the existing `kontrol.css` link, using `{% static 'css/kontrol-workspace.css' %}`. Remove only the Google Fonts/preconnect links used by the control shell; do not remove Bootstrap or Bootstrap Icons in this task.
3. Remove the entire `kontrol-backdrop` decorative block, including its SVG and glow elements. Do not hide it with opacity and leave dead decoration in the DOM.
4. Add a skip link before the shell: `<a class="kontrol-skip-link" href="#kontrol-main">Lewati ke konten</a>`.
5. Change the existing `<main class="kontrol-main">` to `<main class="kontrol-main" id="kontrol-main" tabindex="-1">`. Include `_portal_nav.html` immediately inside it, before the messages and content blocks. Do not add a second main wrapper; there is no existing `kontrol-shell` element.
6. In `risiko.html`, `emr.html`, and `dokumen.html`, replace only the opening page header section with `_portal_header.html`; leave KPI/data blocks intact. Remove the old bottom drill-down strips now represented by the top toolbar; preserve the AI include and unit-services include.
7. In `risiko.html`, fix the mismatched closing tag immediately after the risk-matrix/proxy grid: the element opened as `<div class="kontrol-grid-2">` at current line 42 must close with `</div>`, not the `</section>` at current line 113. Verify the matrix and following panels are siblings in the DOM.
8. In `layanan.html`, keep its unit-service heading, table, pagination/limits, and existing return link. The base now supplies portal tabs, making direct switching available without returning through the application home.
9. Add an integration test verifying HC appears in the shared navigation when both the role capability and active HcGrant exist; reuse the exact grant/config arrangement in `KontrolHubTest.test_hub_menampilkan_kartu_human_capital_bagi_pengguna_berizin`, not a monkeypatched always-true guard.

GREEN check:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_dasbor akreditasi.tests_layanan_unit --verbosity 1
```

At this point only the new stylesheet assertion is expected to remain RED until Task 6 creates the stylesheet. Do not commit a nonexistent asset reference.

### 6. Apply the complete scoped workspace stylesheet

Files: new `static/css/kontrol-workspace.css`; new `akreditasi/tests_kontrol_workspace_style.py`.

Write these tests before adding the stylesheet:

```python
from django.conf import settings
from django.test import SimpleTestCase


class ControlWorkspaceStyleTest(SimpleTestCase):
    def test_brand_and_accessibility_contract(self):
        css = (settings.BASE_DIR / 'static/css/kontrol-workspace.css').read_text(
            encoding='utf-8')
        for required in ('#14213D', '#4F5BD5', '#37429E',
                         ':focus-visible', 'prefers-reduced-motion',
                         '@media print', 'inter-latin.woff2', 'manrope-latin.woff2'):
            with self.subTest(required=required):
                self.assertIn(required, css)
        self.assertNotIn('backdrop-filter', css)
        self.assertNotIn('!important', css)
        self.assertNotIn('fonts.googleapis.com', css)
```

RED/GREEN command:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_workspace --verbosity 2
```

Create the following full stylesheet. It intentionally acts as the opt-in presentation layer over existing chart/layout primitives; do not also append a second override block to `kontrol.css` or import the global `v3-tokens.css` into this standalone shell.

```css
@font-face {
  font-family: 'Inter'; font-style: normal; font-weight: 100 900;
  font-display: swap; src: url('../fonts/inter-latin.woff2') format('woff2');
}
@font-face {
  font-family: 'Manrope'; font-style: normal; font-weight: 200 800;
  font-display: swap; src: url('../fonts/manrope-latin.woff2') format('woff2');
}
body.kontrol-workspace {
  --k-bg: #F6F8FC; --k-panel: #FFFFFF; --k-panel-2: #F0F3F9;
  --k-panel-solid: #FFFFFF; --k-line: #E2E7F0; --k-line-strong: #B8C2D5;
  --k-border: #E2E7F0; --k-text: #17223B; --k-muted: #52617A;
  --k-dim: #52617A; --k-good: #0F766E; --k-watch: #A15C06; --k-critical: #B42318;
  --k-cyan: #4F5BD5; --k-blue: #4F5BD5; --k-violet: #37429E;
  --k-green: #0F766E; --k-amber: #A15C06; --k-red: #B42318;
  --k-shadow: 0 4px 16px rgb(20 33 61 / 5%);
  --k-radius: 16px; --k-radius-sm: 10px;
  color: var(--k-text); font: 15px/1.55 'Inter', sans-serif;
  background: linear-gradient(160deg, #F0EDFF 0, #F6F8FC 520px);
  min-height: 100vh;
}
.kontrol-workspace * { box-sizing: border-box; }
.kontrol-workspace .kontrol-main {
  width: min(100%, 1264px); max-width: 1264px; margin: 0 auto; padding: 24px 32px 40px;
}
.kontrol-workspace :is(h1, h2, h3) { font-family: 'Manrope', sans-serif; }
.kontrol-workspace .kontrol-topbar {
  width: min(calc(100% - 64px), 1200px); margin: 24px auto 0;
  background: #FFFFFF; border: 1px solid var(--k-border); border-radius: 16px;
  color: var(--k-text); padding: 16px 20px; box-shadow: var(--k-shadow); gap: 16px;
}
.kontrol-workspace :is(.kontrol-brand strong, .kontrol-user) { color: var(--k-text); }
.kontrol-workspace :is(.kontrol-brand small, .kontrol-note,
  .kpi-label, .kpi-foot, .quick-label, .bar-label) { color: var(--k-muted); }
.kontrol-workspace :is(.brand-mark, .portal-icon) {
  background: #F0EDFF; color: #37429E; border: 1px solid #E4E7FA;
  box-shadow: none;
}
.kontrol-workspace .brand-mark { background-image: none; }
.kontrol-workspace :is(.kontrol-hero, .kontrol-header, .kontrol-subhead) {
  background: linear-gradient(112deg, #14213D 0%, #27366B 55%, #37429E 100%);
  border: 1px solid #27366B; border-radius: 16px; padding: 28px;
  gap: 24px; margin: 0 0 24px; color: #FFFFFF;
}
.kontrol-workspace .kontrol-title {
  font-size: clamp(28px, 3vw, 40px); line-height: 1.18; letter-spacing: -.025em;
  color: #FFFFFF; max-width: 840px;
}
.kontrol-workspace .kontrol-title-sm { font-size: clamp(26px, 2.6vw, 34px); }
.kontrol-workspace .kontrol-title span {
  color: inherit; background: none; -webkit-text-fill-color: currentColor;
}
.kontrol-workspace .kontrol-eyebrow { letter-spacing: .06em; font-size: 11px; }
.kontrol-workspace :is(.kontrol-hero, .kontrol-header, .kontrol-subhead) :is(.kontrol-lede, .kontrol-lede-sm, .kontrol-lead, .kontrol-eyebrow) {
  color: #E2E7FA;
}
.kontrol-workspace :is(.kontrol-hero, .kontrol-header, .kontrol-subhead) :is(.kontrol-lede, .kontrol-lede-sm, .kontrol-lead) {
  font-size: 15px; line-height: 1.65; max-width: 64ch; margin-bottom: 0;
}
.kontrol-workspace .kontrol-header-main { min-width: 0; flex: 1; }
.kontrol-workspace .kontrol-header { display: flex; align-items: center; justify-content: space-between; }
.kontrol-workspace .kontrol-subhead .kontrol-title-sm { color: #FFFFFF; }
.kontrol-workspace .kontrol-subhead .kontrol-back { color: #E2E7FA; }
.kontrol-workspace .kontrol-portal-nav {
  display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0 24px;
}
.kontrol-workspace .kontrol-portal-nav a {
  display: inline-flex; align-items: center; min-height: 44px; padding: 10px 16px;
  color: var(--k-muted); text-decoration: none; border-radius: 10px;
  font-weight: 600; border: 1px solid transparent;
}
.kontrol-workspace .kontrol-portal-nav a[aria-current='page'] {
  color: #37429E; background: #E4E7FA; border-color: #CCD2EF;
}
.kontrol-workspace .kontrol-module-access {
  background: #FFFFFF; border: 1px solid var(--k-border); padding: 20px;
  border-radius: 16px; margin-bottom: 24px;
}
.kontrol-workspace .kontrol-module-access-label {
  font-size: 12px; font-weight: 700; color: var(--k-muted); margin-bottom: 12px;
}
.kontrol-workspace .kontrol-module-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.kontrol-workspace .kontrol-module-link {
  display: inline-flex; align-items: center; gap: 10px; min-height: 44px;
  border: 1px solid var(--k-border); border-radius: 10px; padding: 10px 14px;
  text-decoration: none; color: var(--k-text); background: #FFFFFF; font-weight: 600;
}
.kontrol-workspace .kontrol-module-link small {
  font-size: 10px; font-weight: 500; color: var(--k-muted);
}
.kontrol-workspace .kontrol-module-link.is-primary {
  background: #4F5BD5; border-color: #4F5BD5; color: #FFFFFF;
}
.kontrol-workspace .kontrol-module-link.is-primary small { color: #FFFFFF; }
.kontrol-workspace .kontrol-portals {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px;
}
.kontrol-workspace :is(.portal-card, .kontrol-panel, .kpi, .kontrol-ai, .layanan-block) {
  background: #FFFFFF; border: 1px solid var(--k-border); border-radius: 16px;
  box-shadow: var(--k-shadow); color: var(--k-text);
}
.kontrol-workspace :is(.portal-card, .kontrol-panel, .kontrol-ai, .layanan-block) { padding: 24px; }
.kontrol-workspace .portal-card { min-width: 0; transform: none; }
.kontrol-workspace .portal-card::before, .kontrol-workspace .portal-card::after { content: none; }
.kontrol-workspace .portal-card h2 {
  color: var(--k-text); font-size: 21px; line-height: 1.4; letter-spacing: -.015em;
}
.kontrol-workspace :is(.portal-card p, .portal-sub) { color: var(--k-muted); }
.kontrol-workspace :is(.portal-tag, .portal-hint, .portal-cta) {
  color: #37429E; border-color: #E4E7FA; background: transparent;
}
.kontrol-workspace :is(.quick-item, .proxy, .kontrol-unit-switch) {
  background: #FFFFFF; border-color: var(--k-border); box-shadow: none;
}
.kontrol-workspace :is(.quick-value, .kpi-value, .portal-metric strong, .panel-head h2,
  .proxy strong, .gauge-value, .kontrol-ai-head h3, .layanan-head h2, .bar-count) {
  color: var(--k-text);
}
.kontrol-workspace :is(.kpi-value, .quick-value, .portal-metric strong) {
  font-family: 'Manrope', sans-serif; font-variant-numeric: tabular-nums; font-size: 28px;
}
.kontrol-workspace .kontrol-unit-switch .form-select {
  color: var(--k-text); background: #FFFFFF; border: 1px solid #B8C2D5;
  min-height: 44px; width: 100%; min-width: 0;
}
.kontrol-workspace .kontrol-unit-switch { max-width: 100%; }
.kontrol-workspace .bar-track { background: #EDF0F6; }
.kontrol-workspace .kontrol-btn {
  min-height: 44px; background: #FFFFFF; border-color: var(--k-border);
  color: var(--k-text); box-shadow: none;
}
.kontrol-workspace .kontrol-btn-ai { color: #37429E; background: #F0EDFF; }
.kontrol-workspace .kontrol-ghost {
  min-height: 44px; background: #FFFFFF; color: #17223B; border-color: #E2E7F0;
}
.kontrol-workspace .kontrol-table { color: var(--k-text); }
.kontrol-workspace .kontrol-table thead { background: #F0F3F9; }
.kontrol-workspace .kontrol-table td, .kontrol-workspace .kontrol-table th {
  border-color: var(--k-border); overflow-wrap: break-word;
}
.kontrol-workspace .kontrol-table-wrap { overflow-x: auto; }
.kontrol-workspace .kontrol-table tbody tr:hover { background: #F6F8FC; }
.kontrol-workspace :is(a, button, select) { transition: background-color 120ms ease, border-color 120ms ease; }
.kontrol-workspace a:hover { transform: none; }
.kontrol-workspace .portal-card:hover { border-color: #AAB4E5; box-shadow: var(--k-shadow); }
.kontrol-workspace .kontrol-module-link.is-primary:hover { background: #37429E; }
.kontrol-workspace :focus-visible { outline: 3px solid #4F5BD5; outline-offset: 3px; }
.kontrol-workspace .kontrol-skip-link {
  position: absolute; top: 8px; left: 16px; transform: translateY(-200%);
  background: #FFFFFF; color: #14213D; padding: 12px; z-index: 100;
}
.kontrol-workspace .kontrol-skip-link:focus { transform: translateY(0); }
@media (max-width: 767px) {
  .kontrol-workspace .kontrol-main { padding: 16px; }
  .kontrol-workspace .kontrol-topbar { width: calc(100% - 32px); margin-top: 16px; }
  .kontrol-workspace .kontrol-portals { grid-template-columns: minmax(0, 1fr); }
  .kontrol-workspace :is(.kontrol-hero, .kontrol-header, .kontrol-topbar) { flex-wrap: wrap; }
  .kontrol-workspace :is(.kontrol-hero, .kontrol-header, .portal-card, .kontrol-panel) { padding: 20px; }
  .kontrol-workspace .kontrol-module-actions { display: grid; grid-template-columns: minmax(0, 1fr); }
  .kontrol-workspace .kontrol-module-link { flex-wrap: wrap; }
  .kontrol-workspace .kontrol-module-link i { margin-left: auto; }
  .kontrol-workspace .kontrol-header { flex-direction: column; align-items: stretch; }
}
@media (prefers-reduced-motion: reduce) {
  .kontrol-workspace *, .kontrol-workspace *::before, .kontrol-workspace *::after {
    animation: none; transition: none; scroll-behavior: auto;
  }
}
@media print {
  .kontrol-workspace { background: #FFFFFF; color: #17223B; }
  .kontrol-workspace :is(.kontrol-topbar, .kontrol-portal-nav, .kontrol-module-access, .kontrol-ai) { display: none; }
  .kontrol-workspace :is(.kontrol-hero, .kontrol-header) {
    background: #FFFFFF; border-color: #E2E7F0; color: #17223B;
  }
  .kontrol-workspace :is(.kontrol-title, .kontrol-hero .kontrol-lead,
    .kontrol-header .kontrol-lead, .kontrol-hero .kontrol-eyebrow,
    .kontrol-header .kontrol-eyebrow) { color: #17223B; }
}
```

Remove the existing `backdrop-filter: blur(10px);` declaration from `.kontrol-topbar` in `static/css/kontrol.css` (current line 65). The new stylesheet deliberately contains no blur property. Keep existing chart severity rules untouched.

Selector names above match inspected markup: `.kontrol-main`, `.kontrol-portals`, `.kontrol-kpis`, `.kpi`, `.kontrol-unit-switch`, `.brand-mark`, and `.portal-sub`. Do not introduce parallel aliases for those established classes. The new shared header uses `.kontrol-header`; the services page retains `.kontrol-subhead`.

### 7. Make hub cards restrained and internally consistent

Files: `templates/akreditasi/kontrol/hub.html`, `akreditasi/kontrol_views.py`, `akreditasi/tests_kontrol_workspace.py`.

1. Add a failing assertion that hub cards contain no inline per-portal `--accent`/glow style and still render the three formal titles and the authorized HC card.
2. In `hub.html`, remove the card's inline `--accent` / `--accent-glow` style binding; let the new scoped stylesheet own the unified indigo accent. Remove purely decorative portal tags only if they repeat the title, but retain metrics, meaningful scope labels, empty states, and the card link.
3. Keep formal names and HC title unchanged; do not rewrite business naming to pass a screenshot review.
4. Replace the opening card anchor and remove its entire old inline style attribute with this exact opening tag; keep its existing contents and closing tag. This preserves the selected resolved unit for control cards without forwarding it into a potentially different HC grant scope:

```django
<a class="portal-card" href="{{ portal.url }}{% if not portal.requires_hc %}?unit={{ unit.pk }}{% endif %}">
```
5. Remove `accent`/`glow` entries from `SUBDASHBOARDS` only after a repository search proves no remaining consumer. Otherwise retain the metadata untouched; removing unused constants is not a prerequisite for the feature.
6. Ensure the single `<a class="portal-card">` remains the only interactive element in each card. A decorative CTA is a `<span>`, not a nested button.

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render akreditasi.tests_layanan_unit --verbosity 1
```

Expected: `OK`, no changes to any metric formula and no permission-dependent rendering failures. Checkpoint B: stage only the navigation builder/view, control partials/templates, new stylesheet/style tests/workspace tests, and any narrowly necessary legacy stylesheet declaration removal; inspect `git diff --cached --name-only` and `git diff --cached --check`, then commit:

```bash
git commit -m "feat(control): redesign gradient workspace and surface direct module access"
```

Do not use an indiscriminate staging command to reach this checkpoint.

### 8. Close the context, permission, and empty-state regression matrix

Files: `akreditasi/tests_kontrol_navigation.py`, `akreditasi/tests_kontrol_workspace.py`, `akreditasi/tests_kontrol_dasbor.py`.

Add one focused test at a time, reproduce any defect, then fix only the responsible builder/context/template:

- Outpatient unit with no `rajal` entitlement: no clinical shortcut and an explanatory toolbar state.
- Unmapped administrative unit: no fake `0 patients`, no random clinic link, existing service explanation remains.
- Bed-owning unit without `ranap`: no bed-management action.
- Clinical primary link resolves directly to its operational destination, not `akreditasi:dashboard`.
- Selected-unit links on risk remain clamped to a unit-scoped user's own unit even with another unit in the request query.
- An authorized hospital-wide role selecting a unit gets that exact unit on risk/M&E links and all internal portal tabs.
- Human Capital tab/card both absent without permission and both present with a real active grant. Expired/inactive grants remain absent using the existing access guard.
- No selected active unit: hub and subpages retain existing empty state and emit no malformed `?unit=None` links.
- Exactly one `aria-current="page"` on hub/risk/EMR/documents; no false active destination on the services page.
- Existing AI panel is still present, button selectors unchanged, GET remains 405, invalid portal POST remains 400; do not make real AI calls in tests.
- Warm-cache query count stays <=12 on both existing hub and EMR budget tests. Do not raise the budget to hide repeated HC checks or a navigation query loop.

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render akreditasi.tests_layanan_unit --verbosity 1
```

Expected: `OK`, with the actual test count reported from execution rather than copied from an old session. Checkpoint C: commit only tests and the minimal fixes needed for those tests, using `test(control): cover scoped shortcuts and workspace states`.

### 9. Verify rendered layout and navigation in a real browser

Files: optionally add narrowly scoped browser-test code if an existing repository QA harness can host it; new verification report `docs/qa/integrated-control-workspace-verification.md` during implementation only. Do not create that report during this planning turn.

1. Check the available browser driver without installing dependencies blindly:

```bash
.venv/Scripts/python.exe -c "import importlib.util; print(bool(importlib.util.find_spec('playwright')))"
python -c "import importlib.util; print(bool(importlib.util.find_spec('playwright')))"
```

The project interpreter may return `False` while the system interpreter returns `True`. That is not a browser-testing blocker.

2. Render the real views through Django's test client using the isolated settings and fixture users, or use an already-running authenticated local test instance. Keep output under `$TMPDIR/control-workspace-qa/`. Do not point a QA renderer at a real database merely to get layout screenshots. Inline/serve the actual source CSS and local fonts. Keep a clear distinction between a component render, a fully authenticated view test, and production validation.
3. For a static view render, preserve all real template structure and replace only non-local navigation targets with inert URLs for geometry testing. Verify actual destination correctness separately through the route/context tests; do not claim a click-through based on inert links.
4. Measure hub, risk, EMR, documents, and services at 1440x900, 1366x768, 768x1024, and 390x844. Include a long unit name, unknown metric values, HC present/absent, and enough rows to exercise a real table.
5. Use this complete browser-console measurement expression, not screenshot intuition alone:

```javascript
(() => {
  const rect = el => el.getBoundingClientRect();
  const visible = el => rect(el).width > 0 && rect(el).height > 0;
  const targets = [...document.querySelectorAll(
    '.kontrol-portal-nav a, .kontrol-module-link, .kontrol-unit-switch select'
  )].filter(visible);
  const clipped = [...document.querySelectorAll(
    '.kontrol-title, .portal-card h2, .kontrol-module-link span'
  )].filter(visible).filter(el => el.scrollWidth > el.clientWidth + 1);
  const primary = document.querySelector('[data-module-primary]');
  const kpis = document.querySelector('.kontrol-kpis');
  return {
    width: innerWidth,
    pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
    clippedLabels: clipped.map(el => el.textContent.trim()),
    undersizedTargets: targets.filter(el => rect(el).height < 43.5)
      .map(el => el.textContent.trim()),
    mainCount: document.querySelectorAll('main#kontrol-main').length,
    headingCount: document.querySelectorAll('h1').length,
    primaryCount: document.querySelectorAll('[data-module-primary]').length,
    actionBeforeKpis: !primary || !kpis || rect(primary).top < rect(kpis).top,
    activeTabs: document.querySelectorAll('.kontrol-portal-nav [aria-current="page"]').length,
    decorativeBackdrop: !!document.querySelector('.kontrol-backdrop'),
    nestedControls: document.querySelectorAll('a.portal-card a, a.portal-card button').length,
  };
})()
```

Expected: `pageOverflow=false`, empty clipped/undersized lists, `mainCount=1`, `headingCount=1`, `actionBeforeKpis=true`, `decorativeBackdrop=false`, `nestedControls=0`; primary count is one for eligible operational pages and zero for hub/services/ineligible EMR. Active tabs are one for the four principal pages and zero for the standalone services page.

6. Check table overflow separately: a table may scroll inside an explicitly scrollable wrapper; the page itself must not overflow or cut off headers. Check the real CSS wrapper class before assuming the generic table selectors cover it.
7. Keyboard-only checks: skip link reaches `#kontrol-main`; tabs are in logical order; every action has a visible focus outline; selected unit and portal tabs remain usable at 200% zoom. Verify text contrast >=4.5:1 and non-text control/focus contrast >=3:1 using actual computed foreground/background values, including the darkest/lightest gradient stops. Do not claim WCAG conformance from palette choice alone.
8. Click operational anchors in the authenticated test environment: risk list, M&E, FMEA/RCA, incidents, documents, manager-only rekap, reports, eligible poli, IGD, beds, and HC. Record actual final URL and status. No intermediate `/` application dashboard is acceptable. If a legacy destination already errors, record it as a pre-existing blocker rather than masking it with a new UI fallback.
9. Verify a supported preserved filter visibly selects the expected unit/year/poli at the target, not merely that the href contains a query string. Explicitly scoped hospital-wide destinations must not pretend to retain the unit.
10. Save screenshots and measurement JSON under scratch, link their absolute paths in the QA report, and record which checks were component-only versus authenticated. Fix any measured overflow and rerun affected viewports after the final CSS edit.

### 10. Collect production assets and package the verified change

Files: source allowlist above; collected `staticfiles/css/kontrol-workspace*.css`, their generated gzip siblings, `staticfiles/css/kontrol*.css` only if the source legacy file changed, self-hosted font references/collected hashes as generated, and `staticfiles/staticfiles.json`.

1. Run the final focused suite from Task 8, then the regular application checks. No migration is required by this feature.

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe manage.py collectstatic --noinput
git diff --check
git status --short
```

Expected: system checks report no new issues; no migrations are generated for this feature; collection succeeds; whitespace check exits 0. The existing parallel model/migration work can make the repository-wide migration check non-green: identify its exact files and do not modify those files to make this UI task pass.

2. Read the collected manifest and verify the entry for `css/kontrol-workspace.css` resolves to an existing hashed file whose bytes match the source after normal static URL post-processing. Verify referenced hashed local font assets exist. Verify gzip decompression matches the corresponding plaintext asset. Never paste a guessed hash into the plan or template.
3. Run the available full regression suite against the isolated test settings; report full-suite failures separately from focused UI tests. A migration-disabled isolated suite is not proof that production migrations work.
4. Inspect `git diff --name-only` and explicitly stage only owned UI/test/static/report files. Check staged names before committing. Generated changes unrelated to these stylesheets must be investigated and excluded, not swept in by `collectstatic`.
5. Checkpoint D: commit assets and the QA report using `build(control): collect branded workspace assets and record QA`.
6. Stop at a local verified artifact unless the user authorizes push/deployment. A previous task's push authorization is not blanket authorization for a new UI implementation.
7. If later asked to deploy, push the approved commits, read the resulting deployment status, then verify authenticated `/control/`, all three subpages, direct module links, and collected CSS URLs. A successful Git push alone is not deployment verification. Never activate STARKES fixtures or run production migrations as part of this UI rollout.

## Validation / acceptance criteria

- [ ] The hub and all three control dashboards use the application's actual navy–indigo palette, not cyan/pink neon or unrelated portal colors.
- [ ] White data surfaces, consistent spacing, restrained typography, and a two-column desktop portal grid replace the decorative dark scene.
- [ ] No hospital illustration, animated glow, glass panel, nested interactive card, new font CDN, or new frontend framework is introduced.
- [ ] Each eligible operational dashboard exposes one primary direct-module link above its KPIs, with relevant secondary links and honest scope labels.
- [ ] Users can switch control dashboards directly, with the resolved unit preserved where supported.
- [ ] Clinical links follow both the selected unit's mapping and the current user's existing module permissions; unmapped units do not receive arbitrary clinical destinations.
- [ ] Human Capital card and shared tab obey the same existing permission/grant guard; its existing workspace and authorization remain unchanged.
- [ ] Manager-only rekap is not advertised to roles that are redirected away by its target view.
- [ ] Null/unknown metrics, RS-wide metrics, real status colors, AI behavior, and service mapping retain their existing meaning.
- [ ] No schema/data migration, catalogue activation, production database write, or global sidebar change is included.
- [ ] The focused suite passes; actual test counts and query counts are recorded from execution.
- [ ] Browser measurements meet the overflow, touch-target, heading, and navigation criteria at every specified viewport.
- [ ] Collected hashed CSS/font references and gzip assets are verified, not just source files.
- [ ] No unrelated parallel work is staged; push/deployment status is reported separately.

## Risks, tradeoffs, and open questions

1. **Scoped stylesheet versus rewriting every chart rule:** a small scoped presentation adapter minimizes regression risk and preserves existing charts, at the cost of retaining the legacy control stylesheet. Keep all new appearance rules in the single adapter; do not build a chain of additional override files. Remove only legacy declarations that conflict with explicit no-blur/no-decoration invariants.
2. **Gradient preference:** assume a professional light workspace with a branded gradient masthead, not a full-screen dark gradient. This uses the application's existing token palette and improves table readability without a new theme picker.
3. **Target routes accept different filters:** unit context cannot honestly be preserved on every existing application page. Only append documented supported parameters, and label broader destinations. Adding new unit-filter semantics to operational views is a separate change.
4. **Clinical access is not universal:** administrative/unmapped units may have no valid patient shortcut. An explicit empty toolbar state is preferable to a misleading or unauthorized destination. Broader clinical operations such as pharmacy/lab shortcuts can be added later from verified route/permission contracts, not guessed in this redesign.
5. **Legacy target authorization:** exposing a link is not evidence that every target enforces perfect object-level scope. Preserve existing guards and test the selected path. Any newly discovered authorization flaw is a separate finding requiring a scoped fix before enabling the affected shortcut.
6. **Production UI not visually inspected while authenticated:** conduct local/authenticated browser verification during execution. Use the vault/login UI for production access if needed; do not put credentials in chat, scripts, or the plan.
7. **Parallel dirty tree and seed migrations:** isolated test settings avoid historical seed/migration interference. They do not excuse skipping a separately reported regular-configuration check or justify altering parallel model/catalogue work.
8. **Human Capital consistency:** its control entry card/tab gains visual consistency, but its destination retains the HC workspace. Applying this design to every HC detail screen is outside the requested control-surface change.
9. **No blocking design question:** the palette, scope, navigation placement, and implementation approach have concrete defaults. If the user later requests a dark-only theme or embedded modules, revise the plan before implementing those materially different requirements.
