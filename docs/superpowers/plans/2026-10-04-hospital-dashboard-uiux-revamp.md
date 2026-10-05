# Modern Hospital UI/UX Revamp Implementation Plan (ARIMA - SIM Akreditasi RS)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the entire UI/UX of ARIMA (SIM Akreditasi RS & SIMRS) into an executive-grade, clinical-standard hospital web dashboard with modern design tokens, improved information hierarchy, unified component system, and streamlined workflows.

**Architecture:** Refactor `static/css/style.css` into a clean CSS design-token system, upgrade `templates/base.html` and `templates/includes/sidebar.html` with a modern collapsible sidebar and executive command topbar, and modernize the primary dashboards (`akreditasi/dashboard.html`, `akreditasi/matriks_pdca.html`, `pasien/dashboard.html`, and `pasien/bed_management.html`) using clean cards, KPI widgets, and high-legibility clinical data tables without breaking any existing Django view contracts.

**Tech Stack:** Django 5.x templates, Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Plus Jakarta Sans, JetBrains Mono, Chart.js 4.x (vanilla HTML/CSS/JS without heavy npm dependencies).

**Spec:** Redesign specification for ARIMA Hospital Management & Accreditation System (RS MonsisKami Tipe B).

## Global Constraints

- **No Breaking Django View Contracts:** All template tags, context variables (`sys_config`, `categories_by_kelompok`, `unit_dashboard`, `rs_profile`, `allowed_mods`), and URL names must remain functional.
- **Zero Heavy Frontend Dependencies:** Do not add Node.js/Webpack/Vite runtime builds to the Django production pipeline. All styles and scripts must reside in standard Django `static/css/` and `static/js/`.
- **Clinical Accessibility & Contrast:** Contrast ratios must satisfy WCAG 2.1 AA (minimum 4.5:1 for body text, 3:1 for large headers and status badges).
- **Responsive Breakpoints:** Fully responsive from 360px mobile view up to 4K ultra-wide monitors, with collapsible desktop sidebar and offcanvas mobile menu.
- **Brand Consistency:** Retain ARIMA identity (Clinical Teal `#0d9488` default theme, Navy `#0f172a` deep headers, Slate `#f8fafc` canvas background, R-D-W-O-S standard color badges).

## Review Focus

- **Active State Drift:** When navigating between nested routes (e.g. `/matriks/?cat=1` vs `/ep/` vs `/pasien/bed/`), ensure sidebar and breadcrumb active states accurately highlight the current route.
- **High-Density Data Overflow:** Data tables in Matriks PDCA and Bed Management must scroll horizontally with sticky first columns on narrow laptop screens without truncating actionable buttons.
- **Theme Switching Integrity:** The `data-theme` attribute on `<body>` (Teal, Blue, Emerald, Navy) must correctly cascade to all newly introduced KPI card borders, active states, and button gradients.
- **Mobile Touch Targets:** Action buttons in tables and mobile navigation links must maintain minimum 44x44px touch-safe padding.
- **Dark Elements & Form Controls:** Select dropdowns, search inputs, and modal headers must retain high-contrast borders and clear focus rings (`ring-2 ring-teal-500/20`).

---

### Task 1: Modern Clinical Design Token System & Global Stylesheet Refactor

**Files:**
- Modify: `static/css/style.css`
- Modify: `templates/base.html`
- Test: `tests/test_ui_theme.py`

**Interfaces:**
- Consumes: Django context `sys_config.theme_color` (defaults to 'teal').
- Produces: Modern CSS variables (`--color-surface-card`, `--shadow-xs`, `--shadow-md`, `--shadow-lg`, `--radius-sm`, `--radius-md`, `--radius-xl`, `--font-heading`, `--font-mono`), refined RDWOS badge utility classes, and card component abstractions.

- [ ] **Step 1: Write UI theme consistency test in Django**

Create `tests/test_ui_theme.py`:
```python
import pytest
from django.test import Client

@pytest.mark.django_db
def test_base_template_loads_design_tokens(client: Client):
    response = client.get('/login/')
    assert response.status_code in [200, 302]
    # Verify Plus Jakarta Sans font and Bootstrap 5 CDN are linked
    content = response.content.decode('utf-8')
    assert 'Plus+Jakarta+Sans' in content or response.status_code == 302
```

