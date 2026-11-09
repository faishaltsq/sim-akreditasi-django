# Asesmen Awal IGD — Master ICD + Tarif, Korelasi EP, dan Katalog 3S (Spec)

**Sumber dokumen (3 berkas, dari user):**
1. `Master icd 10 dan 9 dokter terbaru dengan tarif.docx` — 3.378 baris hasil ekstraksi. 13 kelompok layanan, 14 tabel kasus (Mata punya 2 tabel), masing-masing 15 baris. Kolom: ICD-10, ICD-9-CM (1–3 tindakan), Tarif Umum, Tarif BPJS, Tatalaksana, Level Kewenangan Dokter.
2. `Berikut adalah penyempurnaan rancangan modul asesmen awal icd slki.docx` — 62 baris. Wireframe form (A–E) + tabel rekapitulasi dengan aksi Lihat/Edit/Hapus + status EP akreditasi.
3. `Penambahan di arima asesmen awal igd.docx` — 208 baris. Rekomendasi UX (wizard, smart default, auto-calculate, auto-fill) + prototipe HTML Bootstrap 5.

**Tanggal analisis:** 2026-11-08. **Repo:** `sim-akreditasi-django` @ `master` (9ad5fa0). **Django 5 + Bootstrap 5.3.3 + Supabase Postgres (prod) / SQLite (dev).**

---

## 1. Ringkasan tiap dokumen

| Dokumen | Inti permintaan | Klasifikasi |
|---|---|---|
| Master ICD/tarif | Katalog referensi: diagnosis ICD-10 × tindakan ICD-9-CM × tarif ganda (Umum/BPJS) × tatalaksana × level kewenangan, per kelompok layanan | **Master data baru** |
| Penyempurnaan modul | (A) korelasi EP akreditasi per asesmen, (B) ICD-10 + ICD-9 picker, (C) SDKI→SLKI→SIKI otomatis, (D) tarif otomatis, (E) upload lampiran, (F) tabel rekap dengan aksi | **Fitur transaksional baru** |
| Penambahan IGD | Wizard bertahap, chip "Set Normal", kalkulasi skor instan, auto-fill dari pendaftaran/triase, "salin asesmen sebelumnya" | **UX — mayoritas SUDAH ADA** |

Dokumen ke-3 hampir seluruhnya sudah terimplementasi. Bukan pekerjaan baru; yang tersisa hanya kalkulator Morse otomatis dan konsolidasi JS yang saat ini terduplikasi di dua template.

---

## 2. Audit kode eksisting

