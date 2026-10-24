"""K3 forms (Task A8)."""

from django import forms

from sdm.models import (
    ImunisasiPegawai,
    InsidenK3Pegawai,
    PemeriksaanKesehatanKerja,
    TindakLanjutK3,
)


FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class PemeriksaanKesehatanKerjaForm(forms.ModelForm):
    class Meta:
        model = PemeriksaanKesehatanKerja
        fields = [
            'tanggal', 'status_kebugaran',
            'ringkasan_klinis', 'berlaku_sampai', 'pemeriksa',
        ]
        widgets = {
            'tanggal': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'status_kebugaran': forms.Select(attrs={'class': SELECT_CLASS}),
            'ringkasan_klinis': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
            'berlaku_sampai': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'pemeriksa': forms.TextInput(attrs={'class': FIELD_CLASS}),
        }


class ImunisasiPegawaiForm(forms.ModelForm):
    class Meta:
        model = ImunisasiPegawai
        fields = ['jenis', 'dosis_ke', 'tanggal', 'berlaku_sampai', 'pemberi']
        widgets = {
            'jenis': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'dosis_ke': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '1'}),
            'tanggal': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'berlaku_sampai': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'pemberi': forms.TextInput(attrs={'class': FIELD_CLASS}),
        }


class InsidenK3PegawaiForm(forms.ModelForm):
    class Meta:
        model = InsidenK3Pegawai
        fields = ['employee', 'unit_kerja', 'kategori', 'tanggal', 'deskripsi', 'status']
        widgets = {
            'employee': forms.Select(attrs={'class': SELECT_CLASS}),
            'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS}),
            'kategori': forms.Select(attrs={'class': SELECT_CLASS}),
            'tanggal': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'deskripsi': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }


class TindakLanjutK3Form(forms.ModelForm):
    class Meta:
        model = TindakLanjutK3
        fields = ['tindakan', 'penanggung_jawab', 'tenggat', 'selesai']
        widgets = {
            'tindakan': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
            'penanggung_jawab': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'tenggat': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'selesai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
