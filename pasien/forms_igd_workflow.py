"""Formulir per langkah: hanya field yang dimiliki langkah itu yang boleh ditulis."""
import math
from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelform_factory

from .models import KunjunganPasien
from .triage import validate_triage

VITAL_FIELDS = ('ttv_sistole', 'ttv_diastole', 'ttv_nadi', 'ttv_rr', 'ttv_suhu',
                'ttv_spo2', 'ttv_gcs', 'ttv_skala_nyeri', 'gcs_e', 'gcs_v', 'gcs_m')
STEPS = {
    1: ('Identitas & Penjamin', ('penjamin',)),
    2: ('Triase & Cara Datang', ('triase_skala', 'triase_kategori', 'triage', 'cara_datang',
        'fisik_airway', 'fisik_breathing', 'fisik_circulation', 'fisik_disability', 'fisik_exposure')),
    3: ('Anamnesis & Riwayat', ('anamnesis_rps', 'anamnesis_rpd', 'anamnesis_rpk', 'anamnesis_obat', 'skrining_alergi_status', 'alergi_asesmen')),
    4: ('Tanda-Tanda Vital', VITAL_FIELDS),
    5: ('Biopsikososial, Spiritual & Skrining', ('status_psikososial', 'status_spiritual',
        'status_emosional', 'hambatan_komunikasi', 'kebutuhan_spiritual', 'skrining_gizi_mst',
        'metode_risiko_jatuh', 'skrining_jatuh_skor', 'skrining_jatuh_grade', 'skrining_jatuh_detail', 'hambatan_edukasi', 'skrining_gizi_detail')),
    6: ('Pemeriksaan Fisik Lengkap', ('keadaan_umum', 'kesadaran', 'fisik_head_to_toe', 'secondary_survey_detail', 'fisik_lokalis', 'penanda_anatomi')),
    7: ('Pemeriksaan Penunjang — Order & Hasil', ('penunjang_ekg', 'penunjang_hasil_kritis')),
    8: ('Penetapan Diagnosis & Rencana', ('diagnosa_masuk', 'diagnosa_keperawatan_sdki',
        'luaran_keperawatan_slki', 'intervensi_keperawatan_siki', 'tatalaksana_resusitasi', 'tatalaksana_terapi', 'diagnosis_mode')),
    9: ('Pelaksanaan Asuhan — CPPT & Billing', ()),
    10: ('Evaluasi Akhir IGD', ('disposisi_kondisi_akhir', 'evaluasi_respon_terapi', *VITAL_FIELDS)),
    11: ('Disposisi & Resume Keluar', ('disposisi_tindak_lanjut', 'disposisi_ruang_rawat',
         'disposisi_kontrol_poli', 'disposisi_kontrol_tgl', 'disposisi_rujuk_rs', 'disposisi_rujuk_alasan',
         'sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation', 'waktu_kematian', 'penyebab_kematian')),
}

BOUNDS = {
    'ttv_sistole': (0, 350), 'ttv_diastole': (0, 250), 'ttv_nadi': (0, 350),
    'ttv_rr': (0, 150), 'ttv_suhu': (20, 45), 'ttv_spo2': (0, 100),
    'ttv_skala_nyeri': (0, 10), 'gcs_e': (1, 4), 'gcs_v': (1, 5), 'gcs_m': (1, 6),
    'skrining_gizi_mst': (0, 5),
}


class StepForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_triage_category = self.instance.triase_kategori
        from .physical_exam import GENERAL_CHOICES
        for name, choices in GENERAL_CHOICES.items():
            if name in self.fields:
                original = getattr(self.instance,name) or ''
                options = [('', 'Belum dikaji')] + [(value,value) for value in choices]
                if original and original not in choices:
                    options.append((original,'Historis: '+original))
                self.fields[name] = forms.ChoiceField(choices=options,required=False,label=self.fields[name].label)
        for name, field in self.fields.items():
            field.required = False
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3
            if name in BOUNDS:
                field.min_value, field.max_value = BOUNDS[name]
                field.widget.attrs.update(min=field.min_value, max=field.max_value)

    def clean(self):
        cleaned = super().clean()
        if 'secondary_survey_detail' in self.fields and 'secondary_survey_detail' in cleaned and 'fisik_head_to_toe' in cleaned:
            from .physical_exam import prepare_exam
            try:
                cleaned['secondary_survey_detail'],cleaned['fisik_head_to_toe'] = prepare_exam(
                    self.instance.secondary_survey_detail or {},self.instance.fisik_head_to_toe or {},
                    cleaned['secondary_survey_detail'] or {},cleaned['fisik_head_to_toe'] or {})
            except ValidationError as exc:
                self.add_error('secondary_survey_detail',exc)
        for name, (minimum, maximum) in BOUNDS.items():
            value = cleaned.get(name)
            if value is not None and not minimum <= value <= maximum:
                self.add_error(name, f'Nilai harus antara {minimum} dan {maximum}.')
        for name in ('fisik_head_to_toe', 'secondary_survey_detail', 'skrining_jatuh_detail', 'skrining_gizi_detail'):
            if name in cleaned:
                if cleaned[name] is None:
                    cleaned[name] = {}
                elif not isinstance(cleaned[name], dict):
                    self.add_error(name, 'Isi harus berupa objek JSON.')
        markers = cleaned.get('penanda_anatomi')
        if 'penanda_anatomi' in cleaned:
            if markers is None:
                cleaned['penanda_anatomi'] = []
            elif not isinstance(markers, list) or len(markers) > 100:
                self.add_error('penanda_anatomi', 'Maksimal 100 penanda dalam daftar.')
            else:
                for marker in markers:
                    valid = (isinstance(marker, dict) and set(marker) == {'side','x','y','label','kind'}
                             and marker.get('side') in ('FRONT','BACK') and marker.get('kind') in ('LUKA','NYERI','LAINNYA')
                             and isinstance(marker.get('label'), str) and 0 < len(marker['label']) <= 200)
                    if valid:
                        valid = all(type(marker.get(k)) in (int,float) and math.isfinite(marker[k]) and 0 <= marker[k] <= 1 for k in ('x','y'))
                    if not valid:
                        self.add_error('penanda_anatomi', 'Koordinat/label penanda tidak valid.')
                        break
        morse = cleaned.get('skrining_jatuh_detail')
        weights = {'jatuh_riwayat':(0,25),'jatuh_diagnosis':(0,15),'jatuh_alat':(0,15,30),'jatuh_infus':(0,20),'jatuh_jalan':(0,10,20),'jatuh_mental':(0,15)}
        if morse:
            if set(morse) - set(weights) or any(type(value) is not int or value not in weights[key] for key,value in morse.items() if key in weights):
                self.add_error('skrining_jatuh_detail', 'Jawaban Morse tidak valid.')
            elif set(morse) == set(weights):
                score = sum(morse.values())
                cleaned.update(skrining_jatuh_skor=score, skrining_jatuh_grade='TINGGI' if score >= 45 else 'SEDANG' if score >= 25 else 'RENDAH', metode_risiko_jatuh='Morse Fall Scale')
            else:
                cleaned.update(skrining_jatuh_skor=None, skrining_jatuh_grade='', metode_risiko_jatuh='Morse Fall Scale')
        mst = cleaned.get('skrining_gizi_detail')
        if mst:
            choices = {'berat_badan':range(5),'nafsu_makan':(0,1)}
            if set(mst) - set(choices) or any(type(value) is not int or value not in choices[key] for key,value in mst.items() if key in choices):
                self.add_error('skrining_gizi_detail', 'Jawaban MST tidak valid.')
            elif set(mst) == set(choices):
                cleaned['skrining_gizi_mst'] = mst['berat_badan'] + mst['nafsu_makan']
            else:
                cleaned['skrining_gizi_mst'] = None
        components = [cleaned.get(name) for name in ('gcs_e','gcs_v','gcs_m')]
        if all(value is not None for value in components):
            cleaned['ttv_gcs'] = str(sum(components))
        if 'triase_skala' in cleaned:
            if (cleaned.get('triase_kategori') and not cleaned.get('triase_skala')
                    and cleaned['triase_kategori'] != self.original_triage_category):
                self.add_error('triase_skala', 'Pilih ATS atau ESI untuk kategori baru; jangan menebak sistem historis.')
            try:
                validate_triage(cleaned)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        return cleaned


def form_for_step(step, *, instance, data=None):
    if step not in STEPS:
        raise ValueError('Langkah tidak valid.')
    form_class = modelform_factory(KunjunganPasien, form=StepForm, fields=STEPS[step][1])
    return form_class(data=data, instance=instance, auto_id=f'igd_{step}_%s')
