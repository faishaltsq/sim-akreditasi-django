# Analisis Pelaksanaan Asuhan, CPPT Multiprofesi & Billing IGD

**Tanggal:** 13 November 2026.
**Status:** analisis dan rencana tambahan; tidak mengubah kode aplikasi atau production.
**Sumber:** `C:/Users/cubeb/Downloads/pelaksanaan dan cppt.docx`.
**SHA-256:** `0c8ab23a74b58b13872292909fc867a637f216e7157d922782593179b3233551`.
**Cakupan ekstraksi:** 249 baris teks, termasuk tabel profesi versi awal dan pembaruannya; satu gambar tertanam `word/media/image1.png` diekstrak dan diperiksa visual. Nomor baris di bawah mengacu hasil ekstraksi, bukan halaman Word.
**Git:** HEAD `112a7b3357168ec53aac6cb4c6670b8bcab86f66`; source working tree sedang berubah oleh workstream clinical-expansion dan berisi implementasi fisik yang belum di-commit. HEAD bukan seluruh source yang dibaca.
**Roadmap baru:** `../plans/2026-11-13-igd-professional-care-roadmap.md`.

## 1. Kesimpulan

Dokumen mengubah langkah 9 menjadi pelaksanaan multiprofesi dengan kewenangan RKK/SPK, tarif menurut profesi/jenjang, CPPT berbagai format, serta billing yang dapat ditelusuri. Ini bukan sekadar menambah dropdown profesi pada form SOAP.

**Sebagian fondasi sudah ada:** rencana tindakan, pelaksanaan eksplisit, CPPT otomatis, penulis terautentikasi, waktu pelaksanaan, billing terkait tindakan, version dan replay idempoten. **Yang belum terhubung:** grade/RKK individual, komponen jasa sarana/pelayanan, profesi selain dokter/perawat/bidan pada dispatcher, draf CPPT versus persetujuan, format ADIME/spiritual, verifikasi DPJP terikat akun/isi, serta ringkasan tagihan aktual per profesi.

Rekomendasi: pertahankan `TindakanAsesmen`, `CPPT`, `BillingItem`, resep dan order sebagai domain canonical. Reuse master profesi/jenjang HC yang sudah ada. Pecah pelaksanaan menjadi fondasi kewenangan/tarif → CPPT multiprofesi → eksekusi/billing/UI. Jangan menyalin contoh tarif dan nama petugas menjadi data production.

## 2. Bukti visual

Screenshot dokumen memperlihatkan langkah 9, ringkasan estimasi medis/keperawatan, pesan tidak ada rencana tindakan, dan awal form Tambah CPPT. Ia belum memperlihatkan cascading profesi–jenjang–petugas, rincian komponen tarif, atau form ADIME. Bagian bawah layar tidak seluruhnya terlihat, sehingga ketiadaan kontrol yang berada di luar gambar tidak disimpulkan hanya dari screenshot. Tidak disalin identitas pasien atau petugas yang tampak.

## 3. Traceability kebutuhan

