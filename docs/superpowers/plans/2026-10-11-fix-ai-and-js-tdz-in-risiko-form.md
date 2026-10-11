# Implementation Plan: Fix AI Analysis & JavaScript Temporal Dead Zone (TDZ) in Risiko Form

**Date:** 2026-10-11  
**Project:** SIM Akreditasi RS (ARIMA v2.6)  
**Issue:** "ai nya tidak berfungsi" (AI Analysis button and dependent features unresponsive on `risiko/baru/`)

---

## 1. Root Cause Analysis

### Primary Defect: JavaScript Temporal Dead Zone (TDZ) Exception at Page Load
- In `templates/akreditasi/risiko_form.html`, line 616 calls `update()` immediately upon script execution.
- Function declarations (`updateRpn`, `updateResidual`) are hoisted in JavaScript.
- Inside `update()`, lines 612–613 invoke:
  ```javascript
  if (typeof updateRpn === 'function') updateRpn();
  if (typeof updateResidual === 'function') updateResidual();
  ```
- Inside `updateRpn()` (line 1236), it accesses:
  ```javascript
  if (!deteksiEl) return;
  ```
- However, `const deteksiEl = document.getElementById('deteksi_fmea');` is declared lexically at line 1230.
- Under ECMAScript specifications, `const` and `let` variables reside in the **Temporal Dead Zone (TDZ)** from the start of the block until their declaration line is executed.
- Accessing `deteksiEl` at line 616 throws:
  ```text
  Uncaught ReferenceError: Cannot access 'deteksiEl' before initialization
  ```
- **Consequence:** The entire JavaScript script immediately halts at line 616.
  - `#btn-ai-analisis-masalah` click event listener is NEVER attached (line 992).
  - `#input_masalah` live banner listener is NEVER attached (line 1145) — explaining why placeholder text remained visible in the user's screenshot.
  - Section C (FMEA/RCA) and Section F (Residual) listeners are NEVER attached.
  - Required field indicators and Category Guide chips are NEVER initialized.

### Secondary Defect: Typo in `static/js/ai-assist.js`
- Line 91 references `jenisInput` instead of `jenisInputs[0]`:
  ```javascript
  if (jenisInput) jenisInput.focus(); // ReferenceError: jenisInput is not defined
  ```
  If `btn-ai-mitigasi` is clicked without inputs, it crashes instead of safely focusing.

---

## 2. Proposed Changes

### Task 1: Refactor Variable Scope & Lifecycle in `risiko_form.html`
- Move all DOM element queries for Section B, C, D, E, F to the top of `DOMContentLoaded` or query dynamically / safely guard before first execution.
- Declare variables (`deteksiEl`, `dResEl`, `pResEl`, `detResEl`, `inputRpnFmea`, `rpnLiveBadge`, etc.) with `let` at the top of `DOMContentLoaded`.
- Guard `updateRpn()` and `updateResidual()` to ensure they only execute when elements are defined and safely initialized.
- Call initial `update()`, `updateRpn()`, and `updateResidual()` in orderly sequence AFTER all DOM declarations.

### Task 2: Fix ReferenceError Bug in `static/js/ai-assist.js`
- Change line 91 in `static/js/ai-assist.js` from `if (jenisInput) jenisInput.focus();` to:
  ```javascript
  if (jenisInputs.length && jenisInputs[0]) jenisInputs[0].focus();
  ```

### Task 3: Improve Visual Feedback & Error Handling on AI Button
- Ensure `#ai-analisis-feedback` is positioned prominently and scrolls into view if an error or status occurs.
- Add try/catch block surrounding the entire initialization script so that a failure in one section does not take down the entire form's event listeners.
- Ensure CSRF token lookup has a robust fallback (hidden form input first, then cookie).

### Task 4: Automated Testing & Verification
- Run Node.js headless DOM / syntax checker to guarantee 0 runtime exceptions during script initialization.
- Execute Django automated test suite `akreditasi/tests_reordered_flow_and_bab_seed.py` and `akreditasi/tests_manajemen_risiko_515.py`.
- Verify live behavior via curl / direct test script against local and production endpoints.

---

## 3. Verification Plan
1. **Node.js Initialization Test:** Execute synthetic DOM environment script simulating full `DOMContentLoaded` to verify no `ReferenceError` or `TypeError`.
2. **Django Test Suite:** All 6+ tests pass with exit code 0.
3. **Git Commit & Push:** Push fix to `master` and trigger Vercel deployment.
4. **Vercel Production Verification:** Check HTTP 200 on `sim-akreditasi-django.vercel.app/risiko/baru/`.
