from django import forms
from sdm.models import DataBpjsPegawai, ProfilPribadiPegawai

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'


class ProfilPribadiForm(forms.ModelForm):
    """Editable slice of restricted personal data.

    `nik` is deliberately excluded: NIK only enters through intake/OCR so that
    identity changes keep a single audit trail (see validate_personal_data).
    """
    class Meta:
        model = ProfilPribadiPegawai
        fields = [
            'nama_depan',
            'nama_belakang',
            'gelar_depan',
            'gelar_belakang',
            'tempat_lahir',
            'tanggal_lahir',
            'gender',
            'golongan_darah',
            'agama',
            'status_pernikahan',
            'telepon',
            'email_terverifikasi',
            'alamat_ktp',
            'rt_rw',
            'kelurahan',
            'kecamatan',
            'kabupaten_kota',
            'provinsi',
            'kode_pos',
            'alamat_domisili',
            'alamat_sama_dengan_ktp',
        ]
        widgets = {
            'nama_depan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'nama_belakang': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'gelar_depan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'gelar_belakang': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'tempat_lahir': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'tanggal_lahir': forms.DateInput(
                attrs={'class': FIELD_CLASS, 'type': 'date'}
            ),
            'gender': forms.Select(attrs={'class': SELECT_CLASS}),
            'golongan_darah': forms.Select(attrs={'class': SELECT_CLASS}),
            'agama': forms.Select(attrs={'class': SELECT_CLASS}),
            'status_pernikahan': forms.Select(attrs={'class': SELECT_CLASS}),
            'telepon': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'email_terverifikasi': forms.EmailInput(attrs={'class': FIELD_CLASS}),
            'alamat_ktp': forms.Textarea(
                attrs={'class': FIELD_CLASS, 'rows': 2}
            ),
            'rt_rw': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kelurahan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kecamatan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kabupaten_kota': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'provinsi': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kode_pos': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'alamat_domisili': forms.Textarea(
                attrs={'class': FIELD_CLASS, 'rows': 2}
            ),
        }

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)

    def clean_kode_pos(self):
        kode_pos = (self.cleaned_data.get('kode_pos') or '').strip()
        if kode_pos and not kode_pos.isdigit():
            raise forms.ValidationError('Kode pos harus berupa 5 digit angka.')
        if kode_pos and len(kode_pos) != 5:
            raise forms.ValidationError('Kode pos harus berupa 5 digit angka.')
        return kode_pos


class DataBpjsForm(forms.ModelForm):
    """BPJS Kesehatan & Ketenagakerjaan participation data.

    Card files live in the DokumenPegawai repository and are linked through
    `kartu_kesehatan_versi` / `kartu_tk_versi`, so they are not form fields.
    """
    class Meta:
        model = DataBpjsPegawai
        fields = [
            'no_bpjs_kesehatan',
            'status_bpjs_kesehatan',
            'faskes_1',
            'kelas_rawat',
            'tanggungan_keluarga',
            'no_bpjs_tk',
            'status_bpjs_tk',
            'tmt_bpjs_tk',
            'program_jkm',
            'program_jkk',
            'program_jht',
            'program_jp',
        ]
        widgets = {
            'no_bpjs_kesehatan': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'status_bpjs_kesehatan': forms.Select(attrs={'class': SELECT_CLASS}),
            'faskes_1': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'kelas_rawat': forms.Select(attrs={'class': SELECT_CLASS}),
            'tanggungan_keluarga': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '0', 'step': '1'}
            ),
            'no_bpjs_tk': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'status_bpjs_tk': forms.Select(attrs={'class': SELECT_CLASS}),
            'tmt_bpjs_tk': forms.DateInput(
                attrs={'class': FIELD_CLASS, 'type': 'date'}
            ),
        }

    def __init__(self, *args, employee=None, **kwargs):
        self.employee = employee
        super().__init__(*args, **kwargs)
