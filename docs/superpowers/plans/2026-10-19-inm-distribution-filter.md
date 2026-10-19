# INM Distribution Filter — Unit-Scoped Visibility, Auto-Hide, Per-Unit Realisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Each work unit sees only the national quality indicators (INM) it is actually responsible for, as defined by the 13-row distribution matrix in the source docx. Irrelevant INMs disappear, the unit's own realisation and target status are charted, and below-target units get a route into PDCA.

**Architecture:** One mapping table `InmUnitMapping` (through-model) is the single source of truth for *which unit may see which INM*. One self-FK `IndikatorMutu.inm_induk` links the existing per-bangsal indicator rows (`BAB-*-INM-*`) to their canonical INM, so per-unit realisation already works without touching `CatatanIndikator`'s unique key. One helper `inm_qs_for_user()` decides visibility once and is used by every INM read path. Two new canonical indicators (`INM-15`, `INM-16`) close the two gaps the docx exposes.

**Status:** Analysis done (`docs/plans/2026-10-19-inm-distribusi-analisis.md`). No code written.

**Why this differs from `2026-10-18-inm-unit-access-matrix.md`:** that plan proposed adding `unit` to `CatatanIndikator` and relaxing `unique_together`. Verified data shows the per-unit entry mechanism **already exists** as `BAB-*-INM-*` indicator rows with their own `unit_id` and their own `CatatanIndikator`. This plan uses that instead of migrating 588 production note rows. The 2026-10-18 plan's Task 2 (nullable-column unique key, SQLite/Postgres divergence) is dropped.

**Tech Stack:** Django 6.1.2, Bootstrap 5.3, vanilla JS + Chart.js. Two migrations, one management command, one admin page.

---

## Global Constraints

- **Empty mapping must mean "unrestricted", not "nothing visible".** Production has zero mapping rows today. An unmapped unit must keep seeing today's full list, otherwise every INM disappears on deploy. Auto-hide engages only once a mapping row exists for that unit.
- **The mapping filters visibility; it must never widen authorization.** `profile.is_unit_scoped` keeps its meaning. A mapped unit gaining an edit right it did not have is a bug.
- **Never render a float into JS or CSS without `|unlocalize`.** Locale `id` emits `1,5`; one comma inside `<script>` kills the block (bugs `84c20ce`, `c4c2a3c`). Every touched template must `{% load l10n %}` first.
- **Do not change `CatatanIndikator.Meta.unique_together`.** It stays `[('indikator','bulan','tahun')]`. Per-unit data comes from distinct indicator rows, not from multiple notes on one indicator.
- **Reuse the polarity resolver. No second status formula.** `CatatanIndikator.tercapai` (`akreditasi/risiko_models.py:636-641`) already owns `(target, arah) → bool`. Never write `nilai >= target` anywhere in this work.
- **Seeding never invents.** Any docx row that cannot be matched to an existing `IndikatorMutu` / `UnitKerja` is printed as a warning and skipped.
- **UI copy in Bahasa Indonesia; code, comments, and this plan in English.**
- Work on branch `faishaltsq/medaka`. Commit after the last task.

## Test command (worktree has no `.venv`)

The `.venv` lives in the primary tree only. From the worktree root:

```bash
PY="C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/.venv/Scripts/python.exe"
"$PY" manage.py test akreditasi -v1
```

Run this **once before Task 1** and save the failure list to `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/inm-baseline.txt`. Compare the failure *list* after each task, not just the count. Known pre-existing failures from the last plan: `tests_ai.EndpointAIIntegrationTest.test_anon_user_redirected` (expects 302, gets 401) and `tests_manajemen_risiko_515...test_api_ai_analisis_masalah_risiko_validation` (expects 400, gets 429). Do not fix those here; do not let them mask a new one.

## Verified code facts (read 2026-10-19)

