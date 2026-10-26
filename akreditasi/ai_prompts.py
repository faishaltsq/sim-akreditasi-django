"""
Template prompt AI Asisten Cerdas spesialis Akreditasi RS (KARS STARKES 2022).
Semua prompt dirancang untuk menghasilkan output JSON terstruktur
yang bisa langsung diparsing dan diisikan ke formulir sistem.
"""

# ── SYSTEM PROMPT DASAR ──────────────────────────────────────────────────

SYSTEM_PROMPT_RS = (
    "Anda adalah Konsultan Ahli Senior Manajemen Mutu dan Keselamatan Pasien "
    "Rumah Sakit Tipe B yang berpengalaman menangani akreditasi KARS STARKES 2022. "
    "Anda memahami seluruh standar akreditasi (TKRS, PMKP, KPS, PKPO, ARK, AP, PAP, PPI, MIRM, "
    "dan standar lainnya). Tugas Anda adalah memberikan rekomendasi yang SMART "
    "(Specific, Measurable, Achievable, Relevant, Time-bound), aplikatif, "
    "dan sesuai regulasi perumahsakitan Indonesia (Permenkes, UU Kesehatan, JCI). "
    "SELALU jawab dalam Bahasa Indonesia. "
    "SELALU format output dalam JSON valid (tanpa markdown code block). "
    "JANGAN pernah mencantumkan data identitas pasien pribadi dalam jawaban."
)

# ── 1. REKOMENDASI MITIGASI RISIKO ───────────────────────────────────────

PROMPT_MITIGASI_RISIKO = """Konteks Risiko Unit Kerja Rumah Sakit:
- Unit Kerja: {unit_name}
- Kategori Risiko: {kategori_risiko}
- Jenis Risiko: {jenis_risiko}
- Deskripsi: {deskripsi_risiko}
- Dampak (Severity): {dampak}/5
- Probabilitas (Likelihood): {probabilitas}/5
- Skor Risiko: {skor} — Tingkat: {level}
- Strategi Pilihan User: {strategi}

Tugas: Buatkan Rencana Aksi Mitigasi yang terstruktur dan aplikatif.

Format Output JSON:
{{
  "rencana_aksi": "1. [Langkah pencegahan langsung]\\n2. [Pembaruan SOP/Regulasi internal]\\n3. [Sosialisasi & pelatihan staf]\\n4. [Monitoring & evaluasi berkala]\\n5. [Dokumentasi sebagai bukti akreditasi]",
  "strategi_disarankan": "Hindari / Mitigasi / Transfer / Terima",
  "pj_rekomendasi": "Kepala Unit / Tim terkait",
  "target_durasi_hari": 14,
  "catatan_kars": "Referensi standar STARKES terkait dan rekomendasi pemenuhan",
  "indikator_keberhasilan": "Indikator yang bisa diukur untuk memastikan mitigasi berhasil"
}}"""

# ── 2. ACTION PLAN PDCA ──────────────────────────────────────────────────

PROMPT_PDCA_ACTION_PLAN = """Konteks Elemen Penilaian (EP) Akreditasi RS:
- Kode EP: {ep_code}
- Nama Standar: {ep_name}
- Deskripsi EP: {ep_desc}
- Unit Kerja Penanggung Jawab: {unit_name}
- Skor Saat Ini: {current_score}/10
- Catatan Evaluasi Sebelumnya: {eval_notes}

Tugas: Buatkan Rencana Tindak Lanjut siklus PDCA lengkap.

Format Output JSON:
{{
  "plan": "Rencana kerja/kegiatan spesifik yang akan dilakukan untuk memenuhi EP ini",
  "do": "Langkah-langkah pelaksanaan konkret (siapa, apa, kapan)",
  "check": "Cara monitoring dan evaluasi pencapaian (metode, frekuensi, indikator)",
  "action": "Tindakan perbaikan / tindak lanjut berdasarkan evaluasi",
  "estimasi_biaya": "Rp 0 jika non-biaya, atau estimasi nominal (Capex/Opex)",
  "sumber_anggaran": "Capex Sarpras / Opex Operasional / Non-Biaya",
  "target_waktu": "Waktu penyelesaian (misal: 2 minggu / 1 bulan)",
  "dokumen_bukti": "Jenis dokumen yang perlu disiapkan sebagai bukti (SOP, Laporan, SK, dll)"
}}"""