| Komponen | Lokasi | Status |
|---|---|---|
| Wizard asesmen 4 tab (KU/TTV, Nyeri/Gizi, Fungsional/Fisik, Diagnosa/Risiko) | `templates/pasien/_asesmen_awal_wizard.html:22-37` | **Ada** |
| Chip "Set Normal" | `templates/pasien/igd_dashboard.html:2894` (`setNormalAsesmen`), `asesmen_awal_form.html:181` (`setNormalDetail`) | **Ada** |
| Slider nyeri + badge warna live | `igd_dashboard.html:1787-1789`, `updateSkorNyeri:2882` | **Ada** |
| MST auto-calc live + badge | `igd_dashboard.html:2863-2881`, `asesmen_awal_form.html:169` | **Ada** |
| "Salin dari Asesmen Sebelumnya" | `pasien/views.py:2117` `igd_asesmen_copy_prev`, tombol `igd_dashboard.html:1426` | **Ada** |
| Auto-fill alergi dari master pasien | `pasien/views.py:2087-2089` | **Ada** |
| Jenis pasien Umum/BPJS | `KunjunganPasien.penjamin` (`pasien/models.py:333`) | **Ada** |
| Picker ICD-10 (datalist + API) | `pasien/views.py:32` `ICD10_CODES` (80 kode), `api_icd10:576` | **Ada, terbatas** |
| Picker SDKI | `pasien/views.py:118` `SDKI_CODES` (24 kode), `api_sdki:589` | **Ada, terbatas** |
| Picker ICD-9-CM | — | **TIDAK ADA** (masih free-text: `igd_dashboard.html:1907`) |
| SLKI/SIKI otomatis dari SDKI | — | **TIDAK ADA** (free-text, `models.py:404-406`) |
| Korelasi EP akreditasi per asesmen | — | **TIDAK ADA** |
| Tarif otomatis | — | **TIDAK ADA** (tidak ada model tarif sama sekali) |
| Upload lampiran asesmen | — | **TIDAK ADA** |
| Tabel rekap asesmen + Lihat/Edit/Hapus | — | **TIDAK ADA** |
| Skor Morse otomatis | manual: input skor + pilih grade (`igd_dashboard.html:1884-1890`) | **TIDAK ADA** |
| Level kewenangan klinis (3A/3B/4A) | `sdm.KatalogTindakan` (`sdm/models/katalog_rkk.py:46`) memakai M/S/MT/T | **Ada, skema berbeda** |
| EP (Elemen Penilaian) | `akreditasi.StandardItem` (`akreditasi/models.py:309`), format kode `"<SUB_STANDAR> EP <n>"` | **Ada** |
| EP contoh di dokumen (`PAP 2.1`) | hanya `PAP 2` yang ada di katalog 2022 | **Tidak cocok** — lihat §4 |

**Kesimpulan audit:** yang diminta dokumen 3 sudah ~90% jadi. Nilai tambah nyata ada pada dokumen 1 (master tarif) dan dokumen 2 (EP + tarif + lampiran + rekap).

---

## 3. Matriks gap

| # | Kebutuhan | Gap | Prioritas |
|---|---|---|---|
| G1 | Katalog ICD-10/ICD-9/tarif/kewenangan per kelompok layanan | Tidak ada model & data | P0 |
| G2 | Tarif otomatis Umum/BPJS pada form asesmen | Tidak ada | P0 |
| G3 | Korelasi EP + status pemenuhan per asesmen | Tidak ada | P0 |
| G4 | Tabel rekap asesmen dengan Lihat/Edit/Hapus | Tidak ada | P0 |
| G5 | SDKI→SLKI→SIKI otomatis | Tidak ada pemetaan | P1 |
| G6 | Upload lampiran (.pdf/.xls/.xlsx/.doc/.docx) | Tidak ada | P1 |
| G7 | Picker ICD-9-CM (searchable) | Masih free-text | P1 |
| G8 | Skor Morse otomatis + grade turunan | Manual | P1 |
| G9 | Catatan penyesuaian waktu | Tidak ada field | P2 |
| G10 | Konsolidasi JS asesmen (duplikat 2 template) | **Bukan gap** — duplikasi dibiarkan apa adanya (lihat §5.4 A8) | — |

---

## 4. Register cacat data dokumen sumber

Cacat ini **tidak boleh diperbaiki dengan mengarang isi**. Aturan: simpan verbatim, tandai `perlu_verifikasi=True`, biarkan admin melengkapi.

