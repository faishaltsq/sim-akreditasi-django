# Asesmen Awal IGD v2 — Tarif Editable per Tindakan & EP Otomatis per Item (Spec)

**Sumber dokumen:** `penyempurnaan rancangan modul asesmen awal icd slki dan tarif 8 11.docx` (81 baris; wireframe B/C + blok rekapitulasi).
**Tanggal analisis:** 2026-11-09. **Repo:** `sim-akreditasi-django` @ `master` (9ad5fa0) + working tree (9 modified, 11 untracked).
**Stack:** Django 5, Bootstrap 5.3.3, Supabase Postgres (prod) / SQLite (dev).
**Pendahulu:** `docs/superpowers/specs/2026-11-08-asesmen-igd-master-tarif-ep-3s.md` dan plan `2026-11-08-asesmen-igd-tarif-ep-3s.md` (v1). Dokumen ini adalah **delta v2**, bukan pengganti.

---

## 1. Yang diminta dokumen

| # | Permintaan | Bukti di dokumen |
|---|---|---|
| R1 | Tarif acuan otomatis per tindakan sesuai penjamin (Umum/BPJS) | baris 5, 72 |
| R2 | Nominal tarif dapat **diedit langsung** pada baris tindakan | baris 6, 30, 52, 73 |
| R3 | Catatan/alasan opsional saat tarif diubah dari master | baris 74 |
| R4 | EP akreditasi ter-link otomatis per tindakan (contoh: infus → PAP 2.1) | baris 7-9, 76-79 |
| R5 | EP dapat diganti/ditambah manual lewat selector (⚙️) per tindakan | baris 80 |
| R6 | Badge kelengkapan per item (Terpenuhi 🟢 / Belum Lengkap 🟡) | baris 81 |
| R7 | Rekap biaya + jumlah EP terpenuhi di dalam form | baris 63-68 |
| R8 | Badge sumber data per baris: Master / AI Suggested / Manual Entry | baris 28, 50, 56 |
| R9 | Saran ICD-10/ICD-9 ("AI Suggestion") sebagai chip | baris 17, 24 |
| R10 | Aksi per baris: edit teks, hapus | baris 31, 53 |
| R11 | Blok tindakan medis (ICD-9 + tarif) dan blok keperawatan (SIKI + tarif) | baris 12-61 |

---

## 2. Status implementasi terverifikasi

Bukti dijalankan pada working tree saat ini (bukan asumsi):

- `manage.py test klinis pasien.tests_asesmen_save_ep_tarif pasien.tests_asesmen_rekap pasien.tests_ep_status pasien.tests_morse --keepdb` → **33 test, OK, 34,1 s**.
- Seed katalog: **14 kelompok, 172 ICD-10, 170 ICD-9, 215 kasus, 397 `KasusTindakan`, 27 SDKI / 20 SLKI / 18 SIKI / 22 pemetaan, 4 `AturanEpAsesmen`**.
- Katalog akreditasi: **301 `StandardItem`, 136 `sub_standard`** (`PAP 1`, `PAP 2`, `PAP 3`, `PAP 8`, `SKP 1/2/3`, `HPK 1..5`, `ARK 1..7`, `PP 1..8`, `KPR` **tidak ada**).

