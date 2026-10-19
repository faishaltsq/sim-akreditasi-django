# Pelaksanaan: bukti dokumen + tautan standar akreditasi & EP

**Date:** 2026-10-19
**Status:** Not started
**Spec:** `D:\Downloads\Dibagian pelaksanaan.docx` — verbatim:

> Dibagian pelaksanaan;
> Tambahkan; setiap pelaksanaan ada bukti dokumen dan lingk ke standar akreditasi, EP.

**Goal.** Every risk-mitigation action ("Pelaksanaan Risiko", PDCA **Do**) must
carry document evidence and a link to both the accreditation standard and the
assessment element (EP) it serves.

---

## Scope: what "pelaksanaan" is in this codebase

"Pelaksanaan" is the **Do** phase of Manajemen Risiko. The record is
`TindakLanjutRisiko` (`akreditasi/risiko_models.py:472`), reached through
`RisikoUnit.tindak_lanjut`. Confirmed by the UI it drives:

| Surface | File | What it shows |
|---|---|---|
| Section F of the risk detail | `templates/akreditasi/risiko_detail.html:492-598` | Add form + table of actions |
| G.2 "Status Pelaksanaan" | `templates/akreditasi/risiko_evaluasi.html:289-390` | Per-action status during evaluation |
| Per-unit Do page | `templates/akreditasi/risiko_pelaksanaan.html:294,360` | `risiko_pelaksanaan_unit` |
| Print "Cetak Pelaksanaan (Do)" | `risiko_views.py:1697` | `risiko_pelaksanaan_dokumen` |
| CSV export | `risiko_views.py:1788` | `risiko_pelaksanaan_export_csv` |
| Full report | `templates/akreditasi/risiko_laporan_lengkap.html:430,763,834` | Rincian tindakan |
| Monitoring | `templates/akreditasi/risiko_monitoring_evaluasi.html:333` | Action list |
| Planning preview | `templates/akreditasi/risiko_perencanaan.html:546,588` | Action list |

Not in scope: `RisikoUnit.bukti_pelaksanaan` (a single risk-level attachment on
the risk itself, not per-action) and `CatatanIndikator.bukti_dokumen` (indicator
measurement, already handled by the EP-sync work).

---

## Verified facts (local dev DB, read 2026-10-19)

**`TindakLanjutRisiko`** — fields today: `risiko`, `urutan`, `aksi`,
`status_aksi` (BELUM/SEDANG/SELESAI), `tanggal_mulai`, `tanggal_selesai`,
`bukti_upload` (single `FileField` → `risiko/bukti/`), `catatan`.

- 21 rows total
- **0 rows have `bukti_upload`** — the field exists but nothing uses it
- 6 rows are `SELESAI`; all 6 lack evidence
- 19 rows have `tanggal_selesai`

**The link to standards and EP does not exist.** `TindakLanjutRisiko` has no FK
to `Category` or `StandardItem`. `RisikoUnit` has no such FK either — only
`indikator_mutu_terkait`.

**Standards and EP catalog:**

- `Category` (`models.py:85`) = **standar / pokja**, 16 rows. `code` (`AKP`,
  `HPK`, `KE`, `KPS`, `MFK`, `MRMIK`, …), `name`, `kelompok` (5 groups),
  `unit_pengampu`.
- `StandardItem` (`models.py:154`) = **EP**, 1053 rows. `code` is unique and
  shaped `<Category.code> <sub_standard> EP <n>`, e.g. `AKP 1 EP 1`.
  `description` is the literal text of the EP. `category` FK → `Category`.
- `EvidenceReq` (`models.py:171`) = per-EP proof requirement, 769 rows,
  681 EPs have at least one. `EvidenceFile` = uploaded proof, 1 row (unused).

**Precedent for this exact pattern** — `IndikatorMutu.ep_terkait`
(`risiko_models.py:556`), added by the EP-sync work in `fa921a5`:

