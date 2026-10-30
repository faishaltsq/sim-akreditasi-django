# Implementation Plan: Logbook 36-Bulan Rekap Harian, Seleksi No. RM & Master Tindakan

**Status:** Draft / Ready for Implementation  
**Date:** 2026-10-30  
**Context:** SIM Akreditasi RS (ARIMA) — STARKES 2024 / Human Capital & Clinical Credentialing  

---

## 1. Executive Summary & User Analysis

### 1.1 User Intent & Context Analysis
Based on the two screenshots provided by the user:
- **Image 1 (`/human-capital/logbook/`):** Titled *"Logbook Tindakan Klinis (Rekap 36 bulan)"*, showing employee selection, quick-log form, and entry list.
- **Image 2 (`/logbook/2/`):** Titled *"Logbook Harian IGD · Pagi"*, showing shift metrics and the section *"Tindakan Klinis Shift (Rekap Kredensial & Logbook Saya)"*.

The user made three fundamental clarifications:
1. **"ini tdk usah dihapus, karema itu logbook 36 bulan, rekapan dari loghbook harian":**
   - The user previously requested removing "Logbook saya" from the sidebar menu to simplify navigation. However, the user now emphasizes that the 36-Month Logbook is essential and must NOT be removed from navigation.
   - It is the primary credentialing evidence portfolio (STARKES KPS standard) aggregating 36 months (3 years) of clinical practice for staff credentialing / re-credentialing (RKK).
   - Crucially, it serves as the **aggregation/recap destination** of actions logged during daily hospital shifts.
2. **"pakai pilih rm saja jangan nama pasien":**
   - In the clinical shift action recording form and display tables, patient identification must strictly use the **Medical Record Number (`No. RM`)**, never the patient's full name.
   - Rationale: Patient confidentiality, privacy regulations (MRMIK / HIPAA / Indonesian Ministry of Health PMK Rekam Medis), and professional portfolio privacy where full names must not leak into personnel audit trails.
3. **"tindakan klinisnya pilih itu yang ada dimaster/ database":**
   - In the shift action recording form, clinical actions must be selected **strictly from the master database catalog (`sdm.KatalogTindakan`)**.
   - Free-text input (`tindakan_bebas`) must be removed or prohibited. Actions must map directly to authorized clinical privileges (Rincian Kewenangan Klinis - RKK) so they contribute to verifiable competency tallies.

---

## 2. Architecture & Data Flow

```
+-------------------------------------------------------------+
|               Hospital Shift (IGD / Ranap)                  |
|                   `akreditasi.LogbookHarian`                |
+-------------------------------------------------------------+
                             |
                             v
   Shift Staff inputs Action on Shift Form (`logbook_detail.html`)
   - Select Patient: "No. RM: 123456 (Bed 01)" [NO PATIENT NAME]
   - Select Action : "PK-001 — Pemasangan Infus" [FROM MASTER DB]
   - Select Category: Mandiri (M) / Kolaborasi (K) / Supervisi (S)
                             |
                             v
+-------------------------------------------------------------+
|                Database: `EntriLogbookKlinis`               |
|  - employee: staff performing action                        |
|  - logbook_harian: LogbookHarian FK                         |
|  - logbook_pasien: LogbookPasien FK                         |
|  - pasien_ref: "RM123456" (Strictly RM only)                |
|  - katalog_tindakan: KatalogTindakan FK (Master DB)         |
|  - tindakan: '' (empty, strictly from catalog)              |
|  - jumlah_mandiri / kolaborasi / supervisi: (1 / 0 / 0)     |
+-------------------------------------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|           36-Month Rolling Aggregation Window               |
|           `sdm.services.logbook.logbook_recap()`            |
+-------------------------------------------------------------+
                             |
                             v
+-------------------------------------------------------------+
|         Portfolio Page: `/human-capital/logbook/`           |
|  - Metric Cards: Total 36 Bulan, Mandiri, Kolab, Supervisi  |
|  - Action Breakdown Table: Tally per RKK Catalog Item       |
|  - Detailed Historical Log: Filterable by Staff/Month       |
|  - Links back to Source Shift for verification              |
+-------------------------------------------------------------+
```

---

## 3. Detailed Scope of Changes

### Phase 1: Sidebar Navigation Restoration & Clarity
- **File:** `templates/includes/sidebar.html`
- **Actions:**
  - Restore the link under `{% if nav_kredensial_pribadi %}`:
    ```html
    <a href="{% url 'sdm:logbook_list' %}"
       class="nav-link{% if app == 'sdm' and u|slice:':7' == 'logbook' %} active{% endif %}"
       title="Catatan dan rekapitulasi tindakan klinis 36 bulan">
        <span class="nav-icon"><i class="bi bi-journal-text nav-icon-green" aria-hidden="true"></i></span>
        <span class="nav-text"><span class="nav-title">Logbook saya (36 bln)</span></span>
    </a>
    ```
  - Maintain `Logbook terpadu` under Mutu dan Kinerja (`akreditasi:logbook_daftar`).
  - Update `sdm/tests/test_nav_kredensial_pribadi.py` to assert both links exist and are accessible for healthcare staff.