# ── 3. GRADING & REKOMENDASI INSIDEN KESELAMATAN PASIEN ──────────────────

PROMPT_INSIDEN_GRADING = """Konteks Insiden Keselamatan Pasien (IKP) di Rumah Sakit:
- Jenis Insiden: {jenis_insiden}
- Tingkat Keparahan: {tingkat_keparahan}
- Lokasi Kejadian: {lokasi_kejadian}
- Deskripsi Kejadian: {deskripsi_kejadian}
- Tindakan Segera yang Dilakukan: {tindakan_segera}
- Pasien Terpapar: {pasien_terpapar}
- Unit Kerja: {unit_name}

Tugas: Analisis insiden ini dan berikan grading risiko serta rekomendasi investigasi.

Format Output JSON:
{{
  "grading": "BIRU / HIJAU / KUNING / MERAH",
  "grading_alasan": "Alasan penetapan warna grading berdasarkan matriks risiko IKP",
  "tingkat_investigasi": "Investigasi Sederhana / Root Cause Analysis (RCA)",
  "rekomendasi_tindakan": "1. [Tindakan korektif]\\n2. [Pencegahan]\\n3. [Sistem perbaikan]",
  "standar_kars_terkait": "Referensi standar PMKP / STARKES yang relevan",
  "pembelajaran": "Poin pembelajaran untuk seluruh staf RS",
  "timeline_investigasi": "Batas waktu investigasi (misal: 45 hari untuk RCA)"
}}"""

# ── 4. EVALUASI & TINDAK LANJUT RISIKO ───────────────────────────────────

PROMPT_EVALUASI_RISIKO = """Konteks Evaluasi Risiko Berkala & Indikator Mutu:
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Deskripsi Awal: {deskripsi_risiko}
- Indikator Mutu Terkait: {nama_indikator}
- Target Standar Indikator: {target_capaian}
- Nilai Capaian Realisasi: {capaian_nilai}
- Status Capaian & Gap: {gap_persen}
- Skor Awal: {skor_awal} (Dampak {dampak_awal} × Probabilitas {prob_awal})
- Rencana Mitigasi yang Sudah Dijalankan: {mitigasi_terlaksana}
- Dampak Residual (Sisa): {dampak_residual}/5
- Probabilitas Residual: {prob_residual}/5
- Status Saat Ini: {status}

Tugas: Evaluasi efektivitas mitigasi dan berikan draf analisis capaian mutu berstandar PMKP/STARKES/PDCA Rumah Sakit.

Format Output JSON:
{{
  "efektivitas": "Efektif / Sebagian Efektif / Belum Efektif",
  "analisis_capaian": "Uraian rinci penyebab target indikator belum/sudah tercapai berdasarkan data realisasi",
  "efektivitas_barrier": "Evaluasi apakah barrier/mitigasi yang dipasang berjalan efektif menekan risiko",
  "kendala_lapangan": "Hambatan atau kendala utama di lapangan dalam implementasi mitigasi",
  "draf_evaluasi": "1. Analisis Capaian: [isi ringkas]\\n2. Evaluasi Barrier/Mitigasi: [isi ringkas]\\n3. Kendala di Lapangan: [isi ringkas]",
  "analisis": "Analisis singkat apakah risiko sudah menurun dan mengapa",
  "tindak_lanjut": "1. [Langkah lanjutan]\\n2. [Penyesuaian strategi]\\n3. [Eskalasi jika perlu]",
  "rekomendasi_status": "MONITORING / MITIGASI / SELESAI",
  "catatan": "Catatan tambahan untuk dokumentasi akreditasi"
}}"""

# ── 5. ANALISIS KELENGKAPAN DOKUMEN RDWOS ────────────────────────────────

