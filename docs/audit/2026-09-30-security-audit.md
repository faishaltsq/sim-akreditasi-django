# Security & QA Audit — SIM Akreditasi RS (SIK AP)
**Tanggal:** 2026-09-30  
**Auditor:** Hermes Agent  
**Lingkup:** Seluruh codebase (accounts, akreditasi, config, templates, static)

---

## 🔴 KRITIS — Harus segera diperbaiki

### K-1: IDOR di `quick_score`, `inline_edit_pdca`, `unlink_doc`
**File:** `akreditasi/views.py` baris 311, 347, 517  
**Masalah:** `get_object_or_404(QualityRecord, id=record_id)` / `get_object_or_404(EvidenceFile, id=file_id)` — tidak ada validasi bahwa record/file tersebut milik unit atau rumah sakit yang benar. User unit-scoped (mis. `ka.depo.rajal`) bisa mengirim `record_id` milik unit lain dan mengubah/menghapus data RS lain.  
**Dampak:** Privilege escalation horizontal — user staf bisa ubah skor EP, PDCA, hapus bukti milik unit lain.  
**Fix:** Tambahkan filter owner ke query.

### K-2: IDOR di `verify_kredensial`
**File:** `akreditasi/views.py` baris 1363  
**Masalah:** `get_object_or_404(NakesCredential, id=cred_id)` tanpa filter unit. KEPALA_UNIT bisa verify kredensial nakes dari unit lain.  
**Fix:** Tambahkan filter `user_profile__unit_kerja=request.user.profile.unit_kerja` atau cek ownership.

### K-3: Upload file tanpa validasi ekstensi/MIME
**File:** `akreditasi/views.py` baris 444–478, 710–740, 1264–1295  
**Masalah:** Tidak ada whitelist ekstensi (`pdf`, `docx`, `jpg`, dll.) dan tidak ada validasi magic bytes. User bisa upload `.php`, `.exe`, `.html` (XSS via Supabase public URL).  
**Dampak:** Stored XSS, path injection di nama file.  
**Fix:** Tambahkan `ALLOWED_EXTENSIONS` whitelist + validasi ekstensi sebelum upload.

### K-4: `str(e)` bocor ke response JSON
**File:** `akreditasi/views.py` baris 339, 389, 512  
**Masalah:** `return JsonResponse({'error': str(e)}, status=500)` — exception message bisa berisi stack trace, nama tabel DB, path file sistem.  
**Fix:** Log exception di server, kembalikan pesan generik ke client.

### K-5: Django admin aktif di production tanpa proteksi tambahan
**File:** `config/urls.py` baris 7  
**Masalah:** `path('admin/', admin.site.urls)` — Django admin terbuka di URL default `/admin/`. Tidak ada IP whitelist, rate limit, atau custom URL.  
**Dampak:** Brute force attack target, informasi admin panel terekspos.  
**Fix:** Ubah URL admin ke path acak (`admin-sikai-7f3d/`) atau nonaktifkan jika tidak dipakai.

---

## 🟠 TINGGI — Perbaiki sprint ini

### T-1: Tidak ada HSTS / Secure cookie di production
**File:** `config/settings.py`  
**Masalah:** Tidak ada `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`. Railway sudah HTTPS tapi browser tidak dipaksa.  
**Dampak:** Session hijacking via HTTP downgrade jika cookie ter-intercept.  
**Fix:** Tambahkan block `if not DEBUG:` dengan HSTS + secure cookies.

### T-2: Tidak ada rate limiting di endpoint AI dan login
**File:** `akreditasi/ai_views.py`, `accounts/views.py`  
**Masalah:** Endpoint AI (6 fungsi) tidak ada throttle. Jika API key DeepSeek aktif, user bisa spam 1000 request → biaya besar. Endpoint login juga tidak ada lockout.  
**Fix:** Gunakan `django-ratelimit` atau middleware sederhana di-cache.

### T-3: DEBUG default `True` jika env var tidak di-set
**File:** `config/settings.py` baris 12  
**Masalah:** `os.environ.get('DJANGO_DEBUG', 'True')` — jika Railway gagal inject env var, DEBUG aktif di production.  
**Fix:** Default ke `'False'`. Aktifkan DEBUG hanya secara eksplisit.

### T-4: `SECRET_KEY` fallback plaintext di source code
**File:** `config/settings.py` baris 7–10  
**Masalah:** Fallback `'django-insecure-sim-akreditasi-dev-only-change-in-production'` di kode. Jika env var tidak di-set, session dan CSRF token bisa diforge.  
**Fix:** Raise `ImproperlyConfigured` jika SECRET_KEY tidak di-set di env (production harus gagal startup bukan jalan insecure).

