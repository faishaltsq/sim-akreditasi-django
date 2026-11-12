# Analisis Perbaikan Alur Asesmen Awal IGD

**Status:** Analisis dan desain usulan; belum diimplementasikan.
**Tanggal:** 2026-11-12.
**Sumber:** `C:/Users/cubeb/Downloads/Perbaikan Alur asesmen awal di igd.docx`, hasil ekstraksi 14 baris.
**Baseline kode:** `master`, `36aa2900c1d0d3d174acfdabede1c09a6b7174b1`; working tree bersih sebelum dokumentasi ini.
**Plan:** `../plans/2026-11-12-perbaikan-alur-asesmen-awal-igd.md`.

## 1. Kesimpulan

Dokumen meminta **11 langkah**, bukan 10. Cakupannya adalah satu episode pelayanan IGD: identifikasi, asesmen awal, diagnosis/rencana, pelaksanaan asuhan, evaluasi, dan disposisi. Mengganti urutan tab saja tidak memenuhi kebutuhan penyimpanan, CPPT, order, billing, dan finalisasi.

Rekomendasi: halaman alur IGD khusus dengan 11 langkah, memakai model dan layanan klinis yang sudah ada; bukan membangun EMR kedua dan bukan mengubah wizard bersama yang juga dipakai layanan lain secara membabi buta. Tambahkan metadata draft/final, observasi TTV berulang, dan data yang benar-benar belum tersedia.

## 2. Matriks sumber → kode → gap

| Langkah sumber | Implementasi yang ditemukan | Perubahan yang diperlukan |
|---|---|---|
| 1. Identitas & Penjamin | `Pasien`, `KunjunganPasien.penjamin`, master tarif per penjamin | Header identitas konsisten; koreksi identitas/penjamin mengikuti kewenangan admisi; perubahan tarif harus eksplisit dan diaudit. |
| 2. Triase & Cara Datang + ABCDE | `triage`, `triase_kategori`, `cara_datang`, `fisik_airway` sampai `fisik_exposure` | Satukan layar; pisahkan skala ATS/ESI/warna; koreksi kategori 5 → Hitam; jangan menjadikan halaman berurutan sebagai penghambat pelayanan emergensi. |
| 3. Anamnesis & Riwayat | `anamnesis_rps/rpd/rpk/obat`, alergi di `Pasien` | Susun ulang; bedakan alergi belum dikaji, tidak diketahui, tidak ada, dan ada. Jangan menyalin anamnesis lama sebagai temuan hari ini tanpa tinjauan. |
| 4. TTV | TD, nadi, RR, suhu, SpO2, GCS, nyeri tersedia | Validasi server, pertahankan angka nol yang sah, dan catat waktu/petugas pengukuran. |
| 5. Biopsikososial, spiritual & skrining | Status psikososial/spiritual/emosional, hambatan komunikasi, MST, Morse | Satukan; tambahkan hambatan edukasi yang eksplisit. Jangan melabeli metode lain sebagai Morse atau mengisi skor nol saat belum diperiksa. |
| 6. Pemeriksaan fisik lengkap | `fisik_head_to_toe`, `secondary_survey_detail` | Tentukan pemilik data per organ, jangan punya dua nilai berbeda; tambah lokalis dan penanda anatomi yang dapat diedit/disimpan/dicetak. |
| 7. Penunjang: order & hasil | `OrderPenunjang` LAB/RADIOLOGI; checklist radiologi, EKG, hasil kritis; endpoint order dan hasil | Satu panel order/hasil dengan status; dukung EKG/lainnya secara eksplisit, lampiran terlindungi, kirim order sebagai aksi tersendiri yang idempoten. |
| 8. Diagnosis & Rencana: Manual/Master/AI | ICD-10, ICD-9, 3S, `TindakanAsesmen`; saran katalog deterministik | Pisahkan rencana dari pelaksanaan. Saran katalog bukan LLM. Untuk opsi AI nyata, reuse transport AI backend yang sudah ada, gate per modul, hasil tervalidasi dan diterapkan hanya setelah dipilih petugas. |
| 9. Pelaksanaan asuhan: CPPT & tindakan/billing | `CPPT`, `igd_cppt_quick_add`, `igd_eksekusi_tindakan`, `BillingItem`, sinkronisasi tarif | Hubungkan eksekusi ke baris rencana dan billing; retry tidak menggandakan catatan/tagihan. CPPT saja tidak otomatis berarti tindakan ditagihkan. |
| 10. Evaluasi akhir | Kondisi akhir tersedia; CPPT dapat memuat evaluasi naratif | Tambah panel respons terapi dan TTV ulang bertimestamp, tanpa menghapus pengukuran awal. |
| 11. Disposisi & resume | Pulang, ranap, rujuk, meninggal, konsul/PAPS tersedia pada jalur terpisah; resume cetak tersedia | Integrasikan dengan validasi bersyarat, transaksi dan snapshot final; bedakan konsultasi poli dengan transfer tanggung jawab pelayanan. |

