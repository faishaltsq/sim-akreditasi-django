# Plan P3 — Master Data Klinis: Consent Invasif, Validasi Silang & Audit Otomatis IKP

**Spec induk:** `docs/superpowers/specs/2026-11-04-master-data-klinis-terintegrasi.md`
**Prasyarat:** P1 selesai (katalog). P2 opsional — Aturan 3 tidak butuh jam klinis, tapi laporan audit lebih baik jika P2 sudah ada.
**Tanggal:** 2026-11-04. **Repo:** `sim-akreditasi-django` @ `master` (17d3ffc).
**Dependensi:** P1 (katalog ICD-9 + flag `requires_consent`). **Estimasi:** 5 task, ~1 sesi.

---

## Tujuan

Mengimplementasikan **Aturan 2 dan Aturan 3 PDF**:

- **Aturan 2** — *"Prosedur invasif berisiko HIGH/CRITICAL secara otomatis mewajibkan verifikasi Informed Consent."*
- **Aturan 3** — *"Varians terhadap SLA atau ketidaksesuaian pasang diagnosis–tindakan langsung tercatat ke logbook analitik mutu internal secara otomatis."*

---

## Task 1 — Model consent tindakan invasif

### Temuan audit

`pasien/models.py:983` `GeneralConsentRawatInap` — consent umum rawat inap, OneToOne dengan kunjungan. **Tidak** bisa dipakai untuk tindakan invasif karena:
1. Satu kunjungan bisa punya beberapa tindakan invasif (contoh: intubasi + sentral line).
2. Konsekuensi hukum berbeda: consent rawat inap ≠ consent prosedur.

### Perubahan

**Berkas baru: `pasien/consent_models.py`**

```python
class ConsentTindakanInvasif(models.Model):
    """Aturan 2 PDF: consent prosedur invasif berisiko HIGH/CRITICAL."""

    class Status(models.TextChoices):
        MENUNGGU = 'MENUNGGU', 'Menunggu verifikasi'
        DISETUJUI = 'DISETUJUI', 'Disetujui'
        DITOLAK = 'DITOLAK', 'Ditolak'

    kunjungan = models.ForeignKey('pasien.KunjunganPasien', on_delete=models.CASCADE,
                                  related_name='consent_tindakan')
    icd9 = models.ForeignKey('klinis.MasterIcd9', on_delete=models.PROTECT,
                             related_name='consent')
    icd10 = models.ForeignKey('klinis.MasterIcd10', on_delete=models.PROTECT,
                              related_name='consent', null=True, blank=True)
    nama_tindakan = models.CharField(max_length=200)   # snapshot teks
    risiko = models.CharField(max_length=10)            # snapshot level risiko
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.MENUNGGU, db_index=True)
    penjelasan_diberikan = models.BooleanField(default=False)
    ditolak_alasan = models.TextField(blank=True)
    nama_pemberi = models.CharField(max_length=200, blank=True)   # pasien/keluarga
    hubungan_pemberi = models.CharField(max_length=50, blank=True)  # diri sendiri/suami/istri/...
    saksi = models.CharField(max_length=200, blank=True)
    diverifikasi_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='consent_diverifikasi')
    waktu_persetujuan = models.DateTimeField(null=True, blank=True)
    dibuat = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('kunjungan', 'icd9')]
        ordering = ['-dibuat']
        verbose_name = 'Consent Tindakan Invasif'
        verbose_name_plural = 'Consent Tindakan Invasif'
```

Desain yang disengaja:
- **Snapshot teks** (`nama_tindakan`, `risiko`) — kalau master data berubah, consent yang sudah ditandatangani tetap merekam apa yang dijelaskan saat itu. Ini persyaratan audit medikolegal.
- **`on_delete=PROTECT`** pada FK ke master — master data klinis tidak boleh terhapus selama masih direferensikan consent. Ini pencegahan kehilangan data.
- **`unique_together(kunjungan, icd9)`** — consent idempoten per prosedur.
- `nama_pemberi` + `hubungan_pemberi` — bukan FK ke `Pasien`, karena pemberi consent bisa keluarga yang bukan pasien terdaftar.

### Migrasi

```
python manage.py makemigrations pasien
```

### Admin

`pasien/admin.py` (atau berkas admin consent yang sudah ada — cek dulu apakah `GeneralConsentRawatInap` didaftarkan di `pasien/admin.py`; ikuti pola itu): register dengan `list_display = ('kunjungan', 'nama_tindakan', 'risiko', 'status', 'waktu_persetujuan')`, `list_filter = ('status', 'risiko')`, `search_fields = ('kunjungan__nama_pasien', 'nama_temberi')` (sesuaikan nama field pasien).

### Bukti

