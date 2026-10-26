# Integrated Control Readability and EMR Registration Implementation Plan

> **For agentic workers:** Use `executing-plans` for native execution or `subagent-driven-development` for task-by-task implementation and review. Track progress with the checkboxes below. This document is a plan, not approval to implement, commit, push, or deploy during the planning turn.

**Goal:** Make Integrated Control easier to read and understand, and add a permission-aware patient-registration entry inside the EMR Unit Services section.

**Architecture:** Retain the existing Django views, unit resolver, operational destinations, and standalone Integrated Control shell. Improve typography through the existing scoped workspace stylesheet, clarify presentation copy without changing metric calculations, and add a pure registration-link builder whose result is rendered only in EMR Unit Services. Reuse the existing registration dashboard and its authorization decorator; do not create a new registration workflow or grant additional patient-module permissions.

**Tech stack:** Django, server-rendered templates, Bootstrap 5.3.3, Bootstrap Icons 1.11.3, self-hosted Inter and Manrope, WhiteNoise; existing isolated SQLite test settings.

**Specification:** The user request in this session: tidy Integrated Control UI, improve font clarity and explanatory text, and add patient registration under EMR Unit Services. This plan is the bounded implementation specification. All instructions are English; quoted Indonesian UI literals and existing identifiers are exact implementation data, not text to translate.

## Current context and assumptions

- Workspace: `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`.
- Inspected branch: `master`; current commit: `4e47a14`. The branded workspace already exists in commit `d89d36e`.
- The tree already has unrelated modified seed commands and untracked catalogue, HC, QA, and plan files. Preserve them. Recheck status immediately before execution; never stash, reset, clean, or stage the whole tree.
- `.hermes/plans/2026-10-24_161956-integrated-control-workspace-redesign.md` describes the earlier redesign, and `docs/qa/integrated-control-workspace-verification.md` records its earlier verification. The relevant presentation/navigation files are now tracked and unchanged. This plan builds on that implementation; it does not reimplement that redesign or the HC/STARKES plans.
- No authenticated live-browser inspection was performed for this plan. Repository inspection shows small inherited font rules; it does not prove the exact appearance of a current production session. The implementation must measure rendered output.
- `static/css/kontrol-workspace.css` already provides a light surface and navy/indigo masthead. However, many labels retain font sizes from `static/css/kontrol.css`: KPI scope at `0.58rem`, panel hints at `0.62rem`, KPI labels at `0.7rem`, footnotes at `0.72rem`, and service descriptions at `0.7rem`. Increasing only the body font does not override these explicit sizes.
- `templates/akreditasi/kontrol/_layanan_unit.html` is shared by risk, EMR, and documents. It currently exposes daily services and sometimes beds, but no registration entry. `emr.html` currently places it after the AI panel.
- Existing registration destination: `reverse('pasien:pendaftaran_dashboard')`, declared in `pasien/urls.py:31` and implemented in `pasien/views.py:749-798`. It supports registration/routing and reports hospital-wide data; it does not consume `unit`, `poli`, or a control-page date filter.
- Registration requires `pendaftaran` in `UserProfile.get_allowed_patient_modules()` through `pasien/decorators.py`. Existing policy grants it to superusers, `SUPER_ADMIN`, `ADMIN_RS`, `DIREKTUR`, IGD profiles, and registration/admission/medical-record units, subject to the method's existing branch order. Ordinary outpatient profiles do **not** receive it merely because they can open EMR.
- Assumption: “add registration menu” means expose the existing registration workflow to users already entitled to it. It does not authorize an RBAC expansion for outpatient, lab, pharmacy, or every unit account.
- Registration must remain available to entitled admission or administrative users even when the selected unit has no daily clinical-service mapping. Do not place the registration link inside the mapped-only branch.
- `config/control_test_settings.py` already exists: SQLite `:memory:`, local cache, disabled migrations for the local apps, fast hashers, and plain static-file storage. Use it for tests; no database migration is needed.
- Measured interpreter: `.venv/Scripts/python.exe` imports Django `6.1.1`; `requirements.txt` pins `6.1.2`. Record this discrepancy in verification; do not silently reinstall dependencies or claim pinned-version verification.
- No current tests were run during this planning turn. Earlier recorded test counts are historical evidence, not a fresh baseline.

## Global constraints

1. Keep formal English portal names, navy/indigo branding, Inter/Manrope, no-sidebar shell, existing destinations, unit selection, HC grant handling, AI selectors, and risk-severity colors.
2. Do not change patient models, registration submission handlers, permission policy, snapshot queries, KPI formulas, catalogue lifecycle, or migrations.
3. Preserve existing zero/null behavior in this presentation change. Some existing templates use `default` and therefore display zero as a dash; do not opportunistically change those semantics here.
4. Keep source CSS scoped beneath `.kontrol-workspace`. Edit existing owning blocks rather than appending competing overrides. Do not add `!important`, external fonts, animation, a UI framework, or a new dependency.
5. Do not advertise unit filtering on hospital-wide registration. Its link must have no query string.
6. Keep the clinical `module_actions` list unchanged, including its current primary action and empty-state behavior. Registration is a distinct Unit Services action, not another generic toolbar item.
7. Retain the existing warm-cache query budget of at most 12; do not loosen it.
8. Implementation tests may create data only in isolated test databases. Browser evidence must use synthetic patients/accounts, never live patient data.
9. `staticfiles/` is deliberately tracked for Vercel. Regenerate collected assets only after source/test gates pass; do not delete old tracked artifacts as unrelated cleanup.
10. Commit checkpoints below apply only when execution authorization includes commits. Otherwise leave the reviewed diff uncommitted. No push or deployment is included.