| # | Cacat | Bukti (baris dokumen) | Penanganan |
|---|---|---|---|
| D1 | Tabel pertama berjudul "Kasus Tersering Inap Jantung & Kardiovaskular", isinya 5 baris **SDKI nifas** (Risiko Perdarahan, Risiko Syok Hipovolemik, Keletihan, Ansietas, Defisit Pengetahuan) — tanpa ICD-10/ICD-9/tarif | 2–81 | Reklasifikasi ke kelompok **Nifas** sebagai baris `KasusTersering` dengan `icd10=NULL`, `sdki` terisi |
| D2 | Kode SDKI di dokumen bentrok dengan PPNI yang dipakai repo: dokumen `D.0012 = Risiko Perdarahan`, repo `D.0149 = Risiko Perdarahan` (`pasien/views.py:141`) | 14 | Katalog mengikuti PPNI (repo). Kode dokumen disimpan di `catatan_sumber`, tidak menimpa katalog |
| D3 | Teks tatalaksana terpotong | PD #15 "…malaria berat (serebral/a" (1171); Mata #15 "…atau vitrektomi" (1384); Orto #15 "…saraf Carp" (1954); Nifas #15 "…oleh Anestesi ji" (2140); Bedah #15 "…rujukan kemoterap" (2818); IGD #15 "…pemantauan tanda vital" (3378) | Simpan verbatim + `perlu_verifikasi=True` |
| D4 | Tabel "Pascabedah Mata" **tidak punya kolom biaya** sama sekali | 1394–1509 | `KasusTindakan` tanpa baris tarif; UI menampilkan "Tarif belum ditetapkan", **bukan Rp 0** |
| D5 | Level kewenangan kosong di beberapa baris | Endokrin #15 (889), Nifas #15 (2140), Orto-pasca #15 (1724) | Field nullable; UI "—" |
| D6 | ICD-9 yang sama punya tarif berbeda antar kelompok: `99.18` = Rp 75.000 (Anak), Rp 100.000 (IGD/PD), Rp 150.000 (Kardiologi) | 1013, 3275, 635 | **Tarif di-key ke kasus, bukan ke ICD-9** (keputusan arsitektur A2) |
| D7 | ICD-10 duplikat lintas kelompok: `I50.9` (Kardiologi & PD), `J18.9` (Paru/PD/Anak/IGD), `A91` (Anak & IGD), `N20.1` (IBS & Bedah) | 113, 907, 2858, 3123 | `MasterIcd10.kode` unik → upsert; kasus merujuk ke satu baris master |
| D8 | Contoh EP di dokumen `PAP 2.1` tidak ada; katalog 2022 hanya punya `PAP 2` (`Peresepan & Instruksi Klinis`) | 13, 51 | Autolink wajib punya fallback prefix-match, dan tidak boleh error saat tidak ketemu |

**Jumlah baris target seed:** 14 kelompok × 15 baris (ICD-10) = **210 kasus** + 5 baris SDKI-only yang direklasifikasi ke Nifas (D1) = **215 baris `KasusTersering`**. Dari 210 baris ICD-10, 195 punya tarif dan 15 (Pascabedah Mata) tidak. `KasusTindakan` ± 380–420 baris (1–3 tindakan per kasus). Angka pasti dihitung oleh data module, bukan ditebak — test mengassert `len(DATA)` bukan konstanta literal.

---

## 5. Arsitektur target

### 5.1 Batas domain

```
klinis/    → REFERENCE DATA  (katalog ICD, tarif, 3S, aturan EP)  — tidak menyimpan data pasien
pasien/    → TRANSAKSI       (kunjungan, asesmen, EP terpenuhi, lampiran, billing)
akreditasi/→ EP & bukti      (StandardItem, EvidenceReq, EvidenceFile)  — tidak diubah
sdm/       → kewenangan klinis pegawai (KatalogTindakan)  — tidak diubah
```

Alasan memisahkan `klinis`: `pasien/models.py` sudah 1.108 baris dan `pasien/views.py` 2.596 baris. Katalog referensi punya siklus hidup berbeda (di-seed, jarang berubah, bisa di-import ulang) dibanding transaksi kunjungan. Mencampurnya akan membuat migrasi katalog dan migrasi transaksi saling mengunci.

**Reuse:** rencana `docs/superpowers/plans/2026-11-04-master-data-klinis-katalog.md` sudah merancang app `klinis` dengan `MasterIcd10`/`MasterIcd9`, tetapi **belum dieksekusi** (tidak ada direktori `klinis/`, tidak ada di `INSTALLED_APPS`). Spec ini memakai desain itu sebagai fondasi dan menambah tarif, kasus, 3S, dan aturan EP.

