# IGD Initial Assessment, Unit-Scoped Visit List & Contextual Detail Links

Date: 2026-11-06
Source request: `Lakukan perubahan ini.docx` (3 items, screenshots of `/pasien/kunjungan/3/`) **plus** a follow-up
message with a screenshot of `/control/layanan/?unit=54&tanggal=2026-11-06` (3 further items)
Scope: `pasien` app (kunjungan detail, asesmen awal form, visit list) and `akreditasi` app
(kontrol layanan block + snapshot)
Status: implementation complete; 75 targeted tests pass. Browser layout/keyboard verification and full pasien + akreditasi regression suite remain pending.

Implementation completion notes:
- SEP uses the existing JSON endpoint with same-origin CSRF-protected POST, duplicate-click prevention, and accessible inline success/error feedback. Clinical status is intentionally not overwritten by a SEP message.
- SPRI retains the assigned destination bed even before admission; current-location badges continue using bed_aktif.
- Regression coverage includes full-page save/copy return URLs, row-specific IGD/RAJAL destinations, SEP JSON wiring, and snapshot cache version.

---

## 1. Request as written

The docx contains three asks, all about the visit detail page reached from the IGD dashboard:

1. Remove `Ruangan: Bangsal Mawar …` — the patient has not been admitted to a ward yet.
2. Replace the old "Formulir Asesmen Awal" with the new assessment form; the `Edit / Lengkapi Asesmen Awal` entry must use the new form.
3. Render that new form full width/page — the bottom menu is cut off.

A follow-up message then added three asks, from the ARIMA Control `Layanan Unit` page
(`/control/layanan/?unit=54&tanggal=2026-11-06`, IGD unit, 9 patients):

4. Remove the "kunjungan" menu from `/pasien/kunjungan/` — it is already covered by `/pasien/igd/`.
5. Make sure the patient data matches each unit's own scope — but keep it out of *that* menu.
6. The `Detail` button on that page should lead to the IGD menu instead.

OCR of the two embedded screenshots confirms both are `/pasien/kunjungan/3/` (REG-2026-0003, Budi Santoso):

- Screenshot 1: header badge `Ruangan: Bangsal Mawar (Kelas I) (Kelas Kelas I) · Bed: 03`, section titled
  `Formulir Asesmen Awal Medis & Keperawatan (Standar Akreditasi 3.09)` with four read-only summary cards
  and the `Edit / Lengkapi Asesmen Awal` button.
- Screenshot 2: the 4-step wizard (`1. KU & TTV`, `2. Nyeri & Gizi (MST)`, `3. Fungsional & Fisik`,
  `4. Diagnosis & Risiko`) with `Set Normal / Baik`, the TTV inputs and `Salin dari Asesmen Sebelumnya`.

## 2. Findings (verified in code, not inferred)

### F1 — The ward badge is rendered from a bed the patient does not occupy

`templates/pasien/kunjungan_detail.html:72-78` renders the badge whenever `k.bed` is set:

```django
{% if k.bed %}
  Ruangan: {{ k.bed.ruangan.nama }} (Kelas {{ k.bed.ruangan.get_kelas_display }}) • Bed: {{ k.bed.kode_bed }}
{% endif %}
```

`KunjunganPasien.bed` (`pasien/models.py:323`) means *the bed currently occupied*: it is set on admission
(`models.py:606-607`, `models.py:979-981`) and cleared on discharge (`models.py:624-625`). The template, however,
does not check `status`, so any stale/seed value leaks onto an IGD visit.

The demo row violates that invariant: `seed_pasien_data.py:134-154` assigns `bed: b3` **and** marks the bed `TERISI`
for `REG-2026-0003`, whose `status` is `TRIAGE` (confirmed against the local DB: `IGD / TRIAGE / bed=Bangsal Mawar`).
So the data is wrong *and* the display has no guard.

### F2 — The class label is duplicated twice

- `Ruangan.nama` in seed data already contains the class: `Bangsal Mawar (Kelas I)`.
- `Ruangan.get_kelas_display()` returns `Kelas I` (choices at `models.py:157`).
- The template prefixes `Kelas ` to that value → `(Kelas Kelas I)`.

