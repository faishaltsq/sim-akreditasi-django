# STARKES 2024 — parser, sumber teks EP, dan RDWOS

## Status

Paket **persiapan sumber** selesai dan diuji. Katalog aktif, skor, bukti, riwayat, migrasi, dan deployment produksi tidak diubah oleh pekerjaan ini. `models.py`, `catalogue.py`, `catalogue_models.py`, `catalogue_services.py`, serta importer lama tetap menjadi batas integrasi pekerjaan paralel; tidak diedit oleh paket sumber ini.

Artefak adalah **kandidat review**, bukan katalog resmi tervalidasi: `review_status=PENDING_OWNER_REVIEW`, `production_ready=false`, `inventory_is_official=false`. Hitungan hasil parser tidak ditetapkan sebagai target resmi dan tidak dipaksa menjadi hitungan produksi sebelumnya.

## File hasil

| File | Fungsi |
|---|---|
| `akreditasi/starkes_sources.py` | Parser teks EP KMK lengkap, tanpa Django/DB |
| `akreditasi/starkes_survey.py` | Pemisahan sel EP, RDWOS, instruksi, dan skor berdasarkan geometri PDF |
| `akreditasi/starkes_source_fixture.py` | Pembacaan PDF, perakitan lintas halaman, rekonsiliasi, CLI generator |
| `fixtures/standar_akreditasi_2024.sources.json` | Kedua inventaris, teks penuh, halaman, hash, instruksi, tautan kandidat, antrean review |
| `fixtures/standar_akreditasi_2024.sources.manifest.json` | Hash sumber/artefak/CSV dan inventaris terukur |
| `fixtures/standar_akreditasi_2024.sources.review.csv` | 197 catatan review, termasuk anomali; teks kedua sumber, halaman, dan instruksi tersedia untuk pembandingan |
| `akreditasi/tests_starkes_sources.py` | Regresi parser teks dan geometri sel |
| `akreditasi/tests_starkes_source_fixture.py` | Rekonsiliasi, provenance, artefak aktual, dan validasi dokumen |
| `akreditasi/tests_starkes_source_rehearsal.py` | Rehearsal persiapan sumber tanpa query/mutasi DB |
| `akreditasi/source_test_settings.py` | Konfigurasi tes SQLite memory khusus sumber, bukan konfigurasi deployment |
| `docs/qa/starkes-2024-source-verification.json` | Sertifikat snapshot parser murni |
| `docs/qa/starkes-2024-source-isolated-verification.json` | Sertifikat snapshot 46 tes terisolasi, hash file dependensi, dan reproduksi artefak |

Fixture lama `fixtures/standar_akreditasi_2024.json` sengaja **tidak ditimpa**: skemanya berbeda dan konsumen lama tidak boleh menganggap kandidat baru sebagai data yang sudah disetujui. Parser baru juga **belum menggantikan** `parse_pdf`/persistence importer lama. Perbaikan ini belum tampil di web sampai diintegrasikan dan dirilis oleh jalur katalog.

## Provenance

| Peran | Dokumen | Halaman PDF | SHA-256 |
|---|---|---:|---|
| Bunyi EP | KMK HK.01.07/MENKES/1596/2024 | 356 | `22d2247e6a2b272789141536ca4539f99ebb825ad6c7bfe61106d065aa453116` |
| Bukti RDWOS | HK.02.02/D/47104/2024 | 415 | `fde4091e97bd4b9de944994e3764a125bdc83f07d3fba680ecb5023bb478dd80` |

Nomor halaman selalu indeks PDF berbasis 1, bukan nomor cetak yang diasumsikan sama. Nomor keputusan diperiksa sebelum provenance STARKES diberikan. Hash dihitung dari buffer byte yang sama dengan input parser.

Artefak SHA-256: `d155acc178f9cd5d327a6239a160bec1d92efe477f239eadc15e652e8534eaac`. CSV SHA-256: `8d08e46bdb8a8bc16bdf0fb2220c052f82a8a0893c26463228ae9af69e89eb12`.

## Inventaris terukur