- model: `ep_terkait` FK `StandardItem` + provenance `ep_sumber` / `ep_skor`
- form: `indikator_views.py:532` builds
  `ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')`
  and puts it in context
- form template: `indikator_form.html:234-242`
- detail: `indikator_detail.html:51,149,160` shows the EP code and links to
  `akreditasi:modal_bukti_data` for uploading against that EP
- helper: `ep_sync.buktiringkas(ep)` (`ep_sync.py:350`) summarises an EP's
  `EvidenceReq` and uploaded file counts

**Do not imitate `UnitKerja.standar_terkait`** (`models.py:51`) — it is a
`JSONField` holding codes, not a real FK. It has no referential integrity and
no join. Real FKs only.

**Next migration number: `0043`.** `0042` belongs to the EP-sync work and is
already applied to Supabase (checked: `ep_terkait_id`, `ep_skor`, `ep_sumber`
present on `akreditasi_indikatormutu`).

**Creation paths to update:**

- `risiko_views.py:516` `risiko_detail` — the inline POST handler (L521-542)
  builds `TindakLanjutRisiko(...)` and calls `full_clean(exclude=['bukti_upload'])`
- `risiko_views.py:788` `risiko_evaluasi` — bulk-creates actions from the G.2
  form, currently only reads `status_aksi` per bullet

---

## Design decisions

**1. Two FKs, EP implies standar.** The spec names two links — "standar
akreditasi" and "EP". A single `ep_terkait` would derive the standar through
`StandardItem.category`, but a mitigation action can legitimately serve a whole
standar without a specific EP. So: `standar_terkait` FK → `Category` and
`ep_terkait` FK → `StandardItem`, both nullable. The view keeps them consistent:
choosing an EP sets the standar from `ep.category`; the EP dropdown is filtered
to the chosen standar. This also lets the standar column render without a join
through two hops.

**2. Bukti is required once an action is `SELESAI`, not at creation.** The spec
says "setiap pelaksanaan ada bukti dokumen". Enforcing it at creation would
block the 15 of 21 rows still in progress and make the Do form unusable for
planning. The enforceable reading: a *completed* action must carry evidence.
So validation lands on `clean()`, not on the field. The form gets a `required`
hint on the file input only when status is SELESAI (client-side, advisory), and
the server rejects `SELESAI` without evidence with a message naming the fix.
Existing rows are left alone — the migration adds nothing to them and no
backfill runs; a follow-up data task can decide whether those 6 stale rows need
real documents or should be reopened.

**3. One file per action stays.** `bukti_upload` is a single `FileField`.
Multiple attachments per action is a real want but a different feature (it
wants a through-model like `EvidenceFile`); out of scope here, flagged below.

**4. Reuse the EP evidence machinery rather than duplicating it.** Since the
action now points at an EP, the row can show that EP's proof requirements via
`ep_sync.buktiringkas(ep)` and deep-link to
`akreditasi:modal_bukti_data <ep.pk>`, exactly as `indikator_detail.html:160`
does. That gives the "bukti dokumen" half real teeth: an action can reference
the EP whose documents already exist, instead of holding a stray upload nobody
can trace.

---

## Global constraints

- Working dir `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`,
  venv `.venv/Scripts/python.exe`, branch `master`.
- **A parallel session is active in this repo.** Stage files by name only. Do
  not touch `ai_prompts.py`, `ai_service.py`, `ai_views.py`, `ep_sync.py`,
  `system_models.py`, or anything under `akreditasi/management/commands/` that
  the other session owns. `risiko_models.py` and `risiko_views.py` are shared —
  re-read before every patch and re-check `git status` before every commit.
- `staticfiles/` is tracked for Vercel. Do not delete it. Run `collectstatic`
  and commit the hashed artefacts **only if a static asset changes**; this plan
  touches templates and Python, so normally none.
- Test DB is SQLite and migrations seed demo units (`IRIN`, `BANGSAL-ANAK`, …).
  Every fixture must use a unique prefix in `code`, `kode_indikator`, and any
  other unique field.
