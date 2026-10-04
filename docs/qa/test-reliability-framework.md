# Framework Reliabilitas Pengujian & Manajemen Karantina
## Sistem Informasi Manajemen Akreditasi & Layanan Pasien (ARIMA)

**Dokumen Standar:** Test Reliability & Flakiness Management Standard  
**Kepatuhan:** Level 1 - 4 Test Resilience Architecture  
**Tanggal:** 04 Oktober 2026  

---

### 1. Klasifikasi Akar Masalah Flakiness (Flake Taxonomy)

Setiap kegagalan intermiten diklasifikasikan ke dalam 7 kategori definitif:

| Kategori Flake | Gejala Utama | Akar Penyebab | Pola Perbaikan Wajib |
|---|---|---|---|
| **1. Timing & Async** | Timeout acak pada CI, lolos saat diulang | Race condition animasi CSS, DOM render terlambat | Ganti `sleep()` dengan penungguan kondisi eksplisit (`waitForSelector`, `expect(locator).toBeVisible()`) |
| **2. Data Dependency** | Gagal saat paralel (`--parallel`), lolos saat sendirian | Bentrokan state DB, nomor rekam medis atau NIK duplikat | Isolasi per-tes dengan database rollback otomatis atau fixture unik (`uuid4()`) |
| **3. Environment & Latency**| Gagal pada runner CI tertentu, lolos di lokal | Beban CPU runner tinggi, koneksi DB staging lambat | Tambahkan health check backend sebelum pengujian, mock endpoint lambat |
| **4. Order Dependency** | Tes B hanya lolos jika Tes A dijalankan sebelumnya | Tes B bergantung pada data sampingan yang dibuat Tes A | Jadikan setiap fungsi tes sepenuhnya mandiri dalam blok `setUp()` |
| **5. Time Sensitivity** | Gagal di pergantian bulan, akhir tahun, atau tengah malam | Perhitungan tanggal relatif / timezone tidak statis | Gunakan `freezegun` untuk mematikan pergerakan jam server saat pengujian |
| **6. Visual Rendering** | Perbedaan subpixel pada screenshot | Render font / antialiasing berbeda antara Linux CI dan Windows | Berikan toleransi threshold diff visual (>= 5%) atau hindari pixel diff untuk logika fungsional |
| **7. External Service** | Gagal saat koneksi internet / API eksternal drop | Panggilan nyata ke Supabase Auth, DeepSeek API, atau SATUSEHAT | Lakukan mocking wajib pada lapisan network menggunakan `unittest.mock` |

---

### 2. Penilaian Stabilitas Selector (Selector Stability Scoring)

Setiap elemen interaktif antarmuka yang diuji dengan browser/Playwright dinilai berdasarkan skala 0 - 5:

| Skor | Tipe Locator | Contoh Sintaks | Ketahanan Perubahan |
|---|---|---|---|
| **5** | `data-testid` Spesifik | `page.getByTestId('btn-simpan-consent')` | Tahan terhadap perubahan CSS, teks, dan struktur DOM |
| **4** | Aksesibilitas Semantik | `page.getByRole('button', { name: 'Pesan Kamar' })` | Tahan terhadap perubahan style CSS dan struktur hierarki |
| **3** | Label Terkait | `page.getByLabel('Nomor Rekam Medis')` | Tahan perubahan CSS; rentan jika teks label diganti |
| **2** | Teks Bebas | `page.getByText('Simpan Data Pasien')` | Rentan terhadap pembaruan copy/teks antarmuka |
| **1** | Selektor CSS Kelas | `page.locator('.btn-primary.submit-btn')` | Sangat rentan terhadap refaktor framework CSS/Bootstrap |
| **0** | Jalur XPath Absolut | `page.locator('//div[2]/form/div[3]/button[1]')` | Rusak seketika pada setiap perubahan kecil struktur HTML |

**Aturan Suite ARIMA:**  
Rata-rata skor stabilitas selektor seluruh pengujian E2E wajib **>= 3.8**. Penggunaan selektor Skor 0 dan 1 dilarang keras masuk ke branch `master`.

---

### 3. Pemulihan Mandiri Sadar-Lingkungan (Environment-Aware Healing)

Ketika sebuah tindakan di browser mengalami kegagalan, sistem pengujian tidak boleh langsung menyimpulkan adanya bug antarmuka. Alur verifikasi berlapis wajib dijalankan:

```
[Tindakan UI Gagal / Timeout]
          │
          ▼
   [Cek Endpoint Kesehatan: GET /accounts/login/ atau /profil/]
          │
    ┌─────┴────────────────────────────────┐
    ▼                                      ▼
[Status 5xx atau Timeout]              [Status 200 OK]
    │                                      │
    ▼                                      ▼
[Diagnosis: Backend Down / Latency]    [Diagnosis: Kegagalan UI Riil]
  • Tangguhkan tes                       • Catat kegagalan
  • Jangan hitung sebagai flake tes      • Ambil screenshot bukti
  • Anotasikan laporan lingkungan        • Buka tiket investigasi
```

---

### 4. Pemulihan Mandiri Data Uji (Data Healing Fixtures)

Untuk mencegah kegagalan akibat data usang atau konflik constraint database unik (seperti `NIK` 16 digit dan `no_rkm_medis`), fixture pengujian menerapkan pola pemulihan otomatis:

```python
# Pola Fixture Data Tangguh (Self-Healing Fixture Pattern)
import uuid
from pasien.models import Pasien

def get_or_create_test_patient(prefix="TEST"):
    """
    Menjamin data pasien unik per-eksekusi uji untuk meniadakan Data Dependency Flakes.
    """
    unique_suffix = uuid.uuid4().hex[:6].upper()
    nik_unique = f"3201{uuid.uuid4().int % 1000000000000:012d}"
    rm_unique = f"RM-{unique_suffix}"
    
    pasien, created = Pasien.objects.get_or_create(
        nomor_rm=rm_unique,
        defaults={
            'nik': nik_unique,
            'nama_lengkap': f'{prefix} Pasien {unique_suffix}',
            'jenis_kelamin': 'L',
            'tanggal_lahir': '1990-01-01',
            'alamat': 'Jl. Pengujian Otomatis No. 1',
            'penjamin_utama': 'UMUM',
        }
    )
    return pasien
```

---

### 5. Alur Kerja Perbaikan Terobservasi & Skor Keyakinan (Observable Repair Workflow)

Setiap penggantian selektor otomatis oleh engine *self-healing* wajib melalui audit skor keyakinan (*confidence score* 0.0 - 1.0):

$$\text{Skor Keyakinan} = (0.30 \times S) + (0.15 \times V) + (0.15 \times C) + (0.15 \times T) + (0.15 \times L) + (0.10 \times A)$$

Dimana:
- $S$: Spesifisitas Tipe (testId=1.0, role=0.9, text=0.7, CSS=0.3)
- $V$: Visibilitas Elemen (1.0 jika terlihat, 0.0 jika tersembunyi)
- $C$: Kontainer Induk Sama (1.0 jika dalam form/card yang sama)
- $T$: Kesamaan Tag HTML (1.0 jika sama-sama `<button>`)
- $L$: Kesamaan Teks Levenshtein (Rasio kesamaan nama tombol)
- $A$: Tumpang Tindih Atribut (Jaccard similarity atribut HTML)

**Kebijakan Persetujuan Berdasarkan Skor:**
- **Skor >= 0.90:** Terapkan otomatis (*Auto-apply*), catat di ringkasan PR.
- **Skor 0.70 - 0.89:** Terapkan hanya di lingkungan karantina, beri tag untuk ditinjau manual oleh QA.
- **Skor 0.50 - 0.69:** Jangan terapkan; buka draf issue GitHub dengan bukti perubahan.
- **Skor < 0.50:** Tolak perbaikan kandidat; butuh perbaikan manual insinyur.

---

### 6. Kebijakan Manajemen Karantina (Quarantine Management Policy)

Jika suatu tes terbukti tidak stabil (*flaky*) dan akar masalahnya membutuhkan waktu investigasi lebih dari 1 hari, tes tersebut wajib dipindahkan ke karantina:

#### Aturan Ketat Karantina:
1. **Tidak Memblokir CI:** Tes yang di-karantina diberi penanda tag `@quarantine` dan dijalankan dalam job terpisah dengan konfigurasi `continue-on-error: true`.
2. **Masa Karantina Maksimum 14 Hari:** Setiap tes dalam karantina wajib memiliki tiket issue perbaikan (contoh: `#FIX-FLAKE-42`). Jika dalam 14 hari tidak diperbaiki, tes tersebut harus di-refactor ulang atau dihapus dari repositori. Karantina permanen dilarang.
3. **Ambang Batas Ukuran Karantina:** Maksimum 5% dari total test suite. Jika melebihi 5%, rilis ditangguhkan untuk sesi khusus pembersihan stabilitas test (*de-flaking sprint*).

#### Verifikasi Pelepasan dari Karantina:
Sebelum tag `@quarantine` dicabut, tes terkait wajib dieksekusi sebanyak **50 kali berturut-turut** (`--repeat-each=50`) di lingkungan CI dengan rasio keberhasilan mutlak **50/50 (100% Lolos)**.
