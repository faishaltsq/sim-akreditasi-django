"""C-2 logbook entry forms."""
from django import forms
from django.db.models import Q
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.akses import visible_units
from sdm.models import (
    EntriLogbookKlinis,
    KatalogTindakan,
    PenugasanKlinis,
    RincianKewenangan,
)

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
            'tanggal', 'waktu', 'pasien_ref', 'kategori', 'shift',
            'unit_kerja', 'katalog_tindakan', 'tindakan',
            'jumlah_mandiri', 'jumlah_supervisi', 'jumlah_kolaborasi', 'catatan',
        ]
        widgets = {
            'tanggal': forms.DateInput(
                attrs={'class': FIELD_CLASS, 'type': 'date'}
            ),
            'waktu': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': FIELD_CLASS, 'type': 'datetime-local'},
            ),
            'pasien_ref': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kategori': forms.Select(attrs={'class': SELECT_CLASS}),
            'shift': forms.Select(attrs={'class': SELECT_CLASS}),
            'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS}),
            'katalog_tindakan': forms.Select(attrs={'class': SELECT_CLASS}),
            'tindakan': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'jumlah_mandiri': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
            'jumlah_supervisi': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
            'jumlah_kolaborasi': forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
            'catatan': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }

    def __init__(self, *args, employee=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kategori'].required = False
        self.fields['jumlah_kolaborasi'].required = False
        self.fields['jumlah_supervisi'].required = False
        self.fields['jumlah_mandiri'].required = False
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
        ).filter(self._privilege_catalog_filter(employee))
        profesi_id = getattr(employee, 'profesi_master_id', None)
        if profesi_id:
            catalog = catalog.filter(jenjang__profesi_id=profesi_id)
        else:
            catalog = catalog.none()
        self.fields['katalog_tindakan'].queryset = catalog.select_related(
            'jenjang'
        ).order_by('jenjang__urutan', 'kode')

    @staticmethod
    def _privilege_catalog_filter(employee):
        """Own active SPK privileges when one exists, else profession fallback.

        Active means: assignment flag on, today inside its validity period,
        and the privilege line actually granted by the director (TIDAK_DIBERIKAN
        is not a privilege).
        """
        if employee is None or not employee.pk:
            return Q()  # ponytail: no SPK linkage yet — profession filter alone; narrow when RKK data flows
        today = timezone.localdate()
        active = PenugasanKlinis.objects.filter(
            employee=employee,
            is_active=True,
            berlaku_mulai__lte=today,
        ).filter(
            Q(berlaku_sampai__isnull=True) | Q(berlaku_sampai__gte=today)
        )
        if not active.exists():
            return Q()  # profession fallback per plan Fase 1.3
        rincian = RincianKewenangan.objects.filter(
            pengajuan__decision_id__in=active.values('decision_id'),
            catalog_item__isnull=False,
        ).exclude(status_spk__in=('', 'TIDAK_DIBERIKAN'))
        ids = rincian.values('catalog_item_id')
        return Q(pk__in=ids)

    def clean(self):
        cleaned = super().clean()
        cleaned['kategori'] = cleaned.get('kategori') or self.instance.kategori
        modus = cleaned.get('modus')
        if modus == 'katalog':
            cleaned['tindakan'] = ''
            if not cleaned.get('katalog_tindakan'):
                self.add_error('katalog_tindakan', 'Pilih tindakan dari katalog.')
        else:
            cleaned['katalog_tindakan'] = None
            if not (cleaned.get('tindakan') or '').strip():
                self.add_error('tindakan', 'Isi nama tindakan.')
        for field in ('jumlah_mandiri', 'jumlah_supervisi', 'jumlah_kolaborasi'):
            if cleaned.get(field) is None:
                cleaned[field] = 0
        if not any(cleaned.get(field) for field in (
            'jumlah_mandiri', 'jumlah_supervisi', 'jumlah_kolaborasi',
        )):
            self.add_error(None, 'Minimal satu jumlah (mandiri, supervisi, atau kolaborasi) harus lebih dari nol.')
        return cleaned
