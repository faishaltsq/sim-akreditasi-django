# Plan P1 — Master Data Klinis: Katalog Terstruktur & Seed 20 Baris PDF

**Spec induk:** `docs/superpowers/specs/2026-11-04-master-data-klinis-terintegrasi.md`
**Tanggal:** 2026-11-04. **Repo:** `sim-akreditasi-django` @ `master` (17d3ffc).
**Estimasi:** 4–5 task, ~1 sesi. **Dependensi:** tidak ada.

---

## Tujuan

Membuat app `klinis` berisi master data klinis terstruktur (ICD-10, ICD-9-CM, SLA, level risiko) yang tersambung ke pilihan yang sudah ada di IGD, dan seed 20 baris dari PDF "Master Data Klinis Lengkap".

## Prinsip

- **Reuse-first.** `ICD10_CODES` di `pasien/views.py:29` tetap dipakai sebagai sumber tampilan; katalog baru menambah kode yang hilang dan menyediakan metadata (risiko, SLA, triase) yang tidak bisa ditampung tuple 2-elemen.
- **Tidak ada breaking change.** Tidak ada field/model lama yang dihapus atau diubah tipenya.
- **Idempotent.** Seed bisa dijalankan ulang (`get_or_create` / `update_or_create`) tanpa duplikat.

---

## Task 1 — Buat app `klinis` beserta model katalog

### Perubahan

**Berkas baru: `klinis/__init__.py`, `klinis/apps.py`, `klinis/models.py`, `klinis/admin.py`, `klinis/migrations/__init__.py`**

Model di `klinis/models.py`:

```python
class MasterIcd10(models.Model):
    """Katalog diagnosis ICD-10 beserta metadata klinis."""
    kode = models.CharField(max_length=8, unique=True, db_index=True)
    nama = models.CharField(max_length=200)
    spesialisasi = models.CharField(max_length=50, db_index=True)
    triase_default = models.CharField(
        max_length=8,
        choices=KunjunganPasien.TRIASE_KATEGORI_CHOICES,   # import dari pasien.models
        blank=True,
    )
    risiko_default = models.CharField(
        max_length=10,
        choices=[('LOW','LOW'),('MEDIUM','MEDIUM'),('HIGH','HIGH'),('CRITICAL','CRITICAL')],
        blank=True,
    )
    catatan = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kode']
        verbose_name = 'Master ICD-10'
        verbose_name_plural = 'Master ICD-10'

    def __str__(self):
        return f'{self.kode} — {self.nama}'
```

```python
class MasterIcd9(models.Model):
    """Katalog prosedur ICD-9-CM."""
    kode = models.CharField(max_length=8, unique=True, db_index=True)
    nama = models.CharField(max_length=200)
    spesialisasi = models.CharField(max_length=50, db_index=True)
    invasif = models.BooleanField(default=False,
        help_text='Prosedur invasif — wajib verifikasi informed consent')
    requires_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kode']
        verbose_name = 'Master ICD-9-CM'
        verbose_name_plural = 'Master ICD-9-CM'
```

```python
class MasterSla(models.Model):
    """Aturan target waktu tanggap per kombinasi diagnosis–prosedur.

    Satu baris per aturan SLA (bukan per pasien). Contoh: satu baris
    "Door-to-ECG ≤ 10 menit", satu baris lagi "Door-to-Needle ≤ 90 menit".
    """
    diagnosis = models.ForeignKey(MasterIcd10, on_delete=models.CASCADE,
                                  related_name='sla_rules')
    prosedur = models.ForeignKey(MasterIcd9, on_delete=models.CASCADE,
                                 related_name='sla_rules', null=True, blank=True)
    nama_rule = models.CharField(max_length=120,
        help_text='Contoh: "Door-to-ECG"')
    target_menit = models.PositiveIntegerField()
    ambang_peringatan_pct = models.PositiveIntegerField(default=80,
        help_text='Persen target yang memicu peringatan (default 80% = aturan 1 PDF)')
    catatan = models.TextField(blank=True)

    class Meta:
        ordering = ['diagnosis__kode', 'target_menit']
        unique_together = [('diagnosis', 'prosedur', 'nama_rule')]
        verbose_name = 'Master SLA'
        verbose_name_plural = 'Master SLA'

    def __str__(self):
        return f'{self.nama_rule} ≤ {self.target_menit} mnt'

    @property
    def ambang_menit(self):
        """Menit ke-berapa peringatan SLA breach mulai muncul."""
        return round(self.target_menit * self.ambang_peringatan_pct / 100)
```