| Kebutuhan | Status | Lokasi |
|---|---|---|
| Tarif otomatis per ICD-9 + penjamin | **Ada** | `klinis/services/tarif.py:20-42`, `sync_billing:45-74` |
| Billing idempoten `sumber='ASESMEN'` | **Ada** | `pasien/models.py:788-798`, `pasien/views.py:2177-2189` |
| Picker ICD-9 (datalist + chip) di wizard | **Ada** | `templates/pasien/_asesmen_awal_wizard.html:678-718` |
| Preview total tarif via API | **Ada, RUSAK** | `pasien/views.py:2685-2732` — lihat §3 C1 |
| Korelasi EP tingkat kunjungan | **Ada** | `pasien/models.py:1127-1146`, wizard baris 722-808 |
| EP per tindakan | **Tidak ada** | — |
| Tarif editable + catatan alasan | **Tidak ada** | `sync_billing` menimpa `harga_satuan` tiap simpan |
| Badge sumber data (Master/AI/Manual) | **Tidak ada** | `BillingItem` tidak menyimpan sumber seleksi |
| Badge kelengkapan per item | **Tidak ada** | hanya `status_ep_ringkas` tingkat kunjungan |
| Rekap biaya + hitung EP di form | **Sebagian** | total tampil; hitung EP belum |
| SIKI ber-tarif | **Tidak ada** | SIKI masih free-text, tanpa master tarif |
| Saran ICD ("AI Suggestion") | **Tidak ada** | tidak ada integrasi LLM di repo |
| Edit teks / hapus per baris | **Tidak ada** | chip hanya bisa dihapus, teks tidak bisa diedit |
| Paritas UI di modal IGD | **Tidak ada** | `igd_dashboard.html:1966` masih input teks bebas |

**Kesimpulan:** v1 sudah mengirim ~60% dokumen. Sisa pekerjaan nyata adalah R2, R3, R4, R5, R6, R8, R9, R10, R11-atas (SIKI ber-tarif), plus perbaikan 3 bug laten.

---

## 3. Register cacat — dokumen sumber & kode eksisting

### 3.1 Cacat dokumen (jangan "diperbaiki" dengan mengarang)

| # | Cacat | Bukti | Penanganan |
|---|---|---|---|
| D1 | Contoh EP `PAP 2.1` tidak ada di katalog; yang ada `PAP 2` (instruksi pengobatan) dan `PAP 3` (gawat darurat/Code Blue) | baris 8, 29 | Autolink memakai kode yang **ada**; `PAP 2.1` → `PAP 3` untuk tindakan risiko tinggi. Fallback prefix-match, tanpa error |
| D2 | Contoh `PAP 1.1` tidak ada; yang relevan `PP 2` (skrining nyeri NRS/VAS) dan `PP 1` (ketepatan waktu asesmen awal) | baris 57 | Nyeri/edukasi → `PP 2`; kelengkapan asesmen → `PP 1` |
| D3 | `KPR 3` tidak ada sama sekali di katalog 2022/2024 (tidak ada sub_standard berawalan `KPR`) | baris 8 | Selector EP menampilkan katalog riil; tidak ada referensi keras ke `KPR` |
| D4 | `I.15506` disebut "Manajemen Hipertermia"; di katalog repo `I.15506 = Regulasi Temperatur` | baris 49 | Tampilkan nama katalog; jangan menimpa nama master |
| D5 | Semua tarif SIKI tidak ada di dokumen sumber mana pun (dokumen master hanya memuat tarif ICD-9) | — | **Tidak di-seed.** Tarif SIKI hanya bisa diisi manual oleh petugas (`tarif_acuan = NULL`) |
| D6 | `MasterIcd9.invasif` dan `requires_consent` semuanya `False` (seed tidak mengisinya) | `klinis` seed | Aturan EP berbasis flag tidak akan pernah cocok; v2 hanya mengandalkan aturan kode eksplisit |
| D7 | Satu kode ICD-9 muncul di beberapa kasus IGD (mis. `99.18` 6×, `89.52` 3×) | query seed | `resolve()` memilih baris pertama secara deterministik; tarif bisa berbeda bila `kasus__urutan` berubah. Dokumentasikan, jangan diubah di v2 |

### 3.2 Cacat kode eksisting (harus diperbaiki lebih dulu)

