# QA CRUD — Modul 04: Human Capital (`/human-capital/`)

Tanggal: 2026-10-27. Metode: `django.test.Client` + `force_login(monsiskami, superuser)`, DB `db.sqlite3` lokal.
Objek uji dibuat lewat form/view lalu dihapus (raw SQL, karena `Pegawai.delete()` ORM tidak bisa jalan — lihat B-1).

## Prasyarat lingkungan (temuan awal, memblokir sebagian besar uji)

| # | Temuan | Dampak |
|---|---|---|
| B-1 | Migrasi `sdm 0043_logbook_waktu_kategori_shift` dan `0044_draf_dokumen_kredensial` **belum diterapkan** (`manage.py showmigrations sdm`) | `OperationalError: no such column: sdm_entrilogbookklinis.waktu` / `.jumlah_kolaborasi`; `no such table: sdm_drafdokumenkredensial` |
| B-2 | Akibat B-1, **`Pegawai.objects.get(...).delete()` (ORM) error** — collector menyentuh tabel `sdm_drafdokumenkredensial` | Semua tombol hapus pegawai & teardown berbasis ORM gagal total |

## Tabel status per tombol

| Menu/submenu | View | Method | Status | Bukti (DB delta / redirect / error) |
|---|---|---|---|---|
| Dashboard | `dashboard` | GET | 200 | render OK; filter `?unit=` 200 |
| Pegawai (list) | `pegawai_list` | GET | 200 | 6 baris DEMO tampil; `?q=` & `?unit=` 200 |
| Pegawai — Tambah Staf | `intake_wizard` (name `pegawai_create`) | GET | 200 | `pegawai/baru/` merender wizard langkah 1 |
| Pegawai — form lama | `views.pegawai_create` | — | **TAK TERJANGKAU** | tidak ada URL mengarah ke view ini (lihat B-3) |
| Pegawai detail | `pegawai_detail` | GET | 200 | — |
| Pegawai foto | `pegawai_avatar` | GET | 404 | tanpa avatar → `Http404` (benar) |
| Pegawai edit | `pegawai_edit` | POST | 302 | nama & jabatan berubah di DB |
| Dokumen unggah | `dokumen_upload` | POST | 200 | **dokumen tidak tersimpan** — "Dokumen gagal disimpan ke penyimpanan privat" (B-4) |
| Dokumen tinjau | `dokumen_review` | POST | — | tidak diuji: tak ada dokumen tercipta (B-4) |
| Dokumen unduh | `dokumen_download` | GET | — | tidak diuji: idem |
| Wizard langkah 1 | `intake_wizard` | GET | 200 | form OK |
| Wizard langkah 2–5 | `intake_wizard` | GET | **500** | `NoReverseMatch: pegawai_wizard_resume ... draft_id=''` (B-5) |
| Wizard simpan langkah 1–5 | `intake_wizard` | POST | 302 | draft v1→v5, `draft_data` keys 1..5 bertambah |
| Wizard resume draf | `pegawai_wizard_resume` | GET | 200 | draf dengan UUID valid OK |
| Wizard finalize | `intake_finalize` | POST | 302 | pegawai count 7→8, draf `state=FINALIZED` |
| Impor unggah | `import_upload` | POST | 302 | batch dibuat → redirect preview |
| Impor template | `import_template` | GET | 200 | xlsx terunduh |
| Impor preview | `import_preview` | GET | 200 | — |
| Impor terapkan | `import_apply` | POST | 302 | pegawai 8→9, `QA-IMP-0001` ada |
| Impor hasil | `import_result` | GET | 200 | — |
| Formasi list | `formasi_list` | GET | 200 | — |
| Formasi peta | `formasi_peta` | GET | 200 | — |
| Formasi baru (form) | `formasi_create` | GET | 200 | — |
| Formasi baru (simpan) | `formasi_create` | POST | 200 | **tidak tersimpan**: "Rencana formasi tidak ditemukan." (B-6) |
| Formasi aktivitas | `formasi_add_activity` | POST | — | diblokir B-6 |
| Formasi ajukan | `formasi_submit` | POST | — | diblokir B-6 |
| Formasi setujui | `formasi_approve` | POST | — | diblokir B-6 |
| Rekrutmen list | `rekrutmen_list` | GET | 200 | — |
| Rekrutmen baru | `rekrutmen_create` | POST | 302 | lowongan dibuat |
| Rekrutmen detail | `rekrutmen_detail` | GET | 200 | — |
| Rekrutmen lamaran | `rekrutmen_add_application` | POST | 302 | lamaran=1 |
| Rekrutmen tahap | `rekrutmen_move` | POST | 302 | `MASUK`→`SELEKSI_ADMIN` |
| Kredensial landing | `kredensial_list` | GET | 200 | — |
| Kredensial katalog | `kredensial_katalog` | GET | 200 | — |
| Kredensial pengajuan | `kredensial_daftar_pengajuan` | GET | 200 | — |
| Kredensial SPK | `kredensial_spk_list` | GET | 200 | — |
| Kredensial akses-rme | `kredensial_akses_rme` | GET | 200 | — |
| Kredensial peta | `kredensial_peta` | GET | 200 | — |
| Kredensial pengajuan-saya (HC) | `kredensial_pengajuan_sendiri` | GET | 302→`/` | superuser tak tertaut pegawai → redirect (benar) |
| Kredensial baru (form) | `kredensial_create` | GET | 200 | — |
| Kredensial baru (simpan) | `kredensial_create` | POST | 302 | objek tercipta |
| Kredensial detail | `kredensial_detail` | GET | **500** | `OperationalError no such column sdm_entrilogbookklinis.jumlah_kolaborasi` (B-1) |
| Kredensial bestari | `kredensial_panel_bestari` | GET | 200 | — |
| Kredensial kewenangan | `kredensial_add_privilege` | POST | 302 | RincianKewenangan=1 |
| Kredensial PSV | `kredensial_psv` | POST | 302 | — |
| Kredensial putuskan | `kredensial_decide` | POST | 302 | status→`DISETUJUI` |
| Kredensial rekomendasikan | `kredensial_rekomendasikan` | POST | 302 | — |
| Kredensial terbitkan SPK | `kredensial_terbitkan_spk` | POST | 302 | `PenugasanKlinis` tercipta |
| Kredensial bukti-audit | `kredensial_bukti_audit` | GET | 200 | — |
| Kredensial tahap | `kredensial_tahap` | POST | 302 | — |
| Kredensial berita-acara | `kredensial_berita_acara_rapat` | GET | 200 | — |
| Kredensial syarat tautkan | `kredensial_syarat_tautkan` | POST | **500** | `ValueError: Field 'id' expected a number but got ''` (B-7) |
| Kredensial syarat unggah | `kredensial_syarat_upload` | POST | 302 | baris→`TERPENUHI`, version tertaut (unggah berhasil lewat jalur ini) |
| Kredensial cetak SPK | `kredensial_cetak_spk` | GET | 200 | — |
| Kredensial cetak RKK | `kredensial_cetak_rkk` | GET | 200 | — |
| Kredensial cabut SPK | `kredensial_cabut_spk` | POST | 302 | `is_active=False` |
| Kredensial bukti-starkes | `kredensial_bukti_starkes` | GET | 200 | — |
| Orientasi list | `orientasi_list` | GET | 200 | — |
| Orientasi baru (program) | `orientasi_create` | POST | 302 | ProgramOrientasi tercipta |
| Orientasi baru (assign) | `orientasi_create` | POST | 302 | penugasan tercipta (butuh ≥1 aktivitas) |
| Orientasi detail | `orientasi_detail` | GET | 200 | — |
| Orientasi selesai | `orientasi_complete` | POST | 302 | `selesai=True` |
| Kinerja list | `kinerja_list` | GET | 200 | kosong (DB tak punya data) |
| Kinerja finalkan | `kinerja_finalize` | POST | SKIP | tidak ada `PenilaianKinerja`/`PeriodeKinerja`; seed butuh periode |
| Diklat list | `diklat_list` | GET | 200 | — |
| Diklat baru | `diklat_create` | POST | 302 | KebutuhanPelatihan 0→1 |
| Diklat sertifikat | `diklat_certificate` | POST | SKIP | tak ada `PesertaDiklat` |
| K3 list | `k3_list` | GET | 200 | (butuh grant `hc_health_write` — data, bukan kode) |
| K3 lapor | `k3_report` | POST | 302 | insiden tertambah |
| K3 lapor | `k3_report` | GET | 405 | `require_POST` (benar) |
| K3 imunisasi tambah | `k3_imunisasi_tambah` | GET | 200 | — |
| K3 imunisasi tambah | `k3_imunisasi_tambah` | POST | **500** | `RelatedObjectDoesNotExist: ImunisasiPegawai has no employee` (B-8) |
| K3 MCU tambah | `k3_mcu_tambah` | GET | 200 | — |
| K3 MCU tambah | `k3_mcu_tambah` | POST | **500** | `RelatedObjectDoesNotExist: PemeriksaanKesehatanKerja has no employee` (B-8) |
| K3 insiden tambah | `k3_insiden_tambah` | POST | 302 | insiden 0→1 |
| K3 tindak lanjut | `k3_tindak_lanjut_tambah` | POST | 302 | followup 0→1 |
| Portal index | `portal_index` | GET | 200 | 200 saat grant di-scope ke unit pegawai; 403 saat grant unit lain (data, bukan kode) |
| Portal ajukan | `portal_request_create` | POST | 302 | LayananMandiri 0→1 (dengan grant tepat) |
| Portal batal | `portal_request_cancel` | POST | 302 | `state=CANCELLED` |
| Portal pengajuan-saya | `kredensial_pengajuan_sendiri` | GET | **500** | `OperationalError sdm_entrilogbookklinis.jumlah_kolaborasi` (B-1) |
| Portal ubah pengajuan | `kredensial_pengajuan_ubah` | POST | 302 | `jenis=REKREDENSIAL` |
| Portal unggah dokumen | `portal_dokumen_upload` | POST | 302 | dokumen CV tersimpan |
| Logbook list | `logbook_list` | GET | **500** | `OperationalError no such column sdm_entrilogbookklinis.waktu` (B-1) |
| Logbook baru | `logbook_create` | POST | 302 | **entri tidak tersimpan** (0→0), tertelan B-1 |
| Logbook ubah/hapus | `logbook_edit`/`logbook_delete` | POST | SKIP | tak ada entri |
| Analitik | `analitik_dashboard` | GET | 200 | — |
| Analitik ekspor | `analitik_export` | GET | 200 | xlsx |
| Analitik ekspor PDF | `analitik_export_pdf` | GET | 200 | pdf |
| KPS paket | `kps_report` | GET | 302 | tanpa `framework` → redirect (benar) |
| KPS preview | `kps_pack_preview` | GET | 302 | tanpa artefak sesi → redirect (benar) |
| KPS publish | `kps_pack_publish` | POST | 403/redirect | tanpa artefak → PermissionDenied (benar) |