- `python manage.py makemigrations --check --dry-run` → `No changes detected`
- `python manage.py migrate` → sukses

---

## Task 2 — Deteksi kebutuhan consent + validasi silang (Aturan 2)

### Perubahan

**`pasien/sla_models.py`** — fungsi deteksi:

```python
def tindakan_perlu_consent(icd9_kode, risiko_icd10):
    """True bila prosedur wajib consent.

    Aturan 2 PDF: prosedur invasif + risiko HIGH/CRITICAL.
    """
    try:
        p = MasterIcd9.objects.get(kode=icd9_kode)
    except MasterIcd9.DoesNotExist:
        return False   # kode di luar katalog → tidak dipaksa, tapi catat untuk review
    return p.invasif and risiko_icd10 in ('HIGH', 'CRITICAL')
```

**`pasien/views.py`** — modifikasi `igd_eksekusi_tindakan` (baris 2137) dan view tindakan lain yang menyimpan prosedur ICD-9. Sebelum menyimpan:

1. Ambil ICD-9 dari POST.
2. Ambil risiko dari ICD-10 kunjungan (`MasterIcd10.objects.get(kode=...).risiko_default`).
3. Jika `tindakan_perlu_consent(...)` dan belum ada `ConsentTindakanInvasif` berstatus `DISETUJUI` untuk pasangan itu:
   - **Jangan tolak.** Buat `ConsentTindakanInvasif` berstatus `MENUNGGU` (jika belum ada), tampilkan `messages.warning` berisi tautan ke form consent, dan **blokir penyelesaian disposisi** — bukan blokir pencatatan tindakan. Pasien kritis tetap ditangani; consent menjadi kewajiban administrasi yang terlacak.

Rasional desain: blokir keras pencatatan tindakan akan mengancam pasien (pasien bisa mati karena tombol tidak bisa diklik). PDF bilang "mewajibkan verifikasi" — bukan "mencegah tindakan darurat". Selisih ini penting dan ditulis eksplisit di spec.

**View baru `igd_consent_tindakan(request, pk, icd9)`:**

```python
@login_required
def igd_consent_tindakan(request, pk, icd9_kode):
    """Form verifikasi consent tindakan invasif (Aturan 2 PDF)."""
```

- GET: form dengan field `penjelasan_diberikan`, `nama_pemberi`, `hubungan_pemberi`, `saksi`, dan tombol Setujui/Tolak.
- POST: validasi semua field wajib non-kosong. Jika `status=DISETUJUI`: `waktu_persetujuan=timezone.now()`, `diverifikasi_oleh=request.user`. Jika `DITOLAK`: `ditolak_alasan` wajib, `ConsentTindakanInvasif.status=DITOLAK`.
- Setelah simpan, redirect ke `pasien:igd_dashboard` dengan `messages.success`.

**`pasien/urls.py`** — `path('igd/<int:pk>/consent/<str:icd9_kode>/', views.igd_consent_tindakan, name='igd_consent_tindakan')`.

**Template form baru** `templates/pasien/consent_tindakan_form.html` — extend base, form Django standar (bukan form class — form sederhana, pakai `forms.Form` di view atau render manual). Field konsisten dengan style form yang sudah ada di `templates/pasien/`. Termasuk teks statis penjelasan risiko prosedur (dari `MasterIcd9.nama` + `MasterIcd10.nama`) — ini dokumen yang dibaca pasien, jadi harus terbaca manusia, bukan sekadar checkbox.

### Bukti

Tes baru:
1. `test_tindakan_invasif_critical_perlu_consent` → `True` (baris STEMI 89.52? Tidak — 89.52 non-invasif. Pakai baris 6 `01.59` Craniotomy + I61.9 CRITICAL → `True`).
2. `test_tindakan_non_invasif_tidak_perlu_consent` → `False` (89.52 EKG + I21.0 CRITICAL).
3. `test_tindakan_invasif_risiko_medium_tidak_perlu` → `False` (51.23 kolesistektomi + K80.20 LOW; dan 47.09 apendektomi + K35.30 HIGH → `True`; `74.1` + O15.00 CRITICAL → `True`).
4. `test_kode_diluar_katalog_tidak_perlu_consent` → `False`.
5. `test_eksekusi_tindakan_membuat_consent_menunggu` — POST tindakan invasif HIGH tanpa consent → `ConsentTindakanInvasif` `MENUNGGU` dibuat, response redirect (200/302, **bukan** 403).
6. `test_eksekusi_tindakan_non_invasif_tanpa_consent` — tidak ada baris consent dibuat.
7. `test_consent_setuju_menyimpan_waktu_dan_user` — POST setujui → `waktu_persetujuan` terisi, `diverifikasi_oleh` = user.
8. `test_consent_tolak_wajib_alasan` — POST tolak tanpa alasan → form error, status tetap `MENUNGGU`.
9. `test_consent_field_wajib_kosong` — POST setujui tanpa `nama_pemberi` → error.
10. `test_consent_perlu_login` — anonim → redirect.

