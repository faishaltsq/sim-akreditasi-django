# Plan: Logbook harian otomatis, dokumen kredensial otomatis, dan menu kredensial untuk setiap nakes

Sumber (revisi 2026-10-27):

1. `~/Downloads/buat rancangan Modul Logbook Harian Otomatis Tenaga Kesehatan.docx`
2. `~/Downloads/Buat otomatisasi data pendukung kredensial bsr.docx`
3. `~/Downloads/format dokumen pendukung persyaratan kredensial.docx` (baru: contoh format dan isi 8 dokumen)

Permintaan tambahan pada revisi ini: **menu kredensial harus muncul pada setiap login karyawan nakes**, bukan hanya pada pengguna yang punya grant HC.

## 1. Apa yang sudah ada

Jangan bangun ulang. Repo ini sudah memuat sebagian besar fondasinya.

| Kapabilitas | Sudah ada | Lokasi |
|---|---|---|
| Katalog tindakan per jenjang profesi | Ya, `KatalogTindakan` dengan tingkat `M/S/MT/T` | `sdm/models/katalog_rkk.py` |
| Entri logbook klinis per pegawai | Ya, `EntriLogbookKlinis` (tanggal, unit, katalog atau teks bebas, jumlah mandiri/supervisi) | `sdm/models/logbook.py` |
| Form entri + halaman daftar | Ya, `EntriLogbookForm`, `logbook_list/create/edit/delete` | `sdm/forms/logbook.py`, `sdm/views.py:2318` |
| Rekap 36 bulan | Ya, `logbook_recap()` mengagregasi jendela 36 bulan | `sdm/services/logbook.py` |
| Checklist dokumen kredensial (12 baris) | Ya, `DokumenSyaratKredensial` + `evaluate_requirements` | `sdm/services/syarat_kredensial.py` |
| Riwayat dokumen + versi + masa berlaku | Ya, `DokumenPegawai`/`VersiDokumen` (PENDING/VERIFIED/REJECTED/SUPERSEDED) | `sdm/models/dokumen.py` |
| Verifikasi sumber primer (PSV) | Ya, `VerifikasiSumber` | `sdm/models/kredensial.py:10` |
| PDF server-side | Ya, ReportLab terpasang dan dipakai (`pasien/pdf_utils.py`, `akreditasi/mutu_laporan.py`) | `requirements.txt:14` |
| RKK per pengajuan | Ya, `RincianKewenangan` + `status_spk` | `sdm/models/kredensial.py:125` |
| Panel dokumen pendukung self-service | Ya, `supporting_documents` di `pengajuan_saya.html` (status "Belum ada" dari unggahan manual) | `sdm/views.py:1887` |
| Kop surat resmi | Ya, `SystemConfig.kop_surat_text` | `akreditasi/system_models.py` |

Artinya permintaan ini bukan modul baru, melainkan **tiga lapisan di atas yang sudah ada**, plus satu perbaikan navigasi.

## 2. Temuan baru dari dokumen format (revisi ini)

Dokumen ketiga memberi isi konkret 8 dokumen. Dari sini empat hal menjadi jelas:

### 2.1 Tiga jenis tanda tangan, bukan satu

| Dokumen | Penanda tangan | Artinya bagi sistem |
|---|---|---|
| Surat Rekomendasi KSM | Ketua KSM | Sistem **tidak boleh** mengisi nama ketua KSM; harus ada pilihan pejabat + jejak siapa menandatangani |
| Keanggotaan Organisasi Profesi, Riwayat Malpraktik | **Pegawai sendiri** | Ini pernyataan pribadi; identitas terisi otomatis, isi pernyataan harus disetujui pegawai sebelum dicetak |
| Bebas Sanksi Etik | Ketua Komite Medik/Keperawatan | Butuh data catatan disiplin dari subkomite etik, yang **belum ada di sistem** |
| Asesmen Psikologis | Psikolog klinis + SIP | Hasil tes (EPPS/PAPI/MMPI) berasal dari luar; sistem hanya menyediakan formulir kosong |
| Logbook 36 bulan & harian | Perawat, preseptor, kepala instalasi | Bisa 100% digenerate dari data yang sudah ada |

Kesimpulan: hanya **logbook (2 dokumen) dan CV** yang sepenuhnya bisa otomatis. Sisanya formulir berisi identitas dengan bagian pernyataan dan tanda tangan yang diisi pihak berwenang.