## 3. Temuan teknis prioritas

### P0 — Semantik triase keliru

`pasien/models.py:440-466` memberi label kategori 5 sebagai “Rutin / Hitam / DOA”. `pasien/views.py:2481-2492` memetakan kategori 5 langsung menjadi `HITAM`.

ATS kategori 5 adalah kategori dengan target mulai asesmen/tatalaksana dalam 120 menit, bukan definisi DOA. ATS dan ESI juga tidak boleh dianggap identik hanya karena sama-sama memiliki lima level. Rujukan ATS: [ACEM — Triage](https://acem.org.au/Content-Sources/Advancing-Emergency-Medicine/Better-Outcomes-for-Patients/Triage), diakses pada analisis ini.

**Usulan:** simpan sistem triase dan kategorinya secara eksplisit; warna operasional terpisah. Kematian/DOA adalah data klinis terpisah. Pertahankan nilai historis ambigu, tandai untuk tinjauan, jangan mengubah massal rekam lama. Tidak ada konversi otomatis ESI↔ATS.

### P0 — “Simpan Permanen” belum mempunyai kontrak

Endpoint `kunjungan_asesmen_awal`, `igd_asesmen_awal_save`, dan `igd_asesmen_medis_save` menulis field klinis yang sama melalui jalur berbeda. Belum ditemukan status final terpisah beserta snapshot/version guard. `pasien/views.py:3118-3155` juga mempunyai pengosongan asesmen dan penghapusan artefak.

**Usulan:** status workflow DRAFT/FINAL terpisah dari status pelayanan pasien. Final merekam snapshot dan penandatangan; semua jalur edit/hapus/copy lama harus menghormati kunci final. Koreksi setelah final melalui addendum beralasan dengan jejak revisi; bukan overwrite atau hapus permanen.

### P0 — Rencana, pelaksanaan, dan uang belum satu kontrak

`pasien/asesmen_tindakan.py:89-170` memperlakukan payload sebagai daftar lengkap: baris yang tidak dikirim dihapus dan billing langsung disinkronkan. Ini tidak cocok dipanggil sembarang langkah dalam autosave parsial. `igd_eksekusi_tindakan` mencatat CPPT tetapi tidak membuktikan hubungan satu eksekusi dengan satu baris billing.

**Usulan:** endpoint draft hanya menulis field milik langkah tersebut. Pemilihan rencana tidak menjalankan tindakan. Eksekusi eksplisit, ID stabil, dan operasi idempoten menjadi pemicu sinkronisasi billing untuk workflow baru. Billing dan override lama tidak dihapus/dihitung ulang diam-diam. Tarif BPJS di aplikasi tidak boleh ditampilkan sebagai kepastian klaim disetujui.

### P1 — Riwayat pengukuran belum memadai

TTV pada `KunjunganPasien` hanya satu set. Memakai set yang sama untuk langkah 4 dan 10 akan menimpa hasil sebelumnya.

**Usulan:** observasi TTV append-only, fase awal/evaluasi, waktu pengukuran dan petugas. Field TTV kunjungan tetap menjadi proyeksi nilai terkini untuk konsumen lama; nilai awal/evaluasi diambil dari observasinya masing-masing.

### P1 — Tampilan belum satu alur

`templates/pasien/_asesmen_awal_wizard.html:19-41` mempunyai empat tab; modal asesmen medis pada `templates/pasien/igd_dashboard.html:1435-1475` mempunyai tujuh tab dengan urutan berbeda. Order, CPPT, dan disposisi juga berada pada aksi terpisah. Handler menyebut sepuluh bagian, tetapi itu bukan bukti UI sebelas langkah terpenuhi.

**Usulan:** satu entry point IGD khusus; tombol lama diarahkan ke halaman yang sama setelah paritas teruji. Wizard rawat jalan tetap dipertahankan.

### P1 — Otorisasi harus per objek dan profesi

`pasien/decorators.py` membungkus view dengan akses modul; `pasien/unit_scope.py` menyediakan scope unit. Sejumlah handler yang diperiksa hanya mengambil kunjungan berdasarkan PK di dalam fungsi; keduanya harus dipastikan berlaku bersama. `CPPT` saat ini menerima profesi dari POST dan quick-add menganggap profesi DOKTER sebagai terverifikasi.

**Usulan:** scope objek pada semua endpoint workflow, termasuk download/cetak, serta aktor/profesi dari akun terautentikasi. Hak administrasi bukan tanda tangan dokter/perawat. Pasien yang dipindah unit tetap dapat dicetak oleh pihak berwenang melalui kebijakan riwayat yang eksplisit, bukan akses semua unit.

## 4. Keputusan desain dan tradeoff

| Keputusan | Manfaat | Konsekuensi |
|---|---|---|
| Halaman IGD khusus, bukan mengganti seluruh wizard bersama | Mengisolasi perubahan dan mengurangi regresi RAJAL | Perlu adapter field dan transisi tombol lama. |
| Reuse model klinis; metadata workflow terpisah | Data tunggal untuk rekap, resume, dan layanan lain | Writer lama wajib ikut version/final guard. |
| Simpan draft eksplisit per langkah; bukan autosave setiap ketikan | Perilaku transaksi jelas dan permintaan jaringan terkendali | Petugas perlu tombol Simpan Draft/berpindah langkah yang menyimpan; navigasi keluar meminta keputusan saat ada perubahan. |
| Pengukuran berulang append-only | Nilai awal dan evaluasi tetap dapat ditelusuri | Ada tabel observasi tambahan dan aturan proyeksi TTV terkini. |
| Manual + Master tetap mandiri dari AI | Pelayanan tetap berjalan jika provider tidak tersedia | Opsi AI memiliki aktivasi dan pengujian terpisah. |
| Order/eksekusi/disposisi adalah aksi domain eksplisit | Tidak dipicu hanya oleh pindah tab atau save draft | UI perlu menunjukkan jelas draft, terkirim, terlaksana, dan final. |
| Finalisasi tidak sama dengan discharge | Asesmen bisa final tanpa memalsukan status pelayanan | Tombol tahap 11 perlu pratinjau dampak disposisi dan transaksi yang terpisah/terkoordinasi. |

## 5. Asumsi yang harus dikonfirmasi sebelum implementasi terkait

1. **Skala triase:** gunakan skala yang ditetapkan SOP RS; tidak memilih ATS/ESI otomatis dari rekam lama. Skala historis yang tidak diketahui tetap ditampilkan sebagai tidak diketahui.
2. **Poli spesialis:** opsi “konsultasi” tidak mengeluarkan pasien dari roster IGD; “transfer layanan” baru memindahkan kepemilikan. Konfirmasi apakah dokumen meminta salah satunya atau keduanya.
3. **Finalisasi:** default usulan adalah dokter menandatangani bagian medis dan perawat bagian keperawatan yang berlaku. Pengecualian/“tidak dapat dinilai” harus beralasan; admin tidak boleh menyamar sebagai penandatangan klinis.
4. **AI:** reuse konfigurasi transport DeepSeek yang sudah ada (`akreditasi/ai_service.py`), tetapi gate IGD default nonaktif sampai pengolahan data dan konfigurasi disetujui. Tidak membeli kuota atau mengirim rekam pasien saat analisis ini.
5. **Penjamin asuransi:** gunakan pilihan/model saat ini; jika tarif khusus asuransi belum ada, tampilkan status tarif belum dikonfigurasi, bukan mengarang tarif BPJS/Umum.

## 6. Bukti dan batas analisis

Baseline berikut benar-benar dijalankan pada checkout tersebut:

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python manage.py test \
  pasien.tests_revisi_asesmen_medis_igd \
  pasien.tests_asesmen_save_ep_tarif \
  pasien.tests_asesmen_rekap \
  pasien.tests_morse \
  pasien.tests_igd_lifecycle --keepdb --noinput
```

**Hasil:** 29 tes lulus dalam 30.972 detik; exit 0. Ini baseline subset terkait, bukan bukti fitur baru sudah bekerja atau seluruh repository lulus.

Analisis berupa inspeksi DOCX, kode, plan pendahulu, dan tes lokal. Tidak ada uji browser baru, perubahan aplikasi, migrasi production, pemanggilan AI live, commit, push, atau deploy pada pekerjaan ini. Catatan lama tentang jumlah tes/fitur tidak diperlakukan sebagai verifikasi ulang production.