PROMPT_RDWOS_ANALISIS = """Konteks Kelengkapan Dokumen Bukti Akreditasi:
- Kode EP: {ep_code}
- Nama Standar: {ep_name}
- Dokumen yang Sudah Diunggah: {dokumen_ada}
- Total Kebutuhan Dokumen: {total_kebutuhan}
- Jenis Dokumen yang Sudah Ada: {jenis_dokumen}

Tugas: Analisis kelengkapan dan sarankan dokumen yang masih diperlukan.

Format Output JSON:
{{
  "status_kelengkapan": "Lengkap / Sebagian / Belum Lengkap",
  "persen_terpenuhi": 60,
  "dokumen_kurang": ["Nama dokumen 1 yang belum ada", "Nama dokumen 2"],
  "saran_penamaan": "Rekomendasi format penamaan file sesuai kaidah akreditasi",
  "catatan_surveyor": "Apa yang biasanya ditanyakan surveyor terkait EP ini",
  "prioritas": "TINGGI / SEDANG / RENDAH — berdasarkan pentingnya EP ini untuk kelulusan"
}}"""

# ── 6. REKOMENDASI KPS / KREDENSIAL NAKES ────────────────────────────────

PROMPT_KPS_REKOMENDASI = """Konteks Portofolio Kredensial Tenaga Kesehatan:
- Nama Profesi: {profesi}
- Jabatan: {jabatan}
- Unit Kerja: {unit_name}
- Daftar Kredensial: {daftar_kredensial}
- Kredensial yang Segera Kadaluarsa: {segera_expired}
- Pelatihan yang Sudah Diikuti: {pelatihan}

Tugas: Berikan rekomendasi kelengkapan kredensial dan pelatihan wajib sesuai standar KPS KARS.

Format Output JSON:
{{
  "status_kredensial": "Lengkap / Ada Kekurangan / Segera Kadaluarsa",
  "kredensial_kurang": ["Daftar kredensial yang wajib tapi belum ada"],
  "pelatihan_wajib": ["Pelatihan wajib sesuai profesi yang belum diikuti"],
  "peringatan": "Peringatan jika ada STR/SIP yang segera kadaluarsa dan langkah perpanjangan",
  "standar_kps_terkait": "Referensi standar KPS KARS terkait",
  "rekomendasi": "Saran tindakan untuk pemenuhan standar KPS"
}}"""

# ── 7. FORMULASI INDIKATOR MUTU (INM / IMP-RS / IMP-UNIT) ─────────────────

PROMPT_INDIKATOR_MUTU = """Konteks Perumusan Indikator Mutu Rumah Sakit (STARKES PMKP/TKRS):
- Unit Kerja: {unit_name}
- Jenis Indikator: {jenis}
- Nama / Topik Indikator: {nama_indikator}
- Masalah / Latar Belakang: {masalah}

Tugas: Rumuskan formula indikator mutu yang SMART, terukur, dan aplikatif sesuai kaidah PMKP Kemenkes/KARS.

Format Output JSON:
{{
  "kode_indikator_saran": "IMP-[UNIT]-01",
  "dimensi_mutu": "AMAN / EFEKTIF / EFISIEN / TEPAT_WAKTU / BERPUSAT_PASIEN / AKSESIBEL / ADIL",
  "numerator": "Kalimat definisi numerator (pembilang) yang jelas dan terukur",
  "denominator": "Kalimat definisi denominator (penyebut) yang jelas dan terukur",
  "target_nilai": 85.0,
  "satuan": "%",
  "rencana_aksi": "1. [Langkah pemantauan harian]\\n2. [Verifikasi data bulanan]\\n3. [Audit kepatuhan SOP]\\n4. [Rapat koordinasi perbaikan capaian]",
  "pj_saran": "Kepala Unit / Penanggung Jawab Terkait",
  "frekuensi_pengukuran": "Bulanan",
  "standar_ep_terkait": "PMKP / TKRS / SKP terkait"
}}"""

# ── 8. ANALISIS MASALAH & PENENTUAN JENIS RISIKO (STANDAR 5.15) ──────────

