# Plan P2 — Master Data Klinis: Jam Klinis, Evaluasi SLA & Alert Real-Time

**Spec induk:** `docs/superpowers/specs/2026-11-04-master-data-klinis-terintegrasi.md`
**Prasyarat:** P1 selesai (katalog `MasterIcd10`/`MasterIcd9`/`MasterSla` tersedia).
**Tanggal:** 2026-11-04. **Repo:** `sim-akreditasi-django` @ `master` (17d3ffc).
**Dependensi:** P1. **Estimasi:** 5 task, ~1 sesi.

---

## Tujuan

Mengimplementasikan **Aturan 1 PDF** — *"Apabila waktu pelayanan > 80% dari target (misal: EKG belum di-input menit ke-8 untuk STEMI), kirim peringatan otomatis ke Nurse Station"*.

## Kunci arsitektur: jam klinis

Temuan audit: semua waktu kunjungan IGD (`waktu_asesmen_dokter`, `waktu_disposisi`) adalah `CharField(max_length=10)` berisi string WIB. Delta menit **tidak bisa dihitung andal** dari string.

Keputusan: **tambah model `JamKlinis` yang menyimpan momen kejadian sebagai `DateTimeField`** — jangan ubah field lama.

```
JamKlinis
  kunjungan  → FK KunjunganPasien (CASCADE, related_name='jam_klinis')
  tipe       → CharField choices: DOOR, EKG, NEEDLE, PCI, CT, NEURO_EXAM,
               KONSUL_BS, ANTIKONVULSAN, NEBULISASI, FOTO_THORAX, ABX_PERTAMA,
               AIRWAY, PRIMARY_SURVEY, SEPSIS_BUNDLE, MGSO4, SC_DELIVERY,
               ANALGESIK, HB, TRANSFUSI, HD, ECHO, INSULIN
  waktu      → DateTimeField (db_index bersama kunjungan)
  keterangan → CharField(max_length=200, blank=True)
  dibuat_oleh → FK User (SET_NULL, null=True)

  unique_together = (kunjungan, tipe)   # satu momen per tipe per kunjungan
```

Rasional:
- `tipe` ditutup (`choices`), bukan teks bebas — mencegah "EKG", "ekg", "E.K.G." menjadi tiga hal berbeda.
- `unique_together` membuat **write idempoten**: re-submit EKG = update momen, bukan baris baru.
- Model terpisah dari `KunjunganPasien` supaya satu kunjungan bisa punya banyak momen (EKG, CT, needle) tanpa menambah 15 kolom ke `KunjunganPasien`.
- `KunjunganPasien` sudah punya `waktu_masuk` (verifikasi nama persisnya sebelum pakai — jika hanya tanggal saja, gunakan `created_at` kunjungan sebagai DOOR).

### Peta `tipe` ke aturan SLA PDF

| Tipe | Dipakai untuk baris PDF |
|---|---|
| DOOR | 1, 5, 20 |
| EKG | 1, 2 |
| NEEDLE / PCI | 1 |
| CT | 5 |
| NEURO_EXAM | 5 |
| KONSUL_BS | 6 |
| ANTIKONVULSAN | 7 |
| NEBULISASI | 8 |
| FOTO_THORAX | 9 |
| ABX_PERTAMA | 9, 11 |
| AIRWAY | 10, 15 |
| PRIMARY_SURVEY | 15 |
| SEPSIS_BUNDLE | 17 |
| MGSO4 | 20 |
| SC_DELIVERY | 20 |
| ANALGESIK | 14 |
| HB / TRANSFUSI | 12 |
| HD | 19 |
| ECHO | 3 |
| INSULIN | 18 |

Baris 4 (kardiogenik shock, response 0 mnt) tidak perlu jam — target 0 mnt berarti tidak ada ambang yang bisa dilanggar; ditangani oleh triase MERAH + eskalasi yang sudah ada.

---

## Task 1 — Model `JamKlinis` + helper perhitungan SLA

### Perubahan

**Berkas baru: `pasien/sla_models.py`** (bukan `klinis/` — ini model transaksional pasien, bukan master data. `klinis` hanya katalog.)

