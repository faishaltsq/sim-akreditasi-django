from decimal import Decimal, InvalidOperation

from django import forms

from sdm.akses import visible_units
from sdm.models import AktivitasBebanKerja, RencanaFormasi

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class RencanaFormasiForm(forms.ModelForm):
    unit_kerja = forms.ModelChoiceField(
        queryset=None, label='Unit Kerja',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = RencanaFormasi
        fields = [
            'unit_kerja',
            'profesi',
            'periode_mulai',
            'periode_selesai',
            'metode',
            'effective_minutes_per_employee',
            'support_allowance_pct',
        ]
        widgets = {
            'profesi': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
            'periode_mulai': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'periode_selesai': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'metode': forms.Select(attrs={'class': SELECT_CLASS}),
            'effective_minutes_per_employee': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '0.01', 'step': '0.01'}
            ),
            'support_allowance_pct': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '0', 'step': '0.01'}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_plan_hc_workforce'
        ).order_by('level', 'order', 'code')


class AktivitasBebanKerjaForm(forms.Form):
    nama = forms.CharField(
        label='Nama Aktivitas', max_length=200,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    volume = forms.DecimalField(
        label='Volume per Periode', min_value=Decimal('0.00'), max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'step': '0.01'}),
    )
    standard_minutes = forms.DecimalField(
        label='Standar Menit', min_value=Decimal('0.00'), max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0', 'step': '0.01'}),
    )
    service_category = forms.CharField(
        label='Kategori Layanan', max_length=120, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    equipment_assumption = forms.CharField(
        label='Asumsi Peralatan', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    qualification_note = forms.CharField(
        label='Catatan Kualifikasi', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )

    def save(self, plan):
        return AktivitasBebanKerja.objects.create(
            rencana=plan,
            nama=self.cleaned_data['nama'],
            volume=self.cleaned_data['volume'],
            standard_minutes=self.cleaned_data['standard_minutes'],
            service_category=self.cleaned_data['service_category'],
            equipment_assumption=self.cleaned_data['equipment_assumption'],
            qualification_note=self.cleaned_data['qualification_note'],
        )