Result: `Bangsal Mawar (Kelas I) (Kelas Kelas I)`. Two independent defects, one output.

### F3 — The assessment modal is the reason the bottom menu is clipped

The new 4-step wizard already exists and is the form behind `Edit / Lengkapi Asesmen Awal`:
`kunjungan_detail.html:1133-1788`, posting to `pasien:igd_asesmen_awal_save` (`views.py:1953`), with
`action_mode` = `draft|selesai`.

It sits inside `<div class="modal-dialog modal-xl modal-dialog-scrollable">`, and the `<form>` wraps
`modal-header`, `modal-body` and `modal-footer` (`kunjungan_detail.html:1136-1785`). Bootstrap's scrollable
dialog expects `.modal-body` to be the scroll container, but the intermediate `<form>` element breaks that flex
chain: the body never becomes scrollable, the dialog overflows, and the footer action bar
(`Batal`, `Simpan Draft`, `Simpan & Selesaikan Asesmen`) plus the per-tab `Lanjut` buttons fall below the
viewport. This is exactly "menu dibawah terpotong".

### F4 — Two assessment forms exist and are not interchangeable

| Entry point | Template | Endpoint | Tabs |
|---|---|---|---|
| IGD dashboard `Asesmen` button | `igd_dashboard.html:1262-2285` | `igd_asesmen_medis_save` (`views.py:2214`) | 7 (Anamnesis, ABCDE, Biopsikososial, Diagnosis, **Triase & Cara Datang**, Fisik Lengkap, **Tatalaksana & SBAR**) |
| Visit detail `Edit / Lengkapi` | `kunjungan_detail.html:1133-1788` | `igd_asesmen_awal_save` (`views.py:1953`) | 4 (KU & TTV, Nyeri & Gizi, Fungsional & Fisik, Diagnosis & Risiko) |

The 7-tab form owns fields the 4-tab form does not: `cara_datang`, `waktu_asesmen_dokter`, `suhu_lokasi`,
`nadi_kekuatan`, `nadi_irama`, `pernapasan_pola`, `spo2_alat`, `metode_risiko_jatuh`, `skala_nyeri_sifat`, and the
SBAR handover block (`sbar_situation/background/assessment/recommendation`) that is printed by
`cetak_asesmen_medis_igd.html`. Deleting it without a home for those fields is a clinical data-capture regression.

### F5 — Latent defects worth fixing while touching this page

- `icd10_codes` / `sdki_codes` are only in the IGD dashboard context (`views.py:1095-1096`); the datalists in
  `kunjungan_detail.html:1791-1800` therefore render empty today. The new page must pass them.
- `igd_asesmen_awal_save` is `@login_required` only — no unit-scope authorization, unlike `kunjungan_detail`
  (`views.py:297-305`, `can_read_kunjungan`). Any logged-in user can POST any `pk`.

### F6 — `_layanan_block` and `resolve_visit_ids` give **different** answers for the same visit

Two functions answer "which unit owns this visit", and they disagree:

| Function | Rule | Consumer |
|---|---|---|
| `resolve_visit_ids` (`layanan_unit.py:218-234`) | `unit_kerja__code` **wins**; the poliklinik/ruangan map is only the fallback | `_emr_block`, `kunjungan_scope_q` (front-office, pasien_detail, kunjungan_detail) |
| `_layanan_block` (`kontrol_data.py:356-366`) | for non-IGD, the map wins and `unit_kerja` is only the **fallback** | the `Layanan Unit` page (the screenshot) |

Verified probe on the live dev DB (RAJAL visit, `poliklinik='Poli Jantung & Pembuluh Darah'`,
`unit_kerja=ADMISI`):

```
resolve_visit_ids(POLI-JANTUNG): []          # correct — the visit is still at the front desk
resolve_visit_ids(ADMISI)      : [192]       # correct
_layanan_block(POLI-JANTUNG)   : ['PROBE-1'] # WRONG — leaks a visit owned by the admission desk
_layanan_block(ADMISI)         : ['PROBE-1']
```

