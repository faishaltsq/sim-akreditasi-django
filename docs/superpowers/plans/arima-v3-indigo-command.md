# ARIMA V3 — Indigo Command Modernization Plan

Repo: `sim-akreditasi-django` (Django 5 + Bootstrap 5.3 + Chart.js, deployed on Vercel).
Goal: full UI/UX remake of the existing app with the Navy/Indigo/Violet system, zero feature regression.

## Architecture decisions (from inspection)

- Frontend is Django templates + Bootstrap 5.3.3 + `static/css/style.css` (single ~1,600-line
  sheet, already CSS-variable driven: `--primary`, `--primary-deep`, `--primary-light`,
  `--primary-tint`, `--sidebar-bg`, `--active-nav-bg`, theme selector on `body[data-theme]`).
  Therefore: **no framework migration.** Add one new layer file `static/css/v3-tokens.css`
  loaded *after* `style.css`, which redefines the token root for every `data-theme` value so the
  teal identity is replaced globally without touching 1,600 lines of legacy rules.
- Fonts: self-hosted `static/fonts/inter-latin.woff2`, `inter-latin-italic.woff2`,
  `manrope-latin.woff2` (downloaded from Google Fonts, variable subsets). Google Fonts
  `<link>` for Plus Jakarta Sans / JetBrains Mono removed from `base.html`.
- Sidebar is `templates/includes/sidebar.html` (`.sidebar-nav`, `.nav-section`, `.nav-link`,
  `.nav-icon/.nav-title/.nav-desc`) included twice (desktop aside + mobile offcanvas).
  Navigation links come from real `{% url %}` calls — preserved as-is.
- Context processor `akreditasi.context_processors.sidebar_context` supplies
  `categories_by_kelompok`, `sidebar_unit_standar`, `sidebar_categories`, `sys_config`,
  `rs_profile`. These keys must be preserved.
- Dashboard view `akreditasi.views.dashboard` supplies real metrics in two modes
  (unit-scoped and global). All KPI values must come from that context — no hardcoded mockup
  numbers.

## Steps

1. **Foundation** — `v3-tokens.css`: fonts, indigo token override for all themes, neutrals,
   type scale, 4px spacing scale, radii, shadows, focus ring, motion + reduced-motion,
   shell metrics (sidebar 248/72, topbar 68, content padding 24).
2. **Shell** — `base.html`: font swap, token link, brand block, collapsible sidebar with
   persisted preference (`v3-shell.js`), topbar breadcrumb slot, keep user pill + logout.
3. **Color de-teal** — one-time scripted remap of literal hexes in `templates/**` and
   `static/js/**` to V3 equivalents (hex literals in JS, `var()` in CSS/HTML). Excludes
   `v3-tokens.css`.
4. **Login** — two-column layout, preserve Django auth contract (CSRF, `next`, session).
5. **Dashboard** — KPI ribbon, readiness, document donut, risk heatmap, findings, deadlines,
   quick actions; all bound to existing context; role-aware branches on
   `profile.is_unit_scoped` / `profile.role`.
6. **Modules** — apply the shared component system page by page (matriks PDCA, EP list,
   dokumen hub, risiko, insiden, indikator, audit, pengguna).
7. **Global search** — add a real, permission-scoped `akreditasi:pencarian` endpoint (subset:
   EP, dokumen, risiko, unit, temuan) and wire it into the topbar. No fake input.
8. **QA** — `manage.py check`, existing 267-test suite, responsive breakpoints
   (390/768/1024/1440), keyboard/contrast audit.

## Baseline (measured before any edit)

- `manage.py check`: 0 issues.
- `manage.py test`: 267 tests, 1 failure + 5 errors (pre-existing; see QA section of final report).

## Non-goals

No schema changes, no business-logic rewrite, no new frontend framework, no teal identity,
no hardcoded dashboard figures, no removal of existing routes or buttons.