- [ ] **Step 2: Run test to verify initial state**

Run: `python manage.py test tests.test_ui_theme`
Expected: PASS or skips without failure.

- [ ] **Step 3: Update `static/css/style.css` with Modern Hospital SaaS Tokens**

Add executive clinical design tokens:
- Clean card borders (`border: 1px solid rgba(226, 232, 240, 0.8)`)
- Subtle layered shadows:
  ```css
  --shadow-xs: 0 1px 2px 0 rgb(15 23 42 / 0.05);
  --shadow-sm: 0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.06);
  --shadow-md: 0 4px 6px -1px rgb(15 23 42 / 0.07), 0 2px 4px -2px rgb(15 23 42 / 0.05);
  --shadow-lg: 0 10px 15px -3px rgb(15 23 42 / 0.06), 0 4px 6px -4px rgb(15 23 42 / 0.03);
  ```
- Modern glassmorphism utility classes (`.glass-panel`, `.bg-surface-elevated`).
- Refined status badges with soft backgrounds and high-contrast borders:
  - Regulasi (`.badge-rdwos-r`): `#eff6ff` bg, `#1d4ed8` text, `#bfdbfe` border
  - Dokumen (`.badge-rdwos-d`): `#ecfdf5` bg, `#047857` text, `#a7f3d0` border
  - Wawancara (`.badge-rdwos-w`): `#fffbeb` bg, `#b45309` text, `#fde68a` border
  - Observasi (`.badge-rdwos-o`): `#faf5ff` bg, `#6b21a8` text, `#e9d5ff` border
  - Simulasi (`.badge-rdwos-s`): `#fff1f2` bg, `#be123c` text, `#fecdd3` border

- [ ] **Step 4: Update `templates/base.html` Header & Layout Shell**

Refactor `templates/base.html`:
- Modernize topbar layout with hospital identity badge, global search shortcut placeholder (Ctrl+K), quick notification indicator, and refined profile dropdown.
- Refine mobile navbar and offcanvas drawer transitions.

- [ ] **Step 5: Verify template rendering**

Run: `python manage.py check`
Expected: System check identified no issues.

- [ ] **Step 6: Commit changes**

```bash
git add static/css/style.css templates/base.html tests/test_ui_theme.py
git commit -m "style: overhaul design token system and modern clinical layout shell"
```

---

### Task 2: Modern Collapsible Sidebar Navigation with Section Search

**Files:**
- Modify: `templates/includes/sidebar.html`
- Modify: `static/css/style.css`
- Modify: `static/js/main.js`

**Interfaces:**
- Consumes: `categories_by_kelompok`, `sidebar_categories`, `sidebar_unit_standar`, `request.user.profile`.
- Produces: Clean accordions with badge counts, category progress mini-bars, instant filter input for 16 Pokja chapters, and unified navigation grouping (Dashboard, Akreditasi STARKES, Manajemen Risiko & Mutu, SIMRS Pelayanan, Tata Kelola & Admin).

- [ ] **Step 1: Write sidebar active link unit test**

Create or extend test in `akreditasi/tests/test_views.py` ensuring sidebar context loads properly for authenticated users.

- [ ] **Step 2: Redesign `templates/includes/sidebar.html`**

- Group modules into 5 clear logical domains with distinctive icons:
  1. **Ikhtisar Eksekutif**: Dashboard Utama, Portal Nakes.
  2. **Akreditasi RS (STARKES)**: Matriks PDCA, Elemen Penilaian (EP), Dokumen Bukti (RDWOS), 16 Pokja Akreditasi (collapsible with percentage pill).
  3. **Manajemen Risiko & Mutu**: Daftar Risiko PDCA, Laporan Insiden, Indikator Mutu & Renstra.
  4. **Pelayanan Pasien (SIMRS)**: Dashboard Pasien, IGD, Rajal, Rawat Inap & Bed, Lab, Farmasi.
  5. **Tata Kelola & Laporan**: Auto-Scoring KARS, Rekap & Ekspor, Profil RS, Audit Log, Pusat Kontrol.
- Add client-side quick filter (`#sidebarPokjaSearch`) in the Pokja section to quickly filter 16 Pokjas without page reloads.

