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

# ── Lapis 2 kardiologi langkah 2–6 (F3, matriks S2-L2..S6-L2) ───────────────
# Setiap daftar di bawah adalah salinan opsi matriks apa adanya; urutannya
# dipertahankan supaya layar dan dokumen sumber dapat dibandingkan langsung.

#: S2-L2-01 — Langkah 2 Lapis 2 (matriks menempatkannya di Langkah 2, bukan 3).
ONSET_GEJALA_CHOICES = ('LT_30_MENIT', '30M_6J', '6J_24J', '24J_7H', 'GT_7H_KRONIS')
ONSET_GEJALA_LABELS = {
    'LT_30_MENIT': '< 30 Menit',
    '30M_6J': '30 Menit – 6 Jam',
    '6J_24J': '> 6 – 24 Jam',
    '24J_7H': '> 24 Jam – 7 Hari',
    'GT_7H_KRONIS': '> 7 Hari / Kronis',
}

#: S2-L2-02.
PEMICU_GEJALA_CHOICES = (
    'AKTIVITAS_RINGAN', 'AKTIVITAS_SEDANG_BERAT', 'ISTIRAHAT',
    'STRES_SUHU_DINGIN', 'TIDAK_MENENTU',
)
PEMICU_GEJALA_LABELS = {
    'AKTIVITAS_RINGAN': 'Aktivitas Ringan',
    'AKTIVITAS_SEDANG_BERAT': 'Aktivitas Sedang/Berat',
    'ISTIRAHAT': 'Saat Istirahat',
    'STRES_SUHU_DINGIN': 'Stres Emosional / Suhu Dingin',
    'TIDAK_MENENTU': 'Tidak Menentu',
}

#: S3-L2-01 — multi-select.
RIWAYAT_JANTUNG_CHOICES = (
    'TIDAK_ADA', 'PJK', 'PCI_STENT_CABG', 'GAGAL_JANTUNG',
    'ARITMIA_AF', 'PENYAKIT_KATUP', 'PENYAKIT_BAWAAN',
)
RIWAYAT_JANTUNG_LABELS = {
    'TIDAK_ADA': 'Tidak Ada',
    'PJK': 'Penyakit Jantung Koroner (PJK / CAD)',
    'PCI_STENT_CABG': 'Riwayat PCI / Stent / CABG',
    'GAGAL_JANTUNG': 'Gagal Jantung (HF)',
    'ARITMIA_AF': 'Aritmia / Fibrilasi Atrium (AF)',
    'PENYAKIT_KATUP': 'Penyakit Katup Jantung',
    'PENYAKIT_BAWAAN': 'Penyakit Jantung Bawaan',
}

#: S3-L2-02 — multi-select.
FAKTOR_RISIKO_CHOICES = (
    'HIPERTENSI', 'DIABETES_MELITUS', 'DISLIPIDEMIA',
    'RIWAYAT_KELUARGA_DINI', 'OBESITAS',
)
FAKTOR_RISIKO_LABELS = {
    'HIPERTENSI': 'Hipertensi',
    'DIABETES_MELITUS': 'Diabetes Melitus',
    'DISLIPIDEMIA': 'Dislipidemia',
    'RIWAYAT_KELUARGA_DINI': 'Riwayat Keluarga Penyakit Jantung Dini',
    'OBESITAS': 'Obesitas',
}

#: S3-L2-03.
STATUS_MEROKOK_CHOICES = ('TIDAK_PERNAH', 'MANTAN', 'AKTIF')
STATUS_MEROKOK_LABELS = {
    'TIDAK_PERNAH': 'Tidak Pernah Merokok',
    'MANTAN': 'Mantan Perokok',
    'AKTIF': 'Perokok Aktif',
}

