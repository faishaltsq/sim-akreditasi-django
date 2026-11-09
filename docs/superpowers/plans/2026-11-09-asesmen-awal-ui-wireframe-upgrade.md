# Implementation Plan — IGD Initial Assessment UI/UX Upgrade (ICD, 3S, Editable Tariff & Accreditation EP)

**Source Document:** `penyempurnaan rancangan modul asesmen awal icd slki dan tarif 8 11.docx`
**Date:** 2026-11-09
**Target Repo:** `sim-akreditasi-django` (master branch)
**Stack:** Django 5, Bootstrap 5.3.3, jQuery/Vanilla JS, Supabase PostgreSQL / SQLite test database.

---

## 1. Executive Summary & Context

The source document outlines the upgraded clinical interface and business logic for the Emergency Department (IGD) Initial Clinical Assessment. It emphasizes:
1. Clear demarcation between **Section B: Medical Assessment (Doctor)** and **Section C: Nursing Care Process 3S (SDKI - SLKI - SIKI) (Nurse)**.
2. Direct dynamic selection with **AI / System Suggestion chips** (`💡 AI Suggestion`) for ICD-10 and ICD-9.
3. Multi-item selected lists for Diagnoses (ICD-10 & SDKI) and Outcomes (SLKI), each equipped with source badges (`Master`, `AI Suggested`, `Manual`), accreditation EP links (`🔗 EP`), and inline edit/delete.
4. Auto-loaded reference tariff (Umum vs BPJS) for both Medical procedures (ICD-9-CM) and Nursing interventions (SIKI) with in-row inline price overrides and mandatory reason notes.
5. Unified System Summary: Total estimated procedure cost breakdown (Medical + Nursing) and Accreditation Audit Compliance badge with list of fulfilled EPs.

### Relationship with Logbook Non-Medis Module
While the Logbook Non-Medis module (`LogbookNonMedis`) focuses on administrative, non-clinical departmental daily SOP compliance and risks, both modules feed into ARIMA's overarching **Accreditation Evidence Engine (`StandardItem`)**:
- Non-Medical units map to standards like `TKRS`, `MFK`, `KPS`, and `PMKP`.
- Clinical assessments map directly to clinical standards: `PAP` (Patient Care), `SKP` (Patient Safety), `ARK` (Admission & Continuity), and `PP` (Patient Assessment).

---

## 2. Gap Analysis: Specification vs Current Implementation

| Feature / UI Component | Wireframe / Docx Spec | Current Implementation in Repo | Action Required |
|---|---|---|---|
| **Section B (Doctor)** | Separate Card: ICD-10 + ICD-9 + Subtotal Medis | Mixed in Tab 4 under single generic cards | Split & reconstruct Section B in template |
| **ICD-10 Diagnosis List** | Multi-item row with Edit, Master/AI badge, EP link | Single `<input type="text" name="diagnosa_masuk">` | Implement dynamic diagnosis items with EP link |
| **AI Suggestion Chips** | Chips for ICD-10 (`[A09] [R50.9]`) & ICD-9 (`[96.07] [99.18]`) | Backend `saran_untuk` exists (`/api/saran-icd/`), but no UI chips | Add interactive chips that populate items on click |
| **Section C (Nurse 3S)** | Separate Card: SDKI + SLKI + SIKI + Subtotal Keperawatan | Flat text fields for SDKI/SLKI/SIKI; SIKI mixed into ICD-9 table | Dedicated Section C with 3S cascading auto-select |
| **SDKI & SLKI Multi-item** | Selected list with Source badge, EP link, Edit/Delete | Flat string fields in `KunjunganPasien` | Multi-entry data structure / JSON or relationship with EP |
| **SIKI Tariff & EP** | Interventions with editable tariffs & EP status | Handled generically under `TindakanAsesmen` (`jenis='SIKI'`) | Group SIKI under Section C with subtotal display |
| **Rekapitulasi System** | Total cost (Umum/BPJS) + Compliance list (`ARK 3.1, PAP 2.1, ... 🟢`) | Mini alert in `_tindakan_tarif_ep.html` | Rich system recap box at the bottom of assessment form |

---

## 3. Phased Implementation Roadmap

### Phase 1: Data Contracts & Backend Cascading (TDD)
- **Task 1.1:** Extend `saran_untuk` service to support both ICD-10 suggestions and ICD-9 procedure suggestions simultaneously per clinical case group.
- **Task 1.2:** Implement API endpoint `/pasien/api/3s-cascade/` that accepts an SDKI code and returns recommended SLKI outcomes and SIKI interventions with default tariffs and EP rules from `Pemetaan3S`.
- **Task 1.3:** Unit tests for suggestion and 3S cascade endpoints.

### Phase 2: Section B (Doctor) UI Enhancement
- **Task 2.1:** Create `templates/pasien/_asesmen_seksi_b_dokter.html`:
  - ICD-10 search input with datalist + manual modal.
  - Suggestion chips dynamically fetched from `/pasien/api/saran-icd/?jenis=ICD10`.
  - Selected diagnosis rows with source badge, EP badge, edit and delete.
  - Medical procedures (ICD-9-CM) with suggestion chips, inline editable tariff, and Subtotal Medis counter.

### Phase 3: Section C (Nurse 3S) UI Enhancement
- **Task 3.1:** Create `templates/pasien/_asesmen_seksi_c_perawat.html`:
  - SDKI diagnosis search with chips and manual input.
  - Cascaded SLKI luaran items.
  - SIKI nursing interventions with editable price box, EP selector, and Subtotal Keperawatan counter.

### Phase 4: System Recapitulation & Save Integration
- **Task 4.1:** Build `templates/pasien/_asesmen_rekap_akreditasi.html`:
  - Live calculation: Subtotal Medis + Subtotal Keperawatan = Total Estimasi Biaya.
  - Live badge indicator: Fulfilled EPs (`TERPENUHI 🟢`), warning on unverified or missing EPs.
- **Task 4.2:** Integrate into `_asesmen_awal_wizard.html` and `igd_dashboard.html` (modal).
- **Task 4.3:** Ensure backward compatibility with existing `KunjunganPasien` and `TindakanAsesmen` persistence handlers.

### Phase 5: Verification & Quality Gates
- **Task 5.1:** Run automated test suites:
  - `python manage.py test pasien klinis --keepdb`
- **Task 5.2:** Browser / DOM smoke testing on assessment wizard and IGD dashboard modal.
- **Task 5.3:** Validate no regression on existing billing sync (`BillingItem`) and accreditation records.