**Import `TRIASE_KATEGORI_CHOICES`** dari `pasien.models.KunjunganPasien` di `klinis/models.py`. Cek dulu nama konstanta persisnya (probe awal menunjukkan `TRIASE_KATEGORI_CHOICES` di `pasien/models.py:443`); jika nama di file berbeda, pakai nama yang ada.

### Registrasi

- `config/settings.py`: tambah `'klinis'` ke `INSTALLED_APPS` (setelah `'pasien'`, urutan tidak sensitif karena hanya import konstanta).
- `klinis/apps.py`:

```python
from django.apps import AppConfig

class KlinisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'klinis'
    verbose_name = 'Master Data Klinis'
```

- `klinis/admin.py`: register ketiga model dengan `list_display`, `search_fields` (`kode`, `nama`), `list_filter` (`spesialisasi`, `risiko_default` / `invasif`).

### Migrasi

```
python manage.py makemigrations klinis
```

Muat `TRIASE_KATEGORI_CHOICES` sebagai **literal list di migrasi**, bukan referensi ke model lain (praktik Django: choices harus self-contained di migrasi). Salin isi konstantanya dari `pasien/models.py:443` ke dalam `klinis/migrations/0001_initial.py`.

### Bukti

- `python manage.py makemigrations --check --dry-run` → `No changes detected`
- `python manage.py migrate` → sukses
- `python manage.py shell -c "from klinis.models import MasterIcd10; print(MasterIcd10.objects.count())"` → `0`

---

## Task 2 — Command seed katalog dari 20 baris PDF

### Perubahan

**Berkas baru: `klinis/management/__init__.py`, `klinis/management/commands/__init__.py`, `klinis/management/commands/seed_master_klinis.py`**

Isi `seed_master_klinis.py`: data 20 baris dari tabel §2 spec induk, di-hardcode sebagai tuple di atas `handle()`:

```python
BARIS = [
    # (spesialisasi, icd10, diagnosis, icd9, prosedur, triase, risiko,
    #  [(nama_rule, target_menit), ...], invasif)
    ('Kardiovaskular', 'I21.0', 'Acute transmural MI of anterior wall (STEMI Anterior)',
     '89.52', 'Electrocardiogram (ECG)', 'MERAH', 'CRITICAL',
     [('Door-to-ECG', 10), ('Door-to-Needle/PCI', 90)], False),
    ...  # 19 baris lagi, persis dari tabel §2
]
```

`handle()`:
1. Untuk tiap baris: `MasterIcd10.objects.update_or_create(kode=..., defaults={nama, spesialisasi, triase_default, risiko_default})`
2. `MasterIcd9.objects.update_or_create(kode=..., defaults={nama, spesialisasi, invasif, requires_consent})` — `requires_consent=True` untuk prosedur invasif dengan risiko HIGH/CRITICAL (baris 1, 5, 6, 7, 10, 14, 15, 17, 20 — ditentukan secara eksplisit per baris, bukan inferensi otomatis, supaya tidak ada salah-tanda).
3. Untuk tiap SLA: `MasterSla.objects.update_or_create(diagnosis=..., prosedur=..., nama_rule=..., defaults={target_menit})`
4. `self.stdout.write(self.style.SUCCESS(f'Seeded: {n10} ICD-10, {n9} ICD-9, {ns} SLA'))`

Tambahkan `--reset` flag yang menghapus semua baris dulu (`MasterSla`, lalu `MasterIcd9`, lalu `MasterIcd10`) — berguna untuk uji ulang, aman karena data ini master data murni (tidak ada FK dari model transaksional).

