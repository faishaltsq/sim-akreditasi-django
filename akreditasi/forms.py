from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from .models import StandardItem, QualityRecord, EvidenceReq, UnitKerja, EvidenceFile


LEVEL_CHOICES = [
    (1, 'Level 1 — Puncak (Direktur Utama / Dewan Pengawas / Pemilik)'),
    (2, 'Level 2 — Direktorat / Bidang / Komite RS / SPI'),
    (3, 'Level 3 — Instalasi / KSM / Ruangan Pelayanan'),
    (4, 'Level 4 — Sub-Instalasi / Poliklinik / Ruang Khusus'),
    (5, 'Level 5 — Depo / Satelit / Pos Jaga / Tim'),
]


class UnitKerjaForm(forms.ModelForm):
    level = forms.TypedChoiceField(
        choices=LEVEL_CHOICES,
        coerce=int,
        required=False,
        label='Tingkat Hierarki (Level)',
        help_text='Otomatis menyesuaikan jika memilih Induk Unit, atau pilih langsung jika tanpa induk.',
        widget=forms.Select(attrs={'class': 'form-select font-mono fw-bold', 'id': 'id_level'})
    )

    class Meta:
        model = UnitKerja
        fields = ['name', 'code', 'level', 'parent', 'tipe_unit', 'pic_name', 'description']
        labels = {
            'name': 'Nama Unit Kerja',
            'code': 'Kode Unit (Singkatan)',
            'level': 'Tingkat Hierarki (Level)',
            'parent': 'Induk Unit Kerja (Parent)',
            'tipe_unit': 'Kategori / Tipe Unit',
            'pic_name': 'Penanggung Jawab (PIC)',
            'description': 'Keterangan / Fungsi',
        }
        help_texts = {
            'parent': 'Pilih unit induk di atasnya (contoh: untuk membuat Level 2, pilih Induk Level 1 seperti Direktur Utama atau Direktorat). Kosongkan jika unit independen.',
            'code': 'Gunakan huruf kapital dan tanda hubung unik, contoh: DIR-MED, HUMAS-CS, SUB-PKRS',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Bagian PKRS & Promosi Kesehatan RS'}),
            'code': forms.TextInput(attrs={'class': 'form-control font-mono text-uppercase', 'placeholder': 'Contoh: SUB-PKRS', 'style': 'text-transform: uppercase;'}),
            'parent': forms.Select(attrs={'class': 'form-select', 'id': 'id_parent'}),
            'tipe_unit': forms.Select(attrs={'class': 'form-select'}),
            'pic_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Penanggung Jawab / Kepala Unit'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Deskripsi tugas/fungsi unit kerja...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = UnitKerja.objects.order_by('level', 'code')
        if self.instance and self.instance.pk:
            self.fields['level'].initial = self.instance.level
        elif 'initial' in kwargs and 'parent' in kwargs['initial']:
            parent_obj = kwargs['initial']['parent']
            if parent_obj:
                self.fields['level'].initial = parent_obj.level + 1
        elif not self.fields['level'].initial:
            self.fields['level'].initial = 1

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get('parent')
        level_input = cleaned_data.get('level')
        if parent:
            cleaned_data['level'] = parent.level + 1
        elif level_input:
            cleaned_data['level'] = int(level_input)
        else:
            cleaned_data['level'] = 1
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        parent = self.cleaned_data.get('parent')
        level = self.cleaned_data.get('level')
        if parent:
            instance.level = parent.level + 1
        elif level:
            instance.level = int(level)
        else:
            instance.level = 1
        if commit:
            instance.save()
        return instance


class StandardItemForm(forms.ModelForm):
    class Meta:
        model = StandardItem
        fields = ['category', 'sub_standard', 'sub_title', 'code', 'description', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('category', css_class='col-md-4'),
                Column('sub_standard', css_class='col-md-4'),
                Column('code', css_class='col-md-4'),
            ),
            Row(
                Column('sub_title', css_class='col-md-9'),
                Column('order', css_class='col-md-3'),
            ),
            'description',
        )


class QualityRecordForm(forms.ModelForm):
    class Meta:
        model = QualityRecord
        fields = [
            'unit', 'baseline_data', 'quality_target', 'risk_mitigation',
            'score', 'eval_notes', 'action_plan', 'pic', 'target_date',
            'est_cost', 'budget_source', 'budget_status',
        ]
        widgets = {
            'baseline_data': forms.Textarea(attrs={'rows': 2}),
            'risk_mitigation': forms.Textarea(attrs={'rows': 2}),
            'eval_notes': forms.Textarea(attrs={'rows': 2}),
            'action_plan': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            HTML('<hr><h6 class="text-muted fw-bold text-uppercase small mb-3"><i class="bi bi-layers me-1"></i> I. Identitas & Baseline Kondisi Riil</h6>'),
            Row(
                Column('unit', css_class='col-md-6'),
            ),
            'baseline_data',
            HTML('<hr><h6 class="text-muted fw-bold text-uppercase small mb-3"><i class="bi bi-graph-up me-1"></i> II. Siklus PLAN: Indikator Mutu & Mitigasi Risiko</h6>'),
            'quality_target',
            'risk_mitigation',
            HTML('<hr><h6 class="text-muted fw-bold text-uppercase small mb-3"><i class="bi bi-check2-circle me-1"></i> III. Siklus CHECK: Evaluasi & Self-Assessment Score</h6>'),
            Row(
                Column('score', css_class='col-md-4'),
            ),
            'eval_notes',
            HTML('<hr><h6 class="text-muted fw-bold text-uppercase small mb-3"><i class="bi bi-coin me-1"></i> IV. Siklus ACTION: Rencana Tindak Lanjut & Anggaran RKA</h6>'),
            'action_plan',
            Row(
                Column('pic', css_class='col-md-6'),
                Column('target_date', css_class='col-md-6'),
            ),
            Row(
                Column('est_cost', css_class='col-md-4'),
                Column('budget_source', css_class='col-md-4'),
                Column('budget_status', css_class='col-md-4'),
            ),
        )


class EvidenceFileUploadForm(forms.ModelForm):
    class Meta:
        model = EvidenceFile
        fields = ['file']
        labels = {'file': 'Pilih Berkas (PDF/DOCX/JPG)'}
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.xlsx,.xls'}),
        }
