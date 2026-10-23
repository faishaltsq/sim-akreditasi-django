from django import forms

from sdm.akses import visible_employees, visible_units
from sdm.models import (
    AktivitasOrientasi,
    KebutuhanPelatihan,
    Lamaran,
    Lowongan,
    PengajuanKredensial,
    ProgramOrientasi,
    RincianKewenangan,
    VerifikasiSumber,
)

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'
TEXTAREA_CLASS = 'form-control form-control-sm'


class LowonganForm(forms.ModelForm):
    unit_kerja = forms.ModelChoiceField(
        queryset=None, label='Unit Kerja',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = Lowongan
        fields = ['unit_kerja', 'profesi', 'judul', 'jumlah_kebutuhan', 'status']
        widgets = {
            'profesi': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
            'judul': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'jumlah_kebutuhan': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '1'}
            ),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_recruitment'
        ).order_by('level', 'order', 'code')


class LamaranForm(forms.ModelForm):
    class Meta:
        model = Lamaran
        fields = ['nama_pelamar', 'kontak']
        widgets = {
            'nama_pelamar': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'kontak': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
        }


class PengajuanKredensialForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = PengajuanKredensial
        fields = ['employee', 'unit_kerja']
        widgets = {'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        units = visible_units(user, capability='can_review_hc_credentials')
        self.fields['unit_kerja'].queryset = units.order_by('level', 'order', 'code')
        self.fields['employee'].queryset = visible_employees(
            user
        ).order_by('nama_lengkap')


class RincianKewenanganForm(forms.ModelForm):
    class Meta:
        model = RincianKewenangan
        fields = ['kewenangan', 'catatan']
        widgets = {
            'kewenangan': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'catatan': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }


class VerifikasiSumberForm(forms.ModelForm):
    class Meta:
        model = VerifikasiSumber
        fields = ['issuer', 'reference', 'method', 'outcome']
        widgets = {
            'issuer': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'reference': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'method': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
            'outcome': forms.Select(attrs={'class': SELECT_CLASS}),
        }


class ProgramOrientasiForm(forms.ModelForm):
    class Meta:
        model = ProgramOrientasi
        fields = ['nama', 'unit_kerja', 'berlaku_hari', 'is_active']
        widgets = {
            'nama': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS}),
            'berlaku_hari': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '1'}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_orientation'
        ).order_by('level', 'order', 'code')


class MulaiOrientasiForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    program = forms.ModelChoiceField(
        queryset=AktivitasOrientasi.objects.none(), label='Program',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = visible_employees(
            user, capability='can_manage_hc_orientation'
        ).order_by('nama_lengkap')
        self.fields['program'].queryset = ProgramOrientasi.objects.filter(
            is_active=True
        ).order_by('nama')


class KebutuhanPelatihanForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = KebutuhanPelatihan
        fields = ['employee', 'topik', 'alasan_agregat']
        widgets = {
            'topik': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'alasan_agregat': forms.Textarea(
                attrs={'class': TEXTAREA_CLASS, 'rows': 2}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = visible_employees(
            user, capability='can_manage_hc_training'
        ).order_by('nama_lengkap')
