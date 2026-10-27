# QA CRUD — Modul 01: Akreditasi Inti (EP / PDCA / Unit / Bukti)

Tanggal uji: 2026-10-27 · DB: `db.sqlite3` lokal · Auth: `django.test.Client` + `force_login`
User: `monsiskami` (SUPER_ADMIN), plus `probe2`(ASESOR), `probe3`(ADMIN_RS), `ka.depo.rajal`(KEPALA_UNIT), `koordinator.mutu`(KOORDINATOR_POKJA), `staf.sdm`(STAF_NAKES)

Skrip uji: `.qa_tmp/crud01/crud01.py` (throwaway, tidak masuk repo), RBAC: `.qa_tmp/crud01/rbac.py`.

## 1. Tabel hasil per tombol

| Menu/submenu | View | Method | Status | Bukti (DB delta / redirect / error) |
|---|---|---|---|---|
| EP list | `ep_list` | GET | 200 | len=231.240 |
| EP list (filter q) | `ep_list` | GET | 200 | len=159.125 |
| EP list (filter unit) | `ep_list` | GET | 200 | len=111.867 |
| Matriks PDCA | `matriks_pdca` | GET | 200 | len=324.928 |
| Matriks PDCA `?cat=1` | `matriks_pdca` | GET | 200 | len=324.928 |
| EP create (form) | `ep_create` | GET | 200 | len=75.800 |
| EP create | `ep_create` | POST | 200 (302→`/matriks/?cat=N`) | count 301→302; EvidenceReq 2 baris tercipta; OK |
| EP create (kode duplikat) | `ep_create` | POST | 200 | count tetap; form error tampil; OK |
| EP create (field wajib kosong) | `ep_create` | POST | 200 | count tetap; form error tampil; OK |
| EP create (payload kosong) | `ep_create` | POST | 200 | len=77.849; tidak 500; OK |
| EP edit (form) | `ep_edit` | GET | 200 | len=78.558 |
| EP edit | `ep_edit` | POST | 200 (302→`/matriks/?cat=N`) | `sub_title` berubah, `score`→5, `est_cost`→1500000.00; OK |
| EP detail | `ep_detail` | GET | 200 | len=60.635 |
| EP delete | `ep_delete` | POST | 200 (302→`/matriks/?cat=N`) | count 302→301; row hilang; OK |
| EP delete | `ep_delete` | GET | 405 | `require_POST`; OK |
| Quick score 10 | `quick_score` | POST | 200 | `{"success":true,...}`; db_score=10 |
| Quick score 7 (invalid) | `quick_score` | POST | 400 | `{"success":false,"error":"Invalid score"}`; db tetap |
| Quick score `"abc"` | `quick_score` | POST | **500** | `ValueError: invalid literal int() base 10: 'abc'` → ditangkap `except` jadi `{"success":false,"error":"Terjadi kesalahan internal."}` |
| Quick score 5 | `quick_score` | POST | 200 | db_score=5 |
| Quick score | `quick_score` | GET | 405 | `require_POST`; OK |
| Quick score (record invalid) | `quick_score` | POST | 404 | OK |
| Inline edit `quality_target` | `inline_edit_pdca` | POST | 200 | db="TARGET INLINE" |
| Inline edit `est_cost`="2.500.000" | `inline_edit_pdca` | POST | **500** | `TypeError: 'decimal.Decimal' object not subscriptable` (views.py:873); DB **terlanjur** tersimpan 2500000.00 |
| Inline edit `est_cost`="abc" | `inline_edit_pdca` | POST | **500** | `TypeError` sama; DB terlanjur 0.00 |
| Inline edit `score` (bukan field allowed) | `inline_edit_pdca` | POST | 400 | `{"success":false,"error":"Field tidak diizinkan"}`; OK |
| Inline edit `bogus` | `inline_edit_pdca` | POST | 400 | OK |
| Inline edit `action_plan` + pic + est_cost | `inline_edit_pdca` | POST | 200 | db="RTL batch" |
| Inline edit body bukan JSON | `inline_edit_pdca` | POST | **500** | `JSONDecodeError` → "Terjadi kesalahan internal." |
| Modal bukti data | `modal_bukti_data` | GET | 200 | keys `item_code,item_desc,reqs,linked_files,repo_files` |
| Upload bukti AJAX | `upload_bukti_ajax` | POST | 200 | count 0→1; `{"success":true,"file_id":…}` |
| Upload AJAX tanpa file | `upload_bukti_ajax` | POST | 400 | `{"success":false,"error":"Tidak ada berkas yang diunggah."}` |
| Upload AJAX `.exe` | `upload_bukti_ajax` | POST | 400 | `{"error":"Tipe berkas '.exe' dilarang…"}`; count tidak berubah |
| Upload bukti (form) GET | `upload_bukti` | GET | 200 | len=56.111 |
| Upload bukti (form) POST | `upload_bukti` | POST | 302→`/ep/<id>/detail/` | count 1→2; OK |
| Upload form `.exe` | `upload_bukti` | POST | 302 | count tetap (ditolak); pesan error redirect |
| Link dokumen | `link_existing_doc` | POST | 200 | count 2→3; `{"success":true}` |
| Link req_id invalid | `link_existing_doc` | POST | **500** | `EvidenceReq.DoesNotExist` → `{"error":"Gagal menautkan berkas bukti."}` |
| Link file_id invalid | `link_existing_doc` | POST | **500** | `EvidenceFile.DoesNotExist` → sama |
| Link body bukan JSON | `link_existing_doc` | POST | **500** | `JSONDecodeError` → sama |
| Unlink dokumen | `unlink_doc` | POST | 200 | count 3→2→1; `{"success":true}` |
| Unlink id invalid | `unlink_doc` | POST | 404 | OK |
| Unit list | `unit_list_create` | GET | 200 | len=488.020 |
| Unit hierarki | `unit_tree` | GET | 200 | len=662.552 |
| Unit create | `unit_list_create` | POST | 302→`/unit/` | count 156→157 |
| Unit create (kode duplikat) | `unit_list_create` | POST | 200 | count tetap; error message |
| Unit edit | `unit_edit` | POST | 302→`/unit/` | `name` & `pic_name` berubah |
| Unit delete (punya anak) | `unit_delete` | POST | 302→`/unit/hierarki/` | unit **tidak** terhapus; guard bekerja |
| Unit delete (punya record PDCA) | `unit_delete` | POST | 302→`/unit/hierarki/` | unit **tidak** terhapus; guard bekerja |
| Unit delete (bersih) | `unit_delete` | POST | **EXC / 500** | `OperationalError: no such column: sdm_entrilogbookklinis.waktu` |
| Pokja | `pokja_manage` | GET | 200 | len=77.448; view read-only (tidak ada form) |
| Profil RS | `profil_rs_view` | GET | 200 | len=74.181 |
| Profil RS update | `profil_rs_view` | POST | 302→`/profil/` | `name` berubah |
| Profil RS `akreditasi_tahun` non-angka | `profil_rs_view` | POST | **EXC / 500** | `ValueError: invalid literal int() base 10: 'bukan-angka'` |
| Dokumen hub | `dokumen_hub` | GET | 200 | len=54.839 |
| Rekap | `rekap_view` | GET | 200 | len=520.905 |
| Rekap scoring | `auto_scoring_pokja` | GET | 200 | len=85.432 |
| Rekap cetak | `cetak_dokumen_pokja` | GET | 200 | len=87.595 |
| Rekap export | `export_excel` | GET | 200 | Content-Type xlsx, 25.370 B |