### 5.2 Model `klinis`

```python
# klinis/models.py
class KelompokLayanan(models.Model):
    kode      = CharField(max_length=30, unique=True)          # 'IGD', 'JANTUNG', 'PARU', ...
    nama      = CharField(max_length=120)
    unit_kerja= ForeignKey('akreditasi.UnitKerja', null=True, blank=True, on_delete=SET_NULL)
    urutan    = PositiveIntegerField(default=0)

class MasterIcd10(models.Model):
    kode            = CharField(max_length=8, unique=True, db_index=True)
    nama            = CharField(max_length=200)
    spesialisasi    = CharField(max_length=50, db_index=True, blank=True)
    triase_default  = CharField(max_length=10, blank=True)     # pilihan didefinisikan lokal (§5.4)
    risiko_default  = CharField(max_length=10, blank=True)
    created_at      = DateTimeField(auto_now_add=True)
    # FK ke pasien DILARANG — pilihan triase didefinisikan lokal di klinis

class MasterIcd9(models.Model):
    kode             = CharField(max_length=8, unique=True, db_index=True)
    nama             = CharField(max_length=200)
    invasif          = BooleanField(default=False)
    requires_consent = BooleanField(default=False)

class KasusTersering(models.Model):
    kelompok      = ForeignKey(KelompokLayanan, related_name='kasus')
    urutan        = PositiveIntegerField()
    icd10         = ForeignKey(MasterIcd10, null=True, blank=True, on_delete=PROTECT)
    sdki_kode     = CharField(max_length=10, blank=True)        # untuk baris SDKI-only (D1)
    sdki_nama     = CharField(max_length=150, blank=True)
    tatalaksana   = TextField(blank=True)
    kewenangan    = CharField(max_length=6, blank=True)          # '4A'|'3B'|'3A'|'Sp.X'
    perlu_verifikasi = BooleanField(default=False)               # D3
    catatan_sumber   = TextField(blank=True)                     # D2, verbatim asli
    class Meta:
        unique_together = [('kelompok', 'urutan')]
        ordering = ['kelompok__urutan', 'urutan']

class KasusTindakan(models.Model):
    kasus      = ForeignKey(KasusTersering, related_name='tindakan')
    icd9       = ForeignKey(MasterIcd9, on_delete=PROTECT)
    urutan     = PositiveIntegerField(default=1)
    tarif_umum = DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tarif_bpjs = DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    satuan     = CharField(max_length=30, blank=True)            # '/kantong', '/hari', '/tindakan'
    class Meta:
        unique_together = [('kasus', 'icd9', 'urutan')]

class SdkiDiagnosis(models.Model):
    kode = CharField(max_length=10, unique=True); nama = CharField(max_length=200)

class SlkiLuaran(models.Model):
    kode = CharField(max_length=12, unique=True); nama = CharField(max_length=200)

class SikiIntervensi(models.Model):
    kode = CharField(max_length=14, unique=True); nama = CharField(max_length=200)

class Pemetaan3S(models.Model):
    sdki = ForeignKey(SdkiDiagnosis, related_name='pemetaan')
    slki = ForeignKey(SlkiLuaran, related_name='pemetaan')
    siki = ForeignKey(SikiIntervensi, related_name='pemetaan')
    prioritas = PositiveIntegerField(default=1)

class AturanEpAsesmen(models.Model):
    sub_standard = CharField(max_length=50, unique=True)         # 'ARK 1', 'PAP 3', ...
    label        = CharField(max_length=150)
    wajib        = BooleanField(default=True)
    urutan       = PositiveIntegerField(default=0)
```

### 5.3 Model baru di `pasien`