#: S3-L2-04 — "Hamil (Trimester I/II/III)" adalah SATU opsi pada matriks, bukan
#: tiga; trimester tidak dipecah karena sumber tidak memecahnya.
STATUS_KEHAMILAN_CHOICES = ('TIDAK_BERLAKU', 'TIDAK_HAMIL_TIDAK_MENYUSUI', 'HAMIL', 'MENYUSUI')
STATUS_KEHAMILAN_LABELS = {
    'TIDAK_BERLAKU': 'Tidak Berlaku',
    'TIDAK_HAMIL_TIDAK_MENYUSUI': 'Tidak Hamil / Tidak Menyusui',
    'HAMIL': 'Hamil (Trimester I/II/III)',
    'MENYUSUI': 'Menyusui',
}
#: Status yang memicu peringatan kontraindikasi (matriks §9a).
KEHAMILAN_KONTRAINDIKASI = ('HAMIL', 'MENYUSUI')

#: S3-L2-05 — kepatuhan obat rutin.
KEPATUHAN_OBAT_CHOICES = ('ADA_PATUH', 'ADA_TIDAK_PATUH', 'TIDAK_ADA', 'TIDAK_TAHU')
KEPATUHAN_OBAT_LABELS = {
    'ADA_PATUH': 'Ada & Patuh',
    'ADA_TIDAK_PATUH': 'Ada & Tidak Patuh',
    'TIDAK_ADA': 'Tidak Ada',
    'TIDAK_TAHU': 'Tidak Tahu',
}
#: S3-L2-05 — kelompok obat rutin yang disebut matriks apa adanya.
OBAT_RUTIN_CHOICES = (
    'ANTIPLATELET', 'ANTIKOAGULAN', 'NITRAT', 'ANTIHIPERTENSI',
    'OBAT_GAGAL_JANTUNG', 'STATIN',
)
OBAT_RUTIN_LABELS = {
    'ANTIPLATELET': 'Antiplatelet',
    'ANTIKOAGULAN': 'Antikoagulan',
    'NITRAT': 'Nitrat',
    'ANTIHIPERTENSI': 'Antihipertensi',
    'OBAT_GAGAL_JANTUNG': 'Obat Gagal Jantung',
    'STATIN': 'Statin',
}

#: S5-L2-01.
KONDISI_PSIKOLOGIS_CHOICES = (
    'TENANG_KOOPERATIF', 'CEMAS_RINGAN_SEDANG', 'CEMAS_BERAT_PANIK', 'DEPRESI_MENARIK_DIRI',
)
KONDISI_PSIKOLOGIS_LABELS = {
    'TENANG_KOOPERATIF': 'Tenang / Kooperatif',
    'CEMAS_RINGAN_SEDANG': 'Cemas Ringan–Sedang',
    'CEMAS_BERAT_PANIK': 'Cemas Berat / Panik',
    'DEPRESI_MENARIK_DIRI': 'Depresi / Menarik Diri',
}

#: S5-L2-03 — dropdown + kolom keterangan.
KEBUTUHAN_SPIRITUAL_CHOICES = ('TIDAK_ADA', 'ADA')
KEBUTUHAN_SPIRITUAL_LABELS = {
    'TIDAK_ADA': 'Tidak Ada Kebutuhan Khusus',
    'ADA': 'Ada Kebutuhan Khusus',
}

#: S6-L1-03 — derajat murmur 1/6–6/6, satu-satunya bagian yang matriks enumerasi.
MURMUR_DERAJAT_CHOICES = ('1/6', '2/6', '3/6', '4/6', '5/6', '6/6')
MURMUR_DERAJAT_LABELS = {code: code for code in MURMUR_DERAJAT_CHOICES}

