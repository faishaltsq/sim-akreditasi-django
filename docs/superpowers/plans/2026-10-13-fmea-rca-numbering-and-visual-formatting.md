# Implementation Plan: FMEA & RCA Numbering and Visual Formatting Polish

- **Date:** 2026-10-13
- **Author:** Apex (All-Role Engineering Operator)
- **Status:** Completed
- **Module:** Manajemen Risiko (Risk Management) - FMEA / RCA Section

## Executive Summary
In response to user feedback regarding unformatted text and unclear numbering sequences in the Failure Mode (FMEA) & RCA input form (attached `image_330e16.png`), we improved the typography, automated numbering sequence formatting, and added visual structured card previews.

## Objectives & Acceptance Criteria
1. **Clear Numbering Hierarchy**:
   - Primary numbering: `1. MODE KEGAGALAN:`, `2. MODE KEGAGALAN:`, etc.
   - Secondary indented lettering:
     - `a. Efek Potensial:`
     - `b. Akar Masalah / Penyebab:`
     - `c. Barrier / Kontrol Pencegahan:`
   - Clear line spacing (`\n\n`) between modes to prevent cramped display.
2. **One-Click Auto-Formatter**:
   - Provide a "Rapihkan Nomor" button (`#btn-format-fmea`, `#btn-format-rca`, `#btn-format-tindakan`) that parses raw or existing text and auto-formats it cleanly.
   - Automatically format LLM AI suggestions upon return.
3. **Enhanced Input Experience**:
   - Disable browser spellcheck red squiggles (`spellcheck="false"`).
   - Use comfortable typography with monospace alignment (`font-size: 0.82rem; line-height: 1.65; rows="9"`).
4. **Structured Visual Cards**:
   - Add dynamic structured preview cards beneath the textarea with color-coded callouts:
     - Red for potential effects
     - Amber for root causes
     - Green for barriers & prevention controls
   - Display cards in detail view and dedicated FMEA/RCA view via template filters (`render_fmea_cards`, `render_rca_whys`).

## Modified Components
1. `akreditasi/ai_prompts.py`:
   - Updated `PROMPT_FMEA_SUGGESTION` and `PROMPT_RCA_SUGGESTION` to enforce hierarchical numbered outputs.
2. `akreditasi/ai_service.py`:
   - Added `normalize_fmea_text()` backend pipeline.
   - Formatted `generate_fmea_suggestion()` and `generate_rca_suggestion()`.
3. `templates/akreditasi/risiko_form.html`:
   - Added "Rapihkan Nomor" button and action handler.
   - Textarea styled with `font-monospace`, `rows="9"`, `spellcheck="false"`.
   - Added live structured preview cards (`#fmea-preview-wrapper`) with count badge and hide/show toggle.
4. `akreditasi/templatetags/akreditasi_tags.py`:
   - Added `render_fmea_cards` and `render_rca_whys` filters.
5. `templates/akreditasi/risiko_detail.html` & `templates/akreditasi/risiko_fmea_rca.html`:
   - Applied `render_fmea_cards` and `render_rca_whys` for pristine card rendering.
6. `akreditasi/tests_fmea_rca.py`:
   - Updated and aligned test assertions (27/27 passing).

## Verification
- Ran `python manage.py test akreditasi.tests_fmea_rca` -> 27/27 pass.
- Ran `python manage.py test akreditasi.tests_perencanaan_risiko` -> 13/13 pass.
- Verified parsing of both raw single-line strings and multiline formatted strings.