- Migration must be applied to Supabase manually after deploy — it does not run
  on Vercel.

---

## Task 1: `TindakLanjutRisiko` gains standar + EP links

**Files:**
- Modify: `akreditasi/risiko_models.py`
- Create: `akreditasi/migrations/0043_tindaklanjutrisiko_standar_terkait_ep_terkait.py`
- Test: `akreditasi/tests_pelaksanaan_bukti_ep.py` (new)

- [ ] **Step 1: Write the failing test**

```python
from django.core.exceptions import ValidationError
from django.test import TestCase
from akreditasi.models import Category, StandardItem
from akreditasi.risiko_models import RisikoUnit, TindakLanjutRisiko, UnitKerja


def _mk_category(code):
    from akreditasi.models import Framework
    fw, _ = Framework.objects.get_or_create(name='STARKES', cycle_type='PDCA')
    return Category.objects.create(framework=fw, code=code, name=f'Pokja {code}')


def _mk_ep(category, code):
    return StandardItem.objects.create(
        category=category, sub_standard=code, sub_title='Judul',
        code=code, description='Bunyi EP')


class PelaksanaanLinkTest(TestCase):
    def test_action_carries_standar_and_ep(self):
        cat = _mk_category('TST-A')
        ep = _mk_ep(cat, 'TST-A 1 EP 1')
        unit = UnitKerja.objects.create(code='TSTU-A', name='Unit A', level=3)
        risiko = RisikoUnit.objects.create(unit=unit, tahun=2026,
                                           masalah='x', deskripsi_risiko='y')
        tl = TindakLanjutRisiko.objects.create(
            risiko=risiko, urutan=1, aksi='Aksi', status_aksi='SEDANG',
            standar_terkait=cat, ep_terkait=ep)
        tl.refresh_from_db()
        self.assertEqual(tl.standar_terkait_id, cat.pk)
        self.assertEqual(tl.ep_terkait_id, ep.pk)
        # reverse relations resolve, for the template's benefit
        self.assertIn(tl, cat.tindak_lanjut_set.all())
        self.assertIn(tl, ep.tindak_lanjut_set.all())

    def test_ep_must_belong_to_the_declared_standar(self):
        """The view keeps them consistent; the model must not accept drift."""
        cat_a = _mk_category('TST-B')
        cat_b = _mk_category('TST-C')
        ep_of_b = _mk_ep(cat_b, 'TST-C 1 EP 1')
        unit = UnitKerja.objects.create(code='TSTU-B', name='Unit B', level=3)
        risiko = RisikoUnit.objects.create(unit=unit, tahun=2026,
                                           masalah='x', deskripsi_risiko='y')
        tl = TindakLanjutRisiko(
            risiko=risiko, urutan=1, aksi='Aksi',
            standar_terkait=cat_a, ep_terkait=ep_of_b)
        with self.assertRaises(ValidationError):
            tl.full_clean()
```

- [ ] **Step 2: Run to confirm failure**

Run: `.venv/Scripts/python.exe manage.py test akreditasi.tests_pelaksanaan_bukti_ep -v1`
Expected: `AttributeError`/`TypeError` — the fields do not exist.

- [ ] **Step 3: Add the fields**

```python
    standar_terkait = models.ForeignKey(
        'akreditasi.Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindak_lanjut_set', verbose_name='Standar Akreditasi Terkait')
    ep_terkait = models.ForeignKey(
        'akreditasi.StandardItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tindak_lanjut_set', verbose_name='EP Terkait')

    def clean(self):
        super().clean()
        if self.ep_terkait_id and self.standar_terkait_id:
            if self.ep_terkait.category_id != self.standar_terkait_id:
                raise ValidationError({
                    'ep_terkait': 'EP harus berasal dari standar yang dipilih.'})
```

`SET_NULL`, not `CASCADE` — deleting a standard or an EP must not destroy the
hospital's record of what it did. The link goes stale and the template shows
"tidak lagi tersedia"; the action itself survives.