### RBAC (GET)

| Role | ep/baru | ep/*/edit | unit/ | pokja/ | profil/ | rekap/ | scoring/ | export/ | cetak/ |
|---|---|---|---|---|---|---|---|---|---|
| SUPER_ADMIN | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| ADMIN_RS | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 |
| KEPALA_UNIT | 200 | 200 | 302 | 302 | 302 | 200 | 200 | 200 | 200 |
| KOORDINATOR_POKJA | 200 | 200 | 302 | 302 | 302 | 200 | 200 | 200 | 200 |
| STAF_NAKES | 302 | 302 | 302 | 302 | 302 | 403 | 403 | 403 | 200 |
| ASESOR | 302 | 302 | 302 | 302 | 302 | 403 | 403 | 403 | 200 |

Catatan: `cetak/<cat_id>/` tetap 200 untuk ASESOR dan STAF_NAKES — tidak ada RBAC di `cetak_dokumen_pokja` (views.py:1595).

## 2. Daftar bug

### LEVEL1 — 500 / exception / CRUD tidak berfungsi

1. **`inline_edit_pdca` → TypeError 500 untuk field `est_cost`.**
   `views.py:873` `detail=f"... {value[:80]}"` — `value` sudah diganti objek `Decimal` di baris 848, sehingga slicing gagal. Data **sudah tersimpan** ke DB sebelum exception, jadi klien menerima 500 padahal perubahan berhasil (tidak konsisten).

2. **`inline_edit_pdca` → 500 untuk body non-JSON.** `json.loads` melempar `JSONDecodeError` (subclass `ValueError`) lalu ditangkap `except` → 500. Untuk AJAX seharusnya 400.

3. **`link_existing_doc` → 500 untuk id tidak valid.** `get_object_or_404` di dalam `try` (views.py:978-989) memunculkan `Http404` lalu ditangkap `except Exception` → dibalas JSON 500. Seharusnya 404.

4. **`link_existing_doc` → 500 untuk body non-JSON.** Sama, `json.loads` di dalam `try`.

5. **`quick_score` dengan skor non-angka → 500.** `int(data.get('score', 0))` di views.py:800 tidak divalidasi; `"abc"` → `ValueError` → 500.

6. **`profil_rs_view` → 500 bila `akreditasi_tahun` bukan angka.** views.py:1508 `int(...)` tanpa try. Payload dari form HTML normal aman, tapi nilai non-numerik (mis. form dimanipulasi / input kosong-tidak) memicu 500.

7. **`unit_delete` → 500 `OperationalError: no such column: sdm_entrilogbookklinis.waktu`.**
   Root cause: migrasi `sdm.0043_logbook_waktu_kategori_shift` dan `0044_draf_dokumen_kredensial` **belum diterapkan** pada `db.sqlite3` lokal (`manage.py showmigrations sdm` menampilkan `[ ]`), sementara model `sdm.EntriLogbookKlinis` sudah punya `waktu/kategori/shift/pasien_ref/jumlah_kolaborasi`. Django deletion collector men-SELECT tabel tersebut saat menghapus `UnitKerja` → `OperationalError`. Tabel berisi 0 baris, tetap gagal. Ini murni drift environment DB, bukan bug kode `akreditasi`; namun tombol hapus unit **tidak berfungsi** di DB ini.

### LEVEL2 — CSRF / permission / redirect salah / tombol hilang

8. **Tombol hapus EP tidak ada di UI mana pun.** `ep_delete` (+ `require_POST`) terdaftar di `akreditasi/urls.py:31` dan berfungsi, tetapi tidak ada satu pun `{% url 'akreditasi:ep_delete' %}` di `templates/`. Pengguna tidak bisa menghapus EP dari antarmuka (padahal `views.py:1307` menyediakan fitur).

9. **Tidak ada tombol hapus unit di `/unit/` (`unit_form.html`).** Form hapus unit hanya ada di `unit_tree.html` (baris 238/267/289/308/325, level 1-5 lengkap). Halaman `/unit/` yang menjadi tujuan setelah create/edit tidak menyediakan aksi hapus, sehingga navigasi tidak konsisten.

10. **`unlink_doc` adalah DELETE data, bukan "unlink".** `views.py:1023` memanggil `ev_file.delete()` — berkas bukti hilang permanen dari DB. Komentar UI di `_matriks_pdca_js.html:309` menyatakan *"Berkas tetap tersimpan di repositori"*, dan `link_existing_doc` sendiri mengkloning baris `EvidenceFile`. Jadi tombol "lepas tautan" menghapus record asli (termasuk bila record itu sumber tautan). Label/tooltip menyesatkan.

11. **`link_existing_doc` tidak punya guard IDOR.** `views.py:977-1008`: tidak ada `_can_modify_ep` untuk `target_req` maupun `source_file`, berbeda dengan `upload_bukti_ajax`/`unlink_doc`/`quick_score` yang punya. User ber-unit-scope bisa menautkan dokumen EP di luar cakupannya.

12. **`cetak_dokumen_pokja` tanpa RBAC.** views.py:1595-1611 hanya `@login_required`; ASESOR & STAF_NAKES tetap 200, sementara `rekap_view`/`auto_scoring_pokja`/`export_excel` menolak role yang sama (403). Inkonsistensi kebijakan.

### LEVEL3 — UX / label

13. `_can_edit` memberi izin edit EP ke `KEPALA_UNIT` dan `KOORDINATOR_POKJA` (`can_edit=True`), tetapi batas unit baru dicek di `quick_score`/`inline_edit`/`upload`/`unlink`, **tidak** di `ep_edit`/`ep_delete`. Jadi user unit-scoped bisa mengubah/menghapus EP milik pokja lain via form penuh.

14. Form EP memaksa `budget_status` terisi (`QualityRecordForm` tidak menetapkan `blank=True`/default di form), padahal model punya `default='DRAFT'`. Payload POST tanpa field itu → form invalid tanpa pesan jelas di UI (harus baca error list).

## 3. Root cause file:line

| Bug | Lokasi |
|---|---|
| 1 Decimal slicing | `akreditasi/views.py:873` (value diubah jadi `Decimal` di `:848`, `:862`) |
| 2 inline edit non-JSON | `akreditasi/views.py:840` + `:877` |
| 3 link 404→500 | `akreditasi/views.py:981-982` + `:1006` |
| 4 link non-JSON | `akreditasi/views.py:979` + `:1006` |
| 5 quick score non-angka | `akreditasi/views.py:800` |
| 6 profil tahun non-angka | `akreditasi/views.py:1508` |
| 7 unit delete 500 | migrasi belum jalan: `sdm/migrations/0043_logbook_waktu_kategori_shift.py`, `0044_draf_dokumen_kredensial.py`; kegagalan di `akreditasi/views.py:1472` (`unit.delete()`) |
| 8 tombol hapus EP hilang | `akreditasi/urls.py:31` (view ada) vs `templates/akreditasi/ep_list.html`, `matriks_pdca.html`, `ep_detail.html` (tidak ada `ep_delete`) |
| 9 tombol hapus unit tak ada di `/unit/` | `templates/akreditasi/unit_form.html` (tanpa `unit_delete`) |
| 10 unlink = delete | `akreditasi/views.py:1023`; klaim UI `templates/akreditasi/_matriks_pdca_js.html:309` |
| 11 link tanpa IDOR guard | `akreditasi/views.py:977-1008` |
| 12 cetak tanpa RBAC | `akreditasi/views.py:1594-1611` |
| 13 ep_edit/ep_delete tanpa cek cakupan unit | `akreditasi/views.py:1189-1227`, `:1307-1326` |
| 14 budget_status wajib | `akreditasi/forms.py:114-127` |

## 4. Command reproduksi

```powershell
# dari root proyek, venv aktif
.venv\Scripts\python.exe .qa_tmp\crud01\crud01.py    # suite CRUD + AJAX
.venv\Scripts\python.exe .qa_tmp\crud01\rbac.py      # matriks RBAC per role

# bug 7 (unit delete 500) — cek drift DB
.venv\Scripts\python.exe manage.py showmigrations sdm   # [ ] 0043, [ ] 0044
# perbaikan (di luar lingkup QA, jangan dijalankan tanpa persetujuan):
# .venv\Scripts\python.exe manage.py migrate sdm

# bug 1/2 — inline edit est_cost
# POST /ep/record/<id>/inline-edit/  body {"field":"est_cost","value":"2.500.000"}
#   -> 500, DB tetap berubah

# bug 3/4 — link
# POST /ep/bukti/link/ body {"req_id":999999,"file_id":1}  -> 500 (seharusnya 404)

# bug 5 — quick score
# POST /ep/record/<id>/quick-score/ body {"score":"abc"}   -> 500

# bug 6 — profil
# POST /profil/ data name=&akreditasi_tahun=bukan-angka    -> 500
```

## 5. Catatan integritas data

Saat uji awal, satu EP fixture nyata (`StandardItem` id=1, `TKRS 1 EP 1`) terhapus oleh probe RBAC. Sudah **dipulihkan** dari `db.sqlite3.bak-pre-seed-20261023-175321` (baris `akreditasi_standarditem` id=1, `akreditasi_qualityrecord` id=1, 2 `akreditasi_evidencereq` id=1-2). Nama RS (`RumahSakitProfile`) yang sempat tertimpa "QA RS Test" juga sudah dikembalikan ke "RS MonsisKami". Verifikasi akhir: `standarditem=301`, `qualityrecord=301`, `unitkerja=156`, `qualityrecord` orphan=0, `evidencefile=0`, `evidencereq=2`. Skrip sudah diperbaiki agar probe RBAC memakai EP throwaway.

Objek uji buatan sendiri (unit `QA-*`, EP `QA-*`, `EvidenceFile`, `EvidenceReq` auto) dihapus lewat raw SQL karena ORM delete menabrak drift `sdm` (bug 7).