### 2.2 Target tindakan ternyata per kompetensi, bukan satu angka total

Contoh logbook 36 bulan memakai tabel:

| Kompetensi | Target 3 tahun | Realisasi | Status |
|---|---|---|---|
| Pengkajian & triase anak | 350 kasus | 380 | Tercapai |
| Terapi obat oral & injeksi | 1.200 tindakan | 1.250 | Tercapai |

Itu mengubah desain Fase 0.1: yang dibutuhkan bukan satu ambang global, tapi **matriks target per tindakan** untuk setiap profesi/jenjang, dengan satuan berbeda (kasus, tindakan, sesi).

### 2.3 Kategori tindakan bertambah: Kolaborasi

Contoh logbook harian memakai tiga kategori: **Mandiri / Supervisi / Kolaborasi**. Model sekarang hanya punya `jumlah_mandiri` dan `jumlah_supervisi`.

### 2.4 Logbook harian mencatat identitas pasien

Contoh memuat kolom `Inisial Pasien / No. RM` (`An. A (RM: 12-34-56)`) dan kolom `Waktu` per tindakan. Model sekarang hanya punya `tanggal`, tanpa jam dan tanpa rujukan pasien.

## 3. Celah nyata terhadap permintaan

### A. Logbook harian otomatis

| Permintaan | Kondisi sekarang | Jarak |
|---|---|---|
| Entri cepat, auto-fill | Form manual, satu baris per submit | Tidak ada endpoint catat cepat, tidak ada tindakan terakhir dipakai |
| Waktu per tindakan + inisial/No. RM | Hanya `tanggal`, tanpa jam, tanpa rujukan pasien | Perlu kolom `waktu` dan `pasien_ref` (teks, bukan FK) |
| Kategori Mandiri / Supervisi / Kolaborasi | Dua hitungan | Perlu kategori ketiga + label jelas |
| Dropdown tindakan sesuai RKK | Difilter per **profesi**, bukan per **RKK aktif** | Irisan dengan `PenugasanKlinis`/`RincianKewenangan` |
| Shift kerja (Pagi/Siang/Malam) | Tidak ada | Perlu `shift` atau turunan dari `waktu` |
| Paraf/verifikasi preseptor | **Tidak ada** | Model persetujuan + antrean approval |
| Ringkasan tahunan + 3 tahun vs target per kompetensi | Rekap 36 bulan total saja | Perlu agregasi dan matriks target |
| PDF portofolio + halaman pengesahan 3 kolom | Tidak ada | Generator PDF |

### B. Dokumen kredensial otomatis

| Permintaan | Kondisi sekarang | Jarak |
|---|---|---|
| Generate 8 dokumen | Checklist hanya membaca unggahan manual | Generator + simpan sebagai `VersiDokumen` |
| Tombol `Ada / Belum ada / Edit / Download` per baris | Baris ada, aksi belum | Aksi per baris di `pengajuan_saya.html` |
| Draf yang bisa diedit sebelum final | Belum ada | Tabel draf berisi field terstruktur |
| Jejak siapa menandatangani | Belum ada | Model tanda tangan (pemilik, waktu, hash) |
| Nomor surat (mis. `120 / KSM-ANAK / RS-M / X / 2026`) | Belum ada | Penomoran per jenis per tahun, tidak boleh dikarang |

### C. Menu kredensial untuk setiap nakes (permintaan baru)

| Kondisi sekarang | Seharusnya |
|---|---|
| Menu Human Capital hanya muncul bila pengguna punya grant HC (`hc_navigation` di `sdm/context_processors.py`) | Setiap akun yang tertaut ke `Pegawai` melihat menu kredensial pribadinya |
| `kredensial_pengajuan_sendiri` sudah `@login_required` tanpa grant, tapi tidak ada jalan masuk | Perlu entri menu yang selalu tampil |
| Akun nakes tanpa `Pegawai` tertaut tidak bisa mengajukan | Perlu pesan jelas + jalur minta tautan ke SDM |

Ini bukan penambahan hak akses baru: halaman self-service sudah dirancang untuk pemilik data sendiri (lihat docstring `kredensial_pengajuan_sendiri`). Yang hilang hanya navigasinya.

## 4. Batasan yang harus dijaga