- [ ] **Step 4: Migrate**

Run: `.venv/Scripts/python.exe manage.py makemigrations akreditasi`
Expected: a single migration creating `0043`, two `AddField`s, no data
operation. Confirm the file name starts with `0043` and contains nothing else.

- [ ] **Step 5: Run to confirm pass**

- [ ] **Step 6: Commit**

---

## Task 2: the Do form and table on the risk detail page

**Files:**
- Modify: `akreditasi/risiko_views.py` (`risiko_detail`, L516-562)
- Modify: `templates/akreditasi/risiko_detail.html` (L506-598)
- Test: `akreditasi/tests_pelaksanaan_bukti_ep.py`

- [ ] **Step 1: Write the failing test**

```python
from django.urls import reverse


class RisikoDetailFormTest(TestCase):
    def _login(self):
        from django.contrib.auth.models import User
        u = User.objects.create_user('pel-f', 'p@x.id', 'x')
        from akreditasi.models import UserProfile  # adjust import to real path
        UserProfile.objects.create(user=u, role='SUPER_ADMIN')
        self.client.force_login(u)

    def test_form_offers_standar_and_filtered_ep(self):
        ...  # build unit + risiko + two categories, two EPs
        res = self.client.get(reverse('akreditasi:risiko_detail', args=[risiko.pk]))
        self.assertContains(res, 'name="standar_terkait"')
        self.assertContains(res, 'name="ep_terkait"')

    def test_posting_an_action_saves_both_links(self):
        ...  # POST standar_terkait + ep_terkait + bukti file
        tl = TindakLanjutRisiko.objects.latest('id')
        self.assertEqual(tl.standar_terkait_id, cat.pk)
        self.assertEqual(tl.ep_terkait_id, ep.pk)
        self.assertTrue(tl.bukti_upload)

    def test_ep_dropdown_is_limited_to_the_chosen_standar(self):
        ...  # assert the other standar's EP code is absent from the page
```

- [ ] **Step 2: Run to confirm failure**

- [ ] **Step 3: Teach the view**

In `risiko_detail`:

```python
    standar_id = request.POST.get('standar_terkait') or None
    ep_id      = request.POST.get('ep_terkait') or None
    # EP decides the standar when both are sent; the form filters EP by
    # standar, so a mismatch means a stale page, and the EP wins.
    if ep_id:
        standar_id = StandardItem.objects.filter(pk=ep_id)\
                       .values_list('category_id', flat=True).first() or standar_id
```

Add both to the constructor, and add the `ValidationError` raised by
`full_clean()` to the existing `except Exception as e` path so a drift attempt
re-renders with the message rather than 500. `full_clean` is already called at
L533 with `exclude=['bukti_upload']` — keep the exclusion, the file is validated
in Task 5.

Context gains the two pickers, built the same way `indikator_views.py:532` does:

```python
    standar_list = Category.objects.order_by('code')
    ep_list = StandardItem.objects.select_related('category').order_by('category__code', 'code')
```

- [ ] **Step 4: Add the form controls and the table columns**

In the add form (after the existing `row g-2 mb-2` holding dates and file):
Standar select, then EP select. Both plain `<select>` with
`onchange="this.form.submit()"`-free filters — this page has no AJAX
infrastructure, so filter the EP list client-side with a small `<script>`
mapping `ep.category_id` from `data-` attributes, mirroring the idiom already
in `indikator_form.html:459`.

In the table (L555-563), add two columns after "Bukti Dokumen":

```html
<th>Standar</th>
<th>EP</th>
```

rendering `{{ tl.standar_terkait.code }} — {{ tl.standar_terkait.name }}` and,
for the EP, its code plus a `title` carrying `description` (the bunyi EP), with
`—` when unset. Bump the `{% empty %}` `colspan` from 7 to 9.

- [ ] **Step 5: Run to confirm pass**

