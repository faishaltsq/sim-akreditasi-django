# Monitoring & Evaluation — Indicator Dropdown Limited to Planned Indicators

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** In section G.1 of the risk evaluation page (Check/Act), the "Tautkan ke Indikator Mutu" dropdown must offer only the quality indicators that were already planned for that unit at the Plan stage — not the whole unit catalogue plus all 13 national INM indicators. The target value must come from the planning stage.

**Architecture:** One new helper in `akreditasi/risiko_views.py` derives the planned indicator set from `RisikoUnit.indikator_mutu_terkait` rows of the same unit and its ancestor chain. The existing `indikator_kandidat` context variable is repopulated from that set, with a documented fallback to today's behaviour when the unit has planned nothing yet (so no dropdown is ever empty). Template changes are additive: a mode-aware caption, a manual-indicator hint, and one extra `data-` attribute. No model change, no migration, no new endpoint, no new dependency.

**Status:** Implemented (commit pending) — 16/16 module, 102/102 suite, render-diff clean, `node --check` OK.

**Tech Stack:** Django 6.1.1 (verified in `.venv`), Bootstrap 5.3, vanilla JS. `difflib` not used. No pip install.

**Spec:** `C:\Users\cubeb\Downloads\Lakukan perubahan bagian monitoring dan evaluasi, agar indikator yang muncul hanya yang berkaitan dengan rencana.docx` — sections 1 (workflow: Plan → Evaluation filtering), 2 (user steps), 3 (technical notes: queryset must be limited to planned indicators + target auto-populated from planning).

## Global Constraints

- **No migration, no new model field, no new endpoint, no new pip package.** The planning link already exists as `RisikoUnit.indikator_mutu_terkait` (FK) + `target_capaian_indikator` (Decimal). Nothing new is needed to know what was planned.
- **Section D of `risiko_form.html` must keep its full catalogue.** That page *is* the Plan stage — narrowing it there would make planning impossible. Only G.1 on `risiko_evaluasi.html` changes.
- **Never render an empty dropdown.** If the unit has no planned indicators at all, fall back to today's set (unit + ancestors + global INM), then to `jenis='NASIONAL'`. The caption must say which mode is active so the user is never lied to.
- **Floats into JS/CSS always `|unlocalize`.** Locale `id` renders `85,0`; one comma kills the whole `<script>` block (bugs `84c20ce`, `c4c2a3c`). Template already has `{% load l10n %}` at the top — keep it.
- **Already-linked risks render byte-identical.** The whole linking block is inside `{% if not risiko.indikator_mutu_terkait_id %}`. Do not move or widen that guard.
- **POST acceptance stays permissive.** The view keeps accepting any valid `IndikatorMutu` pk, because 102 of 128 production risks are already linked and the edit form can set an indicator outside the narrowed set. Filtering is a *display* rule per the spec, not an authorization boundary. Add a `ponytail:` comment saying so.
- **UI copy in Bahasa Indonesia; code, comments and this plan in English.**
- Test command: `.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1` — baseline **98/98 OK**.
- Work on `master`; commit after Task 4.

## Verified production data (Supabase `gwaeuzbbdawbekrmrvfd`, read 2026-10-17)

| Fact | Value |
|---|---|
| `akreditasi_risikounit` total | 128 |
| linked (`indikator_mutu_terkait_id` not null) | 102 |
| unlinked | 26 |
| unlinked but unit has other planned risks | 10 |
| risks carrying `[Indikator Mutu Manual: …]` marker | 13 |
| units with ≥1 planned indicator | 20 |
| distinct planned indicators across all units | 89 |
| `akreditasi_indikatormutu` active | 367 (7 global) |
| `IndikatorMutu.sasaran_strategis_id` non-null | **0** — `RenstraFokusItem` links only 15 of 367; do not use Renstra as the planning signal |

Consequence: the planning signal is `RisikoUnit.indikator_mutu_terkait` only. Renstra linkage is too sparse to filter on.

