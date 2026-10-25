from django import forms

from sdm.services.impor_pegawai import MAX_WORKBOOK_BYTES


class ImporWorkbookForm(forms.Form):
    workbook = forms.FileField(
        label='Berkas Excel',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.xlsx'}),
        help_text='Format .xlsx, lembar kerja bernama "Staf".',
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput(), max_length=100)

    def clean_workbook(self):
        workbook = self.cleaned_data['workbook']
        if workbook.size > MAX_WORKBOOK_BYTES:
            raise forms.ValidationError(
                f'Ukuran berkas melebihi batas {MAX_WORKBOOK_BYTES} byte.'
            )
        # The extension is only a hint the browser sends. An .xlsx file is a ZIP
        # container, so validate the actual container signature; the deeper
        # OOXML and expansion checks live in preview_staff_import.
        header = workbook.read(4)
        workbook.seek(0)
        if header != b'PK\x03\x04':
            raise forms.ValidationError('Berkas harus berformat .xlsx.')
        return workbook
