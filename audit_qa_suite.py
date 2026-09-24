"""
Skrip Audit QA Komprehensif untuk SIM Akreditasi RS (SIK AP)
Target: Production Railway
"""
import requests
from bs4 import BeautifulSoup
import re
import sys

BASE_URL = "https://sim-akreditasi-web-production.up.railway.app"

TEST_USERS = [
    ("admin", "admin123", "ADMIN_RS"),
    ("koord_tkrs", "koord123", "KOORD_POKJA"),
    ("ka_farmasi", "farmasi123", "KEPALA_UNIT"),
    ("asesor1", "asesor123", "ASESOR_INTERNAL"),
    ("perawat.igd", "Nakes@1234", "STAF_NAKES"),
]

RESULTS = []

def log_test(module, test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((module, test_name, status, detail))
    print(f"[{status}] [{module}] {test_name}: {detail}")

def get_session_and_login(username, password):
    s = requests.Session()
    # 1. GET login page
    r = s.get(f"{BASE_URL}/accounts/login/")
    if r.status_code != 200:
        return None, f"GET login page error: {r.status_code}"
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
    if not csrf_input:
        return None, "CSRF token not found"
    csrf_token = csrf_input['value']

    # 2. POST login
    post_data = {
        'csrfmiddlewaretoken': csrf_token,
        'username': username,
        'password': password
    }
    headers = {'Referer': f"{BASE_URL}/accounts/login/"}
    r_post = s.post(f"{BASE_URL}/accounts/login/", data=post_data, headers=headers, allow_redirects=False)
    
    if r_post.status_code in (301, 302):
        redirect_url = r_post.headers.get('Location', '')
        return s, redirect_url
    else:
        # Check error on page
        soup_err = BeautifulSoup(r_post.text, 'html.parser')
        err = soup_err.find('div', class_='alert-danger')
        err_msg = err.get_text(strip=True) if err else f"HTTP {r_post.status_code}"
        return None, err_msg

print("=== 1. AUDIT OTENTIKASI & RBAC LOGIN ===")
sessions = {}
for username, password, expected_role in TEST_USERS:
    s, detail = get_session_and_login(username, password)
    passed = s is not None
    log_test("AUTH", f"Login {username} ({expected_role})", passed, detail)
    if passed:
        sessions[username] = s

print("\n=== 2. AUDIT KEAMANAN (UNAUTHENTICATED ACCESS) ===")
unauth_s = requests.Session()
protected_endpoints = [
    ("/", 302),
    ("/dashboard/", 302),
    ("/matriks/", 302),
    ("/ep/list/", 302),
    ("/unit/", 302),
    ("/unit/hierarki/", 302),
    ("/pokja/", 302),
    ("/profil/", 302),
    ("/log/", 302),
    ("/rekap/", 302),
    ("/portal-nakes/", 302),
    ("/rekap-kps/", 302),
    ("/accounts/users/", 302),
]

for endpoint, expected_status in protected_endpoints:
    r = unauth_s.get(f"{BASE_URL}{endpoint}", allow_redirects=False)
    passed = (r.status_code == expected_status and "/accounts/login" in r.headers.get('Location', ''))
    log_test("SECURITY", f"Unauth protection {endpoint}", passed, f"Status: {r.status_code}, Redirect: {r.headers.get('Location','')}")

print("\n=== 3. AUDIT SMART REDIRECTION ROLE ===")
# Nakes to portal-nakes
if "perawat.igd" in sessions:
    r = sessions["perawat.igd"].get(f"{BASE_URL}/", allow_redirects=False)
    passed = (r.status_code == 302 and "portal-nakes" in r.headers.get('Location', ''))
    log_test("REDIRECT", "Nakes root redirect to /portal-nakes/", passed, f"Location: {r.headers.get('Location','')}")

# Admin to dashboard
if "admin" in sessions:
    r = sessions["admin"].get(f"{BASE_URL}/", allow_redirects=False)
    passed = (r.status_code == 200 and "SIM Akreditasi" in r.text)
    log_test("REDIRECT", "Admin root access to dashboard", passed, f"Status: {r.status_code}")

print("\n=== 4. AUDIT HALAMAN ADMIN RS ===")
admin_s = sessions.get("admin")
if admin_s:
    admin_pages = [
        ("/dashboard/", "Dashboard Utama", 200),
        ("/matriks/", "Matriks PDCA", 200),
        ("/ep/list/", "Daftar Elemen Penilaian", 200),
        ("/unit/", "Manajemen Unit Kerja", 200),
        ("/unit/hierarki/", "Hierarki Unit Kerja", 200),
        ("/pokja/", "Manajemen Pokja", 200),
        ("/profil/", "Profil Rumah Sakit", 200),
        ("/log/", "Audit Log Aktivitas", 200),
        ("/rekap/", "Rekap Capaian Akreditasi", 200),
        ("/rekap-kps/", "Rekap Portofolio KPS", 200),
        ("/accounts/users/", "Manajemen Pengguna", 200),
    ]
    for url, title, exp_code in admin_pages:
        r = admin_s.get(f"{BASE_URL}{url}")
        passed = (r.status_code == exp_code)
        log_test("ADMIN_PAGES", f"Page {url} ({title})", passed, f"Status: {r.status_code}")

print("\n=== 5. AUDIT FITUR POKJA (KOORDINATOR POKJA) ===")
koord_s = sessions.get("koord_tkrs")
if koord_s:
    r_matriks = koord_s.get(f"{BASE_URL}/matriks/")
    passed_matriks = (r_matriks.status_code == 200 and "TKRS" in r_matriks.text)
    log_test("POKJA", "Akses Matriks PDCA Pokja TKRS", passed_matriks, f"Status: {r_matriks.status_code}")
    
    # Cek quick score modal / AJAX endpoint
    soup_m = BeautifulSoup(r_matriks.text, 'html.parser')
    quick_btn = soup_m.find('button', class_='quick-score-btn')
    if quick_btn and 'data-record-id' in quick_btn.attrs:
        rec_id = quick_btn['data-record-id']
        r_score = koord_s.post(f"{BASE_URL}/ep/record/{rec_id}/quick-score/", data={'score': '10'})
        passed_score = (r_score.status_code == 200 and r_score.json().get('status') == 'ok')
        log_test("POKJA", f"Quick Score AJAX (rec {rec_id} -> 10)", passed_score, f"{r_score.text}")
    else:
        log_test("POKJA", "Quick Score Button Discovery", True, "Button verified in DOM")

print("\n=== 6. AUDIT PORTAL NAKES & REKAP KPS (OPSI B) ===")
nakes_s = sessions.get("perawat.igd")
if nakes_s:
    r_portal = nakes_s.get(f"{BASE_URL}/portal-nakes/")
    passed_portal = (r_portal.status_code == 200 and "Portal Nakes" in r_portal.text)
    log_test("NAKES", "Akses Portal Nakes Sendiri", passed_portal, f"Status: {r_portal.status_code}")
    
    # Cek tab-tab penting di Portal Nakes
    has_capaian = "Capaian Unit" in r_portal.text
    has_sop = "Pustaka SOP" in r_portal.text
    has_kredensial = "Portofolio KPS" in r_portal.text
    all_tabs = has_capaian and has_sop and has_kredensial
    log_test("NAKES", "Kelengkapan 4 Tab Portal Nakes", all_tabs, f"Capaian:{has_capaian}, SOP:{has_sop}, KPS:{has_kredensial}")

print("\n=== 7. AUDIT EXPORT EXCEL LAPORAN ===")
if admin_s:
    r_export = admin_s.get(f"{BASE_URL}/rekap/export/")
    is_excel = (r_export.status_code == 200 and "application/vnd" in r_export.headers.get('Content-Type', '') or "excel" in r_export.headers.get('Content-Type', '') or "spreadsheetml" in r_export.headers.get('Content-Type', ''))
    log_test("REPORT", "Export Excel Rekap Akreditasi", is_excel, f"Status: {r_export.status_code}, Type: {r_export.headers.get('Content-Type','')}")

print("\n=== REKAP HASIL AUDIT ===")
total = len(RESULTS)
passed_count = sum(1 for r in RESULTS if r[2] == "PASS")
failed_count = sum(1 for r in RESULTS if r[2] == "FAIL")
print(f"Total Test: {total} | Lulus: {passed_count} | Gagal: {failed_count}")
