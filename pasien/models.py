"""
Modul Manajemen Pasien MonsisKami (ARIMA System)
Tahap 1–5: Pendaftaran → Pelayanan → Ranap → Billing → Discharge
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


# ── 1. Master Pasien ─────────────────────────────────────────────────────────

class Pasien(models.Model):
    JENIS_KELAMIN = [('L', 'Laki-laki'), ('P', 'Perempuan')]
    GOLDAR = [('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O'), ('-', 'Tidak Diketahui')]

    no_rm          = models.CharField('No. Rekam Medis', max_length=20, unique=True)
    nik            = models.CharField('NIK', max_length=16, blank=True)
    nama_lengkap   = models.CharField('Nama Lengkap', max_length=200)
    tanggal_lahir  = models.DateField('Tanggal Lahir')
    jenis_kelamin  = models.CharField('Jenis Kelamin', max_length=1, choices=JENIS_KELAMIN)
    golongan_darah = models.CharField('Golongan Darah', max_length=3, choices=GOLDAR, default='-')
    alamat         = models.TextField('Alamat', blank=True)
    no_hp          = models.CharField('No. HP', max_length=20, blank=True)
    no_bpjs        = models.CharField('No. BPJS', max_length=20, blank=True)
    alergi_obat    = models.TextField('Alergi Obat', blank=True, help_text='Pisahkan dengan koma')
    alergi_lain    = models.TextField('Alergi Lain', blank=True)
    # ── SatuSehat Kemenkes ──
    satusehat_id       = models.CharField('SatuSehat Patient ID', max_length=64, blank=True, null=True)
    satusehat_sync_at  = models.DateTimeField('Waktu Sync SatuSehat', null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pasien'
        verbose_name_plural = 'Data Pasien'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.no_rm}] {self.nama_lengkap}'

    @property
    def umur(self):
        from datetime import date
        today = date.today()
        b = self.tanggal_lahir
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def has_alergi(self):
        return bool(self.alergi_obat or self.alergi_lain)


# ── 2. Bed Management ────────────────────────────────────────────────────────

class Ruangan(models.Model):
    KELAS = [('VIP', 'VIP'), ('1', 'Kelas I'), ('2', 'Kelas II'), ('3', 'Kelas III'), ('ICU', 'ICU'), ('IGD', 'IGD'), ('OK', 'Kamar Operasi')]
    JENIS = [('RANAP', 'Rawat Inap'), ('IGD', 'IGD'), ('RAJAL', 'Rawat Jalan'), ('OK', 'Kamar Operasi'), ('ICU', 'ICU')]

    kode    = models.CharField('Kode Ruangan', max_length=20, unique=True)
    nama    = models.CharField('Nama Ruangan', max_length=100)
    kelas   = models.CharField('Kelas', max_length=5, choices=KELAS)
    jenis   = models.CharField('Jenis', max_length=10, choices=JENIS, default='RANAP')
    kapasitas = models.IntegerField('Kapasitas Bed', default=1)

    class Meta:
        verbose_name = 'Ruangan'
        verbose_name_plural = 'Ruangan'
        ordering = ['kelas', 'kode']

    def __str__(self):
        return f'[{self.kode}] {self.nama} ({self.get_kelas_display()})'


class Bed(models.Model):
    STATUS = [
        ('TERSEDIA', 'Tersedia'),
        ('DIBOOKING', 'Dibooking / Dipesan'),
        ('TERISI',   'Terisi'),
        ('STERILISASI', 'Proses Sterilisasi'),
        ('TIDAK_AKTIF', 'Tidak Aktif'),
    ]

    ruangan  = models.ForeignKey(Ruangan, on_delete=models.CASCADE, related_name='beds')
    kode_bed = models.CharField('Kode Bed', max_length=20)
    status   = models.CharField('Status', max_length=15, choices=STATUS, default='TERSEDIA')
    catatan  = models.CharField('Catatan', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Bed'
        verbose_name_plural = 'Bed Management'
        unique_together = [('ruangan', 'kode_bed')]
        ordering = ['ruangan', 'kode_bed']

    def __str__(self):
        return f'{self.ruangan.kode}-{self.kode_bed} [{self.get_status_display()}]'


# ── 3. Kunjungan Pasien ──────────────────────────────────────────────────────

POLIKLINIK_CHOICES = [
    ('POLI_JANTUNG', 'Poli Jantung & Pembuluh Darah'),
    ('POLI_PARU', 'Poli Paru & Respirasi'),
    ('POLI_PENYAKIT_DALAM', 'Poli Penyakit Dalam (Interna)'),
    ('POLI_BEDAH', 'Poli Bedah Umum'),
    ('POLI_ANAK', 'Poli Anak (Pediatri)'),
    ('POLI_OBGYN', 'Poli Kebidanan & Kandungan (Obgyn)'),
    ('POLI_MATA', 'Poli Mata'),
    ('POLI_SARAF', 'Poli Saraf (Neurologi)'),
    ('POLI_THT', 'Poli THT-KL'),
    ('POLI_GIGI', 'Poli Gigi & Mulut'),
    ('POLI_ORTHO', 'Poli Orthopedi & Traumatologi'),
    ('POLI_KULIT', 'Poli Kulit & Kelamin'),
    ('POLI_JIWA', 'Poli Jiwa & Psikiatri'),
    ('REHAB_MEDIK', 'Poli Rehabilitasi Medik'),
    ('POLI_ENDOKRIN', 'Poli Endokrin & Metabolik'),
    ('POLI_BSARAF', 'Poli Bedah Saraf'),
    ('POLI_UMUM', 'Poli Umum'),
]

DPJP_CHOICES = [
    ('dr. Faisal, Sp.JP', 'dr. Faisal, Sp.JP — Spesialis Jantung & Pembuluh Darah'),
    ('dr. Bambang, Sp.JP, FIHA', 'dr. Bambang, Sp.JP, FIHA — Spesialis Jantung & Pembuluh Darah'),
    ('dr. Indah, Sp.P', 'dr. Indah, Sp.P — Spesialis Paru & Respirasi'),
    ('dr. Gunawan, Sp.P, FAPSR', 'dr. Gunawan, Sp.P, FAPSR — Spesialis Paru'),
    ('dr. Budi Santoso, Sp.PD', 'dr. Budi Santoso, Sp.PD — Spesialis Penyakit Dalam'),
    ('dr. Siti Rahma, Sp.PD-KGEH', 'dr. Siti Rahma, Sp.PD-KGEH — Spesialis Penyakit Dalam'),
    ('dr. Hendra, Sp.B', 'dr. Hendra, Sp.B — Spesialis Bedah Umum'),
    ('dr. Ahmad, Sp.B, FICS', 'dr. Ahmad, Sp.B, FICS — Spesialis Bedah'),
    ('dr. Nurul, Sp.A', 'dr. Nurul, Sp.A — Spesialis Anak (Pediatri)'),
    ('dr. Maya, Sp.A, M.Biomed', 'dr. Maya, Sp.A, M.Biomed — Spesialis Anak'),
    ('dr. Rina, Sp.OG', 'dr. Rina, Sp.OG — Spesialis Kebidanan & Kandungan'),
    ('dr. Dewi, Sp.OG(K)', 'dr. Dewi, Sp.OG(K) — Spesialis Kebidanan & Kandungan'),
    ('dr. Farida, Sp.M', 'dr. Farida, Sp.M — Spesialis Mata'),
    ('dr. Eko, Sp.S', 'dr. Eko, Sp.S — Spesialis Saraf (Neurologi)'),
    ('dr. Haryanto, Sp.THT-KL', 'dr. Haryanto, Sp.THT-KL — Spesialis THT-KL'),
    ('drg. Amanda, Sp.KG', 'drg. Amanda, Sp.KG — Dokter Gigi Spesialis'),
    ('drg. Rizki', 'drg. Rizki — Dokter Gigi'),
    ('dr. Kevin, Sp.OT', 'dr. Kevin, Sp.OT — Spesialis Orthopedi & Traumatologi'),
    ('dr. Citra, Sp.DV', 'dr. Citra, Sp.DV — Spesialis Kulit & Kelamin'),
    ('dr. Hadi, Sp.KJ', 'dr. Hadi, Sp.KJ — Spesialis Kedokteran Jiwa'),
    ('dr. Lina, Sp.KFR', 'dr. Lina, Sp.KFR — Spesialis Rehabilitasi Medik'),
    ('dr. Jaga IGD', 'dr. Jaga IGD — Dokter Jaga Gawat Darurat'),
    ('dr. Pratama', 'dr. Pratama — Dokter Umum'),
    ('dr. Intan', 'dr. Intan — Dokter Umum'),
]


class KunjunganPasien(models.Model):
    JENIS_KUNJUNGAN = [
        ('IGD',   'Gawat Darurat (IGD)'),
        ('RAJAL', 'Rawat Jalan (Poliklinik)'),
        ('RANAP', 'Rawat Inap'),
    ]
    TIPE_PENJAMIN = [
        ('UMUM',    'Umum / Tunai'),
        ('BPJS',    'BPJS Kesehatan'),
        ('ASURANSI','Asuransi Swasta'),
    ]
    STATUS_KUNJUNGAN = [
        ('DAFTAR',    'Terdaftar'),
        ('TRIAGE',    'Triage (IGD)'),
        ('ASESMEN',   'Asesmen PPA'),
        ('RANAP',     'Rawat Inap'),
        ('PULANG',    'Pulang'),
        ('RUJUK',     'Dirujuk Keluar'),
        ('MENINGGAL', 'Meninggal'),
        ('BATAL',     'Dibatalkan'),
    ]
    TRIAGE_CHOICES = [
        ('MERAH',  'Merah — Prioritas I (Kritis)'),
        ('KUNING', 'Kuning — Prioritas II (Urgent)'),
        ('HIJAU',  'Hijau — Prioritas III (Non-Urgent)'),
        ('HITAM',  'Hitam — Prioritas IV (Expectant)'),
    ]

    pasien          = models.ForeignKey(Pasien, on_delete=models.CASCADE, related_name='kunjungan')
    no_kunjungan    = models.CharField('No. Kunjungan', max_length=30, unique=True)
    jenis_kunjungan = models.CharField('Jenis Kunjungan', max_length=10, choices=JENIS_KUNJUNGAN)
    tanggal_masuk   = models.DateTimeField('Tanggal Masuk')
    tanggal_keluar  = models.DateTimeField('Tanggal Keluar', null=True, blank=True)
    dpjp            = models.CharField('DPJP', max_length=150, blank=True)
    poliklinik      = models.CharField('Poliklinik / Unit', max_length=100, blank=True)
    bed             = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name='kunjungan')
    penjamin        = models.CharField('Penjamin', max_length=10, choices=TIPE_PENJAMIN, default='UMUM')
    diagnosa_masuk  = models.CharField('Diagnosa Masuk (ICD-10)', max_length=300, blank=True)
    diagnosa_keluar = models.CharField('Diagnosa Keluar (ICD-10)', max_length=300, blank=True)
    triage          = models.CharField('Triage IGD', max_length=10, choices=TRIAGE_CHOICES, blank=True)
    status          = models.CharField('Status Kunjungan', max_length=15, choices=STATUS_KUNJUNGAN, default='DAFTAR')
    catatan_admisi  = models.TextField('Catatan Admisi', blank=True)
    general_consent = models.BooleanField('General Consent Ditandatangani', default=False)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    # ── Discharge Planning H-1 ──
    discharge_planning_aktif   = models.BooleanField('Discharge Planning Aktif', default=False)
    discharge_planning_catatan = models.TextField('Catatan Discharge Planning', blank=True)
    discharge_planning_tgl     = models.DateField('Target Tanggal Pulang', null=True, blank=True)

    # ── SatuSehat Kemenkes Encounter ──
    satusehat_encounter_id = models.CharField('SatuSehat Encounter ID', max_length=64, blank=True, null=True)
    satusehat_status       = models.CharField('Status Sync SatuSehat', max_length=15,
                                choices=[('NOT_SYNCED','Belum Disinkronkan'),('SYNCED','Tersinkronisasi'),('FAILED','Gagal Sync')],
                                default='NOT_SYNCED')

    # ── Antrean & Status Klinis ──
    FLAG_KHUSUS_CHOICES = [
        ('NORMAL',   'Normal'),
        ('AMBULANS', 'Rujukan Ambulans'),
        ('KRITIS',   'Kondisi Kritis / Resusitasi'),
    ]
    STATUS_ANTREAN_CHOICES = [
        ('MENUNGGU',        'Menunggu'),
        ('DIPANGGIL',       'Dipanggil'),
        ('SEDANG_DILAYANI', 'Sedang Dilayani'),
        ('SELESAI',         'Selesai'),
    ]
    nomor_antrean   = models.CharField('No. Antrean', max_length=25, blank=True)
    flag_khusus     = models.CharField('Flag Kondisi Khusus', max_length=10, choices=FLAG_KHUSUS_CHOICES, default='NORMAL')
    status_antrean  = models.CharField('Status Antrean', max_length=20, choices=STATUS_ANTREAN_CHOICES, default='MENUNGGU')

    # ── Tanda-Tanda Vital (TTV) ──
    ttv_sistole     = models.PositiveSmallIntegerField('Tekanan Darah Sistole (mmHg)', null=True, blank=True)
    ttv_diastole    = models.PositiveSmallIntegerField('Tekanan Darah Diastole (mmHg)', null=True, blank=True)
    ttv_nadi        = models.PositiveSmallIntegerField('Nadi (bpm)', null=True, blank=True)
    ttv_rr          = models.PositiveSmallIntegerField('Laju Napas / RR (x/menit)', null=True, blank=True)
    ttv_suhu        = models.DecimalField('Suhu (°C)', max_digits=4, decimal_places=1, null=True, blank=True)
    ttv_spo2        = models.PositiveSmallIntegerField('SpO2 (%)', null=True, blank=True)
    ttv_gcs         = models.CharField('Glasgow Coma Scale (GCS)', max_length=30, blank=True, help_text='Contoh: E4V5M6 (15) atau Somnolen')
    ttv_skala_nyeri = models.PositiveSmallIntegerField('Skala Nyeri (NRS 0-10)', null=True, blank=True, help_text='0 (Tidak Nyeri) s.d 10 (Sangat Hebat)')
    icd9_tindakan   = models.CharField('Tindakan Medis (ICD-9-CM)', max_length=300, blank=True)

    # ── Asesmen Awal IGD (Revisi 02 — Biopsikososiospiritual) ──
    anamnesis_rps          = models.TextField('Riwayat Penyakit Sekarang (RPS)', blank=True)
    anamnesis_rpd          = models.TextField('Riwayat Penyakit Dahulu (RPD)', blank=True)
    anamnesis_rpk          = models.TextField('Riwayat Penyakit Keluarga (RPK)', blank=True)
    anamnesis_obat         = models.TextField('Riwayat Pengobatan / Obat Saat Ini', blank=True)
    fisik_airway           = models.TextField('Airway Assessment', blank=True)
    fisik_breathing        = models.TextField('Breathing Assessment', blank=True)
    fisik_circulation      = models.TextField('Circulation Assessment', blank=True)
    fisik_disability       = models.TextField('Disability Assessment (Neuro)', blank=True)
    fisik_exposure         = models.TextField('Exposure / Environmental', blank=True)
    status_psikososial     = models.TextField('Status Psikologis & Sosial-Ekonomi', blank=True)
    status_spiritual       = models.TextField('Status Spiritual & Budaya', blank=True)
    skrining_jatuh_skor    = models.PositiveSmallIntegerField('Skor Risiko Jatuh', null=True, blank=True)
    skrining_jatuh_grade   = models.CharField('Grade Risiko Jatuh', max_length=20, blank=True, help_text='RENDAH / SEDANG / TINGGI')
    skrining_gizi_mst      = models.PositiveSmallIntegerField('Skor Skrining Gizi (MST)', null=True, blank=True)

    # ── Diagnosis Keperawatan 3S (SDKI / SLKI / SIKI) ──
    diagnosa_keperawatan_sdki   = models.TextField('Diagnosis Keperawatan (SDKI)', blank=True, help_text='Contoh: D.0077 - Nyeri Akut')
    luaran_keperawatan_slki     = models.TextField('Luaran Keperawatan (SLKI)', blank=True, help_text='Contoh: L.08066 - Tingkat Nyeri Menurun')
    intervensi_keperawatan_siki = models.TextField('Intervensi Keperawatan (SIKI)', blank=True, help_text='Contoh: I.08238 - Manajemen Nyeri')

    # ── Rujukan & Konsultasi ──
    sisrute_rs_tujuan = models.CharField('RS Tujuan Rujukan (SISRUTE)', max_length=200, blank=True)
    sisrute_alasan    = models.TextField('Alasan Rujukan Eksternal', blank=True)
    konsul_ke_poli    = models.CharField('Konsul ke Poliklinik', max_length=100, blank=True)
    konsul_catatan    = models.TextField('Catatan Konsultasi Internal', blank=True)

    # ── Meninggal Dunia ──
    waktu_kematian    = models.DateTimeField('Waktu Kematian', null=True, blank=True)
    penyebab_kematian = models.TextField('Penyebab Kematian', blank=True)

    class Meta:
        verbose_name = 'Kunjungan Pasien'
        verbose_name_plural = 'Kunjungan Pasien'
        ordering = ['-tanggal_masuk']

    def __str__(self):
        return f'[{self.no_kunjungan}] {self.pasien.nama_lengkap} ({self.get_jenis_kunjungan_display()})'

    @property
    def lama_rawat(self):
        """Length of Stay dalam hari."""
        from django.utils import timezone
        end = self.tanggal_keluar or timezone.now()
        delta = end - self.tanggal_masuk
        return max(delta.days, 1)

    @property
    def is_aktif(self):
        return self.status not in ('PULANG', 'RUJUK', 'MENINGGAL')

    @property
    def is_asesmen_awal_lengkap(self):
        """Compliance check: anamnesis, ABCDE airway, diagnosis medis, AND diagnosis keperawatan 3S."""
        return bool(
            self.anamnesis_rps.strip()
            and self.fisik_airway.strip()
            and self.diagnosa_masuk.strip()
            and self.diagnosa_keperawatan_sdki.strip()
        )

    @property
    def news_score(self):
        return self.hitung_news_score()[0]

    @property
    def news_category(self):
        return self.hitung_news_score()[1]

    def hitung_news_score(self):
        """
        National Early Warning Score (NEWS-2) from 5 TTV parameters.
        Returns: (int score, str category) — ('NORMAL'|'RENDAH'|'SEDANG'|'TINGGI').
        Gracefully handles None/missing values by treating them as 0 score.
        """
        score = 0
        # Respiratory Rate (RR)
        rr = self.ttv_rr
        if rr is not None:
            if rr <= 8 or rr >= 25:
                score += 3
            elif 21 <= rr <= 24:
                score += 2
            elif 9 <= rr <= 11:
                score += 1
        # SpO2 (saturation)
        spo2 = self.ttv_spo2
        if spo2 is not None:
            if spo2 <= 91:
                score += 3
            elif 92 <= spo2 <= 93:
                score += 2
            elif 94 <= spo2 <= 95:
                score += 1
        # Systolic BP
        bp = self.ttv_sistole
        if bp is not None:
            if bp <= 90 or bp >= 220:
                score += 3
            elif 91 <= bp <= 100:
                score += 2
            elif 101 <= bp <= 110:
                score += 1
        # Heart Rate (Pulse)
        hr = self.ttv_nadi
        if hr is not None:
            if hr <= 40 or hr >= 131:
                score += 3
            elif 111 <= hr <= 130:
                score += 2
            elif (41 <= hr <= 50) or (91 <= hr <= 110):
                score += 1
        # Temperature
        temp = self.ttv_suhu
        if temp is not None:
            if temp <= 35.0:
                score += 3
            elif temp >= 39.1:
                score += 2
            elif (35.1 <= temp <= 36.0) or (38.1 <= temp <= 39.0):
                score += 1
        if score == 0:
            category = 'NORMAL'
        elif score <= 4:
            category = 'RENDAH'
        elif score <= 6:
            category = 'SEDANG'
        else:
            category = 'TINGGI'
        return score, category

    def admit_to_ranap(self, bed, dpjp=None, catatan=''):
        """Transfer / admit patient to Inpatient (RANAP) and lock the bed."""
        from django.db import transaction
        with transaction.atomic():
            if bed.status != 'TERSEDIA':
                raise ValueError(f"Bed {bed} sedang berstatus {bed.get_status_display()}, tidak dapat ditempati.")
            self.jenis_kunjungan = 'RANAP'
            self.status = 'RANAP'
            self.bed = bed
            if dpjp:
                self.dpjp = dpjp
            if catatan:
                self.catatan_admisi = f"{self.catatan_admisi}\n[Admisi Ranap] {catatan}".strip()
            self.save()
            bed.status = 'TERISI'
            bed.save()

    def discharge_patient(self, kondisi='MEMBAIK', resume='', user=None, tanggal=None, edukasi='', obat='', kontrol=None):
        """Discharge patient, release bed to sterilisation, and create DischargeRecord."""
        from django.utils import timezone
        from django.db import transaction
        with transaction.atomic():
            tgl = tanggal or timezone.now()
            self.status = 'PULANG'
            self.tanggal_keluar = tgl
            old_bed = self.bed
            self.bed = None
            self.save()
            if old_bed:
                old_bed.status = 'STERILISASI'
                old_bed.save()
            total = sum(b.subtotal for b in self.billing.all())
            DischargeRecord.objects.update_or_create(
                kunjungan=self,
                defaults={
                    'tanggal_discharge': tgl,
                    'kondisi_pulang':    kondisi,
                    'resume_medis':      resume or 'Pelayanan selesai.',
                    'edukasi_pulang':    edukasi,
                    'obat_pulang':       obat,
                    'jadwal_kontrol':    kontrol,
                    'total_tagihan':     total,
                    'status_clearance':  'CLEARANCE',
                    'dibuat_oleh':       user,
                }
            )


# ── 4. Asesmen Risiko Klinis ─────────────────────────────────────────────────

class AsesmenRisikoKlinis(models.Model):
    JENIS_ASESMEN = [
        ('JATUH_MORSE',    'Risiko Jatuh — Morse Fall Scale (Dewasa)'),
        ('JATUH_HUMPTY',   'Risiko Jatuh — Humpty Dumpty (Anak)'),
        ('NYERI',          'Asesmen Nyeri (NRS/VAS)'),
        ('NUTRISI',        'Asesmen Nutrisi (MNA/NRS-2002)'),
        ('PPI',            'Pencegahan Infeksi (PPI Bundle)'),
        ('ALERGI',         'Asesmen Alergi'),
    ]
    GRADE = [
        ('RENDAH',   'Rendah'),
        ('SEDANG',   'Sedang'),
        ('TINGGI',   'Tinggi'),
        ('SANGAT_TINGGI', 'Sangat Tinggi'),
    ]

    kunjungan    = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='asesmen_risiko')
    jenis        = models.CharField('Jenis Asesmen', max_length=20, choices=JENIS_ASESMEN)
    skor         = models.IntegerField('Skor', default=0)
    grade        = models.CharField('Grade Risiko', max_length=15, choices=GRADE, blank=True)
    temuan       = models.TextField('Temuan / Detail Asesmen', blank=True)
    intervensi   = models.TextField('Intervensi yang Dilakukan', blank=True)
    dinilai_oleh = models.CharField('Dinilai Oleh', max_length=150, blank=True)
    tanggal      = models.DateTimeField('Tanggal Asesmen', auto_now_add=True)

    class Meta:
        verbose_name = 'Asesmen Risiko Klinis'
        verbose_name_plural = 'Asesmen Risiko Klinis'
        ordering = ['-tanggal']

    def __str__(self):
        return f'{self.get_jenis_display()} — {self.kunjungan.pasien.nama_lengkap} ({self.grade})'


# ── 5. CPPT (Catatan Perkembangan Pasien Terintegrasi) ───────────────────────

class CPPT(models.Model):
    PROFESI = [
        ('DOKTER',   'Dokter / DPJP'),
        ('PERAWAT',  'Perawat'),
        ('FARMASI',  'Farmasi / Apoteker'),
        ('GIZI',     'Gizi / Dietisien'),
        ('REHAB',    'Rehabilitasi Medik'),
        ('BIDAN',    'Bidan'),
        ('LAINNYA',  'PPA Lainnya'),
    ]

    kunjungan      = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='cppt')
    profesi        = models.CharField('Profesi PPA', max_length=10, choices=PROFESI)
    nama_ppa       = models.CharField('Nama PPA', max_length=150)
    tanggal        = models.DateTimeField('Tanggal & Jam')
    subjektif      = models.TextField('S — Subjektif (Keluhan)')
    objektif       = models.TextField('O — Objektif (Pemeriksaan)')
    asesmen        = models.TextField('A — Asesmen (Diagnosa)')
    plan           = models.TextField('P — Plan (Rencana)')
    verifikasi_dpjp = models.BooleanField('Terverifikasi DPJP', default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CPPT'
        verbose_name_plural = 'CPPT (Catatan Perkembangan Pasien)'
        ordering = ['-tanggal']

    def __str__(self):
        return f'CPPT [{self.get_profesi_display()}] — {self.kunjungan.pasien.nama_lengkap} {self.tanggal.strftime("%d/%m/%Y %H:%M")}'


# ── 6. Billing ───────────────────────────────────────────────────────────────

class BillingItem(models.Model):
    KATEGORI = [
        ('JASA_MEDIS',  'Jasa Medis / Tindakan'),
        ('OBAT',        'Obat & BMHP'),
        ('LAB',         'Laboratorium'),
        ('RADIOLOGI',   'Radiologi / Imaging'),
        ('KAMAR',       'Biaya Kamar / Akomodasi'),
        ('ADMIN',       'Administrasi'),
        ('LAINNYA',     'Lainnya'),
    ]

    kunjungan  = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='billing')
    kategori   = models.CharField('Kategori', max_length=15, choices=KATEGORI)
    nama_item  = models.CharField('Nama Item', max_length=200)
    kuantitas  = models.DecimalField('Kuantitas', max_digits=8, decimal_places=2, default=1)
    harga_satuan = models.DecimalField('Harga Satuan (Rp)', max_digits=12, decimal_places=2, default=0)
    kode_icd   = models.CharField('Kode ICD-10/9-CM', max_length=20, blank=True)
    tanggal    = models.DateTimeField('Tanggal', auto_now_add=True)
    dicatat_oleh = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Billing Item'
        verbose_name_plural = 'Billing Pasien'
        ordering = ['-tanggal']

    def __str__(self):
        return f'{self.nama_item} — {self.kunjungan.pasien.nama_lengkap}'

    @property
    def subtotal(self):
        return self.kuantitas * self.harga_satuan


# ── 7. Discharge / Pulang ────────────────────────────────────────────────────

class DischargeRecord(models.Model):
    KONDISI_PULANG = [
        ('MEMBAIK',    'Kondisi Membaik'),
        ('SEMBUH',     'Sembuh'),
        ('APS',        'Atas Permintaan Sendiri (APS)'),
        ('RUJUK',      'Dirujuk ke RS Lain'),
        ('MENINGGAL',  'Meninggal'),
    ]
    STATUS_CLEARANCE = [
        ('PROSES',    'Proses Verifikasi'),
        ('CLEARANCE', 'Clearance / Bebas Administrasi'),
    ]

    kunjungan         = models.OneToOneField(KunjunganPasien, on_delete=models.CASCADE, related_name='discharge')
    tanggal_discharge = models.DateTimeField('Tanggal Discharge')
    kondisi_pulang    = models.CharField('Kondisi Saat Pulang', max_length=15, choices=KONDISI_PULANG)
    resume_medis      = models.TextField('Resume Medis (Discharge Summary)')
    edukasi_pulang    = models.TextField('Edukasi & Instruksi Pulang', blank=True)
    obat_pulang       = models.TextField('Obat Pulang', blank=True)
    jadwal_kontrol    = models.DateField('Jadwal Kontrol Ulang', null=True, blank=True)
    total_tagihan     = models.DecimalField('Total Tagihan (Rp)', max_digits=14, decimal_places=2, default=0)
    status_clearance  = models.CharField('Status Clearance', max_length=15, choices=STATUS_CLEARANCE, default='PROSES')
    dibuat_oleh       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    # ── PAPS (Pulang Atas Permintaan Sendiri) ──
    paps_alasan       = models.TextField('Alasan PAPS', blank=True)
    paps_nama_penolak = models.CharField('Nama Pasien / Keluarga Penolak', max_length=150, blank=True)

    # ── SKDP (Surat Keterangan Dalam Perawatan) ──
    skdp_nomor        = models.CharField('Nomor SKDP', max_length=50, blank=True)
    skdp_diagnosa     = models.CharField('Diagnosa SKDP', max_length=250, blank=True)
    skdp_terapi       = models.TextField('Rencana Terapi Lanjutan', blank=True)

    class Meta:
        verbose_name = 'Discharge Record'
        verbose_name_plural = 'Discharge Records'

    def __str__(self):
        return f'Discharge [{self.kunjungan.pasien.nama_lengkap}] {self.tanggal_discharge.strftime("%d/%m/%Y")}'


# ── 7b. Order Penunjang (Laboratorium & Radiologi) ───────────────────────────

class OrderPenunjang(models.Model):
    JENIS_CHOICES = [
        ('LAB',       'Laboratorium'),
        ('RADIOLOGI', 'Radiologi / Imaging'),
    ]
    PRIORITAS_CHOICES = [
        ('CITO',  'CITO / Segera'),
        ('RUTIN', 'Rutin'),
    ]
    STATUS_CHOICES = [
        ('ORDERED', 'Terkirim'),
        ('PROSES',  'Dalam Pemeriksaan'),
        ('SELESAI', 'Selesai / Hasil Tersedia'),
    ]

    kunjungan         = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='order_penunjang')
    jenis             = models.CharField('Jenis Penunjang', max_length=15, choices=JENIS_CHOICES)
    nama_pemeriksaan  = models.CharField('Nama Pemeriksaan / Tindakan', max_length=255)
    catatan_klinis    = models.TextField('Catatan Klinis / Indikasi', blank=True)
    prioritas         = models.CharField('Prioritas', max_length=10, choices=PRIORITAS_CHOICES, default='RUTIN')
    status            = models.CharField('Status Order', max_length=15, choices=STATUS_CHOICES, default='ORDERED')
    dokter_pengirim        = models.CharField('Dokter Pengirim', max_length=150, blank=True)
    hasil_pemeriksaan      = models.TextField('Hasil Pemeriksaan', blank=True)
    is_critical_value      = models.BooleanField('Critical Value Alert', default=False)
    critical_value_catatan = models.CharField('Catatan Nilai Kritis', max_length=200, blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Penunjang'
        verbose_name_plural = 'Order Penunjang (Lab / Radiologi)'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_jenis_display()}] {self.nama_pemeriksaan} — {self.kunjungan.pasien.nama_lengkap}'


# ── 8. E-Prescribing & Farmasi ────────────────────────────────────────────────

class ResepElektronik(models.Model):
    STATUS_RESEP = [
        ('DRAFT',       'Draft Dokter'),
        ('DIKIRIM',     'Terkirim ke Farmasi'),
        ('DISPENSING',  'Sedang Diracik / Dispensing'),
        ('SELESAI',     'Selesai & Diserahkan'),
        ('BATAL',       'Dibatalkan'),
    ]
    JENIS_RESEP = [
        ('RAWAT_INAP',  'Rawat Inap (Depo Ranap)'),
        ('RAWAT_JALAN', 'Rawat Jalan (Depo Rajal)'),
        ('IGD',         'IGD Cito'),
        ('PULANG',      'Obat Pulang / Discharge'),
    ]

    no_resep         = models.CharField('No. Resep', max_length=30, unique=True)
    kunjungan        = models.ForeignKey(KunjunganPasien, on_delete=models.CASCADE, related_name='resep_list')
    dokter_peresep   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resep_dibuat')
    tanggal_resep    = models.DateTimeField('Waktu Dibuat', auto_now_add=True)
    jenis_resep      = models.CharField('Jenis Resep', max_length=15, choices=JENIS_RESEP, default='RAWAT_INAP')
    status           = models.CharField('Status Farmasi', max_length=15, choices=STATUS_RESEP, default='DIKIRIM')
    catatan_dokter   = models.CharField('Catatan Dokter / Iter', max_length=250, blank=True)
    catatan_apoteker = models.CharField('Catatan / Telaah Apoteker', max_length=250, blank=True)
    apoteker         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resep_diproses')
    waktu_selesai    = models.DateTimeField('Waktu Selesai Penyerahan', null=True, blank=True)

    class Meta:
        verbose_name = 'Resep Elektronik'
        verbose_name_plural = 'Resep Elektronik (Farmasi)'
        ordering = ['-tanggal_resep']

    def __str__(self):
        return f'{self.no_resep} — {self.kunjungan.pasien.nama_lengkap} ({self.get_status_display()})'

    @property
    def total_biaya(self):
        return sum(item.subtotal for item in self.items.all())


class ResepDetail(models.Model):
    BENTUK_SEDIAAN = [
        ('TABLET',  'Tablet / Kaplet'),
        ('KAPSUL',  'Kapsul'),
        ('SIRUP',   'Sirup / Suspensi'),
        ('INJEKSI', 'Injeksi / Ampul / Vial'),
        ('INFUS',   'Cairan Infus'),
        ('SALEP',   'Salep / Krim / Tetes'),
        ('PUYER',   'Puyer / Racikan'),
    ]

    resep          = models.ForeignKey(ResepElektronik, on_delete=models.CASCADE, related_name='items')
    nama_obat      = models.CharField('Nama Obat / Alkes', max_length=150)
    bentuk_sediaan = models.CharField('Bentuk', max_length=10, choices=BENTUK_SEDIAAN, default='TABLET')
    dosis          = models.CharField('Dosis', max_length=50, help_text='Contoh: 500 mg, 1 gr, 100 ml')
    aturan_pakai   = models.CharField('Signa / Aturan Pakai', max_length=100, help_text='Contoh: 3x1 tablet sesudah makan')
    jumlah         = models.PositiveIntegerField('Jumlah', default=1)
    harga_satuan   = models.DecimalField('Harga Satuan (Rp)', max_digits=12, decimal_places=2, default=0)
    catatan_khusus = models.CharField('Catatan Khusus (Sebelum/Sesudah Makan, dll)', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Detail Obat Resep'
        verbose_name_plural = 'Detail Obat Resep'

    def __str__(self):
        return f'{self.nama_obat} ({self.aturan_pakai}) x {self.jumlah}'

    @property
    def subtotal(self):
        return self.jumlah * self.harga_satuan


# ── 10. Pemesanan Kamar (Bed Booking) ────────────────────────────────────────

class BookingKamar(models.Model):
    STATUS_BOOKING = [
        ('BOOKED',  'Dipesan (Menunggu Check-in)'),
        ('CHECKIN', 'Sudah Masuk Kamar'),
        ('BATAL',   'Dibatalkan'),
        ('EXPIRED', 'Kedaluwarsa'),
    ]

    nomor_booking = models.CharField('Nomor Booking', max_length=30, unique=True)
    pasien        = models.ForeignKey(Pasien, on_delete=models.CASCADE, related_name='room_bookings')
    kunjungan     = models.ForeignKey('KunjunganPasien', on_delete=models.SET_NULL, null=True, blank=True, related_name='room_bookings')
    bed           = models.ForeignKey(Bed, on_delete=models.CASCADE, related_name='bookings')
    waktu_booking = models.DateTimeField('Waktu Pesan', auto_now_add=True)
    batas_waktu   = models.DateTimeField('Batas Waktu Tunggu')
    status        = models.CharField('Status Booking', max_length=15, choices=STATUS_BOOKING, default='BOOKED')
    catatan       = models.TextField('Catatan / Indikasi', blank=True)
    alasan_batal  = models.TextField('Alasan Pembatalan', blank=True)
    petugas       = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Pemesanan Kamar (Booking Bed)'
        verbose_name_plural = 'Pemesanan Kamar (Booking Bed)'
        ordering = ['-waktu_booking']

    def __str__(self):
        return f'{self.nomor_booking} - {self.pasien.nama_lengkap} -> {self.bed}'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.status == 'BOOKED':
            self.bed.status = 'DIBOOKING'
            self.bed.save(update_fields=['status'])

    def batalkan(self, alasan=''):
        self.status = 'BATAL'
        self.alasan_batal = alasan
        self.save(update_fields=['status', 'alasan_batal'])
        if self.bed.status == 'DIBOOKING':
            self.bed.status = 'TERSEDIA'
            self.bed.save(update_fields=['status'])

    def checkin(self):
        self.status = 'CHECKIN'
        self.save(update_fields=['status'])
        self.bed.status = 'TERISI'
        self.bed.save(update_fields=['status'])
        if self.kunjungan:
            self.kunjungan.bed = self.bed
            self.kunjungan.jenis_kunjungan = 'RANAP'
            self.kunjungan.status = 'RANAP'
            self.kunjungan.save(update_fields=['bed', 'jenis_kunjungan', 'status'])


# ── 11. General Consent Rawat Inap (STARKES HPK) ───────────────────────────

class GeneralConsentRawatInap(models.Model):
    HUBUNGAN_CHOICES = [
        ('DIRI_SENDIRI', 'Diri Sendiri (Pasien)'),
        ('SUAMI_ISTRI',  'Suami / Istri'),
        ('ORANG_TUA',    'Orang Tua / Ayah / Ibu'),
        ('ANAK',         'Anak Kandung'),
        ('SAUDARA',      'Saudara Kandung'),
        ('WALI',         'Wali / Penanggung Jawab Lainnya'),
    ]

    JAMINAN_CHOICES = [
        ('BPJS',     'BPJS Kesehatan / KIS'),
        ('UMUM',     'Biaya Pribadi (Umum / Tunai)'),
        ('ASURANSI', 'Asuransi Swasta / Perusahaan'),
    ]

    kunjungan                  = models.OneToOneField('KunjunganPasien', on_delete=models.CASCADE, related_name='general_consent_doc')
    nama_pj                    = models.CharField('Nama Penanggung Jawab / Wali', max_length=150)
    nik_pj                     = models.CharField('NIK Penanggung Jawab', max_length=20)
    hubungan                   = models.CharField('Hubungan dengan Pasien', max_length=20, choices=HUBUNGAN_CHOICES)
    telepon_pj                 = models.CharField('Nomor Telepon / WhatsApp', max_length=25)
    alamat_pj                  = models.TextField('Alamat Lengkap')

    # STARKES HPK Consent Checkboxes
    setuju_perawatan_umum      = models.BooleanField('Persetujuan Tindakan & Perawatan Medis Umum', default=True)
    setuju_pelepasan_informasi = models.BooleanField('Persetujuan Pelepasan Informasi Medis & Privasi', default=True)
    setuju_tata_tertib         = models.BooleanField('Persetujuan Tata Tertib Rawat Inap & Jam Besuk', default=True)
    nama_anggota_akses_info    = models.TextField('Nama Anggota Keluarga yang Diberi Akses Informasi', blank=True, help_text='Daftar nama keluarga yang diperbolehkan menerima informasi perkembangan medis pasien.')

    # Billing & Financial Responsibility
    jaminan_biaya              = models.CharField('Penjamin / Penanggung Biaya', max_length=15, choices=JAMINAN_CHOICES, default='BPJS')
    pernyataan_selisih_biaya   = models.BooleanField('Setuju Ketentuan Selisih Biaya (Bila Naik Kelas)', default=True)

    waktu_persetujuan          = models.DateTimeField('Waktu Persetujuan', auto_now_add=True)
    petugas_saksi              = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'General Consent Rawat Inap'
        verbose_name_plural = 'General Consent Rawat Inap'

    def __str__(self):
        return f'General Consent Ranap - {self.kunjungan.pasien.nama_lengkap} (Wali: {self.nama_pj})'

    @property
    def is_lengkap(self):
        return bool(self.nama_pj and self.nik_pj and self.setuju_perawatan_umum and self.setuju_pelepasan_informasi)