1. **Jangan mengarang isi pernyataan.** Untuk dokumen yang sumbernya di luar sistem, hasil generate adalah formulir berisi identitas dengan pernyataan dan tanda tangan yang harus diisi pihak berwenang.
2. **Jangan mengarang nomor surat.** Nomor seperti `120 / KSM-ANAK / RS-M / X / 2026` dibuat dari pola yang disimpan admin, atau dikosongkan.
3. **Jangan mengarang target tindakan.** Matriks target per kompetensi berasal dari SK Komite Kredensial dan wajib diinput.
4. **Data pasien minimal.** Simpan inisial atau nomor RM terpotong saja, bukan identitas penuh, dan hanya bila kebijakan RS mengizinkan.
5. **Verifikasi preseptor bukan paraf kosmetik.** Entri terverifikasi terkunci dan tidak bisa diubah diam-diam.
6. **Menu kredensial nakes tidak membuka data orang lain.** Hanya `Pegawai` milik akun itu sendiri.

## 5. Rencana kerja

Urutan mengikat: fase 1 bisa berdiri sendiri, fase 4 butuh fase 0 dan 2.

### Fase 0 - Keputusan pemilik proses (tanpa kode)

| # | Pertanyaan | Kenapa menentukan |
|---|---|---|
| 0.1 | Matriks target tindakan per kompetensi per profesi/jenjang: sudah ada SK-nya? | Tanpa ini, ringkasan 3 tahun tidak bisa menyatakan tercapai |
| 0.2 | Siapa preseptor/supervisor sah per unit, dan apakah sama dengan grant `can_review_hc_credentials`? | Menentukan desain approval |
| 0.3 | Bolehkah logbook menyimpan inisial/No. RM? Berapa lama disimpan? | Menentukan skema privasi |
| 0.4 | Tanda tangan: paraf gambar, atau jejak elektronik (pengguna + waktu + hash)? | Menentukan model dan bentuk PDF |
| 0.5 | Penomoran surat: pola per jenis, siapa yang mengelola counter? | Menentukan model nomor surat |
| 0.6 | Data catatan disiplin/sanksi etik: apakah akan diisi di sistem atau tetap di luar? | Menentukan apakah Surat Bebas Sanksi bisa digenerate |

### Fase 1 - Logbook harian cepat

| Langkah | Berkas | Bukti |
|---|---|---|
| 1.1 Tambah `waktu`, `pasien_ref`, `kategori` (`M`/`S`/`K`), `shift` | `sdm/models/logbook.py`, migrasi | Migrasi jalan, entri lama default aman |
| 1.2 Endpoint catat cepat (POST JSON satu tindakan, balik kartu ringkas) | `sdm/views.py`, `sdm/urls.py` | Test: entri dibuat, validasi tetap jalan |
| 1.3 Dropdown dari RKK aktif (irisan `PenugasanKlinis`), fallback profesi | `sdm/forms/logbook.py` | Test: pegawai ber-SPK hanya melihat tindakannya |
| 1.4 UI entri cepat satu baris di `logbook_list`, tanpa reload | `templates/sdm/logbook/daftar.html` | Smoke: 3 entri beruntun |
| 1.5 Ringkasan tahunan: volume, rasio M:S:K, distribusi, tren 12 bulan | `sdm/services/logbook.py` | Test agregasi cocok dengan fixture |

### Fase 2 - Verifikasi preseptor

| Langkah | Berkas | Bukti |
|---|---|---|
| 2.1 `VerifikasiLogbook` (entri, verifikator, waktu, catatan, status) | `sdm/models/logbook.py` | Test: verifikasi ulang tidak menghapus jejak |
| 2.2 Resolusi preseptor sah per unit | `sdm/services/` | Test: preseptor unit lain ditolak |
| 2.3 Antrean "menunggu paraf" + setujui/tolak | `sdm/views.py`, template | Smoke: antrean kosong lalu terisi |
| 2.4 Entri terverifikasi terkunci | `sdm/models/logbook.py` | Test: edit setelah verifikasi ditolak |

### Fase 3 - Dokumen kredensial otomatis