**Reference case** — risk 140 (flebitis, unit 73 Bangsal Perawatan Anak, parent 66 IRIN):
- today's dropdown offers 13 indicators (6 unit-66 + 7 global INM);
- unit 73 has **0** risks with a linked indicator → the planned set is empty → fallback fires, so the existing G.1 fix keeps working;
- risk 140 carries a manual marker naming the flebitis indicator. The planned-set filter must not hide that context: the manual text is shown verbatim as a hint.

---

### Task 1: `_indikator_rencana()` helper — planned set per unit chain

**Files:**
- Modify: `akreditasi/risiko_views.py` (insert helper above `def risiko_evaluasi`, near the other `_`-prefixed helpers around line 155)

**Why:** the filter needs one place that answers "which indicators did this unit's risks plan for". Keeping it a module-level helper makes it testable without a request and reusable if the monitoring page needs it later.

- [x] **Step 1: Add the helper**

```python
def _indikator_rencana(risiko):
    """Indikator mutu yang sudah direncanakan untuk unit risiko ini.

    Sumber: RisikoUnit.indikator_mutu_terkait milik risiko lain di unit yang
    sama + seluruh rantai leluhur unit. Dipakai untuk menyaring dropdown
    penautan di G.1 agar hanya menampilkan indikator yang memang direncanakan
    (bukan seluruh katalog unit + INM nasional).

    Return (queryset_list, mode) dengan mode:
      'RENCANA'  -> ada indikator hasil perencanaan
      'FALLBACK' -> unit belum merencanakan apa pun; kembalikan set lama
    """
    ancestor_ids = []
    cur = getattr(risiko, 'unit', None)
    while cur is not None and cur.pk not in ancestor_ids:
        ancestor_ids.append(cur.pk)
        cur = cur.parent

    planned_ids = list(
        RisikoUnit.objects
        .filter(unit_id__in=ancestor_ids, indikator_mutu_terkait__isnull=False)
        .exclude(pk=risiko.pk)
        .values_list('indikator_mutu_terkait_id', flat=True)
        .distinct()
    )
    # rencana_target = target capaian yang dipilih di tahap Plan oleh risiko
    # unit yang sama (Min menangani kasus dua risiko beda nilai -> ambil
    # yang paling longgar; anotasi conditional butuh `filter=`, tersedia di
    # Django 6.1). Risiko unit leluhur tidak dihitung -> None -> template
    # jatuh ke target_nilai master lewat JS.
    _rencana_target = Min('risiko_terkait__target_capaian_indikator',
                          filter=Q(risiko_terkait__unit_id=risiko.unit_id))

    if planned_ids:
        qs = (IndikatorMutu.objects
              .filter(aktif=True, pk__in=planned_ids)
              .select_related('unit')
              .annotate(rencana_target=_rencana_target)
              .order_by('jenis', 'kode_indikator'))
        return list(qs), 'RENCANA'

    # ponytail: unit belum punya rencana sama sekali -> perilaku lama
    # (unit + leluhur + INM global). Naikkan ke 'hanya rencana' begitu
    # seluruh unit sudah mengisi section D.
    qs = (IndikatorMutu.objects
          .filter(aktif=True)
          .filter(Q(unit_id__in=ancestor_ids) | Q(unit__isnull=True))
          .select_related('unit')
          .annotate(rencana_target=_rencana_target)
          .order_by('jenis', 'kode_indikator'))
    out = list(qs)
    if not out:
        out = list(IndikatorMutu.objects.filter(aktif=True, jenis='NASIONAL')
                   .order_by('kode_indikator'))
    return out, 'FALLBACK'
```

- [x] **Step 2: Verify it imports and returns for the reference case**

