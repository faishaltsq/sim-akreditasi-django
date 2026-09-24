"""
Audit QA Level 2 — RBAC Isolation, Negative Testing, Edge Cases, UI Consistency
"""
import requests
from bs4 import BeautifulSoup
import re
import json

BASE_URL = "https://sim-akreditasi-web-production.up.railway.app"
RESULTS = []

def log_test(module, test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((module, test_name, status, detail))
    print(f"[{status}] [{module}] {test_name}: {detail}")

def login(username, password):
    s = requests.Session()
    r = s.get(f"{BASE_URL}/accounts/login/")
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
    r_post = s.post(f"{BASE_URL}/accounts/login/", data={
        'csrfmiddlewaretoken': csrf, 'username': username, 'password': password
    }, headers={'Referer': f"{BASE_URL}/accounts/login/"}, allow_redirects=False)
    if r_post.status_code in (301, 302):
        return s
    return None

# ==================== RBAC ISOLATION ====================
print("=== 1. RBAC ISOLATION — Nakes Tidak Bisa Akses Admin ===")
nakes = login("perawat.igd", "Nakes@1234")
if nakes:
    admin_only_urls = [
        ("/accounts/users/", "User Management"),
        ("/unit/", "Unit Management"),
        ("/pokja/", "Pokja Management"),
        ("/profil/", "Profil RS"),
        ("/log/", "Audit Log"),
    ]
    for url, label in admin_only_urls:
        r = nakes.get(f"{BASE_URL}{url}", allow_redirects=False)
        # Nakes should get 403 or redirect, NOT 200
        is_blocked = r.status_code in (403, 302)
        log_test("RBAC", f"Nakes blocked from {label} ({url})", is_blocked, f"Status: {r.status_code}")

print("\n=== 2. RBAC ISOLATION — Asesor Tidak Bisa Modifikasi ===")
asesor = login("asesor1", "asesor123")
if asesor:
    r_ep_create = asesor.get(f"{BASE_URL}/ep/baru/", allow_redirects=False)
    is_blocked = r_ep_create.status_code in (403, 302)
    log_test("RBAC", "Asesor blocked from EP Create", is_blocked, f"Status: {r_ep_create.status_code}")

    r_portal = asesor.get(f"{BASE_URL}/portal-nakes/", allow_redirects=False)
    is_blocked_portal = r_portal.status_code in (403, 302)
    log_test("RBAC", "Asesor blocked from Portal Nakes", is_blocked_portal, f"Status: {r_portal.status_code}")

print("\n=== 3. NEGATIVE TESTING — Invalid Login ===")
invalid_s = requests.Session()
r = invalid_s.get(f"{BASE_URL}/accounts/login/")
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
r_bad = invalid_s.post(f"{BASE_URL}/accounts/login/", data={
    'csrfmiddlewaretoken': csrf, 'username': 'hacker', 'password': 'wrongpass'
}, headers={'Referer': f"{BASE_URL}/accounts/login/"}, allow_redirects=False)
rejected = (r_bad.status_code == 200 and "alert-danger" in r_bad.text)
log_test("NEGATIVE", "Invalid login rejected with error message", rejected, f"Status: {r_bad.status_code}")

print("\n=== 4. NEGATIVE TESTING — 404 Handling ===")
admin_s = login("admin", "admin123")
if admin_s:
    r_404 = admin_s.get(f"{BASE_URL}/nonexistent-page-xyz/")
    log_test("NEGATIVE", "404 for nonexistent URL", r_404.status_code == 404, f"Status: {r_404.status_code}")

    r_ep404 = admin_s.get(f"{BASE_URL}/ep/99999/detail/")
    log_test("NEGATIVE", "404 for nonexistent EP detail", r_ep404.status_code == 404, f"Status: {r_ep404.status_code}")

    r_unit404 = admin_s.get(f"{BASE_URL}/unit/99999/edit/")
    log_test("NEGATIVE", "404 for nonexistent Unit edit", r_unit404.status_code == 404, f"Status: {r_unit404.status_code}")

print("\n=== 5. UI CONSISTENCY — Cek Tema Putih-Hijau (Tidak ada warna lama) ===")
if admin_s:
    pages_to_check = [
        ("/", "Dashboard"),
        ("/matriks/", "Matriks PDCA"),
        ("/unit/hierarki/", "Unit Tree"),
        ("/rekap/", "Rekap"),
        ("/accounts/users/", "User List"),
    ]
    old_colors = ['#0F172A', '#2563EB', '#1D4ED8', '#1E293B']
    for url, label in pages_to_check:
        r = admin_s.get(f"{BASE_URL}{url}")
        found_old = [c for c in old_colors if c.lower() in r.text.lower()]
        passed = len(found_old) == 0
        log_test("UI_THEME", f"No old blue/black colors in {label}", passed, f"Found: {found_old}" if found_old else "Clean")

# Login page CSS check
r_login = requests.get(f"{BASE_URL}/accounts/login/")
found_old_login = [c for c in old_colors if c.lower() in r_login.text.lower()]
log_test("UI_THEME", "No old colors in Login Page", len(found_old_login) == 0, f"Found: {found_old_login}" if found_old_login else "Clean")

# Static CSS check
r_css = requests.get(f"{BASE_URL}/static/css/style.css")
found_old_css = [c for c in old_colors if c.lower() in r_css.text.lower()]
log_test("UI_THEME", "No old colors in style.css", len(found_old_css) == 0, f"Found: {found_old_css}" if found_old_css else "Clean")

print("\n=== 6. CROSS-ROLE PORTAL NAKES ACCESS ===")
# Dokter spesialis & Apoteker farmasi login ke portal nakes masing-masing
for uname, upass in [("dokter.spesialis", "Nakes@1234"), ("apoteker.farmasi", "Nakes@1234")]:
    s = login(uname, upass)
    if s:
        r = s.get(f"{BASE_URL}/portal-nakes/")
        passed = r.status_code == 200 and uname.split('.')[0] in r.text.lower()
        log_test("NAKES_MULTI", f"{uname} akses Portal Nakes", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("NAKES_MULTI", f"{uname} login", False, "Login failed")

print("\n=== 7. DATA INTEGRITY — Seed Data Completeness ===")
if admin_s:
    r_users = admin_s.get(f"{BASE_URL}/accounts/users/")
    soup_users = BeautifulSoup(r_users.text, 'html.parser')
    expected_users = ['admin', 'koord_tkrs', 'ka_farmasi', 'asesor1', 'perawat.igd', 'dokter.spesialis', 'apoteker.farmasi']
    for u in expected_users:
        found = u in r_users.text
        log_test("DATA", f"User {u} exists in User List", found, "Found" if found else "MISSING")

    r_rekap_kps = admin_s.get(f"{BASE_URL}/rekap-kps/")
    has_kps_data = ("STR" in r_rekap_kps.text or "SIP" in r_rekap_kps.text or "kredensial" in r_rekap_kps.text.lower())
    log_test("DATA", "Rekap KPS has credential data", has_kps_data, "KPS data found" if has_kps_data else "Empty")

print("\n=== 8. RESPONSE TIME AUDIT ===")
import time
endpoints_perf = [
    ("/accounts/login/", "Login Page"),
    ("/", "Dashboard (admin)"),
    ("/matriks/", "Matriks PDCA"),
    ("/rekap/", "Rekap"),
    ("/portal-nakes/", "Portal Nakes"),
]
for url, label in endpoints_perf:
    s_perf = admin_s if url != "/portal-nakes/" else nakes
    if s_perf is None:
        continue
    start = time.time()
    r = s_perf.get(f"{BASE_URL}{url}")
    elapsed = time.time() - start
    passed = elapsed < 5.0  # 5s threshold
    log_test("PERF", f"Response time {label}", passed, f"{elapsed:.2f}s (threshold: 5s)")

print("\n=== 9. SECURITY HEADERS ===")
r_sec = requests.get(f"{BASE_URL}/accounts/login/")
headers_check = {
    'X-Frame-Options': ('DENY', 'SAMEORIGIN'),
    'X-Content-Type-Options': ('nosniff',),
}
for hdr, expected_vals in headers_check.items():
    val = r_sec.headers.get(hdr, '')
    passed = any(e.lower() in val.lower() for e in expected_vals) if val else False
    log_test("SECURITY_HDR", f"Header {hdr}", passed, f"Value: {val}" if val else "MISSING")

# CSRF cookie present
csrf_cookie = r_sec.cookies.get('csrftoken', '')
log_test("SECURITY_HDR", "CSRF Cookie present", bool(csrf_cookie), "Present" if csrf_cookie else "MISSING")

print("\n" + "=" * 60)
print("=== REKAP HASIL AUDIT LEVEL 2 ===")
print("=" * 60)
total = len(RESULTS)
passed_count = sum(1 for r in RESULTS if r[2] == "PASS")
failed_count = sum(1 for r in RESULTS if r[2] == "FAIL")
print(f"Total Test: {total} | Lulus: {passed_count} | Gagal: {failed_count}")
if failed_count > 0:
    print("\n--- DETAIL KEGAGALAN ---")
    for module, name, status, detail in RESULTS:
        if status == "FAIL":
            print(f"  ❌ [{module}] {name}: {detail}")