That is exactly ask 5 ("pastikan data pasien sudah sesuai dengan masing-masing unit kerja"): a newly
registered visit appears on the destination clinic's list before it has been routed there, so two
units see the same patient. The layanan block is the only place that still runs the old rule.

### F7 — `/pasien/igd/` is not a replacement for the visit list

`igd_dashboard` (`views.py:987-997`) filters `jenis_kunjungan='IGD'` **and**
`status__in=ACTIVE_IGD_STATUSES` (`DAFTAR, TRIAGE, ASESMEN, PENUNJANG, TINDAKAN, DISPOSISI`) —
no `RANAP`, no `PULANG`, no `RUJUK`, no `MENINGGAL`. It is a clinical board, not a history: no
status/jenis filters, no pagination, no RAJAL and no RANAP rows. Removing the only general entry
point would leave RAJAL and RANAP visits reachable only by typing a URL.

### F8 — The sidebar "Riwayat kunjungan" entry is the *only* read surface for the `riwayat` module

`get_allowed_patient_modules` (`accounts/models.py:241-255`) returns `{'master_pasien','riwayat'}`
for every user without a unit and for every non-clinical unit, and always includes `riwayat`.
`kunjungan_daftar` is guarded by `@require_patient_module('riwayat')` (`views.py:299`) — it is the
only view using that key. Deleting the menu therefore removes all read access for Lab, Farmasi,
and unit-less accounts (probe: a `LAB-BDRS` profile's allowed modules are exactly
`['laboratorium','master_pasien','riwayat']`).

The view itself **is already unit-scoped** (`views.py:281`, `scope_kunjungan_qs`), so ask 5 is
already satisfied for that page — the user's complaint is aimed at the kontrol layanan page (F6),
not at this one.

### F9 — Removing the route would break four pages that link to it

`kunjungan_daftar` is reversed in `sidebar.html:324`, `dashboard.html:154` ("Lihat Semua →"),
`kunjungan_detail.html:15` (breadcrumb), `kunjungan_form.html:14` and `kunjungan_form.html:151`
(cancel button). Deleting the URL name turns all five into `NoReverseMatch` → HTTP 500.

### F10 — The `Detail` link is not the only cross-app action on that page

`kontrol/layanan.html:96-101` renders `Detail` (→ `kunjungan_detail`) and, for BPJS rows, a POST
`SEP` button (→ `pasien:bpjs_buat_sep`). Both jump from the kontrol shell into the pasien shell
without any `next` parameter, so the user lands in a different navigation frame.

## 3. Decisions

### Blok D — dari docx

**D1 — Location becomes a model invariant, not a template conditional.**
Add `KunjunganPasien.bed_aktif` (returns the bed only for an inpatient stay) and `Ruangan.label`
(name + class, class not repeated). Four templates currently read `k.bed` directly
(`kunjungan_detail.html:72`, `kunjungan_daftar.html:102`, `pasien_detail.html:112`, `cetak_spri.html:57`);
one property is cheaper to keep correct than four guards.

"Currently occupies a bed" is `bed_id` **and** (`jenis_kunjungan == 'RANAP'` or `status == 'RANAP'`): every
code path that assigns a bed also flips one of those markers (`admit_to_ranap`, `models.py:599-613`;
`BookingKamar.checkin`, `models.py:974-981`), while `kunjungan_baru` never assigns a bed at all
(`views.py:401-425`). `status == 'RANAP'` alone would be fragile if a ward visit is later moved to another
workflow status.
Tradeoff: two small properties on hot models vs. duplicated template logic — properties win because the
invariant ("a bed is a location only after admission") belongs to the visit.

**D2 — The asesmen awal form becomes a dedicated full-width page; the modal is removed.**
New route `pasien:kunjungan_asesmen_awal` → `/pasien/kunjungan/<pk>/asesmen-awal/`. The wizard markup is moved
verbatim into a partial reused by that page; the save endpoint and its `action_mode` contract are unchanged.
Rationale: the clipping is structural (F3); a page gives normal document scroll, a sticky action bar, deep
linking, browser back, and print, without patching the broken modal flex chain.
Rejected alternative: `modal-fullscreen` + CSS flex fix (4 lines). It removes the symptom but keeps a
600-line clinical form inside a dialog with no URL; keep it only as a fallback if the page is rejected.