```bash
.venv/Scripts/python.exe manage.py shell -c "
from akreditasi.risiko_views import _indikator_rencana
from akreditasi.risiko_models import RisikoUnit
r = RisikoUnit.objects.filter(unit__name__icontains='Anak').first()
print(r.pk if r else None, [(i.kode_indikator) for i in _indikator_rencana(r)[0]][:3], _indikator_rencana(r)[1] if r else '')
"
```

Expected: a pk, a non-empty code list, and `FALLBACK` (local dev DB has no planned rows for that unit).

---

### Task 2: Wire the planned set into `risiko_evaluasi` context

**Files:**
- Modify: `akreditasi/risiko_views.py:818-834` (the `indikator_kandidat` block) and `:836-846` (the `ctx` dict)

- [x] **Step 1: Replace the inline candidate query with the helper**

Replace the whole `indikator_kandidat = []` / `if not risiko.indikator_mutu_terkait_id:` block with:

```python
    indikator_kandidat = []
    indikator_kandidat_mode = ''
    indikator_manual_hint = ''
    if not risiko.indikator_mutu_terkait_id:
        indikator_kandidat, indikator_kandidat_mode = _indikator_rencana(risiko)
        # Indikator yang dulu diketik manual (marker di deskripsi_risiko)
        # ditampilkan apa adanya sebagai petunjuk pilihan, tanpa pencocokan
        # otomatis — nama bebas tidak bisa dipetakan ke master secara andal.
        m = re.search(r'\[Indikator Mutu Manual:\s*(.+?)\]', risiko.deskripsi_risiko or '', re.S)
        if m:
            indikator_manual_hint = m.group(1).strip()
```

- [x] **Step 2: Add the two new context keys**

In the `ctx` dict, after `'indikator_kandidat': indikator_kandidat,`:

```python
        'indikator_kandidat_mode': indikator_kandidat_mode,
        'indikator_manual_hint': indikator_manual_hint,
```

- [x] **Step 3: Add the `re` and `Min` imports**

`akreditasi/risiko_views.py` currently imports no `re` at module level (local `import re as _re` exists inside `api_indikator_by_unit`) and imports only `Count, Q` from `django.db.models`. Add `import re` to the stdlib import block (top of file, above `from decimal import Decimal`) and extend the db.models import to `from django.db.models import Count, Q, Min`.

- [x] **Step 4: Confirm nothing else reads the old variable shape**

```bash
grep -n 'indikator_kandidat' akreditasi/risiko_views.py templates/akreditasi/risiko_evaluasi.html
```

Expected: view lines only from Step 1–2, template lines 211 and 224 (handled in Task 3).

---

### Task 3: Template — caption, manual hint, planned target

**Files:**
- Modify: `templates/akreditasi/risiko_evaluasi.html:205-227`

- [x] **Step 1: Change the caption to state the active mode**

Replace the single `<small class="text-muted" …>` under the select (currently `Pilihan mencakup indikator unit ini + INM nasional ({{ indikator_kandidat|length }} indikator). Target otomatis terisi saat dipilih.`) with:

```html
<small class="text-muted" style="font-size:.66rem;">
    {% if indikator_kandidat_mode == 'RENCANA' %}
    Hanya indikator yang sudah direncanakan pada unit ini ({{ indikator_kandidat|length }} indikator). Target terisi otomatis dari tahap perencanaan.
    {% else %}
    Unit ini belum memiliki indikator pada tahap perencanaan, sehingga ditampilkan indikator unit + INM nasional ({{ indikator_kandidat|length }} indikator). Lengkapi <a href="{% url 'akreditasi:risiko_edit' risiko_id=risiko.pk %}">perencanaan risiko</a> agar pilihan menyempit otomatis.
    {% endif %}
</small>
{% if indikator_manual_hint %}
<div class="alert alert-warning py-1 px-2 mt-1 mb-0" style="font-size:.66rem;">
    <i class="bi bi-pencil-square me-1"></i>Indikator yang Anda tulis manual saat perencanaan: <strong>{{ indikator_manual_hint }}</strong> — pilih indikator master yang paling mendekati.
</div>
{% endif %}
```