| # | Cacat | Bukti | Dampak |
|---|---|---|---|
| C1 | `api_tarif_preview` memanggil `resolve()` yang **tidak diimpor**, lalu memperlakukan hasilnya sebagai dict (`t_res['nominal']`) dan mengakses `tindakan.nama_tindakan` yang tidak ada | `pasien/views.py:2703, 2705, 2709`; import hanya `sync_billing, _kelompok_for` di baris 35 | `GET /pasien/api/tarif-preview/` → `NameError` (500). Strip tarif di wizard tidak pernah terisi |
| C2 | `igd_asesmen_medis_save` membuat `LampiranAsesmen(ukuran_byte=..., keterangan=...)`; field riil adalah `ukuran`, dan `keterangan` tidak ada | `pasien/views.py:2669, 2671` vs `pasien/models.py:1157-1161` | `TypeError` setiap kali upload lampiran lewat simpan asesmen medis IGD |
| C3 | Template menawarkan kategori lampiran `RUJUKAN`; `LampiranAsesmen.JENIS` tidak memuat `RUJUKAN` | `_asesmen_awal_wizard.html:837` vs `models.py:1150-1154` | Nilai tersimpan tanpa validasi; filter/`get_jenis_display()` menampilkan kode mentah |
| C4 | Tidak ada test yang menyentuh `api_tarif_preview` maupun jalur lampiran di `igd_asesmen_medis_save` | `pasien/tests_asesmen_save_ep_tarif.py` hanya menguji endpoint upload terpisah | Tiga cacat di atas lolos dari suite hijau |

---

## 4. Matriks gap v2

| # | Gap | Prioritas |
|---|---|---|
| G1 | Baris tindakan sebagai entitas (bukan `BillingItem`): teks editable, sumber data, tarif acuan vs final, catatan, EP, status | P0 |
| G2 | Override tarif bertahan saat simpan ulang; master tetap tercatat sebagai acuan | P0 |
| G3 | Aturan EP per kode ICD-9/SIKI + resolver | P0 |
| G4 | EP per baris + badge kelengkapan | P0 |
| G5 | Rekap biaya medis/keperawatan + hitung EP di form | P1 |
| G6 | Saran ICD-10/ICD-9 deterministik (bukan LLM) | P1 |
| G7 | Paritas UI modal IGD (bukan hanya halaman wizard) | P1 |
| G8 | SIKI ber-tarif manual | P2 |
| G9 | Perbaikan C1-C3 + test penjaga | P0 (Phase 0) |

---

## 5. Arsitektur target

### 5.1 Model baris: `pasien.TindakanAsesmen`

Alasan memisahkan dari `BillingItem`: dokumen meminta atribut yang bersifat **dokumentasi klinis** (sumber seleksi, teks yang bisa diedit, EP akreditasi, alasan perubahan tarif). Menaruhnya di `BillingItem` akan mencampur domain billing dengan dokumentasi asuhan dan membuat laporan keuangan bergantung pada aturan akreditasi. Uang tetap satu sumber: `BillingItem`.

```python
class TindakanAsesmen(models.Model):
    JENIS = [('ICD9', 'ICD-9-CM'), ('SIKI', 'SIKI'), ('BEBAS', 'Manual / Bebas')]
    SUMBER = [('MASTER', 'Master'), ('SARAN', 'Saran Sistem'), ('MANUAL', 'Input Manual')]
    EP_STATUS = [('TERPENUHI', 'Terpenuhi'), ('BELUM', 'Belum Lengkap'), ('NA', 'Tidak Berlaku')]

    kunjungan   = FK(KunjunganPasien, related_name='tindakan_asesmen', on_delete=CASCADE)
    urutan      = PositiveIntegerField(default=1)
    jenis       = CharField(max_length=6, choices=JENIS, default='ICD9')
    icd9        = FK('klinis.MasterIcd9', null=True, blank=True, on_delete=PROTECT)
    siki        = FK('klinis.SikiIntervensi', null=True, blank=True, on_delete=PROTECT)
    kode        = CharField(max_length=20, blank=True)          # denormalisasi utk SIKI/BEBAS
    nama        = CharField(max_length=200)                     # editable
    sumber_data = CharField(max_length=8, choices=SUMBER, default='MANUAL')
    tarif_acuan = DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tarif       = DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    catatan_tarif = TextField(blank=True)
    standard_item = FK('akreditasi.StandardItem', null=True, blank=True, on_delete=SET_NULL)
    ep_status     = CharField(max_length=12, choices=EP_STATUS, default='BELUM')
    ep_catatan    = TextField(blank=True)
    billing_item  = OneToOneField(BillingItem, null=True, blank=True, on_delete=SET_NULL, related_name='tindakan_asesmen')
    diubah_oleh   = FK(User, null=True, blank=True, on_delete=SET_NULL)
    created_at / updated_at

    class Meta:
        unique_together = [('kunjungan', 'urutan')]
        ordering = ['urutan']

    @property
    def tarif_efektif(self):
        return self.tarif if self.tarif is not None else self.tarif_acuan

    @property
    def ep_lengkap(self):
        return self.standard_item_id is None or self.ep_status in ('TERPENUHI', 'NA')
```

