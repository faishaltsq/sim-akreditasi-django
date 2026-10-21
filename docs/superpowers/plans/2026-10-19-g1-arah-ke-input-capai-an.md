# Plan: G.1 Evaluasi — hapus blok input manual, arahkan ke Input Capaian

**Tanggal:** 2026-10-19
**Sumber:** `C:\Users\cubeb\Downloads\Ini bagian evaluasi dan monitoring setelah pelaksanaan.docx`
**Status:** Selesai — 322/322 hijau, di-push
**Baseline suite:** 322/322 (setelah commit `fa921a5`)

## 1. Requirement (teks asli dari docx)

Docx hanya berisi 3 baris teks + 2 gambar:

> "Tulisan indicator mutu terkait ---kebawah dihapus"
> "Diganti ini (input capaian)"

**Gambar 1** — `…/risiko/134/evaluasi/`, seksi **"G.1 Capaian Indikator Mutu & Bukti Pendukung"**.
Blok yang dimaksud (dari pill ke bawah, persis yang ditandai "kebawah dihapus"):

- pill teal `Indikator Mutu Terkait` + `(Belum ditautkan ke Indikator Mutu formal)`
- help text `Tautkan indikator mutu terlebih dahulu…`
- box `Target Standar Mutu:` (badge `Rencana` + `≥100.0 %`)
- `🔗 Tautkan ke Indikator Mutu` (select `name="indikator_mutu_terkait"`, id `link-indikator-select`)
- `Target Capaian (%)` (`name="target_capaian_indikator"`)
- alert kuning `Indikator yang Anda tulis manual saat perencanaan…` (`indikator_manual_hint`)
- (di bawah fold) `Nilai Capaian Realisasi (%) *` (`capaian_nilai`) + badge gap live
- `Kategori Dokumen Bukti` (`jenis_dokumen_capaian`)
- `Upload Bukti Capaian (max 10MB)` (`bukti_capaian`)

**Gambar 2** — `…/indikator-mutu/226/capaian/`, **"Input Capaian Bulanan"** (yang menggantikan):
breadcrumb `Indikator Mutu / IMP-UNIT-RANAP-01 / Input Capaian`, kartu judul + kode indikator,
info box Target / Numerator / Denominator, field `Bulan *`, `Tahun *`, `Nilai Numerator *`,
`Nilai Denominator *`, upload bukti. Halaman ini **sudah ada** — `akreditasi/indikator_views.py:421`
`indikator_input_capaian` → menulis `CatatanIndikator` per (indikator, bulan, tahun).

**Inti requirement:** capaian tidak lagi diketik inline di halaman evaluasi risiko; kapasitas input
itu pindah penuh ke halaman Input Capaian. Halaman evaluasi tinggal **menampilkan** hasilnya dan
**mengarahkan** ke sana.

## 2. Desain

### Sumber kebenaran capaian

`RisikoUnit.capaian_nilai` (angka manual, diisi di form evaluasi) selama ini satu-satunya sumber
untuk statistik monev, laporan, dan prompt AI. Setelah input inline dihapus, sumber baru:

```
CatatanIndikator (bulan, tahun, num, den)  ←  ditulis oleh indikator_input_capaian
        ↓ agregat per tahun: Σnum / Σden × faktor
RisikoUnit.capaian_evaluasi['capaian']     ←  fallback bila capaian_nilai NULL
```

- `capaian_nilai` manual **tetap menang** bila terisi (tidak ada data yang hilang, tidak ada migrasi).
- Agregat memakai rumus identik dengan `CatatanIndikator.nilai_capaian`
  (`faktor = 100` bila `tipe_pengukuran == 'persen'`, else `faktor_pengali`), dihitung dari
  **jumlah numerator/denominator**, bukan rerata persen bulanan (rerata menyetarakan bulan
  dengan denominator kecil dan besar).
- `_indikator_rencana()` / dropdown penautan di halaman evaluasi **dihapus**; penautan tetap ada di
  form perencanaan/edit risiko (`templates/akreditasi/risiko_form.html:447`).

### Bentuk G.1 baru (read-only)

Satu kartu: badge kode + nama + dimensi indikator → box Target (`ev_capaian` + `arah` +
`|unlocalize`) → baris agregat (`n/12 bulan terisi`, `Σnum/Σden`, `%`, status tercapai/tidak)
→ tombol `Input Capaian Bulanan` (manager) + `Edit Indikator` + `Lihat detail & bukti`.
Bila belum tertaut: hint + tombol `Tautkan di Perencanaan Risiko` → `risiko_edit` (tanpa dropdown).