```python
class JamKlinis(models.Model):
    class Tipe(models.TextChoices):
        DOOR = 'DOOR', 'Door Time (masuk IGD)'
        EKG = 'EKG', 'EKG 12-lead diperekam'
        NEEDLE = 'NEEDLE', 'Door-to-Needle (trombolitik)'
        PCI = 'PCI', 'PCI dimulai'
        CT = 'CT', 'CT Scan dimulai'
        NEURO_EXAM = 'NEURO_EXAM', 'Pemeriksaan neurologis'
        KONSUL_BS = 'KONSUL_BS', 'Konsul Sp.BS'
        ANTIKONVULSAN = 'ANTIKONVULSAN', 'Antikonvulsan IV diberikan'
        NEBULISASI = 'NEBULISASI', 'Nebulisasi pertama'
        FOTO_THORAX = 'FOTO_THORAX', 'Foto thorax'
        ABX_PERTAMA = 'ABX_PERTAMA', 'Antibiotik pertama'
        AIRWAY = 'AIRWAY', 'Airway diamankan'
        PRIMARY_SURVEY = 'PRIMARY_SURVEY', 'Primary survey ABCDE'
        SEPSIS_BUNDLE = 'SEPSIS_BUNDLE', 'Sepsis bundle 1 jam'
        MGSO4 = 'MGSO4', 'MgSO4 diberikan'
        SC_DELIVERY = 'SC_DELIVERY', 'Decision-to-delivery SC'
        ANALGESIK = 'ANALGESIK', 'Analgetik diberikan'
        HB = 'HB', 'Hb diperiksa'
        TRANSFUSI = 'TRANSFUSI', 'Transfusi darah dimulai'
        HD = 'HD', 'Hemodialisis dimulai'
        ECHO = 'ECHO', 'Ekokardiografi'
        INSULIN = 'INSULIN', 'Insulin diberikan'

    kunjungan = models.ForeignKey('pasien.KunjunganPasien', on_delete=models.CASCADE,
                                  related_name='jam_klinis')
    tipe = models.CharField(max_length=16, choices=Tipe.choices, db_index=True)
    waktu = models.DateTimeField(db_index=True)
    keterangan = models.CharField(max_length=200, blank=True)
    dibuat_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)

    class Meta:
        unique_together = [('kunjungan', 'tipe')]
        ordering = ['waktu']
        verbose_name = 'Jam Klinis'
        verbose_name_plural = 'Jam Klinis'
```

**Method di `KunjunganPasien`** (`pasien/models.py`, tambah — jangan ubah yang ada):

```python
def catat_jam(self, tipe, waktu=None, keterangan='', user=None):
    """Catat momen klinis. Idempoten: tipe sama = update momen."""
    from .sla_models import JamKlinis   # hindari circular import
    obj, _ = JamKlinis.objects.update_or_create(
        kunjungan=self, tipe=tipe,
        defaults={'waktu': waktu or timezone.now(), 'keterangan': keterangan,
                  'dibuat_oleh': user})
    return obj

def delta_menit(self, tipe_mulai, tipe_akhir):
    """Selisih menit antara dua momen. None jika salah satu belum ada."""
    from .sla_models import JamKlinis
    a = JamKlinis.objects.filter(kunjungan=self, tipe=tipe_mulai).values_list('waktu', flat=True).first()
    b = JamKlinis.objects.filter(kunjungan=self, tipe=tipe_akhir).values_list('waktu', flat=True).first()
    if not a or not b:
        return None
    return (b - a).total_seconds() / 60
```

**Helper perhitungan evaluasi SLA** di `pasien/sla_models.py` (modul-level, bukan model method — dipakai view dan scheduler):

```python
def evaluasi_sla_kunjungan(kunjungan):
    """Kembalikan list EvaluasiSla untuk satu kunjungan.

    Satu entri per aturan MasterSla yang cocok dengan ICD-10 kunjungan.
    """
```

Status tiap aturan:

