# Merge Identity Tabs + KTP OCR on Profile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement "gabungkan antara identitas kepegawaian dan identitas pribadi.docx": (1) Merge the profile page's "Identitas & Kepegawaian" and "Identitas Pribadi" tabs into one "Profil & Kepegawaian" tab (spec section 3.1; the 6→4 tab consolidation's first step) — one two-column scroll instead of tab-hopping. (2) Add an "Unggah KTP (OCR)" card on that merged tab: the manager uploads a KTP scan for an EXISTING employee, AI extracts NIK/nama/TTL/gender/alamat, and empty personal-profile fields auto-fill for review before save (spec sections 1–2), storing the scan as an IDENTITY/KTP document version (spec 2: "Dokumen Repositori").

**Architecture:** Two independent deliverables sharing one page. (A) Tab merge is pure template surgery on `templates/sdm/pegawai/detail.html`: move the `personal-pane` content into `identity-pane` as a second two-column section, delete the separate tab + pane, rename the merged tab. Data/authorization unchanged — `build_staff_profile` already gates personal visibility (`can_view_personal`) and the masking test `test_detail_masks_personal_data_for_a_view_only_grant` pins that the merged layout must keep (assert NOT-contains still holds because the dl block renders only when permitted). (B) KTP-OCR-for-existing-employee reuses Task-1's `extract_ktp_fields` and the canonical document pipeline: a new POST-only route `pegawai/<uuid:employee_id>/ktp-ocr/` bound to `can_manage_hc_employees` + `can_manage_hc_documents` (same predicate pair as `pegawai_edit` + `dokumen_upload`), which calls `store_private_document(..., document_type='IDENTITY', jenis_berkas 'KTP' recorded after, like `dokumen_upload` does), then in a fresh short transaction fills EMPTY `ProfilPribadiPegawai` fields (`nik`, `nama_depan/nama_belakang` when profile nama empty, `tempat_lahir`, `tanggal_lahir`, `gender`, `alamat_ktp` + mirror `alamat_domisili` when `alamat_sama_dengan_ktp`) — fill-empty-only invariant carried over — then redirects back to the profile with a success/warning message. The OCR service call happens AFTER the document store transaction commits (lesson from the intake deviation: never hold rows across a seconds-long network call).

**Tech Stack:** Django 6 (existing pinned), existing `sdm.services.ktp_ocr.extract_ktp_fields` (frozen signature), existing `store_private_document` + `SupabasePrivateStorage`, Bootstrap tabs already in template. No model/migration changes. No new dependencies.

**Spec:** `C:\Users\cubeb\Downloads\gabungkan antara identitas kepegawaian dan identitas pribadi.docx`; related context: `Masalah unggah dokumen ganda.docx` (form layout, already implemented), plan `docs/superpowers/plans/2026-10-27-ktp-upload-ocr-single-column.md` (intake OCR, already implemented — this plan extends OCR to existing-employee profiles).

## Global Constraints