| Ukuran | Hasil |
|---|---:|
| EP kandidat dari KMK | 806 |
| EP kandidat dari instrumen survei | 794 |
| Tautan teks cocok setelah normalisasi konservatif | 715 |
| Instruksi bukti terambil, termasuk fragmen belum bertipe | 1271 |
| Instruksi bertipe R/D/W/O/S | 1269 |
| Fragmen instruksi belum bertipe | 2 |
| Bab KMK | 16 |

Angka survei 794 tidak membuktikan identitas atau kelengkapan terhadap 794 EP yang pernah terukur di produksi. Kedua sumber dipertahankan terpisah; persamaan angka bukan persamaan persyaratan.

| Bab KMK | EP kandidat |
|---|---:|
| TKRS | 71 |
| KPS | 81 |
| MFK | 72 |
| PMKP | 44 |
| MRMIK | 51 |
| PPI | 62 |
| PPK | 23 |
| AKP | 67 |
| HPK | 39 |
| PP | 58 |
| PAP | 52 |
| PAB | 38 |
| PKPO | 53 |
| KE | 25 |
| SKP | 24 |
| PROGNAS | 46 |

RDWOS: {"R": 171, "D": 612, "W": 356, "O": 109, "S": 21, "UNTYPED": 2}.

## Perbaikan yang dibuktikan

- Tidak ada pemotongan teks sumber pada 300/500 karakter dalam parser baru. `KPS 10 EP c` mempertahankan bagian EKG/EEG/EMG.
- Judul bab setelah `AKP 6 EP d`, kelompok setelah `KE 7 EP b` dan `SKP 6.1 EP 3`, serta BAB IV/PENUTUP setelah `PROGNAS 6.1 EP 4` tidak ikut menjadi uraian EP.
- Variasi salah eja judul sumber, substandar bertingkat, bullet titik, daftar bertingkat, perpindahan halaman dan rentang huruf yang terbungkus dipertahankan. `PMKP 8 EP o` dan `KPS 2 EP d` hasil salah pemisahan rentang tidak dibuat sebagai EP baru.
- Kolom skor tidak dicampurkan ke uraian EP; huruf dalam instruksi bukti bukan EP baru. Bab PPK dengan sel isi menjorok dan label menggantung tetap terbaca.
- Marker RDWOS yang berada di tengah sel memakai batas selnya. Lanjutan tanpa marker tidak diberi tipe tebakan.
- Pencocokan tidak memakai kode saja, tidak memakai fuzzy similarity sebagai keputusan, dan mempertahankan tanda desimal/ambang numerik: `1.5%` tidak dipadankan dengan `15%`.

## Antrean review

| Alasan | Catatan |
|---|---:|
| `source_code_conflict` | 14 |
| `source_text_diff` | 63 |
| `survey_ep_without_exact_decree_match` | 16 |
| `decree_ep_without_exact_survey_match` | 91 |

Angka alasan adalah jumlah catatan, bukan jumlah EP bermasalah unik; satu EP dapat muncul pada lebih dari satu pemeriksaan. Ada pula 1 urutan label KMK tidak berurutan, 10 duplikasi kode/hint survei, dan 2 fragmen bukti belum bertipe. CSV memuat semuanya tanpa menghapus konflik.

Contoh yang membutuhkan keputusan:

- TKRS 2 pada KMK memakai label `a,b,e`; instrumen memakai `a,b,c` untuk teks yang bersesuaian. Label asli tidak direnumber otomatis.
- `standard_code`/`code` pada inventaris survei adalah **hint judul yang teramati/diwarisi**, bukan identitas kanonis yang sudah disetujui. Bagian tanpa judul eksplisit dapat memiliki nilai null atau hint dari judul sebelumnya; konflik hint diberi catatan. `survey_key` mempertahankan identitas ekstraksi tanpa menggabungkan duplikasi.
- Fragmen belum bertipe berada pada PDF survei halaman 205 dan 325. Teksnya tetap tersimpan; tipe tidak diasumsikan.
- 63 kandidat berkode sama memiliki perbedaan teks; tidak diberi tautan otomatis hanya karena kode sama. 91 EP KMK belum memiliki pasangan teks persis menurut normalisasi saat ini. Ini dapat berupa perbedaan dokumen, kesalahan ekstraksi tersisa, atau kebutuhan disambiguasi; bukan otomatis bukti EP resmi hilang.

