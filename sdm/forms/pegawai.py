from decimal import Decimal

from django import forms
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.akses import visible_units
from sdm.models import Pegawai


FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class PegawaiCreateForm(forms.ModelForm):
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
        label='Akhir Penempatan',
        required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    alokasi_fte = forms.DecimalField(
        label='Alokasi FTE',
        min_value=Decimal('0.01'),
        max_value=Decimal('1.00'),
        max_digits=4,
        decimal_places=2,
        initial=Decimal('1.00'),
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0.01', 'max': '1.00', 'step': '0.01'}
        ),
    )

    class Meta:
        model = Pegawai
        fields = [
            'nomor_pegawai',
            'nama_lengkap',
            'kategori',
            'profesi',
            'jabatan',
            'status',
        ]
        widgets = {
            'nomor_pegawai': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'nama_lengkap': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kategori': forms.Select(attrs={'class': SELECT_CLASS}),
            'profesi': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'jabatan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_employees'
        ).order_by('level', 'order', 'code')


class PegawaiEditForm(forms.ModelForm):
    class Meta:
        model = Pegawai
        fields = [
            'nomor_pegawai',
            'nama_lengkap',
            'kategori',
            'profesi',
            'jabatan',
            'status',
        ]
        widgets = {
            'nomor_pegawai': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'nama_lengkap': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kategori': forms.Select(attrs={'class': SELECT_CLASS}),
            'profesi': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'jabatan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }
