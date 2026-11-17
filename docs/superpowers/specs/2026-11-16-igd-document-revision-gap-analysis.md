# Analisis Revisi Diagnosis, Rencana Tindakan/Obat, dan Penunjang IGD ARima

**Tanggal:** 16 November 2026.
**Status:** Analisis dan usulan plan untuk review. Tidak ada implementasi aplikasi, migrasi operasional, impor/aktivasi master, commit, push, atau deployment pada pekerjaan ini.
**Repository:** `C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django`.
**Baseline:** branch `master`, HEAD `f2583ea936dc1d00669ae16b5228880d0e6b5a29`.

## 1. Kesimpulan utama

Permintaan ini adalah **revisi dan penyelesaian integrasi**, bukan pembuatan modul diagnosis/farmasi/penunjang dari nol. Commit `a8d47d9` sudah memuat clinical expansion dan `7228911` sudah mengintegrasikan professional care/CPPT/billing. Kode yang ada menjadi fondasi; instruksi pembuatan file/model pada plan lama tidak dijalankan ulang.

Dokumen baru menegaskan bahwa bagian Langkah 8 lama **diganti**, bukan ditambah di bawahnya. Kode sekarang masih menampilkan input `Resusitasi / Stabilisasi` dan `Terapi Farmakologi IGD` di awal Langkah 8, kemudian keperawatan, baru diagnosis medis dan panel rencana. Karena itu keberadaan modul baru belum memenuhi urutan/penggantian yang diminta.

Rekomendasi arsitektur: satu layar Langkah 8 dengan urutan **Diagnosis Medis → Rencana Tindakan / Rencana Terapi-Obat → Keperawatan**, memakai service, data dan transaksi yang sudah ada. Pelaksanaan nyata, pelaksana, waktu aktual, CPPT dan posting biaya tetap dikelola Langkah 9. Langkah 7 tetap pemilik order/hasil penunjang.

## 2. Identitas sumber dan perubahan yang benar-benar ditemukan

Kedua DOCX dibaca penuh, termasuk tabel. Referensi baris adalah hasil ekstraksi teks, bukan halaman Word. Gambar tertanam pada dokumen revisi juga diperiksa.

| Sumber | SHA-256 | Hasil pembandingan |
|---|---|---|
| `C:/Users/cubeb/Downloads/Pemeriksaan Penunjang untuk aplikasi ARima dengan alur cascading dropdown.docx` | `a42f2b704625b6ff187bce787090909dd3bb0da1c6cfe7b9614c8a6c0433c69f` | Identik dengan sumber penunjang yang dianalisis 13 November; tidak perlu parser/katalog duplikat |
| `C:/Users/cubeb/Downloads/perubahan sebagai pengganti yang sudah ada, penetapan diagnosa medis dan rencana tindakan klinis dan obat.docx` | `b0343c464ab04f157929dec1fb8d1cfd2ae85e4a029187ad38728021293f4c68` | Revisi nyata terhadap sumber diagnosis/tindakan/obat lama |
| Sumber historis pembanding: `Tambahkan diagnosa medis tindakan klinis dan obat.docx` | `606835a388b009c9d123e22e13f9f6c26f0ed02fb51d9aee1928c0adb664bf4f` | Sumber fixture medication saat ini; provenance asli tidak diganti dengan hash dokumen revisi |

Diff teks sumber lama dengan revisi menunjukkan perubahan berikut:

| Perubahan revisi | Dampak implementasi |
|---|---|
| “sebagai pengganti yang sudah ada. Gunakan yang ini saja” | Ganti active input surface, jangan menambah kartu baru sambil mempertahankan editor lama |
| “Hilangkan; resusitasi/stabilisasi dan terapi farmakologi IGD” | Hapus dua kontrol editable dari alur baru; simpan kolom, nilai lama, riwayat dan snapshot |
| Blok rencana dipindah dari setelah intervensi keperawatan menjadi setelah diagnosis ICD-10 | Ubah urutan DOM dan ownership form, bukan hanya label/judul |
| Master ICD-9 berdasarkan hasil kode ICD-10 | Hubungkan relasi master kasus yang sudah tersedia; tetap sediakan pencarian global dan manual jika tidak terpetakan |
| Rekomendasi diagnosis memakai asesmen langkah 1–7, termasuk lab dan penunjang | Audit konteks AI/saran agar memakai temuan bermakna, bukan sekadar keberadaan teks |
| SDKI/SLKI/SIKI didasarkan pada pengkajian sebelumnya | Pertahankan mode independen dan hubungan 3S, lengkapi konteks/saran dan uji journey |

