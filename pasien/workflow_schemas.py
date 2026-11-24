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

# ── Pilihan Lapis 1 langkah 1–6 (matriks S1-L1..S6-L1, verbatim) ─────────────
# Nilai disimpan sebagai kode pendek; label Indonesia ada di ``*_LABELS`` dan
# dirender template. Kode, bukan label, supaya laporan/indikator tidak patah
# saat redaksi label berubah.

ASAL_RUJUKAN_CHOICES = ('FKTP', 'IGD', 'RANAP_ANTAR_POLI', 'RS_LAIN', 'SENDIRI')
ASAL_RUJUKAN_LABELS = {
    'FKTP': 'FKTP / Puskesmas',
    'IGD': 'IGD',
    'RANAP_ANTAR_POLI': 'Rawat Inap / Antar-Poli',
    'RS_LAIN': 'Rujukan RS Lain',
    'SENDIRI': 'Datang Sendiri',
}

STATUS_RUJUKAN_CHOICES = ('AKTIF_TERVERIFIKASI', 'PRB', 'PERLU_VERIFIKASI', 'TIDAK_BERLAKU')
STATUS_RUJUKAN_LABELS = {
    'AKTIF_TERVERIFIKASI': 'Aktif & Terverifikasi',
    'PRB': 'Program Rujuk Balik (PRB)',
    'PERLU_VERIFIKASI': 'Perlu Verifikasi Petugas',
    'TIDAK_BERLAKU': 'Tidak Berlaku (Umum/Tunai)',
}

MOBILITAS_DATANG_CHOICES = ('JALAN', 'KURSI_RODA', 'BRANKAR')
MOBILITAS_DATANG_LABELS = {
    'JALAN': 'Jalan Kaki Mandiri',
    'KURSI_RODA': 'Kursi Roda',
    'BRANKAR': 'Brankar / Dibantu Petugas',
}

#: Red flag kardiovaskular (S2-L1-02). Kode ``ANGINA`` dan ``SESAK_BERAT``
#: memulai jam door-to-ECG <= 10 menit; dua lainnya tidak (matriks §7).
RED_FLAG_CHOICES = ('ANGINA', 'SESAK_BERAT', 'SINKOP', 'PALPITASI_INSTABIL')
RED_FLAG_LABELS = {
    'ANGINA': 'Nyeri Dada Khas Angina (Suspek SKA)',
    'SESAK_BERAT': 'Sesak Napas Berat / Orthopnea / Edema Paru',
    'SINKOP': 'Sinkop / Presinkop',
    'PALPITASI_INSTABIL': 'Palpitasi dengan Hemodinamik Tidak Stabil',
}
#: Red flag yang memicu indikator door-to-ECG (matriks §7).
RED_FLAG_DOOR_TO_ECG = ('ANGINA', 'SESAK_BERAT')

ALUR_AWAL_CHOICES = ('LANJUT_POLI', 'RUJUK_IGD_CITO')
ALUR_AWAL_LABELS = {
    'LANJUT_POLI': 'Lanjut Pemeriksaan Poli Jantung',
    'RUJUK_IGD_CITO': 'Rujuk Segera ke IGD (Cito)',
}

KELUHAN_UTAMA_CHOICES = ('NYERI_DADA', 'SESAK', 'PALPITASI', 'CEPAT_LELAH', 'EDEMA', 'PUSING', 'KONTROL')
KELUHAN_UTAMA_LABELS = {
    'NYERI_DADA': 'Nyeri Dada',
    'SESAK': 'Sesak Napas (Dispnea)',
    'PALPITASI': 'Berdebar-debar (Palpitasi)',
    'CEPAT_LELAH': 'Cepat Lelah / Penurunan Toleransi Aktivitas',
    'EDEMA': 'Bengkak pada Tungkai (Edema)',
    'PUSING': 'Pusing / Hampir Pingsan',
    'KONTROL': 'Kontrol Rutin / Evaluasi Hasil',
}

NYERI_KARAKTERISTIK_CHOICES = ('TIDAK_ADA', 'TERTEKAN', 'TERBAKAR', 'TAJAM', 'TIDAK_NYAMAN')
NYERI_KARAKTERISTIK_LABELS = {
    'TIDAK_ADA': 'Tidak Ada Nyeri Dada',
    'TERTEKAN': 'Terasa Ditekan / Ditindih / Terikat (Tipikal)',
    'TERBAKAR': 'Terasa Terbakar / Panas',
    'TAJAM': 'Nyeri Tajam / Tertusuk',
    'TIDAK_NYAMAN': 'Rasa Tidak Nyaman / Pegal',
}

NYERI_PENJALARAN_CHOICES = ('TIDAK', 'LENGAN_KIRI', 'KEDUA_LENGAN', 'RAHANG_LEHER', 'PUNGGUNG_ULU_HATI')
NYERI_PENJALARAN_LABELS = {
    'TIDAK': 'Tidak Menjalar',
    'LENGAN_KIRI': 'Ke Lengan Kiri',
    'KEDUA_LENGAN': 'Ke Kedua Lengan',
    'RAHANG_LEHER': 'Ke Rahang / Leher',
    'PUNGGUNG_ULU_HATI': 'Ke Punggung / Ulu Hati',
}

IRAMA_NADI_CHOICES = ('REGULER', 'IREGULER', 'SULIT_DINILAI')
IRAMA_NADI_LABELS = {
    'REGULER': 'Teratur (Reguler)',
    'IREGULER': 'Tidak Teratur (Ireguler)',
    'SULIT_DINILAI': 'Sulit Dinilai',
}

STATUS_FUNGSIONAL_CHOICES = ('MANDIRI', 'KETERGANTUNGAN_RINGAN', 'KETERGANTUNGAN_SEDANG_BERAT')
STATUS_FUNGSIONAL_LABELS = {
    'MANDIRI': 'Mandiri',
    'KETERGANTUNGAN_RINGAN': 'Ketergantungan Ringan',
    'KETERGANTUNGAN_SEDANG_BERAT': 'Ketergantungan Sedang/Berat',
}

DUKUNGAN_SOSIAL_CHOICES = ('BAIK', 'TERBATAS', 'TANPA_PENDAMPING')
DUKUNGAN_SOSIAL_LABELS = {
    'BAIK': 'Dukungan Keluarga Baik',
    'TERBATAS': 'Dukungan Terbatas',
    'TANPA_PENDAMPING': 'Tinggal Sendiri / Tanpa Pendamping',
}

IKTUS_KORDIS_CHOICES = ('NORMAL', 'BERGESER', 'TIDAK_TERABA')
IKTUS_KORDIS_LABELS = {
    'NORMAL': 'Iktus Kordis Normal (ICS V LMC Sinistra)',
    'BERGESER': 'Bergeser ke Lateral/Kaudo-Lateral (Kardiomegali)',
    'TIDAK_TERABA': 'Tidak Teraba / Heaving',
}

BUNYI_JANTUNG_CHOICES = ('REGULER_TANPA_TAMBAHAN', 'REGULER_MURMUR', 'REGULER_GALLOP', 'IREGULER')
BUNYI_JANTUNG_LABELS = {
    'REGULER_TANPA_TAMBAHAN': 'BJ I–II Reguler, Murmur (-), Gallop (-)',
    'REGULER_MURMUR': 'BJ I–II Reguler dengan Murmur',
    'REGULER_GALLOP': 'BJ I–II Reguler dengan Gallop (S3/S4)',
    'IREGULER': 'Irama Ireguler',
}

BUNYI_NAPAS_CHOICES = ('VESIKULER', 'RONKI_BASAL', 'RONKI_LUAS', 'WHEEZING')
BUNYI_NAPAS_LABELS = {
    'VESIKULER': 'Vesikuler Normal Kanan/Kiri',
    'RONKI_BASAL': 'Ronki Basah Halus Basal (Rales)',
    'RONKI_LUAS': 'Ronki Basah Luas',
    'WHEEZING': 'Wheezing / Lainnya',
}

#: Pemetaan kode → label untuk seluruh langkah; dipakai template dan API draft
#: supaya nilai mentah tidak pernah tampil sebagai kode di layar.
STEP_LABELS = {
    'asal_rujukan': ASAL_RUJUKAN_LABELS,
    'status_rujukan': STATUS_RUJUKAN_LABELS,
    'mobilitas_datang': MOBILITAS_DATANG_LABELS,
    'red_flag_kardio': RED_FLAG_LABELS,
    'alur_awal': ALUR_AWAL_LABELS,
    'keluhan_utama_kardio': KELUHAN_UTAMA_LABELS,
    'nyeri_karakteristik_kardio': NYERI_KARAKTERISTIK_LABELS,
    'nyeri_penjalaran': NYERI_PENJALARAN_LABELS,
    'irama_nadi': IRAMA_NADI_LABELS,
    'status_fungsional': STATUS_FUNGSIONAL_LABELS,
    'dukungan_sosial': DUKUNGAN_SOSIAL_LABELS,
    'iktus_kordis': IKTUS_KORDIS_LABELS,
    'bunyi_jantung': BUNYI_JANTUNG_LABELS,
    'bunyi_napas': BUNYI_NAPAS_LABELS,
}


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
        StepField('asal_rujukan', 'select', label='Asal rujukan', choices=ASAL_RUJUKAN_CHOICES),
        StepField('status_rujukan', 'select', label='Status rujukan / SEP', choices=STATUS_RUJUKAN_CHOICES),
    )),
    2: StepSpec(2, 'Triase & Cara Datang', (
        StepField('keluhan_utama', 'text', label='Keluhan utama'),
        StepField('cara_datang', 'select', label='Cara datang', choices=CARA_DATANG_CHOICES),
        StepField('mobilitas_datang', 'select', label='Mobilitas datang', choices=MOBILITAS_DATANG_CHOICES),
        StepField('red_flag_kardio', 'select', label='Red flag kardiovaskular', choices=RED_FLAG_CHOICES),
        StepField('alur_awal', 'select', label='Keputusan alur awal', choices=ALUR_AWAL_CHOICES),
    )),
    3: StepSpec(3, 'Anamnesis & Riwayat', (
        StepField('anamnesis_rps', 'text', label='Riwayat penyakit sekarang'),
        StepField('keluhan_utama_kardio', 'select', label='Keluhan utama kardiovaskular', choices=KELUHAN_UTAMA_CHOICES),
        StepField('nyeri_karakteristik_kardio', 'select', label='Karakteristik nyeri dada', choices=NYERI_KARAKTERISTIK_CHOICES),
        StepField('nyeri_penjalaran', 'select', label='Penjalaran nyeri', choices=NYERI_PENJALARAN_CHOICES),
    )),
    4: StepSpec(4, 'Tanda-Tanda Vital', (
        _vital('ttv_sistole', 0, 350, 'Sistole'),
        _vital('ttv_diastole', 0, 250, 'Diastole'),
        _vital('ttv_nadi', 0, 350, 'Nadi'),
        _vital('ttv_rr', 0, 150, 'Laju napas'),
        _vital('ttv_suhu', 20, 45, 'Suhu'),
        _vital('ttv_spo2', 0, 100, 'SpO2'),
        _vital('ttv_skala_nyeri', 0, 10, 'Skala nyeri'),
        StepField('irama_nadi', 'select', label='Irama nadi', choices=IRAMA_NADI_CHOICES),
        _vital('berat_badan', 1, 400, 'Berat badan (kg)'),
        _vital('tinggi_badan', 30, 250, 'Tinggi badan (cm)'),
    )),
    5: StepSpec(5, 'Skrining Gizi & Jatuh', (
        _vital('skrining_gizi_mst', 0, 5, 'Skor MST'),
        _vital('skrining_jatuh_skor', 0, 125, 'Skor Morse'),
        StepField('status_fungsional', 'select', label='Status fungsional', choices=STATUS_FUNGSIONAL_CHOICES),
        StepField('dukungan_sosial', 'select', label='Dukungan sosial & keluarga', choices=DUKUNGAN_SOSIAL_CHOICES),
    )),
    6: StepSpec(6, 'Pemeriksaan Fisik', (
        StepField('keadaan_umum', 'text', label='Keadaan umum'),
        StepField('fisik_lokalis', 'text', label='Pemeriksaan fisik lokalis'),
        StepField('iktus_kordis', 'select', label='Iktus kordis', choices=IKTUS_KORDIS_CHOICES),
        StepField('bunyi_jantung', 'select', label='Bunyi jantung & bunyi tambahan', choices=BUNYI_JANTUNG_CHOICES),
        StepField('bunyi_napas', 'select', label='Bunyi napas paru', choices=BUNYI_NAPAS_CHOICES),
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