#: AMBIGU-17(b) — keputusan produk: lokasi murmur memakai daftar tertutup lima
#: nilai supaya dapat diagregasi sebagai indikator mutu. Kasus non-standar tidak
#: hilang: kode ``LAINNYA`` mewajibkan keterangan bebas di
#: ``murmur_lokasi_lainnya``. Kode, bukan label, yang disimpan.
MURMUR_LOKASI_CHOICES = ('AORTA', 'PULMONAL', 'TRIKUSPID', 'MITRAL', 'LAINNYA')
MURMUR_LOKASI_LABELS = {
    'AORTA': 'Fokus Aorta (ICS II Kanan)',
    'PULMONAL': 'Fokus Pulmonal (ICS II Kiri)',
    'TRIKUSPID': 'Fokus Trikuspid (ICS IV Kiri Parasternal)',
    'MITRAL': 'Fokus Mitral (Apeks, ICS V LMC Sinistra)',
    'LAINNYA': 'Lokasi Lain (tuliskan)',
}
#: Nilai yang membuka field teks bebas di samping daftar tertutup.
MURMUR_LOKASI_LAINNYA = 'LAINNYA'

#: S6-L2-01 — JVP, nilai baku v2.1.
JVP_CHOICES = ('TIDAK_MENINGKAT', 'MENINGKAT')
JVP_LABELS = {
    'TIDAK_MENINGKAT': 'Tidak Meningkat (5 + 0 s.d. 2 cmH2O)',
    'MENINGKAT': 'Meningkat (5 + >= 3 cmH2O)',
}

#: S6-L2-02 — edema ekstremitas bawah / sakral.
EDEMA_CHOICES = ('TIDAK_ADA', 'PRETIBIAL_RINGAN', 'TUNGKAI_JELAS_ANASARKA')
EDEMA_LABELS = {
    'TIDAK_ADA': 'Tidak Ada Edema',
    'PRETIBIAL_RINGAN': 'Edema Pretibial Ringan (+1/+2)',
    'TUNGKAI_JELAS_ANASARKA': 'Edema Tungkai Jelas (+3/+4) / Anasarka',
}

#: S6-L2-04 — perfusi & pulsasi perifer (CRT ikut di dalam opsinya).
PERFUSI_PERIFER_CHOICES = ('AKRAL_HANGAT_CRT_NORMAL', 'AKRAL_DINGIN_CRT_MEMANJANG')
PERFUSI_PERIFER_LABELS = {
    'AKRAL_HANGAT_CRT_NORMAL': 'Akral Hangat, CRT < 2 detik, Pulsasi Kuat',
    'AKRAL_DINGIN_CRT_MEMANJANG': 'Akral Dingin / CRT >= 3 detik / Pulsasi Melemah',
}

# ── Langkah 8 & 9 (F5, matriks S8-L1-01..05, S8-L2-01..03, S9-L1-19) ────────
# Setiap daftar di bawah adalah salinan opsi matriks apa adanya. Tidak ada
# ambang, interval, atau kelas obat yang dikarang di sini: yang tidak tertulis
# di matriks tidak ada di daftar.

#: S8-L1-01 — toolbar metode input yang dipakai bersama Langkah 8 dan 9.
#: ``AI`` ada di daftar matriks, tetapi penyedianya baru F9; karena itu nilai
#: ``AI`` ditolak saat simpan (lihat ``INPUT_MODE_UNAVAILABLE``), bukan
#: diterima lalu diabaikan.
INPUT_MODE_CHOICES = ('MANUAL', 'MASTER', 'AI')
INPUT_MODE_LABELS = {
    'MANUAL': 'Manual — pengisian langsung DPJP/PPA',
    'MASTER': 'Master — katalog ICD-10 / formularium / paket edukasi',
    'AI': 'Bantuan AI (Clinical Decision Support)',
}
#: Mode yang belum punya penyedia pada rilis ini (F9).
INPUT_MODE_UNAVAILABLE = ('AI',)

