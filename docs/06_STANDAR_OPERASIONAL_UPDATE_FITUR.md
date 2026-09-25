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