| Status | Kondisi |
|---|---|
| `OK` | delta ≤ target_menit |
| `WARNING` | delta > ambang_menit dan ≤ target_menit (ambang = 80% target) |
| `BREACH` | delta > target_menit |
| `PENDING` | momen akhir belum tercatat (delta None) |

`PENDING` dengan `waktu_tunggu_sejauh_ini > ambang_menit` = **Aturan 1 PDF terpenuhi**: kunjungan yang belum selesai tapi sudah lewat 80% target. Ini kasus "EKG belum di-input menit ke-8".

### Migrasi

```
python manage.py makemigrations pasien
```

### Bukti

- `python manage.py makemigrations --check --dry-run` → `No changes detected`
- `python manage.py shell -c "from pasien.models import KunjunganPasien; k=KunjunganPasien(); print(hasattr(k,'catat_jam'), hasattr(k,'delta_menit'))"` → `True True`

---

## Task 2 — Input jam klinis di UI IGD

### Temuan

`pasien/views.py:2137` `igd_eksekusi_tindakan` sudah jadi pola persis: POST → baca field → `CPPT.objects.create(...)` → redirect. Ikuti pola itu.

### Perubahan

**`pasien/views.py`** — view baru:

```python
@login_required
@require_POST
def igd_catat_jam(request, pk):
    """Catat momen klinis (EKG, CT, antikonvulsan, dst) untuk perhitungan SLA."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    tipe = request.POST.get('tipe', '').strip().upper()
    if tipe not in dict(JamKlinis.Tipe.choices):
        return HttpResponseBadRequest('Tipe jam klinis tidak dikenal.')
    waktu_str = request.POST.get('waktu', '').strip()  # "HH:MM" WIB hari ini, format form IGD
    waktu = _parse_wib_ke_datetime(waktu_str) if waktu_str else timezone.now()
    if waktu is None:
        return HttpResponseBadRequest('Format waktu harus HH:MM.')
    k.catat_jam(tipe, waktu=waktu, keterangan=request.POST.get('keterangan','').strip(), user=request.user)
    messages.success(request, f'Jam klinis {tipe} tercatat.')
    return redirect('pasien:igd_dashboard')
```

`_parse_wib_ke_datetime(s)` — helper baru di `pasien/views.py`. **Wajib** memperhatikan `TIME_ZONE` (verifikasi di `config/settings.py`; probe sebelumnya menemukan `USE_TZ`/`TIME_ZONE` — baca nilainya sebelum menulis fungsi). Pola: parse `HH:MM` → jamangan hari ini sesuai `TIME_ZONE`, kembalikan aware datetime. Kembalikan `None` untuk input tidak valid (jangan raise ke user).

**`pasien/urls.py`** — path baru: `path('igd/<int:pk>/catat-jam/', views.igd_catat_jam, name='igd_catat_jam')`.

**`templates/pasien/igd_dashboard.html`** — per baris pasien, tambah tombol jam klinis. **Prinsip:** jangan render 21 tombol per pasien. Render hanya tipe yang relevan dengan ICD-10 kunjungan:
- Ambil `kunjungan.diagnosa_utama` (verifikasi nama field — probe menunjukkan field ICD-10 pada asesmen; jika nama berbeda, pakai nama sebenarnya).
- Query `MasterSla.objects.filter(diagnosis__kode=icd10).select_related('prosedur')`.
- Untuk tiap SLA, tentukan `tipe_mulai` dan `tipe_akhir` (lihat peta di atas; ini perlu mapping eksplisit di `sla_models.py`):

```python
# sla_models.py
TIPE_SLA = {
    'Door-to-ECG':      ('DOOR', 'EKG'),
    'Door-to-Needle':   ('DOOR', 'NEEDLE'),
    'Door-to-Needle/PCI': ('DOOR', 'NEEDLE'),
    'Door-to-CT':       ('DOOR', 'CT'),
    'interpretasi':     ('CT', None),        # momen akhir bukan jam, ditangani terpisah
    'Konsul Sp.BS':     ('DOOR', 'KONSUL_BS'),
    ...
}
```

