# Plan: unblock EP ↔ AI sync on the indicator form

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** an operator who empties the **Elemen Penilaian (EP)** column, or picks an EP
recommended by AI, always ends with exactly one visible, truthful state: either the
link is stored in the database or the screen says precisely why it is not. Two
reported failures from the 2026-10-20 docx ("sinkronisasi EP dengan AI tidak bisa /
tidak masuk") are closed, plus the two defects that guarantee they recur.

**Evidence:** `docs/qa/analisa-bug-ep-ai-sync-2026-10-20.md` — read it first. All
`file:line` references below are on `master` @ `efc96ec`, the SHA Vercel production
is running.

**Root causes being fixed:**

| ID | Defect | Where |
|---|---|---|
| D1 | AI guard reads the **database**, the screen shows the **form** — two states can disagree with no way for the operator to see it. | `akreditasi/ai_views.py:308` vs `indikator_form.html:233` |
| D2 | The refusal names no EP ("Kosongkan dulu kolom EP" while the column already reads empty). | `akreditasi/ai_views.py:311` |
| D3 | Emptying the column writes `ep_sumber='MANUAL'`, so a *cleared* row is marked human-touched and auto-sync skips it forever. | `akreditasi/indikator_views.py:589-594` |
| D4 | "Pakai" only moves the `<select>`; nothing is stored until *Simpan Perubahan*, with no dirty-state warning and no "saved" feedback. | `indikator_form.html:579-587` |
| D6 | DeepSeek is given `timeout=120` (`ai_service.py:630`) inside a Vercel lambda capped at `maxDuration: 60` (`vercel.json:8`); when the lambda dies the server-side lexical fallback never runs and the client calls `.json()` on an HTML 504. | — |

**Architecture in one line:** *make the guard report state instead of guessing it,
make clearing a real state transition, and make "Pakai" a write of its own* — the
"manual always wins" invariant from the original plan is preserved, only its
definition becomes precise: **manual = an EP is currently linked by an operator**,
not "this row was ever touched".

---

## Global constraints

- **Branch:** the EP sync feature exists **only** on `master`. The active worktree is
  `faishaltsq/medaka` and does not contain `akreditasi/ep_sync.py`. Branch off
  `master`; never implement this on `medaka`.
- **Manual still wins.** A row with an operator-chosen link is never overwritten by
  `sync_ep_indikator`, with or without `--ulang`. Existing tests
  `test_link_manual_tidak_disentuh_termasuk_dengan_ulang`,
  `test_mengganti_ep_menjadi_pilihan_manual` must stay green.
- **No hallucinated EP codes.** Keep the `code not in codes` rejection and the
  confidence clamp in `generate_ep_rekomendasi()`.
- **Fallback, never a hard failure.** Every AI failure path must still hand the
  operator a ranked list — including the case where the *lambda* would be killed.
- **No new dependency, no Postgres-only feature.** DB may be SQLite locally.
- **Do not touch** `static/css/style.css`, `staticfiles/`, `staticfiles/staticfiles.json`,
  `templates/akreditasi/dashboard.html`.
- **Stage only files this plan owns** (`git add <file>`). Never `git checkout --`,
  `git stash`, or `git add -A` (the tree carries untracked `node_modules/`,
  `package.json`, `pnpm-lock.yaml`).
- **Locale:** any float into JS needs `{% load l10n %}` + `|unlocalize`.
- **Migrations never run on Vercel** — apply by hand to Supabase after deploy.
- Test env must be bootstrapped first (no `.venv` exists in this worktree):
  `python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt`
  (or `uv venv`), then `.venv/Scripts/python.exe manage.py test akreditasi -v1`.
  Baseline: **322 tests, 0 failures**.

---

### Task 0 — Confirm which failure is live (do this before writing code)

- [ ] **Step 1: Read the production row.** Connect to the Supabase project
      (connector `supabase` is currently unconnected — connect it, or use the
      project's SQL editor) and run:

      ```sql
      SELECT id, kode_indikator, ep_terkait_id, ep_sumber, ep_skor
      FROM akreditasi_indikatormutu WHERE id = 209;
      ```

      - `ep_terkait_id IS NOT NULL` → **H1 confirmed**: the screen lied; the link
        is still in the database and D1/D2 are the fix.
      - `ep_terkait_id IS NULL` → **H2**: check whether
        `(SELECT id FROM akreditasi_standarditem WHERE id = <ep_terkait_id>)` would
        have returned a row, i.e. whether the rendered option list contains the
        linked id (`akreditasi_indikatormutu.ep_terkait_id` →
        `akreditasi_standarditem.id`).
- [ ] **Step 2: Time the AI call.** On `/indikator-mutu/209/edit/`, DevTools →
      Network → `POST /ai/ep-rekomendasi/` → note status code and duration.
      Record `status >= 500 || duration > 55000` as **H3 confirmed** (D6).
      Cross-check `SELECT summary, created_at FROM akreditasi_auditlog WHERE
      model_name='AI_DEEPSEEK' ORDER BY created_at DESC LIMIT 5;`
- [ ] **Step 3: Write the result into the plan.** Replace the H1/H2/H3 markers
      below with `confirmed`/`ruled out`. Tasks 1–4 stay in scope either way —
      they remove the defect class, not one instance of it.

### Task 1 — The guard reports state instead of guessing

- [x] **Step 1: Return the blocking fact.** In `akreditasi/ai_views.py:308-312`,
      keep the refusal but make it self-describing:

      ```python
      if ind.ep_terkait_id and ind.ep_sumber == 'MANUAL':
          ep = ind.ep_terkait
          return JsonResponse({
              'success': False,
              'error': (f'EP {ep.code} masih tertaut manual di database. '
                        f'Kosongkan kolom EP lalu tekan "Simpan Perubahan" '
                        f'dulu — atau pakai tombol "Lepas & cari ulang".'),
              'ep_terkait': {'id': ep.id, 'code': ep.code},
              'butuh_simpan': True,
          }, status=400)
      ```

      Add `butuh_simpan` because the real condition is "the stored link differs from
      what the form is showing", which only a save can reconcile.
- [x] **Step 2: Surface it in the card.** In `indikator_form.html`, render a
      persistent chip **above** the sync card whenever `ind.ep_terkait_id` is set,
      e.g. `Tertaut saat ini: <code>KE 4.1</code> — sumber {{ ind.ep_sumber }}`, so
      the operator can see what the guard sees without reading an error.
- [x] **Step 3: Make the JS error path show detail.** The `catch` block
      (`indikator_form.html:570-575`) currently renders only `e.message`. Append
      `b.ep_terkait.code` when present, and detect a non-JSON body before
      `r.json()` so a Vercel 504 reads as a server-timeout message, not
      `Unexpected token <`.

### Task 2 — Clearing becomes a real state transition

- [x] **Step 1: Change the provenance rule** in `akreditasi/indikator_views.py:588-595`:

      ```python
      baru_ep = int(ep_id) if ep_id else None
      if baru_ep is None:
          # Empty is not a manual decision — leave the row joinable by auto-sync.
          ind.ep_sumber = ''
          ind.ep_skor = None
      elif baru_ep != ind.ep_terkait_id:
          ind.ep_sumber = 'MANUAL'
          ind.ep_skor = None
      ind.ep_terkait_id = baru_ep
      ```

      Apply the same rule in `indikator_tambah` (`:516`): a create with no EP must
      store `ep_sumber=''`, not `'MANUAL'`.
- [x] **Step 2: Keep the field honest.** `ep_sumber` already has `blank=True`;
      add an explicit choice `('', 'Belum ditautkan')` to `EP_SUMBER_CHOICES` so
      admin/forms validate, and document on the model that `MANUAL` means
      *currently linked by an operator*.
- [x] **Step 3: Migration `0044`.** Backfill reality into provenance:

      ```sql
      UPDATE akreditasi_indikatormutu SET ep_sumber = ''
      WHERE ep_terkait_id IS NULL;
      ```

      Data migration, one operation, no schema change. **Apply to Supabase by hand
      after deploy** — Vercel does not run it.
- [x] **Step 4: Make auto-sync act on it.** Verify
      `sync_ep_indikator` skips rows on `ep_terkait_id IS NULL`, not on
      `ep_sumber != 'MANUAL'`; with the new semantics, rows cleared by an operator
      become eligible again. Keep skipping every row that *has* an EP.

### Task 3 — "Pakai" writes, and says so

- [x] **Step 1: New endpoint** `POST /ai/ep-terapkan/` in `akreditasi/ai_views.py`
      — `@login_required @require_POST @rate_limit(max_calls=12, window=60, scope='ai')`
      + `_is_manager`. Body `{'indikator_id': n, 'ep_id': n}`. Validates the EP
      exists, then writes `ep_terkait_id`, `ep_sumber='MANUAL'`, `ep_skor=None` and
      `_log(user, 'UPDATE', ind, 'Pakai rekomendasi AI untuk EP …')`.
      Register in `akreditasi/urls.py` next to `ai/ep-rekomendasi/`.
      *Provenance stays `MANUAL` deliberately:* the operator pressed the button, so
      auto-sync must never replace it; the AI origin is preserved in `AuditLog`.
- [x] **Step 2: Wire the button.** Replace the client-only handler at
      `indikator_form.html:579-587` with a `fetch` to the new endpoint; on success
      set `sel.value`, show `Tersimpan ✓` in the card, and mark the pick button
      `btn-success`. On failure keep today's behaviour (move the select) but show
      *"belum tersimpan — tekan Simpan Perubahan"* in `alert-warning`.
- [x] **Step 3: Dirty-state guard.** When `sel` has changed and the form has not
      been submitted, intercept navigation (`beforeunload` + clicks on the `Batal`
      link) with a confirmation. This is what makes D4 impossible to hit silently.
- [x] **Step 4: Re-render truth.** After a failed POST in `indikator_edit`, the
      template re-renders the in-memory `ind` while the database keeps the old row —
      exactly the divergence D1 describes. On exception, reload `ind` from the
      database before rendering, or re-render the submitted values with a visible
      error banner. Pick one; the current mix is the bug.

### Task 4 — Fit the AI call inside the 60 s lambda

- [ ] **Step 1: Measure first** (Task 0 Step 2). Do not shrink a prompt that
      already finishes in 20 s — but do fix the contract either way.
- [x] **Step 2: Bound the model to the platform.** In `ai_service.py:630`, set the
      DeepSeek timeout to a value **below** the lambda budget (e.g. `timeout=45`
      while `maxDuration=60`) so the server-side `_lexical()` fallback returns a
      usable list instead of the platform killing the request. Keep `max_tokens`
      at 1200 only if measurement justifies it; 5 entries with `alasan[:300]` needs
      far less.
- [ ] **Step 3: Shrink the prompt if Step 1 shows >40 s.** `build_ep_catalog()`
      currently ships 115,707 chars of EP text. Cut `description` to its first
      120 chars per EP (keep `code` + `sub_standard` whole) — that halves input
      tokens while preserving every code the anti-halusinasi check needs. **Re-run
      the measurement that justified the full catalog** (`36` sampled links,
      `17/36` sharing zero tokens) on the truncated catalog before keeping it; if
      recall@5 drops, keep the full catalog and raise the platform budget instead.
- [ ] **Step 4: Raise the platform budget if the plan allows it.** `vercel.json`
      `maxDuration: 60`. Confirm the Vercel plan's ceiling (Pro allows up to 300 s);
      if it can be raised for this route, do it *and* keep Step 2's shorter model
      timeout as the belt to that suspenders.
- [x] **Step 5: Report elapsed time.** Append the call duration to the
      `_log_ai_call(..., 'EP_SYNC', ...)` summary so regressions are visible in
      `AuditLog` without reproducing them.

### Task 5 — Say whether AI is on before the operator clicks

- [x] **Step 1:** Add `ai_status` to the `ep-rekomendasi` payload and render it in
      the card on page load: `ai_enable_ep_sync`, `config.ai_enabled`, and whether
      an API key is configured (`config.get_deepseek_api_key()` truthy).
      Show `AI aktif` / `AI nonaktif — hasil akan berupa kecocokan kata` as a chip.
- [x] **Step 2:** Promote the existing `notice` (lexical fallback) from
      `alert-warning` to a state label that survives the render, so a list produced
      by Tier B is never mistaken for AI output (D5).

### Task 6 — Tests

- [x] **Step 1:** `akreditasi/tests_ep_sync.py` — add:
      - clearing the EP via the edit form makes the next `ep-rekomendasi` call
        return 200 (the regression the docx reports);
      - clearing sets `ep_sumber=''` and leaves the row eligible for auto-sync;
      - the refusal payload carries `ep_terkait.code`;
      - `POST /ai/ep-terapkan/` writes the link, is manager-only, rate-limited and
        rejects an unknown `ep_id`;
      - a DeepSeek timeout still returns a non-empty lexical list (D6).
- [x] **Step 2:** Update `test_mengosongkan_ep_mereset_provenance` — it currently
      asserts `ep_sumber == 'MANUAL'` after a clear; the new expectation is `''`.
      Re-read every test that asserts `ep_sumber` so none silently passes on the old
      semantics.
- [x] **Step 3:** Run the suite: `.venv/Scripts/python.exe manage.py test akreditasi -v1`.
      Baseline 322 → expect green plus the new cases.

### Task 7 — Verify on the deployed row, then hand back

- [ ] **Step 1:** After deploy + manual migration: re-open
      `/indikator-mutu/209/edit/`, empty the EP, **press Simpan Perubahan**, return,
      press *Cocokkan with AI* → expect a ranked list, not a red banner.
- [ ] **Step 2:** Pick a recommendation → expect `Tersimpan ✓` **without** pressing
      *Simpan Perubahan*, then confirm the row in SQL:
      `ep_terkait_id` set, `ep_sumber='MANUAL'`.
- [ ] **Step 3:** Confirm a lexical-fallback run still returns a list within 60 s.

---

## Out of scope (say so, don't build it)

- Auto-applying AI suggestions without an operator decision — the plan's own
  measurement (`precision@1 = 10%`, `median gap = 0.000`) forbids it.
- Re-scoring or re-ranking EPs themselves, evidence upload, or the PDCA matrix.
- Rewriting `sync_ep_indikator` beyond the eligibility rule in Task 2 Step 4.

---

## Execution status (2026-10-20, branch `fix/ep-ai-sync`)

**Done:** Task 1 (guard returns `ep_terkait.code` + `butuh_simpan`; chip + `Lepas & cari ulang`
in the card; JS error path shows the detail), Task 2 (clearing writes `ep_sumber=''`, create
without EP writes `''`, choices + help text, migration `0044` with backfill + reverse, eligibility
verified as `ep_terkait IS NULL`), Task 3 (`POST /ai/ep-terapkan/`, `POST /ai/ep-lepas/`, "Pakai"
writes immediately and reports `Tersimpan ✓`, dirty-state guard on `beforeunload` + `Batal`,
failed save re-renders DB truth), Task 4 steps 2 + 5 (client `timeout=45`, duration in `AuditLog`),
Task 5 (`ai_status` chip in the card and in the payload; Tier B notice is a grey state label),
Task 6 (all tests, suite green).

**Not done — needs the live environment:**
- Task 0 Step 1: read production row #209 (Supabase connector not linked in this session).
- Task 0 Step 2: time the real AI call (requires an authenticated browser session).
- Task 4 Step 3: prompt shrink — skipped on purpose; Step 1 measurement never ran.
- Task 4 Step 4: raising `maxDuration` beyond 60 s needs the Vercel plan ceiling confirmed;
  `timeout=45` already makes the 60 s contract safe, so this is an optimization, not a blocker.
- Task 7: verify on the deployed row after deploy + manual migration.

**Branch state (close-out):**

- `fix/ep-ai-sync` rebased onto `master` (`4aad974`) — clean, no conflicts.
- `fix(ep): sinkronisasi AI EP jujur dan bisa dilepas` — code, tests, migration `0044`.
- `docs(qs): analisis dua laporan EP-AI 20-10 dan status eksekusi rencananya` — this file
  and `docs/qa/analisa-bug-ep-ai-sync-2026-10-20.md`.
- **291 tests in `akreditasi` green** after the rebase (`Ran 291 tests ... OK`).
- `manage.py check` clean; `makemigrations --check` → "No changes detected".

**Notes from execution:**

- Migration `0044` applies inside the test suite. A reverse run could not be executed
  against a scratch database because the chain fails earlier, at the pre-existing
  `0023_seed_indikator_mutu_renstra` (`no such column: tipe_pengukuran`) on any fresh
  on-disk sqlite database. Reproduced at the base commit with this branch's changes
  absent, so it is not caused by this work; production is already past `0023`.
  `kembalikan_ke_manual` only issues an UPDATE and was verified by inspection.
- The primary tree carries an **uncommitted** `0044_alter_insidenkeselamatan_...`
  migration. Two `0044_*` files would collide cosmetically; renumber one of them
  before both land.

**Deployed 2026-10-20 12:31 WIB:** `76a59c9` pushed to `master` (`4aad974..76a59c9`,
fast-forward) and built by Vercel — production deployment
`2YJxoyLmxcaFasuRLZAJUSVq5W2G`, GitHub status `Vercel success`. Verified on
`https://sim-akreditasi-django.vercel.app`: `POST /ai/ep-lepas/` and `POST /ai/ep-terapkan/`
answer 403 (CSRF, route present) while a bogus path answers 404.

**Migration `0044` is still unapplied in production** — deploys do not run migrations here.
It is not required for the reported bug: the guard at `ai_views.py:311` requires a real
`ep_terkait_id`, so rows marked `MANUAL` with no link are already unlocked. `0044` only
corrects the stored `ep_sumber` label. Apply with `python manage.py migrate akreditasi`.