- [ ] **Step 6: Commit**

---

## Task 3: every other surface that lists pelaksanaan

The spec applies to the section as a whole, not just the risk detail page. Each
of these already loops `tindak_lanjut`; each gains the two columns and the
evidence state.

- [ ] **Step 1: Per-unit Do page** — `templates/akreditasi/risiko_pelaksanaan.html`
  (L294 and the rowspan table at L360-415). Add Standar and EP columns. Note the
  rowspan layout: cells at L363-368 are per-*risiko*, cells at L415 is
  per-action, so the new columns join the per-action group. Read the table
  before editing; a misplaced cell will silently break the rowspan arithmetic.
- [ ] **Step 2: Print view** — `risiko_views.py:1697`
  `risiko_pelaksanaan_dokumen`. Add the columns to its template so the printed
  Do sheet a surveyor receives names the standard and EP each action served.
- [ ] **Step 3: CSV export** — `risiko_views.py:1788`
  `risiko_pelaksanaan_export_csv`. Append `standar`, `kode_ep`, `judul_ep`,
  `ada_bukti` columns at the end of each row; do not reorder existing ones,
  something may parse that file positionally.
- [ ] **Step 4: Full report** —
  `templates/akreditasi/risiko_laporan_lengkap.html:430,763,834`. Same two
  columns; there are three separate loops here, all three.
- [ ] **Step 5: Monitoring** —
  `templates/akreditasi/risiko_monitoring_evaluasi.html:333`. Same.
- [ ] **Step 6: Planning preview** —
  `templates/akreditasi/risiko_perencanaan.html:546,588`. Same; two loops.
- [ ] **Step 7: Run tests + a manual render of each page**
- [ ] **Step 8: Commit**

---

## Task 4: G.2 can set the link during evaluation, and the EP evidence deep-link

**Files:**
- Modify: `akreditasi/risiko_views.py` (`risiko_evaluasi`, L726; bulk create L788)
- Modify: `templates/akreditasi/risiko_evaluasi.html` (L289-390)
- Modify: `templates/akreditasi/risiko_detail.html` (evidence column)

- [ ] **Step 1: Carry the link into the bulk create**

`risiko_views.py:788` creates an action per bullet from the G.2 form, currently
reading only `status_aksi`. The G.2 form gains one standar/EP pair per bullet,
so the record made during evaluation already satisfies the spec instead of
being born incomplete. Failing test first, as everywhere else.

- [ ] **Step 2: Show the EP's existing proof requirements on the action row**

In `risiko_detail.html`'s "Bukti Dokumen" column, when `tl.ep_terkait` is set,
append a compact line built from `ep_sync.buktiringkas(ep)` — how many
requirements the EP has and how many are already fulfilled — plus the same
`akreditasi:modal_bukti_data` deep link `indikator_detail.html:160` uses. This
is what makes "link ke standar akreditasi, EP" useful rather than decorative:
the row points at the EP, and from there at the documents that EP demands.

Import `buktiringkas` from `.ep_sync` in `risiko_views.py`. Guard against an EP
with no `EvidenceReq` — `indikator_detail.html:182` already models that copy.

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Commit**

---

## Task 5: enforce the evidence rule, then regress

**Files:**
- Modify: `akreditasi/risiko_models.py` (`TindakLanjutRisiko.clean`)
- Modify: `akreditasi/risiko_views.py` (error surface)
- Modify: `templates/akreditasi/risiko_detail.html` (advisory `required` on the
  file input when status is SELESAI)

- [ ] **Step 1: Failing test for the rule**

```python
class BuktiWajibSaatSelesaiTest(TestCase):
    def test_selesai_without_evidence_is_rejected(self):
        ...  # status_aksi='SELESAI', bukti_upload=''
        with self.assertRaises(ValidationError):
            tl.full_clean()

    def test_in_progress_without_evidence_is_allowed(self):
        ...  # status_aksi='SEDANG', bukti_upload=''
        tl.full_clean()  # must not raise

    def test_selesai_with_evidence_passes(self):
        ...  # upload a file, status SELESAI
        tl.full_clean()  # must not raise
```