## Review focus

- An entitled admission account with an unmapped unit must see the registration entry, despite having no daily patient list.
- An outpatient/lab/pharmacy user without registration entitlement must not see the entry; a direct request must still be denied by the destination.
- `ADMIN_RS`/`DIREKTUR` and superuser accounts must retain registration access even on an administrative selected unit; selecting a different unit must not modify registration scope.
- Long portal titles, full unit names, dates, descriptions, and action labels must wrap at narrow widths instead of shrinking or clipping.
- Explicit small-font rules and CSS specificity must not defeat the new typography scale, especially panel headings, scope labels, service dates, and the large EMR bar-list selector.

## Proposed visual and content contract

| Element | Required final behavior |
|---|---|
| Main body | Inter, 16px, line-height 1.6, current dark foreground and light background |
| Main titles | Keep existing responsive 28–40px hub and 26–34px portal scale; permit wrapping |
| Card/panel headings | Manrope, panel headings 18px/1.4, existing portal-card headings 21px/1.4 |
| KPI values | Preserve 28px tabular values |
| Operational labels | 14px/1.5, weight 600; sentence case |
| Supporting text | 14px/1.55 with `--k-muted`; no pale gray or text-opacity trick |
| Compact metadata | 13px/1.5 minimum, including scope, date, band, and footer metadata |
| Service action title | 15px/1.5, weight 600 |
| Service rows | At least 44px high, 16px padding, 12px gaps; full row is a single anchor |
| Layout | Existing 1200px content area, two-column portal cards and one-column mobile; keep 24px section spacing |
| Mobile | At <=767px, stack service icon/text/count; long text wraps, arrow remains visible; no page-level horizontal scroll |
| Navigation/focus | Existing focus ring and skip link; registration row reachable by keyboard and labeled by visible text |
| Scope explanations | Clearly distinguish selected-unit services from hospital-wide registration/bed occupancy/accreditation coverage |
| EMR order | Portal header and existing contextual module toolbar → Unit Services → KPIs → clinical panels → AI |

The registration entry uses exact visible title `Pendaftaran pasien` and description `Buka pendaftaran pasien baru atau lama dan pengaturan tujuan layanan. Cakupan seluruh rumah sakit sesuai hak akses.` It links directly to the existing dashboard in the same tab. Do not nest buttons in the anchor and do not add a modal or duplicate registration form.

### File inventory

Modify:
- `akreditasi/kontrol_navigation.py` — pure registration-action builder.
- `akreditasi/kontrol_views.py` — inject registration action into common context using the existing entitlement calculation.
- `templates/akreditasi/kontrol/_layanan_unit.html` — registration row and explicit scope note.
- `templates/akreditasi/kontrol/emr.html` — move Unit Services earlier and clarify CPPT/PPA explanations.
- `templates/akreditasi/kontrol/hub.html` — clearer user guidance and abbreviation key.
- `templates/akreditasi/kontrol/risiko.html` — expand RTL in explanatory copy.
- `templates/akreditasi/kontrol/dokumen.html` — explain EP and remove implementation jargon from the score explanation.
- `static/css/kontrol-workspace.css` — readable typography and responsive service rows.
- `akreditasi/tests_kontrol_workspace_style.py` — adapt the existing 12px scope contract and add targeted readability invariants.

Create:
- `akreditasi/tests_kontrol_registration.py` — builder, integration, permissions, placement, and copy tests.
- `docs/qa/control-readability-registration-verification.md` — implementation evidence and remaining limitations, written only in the execution phase.

Generated during execution:
- `staticfiles/css/kontrol-workspace.css`, its generated hashed/gzip variants, and `staticfiles/staticfiles.json` as produced by `collectstatic`.
- Scratch browser artifacts under `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/control-readability/`, never in application source.

## Step-by-step tasks

Each checkbox is a focused 2–5 minute action. Tasks combine adjacent RED/GREEN increments; commit only green checkpoints. Commands below are for execution, not this planning turn.

### Task 1: Establish the current baseline

- [ ] Inspect status and interpreter without changing the tree:

```bash
git status --short
git branch --show-current
git log -3 --oneline
.venv/Scripts/python.exe -c "import sys,django; print(sys.executable); print(django.get_version())"
```

Expected: the project interpreter is used; record the actual branch/commit and unrelated changes. If the target files have changed since inspection, reread them before applying the planned edits.

- [ ] Run the isolated focused baseline and route/unit guards:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render akreditasi.tests_layanan_unit accounts.tests_unit_rbac accounts.tests_sidebar_visibility pasien.tests_route_rbac --verbosity 1
```

Expected: `OK`, exit code 0. Record actual failures/counts if different; do not call an import, settings, fixture, or unrelated baseline failure a feature RED.

### Task 2: Specify and implement the registration action

**Files:** create `akreditasi/tests_kontrol_registration.py`; modify `akreditasi/kontrol_navigation.py` and `akreditasi/kontrol_views.py`.

**Interface:** `registration_action(*, active_portal, allowed_patient_modules=None) -> dict | None`. It returns `None` outside EMR or without entitlement; otherwise it returns the normal action dictionary plus `description`. It performs no queries and accepts no unit argument.

- [ ] Create this initial test file:

```python
from django.test import SimpleTestCase
from django.urls import reverse


