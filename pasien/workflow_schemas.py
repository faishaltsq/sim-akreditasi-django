"""Registri skema langkah asesmen per jalur layanan (ADR-1, ADR-9).

``STEP_SCHEMAS['IGD']`` berisi tuple nama field model ``KunjunganPasien``.
Bentuk ini yang dipahami ``modelform_factory`` dan ``save_step`` jalur IGD.
Isinya **identik** dengan ``STEPS`` historis; ``pasien.forms_igd_workflow.STEPS``
menunjuk objek yang sama sehingga tidak ada satu pun pemanggil lama yang
berubah perilaku.

Modul ini tidak boleh mengimpor ``pasien.services.*``: pemanggil yang
melempar ``WorkflowValidation``.
"""
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

STEP_SCHEMAS = {
    'IGD': IGD_STEPS,
}