| Fact | Where |
|---|---|
| `IndikatorMutu.unit` is a single nullable FK to `UnitKerja` | `akreditasi/risiko_models.py:562` |
| `IndikatorMutu.jenis` includes `INM`, `IMRS`, `IMU` + legacy `IMP_RS`, `IMP_UNIT`, `NASIONAL` | `akreditasi/risiko_models.py:534-543` |
| `IndikatorMutu.arah_target` = `MIN` (higher better) / `MAX` (lower better) | `akreditasi/risiko_models.py:545-548` |
| `CatatanIndikator` has no `unit` column; `unique_together ('indikator','bulan','tahun')` | `akreditasi/risiko_models.py:606-624` |
| `CatatanIndikator.save()` auto-creates one `RisikoUnit` draft when below target | `akreditasi/risiko_models.py:652+` |
| Unit-scope filter is copy-pasted 3×, max depth 2: `Q(pk=u)\|Q(parent=u)\|Q(parent__parent=u)` | `indikator_views.py:167`, `views.py:147`, `views.py:376` |
| Every unit already sees every `jenis='NASIONAL'` row: `... \| Q(jenis='NASIONAL')` | `indikator_views.py:169`, `views.py:378` |
| Five INM read paths | `indikator_views.indikator_dashboard`, `api_indikator_tren`, `api_indikator_komparasi_unit`, `views.api_mutu_indikator`, `views.dashboard` |
| `_is_manager` = SUPER_ADMIN / ADMIN_RS / KOORDINATOR / KEPALA_UNIT | `indikator_views.py:122-127` |
| `profile.is_unit_scoped` = not superuser/SUPER_ADMIN/ADMIN_RS/DIREKTUR and has `unit_kerja` | `accounts/models.py:177-181` |
| `UnitKerja` is a self-referencing tree (`parent`, `level`), 219 active rows, depth 1–5 | `akreditasi/models.py:33-60` |
| Latest migration | `0040_risikounit_arah_capaian` |

### Data shape that drives the design (local DB, same structure as production)

```
jenis        count
IMP_RS        98
IMP_UNIT      76
NASIONAL      36   = 14 canonical INM-01..INM-14 + 22 per-bangsal BAB-*-INM-* rows
```

`Kepatuhan Kebersihan Tangan` alone exists as 8 separate rows (`INM-01`, `BAB-HD-INM-01`, `BAB-INTERNA-INM-01`, `BAB-KARDIOLOGI-INM-02`, `BAB-MATA-INM-02`, `BAB-NEUROLOGI-INM-02`, `BAB-NIFAS-INM-02`, `BAB-ORTHOPEDI-INM-02`, `BAB-RANAP-BEDAH-INM-01`). Each already carries its own `unit_id` and its own notes — **this is the existing per-unit entry mechanism.**

`UnitKerja` tree is not uniform:

```
PELAKSANA-TEKNIS
├── IRIN (lvl 2)  → children: BANGSAL-ANAK, BANGSAL-DEWASA, ... (12)
└── IRJ  (lvl 2)  → children: POLI-PD, POLI-BEDAH, ... (7)

BID-YAN
├── RANAP (lvl 3)   ← second "Instalasi Rawat Inap", NOT under IRIN
├── RAJAL (lvl 3)   ← second "Instalasi Rawat Jalan", NOT under IRJ
├── IGD   (lvl 3)
└── VK    (lvl 3)
```

Truncating: `IRIN`+`RANAP` together mean "rawat inap"; `IRJ`+`RAJAL` together mean "rawat jalan". `HUMAS-CS` sits at level 1 with no parent. Units at level 4–5 are unreachable by the current depth-2 query.

### Docx numbering does not match DB numbering

| docx # | docx indicator | DB row |
|---|---|---|
| 1 | KKT | `INM-01` |
| 2 | APD | `INM-02` |
| 3 | Identifikasi Pasien | `INM-03` |
| 4 | SC Emergency ≤ 30 min | **missing** — only `BAB-VK-INM-01` |
| 5 | Waktu Tunggu Rajal ≤ 60 min | `INM-06` |
| 6 | Penundaan Operasi Elektif < 5% | `INM-05` |
| 7 | Waktu Visite Dokter ≥ 80% | **missing** |
| 8 | Hasil Kritis Lab 100% | `INM-12` |
| 9 | Fornas | `INM-07` |
| 10 | Clinical Pathway | `INM-08` |
| 11 | Risiko Jatuh | `INM-09` |
| 12 | Respon Komplain | `INM-10` |
| 13 | Kepuasan Pasien | `INM-11` |
| — | — | `INM-04` (IGD response time), `INM-13` (SBAR), `INM-14` (surgical checklist) — not in docx, keep |

Seeding by position would mis-map 8 of 13. Seed by name match, report the rest.

---

### Task 1: `InmUnitMapping` model + migration `0041`

