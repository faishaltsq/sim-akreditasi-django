# Rencana Implementasi Integrasi AI Asisten Cerdas (DeepSeek API)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengintegrasikan AI Asisten Cerdas berbasis DeepSeek API (`deepseek-chat` / `deepseek-reasoner`) ke dalam SIM Akreditasi RS untuk membantu pengisian otomatis Rencana Aksi Mitigasi Risiko, rekomendasi tindak lanjut PDCA STARKES, grading insiden keselamatan pasien (IKP), dan analisis dokumen bukti akreditasi (RDWOS).

**Architecture:** Modul service mandiri `akreditasi/ai_service.py` yang memanggil endpoint resmi DeepSeek `https://api.deepseek.com/chat/completions` menggunakan standar OpenAI-compatible HTTP client (`requests`/`httpx`). Endpoint internal Django JSON API (`/ai/generate-mitigasi/`, `/ai/generate-pdca/`, dll.) diproteksi CSRF dan permission RBAC. Di antarmuka (frontend), tombol interaktif *"✨ Bantuan AI DeepSeek"* disematkan di sebelah field textarea formulir (risiko, PDCA, insiden) dengan animasi streaming/loading dan tombol *"Terapkan ke Formulir"*. Kunci API dan setelan model dikelola aman melalui singleton `SystemConfig` di Pusat Kontrol Sistem atau environment variable `DEEPSEEK_API_KEY`.

**Tech Stack:** Python 3.11, Django 5.x, DeepSeek Chat/Reasoner API, JavaScript Fetch / Server-Sent Events (SSE), Bootstrap 5.3.3 UI, JSONField caching.

**Spec:** Dokumen kebutuhan integrasi AI asisten rumah sakit sesuai standar akreditasi KARS STARKES 2022 & Panduan Manajemen Risiko RS (PMKP/KPS).

## Global Constraints

- **Keamanan Kunci API:** API Key DeepSeek tidak boleh bocor ke client-side JavaScript. Semua panggilan LLM wajib melalui backend Django proxy view.
- **Data Privasi Medis (HIPAA / Permenkes):** Prompt yang dikirim ke DeepSeek TIDAK boleh mengandung data identitas pribadi pasien (No. RM, NIK, Nama Lengkap). Sistem menyertakan middleware / helper sanitizer otomatis sebelum prompt dikirim.
- **Fallback Toleran:** Jika kuota DeepSeek habis atau koneksi gagal/timeout (default 20s), sistem menampilkan pesan edukatif tanpa merusak/memblokir alur pengisian manual pengguna.
- **Audit Trail:** Setiap prompt dan respons ringkas AI dicatat ke `AuditLog` dengan action `AI_GENERATE` untuk akuntabilitas akreditasi.
- **Format UI:** Tombol AI tampil elegan dengan warna aksen Teal `#0d9488` / Sparkle purple, modal konfirmasi preview sebelum teks dimasukkan ke dalam textarea form.

## Review Focus

1. **Timeout API Eksternal:** Panggilan API DeepSeek memakan waktu > 15 detik atau putus di tengah jalan -> Sistem harus menangani timeout dengan pesan ramah, tanpa HTTP 500.
2. **Kunci API Kosong / Belum Dikonfigurasi:** Admin belum memasukkan `DEEPSEEK_API_KEY` -> Tombol AI disabled atau menampilkan modal instruksi setup bagi Super Admin.
3. **Penyusupan Data Pasien (Prompt Sanitization):** User memasukkan teks berisi nomor identitas pasien -> Fungsi `sanitize_hospital_prompt()` menyamarkan data sensitif sebelum dikirim ke API DeepSeek.
4. **Token Limit Exceeded:** Deskripsi risiko atau standar EP terlalu panjang -> Pemotongan konteks (truncation) cerdas pada batas token yang aman (max 4.000 token).
5. **Hak Akses User:** User non-login atau role tanpa izin edit tidak boleh bisa memicu trigger endpoint AI (CSRF & `login_required` + `can_edit_risk`/`can_edit_pdca`).

---

## File Structure & Map Modul

