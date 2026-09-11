from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from .models import StandardItem, QualityRecord, EvidenceReq, UnitKerja, EvidenceFile


class UnitKerjaForm(forms.ModelForm):
    class Meta:
        model = UnitKerja
        fields = ['name', 'code', 'pic_name']
        labels = {
            'name': 'Nama Unit Kerja',
            'code': 'Kode Unit',
            'pic_name': 'Penanggung Jawab (PIC)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('code', css_class='col-md-3'),
                Column('pic_name', css_class='col-md-3'),
            ),
            Submit('submit', 'Simpan Unit Kerja', css_class='btn btn-primary mt-2'),
        )


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