- Reuse `extract_ktp_fields` verbatim; do not fork the OCR prompt/normalizer.
- Authorization: view must hold `can_manage_hc_employees` AND `can_manage_hc_documents` for the employee's visible scope (matches the two writes performed: profile edit + document creation). Health capability NOT required (document_type IDENTITY/sensitivity personnel).
- NIK uniqueness: `ProfilPribadiPegawai` partial-unique `sdm_profil_pribadi_nik_nonblank_uniq` + intake's duplicate-NIK guard pattern. An OCR NIK that collides must NOT save; surface a form-level error, keep the document.
- Fill-empty-only: OCR never overwrites an existing value (same invariant as intake OCR, pinned there).
- OCR runs only when `SystemConfig.ai_enabled` + key; document still stores when OCR is skipped/failed — same degradation contract as intake.
- The scan must remain in `human-capital-private` via `store_private_document` (no new storage path), status PENDING for the normal review flow.
- Bahasa Indonesia copy; no tab renamed except the two specified; other tabs untouched (spec's 4-tab finish merges 4 more pairs — those are separate follow-ups, not this plan).
- Test runner: `.venv/Scripts/python.exe manage.py test sdm.tests.<module>` — run WITHOUT `--parallel` when asserting counts (parallel runner crashed on a copied venv during planning; root venv is fine either way).

## Review Focus

1. **View-only grant must still see masked personal data** — after the merge, the merged pane renders personal fields only under `profile.can_view_personal`; a `can_view_hc`-only reader gets "Tersembunyi". Pinned by existing `test_detail_masks_personal_data_for_a_view_only_grant` (unchanged) + new `test_merged_tab_still_masks_personal_data_for_reader`.
2. **NIK collision from OCR** — two employees, OCR reads an NIK already owned by another profile: no profile write happens; user sees an error message; DOCUMENT still stored (audit trail). Pinned by new `test_ktp_ocr_nik_collision_keeps_document_but_no_profile_write`.
3. **OCR failure stores the document but writes no fields** — fetch/AI exception path. Pinned by `test_ktp_ocr_failure_stores_document_only`.
4. **No double-KTP-document spam** — repeat uploads create successive document VERSIONS (versioning pipeline exists), not new titled documents每一天. Because `store_private_document` always creates a NEW `DokumenPegawai` (noted gap), a second upload creates a second KTP document — acceptable now, pinned in `test_repeat_ktp_upload_creates_new_document_version` documenting current behavior; consolidation is a follow-up (see NOT-in-plan).
5. **Tab merge must not orphan tab JS/anchors** — `#personal-tab`/`#personal-pane` ids disappear; grep templates/tests for references, and the response must still contain `employee-tabs` nav with 6 tabs. Pinned by `test_profile_has_six_tabs_after_merge`.

---

### Task 1: Merge identity tabs in `templates/sdm/pegawai/detail.html`

**Files:**
- Modify: `templates/sdm/pegawai/detail.html:23-31` (tablist) and `:34-82` (identity + personal panes)
- Test: `sdm/tests/test_directory.py` (extend `PegawaiDirectoryViewTests`)

**Interfaces:**
- Consumes: existing context (`profile.can_view_personal`, `profile.personal`, `profile.has_personal_record`, `profile.masked_nik`) — unchanged.
- Produces: merged tab labeled `Profil & Kepegawaian`; `personal-pane` gone. No route/context change.

- [ ] **Step 1: Failing tests** — append to `PegawaiDirectoryViewTests`:

```python
def test_profile_has_six_tabs_after_merge(self):
    self.client.force_login(self.reader)
    response = self.client.get(
        reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
    )
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'Profil &amp; Kepegawaian')
    self.assertNotContains(response, 'id="personal-tab"')
    self.assertNotContains(response, 'Identitas Pribadi</button>')
    # Employment/legal/placement/documents/activity tabs all survive.
    for marker in ('Riwayat Kepegawaian', 'Legalitas', 'Riwayat Penempatan',
                   'Dokumen Kepegawaian', 'Aktivitas'):
        self.assertContains(response, marker)

def test_merged_tab_still_masks_personal_data_for_reader(self):
    from sdm.models import ProfilPribadiPegawai
    ProfilPribadiPegawai.objects.create(
        employee=self.visible, nik='3201010101010002',
        telepon='081200011122', alamat_ktp='Jl. Gabung 4',
    )
    self.client.force_login(self.reader)  # view-only grant
    response = self.client.get(
        reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
    )
    self.assertEqual(response.status_code, 200)
    self.assertNotContains(response, '3201010101010002')
    self.assertNotContains(response, '081200011122')
    self.assertContains(response, 'Tersembunyi')
```

- [ ] **Step 2: Run red**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_directory --keepmail` → actually `manage.py test sdm.tests.test_directory -k test_profile_has_six_tabs_after_merge -k test_merged_tab_still_masks_personal_data_for_reader` (use `-k` filters or run the class). Expected: both FAIL.

- [ ] **Step 3: Merge template** — in `detail.html`:
  - Tablist: replace the two `<li>` rows for `identity-tab` and `personal-tab` with ONE li: id `identity-tab`, label `Profil &amp; Kepegawaian`, target `#identity-pane`.
  - Panes: inside `identity-pane`, after the existing employment `<dl>`, append the entire personal block currently in `personal-pane` (lines 64-81) wrapped as:

```html
<h2 class="h6 mb-2 mt-4">Identitas Pribadi</h2>
{% if profile.can_view_personal and profile.personal %}
<dl class="row mb-0">
    …existing personal dt/dd rows verbatim…
</dl>
{% elif profile.has_personal_record %}
<p class="text-muted mb-0">Tersembunyi — data identitas pribadi hanya dapat dilihat oleh pemilik profil atau pengguna dengan kewenangan pengelolaan.</p>
{% else %}
<p class="text-muted mb-0">Belum ada data identitas pribadi untuk pegawai ini.</p>
{% endif %}
```

  - Delete the whole `personal-pane` section.

- [ ] **Step 4: Green + no dangling refs**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_directory` → PASS.
Also: `grep -rn "personal-tab\|personal-pane" templates/ sdm/` → no hits outside this file's history.

- [ ] **Step 5: Commit**

```bash
git add templates/sdm/pegawai/detail.html sdm/tests/test_directory.py
git commit -m "feat(sdm): merge Identitas Pribadi into Profil & Kepegawaian tab"
```

---

### Task 2: Profile KTP-OCR route, view, and merged-tab upload card

**Files:**
- Modify: `sdm/urls.py` (route after `pegawai_edit`)
- Modify: `sdm/views.py` (new view `pegawai_ktp_ocr`, near `dokumen_upload`)
- Modify: `templates/sdm/pegawai/detail.html` (upload card at top of merged pane, `can_manage_documents`-gated)
- Modify: `sdm/tests/test_directory.py` (new test class at end)

**Interfaces:**
- Consumes: `extract_ktp_fields(image_bytes, *, actor)` (frozen); `store_private_document(file_obj, *, employee, sensitivity, document_type, title, uploaded_by, issued_date=None, valid_until=None)`; `get_private_storage().fetch_object`; `require_hc_capability`.
- Produces: `sdm:pegawai_ktp_ocr` route `pegawai/<uuid:employee_id>/ktp-ocr/`, POST-only, redirects to `sdm:pegawai_detail`. Field-fill helper `_apply_ktp_fields_to_profile(employee, fields)` in `sdm/views.py` (single source; also documents the merge-mirror rule for `alamat_domisili`).

- [ ] **Step 1: Failing tests** — append class to `sdm/tests/test_directory.py` (reuse its `_user`/`_grant`/`_employee` idiom, plus the storage fake pattern from `test_intake_uploads.py`):

```python
class ProfileKtpOcrTests(TestCase):
    """POST /pegawai/<id>/ktp-ocr/ stores the scan and OCR-fills empty fields."""

    def setUp(self):
        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat KTP', code='DIR-KTP')
        self.manager = self._user('ktp-manager')
        self.employee = self._employee('Basirun', 'KTP-001', self.root)
        self.session = FakeSession(FakeResponse(200))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co', api_key='service-key',
            bucket='hc-private', session=self.session,
        )
        self.ktp_jpeg = SimpleUploadedFile(
            'ktp.jpg', JPEG, 'image/jpeg'
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.can_manage_hc_documents = True
        config.save(update_fields=[
            'can_view_hc', 'can_manage_hc_employees',
            'can_manage_hc_documents', 'updated_at',
        ])
        for capability in ('can_view_hc', 'can_manage_hc_employees',
                           'can_manage_hc_documents'):
            HcGrant.objects.create(user=user, capability=capability, unit_kerja=self.root)
        return user

    def _post(self, ocr_fields=None, ocr_raises=False):
        patchers = [
            patch('sdm.views.get_private_storage', return_value=self.storage),
            patch('sdm.views.extract_ktp_fields',
                  side_effect=ValueError('boom') if ocr_raises
                  else lambda data, actor=None: ocr_fields or {}),
        ]
        self.client.force_login(self.manager)
        with patchers[0], patchers[1]:
            return self.client.post(
                reverse('sdm:pegawai_ktp_ocr',
                        kwargs={'employee_id': self.employee.pk}),
                {'berkas': self.ktp_jpeg},
            )

    def test_upload_stores_identity_document_and_fills_empty_fields(self):
        ocr = {'nik': '3305112209880007', 'nama_lengkap': 'Basirun',
               'tempat_lahir': 'Kebumen', 'tanggal_lahir': '1988-09-22',
               'gender': 'LAKI_LAKI', 'alamat': 'Desa Mangli, Kebumen, Jawa Tengah'}
        response = self._post(ocr_fields=ocr)
        self.assertEqual(response.status_code, 302)
        document = DokumenPegawai.objects.get(
            employee=self.employee, jenis_berkas='KTP'
        )
        self.assertEqual(document.document_type, 'IDENTITY')
        version = document.versions.get()
        profile = self.employee.profil_pribadi
        self.assertEqual(profile.nik, '3305112209880007')
        self.assertEqual(profile.nama_depan, 'Basirun')
        self.assertEqual(profile.tempat_lahir, 'Kebumen')
        self.assertEqual(str(profile.tanggal_lahir), '1988-09-22')
        self.assertEqual(profile.gender, 'LAKI_LAKI')
        self.assertIn('Mangli', profile.alamat_ktp)
        # Domisili mirrors KTP address when the mirror flag is set.
        self.assertIn('Mangli', profile.alamat_domisili)
        # Scan went through the private bucket.
        self.assertTrue(version.storage_key.startswith('personnel/'))

    def test_ocr_never_overwrites_existing_values(self):
        from sdm.models import ProfilPribadiPegawai
        ProfilPribadiPegawai.objects.create(
            employee=self.employee, nik='3201010101010003',
            nama_depan='Sudah', alamat_ktp='Alamat lama',
            alamat_domisili='Alamat lama',
        )
        ocr = {'nik': '3305112209880007', 'nama_lengkap': 'Basirun',
               'alamat': 'Desa Mangli baru'}
        self._post(ocr_fields=ocr)
        profile = self.employee.profil_pribadi
        profile.refresh_from_db()
        self.assertEqual(profile.nik, '3201010101010003')
        self.assertEqual(profile.nama_depan, 'Sudah')
        self.assertEqual(profile.alamat_ktp, 'Alamat lama')

    def test_ktp_ocr_nik_collision_keeps_document_but_no_profile_write(self):
        from sdm.models import ProfilPribadiPegawai
        other = Pegawai.objects.create(
            nama_lengkap='Pegawai Lain', kategori='NON_PPA')
        ProfilPribadiPegawai.objects.create(
            employee=other, nik='3305112209880007')
        ocr = {'nik': '3305112209880007', 'nama_lengkap': 'Basirun'}
        response = self._post(ocr_fields=ocr)
        self.assertEqual(response.status_code, 302)  # back to profile, error msg
        # Document still stored (audit trail), profile untouched.
        self.assertTrue(DokumenPegawai.objects.filter(
            employee=self.employee, jenis_berkas='KTP').exists())
        self.assertFalse(ProfilPribadiPegawai.objects.filter(
            employee=self.employee).exists())

    def test_ktp_ocr_failure_stores_document_only(self):
        self._post(ocr_raises=True)
        self.assertTrue(DokumenPegawai.objects.filter(
            employee=self.employee, jenis_berkas='KTP').exists())
        self.assertFalse(
            hasattr(self.employee, 'profil_pribadi')
            and self.employee.profil_pribadi.nik
        )

    def test_repeat_ktp_upload_creates_new_document(self):
        """Current store_private_document creates a new document per upload;
        consolidation into versions is follow-up work (NOT in this plan)."""
        self._post(ocr_fields={'nik': '3305112209880007'})
        self._post(ocr_fields={'nik': '3305112209880007'})
        self.assertEqual(DokumenPegawai.objects.filter(
            employee=self.employee, jenis_berkas='KTP').count(), 2)

    def test_reader_without_manage_capability_gets_403_or_404(self):
        reader = get_user_model().objects.create_user('ktp-reader')
        UserProfile.objects.create(user=reader, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(user=reader, capability='can_view_hc', unit_kerja=self.root)
        self.client.force_login(reader)
        response = self.client.post(
            reverse('sdm:pegawai_ktp_ocr',
                    kwargs={'employee_id': self.employee.pk}),
            {'berkas': self.ktp_jpeg},
        )
        self.assertIn(response.status_code, (403, 404))
```

Wire imports at file top: `SimpleUploadedFile`, `patch`, plus `from sdm.tests.test_storage_backend import FakeResponse, FakeSession, JPEG` and `from sdm.storage_backend import SupabasePrivateStorage` (copy from `test_intake_uploads.py:1-25` idiom).

- [ ] **Step 2: Run red**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_directory.ProfileKtpOcrTests`
Expected: FAIL — `reverse` NoReverseMatch (`pegawai_ktp_ocr` not registered).

- [ ] **Step 3: Implement**

`sdm/urls.py` — after the `pegawai_edit` path:

```python
path(
    'pegawai/<uuid:employee_id>/ktp-ocr/',
    views.pegawai_ktp_ocr,
    name='pegawai_ktp_ocr',
),
```

`sdm/views.py` — imports: `from sdm.services.ktp_ocr import extract_ktp_fields` (top) and make sure `ProfilPribadiPegawai` is in the model import block. New code after `pegawai_edit`:

```python
KTP_PROFILE_FILL_KEYS = (
    'nik', 'nama_lengkap', 'tempat_lahir', 'tanggal_lahir', 'gender', 'alamat',
)


def _apply_ktp_fields_to_profile(employee, fields):
    """Fill EMPTY ProfillPribadiPegawai fields from OCR; return count filled.

    Fill-empty-only matches the intake OCR invariant. Saves inside the caller's
    transaction. Raises ValidationError on NIK collision (partial-unique) so
    the caller can message without losing the stored document.
    """
    from django.db import IntegrityError
    from sdm.models import ProfilPribadiPegawai

    profile = ProfilPribadiPegawai.objects.filter(employee=employee).first()
    if profile is None:
        profile = ProfilPribadiPegawai(employee=employee,
                                       alamat_sama_dengan_ktp=True)
    updates = []
    def _set(attr, value):
        if value and not (getattr(profile, attr) or '').strip():
            setattr(profile, attr, value)
            updates.append(attr)

    _set('nik', (fields.get('nik') or '').strip())
    nama = (fields.get('nama_lengkap') or '').strip()
    if nama and not ((profile.nama_depan or '').strip()
                     or (profile.nama_belakang or '').strip()):
        parts = nama.split(' ', 1)
        profile.nama_depan = parts[0]
        profile.nama_belakang = parts[1] if len(parts) > 1 else ''
        updates.append('nama_depan')
    _set('tempat_lahir', (fields.get('tempat_lahir') or '').strip())
    raw_date = (fields.get('tanggal_lahir') or '').strip()
    if raw_date and profile.tanggal_lahir is None:
        try:
            from django.utils.dateparse import parse_date
            parsed = parse_date(raw_date)
        except (TypeError, ValueError):
            parsed = None
        if parsed:
            profile.tanggal_lahir = parsed
            updates.append('tanggal_lahir')
    gender = (fields.get('gender') or '').strip()
    if gender in ('LAKI_LAKI', 'PEREMPUAN') and not profile.gender:
        profile.gender = gender
        updates.append('gender')
    alamat = (fields.get('alamat') or '').strip()
    if alamat and not (profile.alamat_ktp or '').strip():
        profile.alamat_ktp = alamat
        updates.append('alamat_ktp')
        if profile.alamat_sama_dengan_ktp and not (
            profile.alamat_domisili or ''
        ).strip():
            profile.alamat_domisili = alamat
            updates.append('alamat_domisili')
    if not updates:
        return 0, profile
    try:
        with transaction.atomic():
            profile.full_clean()
            profile.save()
    except IntegrityError:
        raise ValidationError({
            'nik': 'NIK hasil OCR sudah terdaftar pada pegawai lain; '
                   'periksa manual. Berkas KTP tetap tersimpan sebagai dokumen.'
        }) from None
    return len(updates), profile


@login_required
@require_POST
def pegawai_ktp_ocr(request, employee_id):
    employee = get_object_or_404(visible_employees(request.user), pk=employee_id)
    require_hc_capability(
        request.user, 'can_manage_hc_employees', employee=employee
    )
    require_hc_capability(
        request.user, 'can_manage_hc_documents', employee=employee
    )
    berkas = request.FILES.get('berkas')
    if berkas is None:
        messages.error(request, 'Pilih berkas KTP terlebih dahulu.')
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    # 1) Canonical document first (its own transaction inside the service).
    try:
        document, version = store_private_document(
            berkas,
            employee=employee,
            sensitivity='personnel',
            document_type='IDENTITY',
            title='KTP',
            uploaded_by=request.user,
        )
    except (PermissionDenied, ValidationError) as exc:
        messages.error(request, '; '.join(
            getattr(exc, 'messages', None) or [str(exc)]))
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    document.jenis_berkas = 'KTP'
    document.save(update_fields=['jenis_berkas'])
    PeristiwaSDM.objects.create(
        actor=request.user,
        jenis_peristiwa='private_document_uploaded',
        target_tipe='document_version',
        target_id=str(version.pk),
        status_sesudah='PENDING',
        alasan='sensitivity=personnel; source=profile_ktp_ocr',
    )
    # 2) OCR + profile fill AFTER the document transaction committed;
    #    network latency must never run while holding rows.
    from sdm.storage import get_private_storage as _gps
    from sdm.storage_backend import PrivateStorageError
    try:
        data = get_private_storage().fetch_object(
            version.storage_key, max_bytes=version.size_bytes or None
        )
        fields = extract_ktp_fields(data, actor=request.user)
    except (PrivateStorageError, Exception):
        fields = None
    if not fields or not any((fields.get(k) or '').strip()
                             for k in KTP_PROFILE_FILL_KEYS):
        messages.warning(request, 'KTP tersimpan sebagai dokumen, namun OCR '
                                  'tidak mengenali data. Lengkapi identitas '
                                  'pribadi manual.')
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    try:
        filled, _profile = _apply_ktp_fields_to_profile(employee, fields)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('sdm:pegawai_detail', employee_id=employee.pk)
    if filled:
        messages.success(
            request, f'KTP tersimpan dan {filled} kolom identitas terisi otomatis. '
                     'Periksa dan simpan bila sudah sesuai.')
    else:
        messages.info(request, 'KTP tersimpan; semua kolom identitas sudah '
                               'terisi sehingga tidak ada data yang diubah.')
    return redirect('sdm:pegawai_detail', employee_id=employee.pk)
```

(Extension rule above: `str(exc)` fallback — write `getattr(exc, 'messages', None) or [str(exc)]`; the plan text `str(ele exc)` is a typo, do NOT copy it. Also prefer the existing module-level `get_private_storage` import in views.py over `_gps` — the local alias line is unnecessary, views.py already imports `get_private_storage` for `pegawai_avatar`.)

`templates/sdm/pegawai/detail.html` — at the top of `identity-pane` (before the first `<dl>`), add when permitted:

```html
{% if can_manage_documents %}
<div class="border rounded p-2 mb-3 bg-light">
    <form method="post" action="{% url 'sdm:pegawai_ktp_ocr' employee.pk %}"
          enctype="multipart/form-data" class="row g-2 align-items-end">
        {% csrf_token %}
        <div class="col-12">
            <label class="form-label small fw-semibold mb-1" for="ktp-ocr-file">
                Unggah KTP (OCR) — isi otomatis identitas pribadi
            </label>
            <input type="file" id="ktp-ocr-file" name="berkas" accept=".pdf,image/jpeg,image/png"
                   class="form-control form-control-sm" required>
        </div>
        <div class="col-12">
            <button type="submit" class="btn btn-outline-primary btn-sm">
                <i class="bi bi-qr-code-scan me-1"></i>Scan KTP dengan OCR
            </button>
        </div>
    </form>
</div>
{% endif %}
```

- [ ] **Step 4: Green**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_directory`
Expected: PASS (existing + 6 new OCR tests + 2 tab-merge tests).

- [ ] **Step 5: Whole-app regression**

Run: `.venv/Scripts/python.exe manage.py test sdm.tests.test_directory sdm.tests.test_dokumen sdm.tests.test_intake_uploads sdm.tests.test_ktp_ocr sdm.tests.test_private_documents`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sdm/urls.py sdm/views.py templates/sdm/pegawai/detail.html sdm/tests/test_directory.py
git commit -m "feat(sdm): profile KTP OCR upload auto-fills personal identity"
```

---

### Task 3: Final gate

- [ ] Run `manage.py test sdm.tests.test_directory sdm.tests.test_dokumen sdm.tests.test_intake sdm.tests.test_intake_uploads sdm.tests.test_ktp_ocr sdm.tests.test_private_documents sdm.tests.test_dokumen_kredensial sdm.tests.test_dokumen_kredensial_ui sdm.tests.test_layanan_mandiri` → PASS expected (prior baseline: 108 + ~8 new).
- [ ] `manage.py check` clean.
- [ ] Manual proof (live env): profile page shows merged tab; upload scan; verify fill + review.

## Explicitly NOT in this plan

- Spec's remaining tab merges (Legalitas+Pendidikan→"Legalitas & Kualifikasi"; Riwayat Kepegawaian+Penempatan→"Riwayat & Penempatan"; rename "Dokumen Kepegawaian"→"Dokumen Bukti") — separate follow-ups; this plan deliberately ships only the docx's headline merge (section 3.1 item 1).
- Migrating per-employee repeat KTP uploads into versions of ONE document (`store_private_document` signature change) — recorded as the noted gap from the previous plan; a follow-up when needed.
- Live camera capture; PDF-to-image rasterization before OCR (DeepSeek handles PDF input quality as-is; if production scans prove unreadable, add rasterization then).
- Emergency-contact field (docx mentions "kontak darurat" under the merged tab) — model has no field for it; adding a model+migration is its own decision, deferred.