class RegistrationActionTest(SimpleTestCase):
    def test_entitled_emr_action_has_exact_hospital_wide_destination(self):
        from akreditasi.kontrol_navigation import registration_action

        action = registration_action(
            active_portal='emr', allowed_patient_modules={'pendaftaran'})
        self.assertEqual(action['key'], 'pendaftaran')
        self.assertEqual(action['label'], 'Pendaftaran pasien')
        self.assertEqual(action['href'], reverse('pasien:pendaftaran_dashboard'))
        self.assertEqual(action['scope'], 'Seluruh rumah sakit')
        self.assertIn('pasien baru atau lama', action['description'])

    def test_other_portals_never_advertise_registration(self):
        from akreditasi.kontrol_navigation import registration_action

        for portal in ('hub', 'risiko', 'dokumen', 'layanan'):
            with self.subTest(portal=portal):
                self.assertIsNone(registration_action(
                    active_portal=portal,
                    allowed_patient_modules={'pendaftaran'}))

    def test_missing_or_insufficient_entitlement_returns_none(self):
        from akreditasi.kontrol_navigation import registration_action

        for allowed in (None, set(), {'rajal'}, {'ranap'}, {'laboratorium'}):
            with self.subTest(allowed=allowed):
                self.assertIsNone(registration_action(
                    active_portal='emr', allowed_patient_modules=allowed))
```

- [ ] RED:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_registration.RegistrationActionTest --verbosity 2
```

Expected: import failure for the new `registration_action` symbol. `SimpleTestCase` already forbids database access, so the direct function call also protects the pure-builder contract without creating a database.

- [ ] Add this function immediately after `_action` in `akreditasi/kontrol_navigation.py`:

```python
def registration_action(*, active_portal, allowed_patient_modules=None):
    if active_portal != 'emr' or 'pendaftaran' not in set(allowed_patient_modules or ()):
        return None
    action = _action(
        'pendaftaran', 'Pendaftaran pasien', 'pasien:pendaftaran_dashboard',
        scope='Seluruh rumah sakit',
    )
    action['description'] = (
        'Buka pendaftaran pasien baru atau lama dan pengaturan tujuan layanan. '
        'Cakupan seluruh rumah sakit sesuai hak akses.'
    )
    return action
```

- [ ] In `akreditasi/kontrol_views.py`, replace the existing navigation import:

```python
from .kontrol_navigation import module_actions, portal_navigation, registration_action
```

Add this entry in the dictionary returned by `_common_context`, immediately after `active_portal`:

```python
'registration_action': registration_action(
    active_portal=active_portal, allowed_patient_modules=allowed,
),
```

Reuse the existing `allowed` variable. Do not call `get_allowed_patient_modules()` again, change `module_actions`, put permission results in shared snapshot cache, or infer entitlement from `snapshot.layanan.mapped`.

- [ ] GREEN: rerun the RED command; expect `OK`, exit code 0. Run `akreditasi.tests_kontrol_navigation` as well; its current action-list contracts must remain unchanged.

### Task 3: Specify the real rendering and permission contract

**Files:** append to `akreditasi/tests_kontrol_registration.py`; later implementation belongs to Task 4.

- [ ] Add these imports and this self-contained test class below `RegistrationActionTest`:

```python
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from akreditasi.models import UnitKerja


class RegistrationEntryTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def login(self, *, code, role='STAF', superuser=False):
        unit, _ = UnitKerja.objects.get_or_create(
            code=code,
            defaults={'name': 'Fixture ' + code, 'level': 3, 'is_active': True},
        )
        User = get_user_model()
        user = User.objects.create_user(
            username='entry-' + role.lower() + '-' + code.lower(),
            is_superuser=superuser, is_staff=superuser,
        )
        UserProfile.objects.create(user=user, role=role, unit_kerja=unit)
        self.client.force_login(user)
        cache.clear()
        return unit

    def emr(self, unit):
        return self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': unit.pk})

    def test_entitled_roles_and_units_see_registration(self):
        cases = (
            ('IGD', 'STAF', False),
            ('ADMISI', 'STAF', False),
            ('PENDAFTARAN', 'STAF', False),
            ('REKAM-MEDIS', 'STAF', False),
            ('KOMITE-MUTU', 'SUPER_ADMIN', False),
            ('KOMITE-MUTU', 'ADMIN_RS', False),
            ('KOMITE-MUTU', 'DIREKTUR', False),
            ('KOMITE-MUTU', 'STAF', True),
        )
        for code, role, superuser in cases:
            with self.subTest(code=code, role=role, superuser=superuser):
                unit = self.login(code=code, role=role, superuser=superuser)
                response = self.emr(unit)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-service-action="pendaftaran"', count=1)
                self.assertContains(response, 'Pendaftaran pasien')
                action = response.context['registration_action']
                self.assertEqual(action['href'], reverse('pasien:pendaftaran_dashboard'))
                target = self.client.get(action['href'])
                self.assertEqual(target.status_code, 200)

    def test_unmapped_admission_still_has_registration(self):
        unit = self.login(code='ADMISI')
        response = self.emr(unit)
        self.assertFalse(response.context['snapshot']['layanan']['mapped'])
        self.assertContains(response, 'data-service-action="pendaftaran"')
        self.assertContains(response, 'tidak memiliki layanan pendaftaran pasien')

    def test_non_entitled_users_get_neither_menu_nor_destination_access(self):
        for code in ('POLI-PD', 'LAB-BDRS', 'FARM', 'BANGSAL-DEWASA', 'DIREKSI'):
            with self.subTest(code=code):
                unit = self.login(code=code)
                response = self.emr(unit)
                self.assertNotContains(response, 'data-service-action="pendaftaran"')
                self.assertIsNone(response.context['registration_action'])
                self.assertEqual(self.client.get(
                    reverse('pasien:pendaftaran_dashboard')).status_code, 403)

    def test_shared_partial_does_not_add_registration_to_other_portals(self):
        unit = self.login(code='IGD')
        for name in ('kontrol_risiko', 'kontrol_dokumen', 'kontrol_layanan', 'kontrol_hub'):
            with self.subTest(name=name):
                response = self.client.get(reverse('akreditasi:' + name), {'unit': unit.pk})
                self.assertNotContains(response, 'data-service-action="pendaftaran"')
                self.assertIsNone(response.context['registration_action'])

    def test_registration_belongs_to_services_and_services_precede_kpis(self):
        unit = self.login(code='IGD')
        body = self.emr(unit).content.decode()
        start = body.index('<section class="kontrol-layanan"')
        end = body.index('</section>', start)
        marker = body.index('data-service-action="pendaftaran"')
        self.assertLess(start, marker)
        self.assertLess(marker, end)
        self.assertLess(end, body.index('class="kontrol-kpis"'))
        self.assertLess(end, body.index('class="kontrol-ai"'))

    def test_registration_scope_does_not_follow_requested_unit(self):
        unit = self.login(code='IGD')
        other = UnitKerja.objects.create(code='ENTRY-OTHER', name='Other', level=3)
        response = self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': other.pk})
        self.assertEqual(response.context['unit'].pk, unit.pk)
        self.assertEqual(response.context['registration_action']['href'],
                         reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(response, 'Cakupan seluruh rumah sakit sesuai hak akses.')

    def test_anonymous_emr_still_redirects_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(
            reverse('akreditasi:kontrol_emr')).status_code, 302)
```

