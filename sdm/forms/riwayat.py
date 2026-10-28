from django import forms
from django.core.exceptions import ValidationError
from sdm.models import RiwayatKepegawaian

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class RiwayatKepegawaianForm(forms.ModelForm):
    class Meta:
        model = RiwayatKepegawaian
        fields = [
            'kategori_pegawai',
            'tanggal_tmt',
            'tanggal_akhir',
            'nomor_kontrak',
            'tanggal_mulai_kontrak',
            'tanggal_selesai_kontrak',
            'jam_kontrak_per_minggu',
            'jam_fulltime_referensi',
            'jabatan_struktural',
        ]
        widgets = {
            'kategori_pegawai': forms.Select(attrs={'class': SELECT_CLASS}),
            'tanggal_tmt': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'tanggal_akhir': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'nomor_kontrak': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'tanggal_mulai_kontrak': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'tanggal_selesai_kontrak': forms.DateInput(attrs={'class': FIELD_CLASS, 'type': 'date'}),
            'jam_kontrak_per_minggu': forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
            'jam_fulltime_referensi': forms.NumberInput(attrs={'class': FIELD_CLASS, 'step': '0.01'}),
            'jabatan_struktural': forms.TextInput(attrs={'class': FIELD_CLASS}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        tmt = cleaned.get('tanggal_tmt')
        akhir = cleaned.get('tanggal_akhir')
        if tmt and akhir and akhir < tmt:
            raise ValidationError({
                'tanggal_akhir': 'Tanggal akhir tidak boleh sebelum TMT.'
            })
        self._reject_overlapping_interval(tmt, akhir)
        return cleaned

    def _reject_overlapping_interval(self, tmt, akhir):
        """Riwayat kepegawaian tidak boleh bertumpuk: satu pegawai hanya boleh
        berada dalam satu kategori kepegawaian pada satu tanggal. Riwayat tanpa
        TMT tidak dapat diuji tumpang-tindih, jadi dilewati.
        """
        if tmt is None or self.employee is None:
            return
        others = RiwayatKepegawaian.objects.filter(pegawai=self.employee)
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        for other in others:
            if other.tanggal_tmt is None:
                continue
            other_end = other.tanggal_akhir
            if other_end is None:
                other_end = tmt
            if tmt <= other_end and other.tanggal_tmt <= (akhir or tmt):
                raise ValidationError({
                    'tanggal_tmt': (
                        'Rentang riwayat bertumpang dengan riwayat '
                        f'{other.get_kategori_pegawai_display()} '
                        f'({other.tanggal_tmt:%d %b %Y}'
                        + (f'–{other.tanggal_akhir:%d %b %Y}' if other.tanggal_akhir else '–sekarang')
                        + '). Tutup riwayat tersebut lebih dulu dengan tanggal akhir.'
                    )
                })

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.pegawai = self.employee
        if commit:
            instance.full_clean()
            instance.save()
        return instance
