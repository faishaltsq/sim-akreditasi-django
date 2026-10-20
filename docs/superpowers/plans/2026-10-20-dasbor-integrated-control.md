# Implementation Plan: ARIMA HOSPITAL INTEGRATED CONTROL (Executive Dashboard)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-bleed executive landing layer — `ARIMA HOSPITAL INTEGRATED CONTROL / Executive Dashboard for Quality, Risk & EHR Integration` — that opens into three sub-dashboards (`Integrated Risk & Patient Safety Control + AI`, `Smart EMR & Clinical Quality STARKES + AI`, `Electronic Accreditation Document & Automation Hub + AI`), each rendered per sample unit **without the sidebar**, and each linking into the modules that already exist. No new data model; every number is read from tables already in production.

**Architecture:** A new module pair, `akreditasi/kontrol_data.py` (snapshot builders — pure functions over ORM querysets, no rendering) and `akreditasi/kontrol_views.py` (views + access control), following the split the codebase already uses for `indikator_views.py`, `risiko_views.py`, `mutu_laporan.py`. `akreditasi/views.py` is ~2832 lines and must not grow. Presentation uses a separate shell, `templates/akreditasi/kontrol/base_kontrol.html`, that does **not** extend `templates/base.html` — `base.html` hard-wires the sidebar in two places (`base.html:38` offcanvas, `base.html:57` desktop aside) and has no block to suppress it, so extending it would require editing the shared shell every app page depends on. One new POST endpoint `/ai/kontrol-ringkasan/` reuses `ai_service.py` and the existing `ep_write`-style rate-limit drawer pattern for the "+AI" narrative.

**Status:** Planned 2026-10-20 — not implemented. Nothing below has been written yet.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3 (already loaded by `base.html`, re-declared in the new shell), Chart.js (same CDN pattern as `dashboard.html`), `reportlab` untouched. **No new pip package, no migration.**

**Spec:** `C:\Users\cubeb\Downloads\judul Dasbor Utama terbaik yang profesional.docx` — title, subtitle, three sub-dashboard names with parenthetical scope, one instruction ("Untuk setiap Unit Contoh; dasbor tanpa tulisan Side, selanjutnya masuk ke yang sudah ada"), and a sentence asking for a hospital photo as background. The only media file in that docx (`word/media/image1.png`) is a **screenshot of the current IGD dashboard**, not an asset — see `docs/qa/analisis-dasbor-integrated-control-2026-10-20.md`.

## What the docx asks for, and what already exists

| docx requirement | Existing equivalent | Verdict |
|---|---|---|
| Executive front door, title + subtitle | `dashboard` (`views.py:399`) is PDCA/EP-oriented and sidebar-bound | **New page.** Keep `dashboard` untouched — it is the working surface for PDCA/EP. |
| Risk control center | `RisikoUnit`, `TindakLanjutRisiko`, `InsidenKeselamatan` (`risiko_models.py:18/473/529`) | **Reuse**, aggregate only. |
| Quality indicator profile | `IndikatorMutu`, `CatatanIndikator` (`risiko_models.py:585/737`), `CatatanIndikator.tercapai` | **Reuse.** Never re-derive the comparator. |
| Safety culture | No dedicated model. Proxy = incident reporting rate + RTL completion | **Derive, label as proxy.** Do not invent a score and call it culture. |
| Smart EMR | `pasien.KunjunganPasien`, `CPPT`, `AsesmenRisikoKlinis`, `ResepElektronik`, `DischargeRecord`, `Bed`/`BookingKamar` | **Reuse**, aggregate only. |
| PPA compliance | `accounts.NakesCredential` via `rekap_kps_unit` (`views.py:1826`) | **Reuse the queryset shape**, not the view. |
| Accreditation evidence hub | `StandardItem`, `EvidenceReq`, `EvidenceFile`, `QualityRecord`, `Category` (`models.py:154/171/242/194/85`) | **Reuse.** |
| Per-unit variant, no sidebar | `UnitKerja` + `profile.is_unit_scoped` scoping already exists | **New shell**, existing scoping. |
| "+ AI" | 14 endpoints in `ai_views.py`, client in `ai_service.py` | **Reuse service**, add one aggregate endpoint. |
| Hospital photo background | No `static/img/` directory exists in the repo | **Blocked on asset** — CSS gradient + SVG skyline ship first (Task 3.2). |

## Global Constraints

- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `85,0`; a comma inside `<script>` or a CSS value breaks the block (bugs `84c20ce`, `c4c2a3c`). Every new template loads `{% load l10n %}`.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.** (Standing project rule.)
- **Do not extend `base.html` for these pages, and do not add a "hide sidebar" flag to it.** One shared shell edit risks every page in the app. `base_kontrol.html` is standalone.
- **Scope resolution is imported, not re-implemented:** `akreditasi/akses_indikator.py` → `unit_scope_ids()`, `indikator_aktif_scoped()`. A second scope resolver is a bug factory.
- **`UserProfile.is_unit_scoped` is a read-only property**, not a field. Tests arrange it through `user.is_superuser`, `profile.role`, `profile.unit_kerja`.
- **`ROLE_CHOICES` is exactly** `SUPER_ADMIN, ADMIN_RS, KOORDINATOR_POKJA, KEPALA_UNIT, STAF_NAKES, ASESOR`. Do not reference `DIREKTUR` or `SURVEYOR_INTERNAL` — both are stale literals.
- **Empty is not zero.** A metric with no rows renders `Belum ada data` with a muted style. Rendering `0%` when there is no denominator is a correctness bug, not a cosmetic one.
- **`staticfiles/` is intentionally tracked for the Vercel build.** After any CSS/JS change run `collectstatic` and commit the hashed artifacts + `staticfiles.json`. Never delete that directory.
- **No migration in this plan.** Nothing here adds a field or table; if a task seems to need one, the design is wrong — stop and raise it.
- **`akreditasi/views.py` must not grow.** New views live in `kontrol_views.py`; only the URL wiring and one sidebar entry touch existing files.

## Query budget (hard gate)

Each rendered page must stay within **12 queries** against the primary DB, measured with `assertNumQueries` on a seeded unit. Snapshot builders take an already-fetched unit object and never query inside a loop. Cache the built snapshot per `(unit_id, user_scope, date)` for 60 seconds via `django.core.cache`.

---

## Phase 1 — Snapshot data layer

**Deliverable:** `akreditasi/kontrol_data.py`, no templates.

- [ ] **Task 1.1 — Snapshot contract.** Define `build_unit_snapshot(unit) -> dict` returning exactly these keys, each either a value or `None` (never `0` for "unknown"): `risk_total`, `risk_by_level`, `risk_overdue_rtl`, `incident_total_12m`, `incident_by_grade`, `incident_open`, `indicator_total`, `indicator_on_target`, `indicator_below_target`, `indicator_avg_pct`, `laporan_pending`, `emr_admissions_active`, `emr_cppt_gap`, `emr_risk_assessment_gap`, `bed_occupancy_pct`, `ppa_total`, `ppa_compliant`, `ep_total`, `ep_filled`, `ep_without_evidence`, `evidence_total`, `evidence_expiring`. Document each key with the source model and filter in a module docstring.
- [ ] **Task 1.2 — Risk + incident builder.** Aggregate `RisikoUnit` by level, count `TindakLanjutRisiko` past deadline, group `InsidenKeselamatan` by `tingkat_keparahan` and count non-terminal statuses. Use `values().annotate(Count)` — no per-row Python loops.
- [ ] **Task 1.3 — Indicator builder.** Reuse `CatatanIndikator.tercapai` for on-target counts and `IndikatorMutu.agregat_capaian()` for the average; filter through `indikator_aktif_scoped(profile)` when a profile is passed, else hospital-wide.
- [ ] **Task 1.4 — EMR builder.** Read from `pasien` models only: active `KunjunganPasien`, CPPT coverage gap per active admission, `AsesmenRisikoKlinis` coverage, bed occupancy from `Bed`/`BookingKamar`. If a field needed for a metric does not exist on the model, mark the metric `None` and note it — do not fabricate a proxy silently.
- [ ] **Task 1.5 — Accreditation builder.** `StandardItem` totals per `Category`, `QualityRecord` filled count, `EvidenceReq` without `EvidenceFile`, evidence past its validity window.
- [ ] **Task 1.6 — Derivation helpers.** `safety_proxy(snapshot)` and `status_band(value)` (e.g. `>=90` good, `70-89` watch, `<70` critical). One place, unit-tested, so every card colours identically.
- [ ] **Task 1.7 — Cache wrapper.** `snapshot_cached(unit, profile)` — 60s TTL, key includes unit id and scope ids hash. Bust by key version constant only.

## Phase 2 — Shell and design system

**Deliverable:** `templates/akreditasi/kontrol/base_kontrol.html` + `static/css/kontrol.css`.

