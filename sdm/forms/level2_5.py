from django import forms
from django.forms import inlineformset_factory

from sdm.akses import visible_employees, visible_units
from sdm.services.profil_kredensial import credential_profile
from sdm.models import (
    AktivitasOrientasi,
    KatalogTindakan,
    KebutuhanPelatihan,
    Lamaran,
    Lowongan,
    PengajuanKredensial,
    PenilaianTindakan,
    ProgramOrientasi,
    RincianKewenangan,
    VerifikasiSumber,
)

FIELD_CLASS = 'form-control form-control-sm'
SELECT_CLASS = 'form-select form-select-sm'
TEXTAREA_CLASS = 'form-control form-control-sm'


class LowonganForm(forms.ModelForm):
    unit_kerja = forms.ModelChoiceField(
        queryset=None, label='Unit Kerja',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = Lowongan
        fields = ['unit_kerja', 'profesi', 'judul', 'jumlah_kebutuhan', 'status']
        widgets = {
            'profesi': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
            'judul': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'jumlah_kebutuhan': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '1'}
            ),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_recruitment'
        ).order_by('level', 'order', 'code')


class LamaranForm(forms.ModelForm):
    class Meta:
        model = Lamaran
        fields = ['nama_pelamar', 'kontak']
        widgets = {
            'nama_pelamar': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'kontak': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
        }


class PengajuanKredensialForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={
            'class': SELECT_CLASS, 'data-kredensial-employee': '1',
        }),
    )

    class Meta:
        model = PengajuanKredensial
        fields = ['employee', 'unit_kerja', 'jenis']
        widgets = {
            'unit_kerja': forms.Select(attrs={
                'class': SELECT_CLASS, 'data-kredensial-unit': '1',
            }),
            'jenis': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        units = visible_units(user, capability='can_review_hc_credentials')
        self.fields['unit_kerja'].queryset = units.order_by('level', 'order', 'code')
        self.fields['employee'].queryset = visible_employees(
            user
        ).order_by('nama_lengkap')



    def clean(self):
        """Block submission when the employee's mandatory licences are unusable.

        Kredensial Awal and Re-Kredensial both assert a current right to
        practise, so an absent or expired STR/SIP makes the request unverifiable
        at source. The failure is attached to ``employee`` so the operator sees
        which fact is missing instead of a silent redirect.
        """
        cleaned = super().clean()
        employee = cleaned.get('employee')
        jenis = cleaned.get('jenis')
        if employee is None or jenis not in ('AWAL', 'REKREDENSIAL'):
            return cleaned
        profile = credential_profile(employee)
        unusable = [
            lic['subtype'] for lic in profile['licenses']
            if lic['label'] != 'Berlaku'
        ]
        if unusable:
            self.add_error(
                'employee',
                'Dokumen legalitas belum layak untuk pengajuan '
                f'{" / ".join(unusable)}: statusnya bukan "Berlaku". '
                'Perbarui STR/SIP di E-File pegawai terlebih dahulu, atau '
                'pilih jenis pengajuan lain.',
            )
        return cleaned
class RincianKewenanganForm(forms.ModelForm):
    class Meta:
        model = RincianKewenangan
        fields = ['kewenangan', 'catalog_item', 'usulan', 'catatan']
        widgets = {
            'kewenangan': forms.TextInput(
                attrs={'class': FIELD_CLASS, 'maxlength': 200}
            ),
            'catalog_item': forms.Select(attrs={'class': SELECT_CLASS}),
            'usulan': forms.Select(attrs={'class': SELECT_CLASS}),
            'catatan': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }

    def __init__(self, *args, pengajuan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usulan'].initial = 'MANDIRI'
        self.fields['usulan'].required = False
        catalog = KatalogTindakan.objects.filter(is_active=True).exclude(
            tingkat_supervisi='T'
        )
        profesi_id = getattr(
            getattr(pengajuan, 'employee', None), 'profesi_master_id', None
        )
        employee_emp = getattr(pengajuan, 'employee', None)
        if profesi_id is None and getattr(employee_emp, 'jenjang_master', None) is not None:
            profesi_id = employee_emp.jenjang_master.profesi_id
        if profesi_id:
            # Auto-load: only the profession's own RKK catalog is selectable.
            catalog = catalog.filter(jenjang__profesi_id=profesi_id)
        else:
            catalog = catalog.none()
        jenjang_id = getattr(
            getattr(pengajuan, 'employee', None), 'jenjang_master_id', None
        )
        if jenjang_id:
            catalog = catalog.filter(jenjang_id=jenjang_id)
        self.fields['catalog_item'].queryset = catalog.select_related(
            'jenjang'
        ).order_by('jenjang__urutan', 'kode')
        self.fields['catalog_item'].required = False
        self.fields['kewenangan'].required = False


class VerifikasiSumberForm(forms.ModelForm):
    class Meta:
        model = VerifikasiSumber
        fields = ['issuer', 'reference', 'method', 'outcome']
        widgets = {
            'issuer': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'reference': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'method': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 120}),
            'outcome': forms.Select(attrs={'class': SELECT_CLASS}),
        }


class ProgramOrientasiForm(forms.ModelForm):
    class Meta:
        model = ProgramOrientasi
        fields = ['nama', 'unit_kerja', 'berlaku_hari', 'is_active']
        widgets = {
            'nama': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'unit_kerja': forms.Select(attrs={'class': SELECT_CLASS}),
            'berlaku_hari': forms.NumberInput(
                attrs={'class': FIELD_CLASS, 'min': '1'}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_kerja'].queryset = visible_units(
            user, capability='can_manage_hc_orientation'
        ).order_by('level', 'order', 'code')


class MulaiOrientasiForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    program = forms.ModelChoiceField(
        queryset=AktivitasOrientasi.objects.none(), label='Program',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = visible_employees(
            user, capability='can_manage_hc_orientation'
        ).order_by('nama_lengkap')
        self.fields['program'].queryset = ProgramOrientasi.objects.filter(
            is_active=True
        ).order_by('nama')


class KebutuhanPelatihanForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=None, label='Pegawai',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )

    class Meta:
        model = KebutuhanPelatihan
        fields = ['employee', 'topik', 'alasan_agregat']
        widgets = {
            'topik': forms.TextInput(attrs={'class': FIELD_CLASS, 'maxlength': 200}),
            'alasan_agregat': forms.Textarea(
                attrs={'class': TEXTAREA_CLASS, 'rows': 2}
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = visible_employees(
            user, capability='can_manage_hc_training'
        ).order_by('nama_lengkap')


class PenilaianTindakanForm(forms.ModelForm):
    class Meta:
        model = PenilaianTindakan
        fields = ['rincian', 'rekomendasi', 'catatan_khusus']
        widgets = {
            'rincian': forms.HiddenInput(),
            'rekomendasi': forms.Select(attrs={'class': SELECT_CLASS}),
            'catatan_khusus': forms.Textarea(
                attrs={'class': TEXTAREA_CLASS, 'rows': 2}
            ),
        }


PenilaianTindakanFormSet = inlineformset_factory(
    PengajuanKredensial,
    PenilaianTindakan,
    form=PenilaianTindakanForm,
    extra=0,
    can_delete=False,
)