| Langkah | Berkas | Bukti |
|---|---|---|
| 3.1 `DrafDokumenKredensial` (jenis, pegawai, isian terstruktur, status, versi hasil) | `sdm/models/kredensial.py`, migrasi | Test: satu draf per (pegawai, jenis) |
| 3.2 Registry 8 jenis: field otomatis, field manual, penanda tangan, perlu nomor surat | `sdm/services/dokumen_kredensial.py` | Test: tidak ada field tanpa sumber |
| 3.3 Generator ReportLab: kop dari `SystemConfig`, identitas dari profil, tabel logbook 36 bulan | service | Test: PDF berisi nama dan nomor pegawai |
| 3.4 Simpan sebagai `DokumenPegawai`+`VersiDokumen` (`PENDING`), tautkan ke checklist | service | Test: baris checklist berubah terpenuhi |
| 3.5 UI `Generate / Edit / Unduh` per baris dokumen pendukung | `pengajuan_saya.html`, view + form | Smoke: generate CV, edit, unduh |
| 3.6 Dokumen berpernyataan: cetak identitas terisi, pernyataan kosong, label penanda tangan jelas | template | Test: PDF tidak memuat klaim yang belum diverifikasi |
| 3.7 Penomoran surat dari pola admin | model + service | Test: nomor unik per jenis per tahun |

### Fase 4 - Portofolio dan tanda tangan

| Langkah | Berkas | Bukti |
|---|---|---|
| 4.1 Matriks target per kompetensi + status tercapai/kurang | `sdm/services/logbook.py` | Test: kurang 1 tindakan tidak dinyatakan tercapai |
| 4.2 PDF portofolio: rekap 36 bulan, tabel target vs realisasi, 3 kolom pengesahan | service + template | Test: total PDF sama dengan layar |
| 4.3 Jejak tanda tangan + halaman verifikasi token | model + view | Test: hash berubah bila PDF diganti |

### Fase 5 - Menu kredensial untuk setiap nakes

| Langkah | Berkas | Bukti |
|---|---|---|
| 5.1 Context processor: tandai `nav_kredensial_pribadi` bila akun punya `pegawai_hc` | `sdm/context_processors.py` | Test: akun ber-pegawai true, akun tanpa pegawai false |
| 5.2 Entri menu "Kredensial saya" + "Logbook saya" di sidebar, di luar blok grant HC | `templates/includes/sidebar.html` | Test: role `STAF_NAKES` melihat menu, pengguna lain tanpa pegawai tidak |
| 5.3 Halaman self-service menampilkan pesan jelas bila akun belum tertaut pegawai | `sdm/views.py`, template | Test: pesan muncul, tidak 500 |
| 5.4 Pastikan menu hanya membuka data milik sendiri | test akses | Test: nakes lain tidak bisa membuka pegawai lain |

Fase 5 sengaja dikerjakan lebih dulu bila ingin cepat terlihat pengguna: perubahannya kecil, tidak menunggu keputusan Fase 0, dan langsung memberi jalan masuk ke logbook dan dokumen yang sudah ada.

## 6. Urutan yang disarankan

1. **Fase 5** dulu (menu kredensial pribadi). Kecil, tanpa keputusan menggantung, langsung berguna.
2. **Fase 1.1 sampai 1.4** (logbook cepat). Mengisi rekap 36 bulan yang sudah dipakai halaman kredensial.
3. **Fase 3.1 sampai 3.5** untuk CV dan Logbook 36 bulan lebih dulu: dua dokumen ini 100% dari data sistem.
4. **Fase 2** dan **Fase 4** setelah matriks target dan definisi preseptor diputuskan.
5. Dokumen yang butuh data luar (Surat Bebas Sanksi, Asesmen Psikologis) dikerjakan paling akhir, dan hanya sebagai formulir cetak.

## 7. Yang tidak akan dikerjakan

- Menyalin HTML/CSS simulasi dari dokumen permintaan; tampilan mengikuti `DESIGN.md`.
- Menambah DRF/React, atau `weasyprint` (ReportLab sudah ada).
- Mengarang nomor surat, NIP ketua KSM, hasil tes psikologi, atau pernyataan bebas sanksi.
- Memasang target tindakan default tanpa sumber.
- Memberi menu kredensial akses ke data pegawai lain.

## 8. Bukti sebelum dinyatakan selesai