### T-5: `rekap_view` tanpa RBAC
**File:** `akreditasi/views.py` baris 954  
**Masalah:** `@login_required` saja — semua user login (termasuk STAF_NAKES) bisa lihat rekap skor seluruh pokja semua unit.  
**Fix:** Tambahkan cek `role in ('SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT', 'KOORDINATOR_POKJA')`.

### T-6: `auto_scoring_pokja` tanpa RBAC eksplisit
**File:** `akreditasi/views.py` baris 1013  
**Masalah:** `@login_required` saja — endpoint POST ini mengubah skor massal. Staf nakes bisa trigger auto-scoring global.  
**Fix:** Tambahkan `@editor_required` atau cek role.

---

## 🟡 SEDANG — Backlog teknis

### S-1: Nama file upload tidak di-sanitasi sepenuhnya
**File:** `akreditasi/supabase_storage.py` baris 12  
**Masalah:** `os.path.basename(filename).replace(' ', '_')` — karakter berbahaya lain (`<>:"/?*#`) tetap lolos. Bisa menyebabkan masalah di URL Supabase dan XSS via filename di tooltip HTML.  
**Fix:** Tambahkan `re.sub(r'[^\w.\-]', '_', clean_name)`.

### S-2: File berukuran besar tidak dibatasi
**File:** `akreditasi/views.py` upload endpoints  
**Masalah:** Tidak ada `MAX_UPLOAD_SIZE` check. User bisa upload file 500MB+ → DoS / biaya Supabase.  
**Fix:** Cek `file_obj.size > 10 * 1024 * 1024` (10MB) di awal view.

### S-3: `except Exception: pass` menelan error unit-scoping
**File:** `akreditasi/views.py` baris 235–236  
**Masalah:** Jika query profile gagal (misal DB error), unit-scoping silently disabled → user unit-scoped mendapat akses global.  
**Fix:** Log exception, kembalikan 403 daripada fallback ke akses penuh.

### S-4: `Supabase Key` masuk ke HTTP header pakai `apiKey`
**File:** `akreditasi/supabase_storage.py` baris 20  
**Masalah:** `"apiKey": supabase_key` dikirim di header bersama dengan `Authorization: Bearer`. Kunci sama dua kali. Ini bukan bug tapi prinsip least exposure — cukup satu.  
**Catatan:** Tidak kritis karena backend-only, tapi perlu dirapikan.

### S-5: AuditLog tidak mencatat IP address
**File:** `akreditasi/views.py` (semua AuditLog.objects.create)  
**Masalah:** IP address aktor tidak tersimpan di AuditLog. Investigasi insiden menjadi sulit.  
**Fix:** Tambahkan field `ip_address` di model AuditLog dan isi dari `request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))`.

---

## ✅ Sudah Aman

| Area | Status |
|---|---|
| CSRF protection | ✅ `CsrfViewMiddleware` aktif + `@require_POST` di semua mutasi |
| SQL Injection | ✅ Pure ORM, nol `raw()` / `cursor.execute()` |
| XSS di template | ✅ Django autoescaping aktif, tidak ada `{% autoescape off %}` |
| API Key DeepSeek | ✅ Backend-only, tidak pernah ke response JSON/frontend |
| Sanitasi data medis | ✅ `sanitize_hospital_prompt()` dipanggil di seluruh 6 fungsi AI |
| Path traversal upload | ✅ `os.path.basename()` strip path prefix |
| Autentikasi semua view | ✅ Semua view ada `@login_required` |
| NakesCredential delete | ✅ Filter `user_profile=request.user.profile` mencegah IDOR |
| Supabase key di frontend | ✅ Tidak ada key di template / JS |
| Django admin auth | ✅ Memerlukan `is_staff=True` |
| Clickjacking | ✅ `XFrameOptionsMiddleware` aktif |
| HTTPS di Railway | ✅ `SECURE_PROXY_SSL_HEADER` dikonfigurasi |
| Password validation | ✅ 4 validator aktif |

---

## Prioritas Fix

| # | Issue | Effort | Impact |
|---|---|---|---|
| 1 | K-1: IDOR quick_score/inline_edit/unlink | Kecil | Kritis |
| 2 | K-2: IDOR verify_kredensial | Kecil | Kritis |
| 3 | K-3: File upload tanpa validasi MIME/ext | Kecil | Kritis |
| 4 | K-4: str(e) di JSON response | Kecil | Tinggi |
| 5 | K-5: Django admin URL default | Kecil | Tinggi |
| 6 | T-3: DEBUG default True | Trivial | Tinggi |
| 7 | T-4: SECRET_KEY fallback insecure | Trivial | Tinggi |
| 8 | T-1: HSTS + secure cookies | Kecil | Tinggi |
| 9 | T-5: rekap_view RBAC | Trivial | Sedang |
| 10 | T-6: auto_scoring_pokja RBAC | Trivial | Sedang |
| 11 | T-2: Rate limiting AI & login | Sedang | Sedang |
| 12 | S-1–S-5 | Kecil | Rendah |
