# Plan: Risk Form — 3-Way Input (Menu / Manual / AI) per Field

**Source:** `Downloads/masalah di input resiko 8 10.docx`
**Date:** 2026-10-08
**Branch:** master

---

## Background / Problem Analysis

The docx specifies a new UX model for risk input:

> User inputs **Masalah** + **Data/Bukti Pendukung** first (already done).
> Then fills 5 fields, each supporting **3 ways**:
> 1. Pick from a **preset menu** (dropdown/chips from system data)
> 2. **Manual** free-text entry
> 3. Ask **AI** for a suggestion

**Current state vs target:**

| Field | Preset Menu | Manual | AI |
|---|---|---|---|
| Kategori Risiko | ✅ dropdown | ✅ | ✅ (via btn-ai-analisis-masalah) |
| Jenis Risiko | ✅ chips per kategori | ✅ ketik+tambah | ✅ (via btn-ai-analisis-masalah) |
| Indikator Mutu | ✅ dropdown by unit | ❌ **missing** manual input | ❌ **missing** AI suggest |
| Strategi Mitigasi | ✅ dropdown (ACCEPT/AVOID/etc) | ✅ | ❌ **missing** AI suggest |
| Rencana Aksi | ✅ preset chips per indikator | ✅ textarea | ✅ already has AI btn |

**Gaps to fix:**
1. **Indikator Mutu** — currently only a locked `<select>`; no way to enter manually if the unit has no data in the system. Need a toggle: "Pilih dari sistem" vs "Input manual nama indikator".
2. **Strategi Mitigasi** — no AI suggestion. When AI analyzes the problem, it should also suggest the best mitigation strategy.
3. **AI Analisis Masalah endpoint** — currently returns `kategori_risiko`, `jenis_risiko_list`, `deskripsi_risiko`. Need to also return `strategi_mitigasi_saran` and `indikator_mutu_saran` (name hint for search).
4. **UX clarity** — each section should show the 3-way toggle clearly so user knows they have 3 options.

---

## Scope

This plan covers **form UX only** (no new model fields, no new migrations).
All fields already exist on `RisikoUnit`. Only form template + AI prompt/endpoint response need to change.

---

## Tasks

### T1 — Update AI Prompt & Endpoint Response
**Files:** `akreditasi/ai_prompts.py`, `akreditasi/ai_service.py`, `akreditasi/ai_views.py`

Extend `PROMPT_ANALISIS_MASALAH_RISIKO` to also return:
```json
{
  "kategori_risiko_saran": "HUKUM_KEPATUHAN",
  "jenis_risiko_list": ["Kadaluarsa RKK", "Pelanggaran Kredensial"],
  "deskripsi_risiko_saran": "...",
  "strategi_mitigasi_saran": "REDUCE",
  "indikator_mutu_saran": "Kepatuhan Kredensial Nakes",
  "dampak_saran": 4,
  "probabilitas_saran": 3
}
```

Extend `api_ai_analisis_masalah_risiko` response to pass these new fields to frontend.

Extend `ai_views.py` JS handler in `risiko_form.html` to:
- Autofill `strategi_mitigasi` dropdown
- Show `indikator_mutu_saran` as a search hint in the indikator field

Add 1 test: `test_ai_analisis_masalah_returns_strategi_and_indikator_hint`

---

### T2 — Indikator Mutu: Add Manual Input Toggle
**Files:** `templates/akreditasi/risiko_form.html`

In Section C (Indikator Mutu), add a toggle switch:
```
[● Pilih dari Sistem]  [○ Input Manual]
```

- **Pilih dari Sistem** (default): shows current `<select id="indikator_mutu_select">` + preset chips
- **Input Manual**: hides the select, shows a text `<input name="indikator_mutu_manual" placeholder="Nama indikator mutu...">` + a hint "Indikator akan dicatat sebagai teks bebas"

Backend: `risiko_input` view already saves `indikator_mutu_terkait` as FK. Add fallback: if `indikator_mutu_terkait` empty but `indikator_mutu_manual` has text, save the text to `rencana_aksi` as a note prefix OR store in a new `indikator_mutu_manual` field.

**Decision:** Store manual indikator as text appended to `deskripsi_risiko` with a marker `[INDIKATOR: ...]` — no migration needed.

---

### T3 — Strategi Mitigasi: Add AI Suggestion Badge
**Files:** `templates/akreditasi/risiko_form.html`

After the AI Analisis button fires and returns `strategi_mitigasi_saran`:
- Auto-select the matching value in the `<select name="strategi_mitigasi">` dropdown
- Show a small teal badge next to the label: `✨ AI saran: REDUCE (Kurangi)`
- Badge disappears if user manually changes the dropdown

No new backend changes beyond T1.

---

### T4 — UX: 3-Way Mode Indicators per Section
**Files:** `templates/akreditasi/risiko_form.html`

Add a small `3-way legend` row to Sections A-D in the form:
```
Cara isi: [📋 Sistem]  [✏️ Manual]  [✨ AI]
```

- Icons are informational labels (not clickable), telling user which modes are available for that section
- For Indikator Mutu: the toggle from T2 IS the mode selector (clickable)
- This is pure HTML/CSS, no JS needed

---

### T5 — Tests + Push
**Files:** `akreditasi/tests_manajemen_risiko_515.py`

Add:
1. `test_ai_analisis_returns_strategi_saran` — POST to `/ai/analisis-masalah-risiko/` with masalah → response includes `strategi_mitigasi_saran` key
2. `test_risiko_input_manual_indikator` — POST form with `indikator_mutu_manual` text → verify saved correctly in deskripsi_risiko with marker

Run `manage.py test` → 116/116 expected.
Commit + push to master.
Deploy to Vercel auto via GitHub push.

---

## Order of Execution

```
T1 (prompt+endpoint) → T2 (form toggle) → T3 (AI badge) → T4 (UX legend) → T5 (tests+push)
```

T1 must be done before T3 (frontend needs new AI response fields).
T2 and T4 are independent of T1 (pure frontend).

---

## Files Modified

| File | Change |
|---|---|
| `akreditasi/ai_prompts.py` | Extend `PROMPT_ANALISIS_MASALAH_RISIKO` with 3 new output fields |
| `akreditasi/ai_service.py` | Pass new fields through in `generate_risk_analysis_from_problem` |
| `akreditasi/ai_views.py` | Return `strategi_mitigasi_saran`, `indikator_mutu_saran` in response JSON |
| `templates/akreditasi/risiko_form.html` | T2 toggle + T3 badge + T4 legend |
| `akreditasi/risiko_views.py` | Handle `indikator_mutu_manual` text in POST |
| `akreditasi/tests_manajemen_risiko_515.py` | 2 new tests |

**No migrations required.**

---

## Key Decisions

- **No new model fields** — manual indikator stored via `[INDIKATOR: ...]` marker in `deskripsi_risiko` to avoid migration and keep backward compat.
- **Strategi Mitigasi AI** — suggest only, never force; user can override dropdown after AI fills it.
- **3-way UX legend** — informational only (non-interactive icons), keeps form clean without adding complexity.
- **AI endpoint unchanged** — same URL `/ai/analisis-masalah-risiko/`, just richer response JSON.
