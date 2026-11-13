# Verifikasi lokal — Pemeriksaan Fisik IGD Terstruktur

**Status:** implementasi lokal terverifikasi; belum commit, push, atau deploy.
**Baseline Git:** `112a7b3357168ec53aac6cb4c6670b8bcab86f66`.
**Source fingerprint:** `682ac46fe572b7bc8f90049031792b9d5d4ec9db2c58c5e40cf380acf2817c8a` atas 15 file source dalam `verification.json`. Fingerprint ini milik working tree, bukan SHA commit.

## Perubahan

- Langkah 6 memiliki 11 kelompok pemeriksaan, pilihan multi-temuan, keterangan, alasan tidak diperiksa, keadaan umum/kesadaran, lokalis dan marker yang dipertahankan.
- Data Secondary Survey lama dan alias Head-to-Toe ditampilkan tanpa klasifikasi normal otomatis atau write pada GET.
- Namespace terstruktur divalidasi server, digabung tanpa menghapus bagian yang tidak dikirim, diringkas deterministik dan diproyeksikan menjadi string untuk consumer lama.
- Shortcut normal hanya mengisi bagian kosong yang layak; melewati temuan abnormal/catatan/historis, kesadaran/GCS dan genitalia. Perubahan individual yang menimpa pilihan meminta konfirmasi.
- Snapshot final, resume dan cetak memakai pembaca kompatibel. Field baru yang tidak ada pada snapshot lama tidak memakai nilai live. Persetujuan stale meminta review ulang; original final/addendum tetap immutable.
- Tidak ada model atau migrasi baru; perilaku private attachment tidak diubah.

## Hasil aktual

| Gate | Bukti |
|---|---|
| `manage.py test klinis pasien --keepdb --noinput` | 429 tes lulus, exit 0; waktu tes Django 277.169 detik |
| Probe katalog deterministik | 65 pemeriksaan lulus: setiap pilihan, provenance palsu, batas Unicode 64 KiB, alias legacy |
| Browser dasar | 11 kelompok; nama field klinis unik; spasi pengetikan bertahan; dua simpan/reload; ringkasan preview sama dengan server |
| Layout | 9 pengukuran: baru/legacy/final pada 375, 768, 1366 px; tidak ada overflow horizontal |
| Browser konflik/keamanan | Dua tab menghasilkan 409 tanpa menghilangkan isian; pembatalan ganti abnormal ke normal; alasan tidak diperiksa; HTML tetap teks; keyboard focus; GCS langkah 4/10 tidak diciptakan |
| Browser tambahan | Lainnya kosong ditolak 400 lalu koreksi 200; pilihan general/mixed findings/marker/lokalis bertahan; rekam final setelah transfer RANAP tetap readonly |
| Error JavaScript | Tidak ada page error pada run browser yang selesai |
| Django check | Lulus |
| Migration drift | Tidak ada perubahan yang perlu dibuat |
| Syntax JS | Lulus untuk script workflow yang diperiksa |
| Static assets | Source/unhashed/hashed/decompressed bytes cocok untuk tiga script workflow; hash manifest sesuai |
| Fixture | SQLite/media/session sintetis terisolasi di scratch; server dihentikan, port 18766 ditutup |

Suite ini mencakup app `klinis` dan `pasien`, bukan seluruh app repository. Probes dan suite memiliki overlap; angka-angkanya bukan jumlah tes unik gabungan. Screenshot print memakai snapshot fixture sintetis minimal untuk menguji fallback legacy, bukan contoh rekam klinis lengkap atau rekam pasien production.

## Bukti

- `verification.json`: ringkasan suite, source hashes dan aset.
- `browser.json`: perjalanan dasar dan extended serta pengukuran viewport.
- `browser-additional.json`: validasi Lainnya/general/mixed/marker dan transfer RANAP.
- `catalogue.json`: daftar pemeriksaan per pilihan dan batas.
- `fixture-final-print.png`, `fixture-editor-desktop.png`: screenshot QA sintetis.

Raw logs berada pada scratch Hermes dengan prefix `physical-`. Tidak disalin cookie sesi, credential atau data pasien production ke evidence.

## Batas dan deviasi

- Worker eksternal gagal sebelum mengedit karena provider HTTP 403. Implementasi dilanjutkan langsung; review mandiri dan tool execution nyata dilakukan, bukan approval reviewer eksternal.
- Tahapan RED awal mencatat modul belum tersedia, projection/validation/UI yang belum tersambung, metadata kelengkapan palsu, provenance second-save dan pesan signature stale; perbaikan kemudian lulus gate di atas.
- Percobaan browser awal gagal karena dua asumsi harness: submit-button `intent` dianggap duplicate field klinis dan pencarian exact mengabaikan prefix label temuan. Koreksi ada pada harness; run akhir lulus.
- Urutan penambahan regresi old-snapshot berbeda dari plan: test ditambahkan sesudah wiring reader awal, lalu RED untuk label absent-snapshot sebelum diperbaiki. Klaim TDD tidak diperluas ke urutan yang tidak dilakukan.
- Belum ada deployment, acceptance sesi login production atau audit seluruh default medis legacy. Tidak dibuat/diubah rekam klinis production. Dokumen plan workstream lain yang muncul di workspace dibiarkan utuh.