### Bukti

```
python manage.py seed_master_klinis
python manage.py seed_master_klinis   # jalan kedua: tidak ada duplikat
python manage.py shell -c "
from klinis.models import MasterIcd10, MasterIcd9, MasterSla
print(MasterIcd10.objects.count(), MasterIcd9.objects.count(), MasterSla.objects.count())"
```
→ `20 20 <jumlah SLA>` dan angka sama setelah run kedua.

---

## Task 3 — Sinkronkan kode ICD-10 yang hilang ke picker IGD

### Temuan

`ICD10_CODES` (`pasien/views.py:29`) berisi 83 kode. Dari 20 kode di PDF, yang belum ada: `I21.0, I20.0, J45.901, J96.00, K35.30, K80.20, S72.301A, T07, A41.9, E11.65, N18.6, O15.00` (12 kode). Yang sudah ada: `I50.9, R57.0, I63.9, I61.9, G40.9, J18.9, K92.2, A91` (8 kode).

### Perubahan

**`pasien/views.py`** — tambah 12 entri baru ke `ICD10_CODES`, diurutkan sesuai pola file (alfabetis menurut kode, sudah dipegang oleh blok itu). Posisikan tiap kode pada tempat alfabetisnya yang benar, jangan dump di akhir:

| Kode | Label |
|---|---|
| I20.0 | Angina Pektoris Tidak Stabil |
| I21.0 | Infark Miokard Akut Transmural (STEMI) |
| J45.901 | Asma dengan Eksaserbasi Akut |
| J96.00 | Kegagalan Pernapasan Akut |
| K35.30 | Apendisitis Akut dengan Peritonitis Terlokalisasi |
| K80.20 | Batu Empedu tanpa Kolesistitis |
| A41.9 | Sepsis, Organisme Tidak Spesifik |
| E11.65 | DM Tipe 2 dengan Hiperglikemia |
| N18.6 | Gagal Ginjal Terminal Stadium 5 (ESRD) |
| O15.00 | Eklampsia dalam Kehamilan, Trimester Tidak Spesifik |
| S72.301A | Fraktur Tidak Tertentu Batang Femur Kanan |
| T07 | Cedera Multipel Tidak Spesifik |

**Catatan** — pastikan tidak ada duplikat. Sebelum menambah, grep tiap kode di blok 29–114 (`grep -n "I20.0" pasien/views.py`); probe sudah memastikan 12 kode ini absen, tapi verifikasi ulang karena file aktif di-edit.

### Bukti

- `python manage.py shell -c "from pasien.views import ICD10_CODES; print(len(ICD10_CODES), len(dict(ICD10_CODES)))"` → `95 95` (83 + 12, tanpa duplikat)
- `python -c "from collections import Counter; from pasien.views import ICD10_CODES; c=Counter(x[0] for x in ICD10_CODES); print([k for k,v in c.items() if v>1])"` → `[]`

---

## Task 4 — Tes katalog (unit + seed idempotensi)

### Perubahan

**Berkas baru: `klinis/tests.py`**

Kelas `MasterKlinisCatalogTest(TestCase)`:

1. `test_seed_menghasilkan_20_icd10_dan_20_icd9` — panggil `call_command('seed_master_klinis')`, assert count 20/20.
2. `test_seed_idempoten` — `call_command` dua kali, assert count tidak berubah.
3. `test_seed_reset_bersihkan_lalu_recreate` — seed, buat `MasterSla` sampel, `call_command('seed_master_klinis', reset=True)`, assert count tetap 20/20 dan SLA sampel sudah ter-replace (bukan tercampur).
4. `test_semua_sla_target_positif` — iterasi `MasterSla.objects.all()`, assert `target_menit > 0`.
5. `test_ambang_menit_80_persen` — untuk baris STEMI Door-to-ECG: `sla.ambang_menit == 8`.
6. `test_icd10_kode_unik` — `MasterIcd10.objects.values('kode').annotate(n=Count('id')).filter(n__gt=1)` kosong.
7. `test_icd10_default_triase_valid` — semua `triase_default` ada dalam `KunjunganPasien.TRIASE_KATEGORI_CHOICES`.