```
sim-akreditasi-django/
├── akreditasi/
│   ├── ai_service.py              # Service inti DeepSeek client, prompt builder, sanitizer
│   ├── ai_views.py                # Controller API endpoints AJAX/Fetch
│   ├── ai_prompts.py              # Template prompt standar KARS (Mitigasi Risiko, PDCA, RCA Insiden)
│   ├── system_models.py           # Tambahan field deepseek_api_key, ai_model_name di SystemConfig
│   └── urls.py                    # Routing /ai/...
├── static/
│   ├── js/ai-assist.js            # Frontend helper untuk modal preview, stream/typing effect, copy-to-form
│   └── css/style.css              # Badge AI, sparkle icons, typing cursor styles
├── templates/
│   ├── includes/ai_modal.html     # Modal preview hasil generate AI & selector opsi
│   └── akreditasi/
│       ├── risiko_form.html       # Penyisipan tombol "✨ AI Rekomendasi Mitigasi" di form risiko
│       ├── pdca_matrix.html       # Penyisipan tombol "✨ AI Susun Action Plan" di form PDCA
│       └── insiden_form.html      # Penyisipan tombol "✨ AI Grading & Rekomendasi RCA"
└── tests/
    └── test_ai_integration.py     # Unit test mocking DeepSeek response & sanitasi
```

---

## Task Decomposition

### Task 1: Konfigurasi Model & Penyimpanan Kunci API DeepSeek

**Files:**
- Modify: `akreditasi/system_models.py`
- Modify: `akreditasi/admin.py`
- Test: `tests/test_ai_config.py`

**Interfaces:**
- Produces: `SystemConfig.get_deepseek_api_key() -> str`, `SystemConfig.ai_enabled -> bool`, `SystemConfig.ai_model_name -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai_config.py
import pytest
from akreditasi.system_models import SystemConfig

def test_deepseek_config_fallback_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-env-key-12345")
    config = SystemConfig.get_solo()
    assert config.get_deepseek_api_key() == "sk-test-env-key-12345"
    assert config.ai_model_name in ["deepseek-chat", "deepseek-reasoner"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_config.py -v`
Expected: FAIL (AttributeError: 'SystemConfig' object has no attribute 'get_deepseek_api_key')

- [ ] **Step 3: Tambahkan field dan method pada `SystemConfig`**

Tambahkan field ke `akreditasi/system_models.py`:
- `deepseek_api_key = models.CharField('DeepSeek API Key', max_length=150, blank=True, null=True)`
- `ai_model_name = models.CharField('Model DeepSeek Default', max_length=50, default='deepseek-chat', choices=[('deepseek-chat', 'DeepSeek-V3 (Cepat & Ekonomis)'), ('deepseek-reasoner', 'DeepSeek-R1 (Penalaran Klinis Mendalam)')])`
- `ai_enabled = models.BooleanField('Aktifkan Asisten AI', default=True)`
- Method `get_deepseek_api_key()` yang mengecek database terlebih dahulu, lalu fallback ke `os.environ.get('DEEPSEEK_API_KEY')`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/system_models.py tests/test_ai_config.py
git commit -m "feat(ai): tambahkan konfigurasi DeepSeek API key & model pilihan pada SystemConfig"
```

---

### Task 2: Service DeepSeek Client & Sanitizer Sanitasi Medis

**Files:**
- Create: `akreditasi/ai_prompts.py`
- Create: `akreditasi/ai_service.py`
- Test: `tests/test_ai_service.py`

**Interfaces:**
- Consumes: `SystemConfig.get_deepseek_api_key()`, `SystemConfig.ai_model_name`
- Produces: 
  * `sanitize_hospital_prompt(text: str) -> str`
  * `generate_risk_mitigation(unit_name, risk_type, description, impact, probability, strategy) -> dict`
  * `generate_pdca_action_plan(ep_code, ep_desc, unit_name, current_notes) -> dict`

- [ ] **Step 1: Tulis unit test dengan mock responses**

```python
# tests/test_ai_service.py
from unittest.mock import patch
from akreditasi.ai_service import sanitize_hospital_prompt, generate_risk_mitigation

def test_sanitize_hospital_prompt():
    raw_text = "Pasien Tn. Ahmad No RM 01-23-45 mengalami alergi amoksisilin"
    clean_text = sanitize_hospital_prompt(raw_text)
    assert "01-23-45" not in clean_text
    assert "[NO_RM_DISAMARKAN]" in clean_text or "REDACTED" in clean_text

@patch("akreditasi.ai_service.requests.post")
def test_generate_risk_mitigation_mock(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"rencana_aksi": "1. Buat SOP Double Check\\n2. Pelatihan staf", "strategi_rekomendasi": "Mitigasi (Reduce)", "estimasi_hari": 14}'
            }
        }]
    }
    res = generate_risk_mitigation("Instalasi Farmasi", "Kesalahan Obat", "Salah dosis", 3, 3, "Hindari")
    assert "rencana_aksi" in res
    assert "SOP Double Check" in res["rencana_aksi"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_service.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'akreditasi.ai_service')

- [ ] **Step 3: Implementasikan `ai_prompts.py` dan `ai_service.py`**