---

## Task 3 — Audit otomatis ketidaksesuaian diagnosis–tindakan (Aturan 3a)

### Temuan audit

`akreditasi/logbook_models.py` `LogbookKejadian` sudah punya `sync_ke_ikp()` yang menulis `InsidenKeselamatan` secara idempoten. **Jalur ini yang dipakai** — jangan bikin mekanisme insiden baru.

### Perubahan

**`akreditasi/logbook_models.py`** — tambahkan method **deteksi otomatis** (bukan menambah model baru):

```python
@classmethod
def audit_ketidaksesuaian_diagnosis_tindakan(cls, kunjungan, icd10_kode, icd9_kode):
    """Aturan 3 PDF: catat ketidaksesuaian pasang diagnosis–tindakan.

    Idempoten per (kunjungan, icd9_kode, jenis='KETIDAKSESUAIAN').
    """
```

Aturan pencocokan: satu kunjungan boleh punya prosedur yang **tidak terdaftar sebagai SLA dari diagnosis itu**. Tapi itu terlalu ketat — banyak tindakan umum (pasang infus, oksigen) tidak punya pasangan SLA khusus.

Pendekatan yang benar dan sederhana: **dua kategori temuan**, bukan satu:

| Kategori | Kondisi | Severity |
|---|---|---|
| `TINDAKAN_DI_LUAR_KATALOG` | ICD-9 tidak ada di `MasterIcd9` | `RENDAH` — review manual |
| `RISIKO_MISMATCH` | `risiko_default` ICD-10 ≠ risiko yang tercatat pada tindakan | `SEDANG` |
| `SLA_BREACH` | evaluasi SLA status `BREACH` (butuh P2) | `TINGGI` |

**Pencatatan:** panggil `LogbookKejadian` → `sync_ke_ikp()` yang sudah ada. Untuk pencatatan terprogram (bukan user), isi `LogbookKejadian` dengan `dibuat_oleh=None` (sistem), dan tambahkan field `sumber='OTOMATIS'` pada `LogbookKejadian` (additive, `default='MANUAL'`) supaya bisa dibedakan di laporan. Verifikasi dulu apakah `LogbookKejadian` sudah punya field semacam itu — probe awal menunjukkan ada `sync_ke_ikp()`; jika sudah ada penanda sumber, pakai itu.

**Kapan dipanggil:** dari `igd_eksekusi_tindakan` setelah menyimpan tindakan. Satu panggilan per tindakan, murah (query katalog sudah di-cache Django ORM).

### Bukti

Tes baru di `akreditasi/tests_logbook*`:
1. `test_audit_tindakan_diluar_katalog` → `LogbookKejadian` dibuat dengan kategori `TINDAKAN_DI_LUAR_KATALOG`.
2. `test_audit_risiko_mismatch` → ICD-10 CRITICAL + ICD-9 dengan risiko terdaftar berbeda → `RISIKO_MISMATCH`.
3. `test_audit_idempoten` — panggil dua kali untuk pasangan sama → hanya 1 `LogbookKejadian`.
4. `test_audit_sync_ke_ikp` — setelah audit, `InsidenKeselamatan` terkait ada, dan panggilan ulang tidak menggandakan insiden (memverifikasi jalur `sync_ke_ikp` yang sudah ada benar-benar idempoten).
5. `test_tindakan_cocok_tidak_membuat_audit` — ICD-10/ICD-9 yang cocok sesuai katalog → tidak ada `LogbookKejadian` baru.

---

## Task 4 — Audit otomatis varians SLA (Aturan 3b)

### Perubahan

**`pasien/sla_models.py`** — method pada hasil evaluasi:

```python
def audit_varians_sla(kunjungan, evaluasi_list, user=None):
    """Aturan 3 PDF: setiap SLA BREACH atau WARNING lewat batas dicatat.

    Hanya dipanggil dari tampilan/penghitung, bukan per detik.
    """
```

- `BREACH` → `LogbookKejadian` kategori `SLA_BREACH`, severity `TINGGI`, keterangan berisi nama rule, target, aktual.
- `WARNING` (delta > 80% target, belum breach) → **tidak** dicatat sebagai insiden. Warning adalah peringatan operasional, bukan insiden. Mencatatnya akan memenuhi logbook dengan noise dan membuat data mutu tidak berguna.

Rasional: spec PDF bilang "varians terhadap SLA" — varian adalah penyimpangan dari target (breach), bukan mendekati target. Batas 80% adalah ambang **peringatan**, bukan ambang **insiden**. Ditulis eksplisit di spec agar tidak ada ambiguitas saat implementasi.

