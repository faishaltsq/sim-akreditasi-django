from django import forms

from sdm.forms.riwayat import FIELD_CLASS, SELECT_CLASS
from sdm.models import PeristiwaSDM


class AktivitasManualForm(forms.Form):
    """Pencatatan aktivitas manual oleh pengelola SDM.

    Nilai yang tersimpan masuk ke PeristiwaSDM sebagai baris audit baru;
    model itu immutable, jadi tidak ada jalur edit setelah tersimpan.
    """
    kategori = forms.ChoiceField(
        label='Kategori', choices=PeristiwaSDM.KATEGORI_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    judul = forms.CharField(
        label='Judul Aktivitas', max_length=255,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 255}),
    )
    deskripsi = forms.CharField(
        label='Deskripsi', widget=forms.Textarea(
            attrs={'class': FIELD_CLASS, 'rows': 3}
        ),
    )
    status = forms.ChoiceField(
        label='Status', choices=PeristiwaSDM.STATUS_CHOICES,
        initial='SUCCESS',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    modul = forms.CharField(
        label='Modul', max_length=100, initial='Human Capital', required=False,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 100}),
    )
