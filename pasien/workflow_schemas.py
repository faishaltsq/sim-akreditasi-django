"""Registri skema langkah asesmen per jalur layanan (ADR-1, ADR-9).

Dua bentuk skema hidup di sini dan sengaja berbeda bentuk:

``STEP_SCHEMAS['IGD']``
    Tuple nama field model ``KunjunganPasien``. Bentuk ini yang dipahami
    ``modelform_factory`` dan ``save_step`` jalur IGD. Isinya **identik**
    dengan ``STEPS`` historis; ``pasien.forms_igd_workflow.STEPS`` tetap
    menunjuk objek yang sama sehingga tidak ada satu pun pemanggil lama yang
    berubah perilaku.

``STEP_SCHEMAS['RAJAL_JANTUNG']``
    Spesifikasi deklaratif ``(nama, kind, pilihan/rentang)`` per langkah,
    bukan field model. Nilai langkah rajal disimpan di
    ``IgdAssessmentWorkflow.draft_payload`` (ADR-9) sehingga validasinya
    fungsi murni, bukan ``ModelForm``.

Modul ini tidak boleh mengimpor ``pasien.services.*``: validator mengembalikan
``errors`` dan pemanggil yang melempar ``WorkflowValidation``.
"""
from dataclasses import dataclass, field

VITAL_FIELDS = ('ttv_sistole', 'ttv_diastole', 'ttv_nadi', 'ttv_rr', 'ttv_suhu',
                'ttv_spo2', 'ttv_gcs', 'ttv_skala_nyeri', 'gcs_e', 'gcs_v', 'gcs_m')

#: Skema IGD — byte-identik dengan ``STEPS`` sebelum F1.
IGD_STEPS = {
    1: ('Identitas & Penjamin', ('penjamin',)),
    2: ('Triase & Cara Datang', ('triase_skala', 'triase_kategori', 'triage', 'cara_datang',
        'fisik_airway', 'fisik_breathing', 'fisik_circulation', 'fisik_disability', 'fisik_exposure')),
    3: ('Anamnesis & Riwayat', ('anamnesis_rps', 'anamnesis_rpd', 'anamnesis_rpk', 'anamnesis_obat', 'skrining_alergi_status', 'alergi_asesmen')),
    4: ('Tanda-Tanda Vital', VITAL_FIELDS),
    5: ('Biopsikososial, Spiritual & Skrining', ('status_psikososial', 'status_spiritual',
        'status_emosional', 'hambatan_komunikasi', 'kebutuhan_spiritual', 'skrining_gizi_mst',
        'metode_risiko_jatuh', 'skrining_jatuh_skor', 'skrining_jatuh_grade', 'skrining_jatuh_detail', 'hambatan_edukasi', 'skrining_gizi_detail')),
    6: ('Pemeriksaan Fisik Lengkap', ('keadaan_umum', 'kesadaran', 'fisik_head_to_toe', 'secondary_survey_detail', 'fisik_lokalis', 'penanda_anatomi')),
    7: ('Pemeriksaan Penunjang', ()),
    8: ('Penetapan Diagnosis & Rencana', ('diagnosa_masuk', 'diagnosa_keperawatan_sdki',
        'luaran_keperawatan_slki', 'intervensi_keperawatan_siki', 'diagnosis_mode')),
    9: ('Pelaksanaan Asuhan — CPPT & Billing', ()),
    10: ('Evaluasi Akhir IGD', ('disposisi_kondisi_akhir', 'evaluasi_respon_terapi', *VITAL_FIELDS)),
    11: ('Disposisi & Resume Keluar', ('disposisi_tindak_lanjut', 'disposisi_ruang_rawat',
         'disposisi_kontrol_poli', 'disposisi_kontrol_tgl', 'disposisi_rujuk_rs', 'disposisi_rujuk_alasan',
         'sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation', 'waktu_kematian', 'penyebab_kematian')),
}

RAJAL_JANTUNG_SCHEMA_KEY = 'RAJAL_JANTUNG_V1'

PENJAMIN_CHOICES = ('UMUM', 'BPJS', 'ASURANSI')
JENIS_KUNJUNGAN_KLINIS_CHOICES = ('BARU', 'LAMA', 'KONTROL')
CARA_DATANG_CHOICES = ('SENDIRI', 'AMBULANS', 'RUJUKAN')
KONDISI_AKHIR_CHOICES = ('MEMBAIK', 'SEMBUH', 'RUJUK')