| ID | Baris sumber | Kebutuhan | Status/delta |
|---|---|---|---|
| PC01 | 5–8,118 | Ambil rencana langkah 8 atau tambah tindakan langsung | Plan/execute ada; langkah 9 belum punya form tambah langsung yang memakai kewenangan/tarif multiprofesi. |
| PC02 | 9–82,171–249 | Profesi → jenjang → petugas/tindakan sesuai RKK | Master HC sudah ada; belum digunakan oleh eksekusi IGD. Jenjang bukan bukti kewenangan individual. |
| PC03 | 82,124–128 | Jasa sarana + pelayanan sesuai profesi/jenjang | Resolver sekarang memakai unit/kode/penjamin; tidak punya komponen profesi/grade. Perlu master harga efektif yang ditinjau. |
| PC04 | 123 | Quantity dan waktu aktual | Decimal quantity dan timestamp tersedia; snapshot pelaksana/grade/supervisi saat pelayanan belum lengkap. |
| PC05 | 8,162–167 | Eksekusi menghasilkan draf log CPPT | Sudah membuat CPPT SOAP, tetapi belum memiliki status draf/submit dan format multiprofesi; jangan menjadikan log otomatis sebagai asesmen lengkap. |
| PC06 | 110–116,129–161 | Estimasi dan tagihan aktual per profesi/obat | Ringkasan sekarang menjumlah tindakan planned/performed; harus dipisahkan dari ledger tagihan, termasuk pending/zero/void. |
| PC07 | 145,153,161 | Aksi Hapus | Hapus riwayat tindakan/charge yang sudah terlaksana tidak diterima sebagai hard-delete. Gunakan pembatalan rencana atau void/reversal beralasan yang tetap dapat diaudit. |
| PC08 | 163–165 | SOAP lintas PPA dan identitas penulis | Model memiliki beberapa profesi, dispatcher hanya mengizinkan empat profesi klinis; bukan cukup menambah enum. |
| PC09 | 166 | ADIME untuk gizi | Belum ada format/payload terstruktur ADIME; diagnosis gizi tidak boleh ditulis seolah ICD-10 medis. |
| PC10 | 167 | Catatan spiritual | Belum ada format/profesi spesifik; tidak mewarisi kewenangan medis. |
| PC11 | 168 | Verifikasi DPJP setiap CPPT PPA | Saat ini boolean otomatis true untuk setiap pencatat dokter; tidak membuktikan DPJP episode, verifikator, waktu atau digest isi. |
| PC12 | Integrasi | Farmasi/penunjang tidak double-charge | Workstream resep/penunjang sedang berubah; adapter langkah 9 hanya membaca status owner. Tidak mengulang billing dispensing/order sebagai tindakan baru. |
| PC13 | Integrasi | Hak akses dan supervisor | Dropdown tidak boleh membuat actor mengaku sebagai orang lain; recorder/performed-by/supervisor harus berbeda dan tervalidasi bila delegasi disetujui. |
| PC14 | Integrasi | Snapshot final, koreksi dan replay | Perlu memasukkan konteks profesi/tarif/status catatan/verifikasi/void ke snapshot; old final tidak fallback ke data hidup. |

## 4. Source yang ditelusuri

- `pasien/services/igd_actions.py`: `plan_action` menulis rencana; `execute` sudah membuat CPPT dan billing sekali serta menyimpan pelaksana. `perform_action` mengunci kunjungan dan memakai request UUID/digest. Guard awal hanya menerima dokter umum/spesialis, perawat/bidan. CPPT memetakan selain dokter/perawat menjadi BIDAN dalam jalur tersebut.
- `pasien/forms_igd_operations.py`: `CpptForm` hanya SOAP; `ActionExecutionForm` memiliki action ID, occurred-at dan alasan retrospektif, belum performer/grade/tariff quote.
- `klinis/services/tarif.py`: `resolve_detail(kunjungan, icd9_kode)` memakai kelompok/unit dan BPJS/umum; tidak menerima profesi atau jenjang. Resolver historis memiliki jalur rekonsiliasi berbasis daftar kode yang menghapus item omitted; jangan gunakan itu untuk event pelaksanaan baru.
- `pasien/models.py`: `CPPT.PROFESI` sudah meliputi FARMASI/GIZI/REHAB/LAINNYA, tetapi enum tidak berarti akses IGD sudah tersedia. `verifikasi_dpjp` hanya boolean. `KunjunganPasien.dpjp` adalah teks, bukan relasi akun yang dapat menjadi otorisasi tanda tangan.
- `accounts/models.py`: profesi akun meliputi NUTRISIONIS/APOTEKER dan lainnya, tetapi dokter gigi, rohani dan akupunktur tidak mempunyai mapping khusus yang siap dianggap berwenang. Mapping ke HC harus ditinjau.
- `sdm/models/pegawai.py`: `Pegawai.akun`, `profesi_master`, **`jenjang_master` sudah ada**. Tidak perlu membuat kolom grade kedua. `MasterJenjangProfesi` terikat satu profesi; grade lintas profesi ditolak.
- `sdm/models/katalog_rkk.py`: `KatalogTindakan` menggunakan kode RKK sendiri dan level supervisi M/S/MT/T; bukan otomatis kode ICD9/SIKI atau tarif jasa.
- `sdm/services/clinical_access.py`: `effective_privileges(employee, unit, at)` mengembalikan controlled action codes dari snapshot bertanggal; tidak otomatis membuktikan kewenangan prosedur spesifik. Adapter perlu memeriksa sumber SPK/decision masih berlaku. `require_clinical_action` juga memerlukan izin direktori HC; jangan menuntut semua PPA mendapat akses direktori HR hanya agar dapat menulis CPPT.
- `templates/pasien/_igd_workflow_operations.html`: daftar planned/performed, tombol execute dan form SOAP ada; ringkasan belum ledger/profesi empat kategori. UI global readonly tidak boleh dibuka untuk ahli gizi hanya demi mengaktifkan satu form CPPT.
- `pasien/services/prescriptions.py` adalah source WIP: penyelesaian dispensing membuat billing obat per item. Ini tetap dimiliki plan farmasi; langkah 9 hanya membaca ledger/status tersebut, bukan membuat tagihan obat kedua.
- Reader keuangan yang perlu ikut konsisten bila void diaktifkan ditemukan pada `pasien/models.py`, `pasien/views.py` (detail, discharge, recap/aggregate), `pasien/pdf_utils.py`, `pasien/services/igd_finalization.py`, dan workflow context. Menambah tombol void tanpa memperbaiki reader akan menghasilkan total yang berbeda.