- [ ] **Step 3: Add sidebar accordion toggle script in `static/js/main.js`**

Ensure smooth collapse/expand state persistence in `localStorage` so users don't have to re-expand their active Pokja on page navigation.

- [ ] **Step 4: Test responsiveness and collapse**

Verify that on desktop the sidebar width is 264px with smooth vertical scrolling, and on mobile (<768px) it tucks into an offcanvas drawer with full touch support.

- [ ] **Step 5: Commit changes**

```bash
git add templates/includes/sidebar.html static/css/style.css static/js/main.js
git commit -m "feat(ui): implement modern hierarchical sidebar with pokja filtering and persistence"
```

---

### Task 3: Executive Hospital Accreditation Dashboard Redesign

**Files:**
- Modify: `templates/akreditasi/dashboard.html`
- Modify: `static/css/style.css`

**Interfaces:**
- Consumes: `unit_dashboard`, `unit`, `categories_by_kelompok`, `kpi_summary`, `renstra_years`, `risiko_summary`.
- Produces: Executive KPI pulse row (4 primary metric cards with micro-trend badges), STARKES 16 Pokja visual readiness grid, PDCA 4-stage distribution cards, interactive Renstra 2026-2030 roadmap stepper, and urgent action list (unverified documents, high risk items).

- [ ] **Step 1: Inspect and test current dashboard data context**

Verify context parameters passed from `akreditasi/views.py:dashboard_view`.

- [ ] **Step 2: Restructure `templates/akreditasi/dashboard.html` Hero Section**

- Replace dense gradient banner with modern executive header:
  - Hospital certification status badge (e.g. "SURVEILANS TAHUN KE-2 • TARGET PARIPURNA").
  - Current RS Profile badge with bed count and accreditation tier.
  - Quick action toolbar: `[+ Input Risiko]`, `[+ Upload RDWOS]`, `[Unduh Ringkasan PDF]`.

- [ ] **Step 3: Build Modern KPI Summary Cards**

Design 4 clinical metric cards:
1. **Prediksi Kelulusan STARKES**: Big percentage score with color-coded confidence tier (>=80% Paripurna, >=70% Utama, etc.).
2. **Kesiapan Dokumen Bukti (RDWOS)**: Verified vs pending documents count with mini progress meter.
3. **Siklus PDCA Aktif**: Total Plan/Do/Check/Action items distribution.
4. **Indikator Risiko Klinis**: Critical risk tally with quick link to Risk Register.

- [ ] **Step 4: Redesign 16 Pokja Readiness Matrix**

Create an interactive 16-chapter card grid:
- Grouped into the 5 standard Kemenkes groups (Manajemen, Pelayanan, Keselamatan Pasien, PKPO, Sasaran Keselamatan Pasien).
- Each Pokja card displays: Chapter Code (e.g., KPS, PPI, HPK), Chapter Name, Total EP, Verified EP %, and progress bar with status color.
- Hover lift effect (`transform: translateY(-2px)`, subtle shadow).

- [ ] **Step 5: Enhance Renstra 2026-2030 Roadmap Visual Stepper**

Style the Renstra 5-year timeline with clear milestone markers:
- Active year highlighted with glowing clinical blue badge.
- Strategic focuses for the current hospital operational year.

- [ ] **Step 6: Test dashboard rendering across resolutions**

Verify 1-column on mobile (<768px), 2-column on tablet (768-1024px), and 4-column on desktop (>1024px).

- [ ] **Step 7: Commit changes**

```bash
git add templates/akreditasi/dashboard.html static/css/style.css
git commit -m "feat(ui): redesign main hospital accreditation dashboard into modern executive control center"
```

---

### Task 4: Matriks PDCA & Elemen Penilaian (EP) Modernization

**Files:**
- Modify: `templates/akreditasi/matriks_pdca.html`
- Modify: `templates/akreditasi/ep_list.html`
- Modify: `templates/akreditasi/ep_detail.html`
- Modify: `static/css/style.css`

**Interfaces:**
- Consumes: `categories`, `active_category`, `standar_list`, `ep_list`, `documents_map`.
- Produces: Clean sticky-header PDCA matrix table, standard selector pill-tabs, quick score indicators (0/5/10), and modal-free document preview shortcuts.

