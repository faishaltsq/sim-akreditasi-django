"""Formulir modul Jadwal Praktek Dokter."""
from django import forms

from sdm.models import (
    JadwalPraktekRutin,
    PengajuanIzinDokter,
    Pegawai,
)


class JadwalPraktekRutinForm(forms.ModelForm):
    """Form pola jadwal mingguan; queryset dibatasi lingkup unit pengguna."""

    class Meta:
        model = JadwalPraktekRutin
        fields = [
            'dokter', 'unit_kerja', 'ruang_praktek', 'hari',
            'jam_mulai', 'jam_selesai', 'durasi_per_pasien_menit',
            'kuota_jkn', 'kuota_non_jkn', 'batas_daftar_menit', 'is_active',
        ]
        widgets = {
            'jam_mulai': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'jam_selesai': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'hari': forms.Select(choices=JadwalPraktekRutin.HARI_CHOICES),
        }

    def __init__(self, *args, units=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dokter'].queryset = Pegawai.objects.filter(
            status='AKTIF', kategori='PPA',
        ).order_by('nama_lengkap')
        if units is not None:
            self.fields['unit_kerja'].queryset = units.order_by('code')
        for name, field in self.fields.items():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            field.widget.attrs.setdefault('class', css)


class PengajuanIzinDokterForm(forms.ModelForm):
    """Form pengajuan cuti/izin dokter beserta usulan pengganti."""

    class Meta:
        model = PengajuanIzinDokter
        fields = [
            'dokter', 'jenis', 'tanggal_mulai', 'tanggal_selesai',
            'dokter_pengganti', 'catatan',
        ]
        widgets = {
            'tanggal_mulai': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'tanggal_selesai': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'catatan': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dokter_qs = Pegawai.objects.filter(
            status='AKTIF', kategori='PPA',
        ).order_by('nama_lengkap')
        self.fields['dokter'].queryset = dokter_qs
        self.fields['dokter_pengganti'].queryset = dokter_qs
        self.fields['dokter_pengganti'].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