Satu EP per baris (sesuai wireframe: satu chip EP + gear). EP lintas-tindakan tetap ditangani grid visit-level `KorelasiEpAsesmen` yang sudah ada.

### 5.2 Aturan EP per tindakan: `klinis.AturanEpTindakan`

```python
class AturanEpTindakan(models.Model):
    JENIS = [('ICD9', 'ICD-9-CM'), ('SIKI', 'SIKI'), ('ANY', 'Semua')]
    jenis        = CharField(max_length=6, choices=JENIS, default='ICD9')
    kode         = CharField(max_length=20, blank=True)   # '' = berlaku untuk semua kode
    sub_standard = CharField(max_length=50)
    label        = CharField(max_length=150)
    wajib        = BooleanField(default=True)
    urutan       = PositiveIntegerField(default=0)         # urutan 1 = EP utama baris
    unique_together = [('jenis', 'kode', 'sub_standard')]
```

Resolver `klinis.services.ep_tindakan.resolve_for(jenis, kode)`:
1. Ambil aturan `jenis` sama + `kode` sama, urut `urutan`.
2. Bila kosong, ambil aturan `jenis='ANY'` + `kode=''`.
3. Buang `sub_standard` yang tidak ada di `StandardItem` (mis. `KPR 3`), kembalikan sisanya.
4. Tidak pernah melempar exception; tidak pernah menulis baris EP sendiri.

Seed awal (semua kode terverifikasi ada di katalog):

| Kode | EP utama | EP kedua |
|---|---|---|
| `99.18` (infus) | `PAP 3` | `SKP 1` |
| `99.29` (injeksi/obat) | `SKP 3` | `SKP 1` |
| `99.60` (resusitasi) | `PAP 3` | `PAP 8` |
| `96.04` (intubasi) | `PAP 3` | `PAP 8` |
| `89.52` (EKG) | `PAP 3` | — |
| `01.24`, `47.09` (tindakan invasif) | `PAP 3` | `HPK 3` |
| SIKI `I.08238` (Manajemen Nyeri) | `PP 2` | — |
| SIKI `I.12383` (Edukasi Kesehatan) | `HPK 1` | — |
| SIKI `I.14539` (Pencegahan Infeksi) | `PPI 1` | `SKP 1` |
| ANY | — | — |

### 5.3 Resolusi tarif & override

```
baris ICD9 dipilih
  → resolve_detail(kunjungan, kode)         # dict: nominal, tindakan, icd9, kelompok, penjamin
  → tarif_acuan = nominal (Decimal | None)  # di-refresh setiap simpan, bukan snapshot beku
  → tarif = input petugas bila diisi, jika tidak None
  → tarif_efektif = tarif ?? tarif_acuan
  → validasi: bila tarif != tarif_acuan dan catatan_tarif kosong → tolak dengan pesan, jangan diam-diam
  → sync: BillingItem(kunjungan, JASA_MEDIS, kode_icd, sumber='ASESMEN')
          harga_satuan = tarif_efektif, nama_item = baris.nama
  → bila tarif_efektif None → TIDAK menulis BillingItem (UI: "Tarif belum ditetapkan")
```

Aturan keras:
- Tidak pernah menulis `Rp 0`.
- `sync_billing` lama tetap ada untuk pemanggil teks bebas; fungsi baru `sync_billing_tindakan(kunjungan, lines, user)` yang memakai `tarif_efektif`.
- Baris `sumber='MANUAL'` tidak pernah disentuh.
- Bila baris dihapus dari form → `BillingItem` ASESMEN-nya dihapus, baris lain tetap.
- Override dicatat ke `akreditasi.AuditLog` (`aksi='UPDATE'`, `model_name='TindakanAsesmen'`, detail menyebut acuan → final + alasan).

