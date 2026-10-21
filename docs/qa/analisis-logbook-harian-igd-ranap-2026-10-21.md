# Analisis: Logbook Harian IGD & Rawat Inap (ARIMA)

**Sumber:**
- `C:\Users\cubeb\Downloads\logbook harian igd.docx` (222 baris diekstrak)
- `C:\Users\cubeb\Downloads\logbook harian rawat inap.docx` (243 baris diekstrak)

**Rumah Sakit:** RS Monsiskami ARIMA, Jl. Candiwulan, Mangli, Kuwarasan, Kebumen.
**Tanggal analisis:** 21 Oktober 2026
**Plan implementasi:** `docs/superpowers/plans/2026-10-21-logbook-harian-igd-ranap.md`

---

## 1. Ringkasan kedua dokumen

Keduanya adalah **formulir cetak per shift**, bukan per hari: satu lembar = satu unit + satu tanggal + satu shift (Pagi 07.00–14.00, Siang 14.00–21.00, Malam 21.00–07.00). Strukturnya identik di 5 seksi, hanya isi seksi I–II yang berbeda klinis.

| Seksi | IGD | Rawat Inap |
|---|---|---|
| Header | tanggal, shift, nama perawat/dokter jaga, PJ shift (Katim/Karu) | ruangan + kelas, tanggal, shift, PJ shift, jumlah perawat jaga, rasio perawat:pasien |
| I. Rekap | 4 kategori triage (Merah/Kuning/Hijau/Hitam) + total masuk + indikator shift (Response Time Dokter ≤5 mnt, LOS ≤6 jam, ranap, rujuk/pulang/APS, meninggal di IGD) | Sensus & BOR shift (sisa shift lalu, masuk/transfer in, keluar/rujuk/meninggal, total akhir, BOR %) + kategori dependency (Mandiri/Partial/Total Care) |
| II. Tabel pasien | jam masuk & triage, nama/tgl lahir/RM, kategori triage & resp. time, diagnosa awal & keluhan, prosedur & intervensi (IVFD/injeksi, EKG/nebula, rawat luka/hecting, pasang DC/NGT), HPK & informed consent, edukasi (materi & penerima), jam keluar & LOS, tindak lanjut, TTD petugas | no bed, nama & RM, DPJP, diagnosa utama, skala nyeri (0–10) & risiko jatuh (R/S/T), prosedur (injeksi/IVFD, rawat luka, DC/NGT, transfusi), HPK & GC (HPK teredukasi, GC terdokumentasi, privasi khusus), edukasi (obat, nutrisi/diet, manajemen nyeri; penerima pasien/keluarga), jam operan/status handover (SBAR sesuai, CPPT terisi) |
| III. Checklist akreditasi | A HPK (3 item) + B KE (2 item) + C SKP/PKPO (3 item: identifikasi 2 penanda, troli & kit resusitasi + no segel, obat high alert/sitostatis/LASA) | A HPK (3) + B KE (3) + C SKP (3: identifikasi, high alert/double check transfusi, troli/kit ruangan) |
| IV. IKP & komplain | teks bebas, "diisi jika ada KNC/KTD, jatuh dari brankar, penundaan rujukan, komplain, kerusakan alat" | teks bebas, "diisi jika KNC/KTD, jatuh, re-pemasangan infus/DC, komplain, kendala fasilitas" |
| V. Handover SBAR | pasien kritis/resusitasi, pending bed, pending rujukan, pending lab/rad/tindakan; lembar pengesahan 3 peran × 2 shift + jam handover | pasien kritis/memburuk, rencana operasi/prosedur invasif, penunjang/lab/edukasi pending; lembar pengesahan sama |

Rasio kesamaan struktur sangat tinggi (~80%). Keputusan: **satu keluarga model** dengan penanda `jenis` (`IGD` / `RANAP`), template merender seksi I–II per jenis, seksi III–V dipisah kode checklist per jenis.

---

## 2. Pemetaan field → model yang sudah ada

Prinsip: **jangan minta petugas mengetik ulang data yang sudah ada di EMR.** Setiap kolom di bawah dicek langsung terhadap kode & data dev.

### 2.1 Diturunkan (derived — dihitung, bukan diinput)