**D3 — The detail page keeps the four summary cards as a read-only recap.**
Only the entry point changes: the `Edit / Lengkapi Asesmen Awal` button becomes a link to the new page.
This preserves the at-a-glance clinical view (and the accordion's `Asesmen Lengkap` badge) while removing the
duplicate form surface.

**D4 — Out of scope: the IGD dashboard 7-tab modal.**
It is not what the screenshots show, and replacing it now would drop SBAR/triage capture (F4).
Open decision for the user: (a) keep both forms as they are, or (b) later merge the IGD-only fields into a
5th tab of the new page and redirect the IGD dashboard `Asesmen` button to it. Recommend (b) as a separate change
with its own plan, because it touches printed documents and triage capture.

---

The follow-up asks (items 4-6) get their own decision block. The user then resolved the open question in
this block with "pindahkan saja ke sesuai unit kerja untuk pasiennya" — recorded in §8.

### Blok K — dari screenshot kontrol layanan

**K1 — One resolver, one answer. `_layanan_block` calls `visit_unit_code` instead of re-implementing it.**
`layanan_unit.visit_unit_code` is already the documented single owner of "which unit does this visit belong to"
(`layanan_unit.py:1-15`, and `unit_scope.py:6-14` explicitly delegates to it). The layanan block must not carry a
second, weaker copy of that rule (F6). The change is local: the non-IGD branch collapses to
`code = visit_unit_code(k, index)`, and the IGD branch is deleted because `visit_unit_code` returns `'IGD'` first.
Tradeoff: none — this is strictly a deletion of duplicated logic. `resolve_code` stays exported because
`visit_unit_code` and `resolve_visit_ids` still use it.

**K2 — The sidebar entry is kept; the "Kunjungan" menu is renamed and re-scoped, not deleted.**
The user's literal ask is "delete it, IGD already has it". Two facts block a plain deletion: `/pasien/igd/` cannot
serve RAJAL or RANAP (F7), and the entry is the only `riwayat`-module surface for Lab/Farmasi/unit-less accounts
(F8). Instead:

- The entry stays, pointing at `pasien:kunjungan_daftar`, which is **already** unit-scoped
  (`views.py:281`) — so ask 5 holds for it without any code change.
- The label changes from `Riwayat kunjungan` to `Riwayat Kunjungan Unit Saya` so it is no longer read as a
  hospital-wide list.
- The `Dashboard pasien → Lihat Semua →` link (`dashboard.html:154`) is removed: that page is
  `@require_patient_module('pendaftaran')` and its table is explicitly RS-wide
  (`views.py:202`, `kunjungan_terbaru` is unscoped), so its "see all" jumps to a unit-scoped list and
  silently shows *fewer* rows. Deleting that one link removes the misleading entry point without touching the
  route (F9).

If the user still wants the sidebar entry gone after seeing this, that is a one-line follow-up — but it needs
Lab/Farmasi/unit-less read access to be re-homed first (they would otherwise lose all patient visibility).

**K3 — `Detail` becomes contextual: IGD rows go to `/pasien/igd/`, others to `kunjungan_detail`.**
Ask 6, implemented in `kontrol/layanan.html:96`:

```django
{% if i.jenis == 'IGD' %}
<a class="kontrol-ghost" href="{% url 'pasien:igd_dashboard' %}">Detail</a>
{% else %}
<a class="kontrol-ghost" href="{% url 'pasien:kunjungan_detail' i.pk %}">Detail</a>
{% endif %}
```

`_layanan_block` already provides `i.jenis` (the mapped label `'IGD'`, `'Rawat Jalan'`, `'Rawat Inap'`) and
`i.pk`; no new context key is needed. Tradeoff: an IGD row loses the direct deep link into the ERM. That is
acceptable because the IGD dashboard is the user's stated destination for those rows, and the ERM stays
reachable from there (`igd_dashboard.html:419`, `:428`).
The other three pages that link IGD visits to `kunjungan_detail` (`igd_dashboard.html:419/428/934/2493`,
`rajal_dashboard.html:222`, `pendaftaran_dashboard.html:1100`) are **not** changed — those are already the
right destination for their context, and only the kontrol page was named.

**K4 — The `SEP` action moves next to `Detail` with an explicit `next`, so it does not dump the user into the
pasien shell** (F10). `bpjs_buat_sep_view` (`views.py:2552-2563`) already supports
`request.GET.get('format') == 'json'`, so the kontrol shell keeps its frame:

```django
<button type="button" class="kontrol-ghost" data-sep-url="{% url 'pasien:bpjs_buat_sep' i.pk %}?format=json">SEP</button>
```

driven by ~15 lines of JS in `{% block extra_js %}` that POSTs, then shows the returned message as a toast.
Rejected alternative: keep the plain POST form. It works, but it navigates away from a control dashboard to a
clinical one for a single status message — the exact confusion ask 6 is about.


## 4. Implementation

### Step 1 — Model (`pasien/models.py`)

```python
# class Ruangan
@property
def label(self):
    """Nama ruangan + kelas, tanpa mengulang kelas yang sudah tertulis di nama."""
    nama = self.nama.strip()
    kelas = self.get_kelas_display()
    if kelas and kelas.lower() not in nama.lower():
        return f'{nama} ({kelas})'
    return nama

# class KunjunganPasien
@property
def bed_aktif(self):
    """Bed hanya menjadi lokasi pasien untuk kunjungan rawat inap (atau IGD yang sudah diadmisikan)."""
    if self.bed_id and (self.jenis_kunjungan == 'RANAP' or self.status == 'RANAP'):
        return self.bed
    return None
```

No migration (properties only).

### Step 2 — Templates reading the location

| File:line | Change |
|---|---|
| `kunjungan_detail.html:72-78` | `{% if k.bed_aktif %}` … `{{ k.bed_aktif.ruangan.label }}` … `{{ k.bed_aktif.kode_bed }}` |
| `kunjungan_daftar.html:102` | `{% if k.bed_aktif %}{{ k.bed_aktif.ruangan.label }} / {{ k.bed_aktif.kode_bed }}` |
| `pasien_detail.html:112-113` | same, using `bed_aktif` |
| `cetak_spri.html:57` | keep `k.bed` (the SPRI document legitimately states the admission destination) but render `ruangan.label` to fix the doubled class |

### Step 3 — Route + view

`pasien/urls.py`:

```python
path('kunjungan/<int:pk>/asesmen-awal/', views.kunjungan_asesmen_awal, name='kunjungan_asesmen_awal'),
```

`pasien/views.py`:

```python
@login_required
@require_patient_module('riwayat')
def kunjungan_asesmen_awal(request, pk):
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien', 'bed__ruangan'), pk=pk)
    if not can_read_kunjungan(k, getattr(request.user, 'profile', None)):
        raise PermissionDenied('Anda tidak memiliki akses ke kunjungan unit lain.')
    return render(request, 'pasien/asesmen_awal_form.html', {
        'k': k,
        'icd10_codes': ICD10_CODES,
        'sdki_codes': SDKI_CODES,
        'next_url': reverse('pasien:kunjungan_asesmen_awal', args=[k.pk]),
    })
```

Hardening (same step): add the identical `can_read_kunjungan` guard to `igd_asesmen_awal_save` and
`igd_asesmen_copy_prev`, which today accept any authenticated `pk` (F5).

### Step 4 — Template extraction

New `templates/pasien/_asesmen_awal_wizard.html`:
verbatim move of `kunjungan_detail.html:1146-1772` (allergy banner + `pillsAsesmenDetailTab` nav + four tab panes
+ per-tab navigation buttons). Replaced `{% url %}` targets that pointed to the detail page with `next_url`.

New `templates/pasien/asesmen_awal_form.html` (extends `base.html`, `container-fluid p-0`, **no max-width**):

1. Breadcrumb: Dashboard / Daftar Kunjungan / Detail Kunjungan / Asesmen Awal.
2. Identity banner: name, RM, no. kunjungan, jenis kunjungan, triage badge, DPJP, masuk, `bed_aktif` if any.
3. `<form method="post" id="asesmenAwalForm" action="{% url 'pasien:igd_asesmen_awal_save' k.pk %}">`
   with hidden `next_url`.
4. `{% include 'pasien/_asesmen_awal_wizard.html' %}`.
5. Sticky action bar (`position:sticky; bottom:0; background:#fff; border-top`) with
   `Kembali`, `Simpan Draft` (`action_mode=draft`), `Simpan & Selesaikan Asesmen` (`action_mode=selesai`).
   Add `padding-bottom` to the form so the sticky bar never covers the last fields.
6. `{% block extra_js %}`: move `goToAsesmenTab`, `updateSkorNyeriDetail`, the MST live calculator and
   `setNormalDetail` from `kunjungan_detail.html:1945-2052`. Change the scroll target from
   `#modalEditAsesmenAwal .modal-body` to `window` + focus the tab button for accessibility.

### Step 5 — Detail page cleanup (`kunjungan_detail.html`)

1. `:164` button → `<a href="{% url 'pasien:kunjungan_asesmen_awal' k.pk %}" class="btn btn-sm btn-primary fw-semibold">`
   (label unchanged: `Edit / Lengkapi Asesmen Awal`).
2. Delete the modal block `:1132-1788`.
3. Delete the wizard-only JS `:1945-2052` (functions are not referenced anywhere else on the page).
4. Keep the four summary cards and both badges untouched.

### Step 6 — Seed data (`pasien/management/commands/seed_pasien_data.py:134-154`)

Drop `'bed': b3` from the IGD/TRIAGE visit and stop marking `b3` `TERISI`. The visit must be created without a
bed so the seed matches the invariant. Existing databases need no migration: `bed_aktif` hides the stale row, and
the leftover bed status only affects the demo bed board (optional cleanup command below).

### Step 8 — `_layanan_block` uses the shared resolver (`akreditasi/kontrol_data.py`)

Replace the per-row branch (`:354-366`) with the single owner of the rule:

```python
    items, by_status = [], {}
    for k in rows:
        if hospital_wide:
            pass  # loket pendaftaran: seluruh kunjungan RS pada tanggal itu
        elif visit_unit_code(k, index) not in codes:
            continue
```

and update the imports at `:323-326` (`resolve_code` is no longer needed here; `visit_unit_code` is).
`select_related('bed__ruangan')` must gain `'unit_kerja'` so the resolver's `unit_kerja` branch does not fire
one query per row.

**Snapshot cache:** `build_unit_snapshot` caches for 60 s under
`kontrol:{SNAPSHOT_CACHE_VERSION}:{unit.id}:{scope}:{year}`. Because the item list for existing units can change
(the front-desk leak disappears), bump `SNAPSHOT_CACHE_VERSION` from `'v3'` to `'v4'` (`kontrol_data.py:39`) so
stale v3 snapshots cannot serve the old list. This is a version string, not a migration.

### Step 9 — Contextual `Detail` and a non-navigating `SEP` (`templates/akreditasi/kontrol/layanan.html`)

1. `:96` → the `{% if i.jenis == 'IGD' %}` branch from K3.
2. `:97-102` → the `data-sep-url` button from K4.
3. `{% block extra_js %}`: a small handler that reads the clicked button's `data-sep-url`, POSTs with the CSRF
   token from the `{{ csrf_token }}` rendered in the template, and replaces the row's status cell text with
   `res.message` on success. No page navigation.

### Step 10 — Sidebar label and dashboard link (`templates/includes/sidebar.html`, `templates/pasien/dashboard.html`)

1. `sidebar.html:326` — `Riwayat kunjungan` → `Riwayat Kunjungan Unit Saya`.
2. `dashboard.html:153-154` — delete the `Lihat Semua →` link (F9/K2 rationale).

No route, view, or permission change in this step.

### Step 11 — Tests

`pasien/tests_asesmen_awal_ux.py` + new `pasien/tests_lokasi_kunjungan.py`:

Update:

- `test_modal_renders_4_step_tabs_and_ttv_fields` → GET the new page URL, keep the same assertions.
- `test_modal_placement_and_wizard_navigation` → assert the opposite contract: `modalEditAsesmenAwal` is absent
  from the detail page, the detail page links to `kunjungan_asesmen_awal`, and the page contains
  `id="asesmenAwalForm"`, `id="pillsAsesmenDetailTab"`, `goToAsesmenTab`.

Add:

- `test_igd_triage_visit_hides_room_badge` — IGD visit with a bed and `status='TRIAGE'` → no `Bangsal Mawar` on the
  detail page.
- `test_ranap_visit_shows_room_badge` — `status='RANAP'` + bed → badge present.
- `test_ruangan_label_does_not_repeat_kelas` — `Ruangan(nama='Bangsal Mawar (Kelas I)', kelas='1').label ==
  'Bangsal Mawar (Kelas I)'`.
- `test_asesmen_page_denies_other_unit` — user scoped to another unit gets 403.
- `test_save_redirects_back_to_asesmen_page` — POST with `next_url` returns to the page, values persisted.
- `test_copy_prev_returns_to_asesmen_page`.

New `akreditasi/tests_layanan_block.py` (or extend `tests_layanan_unit.py`):

- `test_layanan_uses_the_shared_resolver` — RAJAL visit, `poliklinik='Poli Jantung & Pembuluh Darah'`,
  `unit_kerja=ADMISI`: it appears in `_layanan_block(admisi)` and **not** in `_layanan_block(poli_jantung)`.
  This is the F6 regression guard; it fails against today's code.
- `test_layanan_igd_row_links_to_igd_dashboard` — the IGD unit page renders
  `href="{% url 'pasien:igd_dashboard' %}"` for its IGD row and no `kunjungan_detail` link for that row.
- `test_layanan_rajal_row_links_to_detail` — a RAJAL row still links to `kunjungan_detail`.
- `test_snapshot_version_is_bumped` — asserts `SNAPSHOT_CACHE_VERSION == 'v4'`, so a future silent revert is
  caught.
- Existing `test_stamped_unit_wins_over_poliklinik_map` (`tests_layanan_unit.py:113`) must stay green unchanged —
  it pins `resolve_visit_ids`, which K1 makes the layanan block agree with.


## 5. Proof to run

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py test pasien.tests_asesmen_awal_ux pasien.tests_lokasi_kunjungan \
    pasien.tests_revisi_asesmen_awal --keepdb -v 2
.venv/Scripts/python.exe manage.py test akreditasi.tests_layanan_block akreditasi.tests_layanan_unit --keepdb -v 2
.venv/Scripts/python.exe manage.py test pasien akreditasi --keepdb
```

Manual (dev server, IGD user), at 1366×768 and 1920×1080:

1. `/pasien/kunjungan/184/` (IGD/TRIAGE) — no `Ruangan:` badge; `Edit / Lengkapi Asesmen Awal` navigates to the
   new page.
2. `/pasien/kunjungan/184/asesmen-awal/` — form occupies the full content width; `Simpan Draft`,
   `Simpan & Selesaikan Asesmen` and the per-tab `Lanjut` buttons are reachable without hunting; no horizontal
   scrollbar; saving returns to the page with the values loaded.
3. `/pasien/kunjungan/183/` (RANAP) — badge shows `Bangsal Mawar (Kelas I) · Bed: <kode>` exactly once.
4. Keyboard: Tab reaches every tab button and the footer actions; tab buttons expose `aria-selected`.
5. `/control/layanan/?unit=54&tanggal=<hari ini>` — the IGD unit page still lists the 9 patients; every IGD row's
   `Detail` goes to `/pasien/igd/`; the sidebar entry is now `Riwayat Kunjungan Unit Saya` and still lists only
   that unit's visits.
6. `/control/layanan/?unit=<poli jantung>` — a visit still sitting at the admission desk no longer appears.

## 6. Risks and rollback

| Risk | Mitigation |
|---|---|
| 600-line template move breaks markup | Move verbatim; tests assert tab ids, field names, and both submit buttons on the new page |
| Authorization added to save endpoints rejects legitimate users | Mirrors `kunjungan_detail`, same `can_read_kunjungan` rule already used to reach the page |
| Sticky footer covers inputs on short viewports | `padding-bottom` on the form + manual check at 1366×768 |
| K1 shrinks the layanan block, so a unit "loses" a patient it used to see | That patient was never routed there (F6). The same rule already governs the front office, pasien detail, and the ERM, so the behavior becomes consistent rather than narrower |
| `SNAPSHOT_CACHE_VERSION` bump invalidates nothing persistent | The snapshot is a 60 s cache; worst case is one cold rebuild |
| K2 keeps the menu the user asked to remove | Explicitly re-confirmed with the user before execution (see §7); deletion is a one-line revert if insisted on |
| No DB migration | Rollback = revert commit; no schema or data state to undo |

## 7. Deliberately not done

- Consolidating the IGD dashboard 7-tab form (D4) — needs a field-parity decision and touches printed documents.
- A `bed_occupancy_reconcile` command for beds marked `TERISI` without a `RANAP` occupant — real but separate from
  this request; the display guard already prevents the wrong UI.
- Reworking the summary cards into the form — the recap is useful and the user asked to change the *form*.
- Deleting the `/pasien/kunjungan/` route or sidebar entry (K2) — `/pasien/igd/` cannot serve RAJAL/RANAP (F7) and
  the entry is the only `riwayat`-module read surface for Lab/Farmasi/unit-less accounts (F8). Flagged for the user;
  do it as a follow-up only if they accept losing those.
- Re-pointing `igd_dashboard.html` / `rajal_dashboard.html` / `pendaftaran_dashboard.html` detail links (K3) — only
  the kontrol page was named, and those links already point at the right destination for their context.

## 8. Resolution of the open question — "pindahkan saja ke sesuai unit kerja untuk pasiennya"

The user answered the K2 fork. Their instruction is the ownership rule, not a menu edit: **each patient's
data must be attributed to the unit that actually serves them**. Implemented as K1 (the layanan block now
delegates to the same `visit_unit_code` resolver the front office, unit dashboards, and EMR already use), so
"which unit owns this visit" has exactly one answer in the system.

What that means concretely, per the resolver (`layanan_unit.py:166-178`):

| Visit state | Owner | Why |
|---|---|---|
| IGD (any status) | `IGD` | the IGD unit is the clinical owner, stamped by `KunjunganPasien.save` |
| RAJAL, fresh from the registration desk | the stamping desk (`ADMISI`) | the patient is still at the desk; the clinic only becomes the owner once routed |
| RAJAL, routed / served | the poliklinik mapped from `poliklinik` | the clinic's worklist is the destination |
| RANAP | the ward from `bed.ruangan.unit_kerja` | the bed is where the patient physically is |
| no stamp, no map hit | nobody | unmapped poliklinik → no unit dashboard shows it |

Two consequences the user should know:

- **A patient can appear to move between units** — from the registration desk to the clinic to the ward.
  That is the intended behavior: it mirrors the physical handover, and it is what the front office,
  `rajal_dashboard`, and the EMR already showed before this change.
- **No patient data is moved or rewritten.** No migration, no backfill, no `unit_kerja` reassignment. The
  change is read-side only: the layanan block stops disagreeing with every other consumer. Existing rows
  keep whatever stamp they have, and `visit_unit_code` falls back to the poliklinik/ruangan map for visits
  registered before stamping existed (`tests_layanan_unit.py:113`).

The sidebar entry stays as `Kunjungan unit saya` (K2): it is already unit-scoped, and it is the only
`riwayat`-module surface for Lab/Farmasi/unit-less accounts (F8). The `Detail` link on the kontrol page
now sends IGD rows to `/pasien/igd/` (K3), which is where IGD patients are actually managed.