### 5.4 Alur simpan (dua handler)

`igd_asesmen_awal_save` dan `igd_asesmen_medis_save` memakai parser yang sama:

```python
TINDAKAN_RE = re.compile(r'^tindakan_(\d+)_id$')

def parse_tindakan(request) -> list[dict]:
    idxs = sorted({int(m.group(1)) for key in request.POST if (m := TINDAKAN_RE.match(key))})
    ...
```

Field POST per baris: `tindakan_<i>_id|jenis|kode|nama|sumber|tarif|catatan_tarif|ep_sub|ep_status|ep_catatan|hapus`.
Kunci terindeks dipilih (bukan Django formset) karena: form di-render dua tempat dengan prefix berbeda, baris ditambah/dihapus via JS, dan seluruh handler di repo ini sudah memakai parsing POST manual. Tradeoff: validasi ditulis tangan — ditutup oleh test.

Duplikat kode dalam satu kunjungan: pertahankan baris pertama, kirim pesan `info`, jangan buat dua baris billing.

### 5.5 Komposisi UI

Satu partial baru: `templates/pasien/_tindakan_tarif_ep.html`, dipakai wizard (tab Diagnosa) dan modal IGD. Isi per baris:

```
[kode] [nama editable]        [Master|Saran|Manual]        [🗑️]
  Tarif acuan: Rp 150.000     Tarif: [ 150000 ]  ✏️        (catatan alasan bila beda)
  EP: [ PAP 3 — gawat darurat ▾ ]  Status: (•) Terpenuhi ( ) Belum ( ) NA   🟢
```

Strip rekap di bawah daftar: subtotal medis, subtotal keperawatan, total, `N EP terpenuhi (kode…)`.
Dropdown EP memuat **136 sub_standard** (bukan 301 EP) dan disimpan sebagai `sub_standard`; server memetakan ke `StandardItem` pertama — pola yang sama dengan grid visit-level.
Input `name="icd9_tindakan"` (readonly) tetap dirender dan tetap diisi ringkasan nama baris oleh server, agar cetak `cetak_asesmen_medis_igd.html` dan test lama tidak putus.

### 5.6 Saran ICD tanpa LLM

Tidak ada dependensi LLM di repo (`grep openai|anthropic|gemini|ollama` → nol). Karena itu "AI Suggestion" diimplementasikan sebagai **saran deterministik**:

`klinis.services.saran.saran_untuk(kunjungan, q='', jenis='ICD10')`
- Batasi ke `KasusTersering.kelompok == kelompok kunjungan`.
- Skor = jumlah token `q` (≥3 huruf, lowercase) yang muncul di `icd10.nama` + `tatalaksana`; tanpa `q` → urut `urutan` pertama 5.
- Kembalikan `{kode, nama, alasan, tindakan:[kode…]}`.
- Endpoint: `GET /pasien/api/saran-icd/?kunjungan=<pk>&q=&jenis=ICD10|ICD9`.
- UI menampilkan chip berlabel **"Saran Sistem"**, bukan "AI". Bila kelak dipasang LLM, kontrak endpoint tidak berubah — hanya provider di balik service.

### 5.7 Keputusan & tradeoff

