# Analisa Bug — Sinkronisasi EP dengan AI tidak bisa masuk

**Tanggal:** 2026-10-20
**Sumber:** `Downloads/Ini ada masalah sinkronisasi dengan AI tidak bisa 20-10.docx`
**Bukti visual:** screenshot `…/indikator-mutu/209/edit/` (Firefox, login `basirun`, 20 Okt 2026 07:35)
**Kode yang dianalisa:** `master` @ `efc96ec` = SHA yang dibangun Vercel production
(`dpl_oKwcNkEHEG8qq5NiBcAZ8ay8MMdQ`, alias `sim-akreditasi-django.vercel.app`)
**Plan perbaikan terkait:** `docs/superpowers/plans/2026-10-20-fix-ep-ai-sync-blocked.md`

---

## 1. Keluhan pengguna

> "Sewaktu akan sinkronisasi EP, mengisi standar akreditasi dengan bantuan AI tidak
> masuk, walaupun sudah mengosongkan link ke system."

Dua makna yang terbaca dari kalimat + screenshot:

1. **Terblokir.** Tombol *Cocokkan dengan AI* menolak dengan banner merah
   *"EP sudah terhubung manual. Kosongkan dulu kolom EP bila ingin mengganti."*
   padahal dropdown EP di layar menampilkan **"— Tidak Di-link ke EP Spesifik —"**
   (kolom sudah kosong di mata pengguna).
2. **Tidak tersimpan.** Hasil rekomendasi AI yang dipilih operator tidak berujung
   menjadi link di database ("tidak masuk").

---

## 2. Fakta kode (terbukti, bukan dugaan)

Semua rujukan pada `master`/`efc96ec`.

| # | Fakta | Lokasi |
|---|---|---|
| F1 | Guard menolak AI **hanya** bila `ep_terkait_id` terisi **dan** `ep_sumber == 'MANUAL'`. Pesan error tidak menyebut EP mana yang terkait. | `akreditasi/ai_views.py:308-312` |
| F2 | Guard membaca **database** (fetch ulang `IndikatorMutu`), bukan nilai form yang sedang diedit. | `akreditasi/ai_views.py:296-301` |
| F3 | Mengosongkan dropdown saat Simpan menulis `ep_sumber = 'MANUAL'` + `ep_skor = None` — artinya **baris "kosong" pun ditandai sebagai sentuhan manusia** dan auto-sync tidak akan pernah mengisinya lagi. | `akreditasi/indikator_views.py:588-595` |
| F4 | Tombol **Pakai** pada hasil AI **hanya memindahkan dropdown di browser**; tidak ada satu pun permintaan jaringan. Link baru masuk database **hanya** setelah *Simpan Perubahan* ditekan. | `templates/akreditasi/indikator_form.html:579-587` |
| F5 | Panggilan DeepSeek memakai `timeout=120` detik untuk prompt ±35k token (seluruh katalog 1053 EP, 115.707 karakter). | `akreditasi/ai_service.py:630` |
| F6 | Seluruh aplikasi Django di Vercel dibatasi `maxDuration: 60` detik per request. | `vercel.json:8` |
| F7 | Bila AI dimatikan/gagal, server **berhasil** mengembalikan daftar lexical (precision@1 terukur 10%) dengan banner kuning, bukan merah. | `akreditasi/ai_service.py` `generate_ep_rekomendasi` → `_lexical()` |
| F8 | Kode EP dari AI divalidasi terhadap katalog, lalu dipetakan ke `data-code` option dropdown → kasus "kode tidak ada di daftar" tidak mungkin pada jalur AI. | `ai_service.py` + `indikator_form.html:474-478` |
| F9 | Dropdown EP di halaman edit memuat **seluruh** `StandardItem` tanpa cap `[:200]` (cap sudah dihapus di `fa921a5`). | `akreditasi/indikator_views.py:575` |

**Kontradiksi yang harus dijelaskan:** F1 mensyaratkan `ep_terkait_id` terisi, tetapi
screenshot menampilkan placeholder. Keduanya tidak bisa benar bersamaan — kecuali
nilai form dan nilai database berbeda.

---

## 3. Hipotesis penyebab (diurutkan keyakinan)

### H1 — Link manual belum benar-benar terhapus di database *(paling mungkin)*

Skenario: operator mengosongkan dropdown lalu menekan *Cocokkan dengan AI*
**sebelum** menekan *Simpan Perubahan* — atau simpan sebelumnya gagal dan nilai
yang tampil adalah nilai dalam memori, bukan nilai tersimpan. Guard tetap melihat
link lama → banner merah muncul di layar yang sudah kosong.

**Mengapa ini jebakan desain, bukan sekadar salah klik:** pesan memerintahkan
"Kosongkan dulu kolom EP", sedangkan kolom di layar *sudah* kosong. Pengguna tidak
punya cara melihat EP mana yang masih menempel di server, dan tidak ada umpan balik
"perubahan belum disimpan". Kegagalan simpan pun hanya muncul sebagai flash message
sebentar di halaman detail setelah redirect.