Semua 715 tautan yang cocok tetap `PENDING_OWNER_REVIEW`; kecocokan teks tidak mengesahkan penerapan klinis atau aktivasi katalog.

## Verifikasi aktual

- **40 tes parser/artefak murni lulus** pada snapshot terpisah dari working tree paralel.
- **46 tes terisolasi lulus** pada snapshot: 40 tes sumber, 1 rehearsal DB, 5 regresi parser lama. Database `:memory:`, model aplikasi dibuat melalui syncdb; ini bukan pengujian rantai migrasi historis atau cutover.
- Rehearsal menyiapkan dua edisi dengan kode EP sama, skor 5, catatan asesmen, rencana tindak lanjut dan berkas bukti versi 3. Dua eksekusi persiapan sumber menjalankan **0 query DB** dan snapshot baris Framework/Category/StandardItem/QualityRecord/EvidenceReq/EvidenceFile sebelum/sesudah identik.
- Generator kedua atas PDF asli menghasilkan JSON, manifest, dan CSV **identik byte-per-byte**. Hash terikat pada snapshot dan disimpan di sertifikat.
- SQLite memberi `models.W047` pada `LaporanMutu` karena `UniqueConstraint.nulls_distinct` tidak didukung; ini dicatat, bukan disamakan dengan validasi constraint PostgreSQL.

Upaya verifikasi yang lebih luas juga dicatat, tidak diklaim hijau:

1. Rantai migrasi historis pada DB memory gagal di `akreditasi.0019_setup_cssd`: `NOT NULL constraint failed: akreditasi_standarditem.code` melalui command legacy. File migrasi/command tersebut tidak diubah.
2. Upaya berikutnya dengan konfigurasi aplikasi penuh tertahan `models.E034`: indeks `sdm_presensi_assignment_time_idx` melebihi 30 karakter pada perubahan presensi paralel. Modul SDM tidak diubah untuk melewati pemeriksaan ini.

## Reproduksi

Dari root repo, gunakan interpreter proyek:

```bash
.venv/Scripts/python.exe -m akreditasi.starkes_source_fixture \
  --decree 'C:/Users/cubeb/Downloads/starkes 2024.pdf' \
  --survey 'C:/Users/cubeb/Downloads/instrumen standar survey akreditasi  rs 2024.pdf' \
  --output 'fixtures/standar_akreditasi_2024.sources.json'

.venv/Scripts/python.exe -m unittest \
  akreditasi.tests_starkes_sources akreditasi.tests_starkes_source_fixture -q

DJANGO_SETTINGS_MODULE=akreditasi.source_test_settings .venv/Scripts/python.exe -m django test \
  akreditasi.tests_starkes_sources akreditasi.tests_starkes_source_fixture \
  akreditasi.tests_starkes_source_rehearsal akreditasi.tests_starkes_2024.EpExtractionTests \
  --verbosity 1
```

## Serah-terima integrasi

### Done

Parser murni, fixture kandidat penuh berprovenance, RDWOS terpisah, rekonsiliasi konservatif, CSV review, pengujian snapshot dan rehearsal non-mutasi selesai. Tidak ada dependensi Python baru.

### Not done, needs catalogue owner / live environment

Review substansi dan penerapan EP; pemutusan konflik label/hint; penyelesaian fragmen bukti; adapter JSON ke jalur staging katalog; penyimpanan teks penuh tanpa limit importer lama; verifikasi identitas `(framework/category, code)`; rehearsal **penerapan** yang sungguh-sungguh; pengujian PostgreSQL, UI terautentikasi, aktivasi, dan deployment produksi belum dilakukan. Rehearsal persiapan sumber tidak menggantikan pengujian penerapan tersebut.

### Skipped on purpose

Tidak mengganti models/catalogue yang sedang dikerjakan paralel. Tidak memakai `loaddata` atau importer lama untuk kandidat JSON ini. Tidak melakukan migrasi database kerja/produksi, mutasi data produksi, pemindahan skor berbasis kode, reset asesmen, commit, push, atau deployment. Keputusan aktivasi harus mengikuti hasil review, bukan hitungan parser.
