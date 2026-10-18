# Plan: expose "Input Capaian" & "Edit Indikator" actions in Evaluasi and Monitoring pages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the Risiko Evaluasi page (G.1) and the Monitoring & Evaluasi page, give users a direct one-click entry to the master-indicator actions — "Input Capaian" (open the monthly capaian form) and "Edit Indikator" (open the indicator edit form) — using the *linked* indicator, so they do not have to leave the PDCA flow, find the indicator in the mutu catalog, and click twice. Nothing new is built for data: both routes and views already exist (`indikator_input_capaian`, `indikator_edit`); this plan only wires them in.

**Architecture:** Two new helper properties on `RisikoUnit` — `linked_indikator` (returns the linked `IndikatorMutu` or `None`) and `linked_indikator_pk` (its pk or `None`) — so templates can guard the buttons with a single `{% if r.linked_indikator %}` and emit `{% url 'akreditasi:indikator_input_capaian' r.linked_indikator_pk %}` without touching the view context. The buttons are gated on the same permission already used for those routes (`_is_manager`: `SUPER_ADMIN`, `ADMIN_RS`, `KOORDINATOR`, `KEPALA_UNIT`, superuser) — not on `is_unit_scoped`, because that would let a `KEPALA_UNIT` of a child unit edit an indicator that belongs to a sibling unit. The Monitoring page additionally gets a "Buka detail indikator" affordance on the indicator name so the same shortcut is reachable from the table without inflating the Aksi column. The Evaluasi page gets the two buttons in the G.1 header, next to the target badge, because that is where the indicator identity already lives.

**Tech Stack:** Django 6.1.1 (`.venv`), Bootstrap 5.3, vanilla JS. No migration, no new route, no new view, no new model.

**Spec:** screenshot `indikator-mutu/209/` — buttons "Edit Indikator" / "+ Input Capaian" exist on the indicator detail page but are absent from the PDCA Evaluasi and Monitoring flows.

## Where the two actions already live

| Action | Route | View | Gate |
|---|---|---|---|
| Edit Indikator | `akreditasi:indikator_edit` | `indikator_views.indikator_edit` | `_is_manager` |
| Input Capaian | `akreditasi:indikator_input_capaian` | `indikator_views.indikator_input_capaian` | `_is_manager` |

Both views fetch `IndikatorMutu` by pk and redirect non-managers to `indikator_dashboard` with an error message, so the template-level gate is a UX nicety, not a security boundary. The linked indicator is already reachable as `risiko.indikator_mutu_terkait` (monev) / `risiko.indikator_mutu_terkait_id` (evaluasi), but the template cannot ask for its pk in one expression without a helper.

## Global Constraints

- **No new route, no new view.** If a task cannot be done with the existing `indikator_edit` / `indikator_input_capaian` routes, it is out of scope.
- **Permission must match the destination.** Both buttons are rendered only when `_is_manager(user)` is true. The existing `_is_manager` helper (`akreditasi/indikator_views.py:122`) already covers the right set. Do not invent a second gate.
- **Do not break the print layout.** The Monitoring page is printable (`@media print`). New buttons must carry `no-print` so they vanish on paper.
- **Do not widen the Aksi column.** The monev table is already wide; the indicator-action buttons live on the indicator *name* cell and in the page header, not in the Aksi column.
- **No N+1.** Both views already `select_related('indikator_mutu_terkait')` (monev) and `select_related('unit', 'indikator_mutu_terkait', 'created_by')` (evaluasi). Verify before merging.
- **Locale rule still applies.** Any `float`/`Decimal` rendered into JS or CSS must use `|unlocalize` + `{% load l10n %}`. The buttons carry no numeric values, so this is a no-op here — but the surrounding indicator cell must keep its `|unlocalize` on target/capaian.
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — baseline 159 tests, 0 failures.

## Verified code facts (read 2026-10-18)