| # | Keputusan | Tradeoff |
|---|---|---|
| A1 | Baris = model baru `TindakanAsesmen`; uang tetap di `BillingItem` | +1 tabel, +1 migrasi; sebagai imbalan atribut klinis tidak mengotori billing |
| A2 | Satu EP per baris + grid EP visit-level | Dokumen menampilkan satu EP per baris; multi-EP per baris ditunda. Tidak ada kehilangan cakupan karena EP lintas-tindakan tetap di grid |
| A3 | `tarif_acuan` di-refresh tiap simpan, `tarif` (override) dipertahankan | Tarif master berubah → acuan ikut berubah; nominal yang sudah di-override tidak berubah. dapat diaudit lewat `AuditLog` |
| A4 | Tarif SIKI tidak di-seed | Tidak mengarang angka; petugas mengisi manual, `tarif_acuan` tetap `NULL` dan UI menyatakan "belum ditetapkan" |
| A5 | Aturan EP berbasis kode eksplisit | Flag `invasif/consent` kosong di seed, jadi tidak dipakai; aturan kode lebih mudah diaudit |
| A6 | Saran deterministik, bukan LLM | Tidak ada biaya/latensi/halusinasi; label UI jujur. Seam provider disiapkan |
| A7 | Parser POST terindeks, bukan formset | Konsisten dengan gaya repo dan dua titik render; validasi manual ditutup test |
| A8 | Satu partial dipakai dua template | Menghapus duplikasi JS picker lama di wizard **hanya** untuk blok baru; JS lama (`updateSkorNyeri`, `hitungMst`, `setNormalAsesmen`, `hitungMorse`) tidak disentuh |

---

## 6. Perubahan model & migrasi

| App | Perubahan | Migrasi |
|---|---|---|
| `klinis` | `AturanEpTindakan` (baru) | `0002_aturan_ep_tindakan` |
| `pasien` | `TindakanAsesmen` (baru) | `0017_tindakan_asesmen` |
| `pasien` | `LampiranAsesmen.JENIS` + `RUJUKAN` | termasuk `0017` |
| `pasien` | Backfill `TindakanAsesmen` dari `BillingItem(sumber='ASESMEN')` | data migration di `0017` |

Backfill: untuk setiap `BillingItem(sumber='ASESMEN')` dengan `kode_icd` yang cocok `MasterIcd9`, buat baris `jenis='ICD9'`, `kode=kode_icd`, `nama=nama_item`, `tarif=tarif_acuan=harga_satuan`, `sumber_data='MASTER'`, `billing_item=item`, `urutan` berurutan per kunjungan. Reverse: hapus semua `TindakanAsesmen` (tabel baru, tidak ada konsumen lain).

---

## 7. Non-goals

- Tidak ada grouper INA-CBG; "tarif BPJS" tetap tarif satuan verifikasi klaim.
- Tidak ada integrasi LLM / API eksternal.
- Tidak mengubah `KasusTindakan` (tetap ICD-9 saja) dan tidak mengubah `sdm.KatalogTindakan`.
- Tidak ada versi/history tarif; jejak perubahan lewat `AuditLog` saja.
- Tidak ada multi-EP per baris dan tidak ada billing export.
- Tidak menyentuh `akreditasi.StandardItem` (read-only).
- Tidak me-refactor JS asesmen yang sudah hijau.

---

## 8. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Migrasi tidak jalan otomatis di deploy | 500 di produksi | Migrasi manual ke Supabase sebelum push, tercantum di DoD |
| Override tertimpa saat simpan ulang | Salah tagih | `sync_billing_tindakan` hanya menulis `tarif_efektif`; test regresi khusus |
| Parser POST salah indeks | Baris hilang/duplikat | Test untuk: tambah, edit, hapus, duplikat kode, baris tanpa tarif |
| Partial baru memecah 3 kelas test UX | Suite merah | Jalankan `tests_asesmen_awal_ux`, `tests_revisi_asesmen_awal`, `tests_igd_modal_scroll` setelah Task 6/7; perbaiki kode, bukan test — kecuali test mengunci DOM chip lama, maka update test secara sadar di commit yang sama |
| `PAP 2.1`/`PAP 1.1`/`KPR 3` dipakai hardcode | Baris EP tidak tersimpan | Resolver prefix + buang yang tidak ada + test `unresolved` |
| Kode ICD-9 sama punya beberapa tarif | Tarif tak terduga | Perilaku v1 dipertahankan & didokumentasikan (D7); override tersedia untuk koreksi |
| 301 `StandardItem` dirender per baris | DOM berat | Dropdown per baris memakai 136 `sub_standard`, bukan 301 EP |