## 5. Data production: metadata dan aggregate saja

Pembacaan dilakukan tanpa identitas pegawai/pasien, tanpa isi CPPT, dan tanpa write.

| Pemeriksaan | Hasil |
|---|---:|
| Master profesi HC | 23 |
| Master jenjang | 118 |
| Katalog tindakan RKK | 499 |
| Baris pegawai | 24 |
| Pegawai terhubung akun | 24 |
| Pegawai terhubung grade | 9 |
| Grade/profesi mismatch pada yang terhubung | 0 |
| SPK terbit | 0 |
| PrivilegeSnapshot | 0 |
| Rincian kewenangan individual | 0 |
| Baris harga `KasusTindakan` | 0 |
| Tindakan asesmen | 0 |
| CPPT per profesi | DOKTER 4; PERAWAT 5 |

Angka pegawai adalah baris aplikasi, bukan sensus tenaga RS terverifikasi. Tidak boleh menganggap akun demo/seeder sebagai pelaksana klinis nyata. **Master 499 tindakan tidak sama dengan 499 kewenangan individual atau master tarif terisi.** Gate RKK ketat belum layak langsung dinyalakan pada production sebelum pemilik data melengkapi assignment/privileges dan harga yang disetujui.

### Perbedaan master terhadap dokumen

- Dokter gigi tersedia sebagai profesi dengan 3 grade, tetapi **0 tindakan RKK**. Jangan diam-diam menawarkan seluruh tindakan dokter umum.
- Apoteker memiliki 2 grade, bukan otomatis tiga kategori yang diminta dokumen.
- Dietisien, nutrisionis, fisioterapi, radiografer, ATLM, psikologi dan terapi wicara masing-masing memiliki 4 grade; bukan angka level yang sama dengan contoh UI.
- Perawat mempunyai 5 grade dan bidan 5 grade; **Pra-PK tidak otomatis tersedia** dan grade perawat tidak boleh dipakai untuk bidan tanpa keputusan katalog.
- Dokter spesialis memiliki 32 grade pada master yang dibaca; jangan meratakan seluruh spesialisasi ke label universal Sp.1/Sp.2 tanpa mapping eksplisit.
- Tidak ada profesi Bina Rohani atau Akupunktur pada 23 master yang dibaca. Perlu master/kompetensi/penugasan yang ditinjau; agama pendamping bukan level kompetensi. Tidak otomatis memerlukan atau memperoleh kewenangan prosedur medis.
- KPS/RKK pada sumber adalah referensi umum, tanpa EP spesifik; plan ini tidak menciptakan kode atau klaim kepatuhan otomatis.

## 6. Keputusan desain dan tradeoff