```python
class KorelasiEpAsesmen(models.Model):
    STATUS = [('TERPENUHI','Terpenuhi'), ('BELUM','Belum Terpenuhi'), ('NA','Tidak Berlaku')]
    kunjungan     = ForeignKey(KunjunganPasien, related_name='korelasi_ep')
    standard_item = ForeignKey('akreditasi.StandardItem', related_name='korelasi_asesmen')
    status        = CharField(max_length=12, choices=STATUS, default='BELUM')
    catatan       = TextField(blank=True)
    diverifikasi_oleh = ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    diverifikasi_pada = DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = [('kunjungan', 'standard_item')]

class LampiranAsesmen(models.Model):
    JENIS = [('ASESMEN','Dokumen Asesmen'), ('PENUNJANG','Hasil Penunjang'), ('LAINNYA','Lainnya')]
    kunjungan   = ForeignKey(KunjunganPasien, related_name='lampiran_asesmen')
    jenis       = CharField(max_length=12, choices=JENIS, default='ASESMEN')
    file        = FileField(upload_to='asesmen/%Y/%m/')
    nama_asli   = CharField(max_length=255)
    ukuran      = PositiveIntegerField(default=0)      # byte
    diunggah_oleh = ForeignKey(User, null=True, on_delete=SET_NULL)
    diunggah_pada = DateTimeField(auto_now_add=True)
```

Penambahan field (aditif, nullable, tanpa mengubah tipe lama):

| Model | Field | Tipe | Alasan |
|---|---|---|---|
| `KunjunganPasien` | `skrining_jatuh_detail` | `JSONField(default=dict)` | Menyimpan 6 item Morse, bukan hanya total |
| `KunjunganPasien` | `asesmen_catatan_waktu` | `TextField(blank=True)` | Dokumen 2 §D |
| `BillingItem` | `sumber` | `CharField(choices=[MANUAL, ASESMEN], default='MANUAL')` | Kunci idempotensi tarif otomatis |

### 5.4 Keputusan arsitektur & tradeoff

**A1 — App `klinis` terpisah, bukan menambah model ke `pasien`.**
Tradeoff: +1 app, +1 `INSTALLED_APPS`, +1 migrasi manual di Supabase. Imbalan: katalog bisa di-seed ulang/di-import tanpa menyentuh tabel transaksi; `pasien` tidak makin gemuk.

**A2 — Tarif menempel ke `KasusTindakan`, bukan ke `MasterIcd9`.**
Wajib, karena cacat D6: kode `99.18` punya 3 tarif berbeda untuk 3 kelompok. Tarif global per ICD-9 akan salah untuk minimal 40% baris. Konsekuensi: memilih ICD-9 di luar konteks kasus tidak menghasilkan tarif — UI harus menampilkan "Tarif belum ditetapkan", bukan Rp 0.

**A3 — Uang tetap di `BillingItem`, tidak diduplikasi ke `KunjunganPasien`.**
Saat asesmen disimpan, service membuat/memperbarui `BillingItem(kategori='JASA_MEDIS', sumber='ASESMEN', kode_icd=<icd9>)` dengan kunci idempotensi. Total tarif di form adalah **turunan** (`SUM(subtotal)`), bukan kolom tersimpan. Imbalan: satu sumber kebenaran uang; tidak ada angka tarif yang bisa basi.

**A4 — "Hapus" menghapus entri asesmen dari database, persis seperti diminta dokumen.**
Dokumen 2: *"Hapus: Menghapus data asesmen yang keliru dari database dengan sistem pengamanan konfirmasi (safety prompt) agar data penting tidak terhapus secara tidak sengaja."* Implementasinya: baris **hilang dari tabel rekap**. Karena asesmen menempel pada `KunjunganPasien`, yang dihapus adalah **data asesmennya** — seluruh field asesmen dikosongkan, `KorelasiEpAsesmen` dan `LampiranAsesmen` dihapus dari database, `BillingItem(sumber='ASESMEN')` dihapus. Baris kunjungan tetap ada karena ia pemilik billing, CPPT, order penunjang, dan jejak RME (MRMIK 5) — menghapusnya akan meng-cascade semuanya dan merusak rekam medis pasien, yang bukan yang diminta. Tabel rekap hanya menampilkan kunjungan **yang punya asesmen**, sehingga setelah hapus entri benar-benar lenyap dari daftar. Konfirmasi wajib: `POST` + token + prompt ketik `HAPUS`.