| Kolom dokumen | Sumber nyata di aplikasi | Status |
|---|---|---|
| Jam masuk / jam keluar / LOS | `KunjunganPasien.tanggal_masuk` (`DateTimeField`), `tanggal_keluar` | ✅ sudah ada |
| Kategori triage (Mera/Kuning/Hijau/Hitam) | `KunjunganPasien.triage` — `TRIAGE_CHOICES` identik 4 opsi | ✅ sudah ada |
| Triase ATS/ESI (untuk catatan ESI 1–5 di indikator) | `KunjunganPasien.triage_kategori` (`KATEGORI_1..5`) | ✅ sudah ada |
| Response Time Dokter | `KunjunganPasien.waktu_asesmen_dokter` (`CharField` 'WIB') + `tanggal_masuk` | ⚠️ perlu parse `HH.MM`/`HH:MM` |
| Diagnosa awal / diagnosa utama | `KunjunganPasien.diagnosa_masuk` (ICD-10) | ✅ sudah ada |
| DPJP | `KunjunganPasien.dpjp` (`DPJP_CHOICES` 30 nama) | ✅ sudah ada |
| Tindak lanjut (Ranap/Rujuk/Pulang/APS/DOA) | `KunjunganPasien.status` (`PULANG`,`RUJUK`,`RANAP`,`MENINGGAL`) + `disposisi` (`RAWAT_INAP`,`PAPS`,`RUJUK`) | ✅ sudah ada |
| Skala nyeri N 0–10 | `KunjunganPasien.ttv_skala_nyeri` | ✅ sudah ada |
| Risiko jatuh R/S/T | `KunjunganPasien.skrining_jatuh_grade` (`RENDAH/SEDANG/TINGGI`) | ✅ sudah ada, perlu pemetaan → R/S/T |
| Dependency (Mandiri/Partial/Total) | `KunjunganPasien.fungsional_adl` — help_text: *Mandiri / Bantuan Parsial / Ketergantungan Total* | ✅ sudah ada, perlu pemetaan |
| "CPPT Terisi" | `CPPT` (FK `kunjungan`) — `CPPT.objects.filter(kunjungan=k).exists()` | ✅ sudah ada |
| "GC Terdokumentasi" (rawat inap) | `GeneralConsentRawatInap` (FK `kunjungan`, field `waktu_persetujuan`) | ✅ sudah ada |
| "General Consent ditandatangani" (IGD) | `KunjunganPasien.general_consent` (Boolean) | ✅ sudah ada |
| BOR shift | point-in-time census dari `KunjunganPasien` × `bed__ruangan`, dibagi `Ruangan.kapasitas` | ✅ bisa dihitung |
| Sisa pasien shift lalu / total akhir shift | `KunjunganPasien` dengan `tanggal_masuk < awal` dan (`tanggal_keluar` NULL atau ≥ awal) pada ruangan/ICU | ✅ bisa dihitung |
| No. bed / nama / no. RM | `Bed.kode_bed`, `Pasien.nama_lengkap` (cek field), `Pasien.no_rm` | ✅ sudah ada |
| Segel troli & kit resusitasi | tidak ada di EMR → input manual + foto bukti | ⚠️ input manual |

### 2.2 Diinput manual (memang hanya ada di logbook)

- Petugas jaga, PJ shift, jumlah perawat, rasio perawat:pasien, jam handover.
- Prosedur/intervensi per baris (checkbox): logbook adalah satu-satunya tempat tindakan shift-harian dicatat eksplisit.
- HPK & Informed Consent per baris (di IGD: `general_consent` menutup sebagian, tapi IC per tindakan tidak ada).
- Edukasi per baris: materi + penerima (tidak ada di EMR; `CPPT.plan` bukan pengganti).
- Item checklist seksi III + bukti foto/dokumen.
- Kejadian khusus / IKP ringkas (seksi IV).
- Rincian handover (seksi V).

---

## 3. Gap: apa yang belum ada di aplikasi