- [x] **Step 1: Add the model** in `akreditasi/risiko_models.py`, after `CatatanIndikator`:

  ```python
  class InmUnitMapping(models.Model):
      """Pemetaan INM ↔ unit yang berhak melihat/menginput (peta distribusi INM).

      Tabel kosong untuk sebuah unit berarti unit tersebut belum dipetakan →
      perilaku lama dipertahankan (lihat selamanya daftar penuh). Auto-hide
      hanya aktif untuk unit yang sudah punya baris di sini.
      """

      ROLE_KEPALA_UNIT = 'KEPALA_UNIT'
      ROLE_DPJP = 'DPJP'
      ROLE_CHOICES = [
          (ROLE_KEPALA_UNIT, 'Semua Kepala Unit / Ruangan'),
          (ROLE_DPJP, 'Semua Dokter DPJP'),
      ]

      indikator = models.ForeignKey(
          IndikatorMutu, on_delete=models.CASCADE, related_name='pemetaan_unit'
      )
      unit = models.ForeignKey(
          UnitKerja, on_delete=models.CASCADE, related_name='pemetaan_inm',
          null=True, blank=True,
          help_text='Kosong bila cakupan ditentukan oleh role_scope, bukan unit.'
      )
      role_scope = models.CharField(
          'Cakupan Role', max_length=20, choices=ROLE_CHOICES, blank=True, default='',
          help_text='Untuk INM seperti Fornas (semua DPJP) atau Komplain (semua Ka. Instalasi).'
      )
      is_pj = models.BooleanField('Unit PJ (Penanggung Jawab Utama)', default=False)
      boleh_input = models.BooleanField('Boleh Input Capaian', default=True)
      berlaku_mulai = models.DateField('Berlaku Mulai', null=True, blank=True)
      created_at = models.DateTimeField(auto_now_add=True)

      class Meta:
          verbose_name = 'Pemetaan INM — Unit'
          verbose_name_plural = 'Pemetaan INM — Unit'
          constraints = [
              models.UniqueConstraint(
                  fields=['indikator', 'unit', 'role_scope'],
                  name='uniq_inm_unit_role',
              ),
              models.CheckConstraint(
                  check=Q(unit__isnull=False) | ~Q(role_scope=''),
                  name='inm_mapping_butuh_unit_atau_role',
              ),
          ]
          ordering = ['indikator_id', 'unit_id']

      def __str__(self):
          scope = self.unit.code if self.unit_id else f"role:{self.role_scope}"
          return f"{self.indikator.kode_indikator} → {scope}"
  ```

  Import `Q` at the top of `risiko_models.py` if not already imported.

- [x] **Step 2: Migration `0041_inm_unit_mapping`**

  ```bash
  "$PY" manage.py makemigrations akreditasi -n inm_unit_mapping
  ```

  No data seed here. Seeding is Task 5, done by an explicit command so it can be re-run against production without a schema deploy.

- [x] **Step 3: Tests** — new `akreditasi/tests_inm_distribusi.py`:

  ```python
  class InmUnitMappingModelTest(TestCase):
      def test_duplicate_unit_for_same_indicator_rejected(self): ...
      def test_role_scoped_row_without_unit_allowed(self): ...
      def test_row_without_unit_and_without_role_rejected(self): ...
  ```

  Run: `"$PY" manage.py test akreditasi.tests_inm_distribusi -v1`

- [x] **Step 4: Tick the boxes in this file.**

---

### Task 2: One subtree resolver, replacing the three copies

The current helper assumes depth ≤ 2 and silently drops level 4–5 units.

- [x] **Step 1: Add to `akreditasi/indikator_views.py`** (importable by `views.py`):

  ```python
  def unit_subtree_ids(unit):
      """Semua id unit: dirinya sendiri + seluruh turunan (kedalaman berapa pun).

      Ditelusuri lewat UnitKerja.parent. 219 baris — CTE rekursif tidak
      memberi keuntungan dan mengorbankan portabilitas SQLite/Postgres.
      """
      ids = {unit.pk}
      frontier = [unit.pk]
      while frontier:
          children = list(
              UnitKerja.objects.filter(parent_id__in=frontier).values_list('pk', flat=True)
          )
          new = [c for c in children if c not in ids]
          ids.update(new)
          frontier = new
      return ids
  ```

- [x] **Step 2: Replace the three inline queries** with calls to it:
  - `akreditasi/indikator_views.py:166-168`
  - `akreditasi/views.py:146-148`
  - `akreditasi/views.py:375-377`

  Behaviour must be identical for depth ≤ 2 units and strictly better below that.