- [x] **Step 2: Carry the planned target on each option**

Inside the `{% for ind in indikator_kandidat %}` option tag, add one attribute after `data-target`:

```html
data-target-rencana="{% if ind.rencana_target is not None %}{{ ind.rencana_target|unlocalize }}{% endif %}"
```

`rencana_target` comes from the `Min(..., filter=Q(risiko_terkait__unit_id=risiko.unit_id))` annotation added in Task 1. It is `None` for indicators no same-unit risk planned (including every ancestor-unit and global INM indicator while evaluating an unlinked risk) — the `is not None` guard then renders an empty attribute and JS falls back to `opt.dataset.target` (the master `target_nilai`), which is today's behaviour. Never drop the guard: an unguarded `None` renders the literal string `"None"` and `parseFloat("None")` poisons `targetVal`.

- [x] **Step 3: Prefer the planned target in the change handler**

In `risiko_evaluasi.html` `linkSelect.addEventListener('change', …)` (~line 630), change the target source line to prefer the planned value:

```js
            const tgt = opt.dataset.targetRencana || opt.dataset.target;
```

(Keep the existing `if (tgt && !targetLinkInput.value.trim())` guard and the `parseFloat` fallback.)

- [x] **Step 4: Syntax-check the rendered script**

Render the page for an unlinked risk and run `node --check` on the extracted `<script>` block, exactly as done for `4f8a06e` (`ev_unlinked.js`). Expected: no output, exit 0.

---

### Task 4: Tests

**Files:**
- Modify: `akreditasi/tests_evaluasi_indikator.py` (append 4 tests to `EvaluasiIndikatorMutuTest`)

All fixtures are created inside the test — never assert against production rows.

- [x] **Step 1: `test_candidates_only_include_planned_indicators`**

