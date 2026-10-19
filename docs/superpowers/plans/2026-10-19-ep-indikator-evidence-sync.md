# Plan: automatic EP ↔ indikator mutu ↔ dokumen bukti sync (STARKES)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate the mapping between a quality indicator (`IndikatorMutu`), its accreditation Elemen Penilaian (`StandardItem`), and the evidence required for that EP (`EvidenceReq`/`EvidenceFile`). Today `IndikatorMutu.ep_terkait` is filled by hand from a dropdown that only offers 200 of 1053 EPs, and **138 of 210 indicators (66%) are unlinked**. The request (docx, 2026-10-19) asks for three mechanisms: (1) AI smart-matching over indicator name/numerator/denominator, (2) recommendation pushed when an indicator is saved, (3) rule-based auto-link by responsible unit. This plan implements all three plus the evidence leg, without changing how EPs themselves are scored.

**Architecture:** a **three-tier cascade** that is cheap-first and expensive-last, because sending 1053 EPs to an LLM per save is slow and pointless:

- **Tier A — rule boost.** `UnitKerja.standar_terkait` already maps each unit to sub-standards (`{"HPK": ["HPK 1", "HPK 4"]}`, 113 units, **2451/2451 values valid, 0 misses**). Used as a *boost*, never a hard filter — it only yields candidates for **39 of the 138** unlinked indicators, and median candidate set is 114 EPs (too wide to trust alone).
- **Tier B — lexical prefilter.** Pure-Python token scoring (no new dependency, no Postgres-only feature — DB may be SQLite) over all 1053 EPs → **top 40**. Used only to show the operator instant suggestions and as the AI's failure fallback: measured `precision@1` = **10%**, and no combination of score/gap ever reached nonzero precision (median gap between correct and wrong EP = **0.000** — ties everywhere), so it is never allowed to write to the database.
- **Tier C — DeepSeek re-rank over the FULL catalog.** `_call_deepseek()` receives the indicator plus **all 1053 EPs** (`ep_sync.build_ep_catalog()`: 115,707 chars ≈ 33–46k tokens, comfortably inside the 64k `deepseek-chat` window) and returns top 5 with a `confidence` and a short `alasan`. The planned "indicator + top-40 candidates" input was rejected on measurement: across 36 sampled links the correct EP shared **zero** tokens with the indicator text 17 times (e.g. *"Angka Sisa Makanan Yang Tidak Dimakan Pasien"* vs *"Tata kelola klinis keperawatan"*), and per-pokja routing only reached recall@5 = 74% while 10 gold EPs scored 0.000 in every partition — a lexical gate would have deleted the right answer before the model saw it. Returned `ep_code` values are validated against the catalog to reject hallucinated codes; flag-off, timeout and malformed replies all degrade to Tier B results (precedent: `_generate_fallback_evaluasi`).

Links carry provenance (`ep_sumber` + `ep_skor`) so automation is visible and **manual links are never overwritten**. The evidence leg renders, on the indicator pages, which `EvidenceReq` the linked EP demands and which are already uploaded — closing the third side of the docx triangle.

**Tech Stack:** Django 6.1.1 (`.venv`), DeepSeek chat API via existing `_call_deepseek()` (`response_format: json_object`, 30s timeout), Bootstrap 5.3, vanilla JS. One migration (`0042`).

**Spec:** docx `sinkronisasi dokumen bukti , indikator mutu dan standar akreditasi.docx` — "Buat otomatis system atau Ai sinkronisasi antara setiap ada indicator mutu, dokumen bukti dengan standar akreditasi" + the three suggested mechanisms (smart matching, auto-recommendation of EP on save, rule-based tagging by unit).

## Data reality (measured 2026-10-19)