Daftar contoh obat/kelas terapi dan spesifikasi medication safety tidak berubah pada diff. Bukan alasan menghapus lalu mengimpor ulang katalog farmasi.

**Bukti gambar:** screenshot dalam revisi memperlihatkan layar Langkah 8 dengan dua editor lama di bagian atas dan komponen SDKI/SLKI/SIKI di bawahnya. Gambar menjelaskan sasaran penggantian tampilan. Gambar sendiri tidak membuktikan izin profesi, perilaku penyimpanan, atau deployment saat ini; temuan tersebut diperiksa terpisah dari source.

## 3. Lapisan bukti: kode, schema, data, test dan deployment

### 3.1 Baseline test yang dijalankan pada pekerjaan ini

```bash
DATABASE_URL='' DJANGO_DEBUG=true PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe manage.py test pasien.tests_igd_diagnosis_lines pasien.tests_igd_target_ai pasien.tests_clinical_expansion pasien.tests_clinical_expansion_safety pasien.tests_penunjang_results pasien.tests_igd_workflow_ui --keepdb --noinput
```

**Hasil terukur:** 101 tests, `OK`, 14.162 detik waktu test Django, exit 0. Pengukuran ulang sebelum handoff juga **101 tests, `OK`, 13.095 detik, exit 0**, tanpa FAIL/ERROR. System check tidak menemukan issue, dengan satu check yang memang disilence. Ada RuntimeWarning fixture lama berupa datetime naive pada `KunjunganPasien.tanggal_masuk`.

Log awal: `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-20261116-plan-baseline.log`. Log pengukuran ulang: `C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima-20261116-plan-final-baseline.log`.

Hasil ini merupakan targeted regression pada test DB SQLite, bukan full suite, browser baru, konkurensi PostgreSQL, kualitas AI live, atau bukti deployment. Beberapa kelas mewarisi test fixture/test methods; angka koleksi bukan hitungan fitur baru atau jumlah acceptance criteria yang sudah terpenuhi.

Pemeriksaan artefak plan: keempat plan lulus `verify_plan_blocks.py` (fence balance, parsing Python dan deklarasi test module); kelima dokumen lulus pemeriksaan link lokal, file referensi existing/proposed dan placeholder. `git diff --check` lulus dan tracked source tetap tidak berubah. Pemeriksaan statis ini **bukan** eksekusi snippet test yang diusulkan atau pembuktian fitur hasil implementasi.

Audit sumber dan verifikasi di atas dikerjakan langsung. Kedua upaya audit subagent tambahan (Langkah 8 dan penunjang) gagal karena kuota provider (HTTP 503/429). Tidak ada independent review subagent yang diperoleh; kesimpulan didasarkan pada pembacaan source, probe read-only, baseline tests dan pemeriksaan artefak yang dijalankan langsung.

Interpreter project yang benar-benar diperiksa: `.venv/Scripts/python.exe`, Python 3.12.10, Django 6.1.1. `requirements.txt:4` mematok Django 6.1.2. Selisih dependency ini harus direkonsiliasi pada environment-verification sebelum eksekusi/release; tidak dilakukan install atau pengubahan dependency dalam pekerjaan planning ini.

### 3.2 Probe read-only database lokal

Database `db.sqlite3` dibuka menggunakan SQLite URI `mode=ro` dan `PRAGMA query_only=ON`; tidak menjalankan bootstrap aplikasi untuk agregat, tidak membaca identitas pasien, tidak memigrasikan DB operasional.

| App | Ledger lokal yang ditemukan | Leaf migrasi di repository |
|---|---|---|
| `pasien` | `0020_antrean_harian_counter` | `0032_professional_evidence_rls` |
| `klinis` | `0002_aturan_ep_tindakan` | `0006_professional_configuration_rls` |
| `accounts` | `0008_rolepermissionconfig_hc_calibrate_appraisals` | `0009_dental_professional_identity` |
| `sdm` | `0066_koreksilogbooktahunan` | `0067_privilege_revocation_timestamp` |