- [x] **Step 3: Tests**
  - `test_subtree_includes_five_level_descendant` — build `A → B → C → D → E`, assert `E.pk in unit_subtree_ids(A)`.
  - `test_subtree_does_not_leak_sibling_branch` — sibling under a different parent must not appear.
  - `test_subtree_depth_two_unchanged` — regression against the old behaviour.

- [x] **Step 4: Tick boxes.**

---

### Task 3: `inm_qs_for_user()` — the single visibility decision

- [x] **Step 1: Write the resolver** in `akreditasi/indikator_views.py`:

  ```python
  def inm_qs_for_user(profile, qs=None):
      """Indikator yang boleh dilihat user ini.

      Urutan keputusan:
      1. Tidak ada profile / tidak unit-scoped → tidak dibatasi.
      2. User unit-scoped yang unitnya belum punya baris mapping → tidak dibatasi
         (produksi saat ini 0 baris; menutup semua akan mengosongkan seluruh menu).
      3. Selain itu → hanya indikator yang dipetakan ke unit user, subtree-nya,
         atau yang cocok dengan role_scope user.
      """
      qs = qs if qs is not None else IndikatorMutu.objects.all()
      if profile is None or not profile.is_unit_scoped or not profile.unit_kerja:
          return qs

      unit_ids = unit_subtree_ids(profile.unit_kerja)
      role = getattr(profile, 'role', '')
      mapping = InmUnitMapping.objects.filter(
          Q(unit_id__in=unit_ids) | Q(role_scope=role) & ~Q(role_scope='')
      )
      if not InmUnitMapping.objects.filter(unit_id__in=unit_ids).exists() \
         and not InmUnitMapping.objects.filter(role_scope=role).exclude(role_scope='').exists():
          return qs  # belum dipetakan → degradasi anggaran

      return qs.filter(pk__in=mapping.values_list('indikator_id', flat=True))
  ```

  Note the guard: the "unmapped" check is per-unit, not global. A unit that has rows must be filtered even while other units are unmapped.

- [x] **Step 2: Apply it to all five read paths**, removing the `| Q(jenis='NASIONAL')` escape hatch from each:
  - `indikator_views.indikator_dashboard` (line ~144)
  - `indicator_views.api_indikator_tren` (line ~596 — must 404 on a hidden indicator, not leak the name)
  - `indikator_views.api_indikator_komparasi_unit` (line ~636)
  - `views.api_mutu_indikator` (line ~372)
  - `views.dashboard` / `_get_mutu_renstra_charts_context` (line ~147)

- [x] **Step 3: Tests**
  - `test_tier_one_sees_everything` (superadmin / DIREKTUR profile)
  - `test_unit_without_mapping_sees_everything` ← the deploy-safety guarantee
  - `test_unit_with_mapping_sees_only_mapped`
  - `test_child_unit_inherits_parent_mapping`
  - `test_role_scoped_mapping_matches_by_role`
  - `test_api_tren_404_for_hidden_indicator`
  - `test_all_five_read_paths_agree` — call each view/API for the same user, assert the resulting indicator id sets are equal

- [x] **Step 4: Tick boxes.**

---

### Task 4: `IndikatorMutu.inm_induk` + backfill (migration `0042`)

Without this the dropdown lists `INM-01` and its eight `BAB-*` copies as nine unrelated indicators.

- [x] **Step 1: Add the field**

  ```python
  inm_induk = models.ForeignKey(
      'self', on_delete=models.SET_NULL, null=True, blank=True,
      related_name='realisasi_unit', verbose_name='INM Induk',
      help_text='Kosong = indikator ini adalah INM kanonik. Terisi = realisasi INM tersebut di satu unit.'
  )
  ```

- [x] **Step 2: Migration `0042_indikatormutu_inm_induk`** with a name-based backfill.

  ```python
  def link_unit_realisations(apps, schema_editor):
      """Hubungkan baris BAB-*-INM-* ke INM kanonik berdasarkan kemiripan nama.

      Hanya menautkan bila tepat satu kandidat kanonik yang cocok. Ambigu atau
      tidak cocok → dibiarkan NULL dan dilaporkan oleh `seed_inm_matrix`.
      """
      IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')
      canonical = list(
          IndikatorMutu.objects.filter(kode_indikator__startswith='INM-')
      )
      for row in IndikatorMutu.objects.filter(kode_indikator__startswith='BAB-'):
          norm = _normalise(row.nama_indikator)          # lowercase, strip target/satuan
          hits = [c for c in canonical if _normalise(c.nama_indikator) in norm
                  or norm in _normalise(c.nama_indikator)]
          if len(hits) == 1:
              row.inm_induk_id = hits[0].pk
              row.save(update_fields=['inm_induk'])
  ```

  Reverse function: set `inm_induk = None` for rows it could have touched — idempotent and lossless (the column is derived, no user data).