Isi `akreditasi/ai_prompts.py`:
- System prompt khusus KARS STARKES 2022 (peran sebagai Ahli Manajemen Mutu dan Keselamatan Pasien RS Tipe B).
- Format output ketat dalam JSON agar mudah diparsing ke masing-masing input field form secara langsung.

Isi `akreditasi/ai_service.py`:
- Regex filter untuk nomor RM, NIK, tanggal lahir.
- Fungsi wrapper HTTP request ke `https://api.deepseek.com/chat/completions` dengan parameter `temperature=0.3`, `timeout=25`.
- Error handler: tangani `requests.exceptions.Timeout`, kuota habis (`insufficient_balance`), dan invalid JSON response.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/ai_prompts.py akreditasi/ai_service.py tests/test_ai_service.py
git commit -m "feat(ai): buat service client DeepSeek dengan prompt spesialis akreditasi KARS & sanitizer data medis"
```

---

### Task 3: Backend Controller Endpoint AJAX

**Files:**
- Create: `akreditasi/ai_views.py`
- Modify: `akreditasi/urls.py`
- Test: `tests/test_ai_views.py`

**Interfaces:**
- Consumes: `ai_service.generate_risk_mitigation()`, `ai_service.generate_pdca_action_plan()`
- Produces: JSON Endpoint POST `/akreditasi/ai/mitigasi-risiko/`, POST `/akreditasi/ai/pdca-plan/`

- [ ] **Step 1: Write the failing view test**

```python
# tests/test_ai_views.py
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User

def test_ai_endpoint_requires_auth():
    c = Client()
    resp = c.post(reverse('akreditasi:ai_generate_mitigasi'), {})
    assert resp.status_code == 302 or resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_views.py -v`
Expected: FAIL (NoReverseMatch)

- [ ] **Step 3: Implementasikan views dan routing**

Di `akreditasi/ai_views.py`:
- Decorator `@login_required` dan verifikasi permission `can_edit_risk` / `can_edit_pdca`.
- Ambil payload JSON dari `request.body`.
- Panggil `ai_service` dan kembalikan `JsonResponse({'success': True, 'data': ...})`.
- Jika terjadi error pada DeepSeek, kembalikan `JsonResponse({'success': False, 'error': str(e)}, status=400)`.

Di `akreditasi/urls.py`:
- Daftarkan `path('ai/mitigasi-risiko/', ai_views.api_generate_mitigasi, name='ai_generate_mitigasi')`
- Daftarkan `path('ai/pdca-plan/', ai_views.api_generate_pdca, name='ai_generate_pdca')`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ai_views.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add akreditasi/ai_views.py akreditasi/urls.py tests/test_ai_views.py
git commit -m "feat(ai): tambahkan REST endpoints untuk trigger rekomendasi mitigasi risiko & PDCA"
```

---

### Task 4: Frontend UI Helper & Integrasi Tombol Form Input Risiko

**Files:**
- Create: `static/js/ai-assist.js`
- Create: `templates/includes/ai_modal.html`
- Modify: `templates/akreditasi/risiko_form.html`
- Modify: `templates/base.html` (include modal)

**Interfaces:**
- Produces: Tombol `✨ AI Bantu Buat Rencana Mitigasi` di header section "C. Rencana Mitigasi" form risiko.
- Interaksi: Mengambil nilai Unit, Jenis Risiko, Deskripsi Risiko, Dampak, Probabilitas -> Kirim via AJAX -> Tampilkan modal preview hasil DeepSeek -> User klik *"Gunakan Rencana Aksi Ini"* -> Textarea `rencana_aksi` otomatis terisi.

- [ ] **Step 1: Buat template modal interaktif `templates/includes/ai_modal.html`**
  - Desain kartu modal bertema Teal dengan badge *"Powered by DeepSeek AI"*.
  - Menampilkan:
    1. Rekomendasi Rencana Aksi (Numbered list terstruktur)
    2. Rekomendasi Strategi Mitigasi
    3. Estimasi Durasi Penyelesaian
  - Tombol: *"Batal"*, *"Generate Ulang"*, dan *"Terapkan ke Formulir"*.

- [ ] **Step 2: Buat `static/js/ai-assist.js`**
  - Listener event tombol AI.
  - Validasi bahwa input dasar (Jenis Risiko & Deskripsi) sudah diisi sebelum memanggil API.
  - State indikator loading spinner + teks *"DeepSeek sedang menganalisis risiko & menyusun mitigasi sesuai standar KARS..."*.
  - Fungsi transfer nilai dari modal ke textarea formulir target.

