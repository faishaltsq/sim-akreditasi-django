# ⚙️ SOP Pembaruan Fitur & Dokumentasi Sistem
### *SIM Akreditasi RS MonsisKami — Panduan Developer & Tim IT*

> **WAJIB DIBACA** oleh developer setiap kali merilis fitur baru ke production.
> Tujuan: Dokumentasi sistem selalu sinkron dengan fitur yang berjalan.

---

## Aturan Pembaruan Dokumentasi

> ☝️ **Aturan Emas:** Tidak ada fitur yang boleh di-deploy ke production sebelum dokumentasi-nya diperbarui atau ditambahkan.

---

## Checklist Deploy Fitur Baru (Wajib Dilengkapi)

Salin checklist ini ke setiap **Pull Request / Merge Request** fitur baru:

```markdown
## Checklist Dokumentasi Fitur: [Nama Fitur]

### 1. File Dokumentasi yang Diperbarui/Ditambahkan:
- [ ] `docs/README.md` — Tabel Indeks Modul diperbarui (jika ada modul baru)
- [ ] `docs/0X_MODUL_TERKAIT.md` — Konten/langkah diperbarui di modul yang relevan
- [ ] `docs/06_STANDAR_OPERASIONAL_UPDATE_FITUR.md` — Log Rilis Fitur ditambah (wajib)
- [ ] `docs/PANDUAN_LENGKAP_RS_MONSISKAMI.html` — Section baru ditambah di portal HTML

### 2. Kode & Teknis:
- [ ] Migrasi database dibuat (jika ada perubahan model)
- [ ] URL baru sudah didaftarkan di `akreditasi/urls.py`
- [ ] Navigasi sidebar diperbarui di `templates/includes/sidebar.html`
- [ ] `python manage.py check` → 0 issues
- [ ] Commit dengan format: `feat(scope): deskripsi singkat`

### 3. Deployment:
- [ ] `railway up --detach` dijalankan dan build sukses
- [ ] `git push origin master` berhasil
- [ ] URL production diverifikasi (HTTP 200/302 pada endpoint baru)
```

---

## Format Log Rilis Fitur (Diisi di Bawah Ini)

Setiap rilis wajib ditambahkan sebagai satu baris/blok di tabel berikut:

---

### 📋 Log Rilis Fitur

| Versi | Tanggal | Commit | Deskripsi Fitur | Modul Docs yang Diperbarui |
|---|---|---|---|---|
| v1.0 | 2026-09-24 | `initial` | Fondasi SIMRS: Pokja, Standar, EP, Matriks PDCA, Upload Bukti RDWOS | README, 01, 02, 03 |
| v1.1 | 2026-09-24 | `rbac` | Role-Based Access Control: 6 role, smart redirect nakes, permission guard per view | 01 (akun demo) |
| v1.2 | 2026-09-24 | `nakes` | Modul Portofolio Nakes: STR, SIP, SIK, SPK, RKK, Ijazah, Sertifikat | 05 |
| v1.3 | 2026-09-24 | `supabase` | Supabase Storage + RLS Fix: upload berkas ke cloud, signed URL baca | 02 (upload) |
| v2.0 | 2026-09-25 | `8ab3579` | **Fase 1–5 Besar:** Branding RS MonsisKami, Pohon 65 Unit, Manajemen Risiko 5×5, Lapor Insiden Anonim, Auto-Scoring KARS, Cetak PDF native | 01, 02, 03, 04, 05 |
| v2.1 | 2026-09-25 | `42b5b4f` | Fix: Login page branded, Profil RS data migration, A11y labels (14 input) | 01 |
| v2.6.1 | 2026-10-25 | `cache-fingerprint` | Fix konsistensi sidebar expanded dan layout Integrated Control compact melalui URL aset statis ber-fingerprint; cache lama browser tidak lagi menahan CSS/JS deploy sebelumnya | 06 |
| v3.0 | 2026-10-26 | `uiux-remake` | Remake UI/UX inti akreditasi: DESIGN.md, IBM Plex, satu sistem token di `style.css`, rail navigasi bertema tugas, dashboard berfokus kesiapan, matriks PDCA dengan sel yang bisa dioperasikan keyboard, halaman EP, dokumen bukti, dan login | 01, 05, 06 |
| v3.1 | 2026-10-27 | `crud-hardening` | Hasil audit CRUD 5 modul: RBAC tulis modul Risiko (`can_manage_risiko` + lingkup unit), `unit_delete` menangani `ProtectedError` dengan pesan yang bisa dibaca, migrasi `sdm.0043`/`0044` diterapkan. Laporan lengkap: `docs/qa/crud-0{1..5}-*.md` | 04, 06, QA |

---

## Template Penambahan Section Baru di Docs

Saat fitur baru tidak masuk ke modul yang sudah ada, buat file `docs/0X_NAMA_MODUL_BARU.md` dengan template berikut:

```markdown
# [Emoji] [Nama Fitur/Modul]
### *SIM Akreditasi RS MonsisKami — [Sub-judul singkat]*

---

## [Nama Sub-Modul 1]

### Apa Tujuannya?
[Jelaskan tujuan fitur/modul ini dalam 2–3 kalimat.]

### Cara [Tindakan Utama]:
1. ...
2. ...
3. ...

> 💡 **Tips:** [Tambahkan tips berguna jika ada]

---

## [Nama Sub-Modul 2]
[dst...]
```

Kemudian daftarkan di tabel `docs/README.md`.

---

## Kontak & Eskalasi Teknis

| Peran | Tanggung Jawab |
|---|---|
| **Developer Utama** | Rilis fitur, deploy Railway, update docs |
| **Admin SIMRS (admin.mutu)** | Verifikasi konten docs sudah sesuai alur kerja RS |
| **Direktur IT / SIMRS** | Persetujuan deploy ke production |

> 📧 Issues teknis: buat laporan di **[GitHub Repository](https://github.com/faishaltsq/sim-akreditasi-django/issues)**

---

## Jenjang Karir RKK & Modul Orientasi Staf (KPS 4 & KPS 8) — 2026-10-27

### Apa Tujuannya?
Menyaring katalog RKK per jenjang karir pegawai, membuka verifikasi logbook
oleh preseptor berbasis jenjang, serta melengkapi modul orientasi: jenis
umum/khusus, auto-assign, post-test, sertifikat & TOR PDF, dashboard, dan
pengingat.

### Cara Menggunakan:
1. **Set jenjang pegawai**: HC edit pegawai → kolom "Jenjang Karir (Master)".
   Katalog logbook & pengajuan kredensial otomatis tersaring ke jenjang itu
   (tanpa jenjang = perilaku lama per profesi).
2. **Preseptor**: jenjang dengan urutan ≥ ambang (default 3: Madya/PK III/BK III)
   boleh memverifikasi logbook unitnya tanpa grant HC; kandidat tampil di
   antrean verifikasi.
3. **Seed program baku**: `manage.py shell` →
   `from sdm.services.orientasi import seed_program_baku; seed_program_baku()`
   (idempoten; sudah dijalankan di DB lokal).
4. **Auto-assign**: finalisasi input pegawai baru atau penempatan baru otomatis
   menugaskan Orientasi Umum + Khusus sesuai kelompok staf (matriks durasi:
   ners 90 hari, medis/nakes lain 28, non-klinis 14, umum 3).
5. **Post-test**: pada detail penugasan, input nilai 0–100. Lulus ≥ 80 →
   status berubah SELESAI bila semua aktivitas wajib selesai. Remedi → tenggat
   diperpanjang satu siklus.
6. **Unduh**: sertifikat PDF per penugasan lulus; TOR PDF per program dari
   daftar orientasi; rekap dashboard PDF (menghormati filter unit/status).
7. **Reminder**: `manage.py hc_reminders` kini juga mengingatkan preseptor
   unit untuk penugasan yang mendekati/lewat tenggat (tipe PRESEPTOR).

> 💡 **Batasan:** daftar tindakan RKK dokter sengaja kosong sampai SK komite;
> reminder hanya in-app (email/WhatsApp menyusul bila dibutuhkan).

---

## Kaskade Pemilihan Nakes & Katalog Tindakan Tertutup — 2026-10-27

### Apa Tujuannya?
Melengkapi katalog RKK dokter dari dokumen "Katalog tindakan klinis" (RS Tipe B),
menambah 105 butir nakes lain per level, dan menghidupkan alur kaskade
Level → Spesialisasi → Tindakan pada detail kredensial.

### Cara Menggunakan:
1. **Seed** (idempoten, sudah dijalankan di DB lokal):
   `manage.py seed_katalog_rkk --apply` → +34 jenjang spesialisasi/subspesialisasi,
   +226 butir (dokter 121 + nakes 105), total katalog 499.
2. **Kaskade di detail kredensial**: dropdown "Jenjang / Spesialisasi" muncul di
   atas katalog. Bawaan = jenjang pegawai; pilih lain untuk menyaring;
   "— semua jenjang profesi —" melepas saringan.
3. **Spesialisasi bebas**: pengaju berjenjang `SP-*`/`SUBSP-*`/`DU-SP`/`DU-KONS`
   mendapat kolom "Spesialisasi / Subspesialisasi" di portal pengajuan mandiri;
   tercetak di berita acara rapat.
4. Status M/S butir nakes lain mengikuti dokumen; yang baku berstatus 'S'
   + catatan "Status baku belum ditetapkan; tinjau komite."

> 💡 DOKTER_SP kini punya jenjang; daftar subspesialisasi memakai urutan 3.