**Dipanggil dari:** tampilan mana pun yang menghitung evaluasi SLA — `igd_dashboard` (P2), dasbor kontrol (`akreditasi/kontrol_data.py` — hanya jika sudah punya jam klinis di sana; kalau belum, jangan paksa), dan laporan mutu. Untuk P3, cukup dari `igd_dashboard` dan dari view baru `igd_sla_audit` eksplisit yang bisa dipanggil dari tombol "Audit SLA sekarang".

### Bukti

Tes baru:
1. `test_audit_breach_membuat_logbook` — STEMI EKG menit ke-15 → `LogbookKejadian` `SLA_BREACH`.
2. `test_audit_warning_tidak_membuat_logbook` — EKG menit ke-8 → tidak ada `LogbookKejadian`.
3. `test_audit_breach_idempoten` — dua kali → 1 baris.
4. `test_audit_breach_mencatat_nilai_aktual` — keterangan berisi `'15'` dan nama rule.
5. `test_audit_tanpa_jam_klinis` — kunjungan tanpa jam → tidak error, tidak ada baris.

---

## Task 5 — Panel & laporan audit

### Perubahan

**`templates/pasien/igd_dashboard.html`** — tambah kolom/panel kecil: bila kunjungan punya `ConsentTindakanInvasif` `MENUNGGU` atau `DITOLAK`, tampil badge "Consent menunggu"/"Consent ditolak" pada baris pasien dengan tautan ke form consent. Ini menutup lingkaran Aturan 2: tindakan tercatat → consent diminta → status terlihat → bisa diverifikasi.

**`klinis/views.py`** — tambah `daftar_audit(request)`: daftar `LogbookKejadan` bersumber `OTOMATIS` (kategori `SLA_BREACH`, `RISIKO_MISMATCH`, `TINDAKAN_DI_LUAR_KATALOG`) dengan filter tanggal, read-only, `@login_required`. Route `path('audit/', views.daftar_audit, name='daftar_audit')`. Template `templates/klinis/daftar_audit.html` reuse gaya tabel `master_klinis.html`.

**Sidebar** — tautan "Audit Klinis Otomatis" di bawah "Master Data Klinis".

### Bukti

Tes baru:
1. `test_daftar_audit_perlu_login`.
2. `test_daftar_audit_tampilkan_breach` — seed 1 breach, `assertContains(response, 'SLA_BREACH')`.
3. `test_daftar_audit_hanya_sumber_otomatis` — buat 1 `LogbookKejadian` manual → tidak muncul di daftar audit.
4. `test_dasbor_badge_consent_menunggu` — `assertContains(response, 'Consent menunggu')`.

---

## Definisi Selesai (DoD)

- [ ] `ConsentTindakanInvasif` ada; migrasi jalan; admin terdaftar.
- [ ] Aturan 2: tindakan invasif HIGH/CRITICAL memicu `ConsentTindakanInvasif MENUNGGU` tanpa memblokir pencatatan tindakan darurat.
- [ ] Form consent: setujui/tolak, field wajib divalidasi, snapshot teks risiko.
- [ ] Aturan 3: `SLA_BREACH` dan ketidaksesuaian diagnosis–tindakan tercatat ke `LogbookKejadian`/`InsidenKeselamatan` lewat jalur `sync_ke_ikp` yang sudah ada, idempoten.
- [ ] WARNING tidak menciptakan insiden (hanya peringatan dasbor).
- [ ] Panel consent + daftar audit tampil, butuh login.
- [ ] Suite hanya 1 failure baseline.
- [ ] Commit: `feat(pasien): consent tindakan invasif + audit otomatis SLA/ketidaksesuaian (Aturan 2 & 3 PDF)`.

---

## Catatan lintas-plan (untuk sesi eksekusi)

1. **P3 tidak wajib menunggu P2**, tapi `audit_varians_sla` butuh `evaluasi_sla_kunjungan` dari P2. Jika P3 dikerjakan lebih dulu, tandai task 4 sebagai blocked sampai P2 selesai.
2. **Satu berkas tes per app**: `klinis/tests.py`, `pasien/tests_sla.py`, `pasien/tests_consent.py`, `akreditasi/tests_logbook_audit.py` — jangan menumpuk semua di berkas tes lama yang sudah besar.
3. **Baca `LogbookKejadan.sync_ke_ikp()` sebelum mengedit apa pun di sekitarnya** — itu mekanisme idempotensi yang sudah teruji; regresi di sana akan merusak laporan mutu yang sudah jalan.
4. **Jangan** memindahkan `GeneralConsentRawatInap` atau menambah field ke model itu. Dua model consent berdampingan adalah keputusan sadar (lihat spec §4).