PROMPT_ANALISIS_MASALAH_RISIKO = """Konteks Masalah & Data Unit Kerja Rumah Sakit:
- Unit Kerja: {unit_name}
- Pernyataan Masalah (Issue Statement): {masalah}
- Data / Bukti Pendukung (Baseline Data): {data_pendukung}

Tugas:
1. Klasifikasikan masalah ini ke dalam salah satu Kategori Risiko Standar STARKES:
   (KLINIS, OPERASIONAL, FINANSIAL, REPUTASI, HUKUM_KEPATUHAN, FASILITAS_LINGKUNGAN).
2. Identifikasi 2 sampai 4 Jenis Risiko spesifik (potensi bahaya/kejadian tidak diharapkan) yang mungkin timbul dari masalah tersebut.
3. Buatkan draft Deskripsi Risiko yang komprehensif.
4. Sarankan Strategi Mitigasi terbaik sesuai STARKES (pilih satu: AVOID, REDUCE, TRANSFER, ACCEPT).
5. Sarankan nama Indikator Mutu yang relevan untuk memonitor risiko ini.

Format Output JSON:
{{
  "kategori_risiko": "KLINIS / OPERASIONAL / FINANSIAL / REPUTASI / HUKUM_KEPATUHAN / FASILITAS_LINGKUNGAN",
  "kategori_alasan": "Alasan singkat pemilihan kategori risiko ini",
  "daftar_jenis_risiko": [
    "Jenis Risiko 1 yang spesifik dan terukur",
    "Jenis Risiko 2 yang spesifik dan terukur",
    "Jenis Risiko 3 (opsional)"
  ],
  "deskripsi_risiko_saran": "Uraian deskripsi risiko lengkap yang menggabungkan konteks masalah dan dampak potensialnya",
  "strategi_mitigasi_saran": "KURANGI / HINDARI / TRANSFER / TERIMA",
  "indikator_mutu_saran": "Nama indikator mutu terkait yang relevan untuk memantau risiko ini",
  "dampak_saran": 3,
  "probabilitas_saran": 3
}}"""


# ── Section E: FMEA — Failure Mode and Effects Analysis (Proaktif) ────────────
PROMPT_FMEA_SUGGESTION = """Konteks Risiko Klinis Rumah Sakit (STARKES PMKP 8 - FMEA):
- Unit Kerja: {unit_name}
- Kategori Risiko: {kategori_risiko}
- Jenis Risiko: {jenis_risiko}
- Masalah / Temuan: {masalah}
- Data Pendukung: {data_pendukung}
- Skor Dampak (1-5): {dampak}
- Skor Probabilitas (1-5): {probabilitas}

Tugas (FMEA - Failure Mode and Effects Analysis, pendekatan PROAKTIF):
Lakukan analisis FMEA terhadap proses berisiko tinggi ini untuk MENCEGAH insiden sebelum terjadi.
1. Uraikan 3-5 MODE KEGAGALAN (failure mode) spesifik yang mungkin terjadi pada proses tersebut.
2. Untuk setiap mode kegagalan, sebutkan EFEK POTENSIAL terhadap pasien/unit.
3. Sebutkan PENYEBAB potensial (root causes).
4. Sebutkan BARRIER / KONTROL PENCEGAHAN yang direkomendasikan.
5. Hitung RPN = Severity x Occurrence x Detection (skala 1-10 tiap komponen, atau 1-5 jika skala RS 1-5).
6. Sarankan susunan TIM FMEA multidisiplin yang relevan.

Format Output JSON:
{{
  "failure_mode": "1. MODE KEGAGALAN:\n   <uraian spesifik modus kegagalan>\n   a. Efek Potensial:\n      <uraian efek terhadap pasien/unit>\n   b. Akar Masalah / Penyebab:\n      <uraian akar penyebab masalah>\n   c. Barrier / Kontrol Pencegahan:\n      <uraian kontrol pencegahan yang harus diterapkan>\n\n2. MODE KEGAGALAN:\n   <uraian spesifik modus kegagalan>\n   a. Efek Potensial:\n      <uraian efek terhadap pasien/unit>\n   b. Akar Masalah / Penyebab:\n      <uraian akar penyebab masalah>\n   c. Barrier / Kontrol Pencegahan:\n      <uraian kontrol pencegahan yang harus diterapkan>",
  "daftar_failure_mode": [
    {{"mode": "...", "efek": "...", "penyebab": "...", "barrier": "...", "severity": 8, "occurrence": 4, "detection": 3}}
  ],
  "rpn": 96,
  "rpn_kategori": "TINGGI / SEDANG / RENDAH",
  "tim_fmea": "Ka. Unit, IPCN, Ka. Farmasi, Komite Mutu, ...",
  "prioritas_tindakan": "Mode kegagalan mana yang harus ditangani lebih dulu dan mengapa",
  "rekomendasi_barrier": "Ringkasan kontrol pencegahan utama yang harus segera diterapkan"
}}"""