- [x] **Step 3: Migration `0043` — add the two missing canonical INMs**

  ```python
  INDICATORS = [
      dict(kode_indikator='INM-15', nama_indikator='Kepatuhan Waktu Visite Dokter',
           target_nilai=80, arah_target='MIN', satuan='%',
           numerator='Jumlah visite dokter yang dilakukan tepat waktu',
           denominator='Jumlah total visite dokter yang diamati',
           dimensi_mutu='TEPAT_WAKTU', jenis='INM', pj='Bidang Pelayanan Medis'),
      dict(kode_indikator='INM-16', nama_indikator='Waktu Tanggap Operasi Seksio Sesarea Emergency (≤ 30 Menit)',
           target_nilai=30, arah_target='MAX', satuan='menit',
           numerator='Jumlah SC emergency dengan waktu tanggap ≤ 30 menit',
           denominator='Jumlah total SC emergency',
           dimensi_mutu='TEPAT_WAKTU', jenis='INM', pj='IGD / VK'),
  ]
  ```

  Use `get_or_create` on `kode_indikator` so the migration is re-runnable. Then point `BAB-VK-INM-01` at `INM-16` explicitly (its name matches, but the backfill in Step 2 ran before these rows existed).

- [x] **Step 4: Dashboard catalogue = canonical only.**
  In `indikator_dashboard`, `api_mutu_indikator`, and `api_indikator_komparasi_unit`, the INM dropdown lists `inm_induk__isnull=True`. Realisations are reached through the parent, not listed beside it.

- [x] **Step 5: Tests**
  - `test_backfill_links_duplicate_name_to_single_canonical`
  - `test_ambiguous_name_left_null`
  - `test_inm_15_and_16_created_once` (run migration twice on the same schema state)
  - `test_dropdown_excludes_unit_realisations`

- [x] **Step 6: Tick boxes.**

---

### Task 5: `seed_inm_matrix` management command