#: F6.3 — matriks S9-L1-09 (quick-chips keluhan) dan S9-L1-10 (kepatuhan
#: terapi), verbatim. Kode pendek disimpan; label dirender template.
KELUHAN_CPPT_CHOICES = (
    'SESAK_NAPAS', 'NYERI_DADA', 'ORTOPNEA', 'PND', 'BERDEBAR',
    'EDEMA_TUNGKAI', 'PUSING_PRESINKOP',
)
KELUHAN_CPPT_LABELS = {
    'SESAK_NAPAS': 'Sesak napas',
    'NYERI_DADA': 'Nyeri dada',
    'ORTOPNEA': 'Ortopnea',
    'PND': 'PND (paroxysmal nocturnal dyspnea)',
    'BERDEBAR': 'Berdebar',
    'EDEMA_TUNGKAI': 'Edema tungkai',
    'PUSING_PRESINKOP': 'Pusing / presinkop',
}

KEPATUHAN_TERAPI_CHOICES = (
    'PATUH_PENUH', 'SEBAGIAN_TERLEWAT', 'MENGHENTIKAN_SENDIRI', 'BELUM_MEMULAI',
)
KEPATUHAN_TERAPI_LABELS = {
    'PATUH_PENUH': 'Patuh penuh',
    'SEBAGIAN_TERLEWAT': 'Sebagian terlewat',
    'MENGHENTIKAN_SENDIRI': 'Menghentikan sendiri',
    'BELUM_MEMULAI': 'Belum memulai',
}

#: S8-L1-02 — diagnosis kerja utama. Matriks menulis kode ICD-10 di dalam
#: labelnya (``I10``, ``I20/I25``, …); kode pendek di sini mempertahankan
#: pengelompokan itu tanpa memecah satu opsi menjadi beberapa.
DIAGNOSIS_UTAMA_KATEGORI_CHOICES = (
    'I10', 'I20_I25', 'I50', 'I48_I49', 'I34_I38', 'LAINNYA',
)
DIAGNOSIS_UTAMA_KATEGORI_LABELS = {
    'I10': 'Hipertensi Esensial (I10)',
    'I20_I25': 'Penyakit Jantung Koroner / Angina Pektoris (I20/I25)',
    'I50': 'Gagal Jantung / CHF (I50)',
    'I48_I49': 'Aritmia Jantung / Atrial Fibrilasi (I48/I49)',
    'I34_I38': 'Penyakit Katup Jantung (I34–I38)',
    'LAINNYA': 'Diagnosis Lainnya',
}

#: S8-L1-04 — klasifikasi fungsional / stratifikasi risiko. Matriks
#: menempatkan NYHA, CCS, dan risiko rendah–sedang/tinggi pada **satu**
#: dropdown, jadi tidak dipecah menjadi tiga field.
KLASIFIKASI_FUNGSIONAL_CHOICES = (
    'NYHA_I', 'NYHA_II', 'NYHA_III', 'NYHA_IV',
    'CCS_I', 'CCS_II', 'CCS_III', 'CCS_IV',
    'RISIKO_RENDAH_SEDANG', 'RISIKO_TINGGI',
)
KLASIFIKASI_FUNGSIONAL_LABELS = {
    'NYHA_I': 'NYHA Kelas I',
    'NYHA_II': 'NYHA Kelas II',
    'NYHA_III': 'NYHA Kelas III',
    'NYHA_IV': 'NYHA Kelas IV',
    'CCS_I': 'CCS Kelas I',
    'CCS_II': 'CCS Kelas II',
    'CCS_III': 'CCS Kelas III',
    'CCS_IV': 'CCS Kelas IV',
    'RISIKO_RENDAH_SEDANG': 'Risiko Rendah–Sedang',
    'RISIKO_TINGGI': 'Risiko Tinggi',
}

#: S8-L1-05 — rencana tindak lanjut utama.
RENCANA_TINDAK_LANJUT_CHOICES = (
    'RAJAL_KONTROL_POLI', 'RAWAT_INAP_ICCU_HCU', 'RUJUK_RS_JEJARING', 'MENUNGGU_PENUNJANG',
)
RENCANA_TINDAK_LANJUT_LABELS = {
    'RAJAL_KONTROL_POLI': 'Rawat Jalan / Kontrol Poli Jantung',
    'RAWAT_INAP_ICCU_HCU': 'Rawat Inap / ICCU / HCU',
    'RUJUK_RS_JEJARING': 'Rujuk ke RS Jejaring / Intervensi Lanjut',
    'MENUNGGU_PENUNJANG': 'Menunggu Hasil Penunjang Lanjutan',
}

