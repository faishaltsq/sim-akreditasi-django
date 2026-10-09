# Implementation Plan: Link Background Problem & Supporting Data to Risk Category and Types

## Problem Statement
Based on `Downloads/Masalah di menu input resiko 1 10.docx`:
> "Latar belakang masalah dan bukti pendukung belum link dengan kategori resiko dan jenis resiko, ---lakukan perubahan supaya user melakukan input data resiko dan masalah dapat terus muncul di kategori dan jenis resikonya"

Users report that after typing the **Masalah (Issue Statement)** and **Data / Bukti Pendukung (Baseline Data)** in the risk form:
1. The problem context disappears or becomes disconnected as they move to select **Kategori Risiko** and **Jenis Risiko**.
2. There is no continuous visual linking showing how the entered problem directly maps to the selected Category and Risk Types.
3. In the Risk Registry (`risiko_daftar.html`), the underlying problem and baseline data are not visibly linked or displayed alongside the Risk Type and Category, making it difficult for unit heads to see the problem-to-risk lineage.

## Objectives
1. **Interactive Form Linking (`risiko_form.html`)**:
   - Add a dynamic, live-updating **"Problem Context Banner" (Konteks Masalah Terhubung)** directly above the Kategori Risiko & Jenis Risiko section that displays the currently typed problem & baseline data in real-time.
   - When users type in `input_masalah` or `input_data_pendukung`, the text mirrors instantly into the Category & Risk Type header pill/callout so it remains visible and referenced throughout the input process.
   - Provide a visual arrow/pipeline flow: `[Masalah Unit] ➔ [Kategori Risiko] ➔ [Jenis Risiko Teridentifikasi]`.
   - Ensure AI suggestions clearly annotate which parts of the problem statement generated each recommended risk type.

2. **Registry Lineage Display (`risiko_daftar.html`)**:
   - In the risk list table, display the underlying `masalah` as an informative sub-row or subtitle badge directly under each `jenis_risiko` item, showing the concrete hospital problem that produced the risk.
   - Add filter / search capability by `masalah`.

3. **Detail View Consistency (`risiko_detail.html`)**:
   - Reorder the detail page so the **Problem & Baseline Data Card** is explicitly framed as the root origin (`Akar Masalah / Latar Belakang`) directly linking to the Risk Matrix classification.

4. **Automated Verification**:
   - Update tests in `akreditasi/tests_manajemen_risiko_515.py` to assert that `masalah` and `data_pendukung` are properly associated with category and risk types in POST requests and table queries.

---

## Detailed Tasks

### Task 1: Add Dynamic Problem-to-Risk Link Banner in `risiko_form.html`
- Add a sticky or prominent "Konteks Masalah Terhubung" callout box right above Section A.3 (Kategori Risiko) and Section A.4 (Jenis Risiko).
- Wire real-time JS input listeners on `#input_masalah` and `#input_data_pendukung` to update the preview banner immediately as the user types.
- If empty, display a helpful hint: *"Ketik masalah & data pendukung di atas — konteksnya akan otomatis terhubung ke pemilihan kategori dan jenis risiko di sini."*
- If filled, show a clean, high-contrast badges:
  - 🔴 **Masalah Terhubung**: `[Excerpt of typed masalah]`
  - 🔵 **Bukti Pendukung**: `[Excerpt of baseline data]`

### Task 2: Display Problem Context Alongside Risk Type in `risiko_daftar.html`
- In the table column **Jenis Risiko**, render a small contextual block under the risk title:
  - If `r.masalah`: render `<div class="text-muted small mt-1" style="font-size: .72rem;"><i class="bi bi-exclamation-circle text-danger me-1"></i><strong>Masalah:</strong> {{ r.masalah|truncatechars:85 }}</div>`.
- In the table header/filter, ensure users can quickly identify risks originating from specific operational issues.

### Task 3: Strengthen Problem Lineage in `risiko_detail.html`
- Show the visual lineage pipeline at the top of the detail page:
  `[Masalah: ...] ➔ [Kategori: ...] ➔ [Jenis Risiko: ...] ➔ [Mitigasi: ...]`.

### Task 4: Run Tests & Live Browser Verification
- Run test suite `manage.py test akreditasi.tests_manajemen_risiko_515`.
- Deploy to Vercel via Git commit & push.
- Verify live rendering with headless Chrome CDP.