- [x] **Step 1: Create `akreditasi/management/commands/seed_inm_matrix.py`.**

  Mapping from docx rows to real unit codes. Subtree expansion is done by the resolver at query time, so listing the root is enough.

  | INM | PJ (`is_pj=True`) | Unit terkait (codes) |
  |---|---|---|
  | `INM-01` KKT | `KOM-PPI` | `IRIN`, `RANAP`, `IRJ`, `RAJAL`, `IGD`, `ICU`, `ICCU`, `VK`, `IBS`, `LAB`, `RAD`, `FARM`, `GIZI`, `JENAZAH`, `RM`, `KESLING` |
  | `INM-02` APD | `KOM-PPI` | `IRIN`, `RANAP`, `IRJ`, `RAJAL`, `IGD`, `ICU`, `ICCU`, `VK`, `IBS`, `LAB`, `RAD`, `CSSD`, `LAUNDRY`, `KESLING`, `JENAZAH` |
  | `INM-03` Identifikasi Pasien | `KMKP` | `IRIN`, `RANAP`, `IRJ`, `RAJAL`, `IGD`, `ICU`, `ICCU`, `VK`, `IBS`, `LAB`, `RAD`, `FARM`, `ADMISI`, `PENDAFTARAN-ADMISSION`, `REHAB` |
  | `INM-16` SC Emergency | `IGD` (PJ), `VK` (PJ) | `IGD`, `VK`, `IBS`, `KAMAR-OPERASI`, `ICU`, `KSM-ANESTESI`, `LAB`, `BDRS` |
  | `INM-06` Waktu Tunggu Rajal | `IRJ` | `IRJ`, `RAJAL`, `PENDAFTARAN-ADMISSION`, `ADMISI`, `RM`, `DEPO-RAJAL`, `FARM` |
  | `INM-05` Penundaan Operasi Elektif | `IBS` | `IBS`, `KAMAR-OPERASI`, `IRIN`, `RANAP`, `POLI-BEDAH`, `KSM-ANESTESI`, `CSSD` |
  | `INM-15` Visite Dokter | `BID-YAN` | `IRIN`, `RANAP`, `ICU`, `ICCU`, `HCU` |
  | `INM-12` Hasil Kritis Lab | `LAB` | `LAB`, `IRIN`, `RANAP`, `ICU`, `ICCU`, `IGD`, `VK` |
  | `INM-07` Fornas | `FARM` | `FARM`, `DEPO-RAJAL`, `DEPO-RANAP-IGD`, `DEPO-BEDAH-INTENSIF`, `KOM-MED`, `KOM-FARMASI` **+ `role_scope='DPJP'`** |
  | `INM-08` Clinical Pathway | `KOM-MED` | `IRIN`, `RANAP`, `BANGSAL-ANAK`, `BANGSAL-DEWASA`, `BANGSAL-OBGYN`, `RM`, `KOM-MUTU` |
  | `INM-09` Risiko Jatuh | `KMKP` | `IRIN`, `RANAP`, `ICU`, `ICCU`, `IGD`, `REHAB`, `RAD` |
  | `INM-10` Respon Komplain | `HUMAS-CS` | `HUMAS-CS` **+ `role_scope='KEPALA_UNIT'`** |
  | `INM-11` Kepuasan Pasien | `HUMAS-CS`, `KOM-MUTU` | `IRJ`, `RAJAL`, `IRIN`, `RANAP`, `IGD`, `FARM`, `SUB-KAS`, `LAB`, `RAD` |

  Command behaviour:

  ```python
  class Command(BaseCommand):
      help = 'Seed peta distribusi INM (13 INM dari docx) ke InmUnitMapping.'

      def add_arguments(self, parser):
          parser.add_argument('--dry-run', action='store_true')
          parser.add_argument('--prune', action='store_true',
                              help='Hapus baris mapping INM-* yang tidak ada di matriks.')

      def handle(self, *args, **opts): ...
  ```

  - Resolve `INM-*` by `kode_indikator`; resolve units by `code`.
  - Skip + `self.stderr.write(f'[SKIP] {kode} unit {code} tidak ditemukan')` on any miss.
  - Idempotent: `update_or_create` on `(indikator, unit, role_scope)`.
  - Print a summary: `created / updated / skipped / total`.
  - `--prune` only ever removes rows whose indicator is inside the matrix; never touches manually added INM.

- [x] **Step 2: Run it against the local DB** and paste the real summary:

  ```bash
  "$PY" manage.py seed_inm_matrix --dry-run
  "$PY" manage.py seed_inm_matrix
  ```

  Expect ≥ 13 PJ rows and ~90 coverage rows. Any `[SKIP]` line means the docx label needs a code added to the table above — fix the table, do not invent a unit.

- [x] **Step 3: Test** `tests_inm_distribusi.SeedInmMatrixTest`:
  - `test_seed_is_idempotent` (run twice, row count unchanged)
  - `test_unknown_unit_is_skipped_not_created`
  - `test_role_scoped_rows_have_no_unit`
  - `test_dry_run_writes_nothing`

- [x] **Step 4: Tick boxes.**

---

### Task 6: Dashboard UI — auto-hide, unit realisation, below-target flag

- [x] **Step 1: `indikator_dashboard` context** gains:

  ```python
  'inm_peta': mapping rows for the user's unit(s), grouped by indicator,
  'inm_realisasi': {indikator_id: [child rows of this unit]},
  'is_terpetakan': bool,   # apakah unit user punya mapping
  ```

  Keep the existing `punya_data` annotation — unmeasured indicators stay visible with a marker. Do not regress to hiding them.

- [x] **Step 2: Template changes** in `templates/akreditasi/indikator_dashboard.html`:

  - `{% load l10n %}` at the top if absent.
  - INM card gets a scope line: `Unit PJ: {{ ind.pj }}` and `Unit Anda: {{ realisasi.nilai }}`.
  - When `is_terpetakan` and the indicator is NOT in `inm_peta`, the card is not rendered at all (auto-hide). When `is_terpetakan` is false, everything renders as today.
  - Below target → badge `[!] Belum Memenuhi Standar` + callout linking to the existing risk evaluation route (`akreditasi:risiko_*`); no new route.

- [x] **Step 3: Chart separation.** The trend chart currently averages every filtered indicator. Add a second series for the unit's own realisation when `inm_realisasi` is non-empty, so hospital aggregate and unit value are visually distinct. Label them `Agregat RS` and `Unit {{ profile.unit_kerja.name }}`.