**A5 — Pemetaan unit → kelompok layanan eksplisit, tanpa heuristik string.**
`KelompokLayanan.unit_kerja` diisi manual (data seed), fallback ke `kode == jenis_kunjungan.upper()`. Tidak ada pencocokan `'JANTUNG' in unit.name`. Alasan: 162 `UnitKerja` di repo, dan nama bangsal tidak konsisten dengan 13 kelompok dokumen.

**A6 — Triase/risiko choices didefinisikan lokal di `klinis`.**
Menghindari import `pasien.models` dari `klinis.models` (arah dependensi terbalik + risiko siklus import). Duplikasi 5 tuple lebih murah daripada coupling.

**A7 — EP dipilih bebas dari katalog akreditasi; `AturanEpAsesmen` hanya pre-selection.**
Dokumen meminta "Pilih Bab / Standar Akreditasi" dengan autolink. Karena itu UI menampilkan **seluruh** `sub_standard` yang ada di `akreditasi.StandardItem` (dropdown, dikelompokkan per `Category`), bukan hanya daftar tertutup. `AturanEpAsesmen` hanya menyediakan 4 baris yang **sudah tercentang** saat form dibuka: `ARK 1` (triage IGD), `PAP 3` (gawat darurat), `PAP 8` (EWS), `SKP 1` (identifikasi pasien) — keempatnya terverifikasi ada di katalog 2022. Petugas boleh menambah/menghapus pilihan. Resolver: exact `sub_standard` → prefix match → peringatan. Wajib tahan `PAP 2.1` (cacat D8).

**A8 — Tidak ada refactor JS. Yang sudah jalan dibiarkan.**
`updateSkorNyeri`, `hitungMst`, `setNormalAsesmen`/`setNormalDetail` sudah bekerja di kedua UI dan tidak disentuh. Pekerjaan JS dibatasi pada satu fungsi baru, `hitungMorse`, yang ditempel di masing-masing template sebagai blok inline kecil — konsisten dengan pola file yang sudah ada. Duplikasi ~90 baris **diterima** sebagai biaya; memindahkannya ke berkas statis berisiko memecah 3 kelas test UX yang sudah hijau tanpa manfaat yang diminta user.

### 5.5 Alur tarif otomatis

```
pilih ICD-9 di form asesmen
   → POST igd_asesmen_medis_save / igd_asesmen_awal_save
   → klinis.services.tarif.resolve(kunjungan, [kode_icd9])
       1. kelompok = KelompokLayanan.unit_kerja == kunjungan.unit_kerja
                     fallback KelompokLayanan.kode == kunjungan.jenis_kunjungan
       2. KasusTersering(kelompok).tindakan(icd9=kode)  → tarif_umum / tarif_bpjs
       3. penjamin: BPJS → tarif_bpjs; UMUM/ASURANSI → tarif_umum
       4. tidak ketemu → return None (UI: "Tarif belum ditetapkan")
   → BillingItem.update_or_create(
        kunjungan, kategori='JASA_MEDIS', kode_icd=kode, sumber='ASESMEN',
        defaults={'nama_item': icd9.nama, 'harga_satuan': nominal, 'kuantitas': 1})
```

Form menampilkan `SUM(subtotal) WHERE sumber='ASESMEN'`. Menghapus pilihan ICD-9 menghapus baris billing terkait (idempotensi dua arah).

### 5.6 Alur korelasi EP