### Phase 2: Shift Action Form — Patient Selection by No. RM Only
- **File:** `templates/akreditasi/logbook_detail.html`
  - In `Pilih Pasien`:
    Change option display from:
    `{{ b.nama_pasien }} (RM: {{ b.no_rm }})`
    To:
    `No. RM: {{ b.no_rm|default:"Tanpa No. RM" }}{% if b.no_bed %} · Bed {{ b.no_bed }}{% endif %}`
  - In `Tindakan Klinis Shift` table:
    Change column header from `PASIEN` to `NO. RM`.
    Change cell display to show only `No. RM: {{ tk.logbook_pasien.no_rm|default:tk.pasien_ref }}` (no patient full name).
- **File:** `akreditasi/logbook.py` (`logbook_simpan_tindakan`)
  - Ensure `pasien_ref` is populated strictly from `pasien_baris.no_rm`:
    ```python
    if pasien_baris:
        pasien_ref = pasien_baris.no_rm or (f"Bed {pasien_baris.no_bed}" if pasien_baris.no_bed else "RM Tidak Tercatat")
    ```
- **File:** `akreditasi/tests/test_logbook_tindakan_views.py`
  - Update assertion to confirm `pasien_ref` contains `'RM101'` and contains NO patient name.

### Phase 3: Shift Action Form — Strict Master Catalog Selection
- **File:** `akreditasi/logbook.py`
  - In `logbook_detail`: query `katalog_tindakan_pilihan` with `select_related('jenjang__profesi')` ordered by profession family, profession name, and action name.
  - In `logbook_simpan_tindakan`:
    - Require `katalog_id`.
    - If `not katalog`: reject with `messages.error(request, 'Pilih tindakan klinis dari master katalog tindakan.')`.
    - Disallow or ignore `tindakan_bebas` for shift entries so that every entry strictly links to `KatalogTindakan`.
- **File:** `templates/akreditasi/logbook_detail.html`
  - Replace datalist and text input with a clear, grouped `<select name="katalog_id" class="form-select form-select-sm" required>`:
    ```html
    <select name="katalog_id" class="form-select form-select-sm" required>
        <option value="">-- Pilih Tindakan Klinis (Master Database) --</option>
        {% regroup katalog_tindakan_pilihan by jenjang.profesi.nama as profesi_list %}
        {% for grp in profesi_list %}
        <optgroup label="{{ grp.grouper }}">
            {% for kat in grp.list %}
            <option value="{{ kat.id }}">{{ kat.kode }} — {{ kat.nama }}</option>
            {% endfor %}
        </optgroup>
        {% endfor %}
    </select>
    ```
  - Remove the input field for `tindakan_bebas`.

### Phase 4: 36-Month Recap Dashboard on Portfolio Page
- **File:** `sdm/views.py` (`logbook_list`)
  - Calculate `recap = logbook_recap(target, months=36)` if `target` exists.
  - Pass `'logbook_recap': recap` to `templates/sdm/logbook/daftar.html`.
- **File:** `templates/sdm/logbook/daftar.html`
  - Insert a 36-Month Recap KPI header card:
    - Total Tindakan 36 Bulan (with badge / icon)
    - Mandiri (M) count & percentage
    - Kolaborasi (K) count & percentage
    - Supervisi (S) count & percentage
    - Periode: `{{ logbook_recap.dari_tanggal|date:"d M Y" }} s/d Hari ini`
  - Add collapsible / accordion section: "Rincian Akumulasi per Tindakan RKK (36 Bulan)" displaying `logbook_recap.per_tindakan`.
  - In the table of entries, ensure the patient column shows `Inisial / No. RM` (strictly masked).
- **File:** `akreditasi/logbook.py` & `templates/akreditasi/logbook_daftar.html`
  - In Tab 2 (`?tab=saya`), provide the same 36-month recap metrics so the user sees the aggregated totals in the unified tab view as well.

### Phase 5: Verification & Automated Tests
- Run tests:
  - `sdm.tests.test_nav_kredensial_pribadi`
  - `akreditasi.tests.test_logbook_tindakan_views`
  - `akreditasi.tests.test_logbook_detail_template`
  - `akreditasi.tests.test_logbook_unified_view`
  - `sdm.tests.test_logbook`
  - `sdm.tests.test_logbook_kategori`
  - `sdm.tests.test_logbook_verifikasi`
- Run static collection & check:
  - `manage.py check`
  - `manage.py collectstatic --noinput`

---

## 4. Acceptance Criteria
1. **Sidebar Navigation:**
   - Healthcare staff sees "Logbook saya (36 bln)" under "Kredensial saya" in the sidebar.
   - Staff also sees "Logbook terpadu" under "Mutu dan kinerja".
2. **Patient Privacy (RM Only):**
   - Shift logbook dropdown displays only `No. RM: ...` and optional bed number. No patient names appear.
   - Shift action log table displays only `No. RM: ...`. No patient names appear.
   - `pasien_ref` stored in `EntriLogbookKlinis` contains only the medical record number or anonymous bed reference.
3. **Master Catalog Action Selection:**
   - The shift form requires selecting from the master database catalog (`KatalogTindakan`).
   - Free-text input is removed; entries without a valid catalog ID are rejected.
4. **36-Month Recap Visibility:**
   - `/human-capital/logbook/` displays clear 36-month aggregation metric cards (Total, Mandiri, Kolaborasi, Supervisi, and date range).
   - Any clinical action recorded in the shift logbook automatically appears in the employee's 36-month recap.