@dataclass(frozen=True)
class StepField:
    """Satu input langkah rajal: nama, bentuk, dan batas nilai."""

    name: str
    kind: str  # 'text' | 'select' | 'number' | 'boolean'
    label: str = ''
    choices: tuple = ()
    minimum: float | None = None
    maximum: float | None = None
    max_length: int = 4000

    def clean(self, value):
        """Return ``(cleaned, error)``; ``error`` is a message or ``None``."""
        if value is None or value == '':
            return None, None
        if self.kind == 'text':
            if not isinstance(value, str):
                return None, 'Nilai harus berupa teks.'
            if len(value) > self.max_length:
                return None, f'Maksimal {self.max_length} karakter.'
            return value.strip(), None
        if self.kind == 'select':
            if value not in self.choices:
                return None, f'Pilihan harus salah satu dari: {", ".join(self.choices)}.'
            return value, None
        if self.kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None, 'Nilai harus berupa angka.'
            if self.minimum is not None and value < self.minimum:
                return None, f'Nilai minimal {self.minimum:g}.'
            if self.maximum is not None and value > self.maximum:
                return None, f'Nilai maksimal {self.maximum:g}.'
            return value, None
        if self.kind == 'boolean':
            if not isinstance(value, bool):
                return None, 'Nilai harus boolean.'
            return value, None
        return None, 'Bentuk field tidak dikenal.'


@dataclass(frozen=True)
class StepSpec:
    """Satu langkah rajal: judul + daftar field yang boleh ditulis."""

    number: int
    title: str
    fields: tuple = field(default_factory=tuple)

    @property
    def field_names(self):
        return tuple(item.name for item in self.fields)

    def validate(self, payload):
        """Return ``(cleaned, errors)``; ``errors`` is ``{field: [message]}``."""
        errors = {}
        cleaned = {}
        by_name = {item.name: item for item in self.fields}
        for name, value in payload.items():
            spec = by_name.get(name)
            if spec is None:
                errors['__all__'] = ['Field tidak dimiliki langkah ini.']
                continue
            value, error = spec.clean(value)
            if error:
                errors.setdefault(name, []).append(error)
            elif value is not None:
                cleaned[name] = value
        return cleaned, errors


def _vital(name, minimum, maximum, label):
    return StepField(name, 'number', label=label, minimum=minimum, maximum=maximum)


#: Kerangka 10 langkah POLI-JANTUNG (F1.3). Kedalaman klinis kardiologi
#: ditambahkan F2/F3/F5/F6/F7 pada langkah yang sama — F1 hanya menetapkan
#: bentuk, nama, dan batas nilai supaya mesin dapat diuji ujung ke ujung.
RAJAL_JANTUNG_STEPS = {
    1: StepSpec(1, 'Registrasi & Penjamin', (
        StepField('penjamin', 'select', label='Penjamin', choices=PENJAMIN_CHOICES),
        StepField('jenis_kunjungan_klinis', 'select', label='Jenis kunjungan klinis', choices=JENIS_KUNJUNGAN_KLINIS_CHOICES),
    )),
    2: StepSpec(2, 'Triase & Cara Datang', (
        StepField('keluhan_utama', 'text', label='Keluhan utama'),
        StepField('cara_datang', 'select', label='Cara datang', choices=CARA_DATANG_CHOICES),
    )),
    3: StepSpec(3, 'Anamnesis & Riwayat', (
        StepField('anamnesis_rps', 'text', label='Riwayat penyakit sekarang'),
    )),
    4: StepSpec(4, 'Tanda-Tanda Vital', (
        _vital('ttv_sistole', 0, 350, 'Sistole'),
        _vital('ttv_diastole', 0, 250, 'Diastole'),
        _vital('ttv_nadi', 0, 350, 'Nadi'),
        _vital('ttv_rr', 0, 150, 'Laju napas'),
        _vital('ttv_suhu', 20, 45, 'Suhu'),
        _vital('ttv_spo2', 0, 100, 'SpO2'),
        _vital('ttv_skala_nyeri', 0, 10, 'Skala nyeri'),
    )),
    5: StepSpec(5, 'Skrining Gizi & Jatuh', (
        _vital('skrining_gizi_mst', 0, 5, 'Skor MST'),
        _vital('skrining_jatuh_skor', 0, 125, 'Skor Morse'),
    )),
    6: StepSpec(6, 'Pemeriksaan Fisik', (
        StepField('keadaan_umum', 'text', label='Keadaan umum'),
        StepField('fisik_lokalis', 'text', label='Pemeriksaan fisik lokalis'),
    )),
    7: StepSpec(7, 'Pemeriksaan Penunjang', (
        StepField('penunjang_catatan', 'text', label='Catatan penunjang'),
    )),
    8: StepSpec(8, 'Penetapan Diagnosis & Rencana', (
        StepField('diagnosa_utama', 'text', label='Diagnosis utama'),
        StepField('rencana_terapi', 'text', label='Rencana terapi'),
    )),
    9: StepSpec(9, 'Pelaksanaan Asuhan — CPPT & Billing', (
        StepField('cppt_ringkas', 'text', label='Ringkasan asuhan'),
    )),
    10: StepSpec(10, 'Evaluasi Akhir & Kondisi Pulang', (
        StepField('kondisi_akhir_rajal', 'select', label='Kondisi akhir', choices=KONDISI_AKHIR_CHOICES),
        StepField('evaluasi_respon_terapi', 'text', label='Evaluasi respons terapi'),
    )),
}

STEP_SCHEMAS = {
    'IGD': IGD_STEPS,
    'RAJAL_JANTUNG': RAJAL_JANTUNG_STEPS,
}

RAJAL_JANTUNG_STEP_NUMBERS = tuple(sorted(RAJAL_JANTUNG_STEPS))