- Tampilkan tombol hanya untuk tipe yang **belum tercatat** (`JamKlinis.objects.filter(kunjungan=k, tipe=t)` kosong), dan tampilkan badge status untuk yang sudah tercatat.
- Gunakan form POST inline (`<form method="post" action="{% url 'pasien:igd_catat_jam' k.pk %}">{% csrf_token %}`) — sama seperti tombol tindakan `igd_eksekusi_tindakan` yang sudah ada. Tidak perlu modal/JS baru.

**Konsistensi UI:** tiap tombol = satu baris kecil di kolom aksi baris pasien, dengan `title` berisi nama rule + target. Tidak menambah kolom baru ke tabel (dashboard sudah padat).

### Bukti

```
python manage.py test pasien.tests_igd --keepdb -v 2   # sesuaikan nama berkas tes IGD
```
Tes baru:
1. `test_catat_jam_membuat_baris` — POST tipe valid → `JamKlinis.objects.count()` bertambah.
2. `test_catat_jam_idempoten` — POST dua kali dengan tipe sama → count tetap 1, `waktu` = yang terbaru.
3. `test_catat_jam_tipe_tidak_dikenal` → `HttpResponseBadRequest` (status 400), tidak ada baris dibuat.
4. `test_catat_jam_waktu_tidak_valid` → 400.
5. `test_catat_jam_perlu_post` — GET → 405.
6. `test_catat_jam_perlu_login` — client anonim → redirect login.
7. `test_delta_menit_benar` — catat DOOR 10:00, EKG 10:08 → `delta_menit('DOOR','EKG') == 8.0`.
8. `test_delta_menit_none_belum_lengkap` — hanya DOOR → `None`.
9. `test_parse_wib_valid_dan_invalid` — `_parse_wib_ke_datetime('10:30')` aware, `_parse_wib_ke_datetime('abc')` → None, `'25:99'` → None.

---

## Task 3 — Panel SLA di dasbor IGD (Aturan 1 PDF)

### Perubahan

**`pasien/views.py` `igd_dashboard`** (baris 1003) — tambahkan ke `ctx`:

```python
'sla_evaluasi': {k.pk: evaluasi_sla_kunjungan(k) for k in qs},
'sla_warning_count': sum(1 for evs in ... if any(e.status in ('WARNING','BREACH') for e in evs)),
```

**Query budget:** `evaluasi_sla_kunjungan` melakukan query per kunjungan. Untuk `qs` 20 pasien itu 21 query tambahan — **tidak dapat diterima** untuk dasbor. Solusi: di dalam `igd_dashboard`, hitung satu kali dengan query ter-batch:

```python
def _batch_evaluasi_sla(qs):
    """Batch: 1 query MasterSla + 1 query JamKlinis untuk seluruh qs."""
```

Ambil semua `MasterSla` sekali, semua `JamKlinis` untuk `kunjungan__in=qs` sekali, lalu hitung di Python. Tidak N+1.

**Verifikasi kuery:** tambahkan `assertNumQueries` (atau `CaptureQueriesContext`) pada tes dasbor baru untuk mengunci jumlah query. Probe: repo belum punya `assertNumQueries` untuk dasbor IGD — tes baru ini jadi acuan pertama. Angka anggaran: hitung dulu aktualnya, lalu set `<=` angka aktual (bukan angka tebakan), dengan komentar kenapa.

**`templates/pasien/igd_dashboard.html`** — panel SLA:
- Baris peringatan di atas tabel jika `sla_warning_count > 0`: "⚠ N kunjungan mendekati/melanggar SLA — periksa jam klinis."
- Per baris pasien, badge per aturan: `OK` (hijau), `WARNING` (kuning), `BREACH` (merah), `PENDING` (abu, dengan menit berjalan).
- Warna: **reuse class badge triase yang sudah ada** di template itu (MERAH/KUNING/HIJAU). Jangan tambah CSS baru kecuali `PENDING` benar-benar tidak punya padanan — kalau perlu, satu class `badge-sla-pending` di stylesheet yang sudah dipakai dashboard.
- Teks badge: nama rule + status, misal `EKG WARNING 8/10 mnt`.