- [ ] **Step 3: Pasang tombol di `templates/akreditasi/risiko_form.html`**
  - Tepat di atas label `Rencana Aksi *`, sematkan tombol:
    `<button type="button" class="btn btn-sm btn-outline-teal float-end" id="btn-ai-mitigasi"><i class="bi bi-stars text-teal me-1"></i>Bantu Susun Rencana Mitigasi</button>`

- [ ] **Step 4: Uji manual di browser (E2E simulation)**
  - Buka `/risiko/baru/`, isi Jenis Risiko: "Pemberian obat LASA tertukar", klik tombol AI, verifikasi data berhasil masuk ke textarea.

- [ ] **Step 5: Commit**

```bash
git add static/js/ai-assist.js templates/includes/ai_modal.html templates/akreditasi/risiko_form.html
git commit -m "feat(ui): sematkan tombol interaktif asisten AI DeepSeek pada formulir Input Risiko"
```

---

### Task 5: Pengaturan AI di Pusat Kontrol Sistem (Tab 4 / Tab Baru)

**Files:**
- Modify: `templates/accounts/admin_control_center.html`
- Modify: `accounts/views.py` (handler simpan konfigurasi AI)
- Test: Verifikasi setting form di Pusat Kontrol

**Interfaces:**
- Menyediakan UI bagi Super Admin untuk:
  * Memasukkan / memperbarui `DEEPSEEK_API_KEY` (input password bertopeng sensor).
  * Memilih model: `deepseek-chat` (V3) atau `deepseek-reasoner` (R1).
  * Toggle ON/OFF fitur AI secara global di seluruh rumah sakit.
  * Uji koneksi langsung (Test Ping ke API DeepSeek).

- [ ] **Step 1: Tambahkan card konfigurasi AI di Tab 4 Pusat Kontrol Admin**
- [ ] **Step 2: Update controller simpan konfigurasi di `accounts/views.py`**
- [ ] **Step 3: Tambahkan tombol "Tes Koneksi DeepSeek" via AJAX**
- [ ] **Step 4: Commit**

```bash
git add templates/accounts/admin_control_center.html accounts/views.py
git commit -m "feat(admin): tambahkan panel konfigurasi & tes koneksi DeepSeek API di Pusat Kontrol Sistem"
```

---

## Rincian Prompt Standar KARS (Preview Spesifikasi)

Prompt yang akan disuntikkan ke DeepSeek dirancang khusus untuk mematuhi regulasi perumahsakitan Indonesia:

```
Anda adalah Konsultan Ahli Manajemen Mutu dan Keselamatan Pasien Rumah Sakit (KARS STARKES 2022).
Tugas Anda adalah menyusun rencana mitigasi risiko yang aplikatif, SMART (Specific, Measurable, Achievable, Relevant, Time-bound), dan berfokus pada pencegahan cedera pasien (patient safety).

Konteks Risiko:
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Deskripsi: {deskripsi_risiko}
- Tingkat Keparahan (Dampak): {dampak} / 5
- Frekuensi (Probabilitas): {probabilitas} / 5
- Skor Risiko: {skor} (Tingkat: {level})

Format Output JSON:
{
  "rencana_aksi": "1. [Langkah pencegahan langsung]\\n2. [Pembaruan SOP / Regulasi internal]\\n3. [Sosialisasi & pelatihan staf]\\n4. [Monitoring berkala]",
  "strategi_disarankan": "Hindari / Mitigasi / Transfer / Terima",
  "pj_rekomendasi": "Kepala Unit / Tim Farmasi Klinis / dll",
  "target_durasi_hari": 14,
  "catatan_kars": "Rekomendasi pemenuhan standar STARKES Pokja PKPO / PMKP terkait"
}
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-28-integrasi-ai-deepseek.md`. Please review the plan. Which execution approach would you prefer?

- **Native** (Direkomendasikan) - Saya langsung implementasikan setiap task step-by-step di sesi ini, langsung diverifikasi pada kode dan dideploy ke Railway, tercepat dan paling efisien.
- **Subagent-driven** - Subagent terpisah mengeksekusi setiap task dengan reviewer independen di tiap langkah.

Untuk plan ini saya merekomendasikan **Native**, karena arsitektur Django service + frontend AJAX tombol form risiko ini terhubung langsung dengan modul yang baru saja kita perbaiki (form risiko unit Farmasi), sehingga implementasi langsung lebih cepat, kohesif, dan bisa langsung kita uji pakai API key DeepSeek.

Apakah plan di atas sudah menangkap kebutuhan yang kamu inginkan, dan apakah kita langsung eksekusi sekarang?