| # | Gap | Dampak | Keputusan |
|---|---|---|---|
| 1 | **Tidak ada model shift sama sekali.** `grep -i shift` di `akreditasi/models.py` & `risiko_models.py` = 0 | Seluruh logbook berdiri di atas entitas baru | Buat `LogbookHarian` (jenis, ruangan, tanggal, shift) + helper `shift_window()` |
| 2 | **`Ruangan` tidak punya FK ke `UnitKerja`** | Scope akreditasi/RBAC (`unit_scope_ids`) tidak bisa diwarisi dari ruangan | Logbook membawa **keduanya**: `unit` FK (untuk scope) + `ruangan` FK (opsional, untuk data klinis) |
| 3 | **`EvidenceFile.requirement` non-nullable** (`FK EvidenceReq`) | Bukti logbook tidak bisa memakai `EvidenceFile` | Buat `LogbookBukti` sendiri, reuse `validate_uploaded_file` + `upload_to_supabase_storage` + `AuditLog` |
| 4 | **`KunjunganPasien.waktu_asesmen_dokter` masih `CharField`** 'HH.MM' | Response Time tidak bisa dihitung langsung | Helper `parse_jam()` toleran `.`/`:`; kalau kosong → RT kosong, indikator dihitung atas baris yang punya jam |
| 5 | **Sebaran data dev sangat tipis** (1 kunjungan IGD, 3 RANAP, 46 bed, 3 bed terisi) | Uji otomatis tidak boleh bergantung pada data dev | Semua test membuat fixture sendiri (pola `tests_mutu_laporan.py: _unit/_ind/_user`) |
| 6 | **Shift MALAM lintas tengah malam** | Query rentang biasa (`tanggal_masuk__date=tanggal`) salah | `shift_window()` mengembalikan `(awal, akhir)` aware datetime; shift MALAM `akhir = tanggal + 1 hari 07.00` |
| 7 | **`rekap_ikp()` di `mutu_laporan.py` membaca `InsidenKeselamatan`** | Seksi IV logbook tidak akan muncul di laporan mutu kalau tidak disinkronkan | `LogbookKejadian.sync_ke_ikp()` membuat row `InsidenKeselamatan` — otomatis ikut rekap & laporan |

---

## 4. Temuan pada formulir (kualitas dokumen)

1. **Matriks seksi I IGD nyampur.** Baris indikator "Response Time Dokter (≤5 menit)" menempel di baris **Merah**, "LOS IGD (≤6 jam)" di baris **Kuning**, "Pasien Ranap" di baris **Hijau**, "Rujuk/Pulang/APS" di baris **Hitam**. Padahal keempatnya indikator **shift**, bukan atribut warna triage. Digital: seksi I dipecah jadi dua blok — (a) rekap triage, (b) tabel indikator shift.
2. **Hanya 2 baris tabel template** di kedua dokumen, padahal beban nyata IGD satu shift bisa 10–30 pasien. Digital: tabel dinamis (tambah baris / auto-tarik dari EMR).
3. **"DOA" (Hitam) dan "Pasien Meninggal di IGD" dihitung terpisah** — dokumen membedakan DOA saat datang vs meninggal dalam perawatan. Digital: dua field berbeda, jangan digabung.
4. **Ejaan "Hecting"** (dari *hecting/stitching*) dan "Response Time" ditulis `RT`. Pertahankan label sesuai formulir agar petugas mengenali kolom, pakai istilah teknis di keterangan.
5. **Checklist "Troli/Kit" punya nomor segel + alasan terbuka** — ini item paling sering diminta surveyor K3RS, jadi wajib menyimpan `segel_no` + `segel_status` + `alasan`, bukan sekadar centang.
6. **Sebagian besar seksi III "Bukti = Upload bukti"** — 9 dari 10 item meminta lampiran. Upload harus serendah mungkin (1 klik, dari dalam baris checklist).
7. **Lembar handover tidak mencantumkan jam di dokumen IGD untuk kolom "Mengetahui"** — ada 3 baris jam handover untuk 3 peran. Digital: satu `jam_handover` +3 nama/ttd.
8. **Rawat inap punya "Jam Operan / Status Handover" per pasien**, IGD tidak. Berarti operan pasien antar shift di ranap wajib per baris (`jam_operan`, `sbar_ok`, `cptt_terisi`).

---

## 5. Keputusan desain

| # | Keputusan | Alasan | Alternatif yang ditolak |
|---|---|---|---|
| 1 | Satu modul `akreditasi/logbook_models.py` + `akreditasi/logbook.py`, **tanpa** menambah logika ke `akreditasi/views.py` (2.832 baris) | Ikuti pola `mutu_laporan.py`, `indikator_views.py`, `kontrol_views.py` | Menambah ke `views.py` → file makin tak terkendali |
| 2 | Satu `LogbookHarian` dengan `jenis` IGD/RANAP, bukan dua model | Seksi III–V identik; duplikasi model = duplikasi migrasi & view | Dua model terpisah |
| 3 | Pasien ditarik dari `KunjunganPasien` (**auto-tarik** per jendela shift), baris menyimpan hanya kolom khas shift | Menghapus ketikan ulang nama/RM/triage/diagnosa/DPJP; angka rekap dijamin konsisten dengan EMR | Form bebas tanpa relasi → angka rekap bisa bohong |
| 4 | Rekap seksi I **dihitung**, bukan diinput (triage, LOS, RT, BOR, sensus) | Form kertas minta angka manual → selisih dengan EMR; digital harus 1 sumber kebenaran | Input manual seperti formulir |
| 5 | Seksi IV menulis ke `InsidenKeselamatan` yang sudah ada | Langsung masuk `rekap_ikp()` dan laporan mutu tanpa kode tambahan | Model IKP baru → data terpecah |
| 6 | Workflow ringan: `DRAF → DIISI → DISETUJUI` (Karu mengetahui) | Form kertas punya lembar pengesahan; wajib ada penanda "sudah diserahterimakan" | Tidak ada status → tidak ada bukti serah terima shift |
| 7 | `ruangan` `null=True` + guard duplikat di `save()` (pola `LaporanMutu.save()`) | IGD punya 2 ruangan (IGD-01 resus, IGD-02 observasi) tapi **satu** logbook IGD; `UniqueConstraint` dengan NULL tidak bekerja di SQLite | UniqueConstraint DB → logbook IGD jadi dua |
| 8 | Scope pakai `unit_scope_ids()` (2 turun + 2 naik) dari `akses_indikator.py` | Konsisten dengan Evaluasi, Monev, Laporan Mutu | Scope turun saja → Kepala IRIN tidak melihat bangsal |