The placement assertion uses the verified `class="kontrol-ai"` opening tag from `templates/akreditasi/kontrol/_ai_panel.html:2`; there is no `id="kontrol-ai"`.

- [ ] RED:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_registration.RegistrationEntryTest --verbosity 2
```

Expected: entitled menu/placement cases fail because the row is absent; denial/anonymous cases may already pass. Do not commit the red test-only state.

### Task 4: Render the registration entry and move Unit Services

**Files:** `templates/akreditasi/kontrol/_layanan_unit.html`, `templates/akreditasi/kontrol/emr.html`.

- [ ] In `_layanan_unit.html`, insert this block after `</header>` and before `{% if not snapshot.layanan.mapped %}`:

```django
    {% if registration_action %}
    <a class="layanan-entry layanan-entry-registration"
       data-service-action="pendaftaran"
       href="{{ registration_action.href }}">
        <span class="layanan-entry-icon"><i class="bi bi-person-plus" aria-hidden="true"></i></span>
        <span class="layanan-entry-text">
            <strong>{{ registration_action.label }}</strong>
            <small>{{ registration_action.description }}</small>
        </span>
        <i class="bi bi-arrow-right layanan-entry-go" aria-hidden="true"></i>
    </a>
    {% endif %}
```

- [ ] Keep the daily-service entry and unmapped explanation intact. After the daily-service anchor, add this visible note in the mapped branch:

```django
    <p class="kontrol-caption layanan-scope-note">Daftar harian mengikuti unit aktif dan tanggal layanan. Pendaftaran pasien dibuka melalui modul terpisah sesuai hak akses.</p>
```

This preserves the distinction between the selected-unit daily list and hospital-wide registration; it must not imply that registrations are prefilled to the selected unit.

- [ ] In `emr.html`, remove the existing bottom occurrence of `{% include "akreditasi/kontrol/_layanan_unit.html" %}` and insert that exact include immediately after `_portal_header.html`. Keep `_ai_panel.html` after the clinical panels. Do not move the services partial on risk/documents pages.

- [ ] GREEN:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_registration akreditasi.tests_layanan_unit akreditasi.tests_kontrol_workspace pasien.tests_route_rbac accounts.tests_unit_rbac --verbosity 1
```

Expected: `OK`, exit code 0; entitled registration destination is HTTP 200, non-entitled destination is HTTP 403, existing clinical toolbar tests remain green.

- [ ] Conditional green commit checkpoint, only if commits are authorized:

```bash
git add akreditasi/kontrol_navigation.py akreditasi/kontrol_views.py akreditasi/tests_kontrol_registration.py templates/akreditasi/kontrol/_layanan_unit.html templates/akreditasi/kontrol/emr.html
git diff --cached --check
git diff --cached --stat
git commit -m "feat(control): add permission-aware EMR registration entry"
```

### Task 5: Specify the typography scale with regression tests

**File:** `akreditasi/tests_kontrol_workspace_style.py`.

- [ ] Update only the final two assertions of `test_module_link_scope_label_readable`. Current exact lines:

```python
        self.assertIn('font-size:12px', decls.replace('font-size: 12px', 'font-size:12px'))
        self.assertIn('line-height:1.35', decls.replace('line-height: 1.35', 'line-height:1.35'))
```

Replace them with:

```python
        self.assertIn('font-size:13px', decls.replace('font-size: 13px', 'font-size:13px'))
        self.assertIn('line-height:1.5', decls.replace('line-height: 1.5', 'line-height:1.5'))
```

Also update that method's docstring to state the new 13px compact-metadata minimum. Keep the existing mobile flex-basis, brand, matrix contrast, reduced-motion, and print tests unchanged.

