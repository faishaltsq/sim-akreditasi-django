# Analisis Tambahan Pemeriksaan Fisik Terstruktur IGD

**Status:** ANALYSIS COMPLETE — implementasi belum dimulai; tidak ada perubahan aplikasi, migrasi, atau production pada tahap ini.
**Tanggal:** 13 November 2026.
**Baseline source:** `112a7b3357168ec53aac6cb4c6670b8bcab86f66`, branch `master`; tree bersih sebelum penulisan dokumen.
**Sumber:** `C:/Users/cubeb/Downloads/Tambahan untuk pemeriksaan fisik 13 11.docx`.
**SHA-256 sumber:** `9b440a3bf048e2fedda3a458ab4657729c2fc4c16dee8e9b73856de0205c8f7f`.
**Ekstraksi:** seluruh 228 baris teks dibaca, termasuk contoh Python dan UX; DOCX tidak memiliki media tertanam. Nomor baris berikut adalah baris hasil ekstraksi, bukan nomor halaman Word.
**Plan:** `../plans/2026-11-13-igd-structured-physical-examination.md`.

## 1. Kesimpulan

Dokumen meminta pengayaan **langkah 6**, bukan pembuatan ulang alur IGD 1–11: pemeriksaan fisik berbasis pilihan terstruktur, banyak temuan per organ, keterangan kondisional, tombol cepat normal, dan ringkasan naratif Secondary Survey.

Gunakan model `KunjunganPasien` dan jalur draft/final yang sudah ada. Tidak perlu menambahkan model `PemeriksaanFisikIGD` seperti contoh dokumen: model terpisah tanpa relasi kunjungan justru menambah sumber data dan risiko sinkronisasi. Rekomendasi adalah **namespace JSON berversi pada `secondary_survey_detail`**, dua field keadaan umum/kesadaran yang sudah tersedia, serta proyeksi teks kompatibel ke `fisik_head_to_toe`. Tidak direncanakan migrasi schema atau backfill massal.

Ini delta terhadap R06 dari plan 12 November. Kontrak triase, TTV bertimestamp, pemisahan rencana/pelaksanaan/billing, otorisasi, optimistic version, signature, finalisasi, addendum, dan private attachment tetap dipertahankan. Dokumen lama adalah riwayat desain/implementasi, bukan instruksi untuk membuat ulang file yang sudah ada. Catatan lama “belum diminta production release” bersifat historis; rilis `112a7b3` sudah dibuktikan dalam percakapan sebelumnya, bukan diverifikasi ulang sebagai deployment baru pada turn analisis ini.

## 2. Kebutuhan sumber dan selisih implementasi