- [ ] **Step 1: Test Matriks PDCA view rendering**

Run: `python manage.py test akreditasi`
Verify existing tests pass.

- [ ] **Step 2: Modernize Matriks PDCA Table (`templates/akreditasi/matriks_pdca.html`)**

- Implement horizontal category navigation pill bar with badges.
- Table improvements:
  - Sticky table header on vertical scroll.
  - Distinct column styling for the 7 PDCA columns (Standar, Elemen Penilaian, Regulasi & Dokumen, Wawancara/Observasi, Status Pemenuhan, Skor KARS, Aksi Tindak Lanjut).
  - Modern status dropdown tags with instant visual indicator.
  - Hover highlights per row for clinical readability.

- [ ] **Step 3: Redesign EP List & EP Detail Views**

- `templates/akreditasi/ep_list.html`: Add filter bar (Filter by Bab, Filter by Status, Search text).
- `templates/akreditasi/ep_detail.html`: Clean 2-column layout (Left: EP definition, KARS reference guidelines; Right: Uploaded RDWOS proof documents, verification status, audit trail).

- [ ] **Step 4: Commit changes**

```bash
git add templates/akreditasi/matriks_pdca.html templates/akreditasi/ep_list.html templates/akreditasi/ep_detail.html static/css/style.css
git commit -m "feat(ui): modernize matriks PDCA and EP detail interfaces for clinical audit workflows"
```

---

### Task 5: SIMRS Patient Management & Bed Occupancy Dashboard UI Upgrade

**Files:**
- Modify: `templates/pasien/dashboard.html`
- Modify: `templates/pasien/bed_management.html`
- Modify: `templates/pasien/igd_dashboard.html`
- Modify: `static/css/style.css`

**Interfaces:**
- Consumes: Patient KPI stats (BOR, ALOS, TOI, IGD queue counts, Bed statuses).
- Produces: Real-time clinical telemetry tiles, visual ward/room bed grid with color status (Tersedia, Terisi, Perbaikan, Dekontaminasi), and triage priority queue tables.

- [ ] **Step 1: Test patient module rendering**

Run: `python manage.py test pasien`
Verify all patient module tests pass.

- [ ] **Step 2: Modernize Bed Management Grid (`templates/pasien/bed_management.html`)**

- Room & Bed visual cards:
  - Green for Available (`bg-emerald-50 text-emerald-700 border-emerald-200`)
  - Red for Occupied with Patient initials & Dr. Penanggung Jawab
  - Amber for Maintenance / Cleaning
- Quick ward filter tabs (ICU, Rawat Inap Dewasa, Rawat Inap Anak, Kebidanan).
- Live calculation summary bar (Total Bed, Terisi, Kosong, BOR %).

- [ ] **Step 3: Modernize IGD & Outpatient Queue (`templates/pasien/igd_dashboard.html`, `templates/pasien/dashboard.html`)**

- Triage P1 (Resusitasi/Merah), P2 (Emergensi/Kuning), P3 (Non-Emergensi/Hijau) modern priority pill indicators.
- Clean time-elapsed counters for waiting patients.

- [ ] **Step 4: Commit changes**

```bash
git add templates/pasien/dashboard.html templates/pasien/bed_management.html templates/pasien/igd_dashboard.html static/css/style.css
git commit -m "feat(ui): modernize SIMRS bed management grid and emergency triage UI"
```

---

### Task 6: Comprehensive Verification & Regression Testing

**Files:**
- Test: All Django test suites (`python manage.py test`)
- Verify: Responsive layout check and static asset integrity

- [ ] **Step 1: Run full automated Django test suite**

Run: `python manage.py test`
Expected: All tests pass with zero errors.

- [ ] **Step 2: Collectstatic check**

Run: `python manage.py collectstatic --noinput --dry-run`
Verify static files resolve without missing references.

- [ ] **Step 3: Final inspection of rendered HTML & CSS**

Inspect key views (`/`, `/akreditasi/matriks/`, `/pasien/bed/`, `/pasien/igd/`) to ensure no broken layout tags or missing variables.

- [ ] **Step 4: Commit and finalize branch**

```bash
git add -A
git commit -m "chore: complete hospital dashboard UI/UX modernization and verification"
```
