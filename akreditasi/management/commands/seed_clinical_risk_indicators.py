"""
Seed Indikator Mutu Klinis & Register Risiko Klinis untuk 9 Unit Pelayanan RS.

Sumber data: `Tolong ini diinputkan indicator resiko klinis.docx`
- 9 unit: IGD, ICU, ICCU, Rawat Jalan, Rawat Inap, HD, Laboratorium, VK, OK
- Setiap unit: 5 risiko klinis spesifik + indikator mutu (INM / IMP-RS / IMP-Unit)
- Masalah & data pendukung diambil langsung dari dokumen operasional RS.

Idempoten: aman dijalankan berulang kali (get_or_create / update_or_create).

Jalankan: python manage.py seed_clinical_risk_indicators
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from akreditasi.models import UnitKerja, StandardItem
from akreditasi.risiko_models import IndikatorMutu, RisikoUnit


# ─────────────────────────────────────────────────────────────────────────────
# INDIKATOR MUTU PER UNIT (kode, nama, jenis, dimensi, target, satuan)
# Kode INM-xx merujuk indikator nasional yang sudah ada (link saja, tidak dibuat ulang)
# ─────────────────────────────────────────────────────────────────────────────

INDIKATOR_NEW = [
    # ── IGD ──────────────────────────────────────────────────────────────────
    dict(kode='IMP-RS-IGD-01', unit='IGD', jenis='IMP_RS',
         nama='Kepatuhan Response Time Triase ≤ 5 Menit',
         dimensi='TEPAT_WAKTU', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah pasien gawat darurat dengan response time triase ≤ 5 menit',
         denominator='Jumlah seluruh pasien gawat darurat yang datang ke IGD',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-IGD-01', unit='IGD', jenis='IMP_UNIT',
         nama='Kepatuhan Door-to-ECG Pasien Nyeri Dada < 10 Menit',
         dimensi='TEPAT_WAKTU', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah pasien nyeri dada dengan Door-to-ECG < 10 menit',
         denominator='Jumlah seluruh pasien nyeri dada yang terdiagnosis STEMI/NSTEMI',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-IGD-02', unit='IGD', jenis='IMP_UNIT',
         nama='Angka Kejadian Unplanned Re-attendance IGD ≤ 24 Jam',
         dimensi='EFEKTIF', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah pasien kembali ke IGD < 24 jam dengan kondisi memburuk tanpa rencana',
         denominator='Jumlah seluruh kunjungan pasien IGD pada periode yang sama',
         ep='ARK 1 EP 1'),

    # ── ICU ──────────────────────────────────────────────────────────────────
    dict(kode='IMP-RS-ICU-01', unit='ICU', jenis='IMP_RS',
         nama='Kepatuhan Penggunaan APD',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah petugas yang patuh menggunakan APD lengkap sesuai indikasi',
         denominator='Jumlah seluruh petugas yang diobservasi penggunaan APD-nya',
         ep='SKP 5 EP 2'),
    dict(kode='IMP-UNIT-ICU-01', unit='ICU', jenis='IMP_UNIT',
         nama='Angka Kejadian VAP (≤ 2,5‰ hari pemakaian ventilator)',
         dimensi='AMAN', target=Decimal('2.50'), satuan='‰',
         numerator='Jumlah kejadian VAP (Ventilator-Associated Pneumonia) di ruang ICU',
         denominator='Jumlah hari pemakaian ventilator × 1000',
         ep='SKP 5 EP 1'),
    dict(kode='IMP-UNIT-ICU-02', unit='ICU', jenis='IMP_UNIT',
         nama='Angka Kejadian IADP (≤ 3,5‰ hari pemasangan kateter)',
         dimensi='AMAN', target=Decimal('3.50'), satuan='‰',
         numerator='Jumlah kejadian Infeksi Aliran Darah Primer (IADP)',
         denominator='Jumlah hari pemasangan kateter vena sentral × 1000',
         ep='SKP 5 EP 1'),
    dict(kode='IMP-UNIT-ICU-03', unit='ICU', jenis='IMP_UNIT',
         nama='Angka Pasien Unplanned Readmission ke ICU < 48 Jam',
         dimensi='EFEKTIF', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah pasien yang dirawat kembali ke ICU < 48 jam pasca keluar ICU',
         denominator='Jumlah seluruh pasien yang keluar dari ICU pada periode yang sama',
         ep='ARK 1 EP 1'),

    # ── ICCU ─────────────────────────────────────────────────────────────────
    dict(kode='IMP-RS-ICCU-01', unit='ICCU', jenis='IMP_RS',
         nama='Kepatuhan Komunikasi Efektif (SBAR/TBAK) saat Handover',
         dimensi='EFEKTIF', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah serah terima pasien yang menggunakan komunikasi SBAR/TBAK lengkap',
         denominator='Jumlah seluruh serah terima pasien yang diobservasi',
         ep='SKP 3 EP 1'),
    dict(kode='IMP-UNIT-ICCU-01', unit='ICCU', jenis='IMP_UNIT',
         nama='Kepatuhan Double Check Pemberian Obat High-Alert (100%)',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah pemberian obat high-alert dengan double check terdokumentasi',
         denominator='Jumlah seluruh pemberian obat high-alert yang diobservasi',
         ep='SKP 4 EP 1'),
    dict(kode='IMP-UNIT-ICCU-02', unit='ICCU', jenis='IMP_UNIT',
         nama='Angka Kejadian Re-Infark Selama Masa Perawatan ICCU',
         dimensi='EFEKTIF', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah pasien yang mengalami re-infark/iskemia berulang di ICCU',
         denominator='Jumlah seluruh pasien dengan diagnosis sindrom koroner akut di ICCU',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-ICCU-03', unit='ICCU', jenis='IMP_UNIT',
         nama='Angka Keberhasilan Resusitasi Jantung Paru (RJP) / ROSC',
         dimensi='EFEKTIF', target=Decimal('50.00'), satuan='%',
         numerator='Jumlah pasien cardiac arrest dengan kembalinya sirkulasi spontan (ROSC)',
         denominator='Jumlah seluruh pasien cardiac arrest yang dilakukan RJP',
         ep='ARK 1 EP 1'),

    # ── Rawat Jalan ──────────────────────────────────────────────────────────
    dict(kode='IMP-RS-RAJAL-01', unit='RAJAL', jenis='IMP_RS',
         nama='Kepatuhan Waktu Tunggu Rawat Jalan ≤ 60 Menit',
         dimensi='TEPAT_WAKTU', target=Decimal('80.00'), satuan='%',
         numerator='Jumlah pasien rawat jalan dengan waktu tunggu ≤ 60 menit',
         denominator='Jumlah seluruh pasien rawat jalan yang diobservasi waktu tunggunya',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-RAJAL-01', unit='RAJAL', jenis='IMP_UNIT',
         nama='Kepatuhan Penilaian & Tindak Lanjut Risiko Jatuh Pasien Poliklinik',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah pasien poliklinik dengan asesmen risiko jatuh & tindak lanjut',
         denominator='Jumlah seluruh pasien poliklinik yang berisiko jatuh',
         ep='SKP 6 EP 1'),
    dict(kode='IMP-UNIT-RAJAL-02', unit='RAJAL', jenis='IMP_UNIT',
         nama='Angka Resep Obat Zero Error di Rawat Jalan',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah resep tanpa kesalahan penulisan/pembacaan',
         denominator='Jumlah seluruh resep yang diterbitkan di rawat jalan',
         ep='SKP 4 EP 1'),

    # ── Rawat Inap ───────────────────────────────────────────────────────────
    dict(kode='IMP-RS-RANAP-01', unit='RANAP', jenis='IMP_RS',
         nama='Kepatuhan Kebersihan Tangan Petugas Rawat Inap',
         dimensi='AMAN', target=Decimal('85.00'), satuan='%',
         numerator='Jumlah peluang kebersihan tangan yang dilakukan sesuai 5 momen',
         denominator='Jumlah seluruh peluang kebersihan tangan yang diamati',
         ep='SKP 5 EP 1'),
    dict(kode='IMP-UNIT-RANAP-01', unit='RANAP', jenis='IMP_UNIT',
         nama='Kepatuhan Pelaksanaan EWS (Early Warning System) saat Perburukan',
         dimensi='TEPAT_WAKTU', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah pasien dengan skor EWS meningkat yang ditindaklanjuti sesuai SPO',
         denominator='Jumlah seluruh pasien dengan peningkatan skor EWS',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-RANAP-02', unit='RANAP', jenis='IMP_UNIT',
         nama='Angka Kejadian Phlebitis (≤ 1,5‰ hari pemasangan)',
         dimensi='AMAN', target=Decimal('1.50'), satuan='‰',
         numerator='Jumlah kejadian phlebitis pada area pemasangan infus intravena',
         denominator='Jumlah hari pemasangan infus intravena × 1000',
         ep='SKP 5 EP 1'),

    # ── HD (Hemodialisa) ─────────────────────────────────────────────────────
    dict(kode='IMP-RS-HD-01', unit='HD', jenis='IMP_RS',
         nama='Kepatuhan Penggunaan APD Lengkap Petugas HD',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah petugas HD yang menggunakan APD lengkap saat tindakan dialisis',
         denominator='Jumlah seluruh petugas HD yang diobservasi',
         ep='SKP 5 EP 2'),
    dict(kode='IMP-UNIT-HD-01', unit='HD', jenis='IMP_UNIT',
         nama='Angka Kejadian Hipotensi Intradialitik Berat',
         dimensi='AMAN', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah kejadian hipotensi berat saat dialisis (TDS < 90 mmHg + gejala)',
         denominator='Jumlah seluruh sesi hemodialisa pada periode yang sama',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-HD-02', unit='HD', jenis='IMP_UNIT',
         nama='Angka Kejadian Infeksi pada Akses Vaskular Pasien HD',
         dimensi='AMAN', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah kejadian infeksi pada akses vaskular (AV Fistula/CDL)',
         denominator='Jumlah seluruh pasien HD aktif dengan akses vaskular',
         ep='SKP 5 EP 1'),

    # ── Laboratorium ─────────────────────────────────────────────────────────
    dict(kode='IMP-UNIT-LAB-01', unit='LAB', jenis='IMP_UNIT',
         nama='Angka Kejadian Salah / Tertukar Label Spesimen (0%)',
         dimensi='AMAN', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah spesimen dengan label salah/tertukar',
         denominator='Jumlah seluruh spesimen yang diterima laboratorium',
         ep='SKP 1 EP 1'),
    dict(kode='IMP-UNIT-LAB-02', unit='LAB', jenis='IMP_UNIT',
         nama='Angka Kontaminasi Kultur Darah (≤ 3%)',
         dimensi='EFEKTIF', target=Decimal('3.00'), satuan='%',
         numerator='Jumlah spesimen kultur darah yang terkontaminasi',
         denominator='Jumlah seluruh spesimen kultur darah yang diperiksa',
         ep='SKP 5 EP 1'),

    # ── VK (Kamar Bersalin) ──────────────────────────────────────────────────
    dict(kode='IMP-RS-VK-01', unit='VK', jenis='IMP_RS',
         nama='Waktu Tanggap (Response Time) SC Emergensi ≤ 30 Menit',
         dimensi='TEPAT_WAKTU', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah SC emergensi dengan waktu keputusan-tindakan ≤ 30 menit',
         denominator='Jumlah seluruh tindakan SC emergensi (cito)',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-VK-01', unit='VK', jenis='IMP_UNIT',
         nama='Angka Kejadian Penanganan Pendarahan Postpartum Sesuai SPO',
         dimensi='EFEKTIF', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah kasus HPP yang ditangani sesuai SPO PONEK',
         denominator='Jumlah seluruh kasus HPP yang terjadi di VK',
         ep='ARK 1 EP 1'),
    dict(kode='IMP-UNIT-VK-02', unit='VK', jenis='IMP_UNIT',
         nama='Angka Kejadian Asfiksia pada Bayi Baru Lahir',
         dimensi='EFEKTIF', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah bayi baru lahir dengan diagnosis asfiksia berat',
         denominator='Jumlah seluruh persalinan pada periode yang sama',
         ep='ARK 1 EP 1'),

    # ── OK (Bedah Sentral) ───────────────────────────────────────────────────
    dict(kode='INM-14', unit='IBS', jenis='NASIONAL',
         nama='Kepatuhan Pelaksanaan Surgical Safety Checklist (100%)',
         dimensi='AMAN', target=Decimal('100.00'), satuan='%',
         numerator='Jumlah operasi dengan SSC (Sign In, Time Out, Sign Out) terisi lengkap',
         denominator='Jumlah seluruh operasi yang dilaksanakan',
         ep='SKP 4 EP 1'),
    dict(kode='IMP-UNIT-IBS-01', unit='IBS', jenis='IMP_UNIT',
         nama='Angka Kejadian Ketinggalan Benda Asing/Kasa Pasca Bedah (0%)',
         dimensi='AMAN', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah kejadian URFO (Unintended Retention of Foreign Objects)',
         denominator='Jumlah seluruh tindakan operasi pada periode yang sama',
         ep='SKP 4 EP 1'),
    dict(kode='IMP-UNIT-IBS-02', unit='IBS', jenis='IMP_UNIT',
         nama='Angka Kejadian Operasi Salah Sisi / Salah Orang / Salah Prosedur (0%)',
         dimensi='AMAN', target=Decimal('0.00'), satuan='%',
         numerator='Jumlah kejadian wrong site / wrong patient / wrong procedure surgery',
         denominator='Jumlah seluruh tindakan operasi pada periode yang sama',
         ep='SKP 1 EP 1'),
]


# ─────────────────────────────────────────────────────────────────────────────
# 45 RISIKO KLINIS — 5 per unit
# ─────────────────────────────────────────────────────────────────────────────

RISIKO_DATA = {
    'IGD': {
        'masalah': 'Terjadi keterlambatan triase awal saat jam sibuk; response time triase hanya 82% dari target 100% dan terdapat 1 kasus keterlambatan Door-to-ECG (>25 menit) pada pasien STEMI hingga mengalami henti jantung.',
        'data_pendukung': '• Capaian Mutu: Response time triase 82% (target 100%).\n• Data KTD: 1 kasus keterlambatan Door-to-ECG (>25 menit) pada pasien STEMI hingga henti jantung.\n• Isu Eksternal: Regulasi baru Kemenkes terkait standar penanganan Stroke & Jantung di IGD.',
        'pj': 'Ka. Instalasi Gawat Darurat (IGD)',
        'risks': [
            ('Keterlambatan respon penanganan pasien kritis (Triage 1-2).', 5, 4, 'KURANGI', 'IMP-RS-IGD-01', 'IMP-RS-IGD-01'),
            ('Kesalahan penentuan derajat triase (under-triage).', 5, 3, 'KURANGI', 'IMP-RS-IGD-01', 'IMP-RS-IGD-01'),
            ('Keterlambatan Door-to-ECG / Door-to-Needle pada kegawatdaruratan jantung.', 5, 4, 'KURANGI', 'IMP-UNIT-IGD-01', 'IMP-UNIT-IGD-01'),
            ('Kejadian Unplanned Re-attendance < 24 jam dengan kondisi memburuk.', 4, 3, 'KURANGI', 'IMP-UNIT-IGD-02', 'IMP-UNIT-IGD-02'),
            ('Kesalahan identifikasi pasien gawat darurat tanpa identitas.', 5, 2, 'HINDARI', 'INM-03', 'INM-03'),
        ],
    },
    'ICU': {
        'masalah': 'Angka VAP melonjak ke 5,1‰ hari pemakaian ventilator (target ≤2,5‰); kepatuhan pelaksanaan Bundle Care VAP oleh perawat hanya 68%; terdapat 1 insiden pelepasan ETT tanpa sengaja (unplanned extubation) saat alih baring.',
        'data_pendukung': '• Data PPI: Angka VAP 5,1‰ hari pemakaian ventilator (target ≤2,5‰).\n• Hasil Audit: Kepatuhan pelaksanaan Bundle Care VAP oleh perawat hanya 68%.\n• Data KTD: 1 insiden pelepasan ETT tanpa sengaja (unplanned extubation) saat alih baring.',
        'pj': 'Ka. Instalasi Rawat Intensif Terpadu (ICU)',
        'risks': [
            ('Kejadian infeksi nosokomial VAP (Ventilator-Associated Pneumonia).', 5, 4, 'KURANGI', 'IMP-UNIT-ICU-01', 'IMP-UNIT-ICU-01'),
            ('Kejadian Infeksi Aliran Darah Utama (IADP) akibat kateter vena sentral.', 5, 3, 'KURANGI', 'IMP-UNIT-ICU-02', 'IMP-UNIT-ICU-02'),
            ('Kejadian Unplanned Extubation (Pelepasan ETT tanpa rencana).', 5, 3, 'KURANGI', 'IMP-UNIT-ICU-01', 'IMP-UNIT-ICU-01'),
            ('Re-admisi ICU < 48 jam pasca perawatan (unplanned readmission).', 4, 3, 'KURANGI', 'IMP-UNIT-ICU-03', 'IMP-UNIT-ICU-03'),
            ('Kejadian dekubitus derajat II/lebih pada pasien tirah baring lama.', 4, 3, 'KURANGI', 'IMP-RS-ICU-01', 'IMP-RS-ICU-01'),
        ],
    },
    'ICCU': {
        'masalah': 'Terdapat 1 kasus keterlambatan penanganan aritmia fatal akibat alarm fatigue pada monitor telemetri; kepatuhan prosedur double check pemberian inotropik High-Alert baru mencapai 75%; angka keberhasilan RJP di ICCU hanya 40% (target >50%).',
        'data_pendukung': '• Data KTD: 1 kasus keterlambatan penanganan aritmia fatal akibat alarm fatigue pada monitor telemetri.\n• Hasil Audit: Kepatuhan double check pemberian inotropik High-Alert baru 75%.\n• Capaian Mutu: Angka keberhasilan RJP di ICCU 40% (target >50%).',
        'pj': 'Ka. Unit ICCU (Intensive Coronary Care Unit)',
        'risks': [
            ('Keterlambatan deteksi aritmia fatal / cardiac arrest.', 5, 4, 'KURANGI', 'IMP-UNIT-ICCU-03', 'IMP-UNIT-ICCU-03'),
            ('Kejadian re-infark atau iskemia berulang selama perawatan.', 5, 3, 'KURANGI', 'IMP-UNIT-ICCU-02', 'IMP-UNIT-ICCU-02'),
            ('Kesalahan dosis atau kecepatan titrasi obat High-Alert.', 5, 3, 'KURANGI', 'IMP-UNIT-ICCU-01', 'IMP-UNIT-ICCU-01'),
            ('Komplikasi pendarahan masif pasca tindakan Primary PCI.', 5, 2, 'KURANGI', 'IMP-RS-ICCU-01', 'IMP-RS-ICCU-01'),
            ('Kegagalan resusitasi jantung paru (RJP) akibat respon tim lambat.', 5, 3, 'KURANGI', 'IMP-UNIT-ICCU-03', 'IMP-UNIT-ICCU-03'),
        ],
    },
    'RAJAL': {
        'masalah': 'Keluhan tinggi (42%) terkait waktu tunggu poliklinik spesialis > 2 jam; terdapat 3 kali kejadian salah panggil nama pasien dengan nama sama/mirip di ruang penerimaan resep; perlu integrasi antrean online BPJS Kesehatan.',
        'data_pendukung': '• Survey Pelanggan: Keluhan tinggi (42%) terkait waktu tunggu poliklinik spesialis > 2 jam.\n• Data KNC (Near Miss): 3 kali kejadian salah panggil nama pasien dengan nama sama/mirip di ruang penerimaan resep.\n• Isu Eksternal: Integrasi Waktu Layanan Antrean Online BPJS Kesehatan.',
        'pj': 'Ka. Instalasi Rawat Jalan (IRJ)',
        'risks': [
            ('Salah identifikasi pasien sebelum tindakan/pemberian resep.', 5, 3, 'HINDARI', 'INM-03', 'INM-03'),
            ('Reaksi alergi obat akibat penelusuran riwayat medis tidak lengkap.', 5, 2, 'KURANGI', 'IMP-UNIT-RAJAL-02', 'IMP-UNIT-RAJAL-02'),
            ('Kejadian pasien jatuh di area antrean / ruang periksa.', 4, 3, 'KURANGI', 'IMP-UNIT-RAJAL-01', 'IMP-UNIT-RAJAL-01'),
            ('Kesalahan penulisan/pembacaan resep (medication error).', 4, 3, 'KURANGI', 'IMP-UNIT-RAJAL-02', 'IMP-UNIT-RAJAL-02'),
            ('Keterlambatan rujukan internal antar spesialisasi pada kasus akut.', 4, 3, 'KURANGI', 'IMP-RS-RAJAL-01', 'IMP-RS-RAJAL-01'),
        ],
    },
    'RANAP': {
        'masalah': 'Terdapat 2 kejadian pasien jatuh dari tempat tidur (1 mengalami fraktur klavikula); kepatuhan perawat memasang klip tanda risiko jatuh kuning hanya 70%; angka kejadian Phlebitis meningkat mencapai 3,8‰ (target ≤1,5‰).',
        'data_pendukung': '• Data KTD: 2 kejadian pasien jatuh dari tempat tidur (1 mengalami fraktur klavikula).\n• Hasil Audit: Kepatuhan perawat memasang klip tanda risiko jatuh kuning hanya 70%.\n• Data PPI: Angka kejadian Phlebitis meningkat 3,8‰ (target ≤1,5‰).',
        'pj': 'Ka. Instalasi Rawat Inap (IRIN)',
        'risks': [
            ('Kejadian pasien jatuh dari tempat tidur / kamar mandi.', 5, 4, 'KURANGI', 'INM-09', 'INM-09'),
            ('Insiden kesalahan pemberian obat (5 Benar Obat).', 5, 3, 'KURANGI', 'IMP-UNIT-RANAP-01', 'IMP-UNIT-RANAP-01'),
            ('Keterlambatan respon penanganan perburukan kondisi pasien (EWS).', 5, 3, 'KURANGI', 'IMP-UNIT-RANAP-01', 'IMP-UNIT-RANAP-01'),
            ('Kejadian Infeksi Saluran Kemih (ISK) akibat kateter menetap.', 4, 3, 'KURANGI', 'IMP-UNIT-RANAP-02', 'IMP-UNIT-RANAP-02'),
            ('Kejadian Phlebitis pada area pemasangan infus intravena.', 4, 4, 'KURANGI', 'IMP-UNIT-RANAP-02', 'IMP-UNIT-RANAP-02'),
        ],
    },
    'HD': {
        'masalah': 'Kelengkapan pengisian asesmen pra dan pasca hemodialisa oleh DPJP/Perawat baru 78%; terdapat 1 insiden hipotensi berat (intradialytic hypotension) hingga pasien tidak sadar; perlu audit berkala kualitas air sistem Reverse Osmosis (RO) sesuai standar Kemenkes.',
        'data_pendukung': '• Hasil Audit: Kelengkapan pengisian asesmen pra dan pasca hemodialisa baru 78%.\n• Data KTD: 1 insiden hipotensi berat (intradialytic hypotension) hingga pasien tidak sadar.\n• Isu Eksternal: Standar Kemenkes terkait audit berkala kualitas air sistem Reverse Osmosis (RO).',
        'pj': 'Ka. Unit Hemodialisa (HD)',
        'risks': [
            ('Kejadian hipotensi Intradialitik berat / syok kardiogenik.', 5, 4, 'KURANGI', 'IMP-UNIT-HD-01', 'IMP-UNIT-HD-01'),
            ('Ruptur atau pendarahan masif pada akses vaskular (AV Fistula/CDL).', 5, 3, 'KURANGI', 'IMP-UNIT-HD-02', 'IMP-UNIT-HD-02'),
            ('Kejadian reaksi pyrogen / hemolisis akibat sindrom dialiser.', 5, 2, 'KURANGI', 'IMP-UNIT-HD-02', 'IMP-UNIT-HD-02'),
            ('Kontaminasi / infeksi bakteri pada akses aliran darah dialisis.', 5, 3, 'KURANGI', 'IMP-UNIT-HD-02', 'IMP-UNIT-HD-02'),
            ('Kesalahan pengaturan Ultrafiltration (UF) Rate atau heparin penawar.', 4, 3, 'KURANGI', 'IMP-RS-HD-01', 'IMP-RS-HD-01'),
        ],
    },
    'LAB': {
        'masalah': 'Pelaporan nilai kritis < 30 menit hanya tercapai 84% (target 100%); terdapat 4 kasus spesimen darah mengalami hemolisis / salah label saat pengiriman dari bangsal; pemantauan Mutu Internal (PMI) alat hematologi harian sering tidak terdokumentasi.',
        'data_pendukung': '• Capaian Mutu: Pelaporan nilai kritis < 30 menit hanya tercapai 84% (target 100%).\n• Data KTC (Tidak Cedera): 4 kasus spesimen darah hemolisis / salah label saat pengiriman dari bangsal.\n• Hasil Audit: Pemantauan Mutu Internal (PMI) alat hematologi harian sering tidak terdokumentasi.',
        'pj': 'Ka. Instalasi Laboratorium Patologi Klinik',
        'risks': [
            ('Spesimen sampel tertukar atau rusak (sample mislabeling/hemolisis).', 5, 3, 'KURANGI', 'IMP-UNIT-LAB-01', 'IMP-UNIT-LAB-01'),
            ('Salah pembacaan/transkripsi hasil pemeriksaan laboratorium.', 5, 2, 'HINDARI', 'IMP-UNIT-LAB-01', 'IMP-UNIT-LAB-01'),
            ('Keterlambatan penyampaian Nilai Kritis (Critical Value) ke DPJP.', 5, 3, 'KURANGI', 'INM-12', 'INM-12'),
            ('Reaksi kontaminasi spesimen kultur darah.', 4, 3, 'KURANGI', 'IMP-UNIT-LAB-02', 'IMP-UNIT-LAB-02'),
            ('Kesalahan hasil akibat spesimen tidak sesuai kriteria penyimpanan.', 4, 3, 'KURANGI', 'IMP-LAB-02', 'IMP-LAB-02'),
        ],
    },
    'VK': {
        'masalah': 'Terdapat 1 kasus Pendarahan Postpartum (HPP) lambat ditangani karena keterlambatan keputusan operasi SC Cito; kepatuhan kelengkapan pengisian Partograf pada persalinan normal baru 80%; keluhan pasien terkait kurangnya edukasi dan pendampingan saat proses persalinan.',
        'data_pendukung': '• Data KTD: 1 kasus Pendarahan Postpartum (HPP) lambat ditangani karena keterlambatan keputusan operasi SC Cito.\n• Hasil Audit: Kepatuhan kelengkapan pengisian Partograf pada persalinan normal baru 80%.\n• Survey Pelanggan: Keluhan pasien terkait kurangnya edukasi dan pendampingan saat proses persalinan.',
        'pj': 'Ka. Instalasi Kamar Bersalin (VK/PONEK)',
        'risks': [
            ('Kejadian Pendarahan Postpartum (HPP) tidak terdeteksi awal.', 5, 4, 'KURANGI', 'IMP-UNIT-VK-01', 'IMP-UNIT-VK-01'),
            ('Kejadian Asfiksia Berat pada Bayi Baru Lahir.', 5, 3, 'KURANGI', 'IMP-UNIT-VK-02', 'IMP-UNIT-VK-02'),
            ('Ruptur uteri / laserasi perineum derajat III-IV.', 5, 3, 'KURANGI', 'IMP-UNIT-VK-01', 'IMP-UNIT-VK-01'),
            ('Keterlambatan keputusan tindakan Sectio Caesarea cito (kegagalan PONEK).', 5, 4, 'KURANGI', 'IMP-RS-VK-01', 'IMP-RS-VK-01'),
            ('Infeksi pasca persalinan (endometritis/sepsis puerperalis).', 4, 3, 'KURANGI', 'IMP-UNIT-VK-01', 'IMP-UNIT-VK-01'),
        ],
    },
    'IBS': {
        'masalah': 'Terdapat 1 insiden ketidaksesuaian jumlah kasa saat penghitungan akhir sebelum penutupan dinding abdomen (near-URFO); kepatuhan pengisian Surgical Safety Checklist (SSC) fase Time Out sebesar 88% (target 100%); angka Infeksi Daerah Operasi (IDO) bersih tercatat 2,8% (target ≤2%).',
        'data_pendukung': '• Data KTD (KTC): 1 insiden ketidaksesuaian jumlah kasa saat penghitungan akhir sebelum penutupan dinding abdomen (near-URFO).\n• Capaian Mutu: Kepatuhan pengisian Surgical Safety Checklist (SSC) fase Time Out 88% (target 100%).\n• Data PPI: Angka Infeksi Daerah Operasi (IDO) bersih tercatat 2,8% (target ≤2%).',
        'pj': 'Ka. Instalasi Bedah Sentral (IBS)',
        'risks': [
            ('Tertinggalnya kasa/instrumen bedah di tubuh pasien (URFO).', 5, 3, 'HINDARI', 'IMP-UNIT-IBS-01', 'IMP-UNIT-IBS-01'),
            ('Kejadian Wrong Site, Wrong Procedure, Wrong Patient Surgery.', 5, 2, 'HINDARI', 'IMP-UNIT-IBS-02', 'IMP-UNIT-IBS-02'),
            ('Kejadian Infeksi Daerah Operasi (IDO) pasca bedah.', 5, 4, 'KURANGI', 'IMP-IBS-02', 'IMP-IBS-02'),
            ('Komplikasi anestesi (apnea, aspirasi pneumonia, cardiac arrest).', 5, 3, 'KURANGI', 'INM-14', 'INM-14'),
            ('Hypotermia sistemik pasca operasi pada pasien bedah mayor.', 4, 3, 'KURANGI', 'INM-14', 'INM-14'),
        ],
    },
}


# Rencana aksi standar per jenis risiko (template mitigasi)
RENCANA_AKSI_TEMPLATE = {
    'IMP-RS-IGD-01': '• Sosialisasi ulang SPO triase berbasis ESI/ATS kepada seluruh perawat IGD\n• Simulasi triase & drill kegawatdaruratan setiap bulan\n• Audit kepatuhan response time triase mingguan oleh Ka. IGD',
    'IMP-UNIT-IGD-01': '• Penempelan alur Door-to-ECG di area triase & ruang resusitasi\n• Penyediaan EKG mobile di area triase\n• Monitoring waktu Door-to-ECG harian dengan feedback ke tim',
    'IMP-UNIT-IGD-02': '• Asesmen ulang kriteria pulang pasien IGD (discharge criteria)\n• Edukasi pasien & keluarga tentang tanda bahaya sebelum pulang\n• Tindak lanjut telepon 24 jam pasca pulang',
    'INM-03': '• Sosialisasi ulang SPO identifikasi pasien (minimal 2 identitas)\n• Audit kepatuhan identifikasi pasien bulanan\n• Penyediaan gelang identitas cadangan untuk pasien tanpa identitas',
    'IMP-UNIT-ICU-01': '• Sosialisasi ulang Bundle Care VAP (head elevation, oral care, sedasi harian)\n• Audit kepatuhan bundle VAP mingguan\n• Pelatihan perawat ICU tentang ventilator care',
    'IMP-UNIT-ICU-02': '• Sosialisasi bundle CLABSI prevention saat pemasangan CVC\n• Audit kepatuhan bundle IADP bulanan\n• Monitoring harian kondisi insersi kateter',
    'IMP-UNIT-ICU-03': '• Kriteria transfer ICU → bangsal yang jelas (ICU discharge criteria)\n• Handover terstruktur SBAR saat transfer\n• Follow-up pasien pasca ICU 48 jam pertama',
    'IMP-RS-ICU-01': '• Sosialisasi ulang SPO penggunaan APD sesuai indikasi\n• Penyediaan stok APD lengkap di setiap bed ICU\n• Audit kepatuhan APD mingguan',
    'IMP-UNIT-ICCU-01': '• Sosialisasi ulang SPO double check obat high-alert\n• Penyediaan tabel dosis standar inotropik di setiap bed\n• Audit kepatuhan double check harian',
    'IMP-UNIT-ICCU-02': '• Protokol monitoring EKG kontinu & alarm setting yang tepat\n• Follow-up troponin serial sesuai protokol\n• Evaluasi kepatuhan terapi antiplatelet/antikoagulan',
    'IMP-UNIT-ICCU-03': '• Pelatihan BLS/ACLS berkala untuk seluruh staf ICCU\n• Penyediaan defibrillator & obat emergensi siap pakai\n• Drill code blue bulanan dengan evaluasi response time',
    'IMP-RS-ICCU-01': '• Sosialisasi ulang format handover SBAR/TBAK\n• Audit kepatuhan komunikasi efektif saat handover\n• Pelatihan komunikasi efektif untuk seluruh staf ICCU',
    'IMP-RS-RAJAL-01': '• Analisis alur pelayanan poliklinik (lean analysis)\n• Penambahan slot jadwal dokter pada jam sibuk\n• Implementasi sistem antrean online terintegrasi',
    'IMP-UNIT-RAJAL-01': '• Skrining risiko jatuh pada setiap pasien poliklinik baru\n• Penyediaan kursi tunggu dengan handrail & lantai anti-slip\n• Edukasi pasien berisiko jatuh & pendampingan',
    'IMP-UNIT-RAJAL-02': '• Sosialisasi ulang SPO penulisan resep yang benar\n• Double check resep oleh apoteker sebelum diserahkan\n• Audit resep zero error bulanan',
    'INM-09': '• Asesmen risiko jatuh pada setiap pasien baru (Morse/Humpty Dumpty)\n• Pemasangan klip kuning & tanda risiko jatuh di bed pasien\n• Edukasi pasien & keluarga tentang pencegahan jatuh\n• Audit kepatuhan asesmen & intervensi jatuh bulanan',
    'IMP-UNIT-RANAP-01': '• Sosialisasi ulang SPO EWS & skor perburukan\n• Pelatihan perawat tentang interpretasi EWS\n• Audit kepatuhan tindak lanjut EWS harian',
    'IMP-UNIT-RANAP-02': '• Sosialisasi bundle pencegahan phlebitis (insersi aseptik, ganti balutan)\n• Monitoring harian area insersi infus\n• Audit kepatuhan perawatan infus mingguan',
    'IMP-RS-RANAP-01': '• Sosialisasi 5 momen kebersihan tangan\n• Penyediaan handrub di setiap bed & pintu masuk\n• Audit kepatuhan kebersihan tangan mingguan',
    'IMP-UNIT-HD-01': '• Monitoring TD & berat badan setiap 30 menit selama dialisis\n• Protokol penanganan hipotensi intradialitik\n• Penyesuaian UF rate & profil sodium sesuai kondisi pasien',
    'IMP-UNIT-HD-02': '• Aseptik ketat saat kanulasi akses vaskular\n• Monitoring harian tanda infeksi pada akses\n• Edukasi perawatan akses vaskular kepada pasien',
    'IMP-RS-HD-01': '• Sosialisasi ulang SPO penggunaan APD di unit HD\n• Penyediaan APD lengkap (sarung tangan, apron, masker, goggles)\n• Audit kepatuhan APD mingguan',
    'IMP-UNIT-LAB-01': '• Verifikasi identitas & label spesimen saat penerimaan\n• Sosialisasi SPO labeling spesimen ke bangsal\n• Audit kepatuhan labeling spesimen bulanan',
    'IMP-UNIT-LAB-02': '• Sosialisasi teknik aseptik pengambilan kultur darah\n• Penyediaan media kultur standar & desinfeksi kulit\n• Monitoring angka kontaminasi kultur bulanan',
    'INM-12': '• Sosialisasi kriteria nilai kritis & alur pelaporan < 30 menit\n• Sistem notifikasi otomatis ke DPJP via SIMRS/WhatsApp\n• Audit kepatuhan pelaporan nilai kritis bulanan',
    'IMP-LAB-02': '• Sosialisasi kriteria penyimpanan & transportasi spesimen\n• Penyediaan cool box & suhu terkontrol untuk transport\n• Monitoring angka penolakan spesimen bulanan',
    'IMP-RS-VK-01': '• Simulasi PONEK & drill SC emergensi setiap bulan\n• Penetapan alur cepat keputusan SC cito (code red obstetri)\n• Monitoring waktu keputusan-tindakan SC emergensi',
    'IMP-UNIT-VK-01': '• Sosialisasi SPO deteksi dini & penanganan HPP\n• Penyediaan obat uterotonika & blood bank standby\n• Pengisian partograf lengkap pada setiap persalinan',
    'IMP-UNIT-VK-02': '• Pelatihan resusitasi neonatus (NRP) untuk seluruh staf VK\n• Penyediaan alat resusitasi neonatus siap pakai\n• Monitoring APGAR & tindak lanjut asfiksia',
    'INM-14': '• Sosialisasi ulang Surgical Safety Checklist (Sign In, Time Out, Sign Out)\n• Audit kepatuhan SSC setiap operasi\n• Pelatihan komunikasi tim bedah (briefing & debriefing)',
    'IMP-UNIT-IBS-01': '• Penghitungan kasa & instrumen sebelum, selama, dan sesudah operasi\n• Dokumentasi jumlah kasa/instrumen di papan OK\n• Sosialisasi SPO URFO prevention ke tim bedah',
    'IMP-UNIT-IBS-02': '• Verifikasi identitas pasien & sisi operasi sebelum insisi (Time Out)\n• Penandaan sisi operasi oleh operator sebelum pasien masuk OK\n• Audit kepatuhan marking & Time Out setiap operasi',
    'IMP-IBS-02': '• Antibiotik profilaksis sesuai waktu & dosis standar\n• Sterilisasi instrumen sesuai SPO CSSD\n• Monitoring tanda infeksi pasca bedah & audit IDO bulanan',
}


class Command(BaseCommand):
    help = 'Seed 45 indikator mutu klinis + 45 risiko klinis untuk 9 unit pelayanan RS.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== SEED INDIKATOR & RISIKO KLINIS 9 UNIT ===\n'))

        unit_map = {u.code: u for u in UnitKerja.objects.all()}

        # ── STEP 1: Seed indikator baru ─────────────────────────────────────
        ind_created, ind_updated = 0, 0
        kode_to_ind = {}

        for item in INDIKATOR_NEW:
            unit = unit_map.get(item['unit'])
            if not unit:
                self.stdout.write(self.style.WARNING(f"  ⚠ Unit '{item['unit']}' tidak ditemukan — dilewati"))
                continue

            ep = StandardItem.objects.filter(code=item['ep']).first() if item.get('ep') else None

            obj, created = IndikatorMutu.objects.update_or_create(
                kode_indikator=item['kode'],
                defaults=dict(
                    nama_indikator=item['nama'],
                    unit=unit,
                    jenis=item['jenis'],
                    dimensi_mutu=item['dimensi'],
                    numerator=item['numerator'],
                    denominator=item['denominator'],
                    target_nilai=item['target'],
                    satuan=item['satuan'],
                    ep_terkait=ep,
                    rencana_aksi=RENCANA_AKSI_TEMPLATE.get(item['kode'], ''),
                    pj=item.get('pj', ''),
                    aktif=True,
                ),
            )
            kode_to_ind[item['kode']] = obj
            if created:
                ind_created += 1
                self.stdout.write(f"  + [{item['kode']}] {item['nama'][:62]}")
            else:
                ind_updated += 1

        # Map indikator existing (INM & IMP) agar bisa dilink
        for im in IndikatorMutu.objects.all():
            kode_to_ind.setdefault(im.kode_indikator, im)

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✔ Indikator: {ind_created} dibuat, {ind_updated} diupdate\n"))

        # ── STEP 2: Seed risiko klinis ──────────────────────────────────────
        risk_created, risk_updated = 0, 0

        for unit_code, data in RISIKO_DATA.items():
            unit = unit_map.get(unit_code)
            if not unit:
                self.stdout.write(self.style.WARNING(f"  ⚠ Unit '{unit_code}' tidak ditemukan — dilewati"))
                continue

            self.stdout.write(self.style.MIGRATE_LABEL(f"\n  ── {unit.name} ──"))

            for (jenis, dampak, prob, strategi, ind_kode, tpl_kode) in data['risks']:
                indikator = kode_to_ind.get(ind_kode)
                # Fallback: bila kode referensi tidak tersedia, pakai indikator apa pun
                # milik unit yang sama agar risiko tetap punya indikator pemantau.
                if indikator is None:
                    indikator = (IndikatorMutu.objects.filter(unit=unit, aktif=True)
                                 .order_by('jenis', 'kode_indikator').first())
                    if indikator:
                        self.stdout.write(self.style.WARNING(
                            f"      ~ [{ind_kode}] tidak ada — fallback ke [{indikator.kode_indikator}]"))
                rencana = RENCANA_AKSI_TEMPLATE.get(tpl_kode, '')

                deskripsi = (
                    f"{jenis} Teridentifikasi dari {data['masalah'][:180]} "
                    f"Mitigasi difokuskan pada penguatan kepatuhan SPO, audit berkala, "
                    f"dan pemantauan indikator mutu terkait."
                )

                obj, created = RisikoUnit.objects.update_or_create(
                    unit=unit,
                    tahun=2026,
                    periode='TAHUNAN',
                    jenis_risiko=jenis,
                    defaults=dict(
                        kategori_risiko='KLINIS',
                        masalah=data['masalah'],
                        data_pendukung=data['data_pendukung'],
                        deskripsi_risiko=deskripsi,
                        dampak=dampak,
                        probabilitas=prob,
                        strategi_mitigasi=strategi,
                        rencana_aksi=rencana,
                        pj_mitigasi=data['pj'],
                        biaya_mitigasi=Decimal('0'),
                        indikator_mutu_terkait=indikator,
                        target_capaian_indikator=indikator.target_nilai if indikator else None,
                        status='IDENTIFIKASI',
                        metode_evaluasi='STANDAR',
                    ),
                )
                if created:
                    risk_created += 1
                    self.stdout.write(f"    + [{dampak}x{prob}={dampak*prob}] {jenis[:70]}")
                else:
                    risk_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✔ Risiko Klinis: {risk_created} dibuat, {risk_updated} diupdate"))

        # ── SUMMARY ─────────────────────────────────────────────────────────
        total_ind = IndikatorMutu.objects.count()
        total_risk = RisikoUnit.objects.filter(kategori_risiko='KLINIS').count()

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*66}\n"
            f"✅ SELESAI\n"
            f"   Total Indikator Mutu di DB   : {total_ind}\n"
            f"   Total Risiko Klinis di DB    : {total_risk}\n"
            f"   Unit ter-seed                : {len(RISIKO_DATA)}\n"
            f"{'='*66}\n"
        ))
