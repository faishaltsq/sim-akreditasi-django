"""Formulir per langkah: hanya field yang dimiliki langkah itu yang boleh ditulis."""
from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelform_factory

from .models import KunjunganPasien
from .anatomy_markers import validate_markers
from .triage import validate_triage
from .workflow_schemas import STEP_SCHEMAS, VITAL_FIELDS

#: Skema langkah IGD. Nama lama dipertahankan karena dipakai view, layanan,
#: dan suite regresi IGD; objeknya identik dengan ``STEP_SCHEMAS['IGD']``.
STEPS = STEP_SCHEMAS['IGD']

LEGACY_STEP8_FIELDS = ('tatalaksana_resusitasi', 'tatalaksana_terapi')
# Field pensiun: tetap disimpan, tetap masuk snapshot, tidak lagi ditulis lewat draft.
LEGACY_STEP7_FIELDS = ('penunjang_ekg', 'penunjang_hasil_kritis')


def snapshot_visit_fields():
    return sorted({name for _, names in STEPS.values() for name in names}
                  | set(LEGACY_STEP8_FIELDS) | set(LEGACY_STEP7_FIELDS))


BOUNDS = {
    'ttv_sistole': (0, 350), 'ttv_diastole': (0, 250), 'ttv_nadi': (0, 350),
    'ttv_rr': (0, 150), 'ttv_suhu': (20, 45), 'ttv_spo2': (0, 100),
    'ttv_skala_nyeri': (0, 10), 'gcs_e': (1, 4), 'gcs_v': (1, 5), 'gcs_m': (1, 6),
    'skrining_gizi_mst': (0, 5),
}

#: Bobot butir Morse Fall Scale. Satu-satunya sumbernya: form IGD sudah memakai
#: tabel ini sejak sebelum F2, dan jalur rajal mengimpor objek yang sama supaya
#: tidak ada dua tabel bobot yang dapat berbeda pendapat.
MORSE_WEIGHTS = {
    'jatuh_riwayat': (0, 25), 'jatuh_diagnosis': (0, 15),
    'jatuh_alat': (0, 15, 30), 'jatuh_infus': (0, 20),
    'jatuh_jalan': (0, 10, 20), 'jatuh_mental': (0, 15),
}
#: Ambang grade Morse — sudah ada di kode IGD (``StepForm.clean``) dan dipakai
#: ulang apa adanya; tidak ada angka baru di F2.
MORSE_TINGGI_MIN = 45
MORSE_SEDANG_MIN = 25
#: Jawaban MST: ``berat_badan`` 0..4, ``nafsu_makan`` 0..1.
MST_CHOICES = {'berat_badan': range(5), 'nafsu_makan': (0, 1)}
#: Ambang "berisiko" MST. **Bukan angka baru dari F2**: tiga template yang sudah
#: ada memakai ``skrining_gizi_mst >= 2`` sebagai batas risiko
#: (``_asesmen_awal_wizard.html:213``, ``igd_dashboard.html:1714``,
#: ``kunjungan_detail.html:232``). F2 memakai ulang konvensi itu supaya dua
#: layar tidak memberi verdict berbeda untuk skor yang sama. Sumber memang tidak
#: menetapkan angkanya (AMBIGU-08), jadi bila Komite Keperawatan menetapkan lain,
#: ubah konstanta ini **dan** ketiga template tersebut dalam satu perubahan.
MST_BERISIKO_MIN = 2


def morse_score(detail):
    """``(skor, grade)`` dari jawaban Morse, atau ``(None, '')`` bila tidak lengkap.

    Ambang grade memakai ``MORSE_TINGGI_MIN``/``MORSE_SEDANG_MIN`` yang sudah
    berlaku di jalur IGD — F2 tidak menetapkan angka baru.
    """
    if not isinstance(detail, dict) or set(detail) != set(MORSE_WEIGHTS):
        return None, ''
    score = sum(detail.values())
    if score >= MORSE_TINGGI_MIN:
        return score, 'TINGGI'
    if score >= MORSE_SEDANG_MIN:
        return score, 'SEDANG'
    return score, 'RENDAH'


def mst_score(detail):
    """``(skor, berisiko)``; ``(None, None)`` bila jawaban tidak lengkap."""
    if not isinstance(detail, dict) or set(detail) != set(MST_CHOICES):
        return None, None
    score = detail['berat_badan'] + detail['nafsu_makan']
    return score, score >= MST_BERISIKO_MIN


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
            markers, marker_error = validate_markers(markers)
            if marker_error:
                self.add_error('penanda_anatomi', marker_error)
            else:
                cleaned['penanda_anatomi'] = markers
        morse = cleaned.get('skrining_jatuh_detail')
        weights = MORSE_WEIGHTS
        if morse:
            if set(morse) - set(weights) or any(type(value) is not int or value not in weights[key] for key,value in morse.items() if key in weights):
                self.add_error('skrining_jatuh_detail', 'Jawaban Morse tidak valid.')
            elif set(morse) == set(weights):
                score, grade = morse_score(morse)
                cleaned.update(skrining_jatuh_skor=score, skrining_jatuh_grade=grade, metode_risiko_jatuh='Morse Fall Scale')
            else:
                cleaned.update(skrining_jatuh_skor=None, skrining_jatuh_grade='', metode_risiko_jatuh='Morse Fall Scale')
        mst = cleaned.get('skrining_gizi_detail')
        if mst:
            choices = MST_CHOICES
            if set(mst) - set(choices) or any(type(value) is not int or value not in choices[key] for key,value in mst.items() if key in choices):
                self.add_error('skrining_gizi_detail', 'Jawaban MST tidak valid.')
            elif set(mst) == set(choices):
                cleaned['skrining_gizi_mst'] = mst_score(mst)[0]
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