#: S8-L2-01 — status terapi farmakologis / e-resep.
TERAPI_STATUS_CHOICES = (
    'RESEP_RAJAL', 'PENYESUAIAN_DOSIS', 'TINDAKAN_POLI', 'BELUM_DIBERIKAN',
)
TERAPI_STATUS_LABELS = {
    'RESEP_RAJAL': 'Diberikan Resep Rawat Jalan',
    'PENYESUAIAN_DOSIS': 'Penyesuaian Dosis Obat Rutin',
    'TINDAKAN_POLI': 'Tindakan / Injeksi di Poli',
    'BELUM_DIBERIKAN': 'Belum Diberikan',
}

#: S8-L2-02 — edukasi pasien & keluarga (Standar KE STARKES). Multi-select.
EDUKASI_KARDIO_CHOICES = (
    'POLA_HIDUP_MEROKOK',
    'DIET_RENDAH_GARAM_LEMAK_CAIRAN',
    'KEPATUHAN_GDMT_EFEK_SAMPING',
    'TANDA_BAHAYA_IGD',
)
EDUKASI_KARDIO_LABELS = {
    'POLA_HIDUP_MEROKOK': 'Pola Hidup Sehat & Berhenti Merokok',
    'DIET_RENDAH_GARAM_LEMAK_CAIRAN': 'Diet Rendah Garam/Lemak & Pembatasan Cairan',
    'KEPATUHAN_GDMT_EFEK_SAMPING': 'Kepatuhan Minum Obat GDMT & Pemantauan Efek Samping',
    'TANDA_BAHAYA_IGD': 'Tanda Bahaya (Red Flags) Kapan Harus ke IGD',
}

#: S8-L2-03 — jadwal kontrol berikutnya. Interval hari hanya untuk tiga opsi
#: pertama; opsi terakhir tidak memberi jarak, jadi tidak ada tanggal yang
#: dihitung untuknya (AMBIGU-19).
JADWAL_KONTROL_CHOICES = ('H7', 'H14', 'H30', 'SESUAI_JADWAL_TINDAKAN')
JADWAL_KONTROL_LABELS = {
    'H7': '7 Hari',
    'H14': '14 Hari',
    'H30': '30 Hari',
    'SESUAI_JADWAL_TINDAKAN': 'Sesuai Jadwal Tindakan / Hasil Lab',
}
#: Jarak hari per kode jadwal; opsi tanpa jarak tidak ada di sini.
JADWAL_KONTROL_HARI = {'H7': 7, 'H14': 14, 'H30': 30}

