# IGD Comprehensive Clinical Modules (Revisi 02 Update) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full Emergency Department (IGD) clinical assessment, nursing diagnosis (SDKI/SLKI/SIKI 3S), integrated CPPT SOAP with EWS calculation, one-click care implementation checklist, disposition/RTL workflow (SBAR/SISRUTE/DoA), automated E-Resume Medis, and dashboard compliance indicators.

**Architecture:** Extend `KunjunganPasien` with structured clinical assessment and 3S nursing fields; provide specialized modal workflows on `igd_dashboard.html`; add calculation helper for Early Warning Score (NEWS/EWS); integrate CPPT creation with automatic execution logging; generate standard PDF/HTML Emergency Clinical Resume (`E-Resume Medis IGD`).

**Tech Stack:** Django 5.x, Python 3.12/3.14, Bootstrap 5.3.3, Django ORM, SQLite/PostgreSQL.

**Spec:** `Downloads/Revisi 02 di unit IGD.docx` (479.3 KB, 222 lines)

## Global Constraints
- Plans must always be written in English.
- Deliverables in Bahasa Indonesia for end-user facing text.
- DeepSeek / AI keys strictly backend-only.
- All credentials and sensitive health data protected and sanitized.
- Unit-level least privilege (RBAC) enforced.

## Review Focus
1. Triage auto-escalation or EWS calculation gracefully handles null/empty vitals without throwing ZeroDivisionError or ValueError.
2. SDKI/SLKI/SIKI nursing diagnosis taxonomy saves cleanly and links to the clinical visit without schema breaks.
3. Asesmen awal completion compliance badge correctly detects whether essential fields (Anamnesis, TTV, Diagnosis, Risiko) are filled.
4. Disposition actions (Admission, SISRUTE referral, Pulang, PAPS, Death) update visit status and bed state consistently.
5. Print/preview E-Resume Medis handles missing optional fields gracefully with standard medical placeholders.

---

### Task 1: Clinical Model Extensions & Migrations

**Files:**
- Modify: `pasien/models.py`
- Test: `pasien/tests_revisi_igd_klinis.py`

**Interfaces:**
- Produces: `KunjunganPasien` clinical fields:
  - Anamnesis: `anamnesis_rps`, `anamnesis_rpd`, `anamnesis_rpk`, `anamnesis_obat`
  - Pemeriksaan Fisik: `fisik_airway`, `fisik_breathing`, `fisik_circulation`, `fisik_disability`, `fisik_exposure`
  - Bio-Psiko-Sosial-Spiritual: `status_psikososial`, `status_spiritual`
  - Skrining: `skrining_jatuh_skor`, `skrining_jatuh_grade`, `skrining_gizi_mst`
  - Diagnosis 3S: `diagnosa_keperawatan_sdki`, `luaran_keperawatan_slki`, `intervensi_keperawatan_siki`
  - Compliance: `is_asesmen_awal_lengkap` (property)
  - Helper: `hitung_news_score()` returning integer EWS and severity grade.

- [ ] **Step 1: Write the failing test for clinical fields and EWS calculation**

```python
from django.test import TestCase
from django.utils import timezone
from pasien.models import Pasien, KunjunganPasien

class ClinicalModelExtensionTestCase(TestCase):
    def test_news_score_calculation(self):
        p = Pasien.objects.create(no_rm='RM-TEST-EWS', nama_lengkap='Pasien EWS', tanggal_lahir='1990-01-01', jenis_kelamin='L')
        k = KunjunganPasien.objects.create(
            pasien=p, no_kunjungan='KUNJ-EWS-01', jenis_kunjungan='IGD', status='TRIAGE',
            tanggal_masuk=timezone.now(),
            ttv_sistole=85,  # low BP -> score 3
            ttv_nadi=135,    # severe tachy -> score 3
            ttv_rr=26,       # tachypnea -> score 3
            ttv_suhu=39.2,   # high fever -> score 2
            ttv_spo2=91      # hypoxemia -> score 3
        )
        score, category = k.hitung_news_score()
        self.assertGreaterEqual(score, 7)
        self.assertEqual(category, 'TINGGI')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis.ClinicalModelExtensionTestCase.test_news_score_calculation`
Expected: FAIL (AttributeError: 'KunjunganPasien' object has no attribute 'hitung_news_score')

- [ ] **Step 3: Add clinical fields and `hitung_news_score` method to `KunjunganPasien`**

Implement fields in `pasien/models.py` and run `makemigrations` and `migrate`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis.ClinicalModelExtensionTestCase.test_news_score_calculation`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/models.py pasien/migrations/* pasien/tests_revisi_igd_klinis.py
git commit -m "feat(pasien): extend KunjunganPasien with comprehensive IGD clinical assessment and EWS helper"
```

---

### Task 2: Backend Clinical Endpoints (Asesmen Awal, CPPT Quick-Add, & E-Resume Medis)

**Files:**
- Modify: `pasien/views.py`
- Modify: `pasien/urls.py`
- Create: `templates/pasien/cetak_resume_igd.html`
- Test: `pasien/tests_revisi_igd_klinis.py`