- [x] **Step 4: Verify the inline JS actually parses.** The template contains `{{ }}` inside `<script>`, so checking the file itself cannot pass:

  ```bash
  "$PY" manage.py shell -c "
  from django.test import Client; from django.contrib.auth import get_user_model
  ...  # login as a unit-scoped user, GET /indikator-mutu/, write response to scratch
  "
  node --check <scratch>/rendered_indikator_dashboard.js
  ```

  Extract `<script>` blocks from the **rendered** response, then `node --check`.

- [x] **Step 5: Tick boxes.**

---

### Task 7: Admin matrix page

The docx makes the operator responsible for maintaining the table, so it cannot stay in a fixture.

- [x] **Step 1: Read-only matrix view** `akreditasi:indikator_inm_matrix` at `/indikator-mutu/matriks-inm/`, `_is_manager` gated:
  - rows = INM, columns = units, cell = `PJ` / `Input` / empty.
  - filter by unit and by INM.
  - link back to the indicator detail.
- [x] **Step 2: Edit affordance** — inline toggle of `is_pj` / `boleh_input` via POST, CSRF-protected, `_log()`-audited like every other mutation in `indikator_views`.
- [x] **Step 3: Tests** — `test_matrix_requires_manager`, `test_toggle_is_audited`, `test_unit_scoped_user_cannot_toggle`.
- [x] **Step 4: Tick boxes.**

---

### Task 8: Fix the polarity data the flag depends on

The flag is only as correct as `arah_target`. Two rows are verifiably wrong.

- [x] **Step 1: Audit command** `akreditasi/management/commands/audit_arah_target.py` — list every `jenis IN ('NASIONAL','INM')` row whose `arah_target` contradicts its name (keywords `≤`, `kurang dari`, `waktu`, `penundaan`, `respon`, `tunggu` → `MAX`; `≥`, `kepatuhan`, `kepuasan` → `MIN`). Print, do not auto-fix.
- [x] **Step 2: Fix only the confirmed rows in a data migration** (`0044`): `BAB-INTERNA-INM-02` → `MIN`; `BAB-VK-INM-01` → handled by Task 4 Step 3 (it becomes a child of `INM-16`, which is `MAX`).
- [x] **Step 3: Test** `test_known_bad_polarity_rows_are_corrected`.
- [x] **Step 4: Tick boxes.**

---

### Task 9: Full verification + commit

- [x] **Step 1:** `"$PY" manage.py makemigrations --check --dry-run` → must report no changes.
- [x] **Step 2:** `"$PY" manage.py test akreditasi -v1` → diff the failure list against `inm-baseline.txt`. New failures are blockers; the two known AI failures are not.
- [x] **Step 3:** Manual check on local server, logged in as a unit-scoped user in `BANGSAL-ANAK` (id 130):
  - dropdown contains `INM-01`, `INM-02`, `INM-03`, `INM-15`, `INM-08`, `INM-09`, `INM-10`, `INM-11`;
  - `INM-16` (SC) and `INM-05` (Penundaan Operatif) are absent;
  - no JS console error.
- [x] **Step 4:** Manual check as `SUPER_ADMIN`: everything still visible, matrix page reachable.
- [x] **Step 5:** `git add` only the touched files (`akreditasi/risiko_models.py`, `indikator_views.py`, `views.py`, `templates/akreditasi/indikator_dashboard.html`, the two migrations, three commands, test file, this plan, the analysis doc). Commit message: `feat(inm): unit-scoped INM distribution filter + per-unit realisation`.

---

## Review Focus

- **The unmapped-unit guarantee can empty production on deploy.** It needs an explicit test, not a comment: the natural implementation fails closed.
- **One status formula.** If a task reaches for `nilai >= target`, it is wrong — `CatatanIndikator.tercapai` owns that.
- **`api_indikator_tren` must 404 on a hidden indicator**, not return its name and target. Otherwise the filter is cosmetic.
- **Seeding by name must be loud.** A silent `[SKIP]` is a missing row in production. The command must print and exit non-zero when the skip count is above zero and `--strict` is passed.
- **Two canonical INMs (`INM-15`, `INM-16`) are new codes.** They must not collide with anything already imported; `get_or_create` on `kode_indikator` plus a pre-check in the migration.
- **`|unlocalize` on every float** that reaches `<script>`. Locale `id` breaks the block, not the number.