| Fact | Value |
|---|---|
| `Framework` / `Category` / `StandardItem` (EP) | 1 / 16 / **1053** |
| EP with non-empty `description` | 1053 of 1053 (94–300 chars) |
| `EvidenceReq` / `EvidenceFile` / `QualityRecord` | 768 / **1** / 298 |
| `IndikatorMutu` total | 210 (IMP_RS 98, IMP_UNIT 76, NASIONAL 36) |
| linked to an EP / **unlinked** | 72 / **138 (66%)** |
| indicators with a `unit` | 210 of 210 (all of the 138 unlinked have one) |
| `UnitKerja.standar_terkait` populated | 113 units, 2451 sub-standards matched, **0 miss** |
| EP candidates after rule filter (per unit) | min 27 / median **114** / max 142 |
| unlinked indicators with rule candidates / with **zero** | 39 / **99** |
| rule agreement vs. 72 existing manual links | agree 43, disagree **11**, no-mapping 18 |
| pokja keys in maps that don't exist in `Category` | **`ARK`, `IPKP`** (stale — must be ignored) |

Two consequences that shape the whole plan: the unit map alone cannot be the gate (99 of 138 get nothing from it), and the rule prior reproduces only 80% of human choices (43/54), so it must never silently win over a human or over text evidence.

## The AI stack to reuse (do not rebuild)

| Piece | Where |
|---|---|
| `_call_deepseek(prompt, system_prompt, model, temperature, max_tokens)` | `akreditasi/ai_service.py:70` — gates on `config.ai_enabled` + API key, `json_object`, 30s timeout |
| `sanitize_hospital_prompt(text)` | `ai_service.py:55` — strip prompt-injection payload from user text |
| `_log_ai_call(user, modul, summary, success)` | `ai_service.py:141` → `AuditLog`, `model_name='AI_DEEPSEEK'` |
| Prompts | `akreditasi/ai_prompts.py` (`PROMPT_RDWOS_ANALISIS` at `:126` is the closest precedent) |
| Endpoint decorator | `@login_required @require_POST @rate_limit(max_calls=12, window=60, scope='ai')` |
| URL pattern | `akreditasi/urls.py:110-119` → `path('ai/<slug>/', ai_views.api_x, name='ai_x')` |
| Module enable flags | `akreditasi/system_models.py:69-73` (`ai_enable_rdwos`, …) checked at the top of each `generate_*` |
| Fallback-on-failure precedent | `ai_service.py:237` `_generate_fallback_evaluasi` |
| Rate-limit reset for tests | `akreditasi/tests_utils.reset_rate_limit(scope='ai')` — **required** in any test class that POSTs to `/ai/` |

## Where the manual seam is today

| Seam | Location |
|---|---|
| `IndikatorMutu.ep_terkait` FK → `StandardItem`, nullable | `akreditasi/risiko_models.py:603` (added by `69d0440`) |
| Selector `<select name="ep_terkait">` | `templates/akreditasi/indikator_form.html:233-237` |
| Catalog fed to that select — **capped `[:200]` of 1053** | `indikator_views.py:504` (create), `:575` (edit) |
| Save handlers reading `ep_id` | `indikator_views.py:471,489` (create) / `:542,560` (edit) |
| Downstream consumer of the link | `risiko_models.py:736` — `QualityRecord.objects.get(standard_item_id=...ep_terkait_id)` |
| EP badge on detail / dashboard | `indikator_detail.html:51-53`, `indikator_dashboard.html:223` |

## Global Constraints