# ── Section E: RCA — Root Cause Analysis (Reaktif) ───────────────────────────
PROMPT_RCA_SUGGESTION = """Konteks Insiden / Risiko Klinis Rumah Sakit (STARKES PMKP 7 - RCA):
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Masalah / Kronologi Kejadian: {masalah}
- Data Pendukung: {data_pendukung}
- Skor Dampak (1-5): {dampak}
- Skor Probabilitas (1-5): {probabilitas}

Tugas (RCA - Root Cause Analysis, pendekatan REAKTIF):
Lakukan analisis akar masalah mendalam atas kejadian/risiko ini menggunakan metode 5-Whys dan kerangka Fishbone (Man, Method, Material, Machine, Measurement, Environment).
1. Susun rantai 5-Whys yang mengarah ke akar masalah utama.
2. Identifikasi penyebab langsung (immediate cause) vs akar masalah sistem (systemic root cause).
3. Kelompokkan kontributor berdasarkan kategori Fishbone.
4. Susun RENCANA TINDAKAN KOREKTIF yang konkret, terukur, dan bersifat solusi permanen (bukan sekadar quick fix).
5. Sarankan TIM INVESTIGASI RCA yang sesuai (ketua, anggota, unit terkait).
6. Sarankan cara memverifikasi efektivitas perbaikan.

Format Output JSON:
{{
  "akar_masalah": "1. Mengapa 1: ...\n2. Mengapa 2: ...\n3. Mengapa 3: ...\n4. Mengapa 4: ...\n5. Mengapa 5 (Akar Masalah Utama): ...",
  "penyebab_langsung": "Uraian penyebab langsung",
  "akar_masalah_sistemik": "Uraian akar masalah sistemik",
  "fishbone": {{
    "man": "...",
    "method": "...",
    "material": "...",
    "machine": "...",
    "measurement": "...",
    "environment": "..."
  }},
  "tindakan_korektif": "1. <tindakan konkret 1>\n2. <tindakan konkret 2>\n3. <tindakan konkret 3>",
  "tim_investigasi": "Ketua Komite Mutu, Ka. Unit, IPCN, ...",
  "verifikasi_efektivitas": "Cara memantau apakah tindakan perbaikan efektif mencegah berulangnya insiden"
}}"""

# ── Section F: Sinkronisasi Indikator Mutu ↔ Elemen Penilaian (EP) ───────────
#
# Katalog dikirim penuh (1053 EP, ~33–46k token) alih-alih dipangkas secara
# katas: 17 dari 36 link manual yang gagal ditemukan prefilter justru tidak
# berbagi SATU kata pun dengan teks EP ("sisa makanan tidak dimakan pasien"
# vs "instruksi pengobatan ditulis jelas di CPPT"), jadi penyaring berbasis
# kata tak akan pernah meneruskan EP yang benar ke model.