## Bug

### LEVEL1 (500 / exception / CRUD tidak berfungsi)

- **B-1** Migrasi belum diterapkan → 3 halaman 500 + logbook tak bisa menulis.
  `manage.py showmigrations sdm` → `[ ] 0043_logbook_waktu_kategori_shift`, `[ ] 0044_draf_dokumen_kredensial`.
  Root: status repositori/migrasi (`sdm/migrations/0043_*.py`, `0044_*.py` belum di-apply ke `db.sqlite3`).
- **B-2** `Pegawai.delete()` gagal: `OperationalError: no such table: sdm_drafdokumenkredensial`.
  Root: `sdm/models/kredensial.py:389` (`DrafDokumenKredensial` FK `on_delete=PROTECT`) + migrasi 0044 belum ada. Konsekuensi B-1.
- **B-3** View `views.pegawai_create` (`sdm/views.py:228`) **tidak terjangkau**: `sdm/urls.py:19` memetakan `pegawai/baru/` → `intake_views.intake_wizard`, dan nama `pegawai_create` juga milik wizard. Form tambah pegawai lama = kode mati.
- **B-5** Wizard langkah 2–5 GET → 500 `NoReverseMatch` untuk `draft_id=''`.
  Root: `templates/sdm/pegawai/wizard.html:118` — `{% url 'sdm:pegawai_wizard_resume' step=prev_step draft_id=draft.pk %}` dievaluasi walau `draft is None` (langkah dibuka langsung tanpa draf).