- [ ] **Task 2.1 — Standalone shell.** Own `<head>`, Bootstrap 5.3 + Bootstrap Icons from the same CDN set `base.html:8` uses, CSRF meta, `{% block content %}`. No sidebar, no offcanvas. Slim top bar: brand mark, unit switcher (`<select>` that GETs the same route with another `unit_id`), and `Masuk ARIMA` button → `{% url 'akreditasi:dashboard' %}`.
- [ ] **Task 2.2 — Background strategy.** Default: layered CSS — deep teal→ink gradient plus an inline SVG hospital skyline silhouette, `background-attachment: fixed`, `@media (prefers-reduced-motion)` respected. Optional photo layer: `static/img/kontrol/hero-hospital.webp` when it exists, applied via `--hero-photo` custom property; when the file is absent the gradient shows and nothing breaks. Do **not** reference a filename that may not ship.
- [ ] **Task 2.3 — Tokens.** Port the palette from `base.html` (`--border`, `--radius-lg`, `--shadow`, `--text-muted`) so the new pages do not look like a different product. Add `--kontrol-ink`, `--kontrol-teal`, `--kontrol-amber`, `--kontrol-rose` for the three status bands.
- [ ] **Task 2.4 — Card primitives.** `.kc-card` (glass panel), `.kc-metric` (label, big numeral, delta), `.kc-portal` (large clickable portal card with icon + description), `.kc-empty` (`Belum ada data`). Numerals use `font-variant-numeric: tabular-nums`.
- [ ] **Task 2.5 — Accessibility pass.** Contrast ≥ 4.5:1 on the gradient, `:focus-visible` rings on portals, every portal card is a real `<a>` (not a div with onclick), `aria-current` on the active unit.
- [ ] **Task 2.6 — `collectstatic`** and commit the hashed `kontrol.*.css` + updated `staticfiles.json`.

## Phase 3 — Main hub

**Deliverable:** `/control/` → `kontrol_hub`.

- [ ] **Task 3.1 — View.** `kontrol_hub(request)`: pick unit from `?unit_id=` else first active unit with data; build snapshot; hand `portals` (3 dicts) + `units` + `snapshot` to the template. `@login_required`.
- [ ] **Task 3.2 — Hero.** Big title `ARIMA HOSPITAL INTEGRATED CONTROL`, subtitle `Executive Dashboard for Quality, Risk & EHR Integration`, live strip of 4 headline numbers (risiko ekstrem/tinggi, indikator di bawah target, EP tanpa bukti, laporan menunggu verifikasi) — each pulled from the snapshot, each with `Belum ada data` when `None`.
- [ ] **Task 3.3 — Portal cards.** Three cards, exact names from the docx, each with a one-line scope, a live sub-count, and `Link` → its sub-dashboard route. The word `Link` is what the docx asks for; render it as the button label, not a bare anchor.
- [ ] **Task 3.4 — Unit strip.** Horizontal list of sample units (`is_active=True`, has at least one risk/indicator/EP row) with mini status dot; clicking switches `?unit_id=`.
- [ ] **Task 3.5 — Access test.** Unit-scoped user requesting another unit's `?unit_id=` is redirected to their own unit, not shown a 403 wall.

## Phase 4 — Sub-dashboard 1: Integrated Risk & Patient Safety Control + AI

**Deliverable:** `/control/unit/<int:unit_id>/risiko/` → `kontrol_risiko`.

- [ ] **Task 4.1 — Layout.** Four KPI cards (risiko ekstrem/tinggi, insiden 12 bulan, RTL lewat tenggat, indikator di bawah target), risk matrix heat block (5×5 built from `RisikoUnit.dampak` × `RisikoUnit.probabilitas`, both validated 1–5), incident-by-grade bar from `InsidenKeselamatan.tingkat_keparahan` (Chart.js), indicator table sorted worst-first.
- [ ] **Task 4.2 — Safety strip.** Explicit proxy disclosure: "Budaya safety (proxy): rasio pelaporan insiden + ketuntasan RTL" — never labelled as a survey score.
- [ ] **Task 4.3 — Drill-down links.** Risiko → `akreditasi:risiko_daftar`, insiden → `akreditasi:insiden_daftar`, indikator → `akreditasi:indikator_dashboard`, each pre-filtered by unit where the target view supports it.
- [ ] **Task 4.4 — Empty state.** Seeded-empty unit renders every card as `Belum ada data` and the matrix as an empty grid with a link to `risiko_input`.

## Phase 5 — Sub-dashboard 3: Electronic Accreditation Document & Automation Hub + AI

**Deliverable:** `/control/unit/<int:unit_id>/dokumen/` → `kontrol_dokumen`. (Built before EMR: evidence data is the most stable, so the shared card/table components get proven on simpler data first.)