| Fact | Where |
|---|---|
| `RisikoUnit.indikator_mutu_terkait` FK, nullable, select_related everywhere | `akreditasi/risiko_models.py`, `risiko_views.py:783,977` |
| `_is_manager` covers SUPER_ADMIN, ADMIN_RS, KOORDINATOR, KEPALA_UNIT | `akreditasi/indikator_views.py:122-127` |
| `indikator_edit` / `indikator_input_capaian` routes exist | `akreditasi/urls.py:101-102` |
| Both views redirect non-managers to `indikator_dashboard` | `indikator_views.py:397,523` |
| Monev Aksi column already holds 4 buttons (Evaluasi, Detail, Edit, Hapus) | `risiko_monitoring_evaluasi.html` KOLOM 8 |
| Evaluasi G.1 header already holds the target badge (right side) | `risiko_evaluasi.html` around `:175-195` |
| `_log` writes percent sign hardcoded (`:.1f%`) — out of scope here | `indikator_views.py:436` (covered by the polarity plan) |

---

### Task 1: `linked_indikator` helper on `RisikoUnit`

- [x] **Step 1: Add the property** in `akreditasi/risiko_models.py`, right after `capaian_status_label` (or next to `capaian_evaluasi`), returning the linked indicator or `None`:

  ```python
  @property
  def linked_indikator(self):
      """The master IndikatorMutu this risk is tied to, or None.

      Centralised here so templates can guard + URL-build in one expression
      ({% if r.linked_indikator %}...{% url '...' r.linked_indikator.pk %}).
      """
      return self.indikator_mutu_terkait
  ```

  (Thin wrapper on purpose: `indikator_mutu_terkait` is the FK and is already select_related everywhere; the wrapper exists only to make the template contract explicit and to leave room for the access-matrix plan to swap the source later without touching templates.)

- [x] **Step 2: Tests** in `akreditasi/tests_risiko_indikator_actions.py` (new file):
  - `test_linked_indikator_none_when_not_tied` — a `RisikoUnit` with no linked indicator returns `None`.
  - `test_linked_indikator_returns_linked_master` — returns the same `IndikatorMutu` instance.

---

### Task 2: Evaluasi page (G.1) — add the two buttons

- [x] **Step 1: Locate the insertion point** — the G.1 header already has a right-hand block with the target badge (`templates/akreditasi/risiko_evaluasi.html`, around the `bg-white p-2 px-3 rounded-3 shadow-sm border` div). Place the buttons **above** that block, inside the same `d-flex ... justify-content-between` row, so they do not push the target badge down.

- [x] **Step 2: Render, manager-gated**

  ```django
  {% if is_manager and risiko.linked_indikator %}
  <div class="d-flex gap-2 flex-wrap">
      <a href="{% url 'akreditasi:indikator_edit' risiko.linked_indikator.pk %}"
         class="btn btn-sm btn-outline-primary" title="Edit Indikator Mutu">
          <i class="bi bi-pencil me-1"></i>Edit Indikator
      </a>
      <a href="{% url 'akreditasi:indikator_input_capaian' risiko.linked_indikator.pk %}"
         class="btn btn-sm btn-success" title="Input Capaian Bulanan">
          <i class="bi bi-plus-lg me-1"></i>Input Capaian
      </a>
  </div>
  {% endif %}
  ```

  Use the same classes as the indicator detail page (`btn-outline-primary` / `btn-success`) so the two pages look identical.

- [x] **Step 3: When the risk is *not* linked** to a master indicator, render a muted hint instead of the buttons: "Tautkan indikator mutu terlebih dahulu untuk membuka Input Capaian / Edit Indikator." This keeps the header from collapsing to an empty gap.

- [x] **Step 4: Tests** — render the evaluasi page for a manager with a linked indicator; assert both button URLs appear (`/indikator-mutu/<pk>/edit/` and `/indikator-mutu/<pk>/capaian/`). Render for a non-manager; assert neither URL appears.

---

### Task 3: Monitoring page — indicator name becomes a link + two small buttons