**Interfaces:**
- Produces:
  - `igd_asesmen_awal_save(request, pk)`: saves 5 tabs of assessment + 3S SDKI/SLKI/SIKI.
  - `igd_cppt_quick_add(request, pk)`: quick-logs SOAP entry with automatic timestamp.
  - `cetak_resume_igd(request, pk)`: prints official Emergency Medical Resume.

- [ ] **Step 1: Write the failing test for endpoints**

```python
def test_igd_asesmen_awal_save_view(self):
    url = reverse('pasien:igd_asesmen_awal_save', kwargs={'pk': self.kunjungan.pk})
    res = self.client.post(url, {
        'anamnesis_rps': 'Nyeri dada mendadak sejak 2 jam lalu',
        'fisik_airway': 'Paten',
        'diagnosa_keperawatan_sdki': 'D.0077 - Nyeri Akut',
        'luaran_keperawatan_slki': 'L.08066 - Tingkat Nyeri Menurun',
        'intervensi_keperawatan_siki': 'I.08238 - Manajemen Nyeri',
    })
    self.assertEqual(res.status_code, 302)
    self.kunjungan.refresh_from_db()
    self.assertEqual(self.kunjungan.anamnesis_rps, 'Nyeri dada mendadak sejak 2 jam lalu')
    self.assertEqual(self.kunjungan.diagnosa_keperawatan_sdki, 'D.0077 - Nyeri Akut')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis.ClinicalEndpointTestCase`
Expected: FAIL (NoReverseMatch or 404)

- [ ] **Step 3: Implement views in `pasien/views.py`, register URLs, and create `cetak_resume_igd.html` template**

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pasien/views.py pasien/urls.py templates/pasien/cetak_resume_igd.html pasien/tests_revisi_igd_klinis.py
git commit -m "feat(igd): add Asesmen Awal save, CPPT quick add, and E-Resume Medis IGD print view"
```

---

### Task 3: Comprehensive IGD Dashboard UI Integration

**Files:**
- Modify: `templates/pasien/igd_dashboard.html`
- Modify: `pasien/views.py` (`igd_dashboard` context)
- Test: `pasien/tests_revisi_igd_klinis.py`

**Interfaces:**
- Produces:
  - Table Action Buttons: `[Asesmen Awal]`, `[CPPT / Observasi]`, `[Disposisi / RTL]`, `[E-Resume]`.
  - Compliance Badge per row: `Badge Hijau (Asesmen Lengkap)` or `Badge Kuning (Asesmen Belum Lengkap)`.
  - EWS Badge per row: calculated from TTV (`NEWS: 0 (Normal)`, `NEWS: 1-4 (Rendah)`, `NEWS: 5-6 (Sedang)`, `NEWS: >=7 (Tinggi)`).
  - Modal Asesmen Awal 5-Tab:
    1. Triage & TTV + Nyeri
    2. Anamnesis (RPS, RPD, RPK, Alergi, Obat) & Fisik ABCDE
    3. Bio-Psiko-Sosial-Spiritual & Ekonomi
    4. Skrining Risiko (Morse / Humpty Dumpty, MST Nutrisi)
    5. Diagnosis Medis (ICD-10/ICD-9) & Diagnosis Keperawatan (SDKI / SLKI / SIKI 3S)
  - Modal CPPT & Observasi with Quick Add + Timeline
  - Modal Disposisi / RTL (Ranap/Bed with SBAR, Rujuk SISRUTE, Pulang Sembuh, PAPS, DoA)

- [ ] **Step 1: Write test for dashboard rendering new action buttons and compliance badges**

```python
def test_dashboard_renders_clinical_modals_and_compliance_badge(self):
    res = self.client.get(reverse('pasien:igd_dashboard'))
    self.assertEqual(res.status_code, 200)
    self.assertContains(res, 'modalAsesmenAwal')
    self.assertContains(res, 'modalCPPT')
    self.assertContains(res, 'modalDisposisi')
    self.assertContains(res, 'Asesmen')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis.DashboardUIClinicalTestCase`
Expected: FAIL

- [ ] **Step 3: Implement dashboard changes in `templates/pasien/igd_dashboard.html` and update `igd_dashboard` context**

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd_klinis`
Expected: PASS

- [ ] **Step 5: Run full regression test suite**

Run: `.venv/Scripts/python.exe manage.py test pasien.tests_revisi_igd pasien.tests_revisi_igd_klinis pasien.tests_revisi_pendaftaran pasien.tests_laboratorium pasien.tests_route_rbac accounts.tests_unit_rbac accounts.tests_sidebar_visibility akreditasi.tests_ai`
Expected: 50+ PASS

- [ ] **Step 6: Commit and Push**

```bash
git add templates/pasien/igd_dashboard.html pasien/views.py pasien/tests_revisi_igd_klinis.py
git commit -m "feat(igd): integrate Asesmen Awal, 3S Nursing Diagnosis, CPPT & EWS, and RTL Disposition modals into IGD Dashboard"
git push origin master
```