- [ ] **Step 2: Implement in `clean()`**

Add to the `clean()` from Task 1:

```python
        if self.status_aksi == 'SELESAI' and not self.bukti_upload:
            raise ValidationError({
                'bukti_upload': 'Pelaksanaan berstatus Selesai wajib punya bukti dokumen.'})
```

- [ ] **Step 3: Surface it**

`risiko_detail` already catches broadly at L541 and re-renders with
`messages.error`. Make the message read as a fix, not a stack trace:
`'Gagal: {e}'` will print the Django error dict verbatim — replace with a
branch that renders `e.message_dict` cleanly when it is a validation error.

- [ ] **Step 4: Advisory client-side hint**

In the add form, `required` on the file input only when `status_aksi` is
`SELESAI`. This page has no AJAX, so the honest approach is a tiny `<script>`
toggling the attribute on the status `<select>`'s `change` event. Keep it
advisory — the server rule is the real one.

- [ ] **Step 5: Full regression**

Run:
`.venv/Scripts/python.exe manage.py test akreditasi -v1`
`.venv/Scripts/python.exe manage.py test accounts pasien -v1`
`.venv/Scripts/python.exe manage.py check`

Baseline before this plan: **akreditasi 196, accounts+pasien 85, full 281, all
OK, check clean.** Expected after: 281 + every test added here, all OK.

- [ ] **Step 6: Commit**

---

## Task 6: data decision and deploy

- [ ] **Step 1: The six stale rows.** 6 actions are `SELESAI` with no evidence
  and no standar/EP. The new rule does not retroactively reject them — Django
  never re-validates saved rows. Decide with the stakeholder: attach real
  documents and links, or drop them back to `SEDANG`. Do **not** write a
  migration that silently flips status.
- [ ] **Step 2: Apply `0043` to Supabase by hand** after deploy. Memory note:
  migrations do not run on Vercel.
- [ ] **Step 3: `collectstatic` only if a static asset changed.** This plan
  should not need it — verify `git status -- staticfiles` is clean instead of
  assuming.
- [ ] **Step 4: Push and verify the deployment** the same way as the last plan:
  `vercel ls` for a Production Ready deployment, then a smoke check that the
  routes still answer.

---

## Review Focus

- **The evidence rule is the part users will push back on.** Requiring a
  document to close an action is the whole point of the spec, and it is also
  the part that will be reported as friction. Task 5 makes it server-side
  authoritative and client-side advisory, which is the right split — but if the
  stakeholder wants evidence optional, this is the step to soften, not the FKs.
- **`SET_NULL` means links rot silently.** Deleting a standard or an EP leaves
  actions pointing at nothing. The templates show `—`, which is honest, but
  there is no report listing actions whose links have gone stale. If that
  matters, it is a separate small task, not a change to the migration.
- **The rowspan table in `risiko_pelaksanaan.html` is the fragile edit.** Its
  per-risk and per-action cells are interleaved. Add columns to the per-action
  group and re-check the rendered table in a browser, not just the test suite —
  a bad rowspan renders as a shifted grid rather than an error.
- **Two FKs can drift if any other creation path appears.** `risiko_views.py:524`
  and `:788` are the only two today. Any future one must route through
  `full_clean()` or the `clean()` guard never runs.
- **`bukti_upload` is one file.** The spec says "bukti dokumen", singular-ish,
  so one file satisfies it, and reusing `EvidenceFile` per EP gives the trace
  path. If a surveyor wants several attachments per action, that is a
  through-model and a bigger change — do not bolt it onto this one.
- **This shares `risiko_models.py` and `risiko_views.py` with nothing else
  right now, but `risiko_models.py` was just edited by the EP-sync work.**
  Re-read before each patch and re-check `git status` before each commit; the
  other session's tree is live.
