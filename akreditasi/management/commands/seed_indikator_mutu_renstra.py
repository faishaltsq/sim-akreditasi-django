"""
Seed 13 Indikator Mutu Nasional (INM) Kemenkes RI +
36 Indikator Mutu Prioritas RS (IMP-RS) per Bidang Kerja
Sesuai Dokumen Renstra RS Monsiskami 2026–2030.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand

# ── 1. 13 INDIKATOR MUTU NASIONAL (INM) ──────────────────────────────────────
INM_LIST = [
    {
        'kode': 'INM-01',
        'nama': 'Kepatuhan Kebersihan Tangan (KKT)',
        'unit_code': 'KOM-PPI',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah peluang kebersihan tangan yang dilakukan sesuai indikasi (5 momen)',
        'denominator': 'Jumlah seluruh peluang kebersihan tangan yang diamati',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'SKP 5 EP 1',
    },
    {
        'kode': 'INM-02',
        'nama': 'Kepatuhan Penggunaan Alat Pelindung Diri (APD)',
        'unit_code': 'KOM-PPI',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah petugas yang patuh menggunakan APD lengkap sesuai indikasi/area',
        'denominator': 'Jumlah seluruh petugas yang diobservasi dalam penggunaan APD',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 5 EP 2',
    },
    {
        'kode': 'INM-03',
        'nama': 'Kepatuhan Identifikasi Pasien',
        'unit_code': 'KOM-MUTU',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah proses verifikasi identitas (min. 2 identitas) yang dilakukan tepat',
        'denominator': 'Jumlah seluruh proses pelayanan yang diobservasi identifikasi pasiennya',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 1 EP 1',
    },
    {
        'kode': 'INM-04',
        'nama': 'Waktu Tanggap Pelayanan Gawat Darurat (Emergency Response Time <= 5 Menit)',
        'unit_code': 'IGD',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien gawat darurat yang dilayani dokter <= 5 menit sejak tiba',
        'denominator': 'Jumlah seluruh pasien gawat darurat yang datang ke IGD',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'ARK 1 EP 1',
    },
    {
        'kode': 'INM-05',
        'nama': 'Penundaan Operasi Elektif (<= 5%)',
        'unit_code': 'IBS',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah pasien operasi elektif yang mengalami penundaan jadwal > 1 jam',
        'denominator': 'Jumlah seluruh pasien yang dijadwalkan operasi elektif',
        'target': Decimal('5.00'),
        'satuan': '%',
        'ep_code': 'PAB 7 EP 1',
    },
    {
        'kode': 'INM-06',
        'nama': 'Waktu Tunggu Rawat Jalan (<= 60 Menit)',
        'unit_code': 'IRJ',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien rawat jalan dengan waktu tunggu dokter <= 60 menit',
        'denominator': 'Jumlah seluruh pasien rawat jalan yang disurvei',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'ARK 2 EP 1',
    },
    {
        'kode': 'INM-07',
        'nama': 'Kepatuhan Pertimbangan Formularium Nasional / RS',
        'unit_code': 'FARM',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah item obat yang diresepkan sesuai Formularium Nasional / Formularium RS',
        'denominator': 'Jumlah seluruh item obat yang diresepkan DPJP',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'PKPO 2 EP 1',
    },
    {
        'kode': 'INM-08',
        'nama': 'Kepatuhan Terhadap Clinical Pathway',
        'unit_code': 'KOM-MED',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah kasus dari 5 diagnosis prioritas yang penatalaksanaannya sesuai Clinical Pathway',
        'denominator': 'Jumlah seluruh kasus dari 5 diagnosis prioritas yang diaudit',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'TKRS 5 EP 1',
    },
    {
        'kode': 'INM-09',
        'nama': 'Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh',
        'unit_code': 'KOM-KEP',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah pasien berisiko jatuh yang dipasang penanda risiko jatuh & intervensi tepat',
        'denominator': 'Jumlah seluruh pasien rawat inap yang berisiko jatuh hasil asesmen',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 6 EP 1',
    },
    {
        'kode': 'INM-10',
        'nama': 'Kecepatan Waktu Tanggap Komplain (< 24 Jam)',
        'unit_code': 'HUMAS-CS',
        'dimensi': 'BERPUSAT_PASIEN',
        'numerator': 'Jumlah komplain (keluhan) pasien/keluarga yang ditindaklanjuti < 24 jam',
        'denominator': 'Jumlah seluruh komplain yang masuk ke RS',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'HPK 1 EP 1',
    },
    {
        'kode': 'INM-11',
        'nama': 'Kepuasan Pasien dan Keluarga (Indeks Kepuasan Masyarakat / IKM)',
        'unit_code': 'HUMAS-CS',
        'dimensi': 'BERPUSAT_PASIEN',
        'numerator': 'Nilai total skor survei kepuasan pasien yang dikonversi ke skala 100',
        'denominator': 'Total responden survei kepuasan pasien',
        'target': Decimal('88.00'),
        'satuan': '%',
        'ep_code': 'PMKP 4 EP 1',
    },
    {
        'kode': 'INM-12',
        'nama': 'Kepatuhan Pelaporan Hasil Kritis Laboratorium (< 15 Menit)',
        'unit_code': 'LAB',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah hasil kritis laboratorium yang dilaporkan ke DPJP/ruangan < 15 menit',
        'denominator': 'Jumlah seluruh hasil kritis laboratorium yang teridentifikasi',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 2 EP 2',
    },
    {
        'kode': 'INM-13',
        'nama': 'Kepatuhan Penggunaan Komunikasi SBAR / TBK Saat Serah Terima Pasien',
        'unit_code': 'KOM-KEP',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah serah terima pasien (handover antar shift/unit) menggunakan format SBAR/TBK',
        'denominator': 'Jumlah seluruh proses serah terima pasien yang diobservasi',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 2 EP 1',
    },
]

# ── 2. INDIKATOR MUTU PRIORITAS RS (IMP-RS) PER BIDANG ───────────────────────
IMP_RS_LIST = [
    # ── Bidang 1: Pelayanan Medis & Keperawatan ──
    # A. UGD
    {
        'kode': 'IMP-UGD-01',
        'nama': 'Waktu Tanggap Pelayanan Dokter UGD (< 5 Menit Sejak Pasien Tiba)',
        'unit_code': 'IGD',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien gawat darurat yang mendapat asesmen dokter < 5 menit',
        'denominator': 'Jumlah seluruh kunjungan pasien di UGD',
        'target': Decimal('90.00'),
        'satuan': '%',
        'ep_code': 'ARK 1 EP 1',
    },
    {
        'kode': 'IMP-UGD-02',
        'nama': 'Angka Pasien Length of Stay (LOS) di UGD (< 6 Jam Sebelum Decision)',
        'unit_code': 'IGD',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah pasien UGD dengan lama tinggal < 6 jam hingga transfer/pulang',
        'denominator': 'Jumlah seluruh pasien yang diobservasi di UGD',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'ARK 1 EP 2',
    },
    {
        'kode': 'IMP-UGD-03',
        'nama': 'Angka Kematian Pasien di UGD (<= 24 Jam)',
        'unit_code': 'IGD',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah pasien meninggal di UGD dalam kurun waktu <= 24 jam',
        'denominator': 'Jumlah seluruh pasien rawat darurat (per mil / 1000 pasien)',
        'target': Decimal('2.00'),
        'satuan': '‰',
        'ep_code': 'ARK 1 EP 3',
    },

    # B. Rawat Inap
    {
        'kode': 'IMP-RANAP-01',
        'nama': 'Angka Kejadian Re-admisi Pasien Diagnosis Sama (< 30 Hari)',
        'unit_code': 'IRIN',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah pasien yang masuk rawat inap kembali dengan diagnosis sama < 30 hari',
        'denominator': 'Jumlah seluruh pasien rawat inap keluar hidup dalam periode yang sama',
        'target': Decimal('3.00'),
        'satuan': '%',
        'ep_code': 'ARK 3 EP 1',
    },
    {
        'kode': 'IMP-RANAP-02',
        'nama': 'Angka Kejadian Dekubitus Baru pada Pasien Tirah Baring Selama Perawatan',
        'unit_code': 'IRIN',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah pasien tirah baring yang mengalami dekubitus baru selama masa rawat',
        'denominator': 'Jumlah seluruh pasien tirah baring yang dirawat inap',
        'target': Decimal('0.00'),
        'satuan': '%',
        'ep_code': 'SKP 6 EP 1',
    },
    {
        'kode': 'IMP-RANAP-03',
        'nama': 'Kepatuhan Pengisian RME Lengkap < 24 Jam Pasca DPJP Visite',
        'unit_code': 'IRIN',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah berkas RME yang diisi lengkap CPPT & instruksi < 24 jam setelah visite',
        'denominator': 'Jumlah seluruh visite DPJP di rawat inap yang diaudit',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'MRMIK 4 EP 1',
    },

    # C. Rawat Jalan (Poliklinik)
    {
        'kode': 'IMP-IRJ-01',
        'nama': 'Waktu Tunggu Pelayanan Poliklinik Spesialis (<= 60 Menit)',
        'unit_code': 'IRJ',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien poliklinik spesialis dengan waktu tunggu <= 60 menit',
        'denominator': 'Jumlah seluruh sampel pasien poliklinik yang disurvei',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'ARK 2 EP 1',
    },
    {
        'kode': 'IMP-IRJ-02',
        'nama': 'Kepatuhan Edukasi Informasi Obat dan Perawatan pada Pasien Pulang',
        'unit_code': 'IRJ',
        'dimensi': 'BERPUSAT_PASIEN',
        'numerator': 'Jumlah pasien rawat jalan yang mendapatkan edukasi obat terintegrasi tercatat',
        'denominator': 'Jumlah seluruh pasien rawat jalan yang menerima resep obat',
        'target': Decimal('95.00'),
        'satuan': '%',
        'ep_code': 'KE 4 EP 1',
    },
    {
        'kode': 'IMP-IRJ-03',
        'nama': 'Angka Pembatalan Perjanjian Dokter Spesialis Tanpa Pemberitahuan H-1',
        'unit_code': 'IRJ',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah pembatalan jadwal praktek dokter spesialis tanpa pemberitahuan H-1',
        'denominator': 'Jumlah seluruh jadwal praktek dokter spesialis dalam sebulan',
        'target': Decimal('2.00'),
        'satuan': '%',
        'ep_code': 'TKRS 9 EP 1',
    },

    # D. Kamar Bedah Sentral (IBS)
    {
        'kode': 'IMP-IBS-01',
        'nama': 'Kepatuhan Pengisian Surgical Safety Checklist (SSC WHO) Lengkap',
        'unit_code': 'IBS',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah operasi dengan formulir SSC terisi lengkap (Sign In, Time Out, Sign Out)',
        'denominator': 'Jumlah seluruh operasi yang dilakukan di Kamar Operasi',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'PAB 8 EP 1',
    },
    {
        'kode': 'IMP-IBS-02',
        'nama': 'Angka Kejadian Infeksi Daerah Operasi (IDO)',
        'unit_code': 'IBS',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah pasien operasi bersih/bersih tercemar yang mengalami IDO dalam 30 hari',
        'denominator': 'Jumlah seluruh pasien yang menjalani operasi bersih/bersih tercemar',
        'target': Decimal('1.50'),
        'satuan': '%',
        'ep_code': 'PPI 7 EP 1',
    },
    {
        'kode': 'IMP-IBS-03',
        'nama': 'Kepatuhan Pelaksanaan Verbal Time Out Sebelum Insisi Bedah',
        'unit_code': 'IBS',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah tindakan bedah yang melakukan Time Out secara verbal bersama tim lengkap',
        'denominator': 'Jumlah seluruh tindakan bedah di Kamar Bedah Sentral',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'SKP 4 EP 1',
    },

    # E. Intensive Care Unit (ICU/ICCU/NICU/PICU)
    {
        'kode': 'IMP-ICU-01',
        'nama': 'Angka Kejadian Ventilator-Associated Pneumonia (VAP)',
        'unit_code': 'INTENSIF',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah kasus VAP pada pasien yang terpasang ventilator mekanik',
        'denominator': 'Jumlah hari pemasangan ventilator mekanik (ventilator-days) per mil (‰)',
        'target': Decimal('5.00'),
        'satuan': '‰',
        'ep_code': 'PPI 7 EP 1',
    },
    {
        'kode': 'IMP-ICU-02',
        'nama': 'Angka Kejadian Infeksi Saluran Kemih (ISK) Akibat Kateter Urin Menetap',
        'unit_code': 'INTENSIF',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah kasus ISK pada pasien ICU yang terpasang kateter urin menetap',
        'denominator': 'Jumlah hari pemasangan kateter urin (catheter-days) per mil (‰)',
        'target': Decimal('4.70'),
        'satuan': '‰',
        'ep_code': 'PPI 7 EP 1',
    },
    {
        'kode': 'IMP-ICU-03',
        'nama': 'Rerata Waktu Pindah Pasien dari ICU ke Bangsal Pasca Instruksi DPJP (< 2 Jam)',
        'unit_code': 'INTENSIF',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien stabil pasca-ICU yang dipindahkan ke bangsal dalam < 2 jam',
        'denominator': 'Jumlah seluruh pasien ICU yang dinyatakan boleh pindah oleh DPJP',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'ARK 4 EP 1',
    },

    # ── Bidang 2: Penunjang Medis ──
    # A. Instalasi Farmasi
    {
        'kode': 'IMP-FARM-01',
        'nama': 'Waktu Tunggu Pelayanan Obat Jadi (<= 30 Menit)',
        'unit_code': 'FARM',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah resep obat jadi yang selesai dilayani dalam waktu <= 30 menit',
        'denominator': 'Jumlah seluruh lembar resep obat jadi yang dilayani di farmasi rawat jalan',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'PKPO 4 EP 1',
    },
    {
        'kode': 'IMP-FARM-02',
        'nama': 'Waktu Tunggu Pelayanan Obat Racikan (<= 60 Menit)',
        'unit_code': 'FARM',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah resep obat racikan yang selesai dilayani dalam waktu <= 60 menit',
        'denominator': 'Jumlah seluruh lembar resep racikan yang dilayani di farmasi rawat jalan',
        'target': Decimal('80.00'),
        'satuan': '%',
        'ep_code': 'PKPO 4 EP 1',
    },
    {
        'kode': 'IMP-FARM-03',
        'nama': 'Angka Kejadian Medication Error (KNC / KTC / KTD Kesalahan Pemberian Obat)',
        'unit_code': 'FARM',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah insiden medication error pada tahap dispensing dan administrasi obat',
        'denominator': 'Jumlah seluruh resep yang dilayani instalasi farmasi',
        'target': Decimal('0.00'),
        'satuan': '%',
        'ep_code': 'PKPO 6 EP 1',
    },

    # B. Instalasi Laboratorium & Bank Darah
    {
        'kode': 'IMP-LAB-01',
        'nama': 'Waktu Tunggu Hasil Pemeriksaan Laboratorium Cito (<= 60 Menit)',
        'unit_code': 'LAB',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pemeriksaan lab cito yang hasilnya keluar dalam waktu <= 60 menit',
        'denominator': 'Jumlah seluruh permintaan pemeriksaan laboratorium berstatus cito',
        'target': Decimal('90.00'),
        'satuan': '%',
        'ep_code': 'PP 5 EP 1',
    },
    {
        'kode': 'IMP-LAB-02',
        'nama': 'Angka Kerusakan / Penolakan Spesimen Darah (Sample Rejection Rate <= 0,5%)',
        'unit_code': 'LAB',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah spesimen darah yang ditolak (lisis, beku, volume kurang, salah tabung)',
        'denominator': 'Jumlah seluruh spesimen darah yang diterima instalasi laboratorium',
        'target': Decimal('0.50'),
        'satuan': '%',
        'ep_code': 'PP 5 EP 2',
    },
    {
        'kode': 'IMP-LAB-03',
        'nama': 'Ketersediaan Stok Darah Aman dan Siap Pakai di Bank Darah RS',
        'unit_code': 'LAB',
        'dimensi': 'AKSESIBEL',
        'numerator': 'Jumlah permintaan darah dari ruangan yang terpenuhi tepat waktu tanpa kekosongan',
        'denominator': 'Jumlah seluruh permintaan darah yang diajukan ke Bank Darah RS',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'PP 6 EP 1',
    },

    # C. Instalasi Radiologi & Diagnostic Imaging
    {
        'kode': 'IMP-RAD-01',
        'nama': 'Waktu Tunggu Hasil Ekspertise Foto Thorax Cito (<= 30 Menit)',
        'unit_code': 'RAD',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah foto thorax cito yang ekspertisenya selesai diverifikasi Spesialis Rad <= 30 menit',
        'denominator': 'Jumlah seluruh pemeriksaan foto thorax berstatus cito',
        'target': Decimal('90.00'),
        'satuan': '%',
        'ep_code': 'PP 7 EP 1',
    },
    {
        'kode': 'IMP-RAD-02',
        'nama': 'Angka Kegagalan / Pengulangan Foto Radiologi (Reject Rate <= 2%)',
        'unit_code': 'RAD',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah eksposure foto rontgen yang diulang karena kesalahan teknis/posisi',
        'denominator': 'Jumlah seluruh pemeriksaan eksposure foto radiologi yang dilakukan',
        'target': Decimal('2.00'),
        'satuan': '%',
        'ep_code': 'PP 7 EP 2',
    },
    {
        'kode': 'IMP-RAD-03',
        'nama': 'Kepatuhan Pemakaian Dosimeter Saku / TLD oleh Petugas Radiasi',
        'unit_code': 'RAD',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah petugas radiasi yang patuh memakai dosimeter personal saat bekerja',
        'denominator': 'Jumlah seluruh staf radiasi yang bertugas dalam periode audit',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'MFK 4 EP 1',
    },

    # D. Instalasi Rekam Medis & SIMRS
    {
        'kode': 'IMP-RM-01',
        'nama': 'Ketersediaan Berkas RME / Dokumen Pasien Saat Pelayanan Poliklinik',
        'unit_code': 'REKAM-MEDIS',
        'dimensi': 'AKSESIBEL',
        'numerator': 'Jumlah pasien poliklinik yang berkas RME-nya siap diakses saat dokter mulai periksa',
        'denominator': 'Jumlah seluruh pasien yang mendaftar di poliklinik spesialis',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'MRMIK 3 EP 1',
    },
    {
        'kode': 'IMP-RM-02',
        'nama': 'Waktu Penyelesaian Resume Medis Pasien Pulang Rawat Inap (<= 24 Jam)',
        'unit_code': 'REKAM-MEDIS',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah pasien pulang rawat inap dengan resume medis lengkap ditandatangani <= 24 jam',
        'denominator': 'Jumlah seluruh pasien rawat inap yang dipulangkan dalam periode tersebut',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'MRMIK 4 EP 1',
    },
    {
        'kode': 'IMP-RM-03',
        'nama': 'Tingkat Keandalan dan Ketersediaan (Uptime) Server SIMRS (>= 99,5%)',
        'unit_code': 'REKAM-MEDIS',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah jam operasional server SIMRS tanpa downtime (unplanned outage)',
        'denominator': 'Total jam operasional 24/7 dalam satu bulan (720 jam)',
        'target': Decimal('99.50'),
        'satuan': '%',
        'ep_code': 'MRMIK 1 EP 1',
    },

    # E. Instalasi Gizi
    {
        'kode': 'IMP-GIZI-01',
        'nama': 'Ketepatan Waktu Pendistribusian Makanan Pasien Rawat Inap',
        'unit_code': 'GIZI',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah porsi makanan pasien yang tiba di bangsal tepat waktu sesuai jadwal makan',
        'denominator': 'Jumlah seluruh porsi makanan yang didistribusikan dalam periode observasi',
        'target': Decimal('95.00'),
        'satuan': '%',
        'ep_code': 'PAP 2 EP 1',
    },
    {
        'kode': 'IMP-GIZI-02',
        'nama': 'Angka Sisa Makanan Yang Tidak Dimakan Pasien Rawat Inap (Food Waste <= 20%)',
        'unit_code': 'GIZI',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah porsi makanan yang bersisa > 20% pada piring/ompreng pasien',
        'denominator': 'Jumlah seluruh porsi makanan pasien yang disurvei sisa makannya',
        'target': Decimal('20.00'),
        'satuan': '%',
        'ep_code': 'PAP 2 EP 2',
    },
    {
        'kode': 'IMP-GIZI-03',
        'nama': 'Angka Kejadian Kesalahan Pemberian Diet Pasien Rawat Inap',
        'unit_code': 'GIZI',
        'dimensi': 'AMAN',
        'numerator': 'Jumlah kejadian salah menu / salah etiket diet pasien rawat inap yang terkirim',
        'denominator': 'Jumlah seluruh porsi diet yang disajikan oleh instalasi gizi',
        'target': Decimal('0.00'),
        'satuan': '%',
        'ep_code': 'SKP 1 EP 1',
    },

    # ── Bidang 3: Manajemen, Finansial & Umum ──
    # A. Keuangan & Casemix
    {
        'kode': 'IMP-KEU-01',
        'nama': 'Rerata Waktu Penyerahan Berkas Klaim BPJS ke Verifikator (<= 10 Hari Kerja)',
        'unit_code': 'BAG-KEU',
        'dimensi': 'TEPAT_WAKTU',
        'numerator': 'Jumlah bulan pelayanan yang berkas klaim BPJS diserahkan <= 10 hari pasca-bulan',
        'denominator': 'Jumlah bulan penagihan klaim BPJS dalam satu tahun anggaran (12 bulan)',
        'target': Decimal('100.00'),
        'satuan': '%',
        'ep_code': 'TKRS 9 EP 1',
    },
    {
        'kode': 'IMP-KEU-02',
        'nama': 'Angka Pengembalian Berkas Klaim BPJS (Pending Claim Rate <= 3%)',
        'unit_code': 'BAG-KEU',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah berkas klaim BPJS yang dikembalikan (pending/dispute) oleh verifikator',
        'denominator': 'Jumlah seluruh berkas klaim BPJS yang diajukan dalam bulan penagihan',
        'target': Decimal('3.00'),
        'satuan': '%',
        'ep_code': 'TKRS 9 EP 2',
    },
    {
        'kode': 'IMP-KEU-03',
        'nama': 'Rerata Turnaround Time (TAT) Pencairan Klaim Asuransi Swasta / Perusahaan (<= 14 Hari)',
        'unit_code': 'BAG-KEU',
        'dimensi': 'EFISIEN',
        'numerator': 'Jumlah klaim asuransi swasta yang cair dalam waktu <= 14 hari sejak penagihan',
        'denominator': 'Jumlah seluruh klaim asuransi swasta yang diajukan dalam periode audit',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'TKRS 9 EP 1',
    },

    # B. Bagian Sumber Daya Manusia (SDM) & Pelatihan
    {
        'kode': 'IMP-SDM-01',
        'nama': 'Rerata Jam Pelatihan per Pegawai per Tahun (>= 20 Jam / Pegawai / Tahun)',
        'unit_code': 'BAG-SDM',
        'dimensi': 'EFEKTIF',
        'numerator': 'Total akumulasi jam diklat seluruh staf RS Monsiskami dalam satu tahun',
        'denominator': 'Jumlah seluruh pegawai aktif di RS Monsiskami',
        'target': Decimal('20.00'),
        'satuan': 'Jam',
        'ep_code': 'KPS 8 EP 1',
    },
    {
        'kode': 'IMP-SDM-02',
        'nama': 'Tingkat Kepuasan Karyawan (Employee Satisfaction Index >= 85%)',
        'unit_code': 'BAG-SDM',
        'dimensi': 'BERPUSAT_PASIEN',
        'numerator': 'Skor kumulatif hasil survei kepuasan karyawan (skala 100)',
        'denominator': 'Jumlah total karyawan yang mengisi survei kepuasan tahunan',
        'target': Decimal('85.00'),
        'satuan': '%',
        'ep_code': 'KPS 1 EP 1',
    },
    {
        'kode': 'IMP-SDM-03',
        'nama': 'Tingkat Retensi Dokter Spesialis dan Perawat Utama (>= 90%)',
        'unit_code': 'BAG-SDM',
        'dimensi': 'EFEKTIF',
        'numerator': 'Jumlah dokter spesialis dan perawat utama yang bertahan kerja >= 1 tahun',
        'denominator': 'Jumlah seluruh dokter spesialis dan perawat utama yang bekerja pada awal tahun',
        'target': Decimal('90.00'),
        'satuan': '%',
        'ep_code': 'KPS 1 EP 2',
    },
]


class Command(BaseCommand):
    help = 'Seed 13 INM Kemenkes + 36 IMP-RS per Bidang Kerja sesuai Renstra 2026-2030'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja, StandardItem
        from akreditasi.risiko_models import IndikatorMutu

        self.stdout.write(self.style.SUCCESS('\n=== SEED INDIKATOR MUTU RENSTRA 2026–2030 ==='))

        # Cache units
        unit_map = {u.code: u for u in UnitKerja.objects.all()}

        # ── 1. Seed 13 INM ──
        inm_created = 0
        for item in INM_LIST:
            unit = unit_map.get(item['unit_code'])
            ep = StandardItem.objects.filter(code=item['ep_code']).first()

            obj, created = IndikatorMutu.objects.update_or_create(
                kode_indikator=item['kode'],
                defaults={
                    'nama_indikator': item['nama'],
                    'unit': unit,
                    'jenis': 'NASIONAL',
                    'dimensi_mutu': item['dimensi'],
                    'numerator': item['numerator'],
                    'denominator': item['denominator'],
                    'target_nilai': item['target'],
                    'satuan': item['satuan'],
                    'ep_terkait': ep,
                    'aktif': True,
                }
            )
            if created:
                inm_created += 1
            status = 'dibuat' if created else 'diupdate'
            self.stdout.write(f"  {status}: [{item['kode']}] {item['nama'][:60]}")

        self.stdout.write(f"  ✔ 13 Indikator Mutu Nasional (INM) siap ({inm_created} baru)")

        # ── 2. Seed 36 IMP-RS ──
        imp_created = 0
        for item in IMP_RS_LIST:
            unit = unit_map.get(item['unit_code'])
            if not unit:
                # Coba fallback ke prefix
                for code, u in unit_map.items():
                    if code.startswith(item['unit_code']):
                        unit = u
                        break

            ep = StandardItem.objects.filter(code=item['ep_code']).first()

            obj, created = IndikatorMutu.objects.update_or_create(
                kode_indikator=item['kode'],
                defaults={
                    'nama_indikator': item['nama'],
                    'unit': unit,
                    'jenis': 'IMP_RS',
                    'dimensi_mutu': item['dimensi'],
                    'numerator': item['numerator'],
                    'denominator': item['denominator'],
                    'target_nilai': item['target'],
                    'satuan': item['satuan'],
                    'ep_terkait': ep,
                    'aktif': True,
                }
            )
            if created:
                imp_created += 1
            status = 'dibuat' if created else 'diupdate'
            self.stdout.write(f"  {status}: [{item['kode']}] {item['nama'][:60]}")

        self.stdout.write(f"  ✔ 36 Indikator Mutu Rumah Sakit (IMP-RS) siap ({imp_created} baru)")
        self.stdout.write(self.style.SUCCESS(f"\n✅ Total Indikator Mutu di Database: {IndikatorMutu.objects.count()} (13 INM + 36 IMP-RS)"))