| Inventaris lokal | Temuan |
|---|---|
| ICD-10 / ICD-9 | 172 / 170 baris |
| Kelompok IGD → kasus berkode ICD-10 → relasi tindakan | 1 kelompok IGD; 15 kasus/15 ICD-10; 32 relasi tindakan |
| Tabel diagnosis terstruktur, workflow, kategori/item penunjang dan master farmasi baru | Belum tersedia pada schema lokal yang diperiksa |
| Order penunjang / header resep / detail resep | Masing-masing 0 pada SQLite lokal ini |

Implikasinya: **sumber sudah mengimplementasikan fitur tidak berarti DB lokal siap menyajikannya**. Angka nol/tabel absen di SQLite bukan bukti data produksi hilang. Jangan memulihkan seed/grant historis atau menjalankan migrasi hanya karena hasil ini. Persiapan environment dilakukan pada DB target yang dipilih eksplisit, setelah backup dan otorisasi eksekusi.

### 3.3 Artefak katalog di repository

Agregasi JSON aktual menunjukkan `penunjang_catalogue.json` berisi **38 nodes / 94 items**, dan `medication_catalogue.json` berisi **9 classes / 59 generics / 59 products**. Ini staging contoh DOCX, bukan ukuran master nasional atau layanan/produk yang sudah aktif.

`import_catalogue()` melakukan dry-run secara default dan `get_or_create` saat apply; bukan full replacement atau update seluruh baris. Aktivasi, reviewer, tujuan layanan, bentuk/kekuatan, komposisi, Fornas dan aturan PPRA tidak boleh direka dari contoh Word.

Delivery ledger 13 November mencatat bukti browser/PostgreSQL dan broad regression historis. Bukti itu berguna sebagai konteks, **tidak dinyatakan sebagai pengujian ulang pada HEAD saat ini**. Tidak ada operational/deployed readback pada pekerjaan ini.

## 4. Pemetaan kebutuhan terhadap kode dan gap

| ID | Kebutuhan/sumber | Yang sudah ada | Delta yang perlu dikerjakan | Pemilik plan |
|---|---|---|---|---|
| RV01 | Revisi baris 4–6: gunakan pengganti, hilangkan dua editor lama | Dua field masih di `STEPS[8]`; loop template merendernya | Retire editor/active draft ownership, pertahankan history/snapshot dan legacy non-workflow compatibility | Step 8 Task 1 |
| RV02 | Revisi baris 13–21: rencana tepat setelah diagnosis | Diagnosis ditampilkan setelah form utama berisi 3S; selector tindakan/obat sudah ada | Susun DOM diagnosis → rencana → keperawatan, tetap form terpisah/tidak nested | Step 8 Task 1 |
| DG01 | Manual/Master/AI dan utama/sekunder | `DiagnosisKunjungan`, primary constraint, audit, replay dan controls | Reuse; rapikan segmented controls, autocomplete kode/nama dan regression pada layar pengganti | Step 8 Tasks 1–2 |
| DG02 | Diagnosis dari data klinis langkah 1–7 | Target AI memakai vital/triase dan term extraction dari sebagian field | Konteks berprovenance mempertahankan negasi/nilai klinis, riwayat relevan dan hasil selesai; bukan hanya irisan keyword | Step 8 Task 3 |
| AC01 | Master ICD-9 berdasarkan ICD-10 | Relasi `KasusTersering.icd10 → KasusTindakan.icd9` sudah terisi; autocomplete ICD-9 masih umum | Lookup diagnosis aktif milik episode, scope kelompok, fallback manual/global | Step 8 Task 2 |
| AC02 | Manual/Master/AI, lokasi/keterangan/quantity, pelaksana/waktu | `plan_action`; target procedure AI; Step 9 professional execution | Pertahankan transaksi; bedakan rencana vs pelaksanaan aktual dan tautkan journey | Step 8 Tasks 1–2 |
| NS01 | SDKI/SLKI/SIKI mode independen dan berdasarkan asesmen | `component_modes`, `validate_components`, mapping, target-specific AI | Segmented UI, mode/provenance konsisten saat apply mapping, konteks asesmen dan invalidasi stale response | Step 8 Tasks 3–4 |
| RX01 | Obat/Racikan/BMHP empat tingkat | Master, cascade, unit/routes, snapshot, komponen racikan dan formulary | Reuse; risiko pilihan aktif menjadi badge/Tall Man yang jelas, no stale product info | Medication Task 1 |
| RX02 | Signa/durasi/jumlah otomatis yang dapat disesuaikan | Kalkulator Decimal server sudah ada; UI menunggu save | Read-only quantity preview, tampilkan unit/manual state, recalculation saat save | Medication Task 2 |
| RX03 | Instruksi penggunaan, PRN | UI mencampur “Indikasi PRN / instruksi tambahan”; serializer hanya mengirimnya pada PRN | Pisahkan `instructions` dengan indikasi PRN, persist/readback untuk FIXED/INTERVAL dan print/farmasi | Medication Task 1 |
| RX04 | Alergi/duplikasi/High Alert/LASA/PPRA | Safety engine, bound review digest, PPRA independent approval, depo grants, replay-safe billing | Pertahankan; uji integrasi dengan composer baru, unavailable states dan frozen instructions | Medication Task 3 |
| PX01 | Penunjang empat tingkat dan multiselect | Kategori→instalasi→kelompok→item, basket lintas cabang, pagination, atomic batch | Tidak dibuat ulang; perbaiki state pagination/reset dan fallback manual eksplisit | Ancillary Task 2 |
| PX02 | Rutin/CITO, indikasi/diagnosis dan persiapan | Backend menerima 9 metadata keys; form hanya status umum/site dan variants | Input/serializer specimen, external destination, region/side/contrast sesuai item; schema bounded | Ancillary Task 1 |
| PX03 | Cabang lab, PA/BDRS/rujukan, pencitraan/elektrofisiologi/endoskopi/nuklir | Fixture cabang tersedia sebagai staging | Reconcile coverage, reviewed representative fixtures, service availability bukan asumsi | Ancillary Task 3 |
| IX01 | Diagnosis/rencana tersambung order/hasil dan billing | Canonical services dan professional care sudah ada | E2E CITO → hasil → diagnosis → plan/resep → execution/farmasi → snapshot; tidak double charge | Roadmap final gate |
| EN01 | Fitur bisa dipakai pada environment target | Schema sumber lengkap, DB lokal tertinggal | Explicit target/backup/migration rehearsal dan readback; tidak disamakan dengan development test DB | Roadmap Phase 0/release |