Create a second indicator in the same unit that no risk references (`kode='INM-UGD-02'`, `nama='Kepatuhan Identifikasi Pasien UGD'`). Create a **second risk** `risk_b` on `self.unit` still linked to `self.indikator` (this is what makes the unit's planned set non-empty), then unlink the fixture risk (`self.risiko.indikator_mutu_terkait = None; save()`). GET the fixture risk's evaluation page. Assert: `self.indikator.nama_indikator` **is** in the response, `Kepatuhan Identifikasi Pasien UGD` **is not**, caption contains `Hanya indikator yang sudah direncanakan`, and each `<option>` carries `data-target-rencana=`.

Gotcha: if you only create the unplanned indicator and unlink the fixture risk *without* `risk_b`, the planned set is empty → fallback fires → both indicators show and the "is not" assertion fails. `risk_b` is the test.

- [x] **Step 2: `test_candidates_fall_back_when_unit_has_no_plan`**

Delete every `RisikoUnit` of the unit except the one under test, unlink it, GET. Assert the page still offers an indicator (status 200, `id="link-indikator-select"` present, at least one `data-target=`), and the caption contains `belum memiliki indikator pada tahap perencanaan`. This is the guard that keeps risk 140 working.

- [x] **Step 3: `test_candidates_include_ancestor_unit_plan`**

Mirror the structure of `test_evaluasi_candidates_include_parent_unit_indicators` (line ~270): parent `UnitKerja` + child unit, `IndikatorMutu('IMP-PARENT-01', …)` owned by the parent, a risk `rc` on the **child** (the page under test, unlinked), plus a risk on the **parent** linked to `IMP-PARENT-01`. GET `rc`'s evaluation page. Assert `IMP-PARENT-01`'s name appears and the caption is the `RENCANA` variant — proving the ancestor chain feeds the planned set, preserving the `4f8a06e` fix under the new filter.

- [x] **Step 4: `test_manual_marker_renders_as_hint`**

Set `self.risiko.deskripsi_risiko += "\n\n[Indikator Mutu Manual: kepatuhan double-check obat high alert]"`, unlink, `save()`, GET. Assert the response contains `kepatuhan double-check obat high alert` and `Indikator yang Anda tulis manual`.

- [x] **Step 5: Run the module, then the full suite**

```bash
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator -v2
.venv/Scripts/python.exe manage.py test akreditasi.tests_evaluasi_indikator akreditasi.tests_indikator_mutu_charts akreditasi.tests_perencanaan_risiko akreditasi.tests_unit_kerja akreditasi.tests_fmea_rca akreditasi.tests_indikator_form akreditasi.tests_indikator_alur_integrasi -v1
```

Expected: 16/16 for the module (12 existing + 4 new), then **102/102 OK** for the suite (98 + 4).

---

### Task 5: Regression proof, commit, deploy

- [x] **Step 1: Byte-identical proof for already-linked risks**

Pick a linked risk, render `risiko_evaluasi` before and after the change, `diff` the two HTML dumps. Expected: no diff (the whole block is inside `{% if not risiko.indikator_mutu_terkait_id %}`).

- [x] **Step 2: `node --check` every extracted script block**

Both an unlinked render (new caption + hint) and a linked render. Expected: exit 0 for both.

- [x] **Step 3: Commit**

```bash
git add akreditasi/risiko_views.py templates/akreditasi/risiko_evaluasi.html akreditasi/tests_evaluasi_indikator.py docs/superpowers/plans/2026-10-17-monitoring-indikator-rencana-filter.md
git commit -m "feat(risiko): filter G.1 indicator dropdown to planned indicators

Monitoring & evaluation section G.1 offered every indicator of the unit
plus all national INM entries. The planning link (RisikoUnit.indikator_mutu_terkait)
is now the filter source, walked over the unit ancestor chain, with a
documented fallback to the old set when a unit has planned nothing yet.
Manually typed indicator names render as a hint instead of being guessed at."
```

- [x] **Step 4: Push and confirm Vercel**

```bash
git push origin master
sleep 80 && gh api repos/faishaltsq/sim-akreditasi-django/commits/$(git rev-parse --short HEAD)/status --jq '.state, .statuses[].description'
```

Expected: `success` / `Deployment has completed`.

- [x] **Step 5: Report to the user**

State: what changed, the 4 evidence lines (16/16, 102/102, render diff empty, deploy success), the reference case behaviour (risk 140 → fallback + hint), and the instruction to Ctrl+F5.

---

## Review Focus

- A risk whose unit planned indicators **but not this one**: the dropdown narrows and the user cannot pick their intended indicator. Is the caption + the `perencanaan risiko` link enough of an escape hatch? (Yes — they can plan it in section D, then come back. Verify `{% url 'akreditasi:risiko_edit' risiko_id=risiko.pk %}` resolves — the URL pattern is `risiko/<int:risiko_id>/edit/`, kwarg name `risiko_id`.)
- Existing 12 tests must pass **unchanged** — the fallback keeps their assertions valid (`test_evaluasi_offers_link_when_indikator_missing`, `…parent_unit_indicators`, `…fallback_inm_when_no_local` all exercise the FALLBACK branch). Only the 4 new tests pin the RENCANA branch.
- A unit where the *only* planned indicator belongs to a sibling risk that was later deleted: `planned_ids` still resolves (FK `SET_NULL` clears it), so the set shrinks or empties → fallback fires. No crash.
- Two risks in the same unit linked to the *same* indicator: `distinct()` on `values_list` prevents duplicate `<option>` rows.
- `indikator_mutu_terkait` pointing at an indicator that was deactivated (`aktif=False`): the `aktif=True` filter drops it, so a linked-and-deactivated risk shows the read-only banner (guard on `_id`, not on the object) — correct, no crash.
- Manual marker containing `]` inside the text: the non-greedy `(.+?)\]` stops at the first `]`, truncating the hint. Cosmetic only.
- Locale `id`: `data-target-rencana` must render `85.0`, not `85,0`.
