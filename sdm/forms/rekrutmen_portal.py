"""Fase C2: form pengajuan lamaran dari portal publik."""
from django import forms
from django.core.exceptions import ValidationError

from sdm.models import Pelamar
from sdm.services.rekrutmen_portal import (
    BERKAS_EXTENSI,
    BERKAS_MAKS_BYTE,
    dokumen_wajib,
)

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-control-sm'
JENIS_PENDIDIKAN = Pelamar.PENDIDIKAN_CHOICES


def validate_berkas_field(file_obj):
    """Reject a disallowed extension or an oversized file.

    Attached to each upload field so the message lands next to the offending
    input instead of surfacing as a page error.
    """
    if file_obj is None:
        return
    ext = file_obj.name.rsplit('.', 1)[-1].lower() if '.' in file_obj.name else ''
    if ext not in BERKAS_EXTENSI:
        raise ValidationError(
            f'Format berkas tidak didukung. Gunakan {", ".join(BERKAS_EXTENSI)}.'
        )
    if file_obj.size > BERKAS_MAKS_BYTE:
        raise ValidationError(
            f'Ukuran berkas melebihi {BERKAS_MAKS_BYTE // (1024 * 1024)} MB.'
        )


class LamaranPortalForm(forms.Form):
    """Public application form: identity plus one upload per required document.

    The required-document list is derived from the vacancy in ``__init__``, so
    a clinical vacancy asks for STR/SIP and a support role does not.
    """

    nama_lengkap = forms.CharField(
        label='Nama Lengkap', max_length=200,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
    )
    email = forms.EmailField(
        label='Email', required=False,
        widget=forms.EmailInput(attrs={'class': FIELD_CLASS}),
    )
    telepon = forms.CharField(
        label='Telepon / WhatsApp', max_length=40,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 40}),
    )
    pendidikan_terakhir = forms.ChoiceField(
        label='Pendidikan Terakhir', choices=JENIS_PENDIDIKAN,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    ipk = forms.DecimalField(
        label='IPK', max_digits=3, decimal_places=2, required=False,
        min_value=0, max_value=4,
        widget=forms.NumberInput(
            attrs={'class': FIELD_CLASS, 'min': '0', 'max': '4', 'step': '0.01'}
        ),
    )
    tanggal_lahir = forms.DateField(
        label='Tanggal Lahir', required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    pengalaman_bulan = forms.IntegerField(
        label='Pengalaman Kerja (bulan)', required=False, min_value=0,
        widget=forms.NumberInput(attrs={'class': FIELD_CLASS, 'min': '0'}),
    )

    def __init__(self, *args, vacancy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vacancy = vacancy
        if vacancy is None:
            return
        for jenis in dokumen_wajib(vacancy):
            self.fields[f'berkas_{jenis.lower()}'] = forms.FileField(
                label=f'Unggah {dict(self._jenis_choices())[jenis]}',
                required=True,
                validators=[validate_berkas_field],
                widget=forms.ClearableFileInput(
                    attrs={'class': FIELD_CLASS, 'accept': '.pdf,.jpg,.jpeg,.png'}
                ),
            )

    @staticmethod
    def _jenis_choices():
        from sdm.models import BerkasPelamar
        return BerkasPelamar.JENIS_CHOICES

    def files_by_jenis(self):
        """Map document kind -> uploaded file using the cleaned field names."""
        if not self.is_valid():
            return {}
        mapping = {}
        for name, value in self.cleaned_data.items():
            if name.startswith('berkas_') and value:
                jenis = name[len('berkas_'):].upper()
                mapping[jenis] = value
        return mapping

    @property
    def maks_ukuran_mb(self):
        return BERKAS_MAKS_BYTE // (1024 * 1024)

    @property
    def ekstensi_diizinkan(self):
        return ', '.join(e.upper() for e in BERKAS_EXTENSI)