- **Manual always wins.** Auto-sync must never modify an indicator whose `ep_terkait` was set by a human (`ep_sumber == 'MANUAL'`). Bulk writes target only `MANUAL`-untouched rows.
- **No hallucinated EP codes.** Any `ep_code` returned by the LLM is checked against the candidate list actually sent; unknown codes are dropped before rendering.
- **Fallback, never a hard failure.** If DeepSeek times out (30s), errors, or returns unusable JSON, return lexical-only results flagged as such — the operator still gets a usable ranking.
- **No new dependency, no Postgres-only feature.** DB may be SQLite locally (`config/settings.py:134`). No `trigram`, no `pgvector`, no embedding service.
- **Respect the AI rate limit.** `scope='ai'`, 12 calls/60s. Bulk runs must throttle.
- **Locale rule:** any `float`/`Decimal` into JS/CSS needs `|unlocalize` + `{% load l10n %}` (`c4c2a3c`). Confidence scores are floats → this rule applies to the recommendation card.
- **Do not touch** `static/css/style.css`, `staticfiles/staticfiles.json`, `templates/akreditasi/dashboard.html` (other session's work in the tree).
- **Stage only files this plan owns** (`git add <file>`). Never `git checkout --` or `git stash`.
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi -v1` — baseline **173 tests, 0 failures**.

---

### Task 1: provenance fields + enable flag (migration 0042)

- [x] **Step 1: Add two fields to `IndikatorMutu`** in `akreditasi/risiko_models.py`, next to `ep_terkait` (`:603`):

  ```python
  EP_SUMBER_CHOICES = [
      ('MANUAL', 'Dipilih manual'),
      ('AI', 'Rekomendasi AI'),
      ('RULE', 'Auto (unit terkait)'),
      ('LEXICAL', 'Auto (kecocokan kata)'),
  ]

  ep_sumber = models.CharField(
      'Sumber Link EP', max_length=10, choices=EP_SUMBER_CHOICES,
      default='MANUAL', blank=True,
  )
  ep_skor = models.DecimalField(
      'Skor Kecocokan EP', max_digits=5, decimal_places=4,
      null=True, blank=True,
  )
  ```

  `default='MANUAL'` deliberately: the 72 rows that already exist were hand-picked, so backfill must not make them look machine-generated.

- [x] **Step 2: Add the module flag** in `akreditasi/system_models.py`, after `ai_enable_rdwos` (`:72`):

  ```python
  ai_enable_ep_sync = models.BooleanField('AI: Sinkronisasi EP Indikator Mutu', default=True)
  ```

- [x] **Step 3: Generate and apply** `.venv/Scripts/python.exe manage.py makemigrations akreditasi` → expect `0042_indikatormutu_ep_sumber_ep_skor_systemconfig_ai_enable_ep_sync.py`. Confirm it names both fields and the config flag, then `manage.py migrate`.

- [x] **Step 4: Sanity-check the default.** In a shell, `IndikatorMutu.objects.filter(ep_sumber='MANUAL').count()` must equal the total row count right after migrating (all pre-existing rows default to MANUAL).

### Task 2: `akreditasi/ep_sync.py` — rule boost + lexical prefilter

- [x] **Step 1: Create the module** with five functions, no imports outside the stdlib + Django ORM.

  ```python
  _STOPWORDS = frozenset(
      'yang dan di ke dari untuk pada dengan adalah ini itu tidak ada dalam oleh '
      'per ke pada saat lebih dapat dilakukan secara serta atau juga karena antar '
      'yaitu telah harus para seluruh setiap telah sebelum sesudah hingga agar '
      'no umur laki perempuan pasien rs unit tahun bulan hari jumlah angka'.split()
  )
  ```

  1. `normalize(text: str) -> set[str]` — lowercase, replace non-alphanumerics with spaces, drop stopwords and single characters, return the token set.
  2. `valid_sub_standards_for_unit(unit) -> set[str]` — read `unit.standar_terkait`, flatten values, return only those present in `StandardItem.values_list('sub_standard', flat=True)`. **Ignore unknown pokja keys** (`ARK`, `IPKP`) rather than raising; cache the valid sub-standard set per call site (one query, reused across indicators).
  3. `score_ep(indicator_tokens, unit_boost, ep, category_name, category_code, kelompok) -> float` — weighted overlap: tokens found in `ep.description` count `1.0`, in `ep.sub_title` `1.5`, in `ep.code`+`ep.sub_standard` `2.0`, in the category name/kelompok `0.75`; sum then divide by `len(indicator_tokens)` and clamp to `1.0`. If `ep.sub_standard` is in `unit_boost`, add `+0.25`. Exact substring match of the normalized indicator name inside the EP description adds `+0.30`.
  4. `prefilter_candidates(indicator, top_k=40) -> list[tuple[StandardItem, float]]` — build tokens from `nama_indikator` + `numerator` + `denominator` + `unit.name`, score all 1053 EPs, sort desc, take `top_k`.
  5. `top_rule_sub_standards(unit)` — helper returning the unit's mapping as `{pokja_code: set(sub_standards)}` for display in the UI ("dipetakan dari unit IGD").

- [x] **Step 2: Performance check.** Scoring 1053 EPs in Python per call must stay well under ~150ms. If `prefilter_candidates` is slower, materialize the per-EP haystack once into a module-level lazy cache keyed by nothing (EPs change rarely) invalidated by an explicit `clear_ep_index()` the test suite calls in `setUp`.

- [x] **Step 3: Unit tests for Tier A/B** (start `akreditasi/tests_ep_sync.py`):

  - a synthetic indicator whose text matches exactly one EP ranks that EP first;
  - `valid_sub_standards_for_unit` drops a bogus pokja key (`ARK`) and a bogus sub-standard without raising;
  - an indicator with no unit still returns `top_k` candidates (Tier B must not depend on the unit map);
  - `score_ep` clamps to `<= 1.0` for a token set entirely contained in the EP text.

### Task 3: `PROMPT_EP_MATCH` + `generate_ep_rekomendasi()`

- [x] **Step 1: Add the prompt** to `akreditasi/ai_prompts.py`, modeled on `PROMPT_RDWOS_ANALISIS` (`:126`). Input slots: `nama`, `numerator`, `denominator`, `kode`, `jenis`, `dimensi`, `unit`, `daftar_ep`. It must:

  - instruct the model to return **only** `{"rekomendasi": [{"ep_code": "...", "confidence": 0.0-1.0, "alasan": "..."}]}` (the transport already forces `response_format: json_object`);
  - forbid inventing `ep_code` values outside `daftar_ep`;
  - cap at 5 entries sorted by confidence;
  - write `alasan` in Indonesian, max ~20 words;
  - state that `confidence` below 0.6 means "not confident" rather than padding everything to 0.9.

- [x] **Step 2: Add the service function** to `akreditasi/ai_service.py`, following `generate_rdwos_analisis` (`:384`) exactly:

  ```python
  def generate_ep_rekomendasi(user, ind, candidates) -> dict:
  ```

  - guard on `SystemConfig.get_solo().ai_enable_ep_sync` (mirror the `ai_enable_rdwos` check);
  - `sanitize_hospital_prompt()` every free-text field from the indicator;
  - truncate each candidate description to 220 chars to bound input size (40 candidates ≈ 4–6K tokens);
  - `_call_deepseek(prompt, max_tokens=1200)` — the answer is small, do not inherit a 2500-token budget;
  - **validate**: keep only `ep_code` present in the candidate codes, clamp `confidence` to `[0, 1.0]`, drop `alasan` longer than 300 chars;
  - if the LLM result is unusable (failure, or zero valid codes), return `{'success': True, 'data': {'rekomendasi': [...lexical-only...], 'sumber': 'LEXICAL'}, 'ai_terpakai': False}` so callers never break;
  - `_log_ai_call(user, 'EP_SYNC', f'{ind.kode_indikator} → {n} kandidat', ...)`.

- [x] **Step 3: Test the contract without hitting the network.** In `tests_ep_sync.py`, patch `akreditasi.ai_service._call_deepseek` to return a payload containing one valid code, one hallucinated code, and a `confidence` of `1.7`. Assert: hallucinated code dropped, confidence clamped to `1.0`, `ep_sumber` path returns `AI`. Add one test where the patched call returns `{'success': False}` and assert the endpoint still returns 200 with lexical results and `ai_terpakai: False`.

### Task 4: endpoint `ai/ep-rekomendasi/`

- [x] **Step 1: Add `api_ai_ep_rekomendasi`** to `akreditasi/ai_views.py`, cloned from `api_ai_rdwos_analisis` (`:211`):

  - `@login_required @require_POST @rate_limit(max_calls=12, window=60, scope='ai')`;
  - body: `indikator_id` (required, int). Fetch with `select_related('unit', 'ep_terkait')`;
  - permission: reuse the indicator module gate (`_is_manager`) — a plain staff user must not drive AI spend or rewrite links;
  - reject an indicator that already has `ep_terkait` **and** `ep_sumber == 'MANUAL'` with 400 `error` "Sudah terhubung manual" (protects human work from re-recommendation churn);
  - run Tier B (`prefilter_candidates`), then Tier C (`generate_ep_rekomendasi`);
  - return `{'success': True, 'kandidat': [{ep_code, judul, pokja, deskripsi, skor, dari_unit}], 'rekomendasi': [...], 'ai_terpakai': bool}`.

- [x] **Step 2: Register the route** in `akreditasi/urls.py` next to line 117:

  ```python
  path('ai/ep-rekomendasi/', ai_views.api_ai_ep_rekomendasi, name='ai_ep_rekomendasi'),
  ```

- [x] **Step 3: Tests.** POST with an invalid payload → 400; anonymous → redirected/401 per the middleware behaviour (login redirect is intentionally preserved since `4124547`); two rapid POSTs plus `reset_rate_limit` handling in `setUp` → assert no 429 leak across classes; manual-linked indicator → 400.

### Task 5: recommendation card on the indicator form + fix the `[:200]` catalog cap

- [x] **Step 1: Fix the truncated catalog.** Both `indikator_views.py:504` and `:575` slice `[:200]` of 1053 EPs, so EP #201–1053 cannot be chosen at all. Replace with the full catalog grouped for readability, one query:

  ```python
  ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'order', 'code')
  ```

  In `indikator_form.html:233-237`, wrap the options in `<optgroup label="{{ ep.category.code }} — {{ ep.category.name }}">` and change the loop to iterate a pre-grouped structure (or use `{% ifchanged %}`). Keep the current `selected` logic on `ind.ep_terkait_id`.

- [x] **Step 2: Mark explicit human choice as MANUAL.** In `indikator_edit` (`:560`) and `indikator_form` create (`:489`), after setting `ep_terkait_id`, also set `ep_sumber='MANUAL'` when the operator picked an EP and `ep_skor = None`. If the operator clears the EP, reset both to blank.

- [x] **Step 3: Push recommendations when a save leaves EP empty.** In `indikator_edit`, after a successful POST where `ep_terkait_id` is falsy, call `prefilter_candidates(ind)` and put the top 10 (code, description, pokja, skor, `dari_unit` flag) into context as `ep_kandidat`. Do **not** call DeepSeek inline in the POST path — the card's "✨ Cocokkan dengan AI" button calls the Task 4 endpoint and renders asynchronously, so a 30s timeout never blocks a save.

- [x] **Step 4: Render the card** in `indikator_form.html`, immediately above the `ep_terkait` select:

  - hidden unless `is_edit` and `not ind.ep_terkait_id` and `ep_kandidat`;
  - heading "Rekomendasi EP" with a muted line explaining they are derived from the indicator text plus `unit.name`'s `standar_terkait` map;
  - one row per candidate: `[{{ c.code }}] {{ c.description|truncatechars:110 }}`, pokja badge, and `{{ c.skor|unlocalize }}` behind `{% load l10n %}` as a Bootstrap progress bar (this is a float into JS/CSS-adjacent markup → **locale rule applies**);
  - a "Pakai" button per row that sets the `<select>` value via `document.getElementById('ep_terkait').value = <id>` and scrolls to it; it must **not** submit;
  - a "✨ Cocokkan dengan AI" button that POSTs to `{% url 'akreditasi:ai_ep_rekomendasi' %}` with the indicator id, shows a spinner, then re-renders the list from `rekomendasi` with the model's `alasan` and confidence, flagging any AI-topped row;
  - a small `no-print` class on the whole card (the form is printable elsewhere).
  - JS lives in `static/js/ai-assist.js` if it already fetches `/ai/` endpoints in this shape; otherwise a `<script>` block at the bottom of `indikator_form.html`, matching whichever convention that page already uses.

- [x] **Step 5: Manual render probe.** Render the edit form through the test client for an indicator with no EP and assert the card appears, the `optgroup` headings are present, and a JS parse check passes after rendering (`node --check` on the extracted script — raw `{{ }}` breaks it, so render first).

### Task 6: evidence leg — "dokumen bukti" for the linked EP

- [x] **Step 1: Build the context helper** in `akreditasi/ep_sync.py`:

  ```python
  def bukti_ringkas(ep) -> dict | None
  ```

  Returns `None` when `ep` is falsy, else `{'total': n, 'wajib': n_mandatory, 'terunggah': n_uploaded, 'reqs': [...]}` where each req carries `category_type`, `title`, `is_mandatory`, and `terunggah` (count of `EvidenceFile`). One query for the reqs plus one `annotate(Count('files'))` — no N+1.

- [x] **Step 2: Surface it on `indikator_detail.html`** below the existing EP badge (`:51-53`):

  - a "Dokumen Bukti (RDWOS)" card listing each `EvidenceReq` with its R/D/W/O/S chip, title, mandatory marker, and upload count `{{ r.terunggah }}`;
  - a summary line: "X dari Y kebutuhan bukti telah diunggah" — with the honest note that `EvidenceFile` currently holds 1 row in this deployment, so the panel is expected to read mostly "belum diunggah";
  - a link to the RDWOS module for that EP so the operator can upload from context;
  - guard the whole card on `{% if ind.ep_terkait %}` so unlinked indicators render nothing.

- [x] **Step 3: Mirror a one-line summary** on `indikator_dashboard.html:223` where the EP is already displayed: append "(n kebutuhan bukti, m terunggah)" when an EP is linked. Do not add a second table there.

- [x] **Step 4: Test.** Seed one EP with two `EvidenceReq` (one mandatory) and one `EvidenceFile`; assert the detail page shows both requirements, the correct uploaded count, and nothing at all when `ep_terkait` is `None`.

### Task 7: bulk backfill `manage.py sync_ep_indikator`

- [x] **Step 1: Create `akreditasi/management/commands/sync_ep_indikator.py`** following the house style of `seed_indikator_mutu_renstra.py`.

  ```
  --apply        write links (default is dry-run: print the table only)
  --no-ai        Tier A+B only — instant, free, no DeepSeek calls
  --limit N      process at most N indicators (default: all unlinked)
  --min-skor F   auto-apply threshold for lexical-only decisions (default 0.55)
  --only-unit U  restrict to one unit code (for spot-checking)
  ```

  Rules:
  - iterate `IndikatorMutu.objects.filter(ep_terkait__isnull=True)` only — **never** touch `ep_sumber='MANUAL'`;
  - Tier B ranks everything; auto-apply when `skor >= --min-skor` **and** the runner-up trails by `>= 0.10` (an ambiguous top-2 is not a decision), setting `ep_sumber='LEXICAL'`, `ep_skor`;
  - for the remainder call `generate_ep_rekomendasi` unless `--no-ai`; apply at `confidence >= 0.85` with `ep_sumber='AI'`; everything else is left unlinked and listed as "perlu ditinjau";
  - when writing, **skip** any indicator whose current `ep_terkait_id` was set since the run started (protects a human editing mid-run);
  - throttle with `time.sleep(6)` between DeepSeek calls to stay inside 12/60s, and print `--limit`-aware progress (`[12/138]`);
  - wrap each indicator in try/except and continue on failure, reporting a summary: linked-lexical, linked-ai, left-for-review, skipped, errors;
  - exit code 0 on a clean run.

- [x] **Step 2: Dry-run on the real 138.** Run **without** `--apply`, with `--no-ai` first, and paste the resulting distribution into the commit message: how many auto-link at 0.55, how many are ambiguous, how many have zero rule candidates (expect ~99). This is the evidence that the threshold is sane.

- [x] **Step 3: Test the command** in `tests_ep_sync.py` with `call_command`: a synthetic indicator matching one EP gets linked with `ep_sumber='LEXICAL'`; an ambiguous one is left unlinked; `--apply` absent leaves the DB untouched; a MANUAL row is never modified.

### Task 8: full verification, then commit

- [x] **Step 1: Full suite.** `.venv/Scripts/python.exe manage.py test akreditasi -v1` — must stay green (baseline 173; expect +8–12 new). Any `/ai/`-touching class needs `reset_rate_limit()` in `setUp`.

- [x] **Step 2: Live render probes.** As a manager, render the indicator edit form (indicator without an EP) and assert the recommendation card + `optgroup` groups appear; render the indicator detail for a linked indicator and assert the bukti panel lists the EP's `EvidenceReq`. Then `node --check` the extracted script.

- [x] **Step 3: Stage only this plan's files** with `git add <file>` — `risiko_models.py`, `system_models.py`, `migrations/0042_*`, `ep_sync.py`, `ai_prompts.py`, `ai_service.py`, `ai_views.py`, `urls.py`, `indikator_views.py`, `management/commands/sync_ep_indikator.py`, `templates/akreditasi/indikator_form.html`, `indikator_detail.html`, `indikator_dashboard.html`, `tests_ep_sync.py`, the plan file. **Do not** stage `static/css/style.css`, `staticfiles/staticfiles.json`, `templates/akreditasi/dashboard.html`.

- [x] **Step 4: Commit + push**, then confirm Vercel via `gh api repos/faishaltsq/sim-akreditasi-django/commits/<sha>/status`. Report the dry-run distribution, the new test count, and the measured `prefilter_candidates` latency.

## Out of scope (say so, don't build it)

- **Embeddings / pgvector.** Adds a dependency, a migration, and a paid service; the DB is SQLite locally. Tier B already cuts 1053 → 40 in pure Python.
- **Rewriting `EvidenceReq` seeds.** The 768 requirements are standard-defined; the sync only reads them.
- **Backfilling `UnitKerja.standar_terkait` for the units that lack it** (the 99-zero-candidate group). That is a data-entry task for the operator, surfaced by the command's "perlu ditinjau" list; automating it would mean guessing unit→standar mappings.
- **Changing how EPs are scored** (`QualityRecord.score`) or the RDWOS upload flow.
- **Re-touching the Evaluasi/Monitoring buttons** from the previous plan (`c57bdd3`/`db55d51`).

## Execution results (2026-10-19)

**Deviation 1 — full catalog instead of a top-40 candidate list (Tier C).** Measured, not stylistic: 17 of 36 sampled links shared zero tokens with the correct EP, and per-pokja routing capped recall@5 at 74% while 10 gold EPs scored 0.000 in every partition. Details in the architecture section above.

**Deviation 2 — lexical never auto-applies (Task 7 Steps 2–3).** The plan expected a `0.55` threshold to auto-link some indicators with `ep_sumber='LEXICAL'`. Measured against the 72 existing manual links: `precision@1` = **10%**, and the confident set stayed at **0% precision at every threshold tried** (min score 0.15–0.50 × gap 0.05–0.20), with median score 0.461 correct vs 0.418 wrong and a median gap of **0.000** — essentially permanent ties. Any threshold would have written mostly wrong links, so the command writes only under `--ai --apply` with `confidence >= 0.75`, and otherwise prints `perlu keputusan operator`. Dry run over the real 138 unlinked: **0 auto-linked, 138 deferred to the operator, 0 with zero candidates**, index build 57ms.

**Deviation 3 — no `ep_kandidat` in the GET context (Task 5 Step 3).** The card fetches candidates from the Task 4 endpoint when clicked instead, so every form render stays at one query instead of scoring 1053 EPs per GET.

**Bug fixed along the way.** `_is_manager()` in `indikator_views.py` tested `'KOORDINATOR'`, which does not exist in `UserProfile.ROLE_CHOICES` (only `KOORDINATOR_POKJA`) — that role was never recognised as a manager, which had also silently disabled the previous plan's buttons. Also removed the `[:200]` slice so EP #201–1053 can be selected at all.

**Measured performance.** `get_ep_index()` build 57–92ms for 1053 EPs (module-level cache with explicit invalidation); `prefilter_candidates()` 7–9ms per call; catalog 115,707 chars ≈ 33–46k tokens.

**Tests.** 41 new tests in `akreditasi/tests_ep_sync.py`: catalog, service contract (anti-hallucination, clamping, all fallback paths), endpoint access control, form rendering, evidence panel, command safety (dry run, manual link protection, `--ulang`), manual-save provenance, dashboard summary. Full suite **322/322** green; both rendered script blocks pass `node --check`.