- **B-6** Formasi baru tidak pernah tersimpan: POST → 200 + "Rencana formasi tidak ditemukan."
  Root: `sdm/services/formasi.py:28` `if plan.pk:` — `RencanaFormasi.id` punya `default=uuid.uuid4` (`sdm/models/formasi.py:31`), jadi `plan.pk` sudah terisi sebelum `save()`, lalu query "existing" mengembalikan `None` dan melempar `ValidationError`.
- **B-7** `kredensial_syarat_tautkan` → 500 `ValueError: Field 'id' expected a number but got ''`.
  Root: `sdm/views.py:1259-1262` — `VersiDokumen.objects.filter(pk=request.POST.get('document_version') or '', ...)`; string kosong diteruskan sebagai `pk`.
- **B-8** K3 imunisasi & MCU tambah → 500 `RelatedObjectDoesNotExist: ... has no employee`.
  Root: `sdm/forms/k3.py:33-44` (`ImunisasiPegawaiForm.fields` tanpa `employee`) dan `sdm/forms/k3.py:17-32` (`PemeriksaanKesehatanKerjaForm` idem); view `sdm/views.py:1623-1635` lalu memakai `immunization.employee` (dan `sdm/views.py:1645-1655` `exam.employee`). Form tidak pernah bisa menyimpan → fitur mati.