- [ ] Append these methods inside `ControlWorkspaceStyleTest`:

```python
    def test_readable_body_and_panel_heading_scale(self):
        css = _css()
        body = _declarations(css, 'body.kontrol-workspace')
        self.assertIn("font: 16px/1.6 'Inter'", body)
        heading = _declarations(css, '.kontrol-workspace .panel-head h2')
        self.assertIn('font-size: 18px', heading)
        self.assertIn('line-height: 1.4', heading)

    def test_readable_labels_and_service_text(self):
        css = _css()
        for selector, size in (
            ('.kontrol-workspace .kpi-label', 14),
            ('.kontrol-workspace .kpi-foot', 14),
            ('.kontrol-workspace .kpi-scope', 13),
            ('.kontrol-workspace .panel-hint', 13),
            ('.kontrol-workspace .layanan-date', 13),
            ('.kontrol-workspace .layanan-entry-text strong', 15),
            ('.kontrol-workspace .layanan-entry-text small', 14),
            ('.kontrol-workspace .kontrol-caption', 14),
        ):
            with self.subTest(selector=selector):
                self.assertIn(f'font-size: {size}px', _declarations(css, selector))

    def test_service_rows_support_long_mobile_copy(self):
        css = _css()
        mobile = _block(css, '@media (max-width: 767px)')
        row = _declarations(mobile, '.kontrol-workspace .layanan-entry')
        self.assertIn('display: grid', row)
        self.assertIn('minmax(0, 1fr)', row)
        self.assertIn("grid-template-areas: 'icon text go' '. count .'", row)
        text = _declarations(css, '.kontrol-workspace .layanan-entry-text')
        self.assertIn('min-width: 0', text)
        self.assertIn('overflow-wrap: anywhere', text)
```

- [ ] RED:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_workspace_style --verbosity 2
```

Expected: failures for the old body/scope sizes and missing exact scoped selectors, not failures in unrelated brand contracts.

### Task 6: Apply readable CSS without another redesign

**File:** `static/css/kontrol-workspace.css`.

- [ ] Change the existing body font declaration from `15px/1.55` to `16px/1.6`. In the existing `.kontrol-module-link small` block, change `12px/1.35` to `13px/1.5`. Do not duplicate either block.

- [ ] Add the following explicit typography section immediately before the existing `/* unit switch */` section. This is the only new typography section; keep the source declarations together and leave base `kontrol.css` unchanged:

```css
.kontrol-workspace .panel-head h2 { font-size: 18px; line-height: 1.4; }
.kontrol-workspace .kpi-label {
  font-size: 14px; line-height: 1.5; font-weight: 600;
  text-transform: none; letter-spacing: normal;
}
.kontrol-workspace .kpi-foot { font-size: 14px; line-height: 1.55; }
.kontrol-workspace .kpi-scope { font-size: 13px; line-height: 1.5; letter-spacing: normal; }
.kontrol-workspace .panel-hint {
  font-size: 13px; line-height: 1.5; letter-spacing: normal; text-transform: none;
}
.kontrol-workspace .layanan-date { font-size: 13px; line-height: 1.5; letter-spacing: normal; }
.kontrol-workspace .layanan-entry-text strong { font-size: 15px; line-height: 1.5; }
.kontrol-workspace .layanan-entry-text small { font-size: 14px; line-height: 1.55; }
.kontrol-workspace .kontrol-caption {
  font-size: 14px; line-height: 1.55; color: var(--k-muted); margin: 12px 0 0;
}
.kontrol-workspace :is(.quick-label, .portal-sub, .portal-foot, .portal-metric span,
  .bar-label, .bar-list-lg .bar-label, .proxy-label, .proxy-unit, .gauge-label,
  .kontrol-note, .kontrol-disclaimer, .kontrol-empty-inline, .layanan-empty,
  .layanan-note, .layanan-sub, .ai-limit) {
  font-size: 14px; line-height: 1.55; letter-spacing: normal;
}
.kontrol-workspace :is(.kontrol-eyebrow, .portal-band, .kontrol-brand small,
  .kontrol-footer, .kontrol-footer-meta, .matrix-tick, .matrix-axis-x, .matrix-axis-y) {
  font-size: 13px; line-height: 1.5; letter-spacing: .02em;
}

