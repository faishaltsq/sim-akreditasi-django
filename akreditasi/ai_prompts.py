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

PROMPT_EVALUASI_RISIKO = """Konteks Evaluasi Risiko Berkala:
- Unit Kerja: {unit_name}
- Jenis Risiko: {jenis_risiko}
- Deskripsi Awal: {deskripsi_risiko}
- Skor Awal: {skor_awal} (Dampak {dampak_awal} × Probabilitas {prob_awal})
- Rencana Mitigasi yang Sudah Dijalankan: {mitigasi_terlaksana}
- Dampak Residual (Sisa): {dampak_residual}/5
- Probabilitas Residual: {prob_residual}/5
- Status Saat Ini: {status}

Tugas: Evaluasi efektivitas mitigasi dan berikan rekomendasi tindak lanjut.

Format Output JSON:
{{
  "efektivitas": "Efektif / Sebagian Efektif / Belum Efektif",
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