**Perubahan di `pasien/tests.py`** (atau berkas tes yang relevan — cari kelas tes yang menyentuh `ICD10_CODES` dulu):

8. `test_icd10_codes_tidak_duplikat` — assert len(list) == len(dict).
9. `test_icd10_memuat_12_kode_baru` — assert set 12 kode baru ⊆ set kode.

### Bukti

```
python manage.py test klinis pasien.tests --keepdb -v 2
```
→ semua baru hijau; tidak ada tes lama yang jatuh.

---

## Task 5 — Dasbor master data klinis (read-only, admin-adjacent)

### Tujuan

Tampilan sederhana untuk melihat katalog dan SLA-nya. Ini bukan CRUD — admin Django sudah CRUD. Tujuan plan ini adalah **tampilan sirkular katalog** (satu baris = pasangan diagnosis–prosedur + triase + risiko + SLA) seperti tabel PDF, karena itu yang dipakai klinisi untuk verifikasi.

### Perubahan

**Berkas baru: `klinis/views.py`, `klinis/urls.py`, `templates/klinis/master_klinis.html`**

- `klinis/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import MasterIcd10

@login_required
def master_klinis(request):
    rows = (
        MasterIcd10.objects
        .prefetch_related('sla_rules', 'sla_rules__prosedur')
        .select_related()
        .order_by('spesialisasi', 'kode')
    )
    return render(request, 'klinis/master_klinis.html', {'rows': rows})
```

- `klinis/urls.py` → `app_name = 'klinis'`, satu path `''` → `master_klinis`, name `master_klinis`.
- `config/urls.py` → `path('klinis/', include('klinis.urls'))`.
- **Template** `templates/klinis/master_klinis.html`: extend `templates/base.html`, tabel dengan kolom: Spesialisasi | ICD-10 | Diagnosis | ICD-9 | Prosedur | Triase (badge warna) | Risiko (badge warna) | Aturan SLA (nama + target menit). Ikuti pola badge warna yang sudah ada di `templates/pasien/igd_dashboard.html` (probe: dashboard sudah punya badge triase MERAH/KUNING/HIJAU/HITAM — reuse class CSS-nya, jangan bikin baru).
- **Sidebar** `templates/includes/sidebar.html`: tambah item "Master Data Klinis" di grup yang sesuai (lihat grup mana yang dipakai menu terkait akreditasi/klinis; jangan taruh di grup pasien jika konteksnya manajemen).

### Bukti

```
python manage.py test klinis --keepdb -v 2
```

Tambah tes `test_master_klinis_perlu_login` (GET anonim → redirect ke login) dan `test_master_klinis_tampilkan_20_baris` (login, seed, assert jumlah baris tabel = 20 via `assertContains(response, 'I21.0')` dan `assertQueryset`/count pada konteks).

---

## Definisi Selesai (DoD)

- [ ] App `klinis` terdaftar, migrasi jalan, `makemigrations --check` bersih.
- [ ] Seed menghasilkan 20 ICD-10, 20 ICD-9, dan semua SLA; idempoten.
- [ ] 12 kode ICD-10 PDF hadir di `ICD10_CODES`; tidak ada duplikat.
- [ ] Dasbor read-only tampil, butuh login, 20 baris.
- [ ] Tes baru hijau; suite `pasien akreditasi` hanya 1 failure baseline (`KontrolQueryBudgetTest`).
- [ ] Tidak ada perubahan pada field/model lama; `git diff --stat` hanya menambah berkas + 2 berkas ubah (`settings.py`, `pasien/views.py`, `config/urls.py`, `sidebar.html`).
- [ ] Commit: `feat(klinis): master data klinis — katalog ICD-10/ICD-9/SLA + seed 20 baris PDF`.