### Dampak yang harus ditangani (temuan riset)

| Dampak | Lokasi | Penanganan |
|---|---|---|
| JS tombol AI hard-stop kalau `capaian_nilai` kosong (`alert` + `focus()` lalu return) | `risiko_evaluasi.html:742-747` | payload ganti jadi `risiko_id`, capaian/target/gap dihitung **server-side** |
| Payload AI dibangun dari input yang dihapus (`targetVal`, `capaianVal`) | `risiko_evaluasi.html:769-771` | server ambil dari `RisikoUnit` + agregat |
| Linking POST `indikator_mutu_terkait` jadi tak terjangkau UI | `risiko_views.py:803-810` | branch tetap dipertahankan (guarded, no-op, kompatibel test lama) |
| Context jadi mati | `risiko_views.py:909-919, 926, 933-935` | dibuang dari context (hanya dipakai blok yang dihapus) |
| Test lama menguji dropdown yang dihapus | `tests_evaluasi_indikator.py:106-110, 226-250` | dirombak, ditambah uji kondisi baru |
| Monev/laporan baca `r.capaian_nilai` mentah | `risiko_views.py:1009, 1107, 2128`; `risiko_monitoring_evaluasi.html:283-286`; `risiko_laporan_lengkap.html:488, 912` | **di luar scope** (lihat §5) — nilai manual lama tetap tampil, data baru muncul via `capaian_evaluasi` |

## 3. Architecture

1. **`IndikatorMutu.agregat_capaian(tahun)`** (baru, `risiko_models.py`) — satu query
   `SUM(nilai_numerator)`, `SUM(nilai_denominator)`, `Count` bulan valid. Return
   `{'tahun', 'num', 'den', 'bulan_terisi', 'capaian'}` (`capaian=None` bila `den <= 0`).
2. **`RisikoUnit.capaian_evaluasi`** (ada) — `capaian_nilai` menang; kalau NULL dan ada indikator
   tertaut, pakai `agregat_capaian()`. Tambah kunci baru **`capaian_sumber`**
   (`'manual' | 'catatan' | None`). Kunci `sumber` (sumber **target**: rencana/master/tidak_ada)
   tidak disentuh — template memakainya untuk badge `Rencana` (`risiko_evaluasi.html:213`).
3. **`capaian_persen_display`** (ada) — fallback yang sama supaya monev/laporan tidak
   menampilkan `—` padahal ada data bulanan.
4. **`risiko_evaluasi` GET** — context bersih (tanpa kandidat/hint/jenis_dokumen) +
   `agregat` untuk kartu.
5. **`api_ai_evaluasi_risiko`** — terima `risiko_id` opsional; bila ada, seluruh payload
   (unit, jenis, deskripsi, skor, nama indikator, target, capaian, gap) diambil dari model.
   Field eksplisit dari payload lama tetap didahulukan → test lama tetap hijau, endpoint tetap
   kompatibel.
6. **Template + JS** — blok 173–310 dihapus; kartu read-only masuk; JS penautan + live-gap
   dihapus; tombol AI kirim `risiko_id`.

**Tidak ada migrasi** — tidak ada field model yang ditambah/diubah/dihapus.

## 4. Tasks & Steps

### Task 1 — Resolver agregat capaian
- [x] Tambah `IndikatorMutu.agregat_capaian(tahun: int) -> dict` di `akreditasi/risiko_models.py`
      (tepat setelah helper sejenis; `from django.db.models import Sum, Count` bila belum ada).
      Rumus = `CatatanIndikator.nilai_capaian` line 684-697; `den <= 0` → `capaian = None`;
      bulan dihitung hanya yang `den > 0`.
- [x] `RisikoUnit.capaian_evaluasi` (line 227): fallback ke agregat bila `capaian_nilai is None`
      dan `indikator_mutu_terkait` ada; tambah kunci `capaian_sumber`; pastikan return awal
      (line 229-231) juga membawa kunci baru.
- [x] `RisikoUnit.capaian_persen_display` (line 242-246): format dari `capaian_evaluasi['capaian']`
      (manual dulu, lalu agregat) — `f"{x:.1f}%"`.