- [x] **Step 1: Make the indicator name clickable** in the "Indikator Mutu & Target" cell (`risiko_monitoring_evaluasi.html`, the `{{ r.indikator_mutu_terkait.nama_indikator }}` block). Wrap it in an `<a>` to `indikator_detail` when `r.linked_indikator` exists, opening in a new tab (`target="_blank" rel="noopener"`) so the MONEV table stays put. Keep the muted "Risiko: …" fallback for risks without a linked indicator.

- [x] **Step 2: Add two small buttons below the name**, manager-gated, `no-print`, opening in a new tab:

  ```django
  {% if is_manager and r.linked_indikator %}
  <div class="d-flex gap-1 mt-1 no-print">
      <a href="{% url 'akreditasi:indikator_edit' r.linked_indikator.pk %}" target="_blank" rel="noopener"
         class="btn btn-xs btn-outline-primary py-0 px-2" style="font-size:.68rem;" title="Edit Indikator">
          <i class="bi bi-pencil"></i>
      </a>
      <a href="{% url 'akreditasi:indikator_input_capaian' r.linked_indikator.pk %}" target="_blank" rel="noopener"
         class="btn btn-xs btn-success py-0 px-2" style="font-size:.68rem;" title="Input Capaian">
          <i class="bi bi-plus-lg"></i>
      </a>
  </div>
  {% endif %}
  ```

  Reuse the `btn-xs` + `monev-action-btn` classes already defined in this template so the buttons match the rest of the row.

- [x] **Step 3: Print-safety check** — `@media print` already hides `.no-print`. Verify the new buttons carry the class and that the print preview (manual or `window.print()` in headless) does not show them. Add a regression test that renders the page and asserts `no-print` is present on the button container.

- [x] **Step 4: Tests** — render the monev page for a manager with a linked indicator; assert both new URLs and `indikator_detail` appear. Render for a non-manager; assert the new URLs do not appear (the name link to `indikator_detail` stays, since detail is read-only).

---

### Task 4: Permission plumbing (one small view change)

- [x] **Step 1: Expose `is_manager` in the monev view context.** The evaluasi view already does (`ctx['is_manager']`? check — if not, add). The monev view does not pass it today, so the template gate cannot work without it. Add `'is_manager': _is_manager(request.user)` to the monev context dict. `_is_manager` lives in `indikator_views`; import it (or duplicate the 4-line helper) — prefer importing to keep one source of truth.

- [x] **Step 2: Tests** — `tests_risiko_indikator_actions.py` (or extend an existing monev test module) covers the context flag for a manager and a non-manager.

---

### Task 5: Verification & commit

- [x] **Step 1: Run `manage.py test akreditasi`** — must stay at 159 + new tests, 0 failures.
- [x] **Step 2: Render probe** — fetch `/risiko/<id>/evaluasi/` and `/risiko/monitoring-evaluasi/` via the test client for a manager user; grep the HTML for both new URLs and `no-print`.
- [x] **Step 3: `node --check`** on any inline JS touched (none expected, but run if a script block changed).
- [x] **Step 4: Commit** — `feat(indikator): surface Input Capaian / Edit Indikator in Evaluasi and Monitoring`. Push after Vercel green.

## Review Focus

- **Do not let a non-manager see the buttons.** The view already refuses the POST, but hiding the link is what keeps a `STAF` from even knowing the form exists. Both gates must agree.
- **Do not break the printable MONEV.** Every new affordance must be `no-print`; the print CSS already hides that class, but a missing class on one button shows up as a stray button on paper.
- **Access-matrix plan dependency.** `linked_indikator` is a thin wrapper over `indikator_mutu_terkait`. When `2026-10-18-inm-unit-access-matrix.md` lands and swaps the source of an indicator's "linked unit" to `IndikatorUnitTerlibat`, only this property changes — templates stay untouched. That is the whole point of the wrapper.
- **No new data.** If a task here starts creating a model, a migration, or a route, stop: it is out of scope and belongs in the polarity or access-matrix plan.
- **Do not touch `CatatanIndikator` or `nilai_capaian`.** This plan is read-only with respect to capaian data.