#: S9-L1-19 — pintasan regimen GDMT & penyesuaian dosis. Matriks memberi empat
#: pilihan; tidak ada dosis angka di sini karena matriks tidak menyebutnya.
GDMT_PENYESUAIAN_CHOICES = (
    'MULAI_DOSIS_RENDAH', 'TITRASI_NAIK', 'TAHAN_TURUNKAN_DOSIS', 'LANJUTKAN_DOSIS',
)
GDMT_PENYESUAIAN_LABELS = {
    'MULAI_DOSIS_RENDAH': 'Mulai Dosis Rendah',
    'TITRASI_NAIK': 'Titrasi Naik',
    'TAHAN_TURUNKAN_DOSIS': 'Tahan / Turunkan Dosis',
    'LANJUTKAN_DOSIS': 'Lanjutkan Dosis Saat Ini',
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
    'onset_gejala': ONSET_GEJALA_LABELS,
    'pemicu_gejala': PEMICU_GEJALA_LABELS,
    'riwayat_jantung': RIWAYAT_JANTUNG_LABELS,
    'faktor_risiko_kardio': FAKTOR_RISIKO_LABELS,
    'status_merokok': STATUS_MEROKOK_LABELS,
    'status_kehamilan_menyusui': STATUS_KEHAMILAN_LABELS,
    'kepatuhan_obat': KEPATUHAN_OBAT_LABELS,
    'obat_rutin': OBAT_RUTIN_LABELS,
    'kondisi_psikologis': KONDISI_PSIKOLOGIS_LABELS,
    'kebutuhan_spiritual': KEBUTUHAN_SPIRITUAL_LABELS,
    'murmur_derajat': MURMUR_DERAJAT_LABELS,
    'murmur_lokasi': MURMUR_LOKASI_LABELS,
    'jvp': JVP_LABELS,
    'edema_ekstremitas': EDEMA_LABELS,
    'perfusi_perifer': PERFUSI_PERIFER_LABELS,
    'input_mode': INPUT_MODE_LABELS,
    'diagnosis_utama_kategori': DIAGNOSIS_UTAMA_KATEGORI_LABELS,
    'klasifikasi_fungsional': KLASIFIKASI_FUNGSIONAL_LABELS,
    'rencana_tindak_lanjut': RENCANA_TINDAK_LANJUT_LABELS,
    'terapi_status': TERAPI_STATUS_LABELS,
    'edukasi': EDUKASI_KARDIO_LABELS,
    'jadwal_kontrol': JADWAL_KONTROL_LABELS,
    'gdmt_penyesuaian': GDMT_PENYESUAIAN_LABELS,
}