### Referensi source yang diperiksa

- `pasien/forms_igd_workflow.py:12–29` — sebelas langkah dan dua field lama pada Langkah 8.
- `templates/pasien/_igd_step8_fields.html:1–6` dan `igd_workflow.html:41–65` — urutan rendering lama; independent forms sudah ada.
- `pasien/igd_workflow_views.py:59–67,142–172,284–299` — role gating, context mode/diagnosis/depo, catalogue lookup umum.
- `pasien/tests_igd_diagnosis_lines.py:23–169` — primary/secondary, replay, projection, audit, scope dan HTTP render tests yang harus dipertahankan.
- `klinis/models.py:77–136` dan `klinis/services/saran.py:15–88` — relasi kasus/tindakan dan rekomendasi deterministik yang bisa diperluas.
- `klinis/services/ai_igd_targets.py:13–60` — target/profession/provider gates dan reduksi context menjadi keyword catalogue. Ini actual AI transport, bukan hanya ranking yang diberi label AI.
- `pasien/services/igd_planning_components.py:11–57` — mode independen, relation validation dan target-bound tickets.
- `templates/pasien/_igd_medication_composer.html:14–32,35–43` dan `static/js/igd-clinical-expansion.js:125–153` — quantity belum dipreview dan instruksi non-PRN belum diserialisasi dari kontrol campuran.
- `pasien/services/prescriptions.py:28–54,74–171,197–274` — kalkulasi, draft/submit dan replay-safe dispensing/financial-pending.
- `templates/pasien/farmasi_antrean.html:31,280–286` dan `igd_workflow_resume.html:17` — signa yang ditampilkan masih dominan `aturan_pakai`; full structured instructions perlu consumer eksplisit.
- `klinis/services/penunjang_catalogue.py:6–60`, `pasien/services/penunjang_orders.py:9–54`, `_igd_ancillary_order.html:6–16` — metadata backend lebih luas daripada input UI.
- `pasien/services/penunjang_results.py:17–79` — scoped worklist dan validasi/correction/audit hasil yang tidak dibangun ulang.
- `pasien/services/igd_actions.py:191–246` — operasi/digest/version/replay dan larangan legacy execution saat professional care aktif.
- `pasien/services/igd_finalization.py:19–38` dan `igd_workflow_views.py:320–325` — snapshot serta resume bergantung pada `STEPS`, sehingga penghapusan editor punya efek ke history jika tidak dipisahkan.