### Cakupan pendaftar (RBAC)

Role yang ada: `SUPER_ADMIN`, `ADMIN_RS`, `KOORDINATOR_POKJA`, `KEPALA_UNIT`, `STAF_NAKES`, `ASESOR`.

| Aksi | Role |
|---|---|
| Membuka/mengisi logbook, menarik pasien, unggah bukti | `SUPER_ADMIN`, `ADMIN_RS`, `KEPALA_UNIT`, `STAF_NAKES` (dengan lingkup unit cocok) |
| Melihat daftar & detail | Semua role login; `ASESOR` hanya setelah `DISETUJUI` |
| Serah terima (`DIISI`) | Yang mengisi + `KEPALA_UNIT`/`ADMIN_RS`/`SUPER_ADMIN` |
| Pengesahan Karu (`DISETUJUI`) | `KEPALA_UNIT` (unit cocok), `ADMIN_RS`, `SUPER_ADMIN` — **bukan** `STAF_NAKES` |

---

## 6. Dampak ke modul lain

| Modul | Dampak |
|---|---|
| `rekap_ikp()` (`mutu_laporan.py:950`) | Ikut menghitung kejadian dari logbook tanpa perubahan kode, karena menulis ke `InsidenKeselamatan` |
| Laporan Mutu (bulanan/semester/tahunan) | Tidak berubah. Logbook adalah sumber data operasional, bukan indikator |
| Dasbor Integrated Control (`kontrol_data.py`) | Nol perubahan — snapshot sudah membaca `InsidenKeselamatan` & `KunjunganPasien` |
| Sidebar & URL | Tambah 1 entri menu + 13 path `logbook/*` |
| Migration | 1 migration baru (5 model) — **harus dijalankan manual saat deploy** (konsesi deploy Vercel tidak auto-migrate) |

---

## 7. Data dev untuk pengujian (hasil probe, bukan asumsi)

```
Ruangan : IGD-01 (Resusitasi & Triase, kap 4), IGD-02 (Observasi, kap 6),
          R-K1 Mawar (6), R-K2 Melati (8), R-K3 Dahlia (12), VIP-A Anggrek (4),
          ICU-01 (4), OK-01 (2)
Unit    : IGD (L3, parent BID-YAN), IRIN (L2), BANGSAL-ANAK/BEDAH/DEWASA/OBGYN/VIP (L3, parent IRIN),
          ICU (L3), HCU, ICCU, NICU-PICU, OBSERVASI-EMERGENCY (L3, parent IGD)
Kunjungan: IGD 1 (triage MERAH), RAJAL 1, RANAP 3 (status: PULANG 1, RANAP 2)
Bed     : TERISI 3, TERSEDIA 43
```

Konsekuensi: **semua test wajib membuat fixture sendiri.** Jangan menulis test yang bergantung pada baris data dev.

---

## 8. Sisa yang belum dipastikan sebelum eksekusi

1. Field persis `Pasien.nama_lengkap` / `Pasien.no_rm` (belum dibaca baris per baris) — Task 1 menegakkan dengan membaca `pasien/models.py:12-154`.
2. Nilai persis `KunjunganPasien.fungsional_adl` di data nyata (belum ada baris terisi) — pemetaan ditulis bertoleransi (`startswith`) dan diuji dengan 3 nilai bantu di test.
3. Apakah IGD menginginkan 1 logbook gawat darurat atau per ruangan (IGD-01/IGD-02) — keputusan: **1 logbook IGD** (`ruangan=None`), pasien ditarik berdasarkan `jenis_kunjungan='IGD'`.