```
form asesmen (tab Diagnosa & Risiko)
   → dropdown "Bab / Standar Akreditasi" berisi SELURUH sub_standard di katalog
     (dikelompokkan per Category: ARK, PAP, HPK, SKP, MRMIK, ...)
   → 4 baris dari AturanEpAsesmen sudah tercentang otomatis saat form dibuka
   → petugas boleh menambah/menghapus pilihan; per EP: radio Terpenuhi / Belum / NA + catatan
   → simpan: KorelasiEpAsesmen.update_or_create(kunjungan, standard_item)
   → kolom "Status EP" di tabel rekap = "Terpenuhi (ARK 1)" / "Belum (PAP 3)" / "—"
```

Status ringkas kunjungan: `TERPENUHI` bila **semua** EP `wajib=True` berstatus `TERPENUHI`; `SEBAGIAN` bila ada yang terpenuhi; `BELUM` bila tidak ada. EP yang dipilih manual di luar `AturanEpAsesmen` ikut dihitung sebagai terpenuhi bila statusnya `TERPENUHI`, tetapi tidak bisa membuat status ringkas jadi `BELUM`.

### 5.7 Aturan upload lampiran

- Ekstensi diizinkan: `.pdf`, `.xls`, `.xlsx`, `.doc`, `.docx` (dokumen 2 menyebut `.doc`; `.docx` ditambahkan karena format aktual).
- Ukuran maksimum: 10 MB. Validasi di server (bukan hanya `accept=` di HTML).
- Nama file disanitasi; disimpan dengan nama UUID di `media/asesmen/%Y/%m/`, `nama_asli` disimpan terpisah untuk ditampilkan.
- Unduh lewat view ber-`login_required` + `can_read_kunjungan` — bukan URL media langsung (konsisten dengan pola `download_kredensial_nakes` di `akreditasi`).
- Upload dicatat ke `AuditLog` (`akreditasi.models.AuditLog`).

---

## 6. Non-goals

- Tidak menyentuh `akreditasi.StandardItem` / `EvidenceReq` / `EvidenceFile`. EP hanya dibaca.
- Tidak mengubah `sdm.KatalogTindakan` (jenjang M/S/MT/T) menjadi 3A/3B/4A. Level kewenangan dokumen disimpan sebagai teks di `KasusTersering.kewenangan`; rekonsiliasi dengan RKK adalah pekerjaan terpisah.
- Tidak mem-parse `.docx` saat runtime. Data seed ditulis sebagai modul Python yang bisa dibaca dan direview.
- Tidak membuat klaim INA-CBG (grouper). "Tarif BPJS" di dokumen adalah tarif satuan verifikasi klaim, bukan tarif INA-CBG final.
- Tidak mengubah `BillingItem` selain menambah kolom `sumber`.
- Tidak menyentuh `staticfiles/` (tracked untuk Vercel) kecuali lewat `collectstatic` di akhir.

---

## 7. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Migrasi tidak jalan otomatis di deploy | Fitur 500 di produksi | Jalankan migrasi manual ke Supabase **sebelum** push; tercantum di DoD |
| 40+ file test `pasien` (164 test) regresi | Suite merah | Jalankan `--keepdb` per task, bukan sekali di akhir |
| Transkripsi 210 baris salah | Data klinis/tarif keliru | Test integritas: jumlah baris, tidak ada `KasusTindakan` tanpa `icd9`, tidak ada tarif negatif, semua `kewenangan` di himpunan yang dikenal |
| `unique_together (kelompok, urutan)` bentrok saat re-seed | Seed gagal | Seed pakai `update_or_create` pada kunci natural, bukan `create` |
| Nominal tarif salah ketik (7.500.000 vs 750.000) | Salah tagih | `DecimalField`, test rentang wajar per kelompok (mis. IGD ≤ Rp 15 jt), review manual baris > Rp 25 jt |
| `PAP 2.1` tidak ada | Autolink crash | Resolver menelan `DoesNotExist`, log `WARNING`, UI tetap render |