### LEVEL2 (permission/CSRF/redirect/ tombol hilang)

- **B-4** `dokumen_upload` gagal simpan: "Dokumen gagal disimpan ke penyimpanan privat."
  Root: `sdm/views.py:424-431` menangkap `PrivateStorageError` dari `store_private_document`; backend `SupabasePrivateStorage` (`sdm/storage_backend.py:25`) butuh kredensial Supabase yang tak ada di env lokal. Perilaku aman (tidak mencatat metadata), tetapi tombol unggah dokumen kepegawaian praktis tidak berfungsi di dev/test.
- **B-9** `logbook_create` menelan kegagalan: tanpa B-1 pun, `sdm/views.py:2342-2382` hanya `messages.error` lalu redirect ke `logbook_list` (yang 500). Tidak ada umpan balik yang bisa dibaca pengguna.
- **B-10** Tombol "Tambah Pegawai" di `templates/sdm/pegawai/list.html:15` mengarah ke `sdm:pegawai_create` = wizard, bukan form `views.pegawai_create`. Konsisten dengan B-3, tetapi UI menyebut dua alur berbeda dengan satu tautan.

### LEVEL3 (UX/label)

- **B-11** `database_tambah_staf` (`sdm/navigation.py:131`) berlabel "Tambah Staf" → membuka wizard 5 langkah, sementara `views.pegawai_form` menyediakan form tunggal; istilah ganda membingungkan.
- **B-12** `k3_report` GET → 405 tanpa halaman penjelas; menu "Lapor" perlu formulir (`k3/insiden/tambah/`) agar tidak menyesatkan.

## Command reproduksi

```bash
cd /c/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django

# B-1
.venv/Scripts/python.exe manage.py showmigrations sdm | tail -3

# B-5 / B-3 / B-6 / B-7 / B-8 (satu skrip, lihat .qa_tmp/crud04/probe.py)
.venv/Scripts/python.exe .qa_tmp/crud04/probe.py

# B-6 minimal
.venv/Scripts/python.exe - <<'EOF'
import os,sys,django;sys.path.insert(0,'.');os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from sdm.models import RencanaFormasi
p=RencanaFormasi(profesi='X')
print('pk terisi sebelum save:', p.pk)   # B-6
EOF

# B-8 minimal
.venv/Scripts/python.exe - <<'EOF'
import os,sys,django;sys.path.insert(0,'.');os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from sdm.models import HcGrant
u=get_user_model().objects.get(username='monsiskami')
g=HcGrant.objects.create(user=u,capability='hc_health_write',granted_by=u)
c=Client(); c.force_login(u)
try: c.post('/human-capital/k3/imunisasi/tambah/',{'jenis':'X','dosis_ke':'1','tanggal':'2026-01-01'})
except Exception as e: print(type(e).__name__, e)
g.delete()
EOF

# B-2
.venv/Scripts/python.exe - <<'EOF'
import os,sys,django;sys.path.insert(0,'.');os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from sdm.models import Pegawai
try: Pegawai.objects.first().delete()
except Exception as e: print(type(e).__name__, e)
EOF
```

## Catatan metodologi

- Data `HcGrant` untuk `unitcheck` menunjuk unit `DBG-1` (fixture probe modul lain) sementara pegawainya di `RUANG-OK`; karena itu portal 403 pada run utama, dan 200 setelah grant di-scope ke `RUANG-OK`. Bukan bug kode.
- `hc_health_write` tidak ada di data grant `monsiskami`; probe menambah grant sementara lalu menghapusnya di akhir run.
- Skip yang sah: `kinerja_finalize` dan `diklat_certificate` — DB tidak punya `PeriodeKinerja`/`PesertaDiklat`, dan seed buatan probe butuh periode induk yang tidak tersedia.
