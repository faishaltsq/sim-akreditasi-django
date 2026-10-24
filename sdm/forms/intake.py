"""Five-step intake forms (Task B4)."""

from decimal import Decimal

from django import forms
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.akses import visible_units
from sdm.models import Pegawai


FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class IntakeStep1Form(forms.Form):
    """Identitas & Kontak — personal data per B2 contract."""

    GENDER_CHOICES = [
        ('LAKI_LAKI', 'Laki-laki'),
        ('PEREMPUAN', 'Perempuan'),
    ]
    AGAMA_CHOICES = [
        ('ISLAM', 'Islam'),
        ('KRISTEN_PROTESTAN', 'Kristen Protestant'),
        ('KRISTEN_KATOLIK', 'Katolik'),
        ('HINDU', 'Hindu'),
        ('BUDDHA', 'Buddha'),
        ('KONGHUCU', 'Konghucu'),
        ('LAINNYA', 'Lainnya'),
    ]

    nik = forms.CharField(
        label='NIK', max_length=16, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    nama_depan = forms.CharField(
        label='Nama Depan', max_length=100,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    nama_belakang = forms.CharField(
        label='Nama Belakang', max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    gelar_depan = forms.CharField(
        label='Gelar Depan', max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    gelar_belakang = forms.CharField(
        label='Gelar Belakang', max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    tempat_lahir = forms.CharField(
        label='Tempat Lahir', max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    tanggal_lahir = forms.DateField(
        label='Tanggal Lahir', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    gender = forms.ChoiceField(
        label='Jenis Kelamin', choices=GENDER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    agama = forms.ChoiceField(
        label='Agama', choices=AGAMA_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    status_pernikahan = forms.ChoiceField(
        label='Status Pernikahan', choices=(
            ('BELUM_KAWIN', 'Belum Kawin'), ('KAWIN', 'Kawin'),
            ('CERAI_HIDUP', 'Cerai Hidup'), ('CERAI_MATI', 'Cerai Mati'),
        ), required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    telepon = forms.CharField(
        label='Nomor Telepon', max_length=30, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    email_terverifikasi = forms.EmailField(
        label='Email Terverifikasi', required=False,
        widget=forms.EmailInput(attrs={'class': FIELD_CLASS}),
    )
    alamat_ktp = forms.CharField(
        label='Alamat KTP', required=False,
        widget=forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
    )
    alamat_domisili = forms.CharField(
        label='Alamat Domisili', required=False,
        widget=forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
    )
    alamat_sama_dengan_ktp = forms.BooleanField(
        label='Domisili sama dengan KTP', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class IntakeStep2Form(forms.Form):
    """Kepegawaian & Penempatan — employment history + first placement."""

    KATEGORI_PEGAWAI_CHOICES = [
        ('TETAP', 'Tetap'), ('PKWT', 'PKWT'), ('MITRA', 'Dokter Mitra'),
        ('LEPAS', 'Tenaga Lepas'), ('MAGANG', 'Magang'), ('RESIDEN', 'Residen'),
    ]

    nomor_pegawai = forms.CharField(
        label='Nomor Pegawai', max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    kategori = forms.ChoiceField(
        label='Kategori Staf', choices=Pegawai.KATEGORI_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    profesi = forms.CharField(
        label='Profesi', max_length=120, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    jabatan = forms.CharField(
        label='Jabatan', max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    status = forms.ChoiceField(
        label='Status Kepegawaian', choices=Pegawai.STATUS_CHOICES,
        initial='AKTIF',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    kategori_pegawai = forms.ChoiceField(
        label='Kategori Pegawai (kontrak)', choices=KATEGORI_PEGAWAI_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    tanggal_tmt = forms.DateField(
        label='TMT Kepegawaian', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    tanggal_akhir = forms.DateField(
        label='Tanggal Akhir', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    nomor_kontrak = forms.CharField(
        label='Nomor Kontrak', max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    tanggal_mulai_kontrak = forms.DateField(
        label='Tanggal Mulai Kontrak', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    tanggal_selesai_kontrak = forms.DateField(
        label='Tanggal Selesai Kontrak', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    jam_kontrak_per_minggu = forms.DecimalField(
        label='Jam Kerja Kontrak per Minggu', required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
    )
    jam_fulltime_referensi = forms.DecimalField(
        label='Jam Fulltime Referensi per Minggu', required=False,
        min_value=Decimal('0.01'), initial=Decimal('40.00'),
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
    )
    unit_kerja = forms.ModelChoiceField(
        queryset=UnitKerja.objects.none(),
        label='Unit Kerja',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    tanggal_mulai = forms.DateField(
        label='Mulai Penempatan',
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    tanggal_selesai = forms.DateField(
        label='Akhir Penempatan', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    alokasi_fte = forms.DecimalField(
        label='Alokasi FTE', min_value=Decimal('0.01'), max_value=Decimal('1.00'),
        max_digits=4, decimal_places=2, initial=Decimal('1.00'),
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0.01', 'max': '1.00', 'step': '0.01'}
        ),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_employees'
        ).order_by('level', 'order', 'code')


class IntakeStep3Form(forms.Form):
    """Legalitas & Pendidikan — licenses and education."""

    izin_subtype = forms.ChoiceField(
        label='Jenis Izin', choices=(
            ('STR', 'STR'), ('SIP', 'SIP'), ('SIPA', 'SIPA'), ('OTHER', 'Lainnya'),
        ), required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    nomor_izin = forms.CharField(
        label='Nomor Izin', max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    pemberi_izin = forms.CharField(
        label='Pemberi Izin', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    izin_profesi = forms.CharField(
        label='Profesi Izin', max_length=120, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    validity_mode = forms.ChoiceField(
        label='Mode Masa Berlaku', choices=(
            ('DATED', 'Tanggal Berthi'), ('LIFETIME', 'Seumur Hidup'),
        ), initial='DATED', required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    tanggal_terbit = forms.DateField(
        label='Tanggal Terbit', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    tanggal_berakhir = forms.DateField(
        label='Berlaku Sampai', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    organisasi_praktik = forms.CharField(
        label='Organisasi Praktik', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    lokasi_praktik = forms.CharField(
        label='Lokasi Praktik', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    is_local_rs = forms.BooleanField(
        label='Praktik di RS Ini', required=False, initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    pendidikan_tingkat = forms.ChoiceField(
        label='Tingkat Pendidikan', choices=(
            ('D3', 'D3'), ('S1', 'S1'), ('PROFESI', 'Profesi'), ('S2', 'S2'),
            ('SP1', 'Spesialis 1'), ('SP2', 'Spesialis 2'), ('OTHER', 'Lainnya'),
        ), required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    pendidikan_institusi = forms.CharField(
        label='Institusi', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    pendidikan_program = forms.CharField(
        label='Program Studi', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    tanggal_lulus = forms.DateField(
        label='Tanggal Lulus', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )


class IntakeStep4Form(forms.Form):
    """Akun & Akses — optional account activation."""

    create_account = forms.BooleanField(
        label='Buat akun login untuk pegawai ini', required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    email = forms.EmailField(
        label='Email untuk undangan aktivasi', required=False,
        widget=forms.EmailInput(attrs={'class': FIELD_CLASS}),
    )


class IntakeStep5Form(forms.Form):
    """Dokumen Pendukung — metadata only; files staged via service."""

    dokumen_judul = forms.CharField(
        label='Judul Dokumen Pendukung', max_length=250, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    dokumen_jenis_berkas = forms.ChoiceField(
        label='Jenis Berkas', choices=(
            ('KTP', 'KTP'), ('FOTO', 'Foto'), ('IJAZAH', 'Ijazah'),
            ('TRANSKRIP', 'Transkrip Nilai'), ('STR', 'STR'), ('SIP', 'SIP'),
            ('SIPA', 'SIPA'), ('KONTRAK', 'Kontrak Kerja'),
            ('SK_PENGANGKATAN', 'SK Pengangkatan'), ('SPK_RKK', 'SPK RKK'),
            ('URAIAN_TUGAS', 'Uraian Tugas'), ('SERTIFIKAT', 'Sertifikat'),
            ('OTHER', 'Lainnya'),
        ), required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