## 5. Temuan prioritas dan batas klaim

| Prioritas | Temuan | Bukti/klasifikasi | Tindakan |
|---|---|---|---|
| P1 | Menu baru ditambahkan tetapi editor lama belum diganti | Source trace dan screenshot permintaan; bukan browser ulang | Ganti layout/ownership aktif sambil menjaga history |
| P1 | ICD-10 tidak mengarahkan pilihan Master ICD-9 pada layar ini | Catalogue endpoint umum + relasi data terukur | Sambungkan existing FK, tanpa tabel mapping baru |
| P1 | Konteks rekomendasi menghilangkan informasi klinis numerik/negatif menjadi keyword | Source AI; bukan penilaian kualitas provider live | Kontrak bounded evidence berprovenance dan tests |
| P1 | Input instruksi tambahan tidak terkirim untuk frekuensi non-PRN | Source serializer branch; perlu browser RED/readback | Pisah instruksi umum/PRN dan consumer |
| P1 | Required specimen/external referral tidak punya kontrol dedicated | Backend allowlist vs template; perlu browser RED/readback | Schema-driven bounded inputs dan serialisasi |
| P2 | Quantity calculation ada tetapi feedback baru setelah save | Source composer/calc | Preview read-only dan unit-aware |
| P2 | Badge produk sebelum save belum terpisah; old info/pagination owner perlu reset lengkap | Source JS; race spesifik menjadi hipotesis yang harus diuji RED | Tampilan risk/state dan stale pagination tests |
| Environment gate | SQLite lokal belum punya schema workflow/expansion | Read-only ledger dan tabel | Persiapan target terotorisasi, bukan perbaikan spekulatif aplikasi |

Prioritas di atas adalah urutan pengerjaan, bukan klaim telah menjalankan exploit atau seluruh journey. Ketika temuan bersifat source-level, plan memulai dengan pengujian boundary yang gagal karena perilaku yang benar-benar dimaksud, bukan mengasumsikan existing green suite sudah mencakupnya.

## 6. Koreksi interpretasi dokumen

1. **KFA bukan master diagnosis ICD-10.** Pertahankan pemisahan code systems; kesiapan mapping bukan aktivasi SATUSEHAT.
2. **Tidak ada konversi universal ICD-10 → ICD-9.** Gunakan pemetaan kasus lokal yang tersedia sebagai kandidat; dokter tetap menetapkan tindakan. Diagnosis manual/unmapped tetap dapat memakai Manual/Master global.
3. **Kode 3S mengikuti katalog aktual.** Probe lokal mengembalikan `D.0077 — Nyeri Akut`, `D.0001 — Bersihan Jalan Napas Tidak Efektif`, `L.08066 — Tingkat Nyeri`, `L.01001 — Bersihan Jalan Napas`, `I.08238 — Manajemen Nyeri`, dan **`I.01011 — Manajemen Jalan Napas`**, bukan label “Latihan Batuk Efektif” pada dokumen. Kata “menurun/meningkat” adalah target luaran, bukan penggantian nama master.
4. **Flag obat dapat berlapis.** LASA/High Alert/OOT/narkotika/psikotropika/PPRA tidak dibuat enum tunggal. Nama contoh merek, kombinasi kekuatan dan label risiko perlu provenance/review.
5. **Fornas bukan jaminan klaim disetujui.** Perlu versi, periode/restriksi yang tepat; tidak mengarang membership dari nama obat.
6. **Frekuensi × dosis × durasi tidak berlaku universal.** PRN, variabel, racikan/BMHP, kemasan/konversi yang belum diketahui tetap manual beralasan. Preview tidak menjadi persetujuan dosis atau otoritas jumlah akhir.
7. **Order/rencana bukan pelaksanaan/tagihan.** Jangan membuat charge saat memilih katalog/AI/mengirim order; jaga kepemilikan billing agar EKG tidak ditagih dua kali oleh dua jalur.
8. **Hilangkan editor bukan hilangkan rekam klinis.** Dua field lama tetap tersimpan dan dapat dibaca sebagai historis; data signed, performed, dispensed dan billed tidak dibersihkan.
9. **Nurse delegation belum disepakati.** Source penunjang menyebut dokter/perawat; current policy hanya dokter mengirim order. Plan default mempertahankan policy terverifikasi, tidak memberi izin baru diam-diam.