PROMPT_EP_MATCH = """Konteks Perumusan Indikator Mutu vs Elemen Penilaian (EP) STARKES:
- Kode Indikator: {kode}
- Nama Indikator: {nama}
- Numerator: {numerator}
- Denominator: {denominator}
- Jenis Indikator: {jenis}
- Dimensi Mutu: {dimensi}
- Unit Kerja: {unit}
- Pemetaan pokja unit ini (bila ada): {petunjuk_unit}

Katalog EP ({n_ep} baris). Format tiap baris: KODE | POKJA | BUNYI EP
{daftar_ep}

Tugas: pilih MAKSIMAL 5 EP yang paling relevan dengan indikator di atas.

Cara menilai:
- Nilai MAKNAnya, bukan kesamaan kata. Indikator memakai istilah klinis atau
  administratif, sedangkan EP memakai bahasa standar — keduanya sering tidak
  berbagi kata yang sama meski membahas hal yang sama.
- Cocokkan juga dengan unit kerja dan pemetaan pokja bila membantu.
- Utamakan EP yang benar-benar mengatur hal yang diukur indikator, bukan EP
  pokja yang sekadar mirip topik.

Aturan keras:
- ep_code HARUS persis salah satu kode pada katalog. JANGAN mengarang kode,
  jangan memodifikasi kode, jangan menebak kelanjutan pola kode.
- Urutkan dari confidence tertinggi.
- confidence antara 0.0 dan 1.0. Pakai di bawah 0.60 bila ragu-ragu; jangan
  mengisi semua dengan 0.9.
- alasan maksimal 25 kata dalam Bahasa Indonesia, sebutkan hubungan spesifik
  antara indikator dan EP itu.
- Bila memang tidak ada EP yang relevan, kembalikan "rekomendasi": [].

Format Output JSON:
{{
  "rekomendasi": [
    {{"ep_code": "TKRS 1 EP 1", "confidence": 0.9, "alasan": "contoh alasan singkat"}}
  ]
}}"""


# ── 12. NARASI LAPORAN CAPAIAN INDIKATOR MUTU ────────────────────────────

# Panduan isi per bagian. Dipakai bersama oleh prompt AI dan oleh UI supaya
# penyusun tahu apa yang diharapkan surveyor pada bagian tersebut.
PANDUAN_NARASI_BAB = {
    'RINGKASAN_EKSEKUTIF': (
        'Ringkas capaian indikator mutu periode ini dalam satu tarikan napas: '
        'berapa indikator terukur, berapa mencapai target, indikator mana yang '
        'paling bermasalah, dan apa rekomendasi pokok manajemen.'),
    'KENDALA': (
        'Uraikan hambatan nyata yang membuat target tidak tercapai — keterbatasan '
        'SDM, alat, alur, kepatuhan pengisian data, atau koordinasi lintas unit. '
        'Sebutkan dampaknya terhadap angka capaian, bukan keluhan umum.'),
    'REKOMENDASI': (
        'Rumuskan upaya perbaikan yang spesifik dan dapat dieksekusi: apa yang '
        'dilakukan, siapa penanggung jawabnya, kapan tenggatnya, dan bagaimana '
        'keberhasilannya diukur.'),
    'BAB_I': (
        'Bagian umum: dasar penyusunan laporan (regulasi, standar PMKP/KARS '
        'STARKES, kebijakan internal), tujuan penyusunan, ruang lingkup unit dan '
        'periode, serta sistematika laporan.'),
    'BAB_II': (
        'Analisis dan evaluasi capaian kinerja pelayanan: bandingkan angka capaian '
        'dengan standar/target, jelaskan tren antar bulan atau antar periode, '
        'kelompokkan indikator yang tercapai dan tidak tercapai, lalu analisis '
        'penyebabnya dengan kerangka PDSA.'),
    'BAB_III': (
        'Analisis dan evaluasi program kerja: program mutu apa yang dijalankan '
        'periode ini, capaian tiap program, kesesuaiannya dengan rencana kerja, '
        'serta kendala pelaksanaan dan penyesuaian yang diperlukan.'),
    'BAB_IV': (
        'Analisis dan evaluasi komponen biaya: dampak efisiensi biaya terhadap '
        'mutu pelayanan, sumber pembiayaan kegiatan mutu, dan implikasi capaian '
        'indikator terhadap biaya pelayanan. Bila data biaya belum tersedia, '
        'nyatakan keterbatasan data secara eksplisit.'),
    'BAB_V': (
        'Rekap kejadian keselamatan pasien (IKP), klaim, dan risiko: jumlah '
        'kejadian per jenis dan grading, tindak lanjut investigasi, status klaim, '
        'serta risiko yang teridentifikasi pada periode ini.'),
    'BAB_VI': (
        'Kesimpulan dan usulan: simpulkan tingkat capaian mutu periode ini, '
        'usulan prioritas perbaikan periode berikutnya, dan kebutuhan dukungan '
        'manajemen.'),
    'KESIMPULAN': (
        'Simpulkan capaian, penyebab utama masalah, dan usulan tindak lanjut '
        'prioritas beserta penanggung jawab dan tenggatnya.'),
    'PENUTUP': (
        'Penutup laporan: pernyataan bahwa laporan disusun sebagai bagian siklus '
        'penjaminan mutu, ucapan terima kasih kepada pihak yang berkontribusi, '
        'dan harapan tindak lanjut.'),
}

