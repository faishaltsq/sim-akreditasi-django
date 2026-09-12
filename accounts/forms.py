from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


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
        fields = ['role', 'full_name', 'jabatan', 'telepon', 'unit_kerja', 'pokja_access', 'is_active_member']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'jabatan': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'telepon': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'unit_kerja': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'pokja_access': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'pokja_access': 'Akses Pokja (untuk Koordinator Pokja)',
        }
        help_texts = {
            'pokja_access': 'Pilih satu atau lebih Pokja yang dapat dikelola pengguna ini.',
        }