### Bukti

Tes baru di berkas tes IGD:
1. `test_dasbor_sla_ok` — kunjungan STEMI, DOOR 10:00, EKG 10:05 → status `OK`.
2. `test_dasbor_sla_warning` — EKG 10:08 (80% dari 10) → status `WARNING`, badge muncul di HTML.
3. `test_dasbor_sla_breach` — EKG 10:15 → `BREACH`.
4. `test_dasbor_sla_pending_lewat_ambang` — hanya DOOR 40 menit lalu, target 10 → `PENDING` dengan `menit_berjalan >= 8` → **muncul di panel peringatan** (inti Aturan 1).
5. `test_dasbor_sla_tanpa_icd10` — kunjungan tanpa diagnosis → tidak error, tidak ada aturan.
6. `test_dasbor_tidak_n_plus_1` — `assertNumQueries` di `igd_dashboard` dengan 20 kunjungan ter-seed; anggaran = aktual + 0, dikunci.
7. `test_panel_peringatan_muncul_saat_ada_warning` — `assertContains(response, 'mendekati/melanggar SLA')`.

---

## Task 4 — Ekspor & tautan dari katalog ke kunjungan

### Perubahan

**`klinis/views.py`** — tambah:

```python
@login_required
def master_klinis(request):
    ...
    ctx['rows'] = rows
    ctx['total_sla'] = MasterSla.objects.count()
```

**`templates/klinis/master_klinis.html`** — tiap baris dapat tautan `?icd10=KODE` ke dasbor IGD? **Tidak** — dasbor IGD tidak mendukung filter ICD-10 (probe: hanya `triage` filter). Jangan tambah filter baru hanya untuk tautan ini. Biarkan katalog sebagai tampilan referensi saja.

Sebagai gantinya, tambahkan di `klinis/views.py` endpoint kecil yang **memetakan ICD-10 → tipe jam klinis** untuk dipakai template IGD:

```python
def tipe_jam_untuk_icd10(kode_icd10):
    """Tipe jam klinis relevan untuk satu kode ICD-10 (untuk render tombol IGD)."""
```

Taruh di `pasien/sla_models.py` (bukan `klinis/views.py`) karena konsumennya view pasien, dan butuh `MasterSla` + `TIPE_SLA` yang bersebelahan.

### Bukti

Tes di `pasien/tests_*`:
1. `test_tipe_jam_untuk_stemi` → `{'DOOR','EKG','NEEDLE','PCI'}`.
2. `test_tipe_jam_untuk_icd10_tanpa_sla` → set kosong.

---

## Task 5 — Verifikasi menyeluruh + dokumentasi

### Bukti

```
python manage.py test klinis pasien akreditasi --keepdb -v 1
```
→ 1 failure baseline saja (`KontrolQueryBudgetTest`), semua tes baru hijau.

**Dokumentasi:**
- Update spec induk §3.2 (hapus "Tidak ada SLA clock" dan "Tidak ada alert otomatis" — keduanya selesai).
- Catat di spec bahwa alert bersifat **on-demand** (muncul saat dasbor dibuka), bukan push — keterbatasan yang diterima secara eksplisit.

### DoD

- [ ] `JamKlinis` ada, `unique_together(kunjungan, tipe)`, migrasi jalan.
- [ ] `catat_jam`/`delta_menit` idempoten, teruji.
- [ ] Input jam klinis di UI IGD hanya untuk tipe relevan dengan ICD-10 kunjungan.
- [ ] Panel SLA tampil di dasbor dengan 4 status; `PENDING` lewat 80% target memicu peringatan (Aturan 1).
- [ ] Tidak ada N+1 — query dasbor terkunci dengan `assertNumQueries`.
- [ ] Semua endpoint baru: `@login_required` + `@require_POST` (untuk yang menulis) + validasi tipe/waktu.
- [ ] Suite hanya 1 failure baseline.
- [ ] Commit: `feat(pasien): jam klinis + evaluasi SLA + alert 80% di dasbor IGD (Aturan 1 PDF)`.