PROMPT_NARASI_LAPORAN = """Konteks Laporan Capaian Indikator Mutu Rumah Sakit:
- Unit Kerja / Lingkup: {unit}
- Periode Laporan: {periode}
- Jenis Laporan: {jenis}
- Bagian yang Diminta: {judul_bab}
- Panduan Isi Bagian: {panduan}
- Statistik Capaian: {statistik}
- Indikator Tidak Tercapai (prioritas analisis): {tidak_tercapai}
- Indikator Tercapai: {tercapai}
- Rekap Insiden Keselamatan Pasien (IKP): {ikp}
- Arahan Tambahan Penyusun: {instruksi}
- Narasi yang Sudah Ada (pertahankan substansinya bila masih relevan): {isi_sekarang}

Tugas: tulis narasi resmi untuk bagian "{judul_bab}" pada laporan di atas.

Aturan:
- Bahasa Indonesia formal perumahsakitan, siap dimasukkan ke dokumen akreditasi.
- Hanya paragraf prosa. TANPA markdown, TANPA bullet, TANPA penomoran, TANPA
  mengulang judul bagian.
- 3 sampai 6 paragraf; tiap paragraf 3–6 kalimat dan mengalir, bukan daftar.
- Gunakan ANGKA dari statistik yang diberikan. Jangan mengarang angka, nama
  orang, atau data yang tidak ada pada konteks.
- Bila data pendukung tidak tersedia, tulis keterbatasannya secara wajar —
  jangan mengisi dengan asumsi.
- Analisis memakai kerangka PDSA (Plan-Do-Study-Act): apa yang direncanakan,
  apa yang dijalankan, apa hasil ukurnya, apa tindak lanjutnya.
- Jangan menyebut nama pasien atau data identitas pribadi apa pun.

Format Output JSON:
{{
  "narasi": "paragraf pertama...\n\nparagraf kedua...\n\nparagraf ketiga..."
}}"""


PROMPT_KONTROL_RINGKASAN = """Anda analis mutu dan keselamatan pasien rumah sakit. Anda menerima RINGKASAN ANGKA satu unit kerja dari dasbor eksekutif. Tugas Anda: menjelaskan apa arti angka itu dan apa yang harus dikerjakan minggu ini.

KONTEKS
- Unit Kerja: {unit_name}
- Portal: {portal_name}
- Tanggal: {tanggal}
- Cakupan data: {scope_note}

ANGKA (satu-satunya sumber yang boleh Anda pakai)
{data_block}

Aturan:
- Bahasa Indonesia formal perumahsakitan, ringkas, tanpa basa-basi.
- Sebut HANYA angka yang ada di blok ANGKA di atas. Bila sebuah bagian tidak
  ada datanya, katakan datanya belum tersedia — jangan menebak, jangan
  mengarang, jangan menghitung sendiri angka baru.
- Okupansi bed dan cakupan EP bersifat RS-wide: jangan menyebutnya sebagai
  angka unit ini.
- "risiko_utama": 3 poin paling mendesak, masing-masing satu kalimat, boleh
  menyebut angka.
- "aksi_minggu_ini": 3 tindakan konkret yang bisa dieksekusi kepala unit,
  kalimat perintah, bukan rencana abstrak.
- "batas_data": satu atau dua kalimat tentang apa yang TIDAK bisa disimpulkan
  dari angka ini (mis. tidak ada data insiden, belum ada catatan indikator).
- Jangan menyebut nama pasien, nama pegawai, atau data identitas apa pun.

Format Output JSON:
{{
  "ringkasan": "2-4 kalimat...",
  "risiko_utama": ["...", "...", "..."],
  "aksi_minggu_ini": ["...", "...", "..."],
  "batas_data": "..."
}}"""