| Fase | Bukti |
|---|---|
| 5 | Login sebagai `STAF_NAKES` dengan `Pegawai` tertaut: menu terlihat, halaman terbuka, hanya data sendiri |
| 5 | Login tanpa `Pegawai` tertaut: menu tetap ada, halaman menampilkan instruksi menghubungi SDM |
| 1 | 3 entri beruntun lewat UI; rekap 36 bulan di halaman kredensial ikut bertambah |
| 2 | Entri diverifikasi preseptor unit lain ditolak; entri terverifikasi tidak bisa diedit |
| 3 | Generate CV: PDF berisi nama dan unit benar; baris checklist berubah dari "Belum ada" ke "Terpenuhi" |
| 3 | Generate Surat Riwayat Malpraktik: identitas terisi, pernyataan kosong, label "ditandatangani pegawai" |
| 4 | PDF portofolio: total tindakan sama dengan layar; verifikasi hash menolak PDF lama |

## 9. Lampiran: format keputusan Fase 0

Enam templat di bawah diisi pemilik proses. Sel kosong berarti keputusan belum ada dan batasan yang menyertainya berlaku sampai sel itu terisi. Jangan mengisi angka atau nama sebagai tebakan.

### 0.1 Matriks target tindakan per kompetensi

Bila kosong: kolom `Target 3 tahun` dan `Status` pada PDF logbook tetap kosong, dan sistem tidak pernah menyatakan suatu kompetensi tercapai.

| Profesi | Jenjang | Kode katalog tindakan | Nama tindakan | Satuan | Target 3 tahun | Sumber SK |
|---|---|---|---|---|---|---|
| Perawat (CONTOH, ganti dengan data resmi) | Perawat Ahli Pertama | KAT-000 | Pengkajian dan triase anak | kasus | 350 | SK nomor (contoh) |
| Perawat (CONTOH, ganti dengan data resmi) | Perawat Ahli Pertama | KAT-001 | Terapi obat oral dan injeksi | tindakan | 1200 | SK nomor (contoh) |
|  |  |  |  |  |  |  |

### 0.2 Preseptor per unit

Bila kosong: unit tersebut tidak dapat memverifikasi entri logbook, dan entri tetap berstatus belum terverifikasi.

| Unit kerja | Nama preseptor | Peran (Karu/Katib/DPJP) | Sumber kewenangan |
|---|---|---|---|
|  |  |  |  |

### 0.3 Kebijakan data pasien di logbook

Bila kosong: `pasien_ref` dibiarkan kosong untuk semua entri baru.

```
Penyimpanan pasien_ref (pilih satu):
  [ ] Nomor RM penuh
  [ ] Nomor RM terpotong (mis. 12-34-56 -> 12-34-xx)
  [ ] Inisial saja (mis. An. A)

Masa simpan: ............ (contoh: 5 tahun sejak kunjungan terakhir)
Yang boleh melihat: ............ (peran atau nama unit)
Dasar kebijakan: ............ (nomor SK atau kebijakan privasi RS)
```

### 0.4 Bentuk tanda tangan

Bila kosong: dokumen hasil generate tetap `PENDING` dan tidak boleh diperlakukan sebagai sudah ditandatangani.

```
Pilihan (pilih satu):
  [ ] Paraf gambar tersimpan
      butuh: gambar tanda tangan, pemilik, tanggal berlaku
  [ ] Jejak elektronik
      butuh: akun penanda tangan, waktu, hash dokumen (SHA-256)

Pilihan: ............
Penanggung jawab: ............
```

### 0.5 Penomoran surat

Bila kosong: `nomor_surat` tetap kosong pada PDF hasil generate, dan PDF tidak boleh dipakai sebagai surat bernomor.

| Jenis dokumen | Pola nomor | Pengelola counter |
|---|---|---|
|  | `{urut} / KSM-ANAK / RS-M / {bulan_romawi} / {tahun}` |  |

Pola di atas hanya contoh bentuk. Isi pola resmi, urutan awal counter per tahun, dan siapa yang menaikkan counter.

### 0.6 Data sanksi etik

Bila kosong: `BEBAS_SANKSI` hanya dapat digenerate sebagai formulir tanpa pernyataan dari sistem, dan tidak pernah diterbitkan atas nama sistem.

```
Pilihan (pilih satu):
  [ ] Catatan disiplin diisi di dalam sistem
      peran yang boleh menulis: ............
      siapa yang boleh melihat: ............
  [ ] Catatan disiplin tetap di luar sistem
      dokumen hanya berupa formulir cetak: ya
```