- [ ] **Task 5.1 — Coverage per chapter.** Horizontal bars: EP terisi / total per `Category`, label read from the DB (never hardcode "STARKES").
- [ ] **Task 5.2 — Evidence health.** Counts: `EvidenceReq` tanpa file, file kedaluwarsa, file menunggu verifikasi; table of the ten oldest gaps.
- [ ] **Task 5.3 — Document hub links.** `akreditasi:dokumen_hub`, `akreditasi:ep_list`, `akreditasi:matriks_pdca`, `akreditasi:laporan_mutu_daftar`.

## Phase 6 — Sub-dashboard 2: Smart EMR & Clinical Quality STARKES + AI

**Deliverable:** `/control/unit/<int:unit_id>/emr/` → `kontrol_emr`.

- [ ] **Task 6.1 — Census block.** Kunjungan aktif per jenis (RI/RJ/IGD), BOR, bed tersedia.
- [ ] **Task 6.2 — Clinical completeness.** CPPT coverage gap, `AsesmenRisikoKlinis` coverage, discharge planning pending — each as `x / y` plus percentage, each `None`-safe.
- [ ] **Task 6.3 — PPA compliance.** Compliant / total from `NakesCredential`, with link to `akreditasi:rekap_kps`.
- [ ] **Task 6.4 — Query budget check.** This page is the heaviest; assert ≤12 queries or split the aggregates into one `values().annotate()` pass per source model.

## Phase 7 — "+ AI" narrative

**Deliverable:** `POST /ai/kontrol-ringkasan/` in `ai_views.py` + a panel on all three sub-dashboards.

- [ ] **Task 7.1 — Endpoint.** Accept `unit_id` + `portal` (`risiko|emr|dokumen`), build the same snapshot server-side (never trust client numbers), send a compact JSON to `ai_service`, return `{ringkasan, temuan[], saran[]}`. Rate-limit with the existing shared drawer; return `429` JSON, never HTML.
- [ ] **Task 7.2 — Timeout.** Client timeout **45 s** — the Lambda `maxDuration` is 60 s; anything ≥60 gets truncated before the fallback tier runs (regression fixed in `ai_service.py`, `76a59c9`).
- [ ] **Task 7.3 — UI.** `AI Ringkas` button, spinner, inline render into the panel; on failure show the error detail, not "terjadi kesalahan".
- [ ] **Task 7.4 — Guard.** No API key, no model name, no prompt text in the response. Same discipline as every other `/ai/` endpoint.

## Phase 8 — Tests, polish, ship

- [ ] **Task 8.1 — `akreditasi/tests_kontrol.py`.** Cover: hub renders 3 portals with docx names; every metric matches a hand-computed fixture; `None` renders `Belum ada data` and never `0`; sidebar markup absent from hero pages (`assertNotContains 'sidebar-desktop'`); unit-scoped user cannot see another unit; `assertNumQueries(12)` per page; AI endpoint 429 on the 31st call; AI failure path returns JSON not HTML.
- [ ] **Task 8.2 — Responsive + print.** Verify at 1366×768, 1920×1080, 390×844 (mobile: portals stack, top bar collapses to brand + unit select). Print stylesheet: cards keep borders, gradient dropped, charts hidden with a numeric table fallback.
- [ ] **Task 8.3 — Motion.** One entrance animation on the hero (600 ms, transform + opacity), `prefers-reduced-motion` disables it. No parallax, no autoplaying carousels.
- [ ] **Task 8.4 — Full suite.** `manage.py test akreditasi` must stay green (currently 336 tests) plus the new module. `manage.py check` clean; `makemigrations --check` → `No changes detected`.
- [ ] **Task 8.5 — Sidebar entry.** One link "Control Room" → `akreditasi:kontrol_hub` in `templates/includes/sidebar.html`, visible to hospital-wide roles only.
- [ ] **Task 8.6 — Deploy.** Push to `master`, Vercel builds, then verify: `GET /control/` → 302 anonymous, 200 authenticated; `/control/unit/1/risiko/` → 200; bogus unit → 404. **No migration to run** — this plan adds no schema.

---

## Acceptance criteria

1. `/control/` renders the exact title and three sub-dashboard names from the docx.
2. No hero page contains sidebar markup; `Masuk ARIMA` reaches the existing dashboard in one click.
3. Every number on screen traces to a row in the DB, or shows `Belum ada data`. Nothing is hardcoded, nothing is estimated.
4. Unit-scoped users see only their unit, enforced server-side.
5. ≤12 queries per page, proven by `assertNumQueries`.
6. `manage.py test akreditasi` green, `check` clean, `makemigrations --check` empty.
7. Anonymous visitors get 302, never 500, on any control route.

## Open questions (blocking only where noted)