# --- Section G: RINGKASAN INVESTIGASI LANJUTAN (G.4) & RENCANA TINDAK LANJUT (G.5) ---
PROMPT_INVESTIGASI_RTL = """Konteks Evaluasi Risiko Rumah Sakit (STARKES PMKP 7 & 12):
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Pernyataan Masalah: {masalah}
- Data Pendukung / Bukti: {data_pendukung}
- Skor Risiko Awal: {skor} (Dampak {dampak} x Probabilitas {probabilitas}) - Tingkat: {level}
- Metode Evaluasi Mendalam: {metode_evaluasi}
- Uraian Evaluasi Capaian yang Sudah Diisi: {evaluasi_capaian}
- Capaian Indikator Realisasi: {capaian_nilai}
- Target Indikator: {target_capaian}
- Analisis Fishbone yang Sudah Diisi User: {fishbone_terisi}

Tugas: Susun DUA bagian berikut sekaligus, saling konsisten.

BAGIAN 1 - RINGKASAN INVESTIGASI LANJUTAN (untuk kolom G.4):
Tulis narasi investigasi akar masalah yang siap ditempel ke dokumen akreditasi, memakai
5-Whys dan kerangka Fishbone (Manpower, Process/Method, Material, Machine, Environment,
System). Pisahkan penyebab langsung dari akar masalah sistemik. Jangan mengulang kalimat
template; gunakan bahasa faktual khas rumah sakit.

BAGIAN 2 - RENCANA TINDAK LANJUT / RTL (untuk kolom G.5):
Susun RTL yang SMART (Specific, Measurable, Achievable, Relevant, Time-bound), berupa
langkah bernomor yang benar-benar menyelesaikan akar masalah sistemik di Bagian 1 - bukan
sekadar quick fix. Sertakan saran PIC dan tenggat dalam hari.

Format Output JSON (tanpa markdown code block):
{{
  "analisis_investigasi": "1. Kronologi & Dampak: ...\\n2. Analisis 5-Whys: 1) Mengapa ... 2) Mengapa ... 3) Mengapa ... 4) Mengapa ... 5) Akar masalah: ...\\n3. Akar Masalah Sistemik: ...\\n4. Penyebab Langsung: ...\\n5. Kesimpulan Investigasi: ...",
  "fishbone": {{
    "manpower": "Kontributor dari sisi SDM / kompetensi / beban kerja",
    "process": "Kontributor dari sisi metode / SPO / alur kerja",
    "material": "Kontributor dari sisi bahan / sarana / dokumen",
    "machine": "Kontributor dari sisi alat / fasilitas / SIMRS",
    "environment": "Kontributor dari sisi lingkungan kerja / budaya keselamatan",
    "system": "Kontributor dari sisi kebijakan / tata kelola / sistem RS"
  }},
  "akar_masalah_sistemik": "Satu paragraf akar masalah tingkat sistem",
  "verifikasi_efektivitas": "Cara membuktikan perbaikan berhasil (indikator, frekuensi, ambang)",
  "rencana_tindak_lanjut": "1. [Langkah perbaikan konkret]\\n2. [Revisi SPO / sarana]\\n3. [Pelatihan & sosialisasi]\\n4. [Audit kepatuhan berkala]\\n5. [Pelaporan hasil ke Komite Mutu]",
  "pj_saran": "Jabatan PIC yang paling tepat (mis. Kepala Instalasi / Ka. Unit / Komite Mutu)",
  "target_hari": 30,
  "indikator_keberhasilan": "Indikator terukur yang menandakan RTL berhasil",
  "status_rtl_saran": "BELUM / PROSES / SELESAI"
}}"""
