# Plan: Implement Incident Safety Management System (IKP STARKES PMKP)

## 1. Goal
Complete Phase 1 Task 1: Build the Incident Safety Management Register (`/insiden/daftar/`), Detail View (`/insiden/<id>/`), and Investigation Status Workflow (`/insiden/<id>/update-status/`) to meet STARKES PMKP 6 & Permenkes 11/2017 standards.

## 2. Scope
1. **Views & Routing** (`akreditasi/risiko_views.py`, `akreditasi/urls.py`):
   - `insiden_daftar`: Paginated table of all reported incidents, filterable by unit, incident type (KNC/KTD/KTC/SENTINEL), severity level, and investigation status. Includes summary stats (total, by status, sentinel alert).
   - `insiden_detail`: Comprehensive view of the incident, including reporter details (if non-anonymous), immediate actions taken, risk grading badge, investigation assignment, and linkage to RCA.
   - `insiden_update_status`: POST endpoint for Komite Mutu / Tim KP to update investigation status (DILAPORKAN -> VERIFIKASI -> INVESTIGASI -> SELESAI), assign PJ, and flag RCA requirement.
2. **Templates** (`templates/akreditasi/`):
   - `insiden_daftar.html`: Modern, accessible table with badge indicators, stat cards, filter bar, export/print view, and direct link to report new incident.
   - `insiden_detail.html`: Incident breakdown card, risk matrix badge (Biru/Hijau/Kuning/Merah calculated from severity), timeline, investigation notes, and status update modal.
3. **Navigation & Sidebar** (`templates/akreditasi/base.html` / `navbar.html`):
   - Update navigation links from bare `/insiden/lapor/` to `/insiden/daftar/` with quick-actions.
4. **Automated Testing** (`akreditasi/tests_insiden.py`):
   - Test listing with filters.
   - Test detail view permissions.
   - Test status update POST.
   - Test anonymous vs non-anonymous handling.

## 3. Verification Steps
1. Run local test suite via `python manage.py test akreditasi.tests_insiden`.
2. Run security and regression tests (`tests_security.py`).
3. Deploy to production via git push & verify Vercel deployment.
4. Verify `/insiden/daftar/` live in browser.