1. **Hospital photo** — needed for the literal "background ada gambar RS". Until supplied, Task 2.2 ships the gradient + SVG. Not blocking.
2. **"tanpa tulisan Side"** — interpreted as *no sidebar nav* on hero pages. If it meant removing a specific label inside the sidebar, that is a one-line change in Task 8.5 instead. Blocking only if the other reading is correct.
3. **"Unit Contoh" set** — currently derived (active + has data). If it should be a fixed list (e.g. IGD, Rawat Inap, ICU, Laboratorium), say which; otherwise the derived rule ships.
4. **Does `/control/` replace the current dashboard as the post-login landing page?** Plan keeps `dashboard` as-is and adds `/control/` beside it. Switching the post-login redirect is a separate one-line change and a product decision.

---

## Execution status — 2026-10-20

**Shipped (uncommitted at time of writing):**

| # | Task | State |
|---|------|-------|
| 1.1–1.7 | Snapshot layer | Done — `akreditasi/kontrol_data.py` (≈380 lines), nested keys `risk/incident/indicator/laporan/emr/ppa/ep`, every unknown is `None`. `snapshot_cached()` 60 s, `sample_units()` also cached. |
| 2.1–2.4, 2.6 | Shell + tokens + cards + collectstatic | Done — `templates/akreditasi/kontrol/base_kontrol.html`, `static/css/kontrol.css` (21 KB). Hashed artefak `staticfiles/css/kontrol.<hash>.css` + `staticfiles.json` ikut di-commit. |
| 3.1, 3.2, 3.3, 3.5 | Hub view + hero + portal cards + access | Done. |
| 4.1–4.4 | Risk portal | Done — KPI strip, 5×5 matrix from `dampak`×`probabilitas` (level per cell via `risk_level_for`), two `safety_proxy` figures, drill-down links. Incident bar chart **not** built (numbers shown instead of a Chart.js canvas). |
| 5.3 | Document portal links | Done. |
| 5.1, 5.2 | Coverage bars per `Category`, evidence health table | **Not built** — document portal shows RS-wide EP gauge + evidence counts only. |
| 6.1, 6.3, 6.4 | Census, PPA, query budget | Done. |
| 6.2 | Discharge planning pending | **Not built** — no reliable field on `KunjunganPasien`. |
| 7.1–7.4 | AI briefing | Done — `POST /control/ringkasan-ai/`, `@rate_limit(6/jam, scope='kontrol_ai')`, snapshot rebuilt server-side, JSON error surfaces real message. |
| 8.1 | Tests | Done — `akreditasi/tests_kontrol_dasbor.py`, 13 tests, query budget via `CaptureQueriesContext` (7 queries warm vs budget 12). |
| 8.4 | Suite + checks | Done — see log below. |
| 8.5 | Sidebar entry | Done — "Integrated Control" first item in `templates/includes/sidebar.html`. |
| 2.5, 8.2, 8.3 | A11y focus rings, print stylesheet, entrance animation | **Partial/none** — halos `:focus` default Bootstrap; tidak ada print CSS, tidak ada entrance animation. |
| 8.6 | Deploy | Pending. |

### Deviations from the written plan

1. **Routes** are `/control/`, `/control/risiko/`, `/control/emr/`, `/control/dokumen/`, `/control/ringkasan-ai/`. The plan's `/control/unit/<id>/risiko/` shape was dropped: unit is a query parameter, and unit-scoped accounts are forced server-side.
2. **Post-login landing changed**: `LOGIN_REDIRECT_URL = 'akreditasi:kontrol_hub'` (answer #4 from the operator). `akreditasi:dashboard` is untouched and still reachable from the top bar.
3. **Background**: no hospital photo (none supplied) and no external image — self-made SVG skyline (`<svg viewBox="0 0 1440 640">`) baked into the shell, so nothing can 404.
4. **Rate limit**: reused the in-house `akreditasi.security_utils.rate_limit`, not `django-ratelimit` (that package is not a dependency).
5. **`pct` semantics**: EP coverage is `None` while zero items are scored, so the UI says "Belum ada data" instead of a misleading `0%`.
6. **`Bed` and `StandardItem` have no FK to `UnitKerja`** — bed occupancy and EP coverage are labelled `RS-wide` in the UI and forbidden to the AI prompt as unit figures.

### Verification log

```
manage.py check                                  → no issues (1 silenced)
manage.py makemigrations --check --dry-run       → No changes detected
manage.py test akreditasi.tests_kontrol_dasbor   → Ran 13 tests … OK
manage.py test akreditasi accounts               → (isi di bawah saat selesai)
```