## 7. Alternatif arsitektur dan rekomendasi

| Opsi | Kelebihan | Biaya/risiko | Keputusan |
|---|---|---|---|
| Perluas layar/service sekarang | Satu episode, audit, privilege, replay dan billing tetap konsisten; relasi master sudah ada | Butuh disiplin form/snapshot/shared-file ownership | **Direkomendasikan** |
| Tambahkan form/JSON menu baru berdampingan | Cepat menambah tampilan | Melanggar permintaan pengganti; state/diagnosis/billing ganda | Tidak dipilih |
| Buat app/microservice farmasi/penunjang baru | Isolasi domain lebih besar | Duplikasi transport/auth/deploy tanpa kebutuhan baru yang terbukti | Tidak dipilih |

Pemisahan tugas berdasarkan workstream, bukan tiga sistem baru. Tidak diperkirakan membutuhkan model/migrasi baru untuk gap utama yang ditemukan; schema installation yang tertinggal adalah persoalan environment berbeda.

## 8. Keputusan review dan scope

Asumsi rancangan untuk direview: hilangkan kedua editor hanya pada alur baru; pertahankan history/legacy guarded compatibility; diagnosis manual tetap bebas; rekomendasi Master deterministik bukan AI; AI tidak auto-accept; dokter menetapkan diagnosis/rencana dan mengirim resep/order; perawat/bidan mengelola 3S sesuai kewenangan; farmasi/PPRA tetap dengan penugasan terpisah. Order CITO tidak ditahan sampai seluruh asesmen selesai.

Hal yang memerlukan keputusan sebelum aktivasi terkait: lingkungan target, otorisasi migrasi/import, reviewer/versi master obat dan penunjang, tujuan layanan/depo, aturan Fornas/PPRA/override, delegasi perawat jika diinginkan, dan kebijakan pengakuan biaya yang belum ditetapkan. Hal itu tidak menghalangi implementasi/test sintetis gap UI, tetapi tidak boleh dianggap sudah disetujui oleh permintaan planning.

**Di luar scope — do not implement, do not fix while here:** redesain pemeriksaan fisik langkah 6, kredensial/tarif profesional/CPPT baru, stok/pengadaan, bedside MAR/transfusi, LIS/PACS/SATUSEHAT/BPJS live, impor master nasional tanpa sumber resmi, perubahan policy/delegasi profesi, pembersihan DB atau aktivasi demo/produksi, perbaikan seluruh modul RAJAL/RANAP, commit/push/deploy.

Lima file untracked yang sudah ada (`config/professional_browser_settings.py`, `config/professional_qa_settings.py`, `qa/professional_browser_probe.py`, `qa/professional_browser_server.py`, `qa/professional_regression_gate.py`) adalah pekerjaan sebelumnya dan dipertahankan.

## 9. Dokumen eksekusi yang diusulkan

Plan ditulis dalam English mengikuti konvensi project; analisis dan ringkasan pengguna dalam Bahasa Indonesia.

1. `../plans/2026-11-16-igd-document-revision-roadmap.md` — authoritative sequencing, baseline/environment, shared ownership dan acceptance/release gates.
2. `../plans/2026-11-16-igd-step8-replacement-completion.md` — pengganti layar, history, ICD-10→ICD-9, konteks saran dan 3S.
3. `../plans/2026-11-16-igd-medication-composer-completion.md` — instructions, risk display, quantity preview dan end-to-end lifecycle.
4. `../plans/2026-11-16-igd-ancillary-integration-completion.md` — metadata, cascade/reset/manual fallback dan coverage/journey.

Plan 13 November dan delivery ledger tetap bukti historis. Instruksi NEW-file/create-model pada plan tersebut **superseded untuk requirement yang sudah diimplementasikan**; jangan mengeksekusi seluruh plan lama bersamaan dengan completion plan ini. Kontrak privilege/CPPT/professional billing dan pemeriksaan fisik tetap dipertahankan.