1. **Reuse HC, bukan tabel profesi/grade baru.** Tambahkan mapping layanan profesional–katalog kewenangan yang ditinjau. Tradeoff: ketersediaan fitur tergantung kualitas data HC, ditampilkan sebagai belum dikonfigurasi, bukan daftar kosong tanpa penjelasan.
2. **Self-performance default.** Pencatat dan pelaksana default akun login terhubung pegawai. Pemilihan petugas lain hanya jika policy delegasi terpisah diaktifkan dan diaudit, dengan supervisor yang memenuhi kewenangan bila diperlukan. Admin tarif tidak otomatis menjadi klinisi.
3. **Tarif berversi per layanan/unit/penjamin/profesi/grade/periode.** Sarana dan pelayanan adalah Decimal; snapshot dibekukan saat eksekusi. Rp0 yang disahkan berbeda dengan harga belum tersedia. Tradeoff: perlu pemilik harga dan kebijakan efektif, tidak bisa diisi dari contoh nominal dokumen.
4. **CPPT otomatis adalah draf.** Isi hanya fakta event tindakan yang benar-benar terjadi; S/O/A yang tidak dicatat tetap kosong. PPA melengkapi dan submit/sign secara eksplisit. Tradeoff: tidak langsung menjadi catatan tervalidasi hanya karena tombol eksekusi diklik.
5. **DPJP explicit.** Relasi akun DPJP/penugasan pengganti perlu dibentuk dari assignment terverifikasi, bukan kecocokan nama teks. Counter-signature terikat versi/digest catatan; dokter penulis biasa tidak otomatis memverifikasi semua PPA.
6. **Billing tetap satu ledger.** Tindakan profesional memakai `BillingItem` sekali; obat tetap ditagih owner dispensing, jasa lab/radiologi oleh owner order/result sesuai policy. Ringkasan membedakan planned estimate, posted gross, void dan net. Tradeoff: adapter kategori historis yang ambigu harus berlabel historis/tidak terpetakan.
7. **Tidak hard-delete performed care.** Plan cancellation untuk yang belum dilakukan; full void/reversal beralasan untuk salah pencatatan yang memenuhi policy, dengan bukti original tetap tersimpan dan seluruh total reader konsisten. Refund pembayaran dan partial credit di luar scope ini.

## 7. Pembagian plan dan batas ownership

- Roadmap baru: `2026-11-13-igd-professional-care-roadmap.md`.
- A: `2026-11-13-igd-professional-tariffs-privileges.md` — profesi/jenjang, eligible performer, mapping kewenangan, master harga dan quote.
- B: `2026-11-13-igd-multiprofessional-cppt.md` — SOAP/ADIME/spiritual, status draf/sign, DPJP assignment/verifikasi dan historical read.
- C: `2026-11-13-igd-care-execution-billing.md` — integrasi rencana/langsung, atomic execute→draft CPPT→billing, ringkasan/void/UI.

Urutan A → B → C; shared files single-writer. Plan diagnosis/actions, farmasi, dan ancillary tetap memiliki produksi rencana, resep, dispensing serta ordernya. Source aktif sudah lebih jauh daripada execution note klinis yang masih menyatakan isolated tracer; **kode aktual dan handoff owner harus diperiksa lagi sebelum mulai**, bukan menganggap status markdown lengkap/current. Dokumen baru ini tidak mengubah plan/workstream orang lain dan tidak mengizinkan menimpa shared files yang sedang ditulis.

## 8. Baseline dan batas verifikasi

Perintah lokal dengan SQLite eksplisit: `DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python manage.py test pasien.tests_igd_workflow_integration klinis.tests.test_tarif_service --keepdb --noinput`.

Baseline terarah berhasil: 18 tes, exit 0. Run penutup setelah penulisan plan lulus dalam 6.407 detik waktu tes; SHA-256 file sumber yang diawasi sama sebelum/sesudah run tersebut. Log dan manifest disimpan di scratch sebagai `step9-plan-close-baseline.log` dan `step9-plan-close-source.json`. Ini hanya fondasi action/tarif lama, bukan acceptance fitur multiprofesi baru, bukan full suite, dan bukan bukti deployment. Source workstream lain tetap mutable; executor wajib membekukan snapshot/handoff lalu mengukur ulang. Bukti klinis fisik 429 tes sebelumnya tidak dipakai sebagai sertifikasi source expansion saat ini.

Keempat plan baru lulus pemeriksaan struktur fence, Python AST dan label modul tes (termasuk file tes yang secara eksplisit direncanakan). Ini validasi statis dokumen, bukan eksekusi contoh implementasi atau pengujian fitur yang belum dibuat.

**Tidak dilakukan:** edit kode aplikasi, seed/migrasi operational, penambahan nominal tarif/privilege, penciptaan data pasien production, eksekusi klinis, tanda tangan, billing/void, commit, push atau deploy.