| ID | Sumber | Kebutuhan | Kondisi saat ini / delta |
|---|---|---|---|
| PF01 | 8–22 | Keadaan umum serta kesadaran; referensi GCS E/V/M | `keadaan_umum`, `kesadaran`, GCS sudah ada; dua field pertama belum dimiliki form langkah 6. Tambahkan pilihan, tampilkan referensi pengukuran GCS tanpa menulis ulang langkah 4/10. |
| PF02 | 22–31 | Kepala & wajah | UI baru menggabungkan kepala/leher dalam teks; pisahkan pilihan kepala/wajah. |
| PF03 | 31–46 | Mata | UI baru teks; UI medis lama sudah memiliki rincian mata pada JSON lain. Tambahkan multi-temuan dan pembacaan historis. |
| PF04 | 46–58 | THT | Tambahkan pilihan, sisi dan karakteristik temuan melalui catatan. |
| PF05 | 58–70 | Leher | Pisahkan dari kepala; jangan menduplikasi/mengartikan otomatis teks historis kepala-leher sebagai normal di dua bagian. |
| PF06 | 70–85 | Thorax–paru | Pisahkan pilihan paru dari jantung; pertahankan lokasi/lapang paru di catatan. |
| PF07 | 85–97 | Thorax–jantung | Tambahkan pilihan ritme, murmur, gallop, bunyi menjauh dan catatan. |
| PF08 | 97–112 | Abdomen | Tambahkan multi-temuan dan rincian kuadran. |
| PF09 | 112–121 | Genitalia & anus | Belum ada pada tujuh textarea baru; sediakan “Belum dikaji”/“Tidak diperiksa” terpisah dari normal. Pemeriksaan sesuai indikasi, bukan wajib normal. |
| PF10 | 121–136 | Ekstremitas | Pilihan temuan dan catatan sisi, lokasi serta kekuatan otot. |
| PF11 | 136–148 | Kulit & integumen | Pilihan temuan dan rincian luas/derajat bila relevan. |
| PF12 | 206–225 | Multi-select, keterangan, status lokalis | Reuse JSON; `fisik_lokalis` dan marker anatomi sudah ada dan harus tetap bekerja. |
| PF13 | 226–227 | Tombol “Semua Normal” | Belum tersedia dalam workflow baru. Aksi eksplisit hanya mengisi draft organ yang layak, tidak menimpa abnormal/catatan, tidak menetapkan kesadaran/GCS atau pemeriksaan genitalia yang belum dilakukan. |
| PF14 | 228 | Auto-summary ke Secondary Survey | Saat ini JSON mentah masih dapat tampil sebagai field form. Tambahkan preview naratif dan generasi ulang otoritatif di server. |
| PF15 | Integrasi yang diperlukan | Simpan, buka kembali, final, cetak, addendum, kompatibilitas data lama | Adapter baca legacy, serializer canonical, invalidasi signature dan renderer snapshot harus diuji sebagai satu perjalanan, bukan widget saja. |

### Katalog pilihan yang wajib tercakup

Label boleh diperjelas ejaannya, tetapi tidak boleh menghilangkan temuan sumber. Tambahkan “Lainnya” dan catatan agar daftar bukan pembatas temuan klinis.

1. **Keadaan umum & kesadaran:** baik/tampak sakit ringan, tampak sakit sedang, tampak sakit berat; kompos mentis, apatis, somnolen, sopor, koma. Dua dimensi disimpan pada field existing yang terpisah.
2. **Kepala & wajah:** normal; hematoma/vulnus; deformitas/fraktur impresi; nyeri tekan.
3. **Mata:** normal; konjungtiva anemis; sklera ikterik; anisokor; midriasis/miosis; edema palpebra/hematoma periorbita.
4. **THT:** normal; otorrhea/rhinorrhea; epistaksis; deviasi septum; faring hiperemis/tonsil membesar.
5. **Leher:** normal; JVP meningkat; deviasi trakea; KGB/tiroid membesar; kaku kuduk/jejas leher.
6. **Paru:** normal; gerak asimetris/retraksi; vesikuler menurun/hilang; rhonki; wheezing; perkusi redup/hipersonor.
7. **Jantung:** normal; ireguler; murmur; gallop; bunyi menjauh.
8. **Abdomen:** normal; distensi; nyeri tekan epigastrium/kuadran; defans; bising usus meningkat/menurun/menghilang; hepatomegali/splenomegali.
9. **Genitalia & anus:** normal bila diperiksa; perdarahan pervaginam/uretra; retensi urin/distensi vesika; hemoroid/melena/hematochezia; status kateter sebagai detail eksplisit, bukan asumsi.
10. **Ekstremitas:** normal; akral dingin/pucat/sianosis; CRT >2 detik; edema; deformitas/krepitasi/fraktur; paresis/plegia.
11. **Kulit & integumen:** normal; turgor menurun; sianosis/pucat/ikterik; ruam/petekie/ekimosis; luka bakar/ulkus dekubitus.

## 3. Bukti dari kode dan data

