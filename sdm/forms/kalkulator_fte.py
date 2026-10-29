from decimal import Decimal, InvalidOperation

from django import forms

from sdm.akses import visible_units

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class KalkulatorFteForm(forms.Form):
    """Satu halaman: parameter JKE + beban kerja → pratinjau FTE.

    `activities` memakai textarea satu baris per aktivitas dengan format
    `nama | volume | menit`; parser mengembalikan tuple siap pakai
    compute_fte sehingga tidak ada format perantara yang bocor ke service.
    """
    unit_kerja = forms.ModelChoiceField(
        queryset=None, label='Unit Kerja',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    profesi = forms.CharField(
        label='Profesi', max_length=120,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
    )
    hari_kerja = forms.IntegerField(
        label='Hari Kerja per Tahun', min_value=0, initial=250,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
    )
    cuti_tahunan = forms.IntegerField(
        label='Cuti Tahunan (hari)', min_value=0, initial=12,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
    )
    hari_sakit_rata2 = forms.IntegerField(
        label='Rata-rata Sakit (hari)', min_value=0, initial=5,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
    )
    libur_nasional = forms.IntegerField(
        label='Libur Nasional (hari)', min_value=0, initial=16,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
    )
    pendidikan_pelatihan = forms.DecimalField(
        label='Pendidikan & Pelatihan (hari)', min_value=0, initial=5,
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0', 'step': '0.01'}
        ),
    )
    jam_kerja_per_hari = forms.DecimalField(
        label='Jam Kerja per Hari', min_value=0.01, initial=7.00,
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0.01', 'step': '0.01'}
        ),
    )
    support_allowance_pct = forms.DecimalField(
        label='Tunjangan Dukungan (%)', min_value=0, initial=15.00,
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0', 'step': '0.01'}
        ),
    )
    activities = forms.CharField(
        label='Beban Kerja', widget=forms.Textarea(
            attrs={
                'class': FIELD_CLASS,
                'rows': 8,
                'placeholder': 'Nama aktivitas | volume | standar menit',
            }
        ),
        help_text='Satu aktivitas per baris, format: nama | volume | menit.',
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_plan_hc_workforce'
        ).order_by('level', 'order', 'code')

    def clean_activities(self):
        raw = self.cleaned_data.get('activities') or ''
        parsed = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            parts = [part.strip() for part in stripped.split('|')]
            if len(parts) != 3 or not parts[0]:
                raise forms.ValidationError(
                    f'Baris "{stripped}" tidak valid; '
                    'gunakan format nama | volume | menit.'
                )
            try:
                volume = Decimal(parts[1])
                standard_minutes = Decimal(parts[2])
            except (InvalidOperation, ValueError):
                raise forms.ValidationError(
                    f'Baris "{stripped}" tidak valid; '
                    'gunakan format nama | volume | menit.'
                )
            if volume < 0 or standard_minutes < 0:
                raise forms.ValidationError(
                    f'Baris "{stripped}" tidak valid; '
                    'volume dan menit tidak boleh negatif.'
                )
            parsed.append((parts[0], volume, standard_minutes))
        if not parsed:
            raise forms.ValidationError(
                'Minimal satu aktivitas beban kerja wajib diisi.'
            )
        return parsed