@dataclass(frozen=True)
class ConditionalField:
    """Sub-field teks yang hanya sah untuk satu nilai pemicu (AMBIGU-17(b)).

    ``name`` wajib terisi bila ``trigger`` bernilai ``trigger_value``, dan wajib
    kosong untuk nilai lain. Aturan dua arah ini yang membuat daftar tertutup
    tetap dapat diagregasi: kode ``LAINNYA`` tidak pernah tersimpan tanpa
    keterangan, dan empat kode baku tidak pernah membawa teks liar.
    """

    name: str
    trigger: str
    trigger_value: str
    label: str = ''
    max_length: int = 200

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
    #: Hanya untuk ``kind='group'``: sub-field yang membentuk satu dict.
    children: tuple = ()
    #: Hanya untuk ``kind='group'``: field kondisional antar sub-field.
    conditional: tuple = ()

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
        if self.kind == 'multiselect':
            if not isinstance(value, list):
                return None, 'Nilai harus berupa daftar pilihan.'
            if len(set(value)) != len(value):
                return None, 'Pilihan tidak boleh berulang.'
            unknown = [code for code in value if code not in self.choices]
            if unknown:
                return None, f'Pilihan harus salah satu dari: {", ".join(self.choices)}.'
            return value, None
        if self.kind == 'markers':
            from .anatomy_markers import validate_markers
            markers, error = validate_markers(value)
            return (None, error) if error else (markers, None)
        if self.kind == 'group':
            if not isinstance(value, dict):
                return None, 'Nilai harus berupa objek.'
            unknown = sorted(set(value) - {child.name for child in self.children})
            if unknown:
                return None, f'Bagian tidak dikenal: {", ".join(unknown)}.'
            cleaned, problems = {}, []
            for child in self.children:
                if child.name not in value:
                    continue
                child_value, error = child.clean(value[child.name])
                if error:
                    problems.append(f'{child.name}: {error}')
                elif child_value is not None:
                    cleaned[child.name] = child_value
            if problems:
                return None, ' '.join(problems)
            for rule in self.conditional:
                text = cleaned.get(rule.name)
                if cleaned.get(rule.trigger) == rule.trigger_value:
                    if not text:
                        problems.append(
                            f'{rule.name}: wajib diisi bila {rule.trigger} = {rule.trigger_value}.')
                elif text:
                    problems.append(
                        f'{rule.name}: hanya boleh diisi bila {rule.trigger} = {rule.trigger_value}.')
            if problems:
                return None, ' '.join(problems)
            return cleaned, None
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
        # S2-L2-01/S2-L2-02 — matriks menempatkan keduanya di Langkah 2 Lapis 2.
        StepField('onset_gejala', 'select', label='Waktu onset gejala utama', choices=ONSET_GEJALA_CHOICES),
        StepField('pemicu_gejala', 'select', label='Pemicu gejala', choices=PEMICU_GEJALA_CHOICES),
    )),
    3: StepSpec(3, 'Anamnesis & Riwayat', (
        StepField('anamnesis_rps', 'text', label='Riwayat penyakit sekarang'),
        StepField('keluhan_utama_kardio', 'select', label='Keluhan utama kardiovaskular', choices=KELUHAN_UTAMA_CHOICES),
        StepField('nyeri_karakteristik_kardio', 'select', label='Karakteristik nyeri dada', choices=NYERI_KARAKTERISTIK_CHOICES),
        StepField('nyeri_penjalaran', 'select', label='Penjalaran nyeri', choices=NYERI_PENJALARAN_CHOICES),
        StepField('riwayat_jantung', 'multiselect', label='Riwayat penyakit jantung sebelumnya', choices=RIWAYAT_JANTUNG_CHOICES),
        StepField('faktor_risiko_kardio', 'multiselect', label='Faktor risiko kardiovaskular', choices=FAKTOR_RISIKO_CHOICES),
        StepField('status_merokok', 'select', label='Status merokok', choices=STATUS_MEROKOK_CHOICES),
        # Batas angka tidak ada pada matriks (S3-L2-03 hanya menyebut "estimasi
        # batang/hari dan lama merokok"), jadi tidak ada minimum/maksimum yang
        # dikarang di sini.
        StepField('batang_per_hari', 'number', label='Estimasi batang/hari'),
        StepField('tahun_merokok', 'number', label='Lama merokok (tahun)'),
        StepField('status_kehamilan_menyusui', 'select', label='Status kehamilan & menyusui', choices=STATUS_KEHAMILAN_CHOICES),
        StepField('kepatuhan_obat', 'select', label='Riwayat obat rutin kardiovaskular (kepatuhan)', choices=KEPATUHAN_OBAT_CHOICES),
        StepField('obat_rutin', 'multiselect', label='Kelompok obat rutin', choices=OBAT_RUTIN_CHOICES),
        StepField('obat_rutin_terakhir', 'text', label='Waktu konsumsi dosis terakhir', max_length=200),
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
        # S5-L2-01, S5-L2-03 — aspek psikologis & spiritual (F3.7).
        StepField('kondisi_psikologis', 'select', label='Kondisi psikologis / kecemasan', choices=KONDISI_PSIKOLOGIS_CHOICES),
        StepField('kebutuhan_spiritual', 'select', label='Kebutuhan spiritual / nilai budaya khusus', choices=KEBUTUHAN_SPIRITUAL_CHOICES),
        StepField('keterangan_spiritual', 'text', label='Keterangan pendampingan rohani/budaya', max_length=500),
    )),
    6: StepSpec(6, 'Pemeriksaan Fisik', (
        StepField('keadaan_umum', 'text', label='Keadaan umum'),
        StepField('fisik_lokalis', 'text', label='Pemeriksaan fisik lokalis'),
        StepField('iktus_kordis', 'select', label='Iktus kordis', choices=IKTUS_KORDIS_CHOICES),
        StepField('bunyi_jantung', 'select', label='Bunyi jantung & bunyi tambahan', choices=BUNYI_JANTUNG_CHOICES),
        StepField('bunyi_napas', 'select', label='Bunyi napas paru', choices=BUNYI_NAPAS_CHOICES),
        # F3.5: satu dict ``fisik_kardio`` berisi sub-pemeriksaan kardio
        # terstruktur. Derajat murmur dan lokasi katup keduanya dienumerasi.
        # AMBIGU-17(b) ditutup oleh keputusan produk: lima lokasi tertutup plus
        # teks bebas yang hanya sah untuk ``LAINNYA``.
        StepField('fisik_kardio', 'group', label='Pemeriksaan fisik kardiovaskular', children=(
            StepField('murmur_derajat', 'select', label='Derajat murmur', choices=MURMUR_DERAJAT_CHOICES),
            StepField('murmur_lokasi', 'select', label='Lokasi murmur / katup', choices=MURMUR_LOKASI_CHOICES),
            StepField('murmur_lokasi_lainnya', 'text', label='Keterangan lokasi lain', max_length=200),
            StepField('jvp', 'select', label='Tekanan vena jugularis (JVP)', choices=JVP_CHOICES),
            StepField('edema_ekstremitas', 'select', label='Edema ekstremitas bawah / sakral', choices=EDEMA_CHOICES),
            StepField('perfusi_perifer', 'select', label='Perfusi & pulsasi perifer', choices=PERFUSI_PERIFER_CHOICES),
        ), conditional=(
            ConditionalField('murmur_lokasi_lainnya', 'murmur_lokasi', MURMUR_LOKASI_LAINNYA,
                             label='Keterangan lokasi lain'),
        )),
        # F3.6: penanda anatomi memakai validasi yang sama dengan jalur IGD
        # (maks 100, koordinat 0–1), disimpan di payload — bukan kolom baru.
        StepField('penanda_anatomi', 'markers', label='Penanda anatomi'),
    )),
    7: StepSpec(7, 'Pemeriksaan Penunjang', (
        StepField('penunjang_catatan', 'text', label='Catatan penunjang'),
    )),
    8: StepSpec(8, 'Penetapan Diagnosis & Rencana', (
        # S8-L1-01: toolbar Manual/Master/AI direkam sebagai nilai langkah,
        # sehingga provenance tiap isian dapat dibedakan tanpa kolom baru.
        StepField('input_mode', 'select', label='Metode input', choices=INPUT_MODE_CHOICES),
        StepField('diagnosis_utama_kategori', 'select', label='Diagnosis kerja utama',
                  choices=DIAGNOSIS_UTAMA_KATEGORI_CHOICES),
        StepField('diagnosa_utama', 'text', label='Diagnosis utama'),
        # S8-L1-04: satu dropdown memuat NYHA, CCS, dan stratifikasi risiko.
        StepField('klasifikasi_fungsional', 'select', label='Klasifikasi fungsional / stratifikasi risiko',
                  choices=KLASIFIKASI_FUNGSIONAL_CHOICES),
        StepField('rencana_tindak_lanjut', 'select', label='Rencana tindak lanjut utama',
                  choices=RENCANA_TINDAK_LANJUT_CHOICES),
        StepField('terapi_status', 'select', label='Status terapi farmakologis / e-resep',
                  choices=TERAPI_STATUS_CHOICES),
        StepField('edukasi', 'multiselect', label='Edukasi pasien & keluarga',
                  choices=EDUKASI_KARDIO_CHOICES),
        # S8-L2-02 menuntut bukti bertanda tangan pasien/keluarga; nama
        # penerima edukasi karena itu ikut tercatat, bukan dikarang dari data
        # pasien saat PDF dibuat.
        StepField('edukasi_penerima', 'text', label='Nama pasien/keluarga penerima edukasi',
                  max_length=150),
        StepField('jadwal_kontrol', 'select', label='Jadwal kontrol berikutnya',
                  choices=JADWAL_KONTROL_CHOICES),
        StepField('rencana_terapi', 'text', label='Rencana terapi'),
    )),
    9: StepSpec(9, 'Pelaksanaan Asuhan — CPPT & Billing', (
        StepField('input_mode', 'select', label='Metode input', choices=INPUT_MODE_CHOICES),
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
