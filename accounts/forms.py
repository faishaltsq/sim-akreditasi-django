from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, NakesCredential


class UserCreateForm(UserCreationForm):
    first_name = forms.CharField(label='Nama Depan', max_length=100, required=False)
    last_name = forms.CharField(label='Nama Belakang', max_length=100, required=False)
    email = forms.EmailField(label='Email', required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control form-control-sm'


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'role', 'full_name', 'jabatan', 'nip_nrp', 'profesi',
            'telepon', 'unit_kerja', 'pokja_access', 'is_active_member',
        ]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'jabatan': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'nip_nrp': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Contoh: 198801012010011001'}),
            'profesi': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'telepon': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'unit_kerja': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'pokja_access': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'pokja_access': 'Akses Pokja (untuk Koordinator Pokja)',
            'nip_nrp': 'NIP / NRP / No. Pegawai',
            'profesi': 'Profesi Klinis (untuk Staf Nakes)',
        }
        help_texts = {
            'pokja_access': 'Pilih satu atau lebih Pokja yang dapat dikelola pengguna ini.',
            'profesi': 'Wajib diisi jika role adalah Staf Nakes.',
            'unit_kerja': 'Wajib diisi untuk role Staf Nakes dan Kepala Unit.',
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        unit_kerja = cleaned_data.get('unit_kerja')
        profesi = cleaned_data.get('profesi')

        if role in ('STAF_NAKES', 'KEPALA_UNIT') and not unit_kerja:
            self.add_error('unit_kerja', 'Unit Kerja wajib diisi untuk role ini.')
        if role == 'STAF_NAKES' and not profesi:
            self.add_error('profesi', 'Profesi wajib diisi untuk Staf Nakes.')
        return cleaned_data


class NakesCredentialForm(forms.ModelForm):
    """Form upload mandiri dokumen kredensial nakes (STR, SIP, sertifikat pelatihan)."""

    class Meta:
        model = NakesCredential
        fields = ['doc_type', 'title', 'document_number', 'issued_date', 'valid_until', 'file']
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Contoh: STR Perawat atas nama Ns. Budi, S.Kep',
            }),
            'document_number': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Nomor STR / SIP / Sertifikat',
            }),
            'issued_date': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date',
            }),
            'valid_until': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date',
            }),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'}),
        }
        labels = {
            'doc_type': 'Jenis Dokumen KPS',
            'title': 'Nama / Judul Dokumen',
            'document_number': 'Nomor Dokumen / Sertifikat',
            'issued_date': 'Tanggal Terbit / Pelaksanaan',
            'valid_until': 'Masa Berlaku Sampai',
            'file': 'Unggah Scan / Foto Dokumen (PDF/JPG)',
        }
        help_texts = {
            'valid_until': 'Kosongkan jika tidak ada masa kedaluwarsa.',
            'file': 'Format: PDF, JPG, PNG. Maks. 10 MB.',
        }


class CredentialVerifyForm(forms.ModelForm):
    """Form verifikasi kredensial oleh Admin RS atau Kepala Unit."""

    class Meta:
        model = NakesCredential
        fields = ['status', 'verification_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'verification_notes': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
                'placeholder': 'Catatan verifikasi (opsional)',
            }),
        }