| Lapisan | Observasi terverifikasi |
|---|---|
| Model | `pasien/models.py:397–401` menyediakan keadaan umum, kesadaran, JSON head-to-toe; `:506` menyediakan JSON Secondary Survey. |
| Form | `pasien/forms_igd_workflow.py:21` memiliki empat field langkah 6: head-to-toe, secondary, lokalis, marker; validasi JSON baru memeriksa bentuk dictionary, belum katalog atau normal-vs-abnormal. |
| Writer workflow | `save_step` pada `pasien/services/igd_assessment_workflow.py:60–153` memakai lock kunjungan, validasi form, daftar field berubah dan version; hasil turunan harus dimasukkan ke daftar `update_fields`, bukan hanya dihitung di form. |
| UI baru | `pasien/igd_workflow_views.py:77,112` membangun tujuh organ dari `fisik_head_to_toe`; `_igd_clinical_widgets.html:10` masih tujuh textarea; `igd-clinical-controls.js:108–112` mengubah JSON teks, bukan pilihan terstruktur. |
| Writer lama | `pasien/views.py:2578–2642` menyimpan objek nested per organ di `secondary_survey_detail`. Writer lain menggunakan key `toraks_dada`, `genitalia_anus`, `integumen_kulit` pada head-to-toe. Ini berbeda dari `thorax`/`kulit` yang dibaca UI baru. |
| Finalisasi | `igd_finalization.py:18–32` sudah memasukkan field `STEPS` ke snapshot; `:68` memakai truthiness JSON untuk kelengkapan fisik. JSON scaffolding berisi schema saja tidak boleh dianggap pemeriksaan terisi. |
| Resume | `igd_workflow_resume` membangun row dari snapshot; template belum memformat structured examination sebagai tabel per bagian. Field baru yang tidak ada di snapshot lama tidak boleh fallback ke data kunjungan terkini. |
| Cetak lama | `cetak_asesmen_medis_igd.html:147–169` memiliki default tampilan normal pada data kosong. Untuk bagian fisik yang disentuh perubahan ini, kosong harus terbaca sebagai belum tercatat, bukan pemeriksaan normal. |
| Data production, read-only | 11 kunjungan IGD; 1 memiliki head-to-toe nonkosong; 1 memiliki Secondary Survey nonkosong; **1 memiliki Secondary Survey tetapi head-to-toe kosong**. Namespace `head_to_toe` belum digunakan; tidak ditemukan JSON non-object pada dua field tersebut. Ada 1 workflow, belum ada FINAL. Tidak dibaca atau disalin identitas/isi klinis pasien. |
| Baseline lokal saat analisis | `manage.py test pasien.tests_igd_workflow_clinical pasien.tests_igd_workflow_ui pasien.tests_igd_workflow_finalization --keepdb --noinput`: **35 tes lulus**, exit 0; waktu tes 4.701 detik. Bukan full suite dan bukan acceptance production. |

**Temuan penting terkait keluhan kosong sebelumnya:** ada gap adapter yang nyata: UI baru hanya membaca satu JSON sementara writer lama menyimpan pada JSON lain; aggregate production menunjukkan kasus secondary-only memang ada. Ini bukan bukti bahwa semua langkah hilang, dan belum membuktikan bahwa kasus tersebut adalah URL yang sebelumnya dibuka pengguna. Plan harus memperbaiki fallback read-only, bukan mengisi data pasien dengan nilai default normal.

## 4. Koreksi terhadap contoh implementasi dokumen