- [x] Uji unit baru (`tests_evaluasi_indikator.py` atau `tests_risiko*.py`): agregat benar
      (Σnum/Σden×100), `den=0` → None, `tipe_pengukuran='jumlah'` pakai `faktor_pengali`,
      `capaian_nilai` manual **tidak** ditimpa agregat, `capaian_sumber` benar.

### Task 2 — G.1 template: hapus + ganti kartu
- [x] Hapus `templates/akreditasi/risiko_evaluasi.html:173-310` (banner penautan + baris
      `capaian_nilai` / `jenis_dokumen_capaian` / `bukti_capaian`). Pertahankan heading G.1
      (line 168-171) dan blok naratif `evaluasi_capaian` (line 312-332) beserta dua tombolnya.
- [x] Sisipkan kartu read-only baru di tempatnya: `{% load l10n %}` di atas file,
      badge `kode_indikator` + `nama_indikator` + `Dimensi Mutu`, box target
      (`arah_nilai_display`, `target_nilai_display|unlocalize`, `satuan_nilai_display`),
      baris agregat (`bulan_terisi`/12, Σnum/Σden, `ev_capaian.capaian` + status tercapai),
      tombol `Input Capaian Bulanan` → `{% url 'akreditasi:indikator_input_capaian' risiko.linked_indikator.pk %}`,
      `Edit Indikator`, `Lihat detail & bukti` → `{% url 'akreditasi:indikator_detail' … %}`.
- [x] Cabang belum tertaut: hint `Belum ditautkan ke Indikator Mutu formal` + tombol
      `Tautkan di Perencanaan Risiko` → `{% url 'akreditasi:risiko_edit' risiko_id=risiko.pk %}`;
      gate tombol manager dengan `is_manager`.
- [x] Pastikan tidak ada `{{ …|unlocalize }}` numerik tanpa `{% load l10n %}`
      (bug `c4c2a3c` kena dua kali — wajib dicek, locale `id` mengeluarkan koma).

### Task 3 — JS halaman evaluasi
- [x] Hapus blok penautan auto-target (`risiko_evaluasi.html:654-674`) dan mesin live-gap
      (`capaianInput`, `evaluateCapaian`, `statusBadge`, listener) di area 676-735 — baca dulu
      700-735 untuk memastikan batas akhir blok, jangan memotong kode yang dipakai G.2/G.3.
- [x] Tombol AI (`:740-747`): buang guard `capaianVal` + alert; payload jadi
      `{risiko_id: <id>, dampak_residual, prob_residual}` (sumber nilai lain dari server);
      pertahankan penanganan `res.success` yang sudah ada.
- [x] Render halaman lewat test Client lalu jalankan `node --check` pada tiap blok `<script>`
      hasil render (template `{{ }}` membuat parse mentah gagal — aturan lama).

### Task 4 — Server view + endpoint AI
- [x] `akreditasi/risiko_views.py:905-935` — buang `indikator_kandidat`,
      `indikator_kandidat_mode`, `indikator_manual_hint`, `jenis_dokumen_choices`, dan pemanggilan
      `_indikator_rencana()` + regex hint (semua hanya dipakai blok yang dihapus; verifikasi dulu
      dengan grep agar tak mematikan template lain). Tambah context `agregat` (dict dari Task 1).
- [x] `_indikator_rencana` (`:725`) jadi tak terpakai → grep dulu test/pend caller; kalau hanya
      test-nya, hapus test-nya bersama fungsi; kalau ada pemakai lain, biarkan.
- [x] **Pertahankan** seluruh branch POST guarded (`:803-827`) — tak ada input yang mengisinya,
      tapi tetap no-op aman dan membuat test POST lama lulus.
- [x] `akreditasi/ai_views.py:187-203` — bila payload punya `risiko_id`, ambil `RisikoUnit`
      (`select_related('unit','indikator_mutu_terkait')`) lalu isi `unit_name`, `jenis_risiko`,
      `deskripsi_risiko`, `skor_awal/dampak/prob`, `mitigasi_terlaksana`, `dampak/prob_residual`,
      `nama_indikator`, `target_capaian`, `capaian_nilai`, `gap_persen` dari model
        (`target_capaian`/`gap_persen` dari `capaian_evaluasi`; `capaian_nilai` dari
        `capaian_persen_display`); field eksplisit pada payload tetap didahulukan (kompatibilitas mundur);
      `risiko_id` tidak valid/200 tidak ditemukan → 400 seperti sekarang;
      `rate_limit(max_calls=12, window=60, scope='ai')` sudah terpasang — jangan diubah.

