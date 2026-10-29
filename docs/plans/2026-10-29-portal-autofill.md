# Part B - Auto-fill for Portal Credential Submission Form

This is the lightweight auto-fill for the portal version (`pengajuan_saya.html`), where there is no employee dropdown and the employee is always the logged-in user.

## Functional Requirements
1. **Auto-load unit kerja from employee profile** – when the page loads, automatically select the employee’s current unit kerja from the employee profile.
2. **Profile panel** – show Nama, NIP, Profesi, Jabatan, Jenjang, Masa Kerja, plus a list of STR/SIP statuses (like `credential_profile`, but using the same JSON endpoint).
3. **Badge** – small badge beside the Unit Kerja field indicating if the unit is auto-filled or manually changed.
4. **Manual override** – the employee’s unit is still editable, and when they change it the badge updates to "Manual change".
5. **Smart validation** – block the form if the employee’s legal status is unusable (STR/SIP expired/inactive) and surface the error on the Unit Kerja field with clear guidance.

## Condition Checks
- The form already has a `unit_kerja` field.
- The view (`kredensial_pengajuan_sendiri`) always has an employee bound to `request.user.pegawai_hc`.
- The form already uses `PengajuanPortalForm` (defined in `sdm/forms/kredensial_portal.py`), which auto-fills unit_kerja from the employee’s placement; the badge is the new element to add.
- The employee cannot pick a unit that is outside their active placements.

## Steps
1. **Add badge + profile panel before the form**
   - Insert the following structure just before the `<form>`:
     ```html
     <div class="d-flex align-items-center gap-2 mb-2">
         <span class="badge bg-secondary" data-kredensial-portal-badge hidden></span>
     </div>
     <div class="alert alert-light border small mb-3" data-kredensial-portal-panel hidden></div>
     ```
   - This matches the same styling as the HC form but with `portal` identifiers.

2. **Add JS script** (`static/js/hc-kredensial-portal-autofill.js`)
   - Fetch employee profile from `/kredensial/pegawai/<id>/profil.json`.
   - Render a summary panel (Nama, NIP, Profesi, Jabatan, Jenjang, Masa Kerja, licenses).
   - Fill unit_kerja if the employee’s current unit is within the employee’s grant.
   - Update badge to indicate auto-fill or manual change.
   - Display legal status warnings in the panel.

3. **Update view** (`sdm/views.py`)
   - Ensure `profile` is passed to the template (already done).
   - Optionally store the badge state in the session/request for later display.

4. **Integrate validation** (already in `PengajuanKredensialForm.clean()`) – check STR/SIP and block submission with a field error on `unit_kerja` (consistent with the HC form).

5. **Add badge and panel to the portal form** (`templates/sdm/kredensial/pengajuan_saya.html`)
   - Insert the HTML snippet (step 1) before the `<form>`.
   - Add script include (step 2) at the bottom of the page.
   - Change `unit_kerja` widget class to `data-kredensial-unit='1'` (optional but nice for selector).

## JSON Payload (Same as HC form)
```json
{
  "employee_id": "uuid",
  "nama": "...".
  "nomor_pegawai": "...".
  "profesi": "...".
  "jabatan": "...".
  "jenjang": "...".
  "masa_kerja": "...".
  "unit_kerja": {"id": "uuid", "code": "IGD", "name": "Instalasi Gawat Darurat"},
  "licenses": [
    {"subtype": "STR", "label": "Berlaku", "nomor": "...", "berakhir": "..."},
    {"subtype": "SIP", "label": "Kadaluwarsa", "nomor": "...", "berakhir": "..."}
  ]
}
```

## Technical Details
- The JSON endpoint is the same as HC: `/kredensial/pegawai/<employee_id>/profil.json`.
- The script uses the `fetch` API; if the response is not OK, we clear the panel and show a danger badge.
- For manual override detection, we store the originally auto-filled unit id and compare when the unit select changes.
- The badge uses Bootstrap classes `bg-success` (auto-filled), `bg-info` (manual), `bg-warning` (out-of-scope), `bg-danger` (error).

## Testing Points
- Auto-fill when employee has a single active unit.
- Manual change updates badge and persists.
- Edit page shows panel and unit value.
- Submit with missing STR/SIP shows field error on employee or unit.
- Unit not in grant shows warning badge (out of scope).

## Styling Notes
- The panel is an `alert alert-light border small mb-3`.
- The badge is `badge bg-...`.
- The badge is absolutely placed or inline, depending on design.

## Future Extensibility
- Reuse this pattern for other forms (I guess).
- Keep the badge independent of UI state; allow other modules to read the original auto-filled unit id for, e.g., audit logs.

---

## Summary
- **Goal**: Give portal users immediate context, less friction, and clear hints about legal status – no need to scroll.
- **Approach**: Borrow the design and logic from the HC form, simplify employee selection, keep security boundaries.
- **Outcome**: Less manual typing, easier navigation, and better error handling for employees submitting their own RKK.