.kontrol-workspace :is(.portal-cta, .kontrol-ghost, .kontrol-user,
  .kontrol-unit-switch label, .kontrol-btn, .layanan-entry-count) {
  font-size: 14px; line-height: 1.5;
}
.kontrol-workspace .layanan-entry {
  min-height: 44px; padding: 16px; gap: 12px; align-items: center;
}
.kontrol-workspace .layanan-entry-text {
  min-width: 0; flex: 1 1 auto; white-space: normal; overflow-wrap: anywhere;
}
.kontrol-workspace .layanan-entry-registration {
  background: #F0EDFF; border-color: #CCD2EF;
}
.kontrol-workspace .layanan-entry-registration:hover { background: #E4E7FA; }
.kontrol-workspace .layanan-scope-note { margin-bottom: 12px; }
.kontrol-workspace .layanan-table { font-size: 14px; line-height: 1.55; }
.kontrol-workspace .layanan-table thead th { font-size: 13px; letter-spacing: normal; }
.kontrol-workspace .layanan-table .mono { font-size: 13px; }
.kontrol-workspace [class*='layanan-badge-'] { font-size: 13px; line-height: 1.5; }
.kontrol-workspace :is(.kontrol-title, .portal-card h2, .panel-head h2, .layanan-head h2) {
  overflow-wrap: anywhere;
}
```

The existing masthead eyebrow selector currently sets `font-size: 11px`; change that existing declaration to `13px`. The explicit masthead selector is more specific than the grouped typography rule above, so both must agree on the new minimum; do not append another masthead override.

- [ ] Inside the **existing** `@media (max-width: 767px)` block, add:

```css
  .kontrol-workspace .layanan-entry {
    display: grid; grid-template-columns: 36px minmax(0, 1fr) 18px;
    grid-template-areas: 'icon text go' '. count .';
  }
  .kontrol-workspace .layanan-entry-icon { grid-area: icon; }
  .kontrol-workspace .layanan-entry-text { grid-area: text; }
  .kontrol-workspace .layanan-entry-count { grid-area: count; justify-self: start; }
  .kontrol-workspace .layanan-entry-go { grid-area: go; justify-self: end; }
  .kontrol-workspace .layanan-head { align-items: flex-start; gap: 8px; flex-wrap: wrap; }
```

Keep the mobile header-main reset and one-column card/module grids. Do not use `overflow-x: hidden` to conceal layout defects. The service-table wrapper may scroll horizontally; the page itself may not.

- [ ] GREEN: rerun `akreditasi.tests_kontrol_workspace_style`; expect `OK`. Then run the complete Task 1 focused command plus `akreditasi.tests_kontrol_registration`; expect `OK` and unchanged query ceilings.

### Task 7: Clarify abbreviations and metric scope with exact copy

**Files:** `akreditasi/tests_kontrol_registration.py`, `templates/akreditasi/kontrol/{hub,emr,risiko,dokumen}.html`.

- [ ] Append this test method to `RegistrationEntryTest`:

```python
    def test_dashboard_explanations_are_visible_and_specific(self):
        unit = self.login(code='IGD')
        checks = {
            'kontrol_hub': ('Pilih unit aktif', 'Elemen Penilaian'),
            'kontrol_emr': ('Catatan Perkembangan Pasien Terintegrasi',
                            'Profesional Pemberi Asuhan', 'Seluruh RS'),
            'kontrol_risiko': ('Rencana Tindak Lanjut',),
            'kontrol_dokumen': ('Elemen Penilaian', 'Catatan mutu unit dengan skor di atas 0'),
        }
        for name, phrases in checks.items():
            with self.subTest(name=name):
                response = self.client.get(reverse('akreditasi:' + name), {'unit': unit.pk})
                for phrase in phrases:
                    self.assertContains(response, phrase)
```

- [ ] RED:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_registration.RegistrationEntryTest.test_dashboard_explanations_are_visible_and_specific --verbosity 2
```

Expected: missing clarification phrases fail. Do not alter metric values to satisfy text assertions.

- [ ] Apply these exact presentation replacements:

1. In `hub.html`, replace the existing `kontrol-lede` paragraph body with:

```django
        Pilih unit aktif untuk melihat ringkasan risiko, layanan klinis, dan dokumen.
        Buka sub-dasbor untuk melihat rincian dan mengakses modul operasional sesuai hak akses.
```

After the paragraph and before the unit-switch include, insert:

```django
    <p class="kontrol-lede">EP: Elemen Penilaian akreditasi. RTL: Rencana Tindak Lanjut. Data bertanda RS mencakup seluruh rumah sakit.</p>
```

2. In `emr.html`, replace only these existing explanatory spans:

```django
        <span class="kpi-foot">status terdaftar sampai rawat inap pada unit aktif</span>
```

This replaces `status terdaftar s.d. rawat inap`.

```django
        <span class="kpi-foot">Catatan Perkembangan Pasien Terintegrasi: {{ snapshot.emr.cppt_total|default:0 }} catatan tercatat</span>
```

This replaces the CPPT-total footnote; keep the KPI value expression untouched.

Replace visible `RS-wide` with `Seluruh RS`. After the Kredensial PPA panel header and before its `{% if snapshot.ppa.total %}`, insert:

```django
        <p class="kontrol-caption">PPA: Profesional Pemberi Asuhan. Ringkasan mengikuti kredensial yang tercatat pada unit aktif.</p>
```

3. In `risiko.html`, replace `aksi belum selesai &amp; tanggal terlewati` with `Rencana Tindak Lanjut belum selesai dan sudah melewati tenggat`.

4. In `dokumen.html`, replace `QualityRecord dengan skor &gt; 0` with `Catatan mutu unit dengan skor di atas 0`. Replace the KPI footnote `item berskor` with `Elemen Penilaian berskor` in the first KPI only. Replace `RS-wide` with `Seluruh RS`.

Do not rename the formal portal headings, metric keys, existing daily-services title, or the unmapped-unit message that existing tests already verify. Avoid changing the `Unit Contoh` business label in the shared selector in this change; improved hub guidance is sufficient without renaming a shared control.

- [ ] GREEN: rerun the copy test, then the focused regression command. Expected: `OK`, no existing assertion is removed merely to force success.

- [ ] Conditional green commit checkpoint:

```bash
git add static/css/kontrol-workspace.css akreditasi/tests_kontrol_workspace_style.py akreditasi/tests_kontrol_registration.py templates/akreditasi/kontrol/hub.html templates/akreditasi/kontrol/emr.html templates/akreditasi/kontrol/risiko.html templates/akreditasi/kontrol/dokumen.html
git diff --cached --check
git diff --cached --stat
git commit -m "fix(control): improve typography and explain dashboard scope"
```

### Task 8: Verify the rendered UI, not only CSS text

**Artifacts:** scratch browser HTML, results, and screenshots; `docs/qa/control-readability-registration-verification.md`.

- [ ] Use the `django-layout-verification` skill. Check available browser tooling without installing anything first:

```bash
.venv/Scripts/python.exe -c "import importlib.util; print('playwright', bool(importlib.util.find_spec('playwright')))"
python -c "import importlib.util; print('playwright', bool(importlib.util.find_spec('playwright')))"
```

Expected: record which interpreter has Playwright. A missing project-venv package does not mean the Hermes interpreter lacks it. Use the available browser tool if neither has it; do not add a product dependency for this verification.

- [ ] Render the real authenticated views into scratch using the test-client fixture pattern from `RegistrationEntryTest`, `setup_databases`, and `teardown_databases` in `finally`. Assert SQLite `:memory:` before `django.setup()`. Serve real source assets, not stale hashed assets. Use synthetic fixtures only. Required scenarios:

| Scenario | Account / selected unit | Required result |
|---|---|---|
| Hub | `ADMIN_RS`, `POLI-PD` | Two-column desktop cards; complete headings and descriptions |
| Risk | `STAF`, `IGD` | Readable KPI labels and matrix, unchanged severity colors |
| Documents | `STAF`, `IGD` | Readable EP explanation and hospital-wide scope |
| EMR entitled | `STAF`, `IGD` | Exactly one registration row inside Unit Services, before KPIs and AI |
| EMR unmapped entitled | `STAF`, `ADMISI` | Registration still present; no fabricated daily patient list |
| EMR broad role | `ADMIN_RS`, `KOMITE-MUTU` | Registration visible, administrative daily-services empty state retained |
| EMR denied | `STAF`, `POLI-PD` | No registration row; current clinical link retained |
| Daily services | `STAF`, `IGD` | Larger table text; horizontal scroll confined to table wrapper if needed |

Render at `1440x900`, `1366x768`, `768x1024`, `390x844`, and `360x800`. Include a long synthetic unit name and zero/nonzero metrics. Populate matrix cells for every severity when measuring contrast. Any required document-route catalogue fixture belongs only in the temporary database.

- [ ] Run this browser-side evaluation after fonts load for each rendered scenario/viewport; it returns evidence rather than judging screenshots by impression:

```javascript
async () => {
  await document.fonts.ready;
  const visible = el => !!(el.getClientRects().length && el.getBoundingClientRect().height);
  const size = selector => [...document.querySelectorAll(selector)]
    .filter(visible).map(el => ({
      text: el.textContent.trim(),
      px: parseFloat(getComputedStyle(el).fontSize),
      lineHeight: getComputedStyle(el).lineHeight,
      color: getComputedStyle(el).color,
    }));
  const links = [...document.querySelectorAll('.layanan-entry')].filter(visible);
  const section = document.querySelector('.kontrol-layanan');
  const registration = document.querySelector('[data-service-action="pendaftaran"]');
  const kpis = document.querySelector('.kontrol-kpis');
  return {
    width: innerWidth,
    pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
    headings: size('h1, .panel-head h2'),
    labels: size('.kpi-label'),
    details: size('.kpi-foot, .layanan-entry-text small, .kontrol-caption'),
    metadata: size('.panel-hint, .kpi-scope, .layanan-date'),
    smallTargets: links.filter(el => el.getBoundingClientRect().height < 44)
      .map(el => el.textContent.trim()),
    clippedServices: links.filter(el => el.scrollWidth > el.clientWidth + 1)
      .map(el => el.textContent.trim()),
    registrationCount: document.querySelectorAll('[data-service-action="pendaftaran"]').length,
    registrationInsideServices: registration ? section.contains(registration) : null,
    registrationHref: registration ? registration.getAttribute('href') : null,
    servicesBeforeKpis: section && kpis ? !!(section.compareDocumentPosition(kpis)
      & Node.DOCUMENT_POSITION_FOLLOWING) : null,
  };
}
```

Expected: `pageOverflow=false`, empty `smallTargets`/`clippedServices`, operational labels at least 14px, details at least 14px, compact metadata at least 13px. On entitled EMR, registration count is one, `registrationInsideServices=true`, `servicesBeforeKpis=true`, and href equals the reversed registration path without query parameters. On denied/non-EMR cases, registration count is zero.

- [ ] Verify keyboard traversal: visible focus reaches registration, Enter follows the real route, no nested control intercepts it. Verify `pendaftaran_dashboard` via Django client as in Task 3; a static HTML preview alone is not a navigation E2E result.

- [ ] Inspect saved desktop and 360px screenshots. Measure foreground/background contrast for normal text at >=4.5:1, large text at >=3:1; composite translucent backgrounds, reject NaN/infinite ratios, preserve matrix colors. Confirm fonts actually loaded using `document.fonts.check`, not merely the CSS family declaration.

If a browser or required asset is unavailable, report that gate as blocked and retain the passing server/CSS evidence separately. Do not label a string-based CSS test a completed visual audit.

### Task 9: Regenerate collected assets and close verification

- [ ] Run the complete focused gate and system check:

```bash
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django test akreditasi.tests_kontrol_navigation akreditasi.tests_kontrol_workspace akreditasi.tests_kontrol_workspace_style akreditasi.tests_kontrol_registration akreditasi.tests_kontrol_dasbor akreditasi.tests_kontrol_render akreditasi.tests_layanan_unit accounts.tests_unit_rbac accounts.tests_sidebar_visibility pasien.tests_route_rbac --verbosity 1
DJANGO_SETTINGS_MODULE=config.control_test_settings .venv/Scripts/python.exe -m django check
```

Expected: `OK`, exit code 0; system check has no errors. Record actual test count and query-budget results. These migration-disabled tests do not certify PostgreSQL migration readiness.

- [ ] Collect static assets using production static storage while replacing the database before Django initialization:

```bash
.venv/Scripts/python.exe -c "import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from django.conf import settings; settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}; import django; django.setup(); from django.core.management import call_command; call_command('collectstatic',interactive=False,verbosity=1)"
```

Expected: exit code 0; manifest includes the new processed workspace stylesheet. Do not run `collectstatic` under `config.control_test_settings`, which deliberately uses a different static storage backend.

- [ ] Validate collected CSS with this exact command:

```bash
.venv/Scripts/python.exe -c "import gzip,json; from pathlib import Path; r=Path('staticfiles'); m=json.loads((r/'staticfiles.json').read_text(encoding='utf-8')); key='css/kontrol-workspace.css'; p=r/m['paths'][key]; assert p.is_file(); assert (r/key).read_bytes()==Path('static/css/kontrol-workspace.css').read_bytes(); text=p.read_text(encoding='utf-8'); assert 'font: 16px/1.6' in text; assert '.layanan-entry-registration' in text; z=Path(str(p)+'.gz'); assert not z.exists() or gzip.decompress(z.read_bytes())==p.read_bytes(); print('PASS',m['paths'][key])"
git diff --check
git status --short
git diff --stat
```

Expected: `PASS` with the actual manifest filename, whitespace check exit code 0, and only planned source/generated changes in the feature diff. A changed font URL inside the hashed CSS is expected Django post-processing, not a source mismatch.

- [ ] Rerender one desktop and one mobile EMR fixture with collected assets. Repeat the computed-style checks to catch stale manifest references.

- [ ] Write `docs/qa/control-readability-registration-verification.md` with actual commands, exit codes, measured sizes/overflow/contrast, entitlement cases, screenshot paths, interpreter version discrepancy, and any blocked checks. Clearly separate server tests, rendered component checks, and any true browser navigation testing. Do not claim production verification or global regression success from this focused gate.

- [ ] Conditional final commit checkpoint: stage the exact generated paths listed by `git status` plus the new QA report, review `git diff --cached --stat` and `git diff --cached --check`, then commit with `chore(control): collect readable workspace assets and record QA`. Never use a wildcard that sweeps unrelated static changes or untracked work.

## Risks, tradeoffs, and open questions

1. **Permission scope:** ordinary poli users cannot register under the existing policy. This plan deliberately preserves that boundary. If the requester expects every clinical user to register, obtain a separate explicit RBAC requirement and role/unit matrix before changing `accounts/models.py`.
2. **Hospital-wide destination:** registration opens a hospital-wide desk, not a selected-unit-prefilled form. Honest scope copy is cheaper and safer than inventing a filter the destination ignores. Unit-prefilled registration is outside scope.
3. **Readability versus density:** larger labels and full explanations increase card heights and vertical scrolling. Preserve clear wrapping instead of shrinking text to fit a fixed-height card.
4. **Shared partial:** registration must remain EMR-only even though the services markup is shared. Injecting a distinct context action avoids adding registration to every portal or altering existing toolbar ordering.
5. **Template ordering:** moving services before KPIs improves access to the requested menu but pushes metrics lower. Keep the existing contextual toolbar and avoid a second registration link above it.
6. **CSS specificity:** the legacy stylesheet has many explicit sizes and some mobile overrides. Source tests are not enough; computed styles at all target widths are required.
7. **Known adjacent issue — do not implement, do not fix while here:** the existing bed row in `_layanan_unit.html` is not gated exactly like the newer clinical toolbar and describes a unit scope despite a broader destination. Do not expand this registration task into a bed-permission redesign. Record any observed problem for separate work.
8. **Known adjacent issue — do not implement, do not fix while here:** zero/dash presentation, malformed unit query handling, snapshot aggregation semantics, catalogue changes, and broad historical-suite failures are separate concerns. Preserve baseline behavior and report regressions caused by this change only.
9. **Environment mismatch:** installed Django is `6.1.1`, whereas requirements pin `6.1.2`; focused test evidence must identify the runtime actually used. Reproducible pinned-version release testing remains an explicit follow-up if not available during execution.
10. **No deployment authority:** this plan includes no push, live migration, seed operation, or production change. Deploy only after a separate user instruction.

## Acceptance checklist

- [ ] Integrated Control retains its current brand/layout but uses the specified readable typography and visible explanations.
- [ ] CPPT, PPA, RTL, and EP have plain-language explanations in relevant screens.
- [ ] Entitled users see exactly one `Pendaftaran pasien` entry inside EMR Unit Services before KPI/AI content.
- [ ] The entry opens the existing registration dashboard without unsupported query parameters.
- [ ] Entitled unmapped admission users and hospital-wide roles retain the entry.
- [ ] Non-entitled users do not see it and still receive HTTP 403 at the direct destination.
- [ ] Risk/documents/daily-services/hub pages do not gain registration entries from the shared partial.
- [ ] Existing unit confinement, HC grants, contextual actions, AI contract, severity colors, and query ceilings remain intact.
- [ ] Source tests, computed-style/viewport checks, and collected-asset checks pass, with real evidence recorded.
- [ ] No unrelated user work is staged, removed, reformatted, or committed.