### Task 5 — Test
- [x] `tests_evaluasi_indikator.py:95-119` (`test_view_risiko_evaluasi_get`): buang assertion
      `jenis_dokumen_choices` + `jenis_dokumen_capaian`; ganti dengan: heading G.1 tetap ada,
      kartu agregat tampil, URL `indikator_input_capaian` ada di HTML,
      `assertNotContains(resp, 'name="capaian_nilai"')`,
      `assertNotContains(resp, 'link-indikator-select')`.
- [x] `:226-237` (`test_evaluasi_offers_link_when_indikator_missing`): ganti — belum tertaut →
      hint tampil, `assertNotContains(name="indikator_mutu_terkait")`, ada link `risiko_edit`.
- [x] `test_evaluasi_hides_link_ui_when_already_linked` → sesuaikan (dropdown tidak ada untuk
      kedua kondisi; yang berbeda hanya tombol vs hint).
- [x] POST test (`:137+`): buang `capaian_nilai` / `jenis_dokumen_capaian` dari payload (bukti
      tak ada inputnya), pastikan 302 ke detail, `evaluasi_capaian` + status tindak lanjut tetap
      tersimpan, dan `capaian_nilai` lama tidak terhapus.
- [x] Uji endpoint AI dengan `risiko_id` + mock DeepSeek: assert draf terbentuk dan prompt
      memuat capaian agregat (bukan `(belum diisi)`), payload lama tanpa `risiko_id` tetap 200.

### Task 6 — Verifikasi
- [x] `manage.py test akreditasi.tests_evaluasi_indikator` hijau.
- [x] Full suite (`manage.py test`) — baseline **322/322** tidak boleh turun.
- [x] Probe render (test Client): GET `/risiko/<id>/evaluasi/` 200, blok `link-indikator-select`
      hilang, `Input Capaian Bulanan` muncul, POST 302 → detail, endpoint AI 200.
- [x] `node --check` semua blok `<script>` hasil render.
- [x] Commit per-file (`git add <nama>` saja) + push, pantau status Vercel.

## 5. Out of scope

- Kolom `Capaian & Bukti` di monev + laporan tetap membaca `capaian_nilai` mentah — nilai manual
  lama tetap tampil; mengganti ke `capaian_evaluasi` menyentuh 5+ lokasi dan bisa mengubah isi
  laporan formal. Kandidat tindak lanjut terpisah.
- Field `capaian_nilai`, `bukti_capaian`, `jenis_dokumen_capaian` **tidak dihapus** dari model
  (tanpa migrasi, data lama aman, riwayat tetap terbaca di detail risiko).
- Teks naratif `evaluasi_capaian` + `Sisipkan Template Panduan` + `Buatkan Draf Analisis AI`
  **dipertahankan** (narasi Check/Act PDCA, dipakai `risiko_laporan_lengkap`) — ini satu-satunya
  bagian "di bawah pill" yang tidak ikut dihapus; bila ternyata ikut dimaksud, tinggal hapus blok
  `risiko_evaluasi.html:312-332` di task terpisah.
- Penautan indikator dari form perencanaan (`risiko_form.html:447`) tidak disentuh.

## 6. Key decisions

- **Input inline dihapus total, bukan dipindah** — sesuai docx; kapasitas input hidup di satu
  tempat (`CatatanIndikator`) sehingga tidak ada dua tempat yang bisa berbeda angka.
- **`capaian_nilai` manual tetap menang** — tidak ada data historis yang direbut agregat.
- **Agregat Σ/Σ, bukan rerata persen** — matematis benar untuk numerator/denominator.
- **Payload AI memakai `risiko_id`, server yang hitung** — menghapus sumber ganda (nilai yang
  dirender JS vs nilai DB) dan menghapus guard tombol AI yang bergantung pada input yang dihapus.
- **Branch POST lama dipertahankan** — guarded `if key in request.POST`, tak ada biaya, menjaga
  test lama hijau, dan tetap berfungsi bila klien lama masih mengirim field itu.
- **Tanpa migrasi** — perubahan murni template/view/helper property.
