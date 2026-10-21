"""Logbook harian per shift untuk IGD dan Rawat Inap.

Satu baris ``LogbookHarian`` = satu unit/ruangan + satu tanggal + satu shift.
Angka rekap seksi I (jumlah pasien, triage, response time, LOS, sensus, BOR)
SELALU dihitung dari ``KunjunganPasien`` — tidak pernah diinput manual, supaya
rekap shift tidak bisa berbeda dari EMR.

Isian manual hanya untuk hal yang memang tidak ada di EMR: personel jaga,
checklist akreditasi (HPK / KE / SKP), bukti berkas, kejadian keselamatan,
dan lembar serah terima SBAR.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .models import UnitKerja
from .risiko_models import InsidenKeselamatan
from pasien.models import KunjunganPasien, Ruangan


# ---------------------------------------------------------------------------
# 1. Konstanta
# ---------------------------------------------------------------------------

JENIS_CHOICES = [
    ('IGD', 'Logbook Harian IGD'),
    ('RANAP', 'Logbook Harian Rawat Inap'),
]

SHIFT_CHOICES = [
    ('PAGI', 'Pagi (07.00–14.00)'),
    ('SIANG', 'Siang (14.00–21.00)'),
    ('MALAM', 'Malam (21.00–07.00)'),
]

# Jam mulai/selesai shift. Shift malam selesai pada hari berikutnya — lihat
# ``shift_window``.
SHIFT_MULAI = {'PAGI': time(7, 0), 'SIANG': time(14, 0), 'MALAM': time(21, 0)}
SHIFT_SELESAI = {'PAGI': time(14, 0), 'SIANG': time(21, 0), 'MALAM': time(7, 0)}

STATUS_CHOICES = [
    ('DRAF', 'Draf'),
    ('DIISI', 'Sudah Diserahterimakan'),
    ('DISETUJUI', 'Disetujui Kepala Unit'),
]

DEPENDENCY_CHOICES = [
    ('M', 'Mandiri'),
    ('P', 'Bantuan Parsial'),
    ('T', 'Ketergantungan Total'),
    ('?', 'Tidak Terdata'),
]

# Checklist akreditasi per jenis logbook. Bentuk tuple:
# (kunci, seksi, no_urut, parameter, butuh_nomor_segel)
CHECKLIST_IGD = [
    ('IGD-HPK-1', 'HPK', 1, 'Hak & kewajiban pasien diedukasikan saat penerimaan IGD', False),
    ('IGD-HPK-2', 'HPK', 2, 'General consent / informed consent tindakan terdokumentasi', False),
    ('IGD-HPK-3', 'HPK', 3, 'Identitas pasien diverifikasi (gelang identitas) sebelum tindakan', False),
    ('IGD-KE-1', 'KE', 1, 'Identifikasi pasien dengan dua identitas sebelum obat / tindakan', False),
    ('IGD-KE-2', 'KE', 2, 'Serah terima antar shift memakai SBAR dan terdokumentasi', False),
    ('IGD-SKP-1', 'SKP', 1, 'Kepatuhan kebersihan tangan lima momen', False),
    ('IGD-SKP-2', 'SKP', 2, 'Troli Emergency IGD & Kit Resusitasi tersegel dan lengkap', True),
    ('IGD-SKP-3', 'SKP', 3, 'Skrining risiko jatuh dikerjakan untuk seluruh pasien', False),
    ('IGD-SKP-4', 'SKP', 4, 'Kepatuhan alur klinis / clinical pathway kasus prioritas', False),
]

CHECKLIST_RANAP = [
    ('RANAP-HPK-1', 'HPK', 1, 'Hak & kewajiban pasien diedukasikan ulang pada shift ini', False),
    ('RANAP-HPK-2', 'HPK', 2, 'Persetujuan tindakan / rawat inap terdokumentasi di berkas', False),
    ('RANAP-HPK-3', 'HPK', 3, 'Identitas pasien diverifikasi sebelum pemberian obat & tindakan', False),
    ('RANAP-KE-1', 'KE', 1, 'Komunikasi efektif SBAR dipakai saat operan antar shift', False),
    ('RANAP-KE-2', 'KE', 2, 'Instruksi verbal / telepon ditulis dan dibacakan ulang (TBAK)', False),
    ('RANAP-SKP-1', 'SKP', 1, 'Kepatuhan kebersihan tangan lima momen di ruangan', False),
    ('RANAP-SKP-2', 'SKP', 2, 'Troli / Kit Emergency ruangan tersegel dan lengkap', True),
    ('RANAP-SKP-3', 'SKP', 3, 'Risiko jatuh dinilai ulang pada pasien risiko tinggi', False),
    ('RANAP-SKP-4', 'SKP', 4, 'Rekonsiliasi obat & penandaan obat high-alert', False),
]

CHECKLIST_PER_JENIS = {'IGD': CHECKLIST_IGD, 'RANAP': CHECKLIST_RANAP}

SEKSI_LABEL = {'HPK': 'HPK — Hak & Kewajiban Pasien', 'KE': 'KE — Komunikasi Efektif',
               'SKP': 'SKP — Sasaran Keselamatan Pasien'}


def checklist_untuk(jenis):
    """Daftar checklist untuk satu jenis logbook."""
    return CHECKLIST_PER_JENIS.get(jenis, [])


# ---------------------------------------------------------------------------
# 2. Helper waktu
# ---------------------------------------------------------------------------

def parse_jam(nilai):
    """Ubah ``'9.05'`` / ``'09:05'`` menjadi ``datetime.time``.

    Formulir cetak ARIMA menulis jam dengan titik (9.05), sedangkan input
    HTML mengirim titik dua. Keduanya diterima. Nilai kosong atau tidak
    terbaca menghasilkan ``None`` supaya pemanggil menampilkan tanda hubung
    alih-alih melempar exception.
    """
    if nilai is None:
        return None
    teks = str(nilai).strip()
    if not teks:
        return None
    teks = teks.replace('.', ':')
    if ':' not in teks:
        return None
    jam_teks, _, menit_teks = teks.partition(':')
    try:
        jam = int(jam_teks)
        menit = int((menit_teks or '0').strip()[:2])
    except (TypeError, ValueError):
        return None
    if not (0 <= jam <= 23 and 0 <= menit <= 59):
        return None
    return time(jam, menit)


def shift_window(tanggal, shift):
    """Kembalikan ``(awal, akhir)`` aware untuk satu shift.

    Shift MALAM (21.00–07.00) berakhir pada tanggal+1. Memakai ``__date``
    pada ``tanggal_masuk`` saja akan membuang seluruh kunjungan dini hari,
    karena itu jendela dikembalikan sebagai datetime.
    """
    mulai = SHIFT_MULAI.get(shift)
    if mulai is None:
        raise ValueError(f'Shift tidak dikenal: {shift}')
    akhir_t = SHIFT_SELESAI[shift]
    awal = timezone.make_aware(datetime.combine(tanggal, mulai))
    if shift == 'MALAM':
        akhir = timezone.make_aware(datetime.combine(tanggal + timedelta(days=1), akhir_t))
    else:
        akhir = timezone.make_aware(datetime.combine(tanggal, akhir_t))
    return awal, akhir


def response_time_menit(kunjungan):
    """Selisih menit antara jam masuk dan jam asesmen dokter.

    ``waktu_asesmen_dokter`` hanya menyimpan jam (tanpa tanggal). Bila jam
    asesmen lebih kecil dari jam masuk, asesmen dianggap terjadi keesokan
    harinya (pasien masuk 23.50, diasesmen 00.10) sehingga hasilnya tidak
    negatif.
    """
    jam_asesmen = parse_jam(getattr(kunjungan, 'waktu_asesmen_dokter', ''))
    if jam_asesmen is None or kunjungan.tanggal_masuk is None:
        return None
    masuk = timezone.localtime(kunjungan.tanggal_masuk)
    asesmen = timezone.make_aware(datetime.combine(masuk.date(), jam_asesmen))
    if asesmen < masuk:
        asesmen += timedelta(days=1)
    return int((asesmen - masuk).total_seconds() // 60)


def los_menit(kunjungan):
    """Lama rawat dalam menit; pasien yang belum pulang dihitung sampai sekarang."""
    if kunjungan.tanggal_masuk is None:
        return None
    keluar = kunjungan.tanggal_keluar or timezone.now()
    return max(int((keluar - kunjungan.tanggal_masuk).total_seconds() // 60), 0)


def dependency_kode(adl):
    """Petakan teks ``fungsional_adl`` ke kode M / P / T.

    Nilainya bebas teks di EMR ("Mandiri", "Bantuan Parsial",
    "Ketergantungan Total", kadang kosong), jadi pencocokan memakai
    ``startswith`` dan nilai tak dikenal jatuh ke ``'?'`` — bukan
    diasumsikan mandiri.
    """
    teks = (adl or '').strip().lower()
    if teks.startswith('mandiri'):
        return 'M'
    if teks.startswith('bantuan'):
        return 'P'
    if teks.startswith('ketergantungan'):
        return 'T'
    return '?'


def kunjungan_shift(jenis, tanggal, shift, ruangan=None):
    """QuerySet kunjungan yang masuk jendela shift.

    IGD: pasien yang MASUK pada jendela — mayoritas tidak menempati bed,
    sehingga filter ruangan justru mengosongkan rekap.
    Ranap: pasien yang masih dirawat di ruangan tersebut selama jendela,
    termasuk yang masuk sebelum shift dan belum keluar.
    """
    awal, akhir = shift_window(tanggal, shift)
    qs = KunjunganPasien.objects.select_related('pasien', 'bed', 'bed__ruangan')

    if jenis == 'IGD':
        return qs.filter(jenis_kunjungan='IGD',
                         tanggal_masuk__gte=awal,
                         tanggal_masuk__lt=akhir)

    qs = qs.filter(jenis_kunjungan='RANAP', tanggal_masuk__lt=akhir).filter(
        Q(tanggal_keluar__isnull=True) | Q(tanggal_keluar__gte=awal))
    if ruangan is not None:
        qs = qs.filter(bed__ruangan=ruangan)
    return qs


# ---------------------------------------------------------------------------
# 3. LogbookHarian
# ---------------------------------------------------------------------------

class LogbookHarian(models.Model):
    jenis = models.CharField('Jenis Logbook', max_length=6, choices=JENIS_CHOICES)
    unit = models.ForeignKey(UnitKerja, on_delete=models.PROTECT,
                             related_name='logbook_harian', verbose_name='Unit Kerja')
    ruangan = models.ForeignKey(Ruangan, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='logbook_harian', verbose_name='Ruangan')
    tanggal = models.DateField('Tanggal Shift')
    shift = models.CharField('Shift', max_length=6, choices=SHIFT_CHOICES)
    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES, default='DRAF')

    # Seksi II — personel & catatan shift
    pj_shift_nama = models.CharField('Penanggung Jawab Shift', max_length=150, blank=True)
    jumlah_perawat = models.PositiveSmallIntegerField('Jumlah Perawat Jaga', null=True, blank=True)
    rasio_perawat_pasien = models.CharField('Rasio Perawat : Pasien', max_length=20, blank=True)
    pasien_kritis_nama = models.CharField('Pasien Kritis (nama / no. bed)', max_length=250, blank=True)
    pasien_menunggu_kamar = models.PositiveSmallIntegerField('Pasien Menunggu Kamar', default=0)
    penunjang_pending = models.TextField('Pemeriksaan Penunjang Masih Pending', blank=True)
    catatan_shift = models.TextField('Catatan Shift', blank=True)

    # Seksi V — serah terima SBAR
    sbar_situation = models.TextField('SBAR — Situation', blank=True)
    sbar_background = models.TextField('SBAR — Background', blank=True)
    sbar_assessment = models.TextField('SBAR — Assessment', blank=True)
    sbar_recommendation = models.TextField('SBAR — Recommendation', blank=True)
    ttd_perawat = models.CharField('Nama Perawat Penanggung Jawab', max_length=150, blank=True)
    ttd_kepala_ruang = models.CharField('Nama Kepala Ruangan / Katim', max_length=150, blank=True)

    dibuat_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='logbook_dibuat')
    diserahterimakan_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True,
                                              related_name='logbook_serah_terima')
    diserahterimakan_pada = models.DateTimeField('Diserahterimakan Pada', null=True, blank=True)
    disetujui_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='logbook_disetujui')
    disetujui_pada = models.DateTimeField('Disetujui Pada', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Logbook Harian'
        verbose_name_plural = 'Logbook Harian'
        ordering = ['-tanggal', 'shift']
        constraints = [
            models.UniqueConstraint(fields=['jenis', 'unit', 'tanggal', 'shift'],
                                    name='logbook_harian_unik_per_shift'),
        ]

    def __str__(self):
        return f'{self.get_jenis_display()} — {self.unit.name} — {self.tanggal:%d/%m/%Y} {self.get_shift_display()}'

    # ── Status ────────────────────────────────────────────────────────────
    @property
    def boleh_ubah(self):
        """Isian hanya boleh diubah selama belum disetujui."""
        return self.status in ('DRAF', 'DIISI')

    @property
    def terkunci(self):
        return self.status == 'DISETUJUI'

    # ── Pengisian otomatis ────────────────────────────────────────────────
    def tarik_pasien(self):
        """Salin pasien shift ke ``LogbookPasien``. Idempoten.

        Snapshot dibuat sekali per kunjungan; pemanggilan ulang tidak
        menduplikasi baris maupun menimpa isian manual petugas.
        """
        dibuat = 0
        for k in kunjungan_shift(self.jenis, self.tanggal, self.shift, self.ruangan):
            bed = k.bed
            _, baru = LogbookPasien.objects.get_or_create(
                logbook=self, kunjungan=k,
                defaults={
                    'no_rm': k.pasien.no_rm,
                    'nama_pasien': k.pasien.nama_lengkap,
                    'jenis_kelamin': k.pasien.jenis_kelamin,
                    'umur': k.pasien.umur,
                    'no_bed': bed.kode_bed if bed else '',
                    'triage': k.triage,
                    'diagnosa': k.diagnosa_masuk,
                    'jam_masuk': timezone.localtime(k.tanggal_masuk).time()
                                 if k.tanggal_masuk else None,
                    'jam_keluar': timezone.localtime(k.tanggal_keluar).time()
                                  if k.tanggal_keluar else None,
                    'disposisi': k.disposisi_tindak_lanjut,
                    'dependency': dependency_kode(k.fungsional_adl),
                })
            if baru:
                dibuat += 1
        return dibuat

    def ensure_checklist(self):
        """Buat baris checklist yang belum ada. Idempoten."""
        dibuat = 0
        for kunci, seksi, no_urut, parameter, butuh_segel in checklist_untuk(self.jenis):
            _, baru = LogbookChecklist.objects.get_or_create(
                logbook=self, kunci=kunci,
                defaults={'seksi': seksi, 'no_urut': no_urut,
                          'parameter': parameter, 'butuh_nomor_segel': butuh_segel})
            if baru:
                dibuat += 1
        return dibuat

    # ── Rekap seksi I (dihitung) ──────────────────────────────────────────
    def rekap(self):
        """Angka seksi I. Dihitung dari pasien shift, tidak pernah diinput."""
        baris = list(self.pasien.select_related('kunjungan'))

        triage = {kode: 0 for kode, _ in KunjunganPasien.TRIAGE_CHOICES}
        disposisi = {kode: 0 for kode, _ in KunjunganPasien.DISPOSISI_CHOICES}
        dependency = {kode: 0 for kode, _ in DEPENDENCY_CHOICES}
        status = {kode: 0 for kode, _ in KunjunganPasien.STATUS_KUNJUNGAN}

        rt_daftar, los_daftar = [], []
        for b in baris:
            if b.triage in triage:
                triage[b.triage] += 1
            if b.disposisi in disposisi:
                disposisi[b.disposisi] += 1
            if b.dependency in dependency:
                dependency[b.dependency] += 1
            k = b.kunjungan
            if k is not None:
                if k.status in status:
                    status[k.status] += 1
                rt = response_time_menit(k)
                if rt is not None:
                    rt_daftar.append(rt)
                los = los_menit(k)
                if los is not None:
                    los_daftar.append(los)
            if b.jam_keluar and b.jam_masuk:
                menit = (b.jam_keluar.hour * 60 + b.jam_keluar.minute) - \
                        (b.jam_masuk.hour * 60 + b.jam_masuk.minute)
                if menit < 0:
                    menit += 24 * 60
                los_daftar.append(menit)

        return {
            'jumlah_pasien': len(baris),
            'triage': triage,
            'disposisi': disposisi,
            'dependency': dependency,
            'status': status,
            'rt_rata2': round(sum(rt_daftar) / len(rt_daftar), 1) if rt_daftar else None,
            'rt_terlambat': sum(1 for m in rt_daftar if m > 5),
            'rt_terisi': len(rt_daftar),
            'los_rata2_jam': round(sum(los_daftar) / len(los_daftar) / 60, 1) if los_daftar else None,
            'los_lebih_6_jam': sum(1 for m in los_daftar if m > 360),
            'bor_persen': self.hitung_bor(baris),
        }

    def hitung_bor(self, baris=None):
        """BOR shift dalam persen, atau ``None`` bila ruangan/kapasitas tidak diketahui."""
        if self.ruangan is None:
            return None
        total_bed = self.ruangan.beds.filter(
            status__in=['TERSEDIA', 'TERISI', 'DIBOOKING']).count() or self.ruangan.kapasitas
        if not total_bed:
            return None
        if baris is None:
            baris = list(self.pasien.select_related('kunjungan'))
        terisi = 0
        for b in baris:
            k = b.kunjungan
            if k is None or k.tanggal_keluar is None:
                terisi += 1
            else:
                awal, akhir = shift_window(self.tanggal, self.shift)
                if k.tanggal_keluar >= awal:
                    terisi += 1
        return round(terisi * 100 / total_bed, 1)


# ---------------------------------------------------------------------------
# 4. LogbookPasien — snapshot pasien per shift
# ---------------------------------------------------------------------------

class LogbookPasien(models.Model):
    logbook = models.ForeignKey(LogbookHarian, on_delete=models.CASCADE, related_name='pasien')
    kunjungan = models.ForeignKey(KunjunganPasien, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='logbook_baris', verbose_name='Kunjungan')

    no_rm = models.CharField('No. Rekam Medis', max_length=30, blank=True)
    nama_pasien = models.CharField('Nama Pasien', max_length=150)
    jenis_kelamin = models.CharField('Jenis Kelamin', max_length=2, blank=True)
    umur = models.PositiveSmallIntegerField('Umur (tahun)', null=True, blank=True)
    no_bed = models.CharField('No. Bed', max_length=20, blank=True)
    triage = models.CharField('Triage', max_length=10, blank=True)
    diagnosa = models.CharField('Diagnosa Masuk', max_length=300, blank=True)

    jam_masuk = models.TimeField('Jam Masuk', null=True, blank=True)
    jam_keluar = models.TimeField('Jam Keluar', null=True, blank=True)
    tindakan = models.CharField('Tindakan / Intervensi', max_length=300, blank=True)
    disposisi = models.CharField('Disposisi', max_length=15, blank=True)
    dependency = models.CharField('Ketergantungan (ADL)', max_length=1,
                                  choices=DEPENDENCY_CHOICES, default='?')
    catatan = models.TextField('Catatan Perawat', blank=True)

    class Meta:
        verbose_name = 'Pasien Logbook'
        verbose_name_plural = 'Pasien Logbook'
        ordering = ['jam_masuk', 'nama_pasien']
        constraints = [
            models.UniqueConstraint(fields=['logbook', 'kunjungan'],
                                    name='logbook_pasien_unik_per_kunjungan'),
        ]

    def __str__(self):
        return f'{self.nama_pasien} ({self.no_rm or "tanpa RM"})'


# ---------------------------------------------------------------------------
# 5. LogbookChecklist — butir akreditasi per shift
# ---------------------------------------------------------------------------

class LogbookChecklist(models.Model):
    STATUS_CHOICES = [
        ('TERLAKSANA', 'Terlaksana'),
        ('TIDAK', 'Tidak Terlaksana'),
        ('NA', 'Tidak Berlaku'),
    ]

    logbook = models.ForeignKey(LogbookHarian, on_delete=models.CASCADE, related_name='checklist')
    kunci = models.CharField('Kunci Butir', max_length=40)
    seksi = models.CharField('Seksi', max_length=10)
    no_urut = models.PositiveSmallIntegerField('No. Urut', default=1)
    parameter = models.CharField('Parameter yang Dinilai', max_length=250)
    status = models.CharField('Status', max_length=12, choices=STATUS_CHOICES, default='TERLAKSANA')
    keterangan = models.TextField('Keterangan / Temuan', blank=True)
    butuh_nomor_segel = models.BooleanField('Butuh Nomor Segel', default=False)
    nomor_segel = models.CharField('Nomor Segel Troli Emergency', max_length=60, blank=True)

    class Meta:
        verbose_name = 'Checklist Logbook'
        verbose_name_plural = 'Checklist Logbook'
        ordering = ['seksi', 'no_urut']
        constraints = [
            models.UniqueConstraint(fields=['logbook', 'kunci'],
                                    name='logbook_checklist_unik_per_butir'),
        ]

    def __str__(self):
        return f'{self.kunci} — {self.parameter[:50]}'


# ---------------------------------------------------------------------------
# 6. LogbookBukti — berkas bukti per shift
# ---------------------------------------------------------------------------

def _path_bukti(instance, filename):
    return f'logbook/{instance.logbook_id}/{filename}'


class LogbookBukti(models.Model):
    logbook = models.ForeignKey(LogbookHarian, on_delete=models.CASCADE, related_name='bukti')
    checklist = models.ForeignKey(LogbookChecklist, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='bukti', verbose_name='Butir Checklist')
    judul = models.CharField('Judul Berkas', max_length=200)
    berkas = models.FileField('Berkas', upload_to=_path_bukti)
    ukuran = models.CharField('Ukuran', max_length=20, blank=True)
    diunggah_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bukti Logbook'
        verbose_name_plural = 'Bukti Logbook'
        ordering = ['-created_at']

    def __str__(self):
        return self.judul


# ---------------------------------------------------------------------------
# 7. LogbookKejadian — kejadian keselamatan selama shift
# ---------------------------------------------------------------------------

class LogbookKejadian(models.Model):
    logbook = models.ForeignKey(LogbookHarian, on_delete=models.CASCADE, related_name='kejadian')
    jenis_insiden = models.CharField('Jenis Insiden', max_length=15,
                                     choices=InsidenKeselamatan.JENIS_CHOICES)
    tingkat_keparahan = models.CharField('Tingkat Keparahan', max_length=15,
                                         choices=InsidenKeselamatan.KEPARAHAN_CHOICES,
                                         default='TIDAK_CEDERA')
    waktu_kejadian = models.TimeField('Waktu Kejadian', null=True, blank=True)
    lokasi_kejadian = models.CharField('Lokasi Kejadian', max_length=200)
    deskripsi_kejadian = models.TextField('Deskripsi Kejadian')
    tindakan_segera = models.TextField('Tindakan Segera', blank=True)
    pasien_terpapar = models.BooleanField('Pasien Terpapar', default=False)

    insiden = models.ForeignKey(InsidenKeselamatan, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='logbook_kejadian',
                                verbose_name='Terhubung ke Insiden Keselamatan')
    dilaporkan_oleh = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Kejadian Logbook'
        verbose_name_plural = 'Kejadian Logbook'
        ordering = ['waktu_kejadian', 'pk']

    def __str__(self):
        return f'[{self.jenis_insiden}] {self.lokasi_kejadian}'

    def sync_ke_ikp(self):
        """Tulis ke ``InsidenKeselamatan`` supaya rekap IKP ikut menghitungnya.

        Kejadian di logbook bukan catatan terpisah: laporan mutu menarik IKP
        dari ``InsidenKeselamatan``, jadi kejadian shift yang tidak masuk ke
        sana akan hilang dari statistik rumah sakit. Idempoten — baris yang
        sudah tertaut tidak dibuat ulang.
        """
        if self.insiden_id:
            return self.insiden
        insiden = InsidenKeselamatan.objects.create(
            unit=self.logbook.unit,
            tanggal_kejadian=self.logbook.tanggal,
            waktu_kejadian=self.waktu_kejadian,
            jenis_insiden=self.jenis_insiden,
            tingkat_keparahan=self.tingkat_keparahan,
            lokasi_kejadian=self.lokasi_kejadian,
            deskripsi_kejadian=self.deskripsi_kejadian,
            tindakan_segera=self.tindakan_segera,
            pasien_terpapar=self.pasien_terpapar,
        )
        self.insiden = insiden
        self.save(update_fields=['insiden'])
        return insiden
