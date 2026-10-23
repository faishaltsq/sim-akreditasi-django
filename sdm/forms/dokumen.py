from django import forms

from sdm.models import DokumenPegawai

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class DokumenForm(forms.ModelForm):
    """Metadata for a private employee document; the file is stored separately."""

    file = forms.FileField(
        label='Berkas',
        widget=forms.ClearableFileInput(attrs={'class': FIELD_CLASS}),
    )
    issued_date = forms.DateField(
        label='Tanggal Terbit',
        required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )
    valid_until = forms.DateField(
        label='Berlaku Sampai',
        required=False,
        widget=forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
    )

    class Meta:
        model = DokumenPegawai
        fields = ['document_type', 'title', 'sensitivity']
        widgets = {
            'document_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'title': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 250}),
            'sensitivity': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('sensitivity') == 'health' and (
            cleaned.get('document_type') != 'HEALTH'
        ):
            raise forms.ValidationError(
                'Dokumen kesehatan kerja harus berjenis Kesehatan Kerja.'
            )
        return cleaned


class ReviewDokumenForm(forms.Form):
    STATUS_CHOICES = [
        ('VERIFIED', 'Terverifikasi'),
        ('REJECTED', 'Ditolak / Perlu Perbaikan'),
    ]
    status = forms.ChoiceField(
        label='Keputusan Tinjauan',
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    notes = forms.CharField(
        label='Catatan Tinjauan',
        required=False,
        widget=forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
    )