- Narasi sumber berisi **11 kelompok**, sementara contoh model hanya enam kelompok JSON; jangan menjadikan contoh model sebagai batas scope.
- Contoh tidak menghubungkan `PemeriksaanFisikIGD` dengan pasien/kunjungan atau memasukkannya ke transaksi, authorization dan snapshot. Reuse domain saat ini.
- Kepala/leher dan thorax pada contoh digabung; kebutuhan naratif memisahkan kepala-wajah/leher serta paru/jantung.
- `secondary_survey_detail` saat ini **JSON**, bukan kolom teks naratif. Simpan struktur berversi dan ringkasan server di namespace khusus; jangan mengganti tipe kolom.
- Kombinasi `normal` bersama abnormal dalam organ yang sama harus ditolak server. Beberapa temuan abnormal boleh bersamaan; pilihan yang saling berlawanan dalam dimensi yang sama perlu grup eksklusif.
- Kesadaran kompos mentis pada UI tidak boleh menciptakan pengukuran GCS 15, komponen E/V/M, atau waktu observasi secara otomatis. Perlihatkan nilai existing dan arahkan koreksi ke langkah 4/10.
- Contoh “Hb rendah” hanya masuk narasi jika benar-benar dicatat petugas; generator tidak boleh menambah hasil lab, diagnosis, atau hubungan sebab-akibat.
- Sumber menyebut STARKES secara umum, tanpa EP tertentu. Tidak ada seed, kode EP baru, atau klaim kepatuhan otomatis dalam penambahan ini.

## 5. Desain yang direkomendasikan dan tradeoff

1. **Namespace existing JSON dibanding model baru:** tidak membutuhkan migrasi dan tidak membuat identitas/kunjungan ganda. Tradeoff: validasi schema, merge dan versi katalog harus ketat di aplikasi.
2. **Canonical structured + proyeksi teks lama:** `secondary_survey_detail.head_to_toe` adalah data pilihan baru; `head_to_toe_summary` adalah teks turunan server. `fisik_head_to_toe` tetap dictionary string untuk consumer lama, termasuk property yang memanggil `.strip()`. Tradeoff: dua representasi, tetapi hanya satu writer bersama dan proyeksi tidak diedit independen setelah adopsi.
3. **General state memakai field existing:** perlu menambah `keadaan_umum`/`kesadaran` ke kepemilikan langkah 6 dan snapshot baru; data historis tidak dipetakan otomatis menjadi pilihan klinis baru. Tradeoff: perlu dukungan nilai legacy yang tidak berada pada pilihan baru.
4. **Adapter legacy nonmutating:** tampilkan nilai original dengan asal datanya, tanpa menebak kode checkbox. Teks gabungan kepala/leher atau thorax tetap diberi label gabungan, bukan disalin seolah dua pemeriksaan terpisah. Tradeoff: petugas melakukan review eksplisit saat mengadopsi formulir baru.
5. **Generator ringkasan deterministik tanpa AI:** cepat, tidak menambah biaya/integrasi, tidak mengirim data pasien keluar; format harus disepakati dan diuji. Ringkasan tidak menghapus catatan legacy/manual.
6. **Semua Normal sebagai aksi draft eksplisit:** blank default tetap “Belum dikaji”; abnormal/catatan/riwayat ambigu tidak ditimpa. Genitalia dan keadaan umum/kesadaran tidak dinormalisasi massal. Tradeoff: satu klik tidak berarti menandai semua pemeriksaan sebagai sudah dilakukan.

## 6. Batas scope dan kriteria selesai

**Dalam scope:** langkah 6 IGD; 11 kelompok; adapter data lama; pilihan/validasi; ringkasan; normal shortcut; persistence/reload; snapshot/cetak; signature invalidation; baseline, regresi dan browser terisolasi.

**Tidak dalam plan ini — do not implement, do not fix while here:** redesign pendaftaran, konversi data klinis historis massal, rollout form baru ke seluruh RANAP/RAJAL, perubahan order/CPPT/tarif/billing, perbaikan seluruh default medis di luar bagian pemeriksaan fisik yang disentuh, AI live, sertifikasi signature, penghapusan proyek probe CLI, ataupun penciptaan rekam final/pasien sintetis di production.

Selesai hanya jika pilihan bertahan setelah simpan/reload, halaman secondary-only menampilkan data lama tanpa write, dua representasi konsisten dari hasil server, marker/lokalis tetap utuh, final membaca snapshot immutable, addendum tidak menimpa original, nilai kosong tidak menjadi normal, dan browser membuktikan kontrol/summary/readonly pada lebar target. Push/deploy memerlukan instruksi eksekusi/rilis tersendiri; saat ini hanya analisis dan plan.