**Cara memastikan (1 menit):**

```sql
SELECT id, kode_indikator, ep_terkait_id, ep_sumber, ep_skor, updated_at
FROM akreditasi_indikatormutu WHERE id = 209;
```

- `ep_terkait_id IS NOT NULL` → H1 terkonfirmasi.
- `ep_terkait_id IS NULL` → H1 gugur, lihat H2.

### H2 — Link ada tetapi option EP-nya tidak ikut terrender *(perlu dicek)*

Bila `ep_terkait_id` terisi namun option dengan `value` itu tidak ada di `ep_list`,
browser menampilkan option pertama = placeholder, dan guard tetap menolak. Dari kode,
`ep_list` tidak difilter sehingga kasus ini kecil — tetapi mudah dibuktikan:

```sql
-- opsi yang dirender = SELECT id FROM akreditasi_standarditem ORDER BY …
SELECT si.id, si.code FROM akreditasi_standarditem si WHERE si.id = <ep_terkait_id>;
```

Bila baris tidak ada → FK menggantung (`on_delete=SET_NULL` seharusnya mencegah ini,
tetapi perlu dicek apakah ada rekam jejak delete lewat SQL langsung).

### H3 — Panggilan AI dibunuh limit 60 detik Vercel *(penyebab terpisah untuk "AI tidak bisa")*

F5 vs F6: model diberi 120 detik, lambda mati di 60 detik. Prompt 35k token butuh
prefill + 1200 token output yang waktunya berada di sekitar batas itu. Bila lambda
mati, **fallback lexical tidak sempat berjalan** (fallback terjadi di sisi server),
dan klien menerima HTML 504 → `r.json()` melempar error → banner merah dengan pesan
yang tidak informatif.

Ini **bukan** pesan yang terlihat di screenshot, jadi H3 adalah temuan terpisah —
tetapi ia menjelaskan versi keluhan "AI tidak bisa" yang lebih berat.

**Cara memastikan:** buka DevTools → Network → POST `/ai/ep-rekomendasi/`, baca
status code dan waktu. 504 / `ERR_CONNECTION_RESET` / >60 dtk = H3 terkonfirmasi.
Durasi juga tercatat di `AuditLog` (`_log_ai_call`, `model_name='AI_DEEPSEEK'`).

### H4 — Rekomendasi dipilih tapi form tidak disimpan

Bila H1 gugur dan panggilan AI sukses, "tidak masuk" paling mungkin berarti
operator menekan *Pakai* (F4) lalu menutup halaman tanpa *Simpan Perubahan*.
Tidak ada peringatan "ada perubahan belum disimpan" dan label *Dipakai ✓*
terbaca seperti status tersimpan.

---

## 4. Cacat desain yang pasti ada (berlaku di semua hipotesis)

| ID | Cacat | Dampak |
|---|---|---|
| **D1** | Guard membaca database, UI menampilkan form. | Dua state berbeda di layar yang sama; pesan perintahnya tidak bisa dipenuhi pengguna. |
| **D2** | Pesan error tidak menyebut EP yang menghalangi. | Pengguna tidak tahu harus menghapus apa; dead-end. |
| **D3** | Mengosongkan EP justru menulis `ep_sumber='MANUAL'`. | Setiap baris yang pernah disentuh (termasuk yang dikosongkan) ditandai manual → auto-sync `sync_ep_indikator` tidak akan pernah mengisinya; provenance rusak. |
| **D4** | *Pakai* tidak mempertahankan apa pun tanpa simpan penuh. | Hasil AI "hilang" bila operator lupa/keluar; tidak ada status *tersimpan*. |
| **D5** | Tidak ada indikator ketersediaan AI sebelum tombol ditekan (flag `ai_enable_ep_sync`, `ai_enabled`, API key). | Operator baru tahu AI mati setelah klik; hasil lexical terbaca sebagai "hasil AI". |
| **D6** | `timeout=120` > `maxDuration=60`, dan timeout klien tidak ditangani. | Gagal seluruhnya tanpa fallback; pesan error membingungkan. |

---

## 5. Batasan lingkup analisa

- Penelusuran berbasis kode + screenshot; **belum ada akses ke database produksi**
  (konektor Supabase belum tersambung, tidak ada `DATABASE_URL` lokal), jadi H1/H2
  belum diverifikasi langsung.
- Tidak ada virtualenv di worktree ini → suite test Django belum bisa dijalankan
  dari sesi ini (`python -c "import django"` → `ModuleNotFoundError`).
- Worktree aktif `faishaltsq/medaka` **tidak memuat** fitur EP sync; seluruh kode di
  atas dibaca dari `master` lewat `git show`.
