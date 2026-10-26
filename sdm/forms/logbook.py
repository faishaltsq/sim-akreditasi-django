"""C-2 logbook entry forms."""
from django import forms

from akreditasi.models import UnitKerja
from sdm.akses import visible_units
from sdm.models import EntriLogbookKlinis, KatalogTindakan

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'
TEXTAREA_CLASS = 'form-control form-control-sm'

MODUS_CHOICES = [
    ('katalog', 'Tindakan Katalog'),
    ('bebas', 'Tindakan Lain (Teks Bebas)'),
]


class EntriLogbookForm(forms.ModelForm):
    """XOR dispatch: 'modus' picks catalog or free-text, then the other clears."""

    modus = forms.ChoiceField(
        choices=MODUS_CHOICES, label='Jenis Tindakan',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = EntriLogbookKlinis
        fields = [
            'tanggal', 'unit_kerja', 'katalog_tindakan', 'tindakan',
            'jumlah_mandiri', 'jumlah_supervisi', 'catatan',
        ]
        widgets = {
            'tanggal': forms.DateInput(
                attrs={'class': FIELD_CLASS, 'type': 'date'}
            ),
            'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS}),
            'katalog_tindakan': forms.Select(attrs={'class': SELECT_CLASS}),
            'tindakan': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'jumlah_mandiri': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
            'jumlah_supervisi': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
            'catatan': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }

    def __init__(self, *args, employee=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        if user is not None and getattr(user, 'pegawai_hc', None) is not None:
            # Self-service: own entries only, own placement units, own profession catalog.
            employee = user.pegawai_hc
            self.fields['unit_kerja'].queryset = UnitKerja.objects.filter(
                pk__in=employee.penempatan.values('unit_kerja_id'),
            ).order_by('level', 'order', 'code')
        else:
            self.fields['unit_kerja'].queryset = visible_units(
                user, capability='can_review_hc_credentials'
            ).order_by('level', 'order', 'code')
        catalog = KatalogTindakan.objects.filter(is_active=True).exclude(
            tingkat_supervisi='T'
        )
        profesi_id = getattr(employee, 'profesi_master_id', None)
        if profesi_id:
            catalog = catalog.filter(jenjang__profesi_id=profesi_id)
        else:
            catalog = catalog.none()
        self.fields['katalog_tindakan'].queryset = catalog.select_related(
            'jenjang'
        ).order_by('jenjang__urutan', 'kode')

    def clean(self):
        cleaned = super().clean()
        modus = cleaned.get('modus')
        if modus == 'katalog':
            cleaned['tindakan'] = ''
            if not cleaned.get('katalog_tindakan'):
                self.add_error('katalog_tindakan', 'Pilih tindakan dari katalog.')
        else:
            cleaned['katalog_tindakan'] = None
            if not (cleaned.get('tindakan') or '').strip():
                self.add_error('tindakan', 'Isi nama tindakan.')
        for field in ('jumlah_mandiri', 'jumlah_supervisi'):
            if cleaned.get(field) is None:
                cleaned[field] = 0
        if not (cleaned.get('jumlah_mandiri') or cleaned.get('jumlah_supervisi')):
            self.add_error(None, 'Minimal satu jumlah (mandiri/supervisi) harus lebih dari nol.')
        return cleaned
