"""
Management command: seed 132 indikator klinis & 55 risiko klinis 11 unit pelayanan
berdasarkan dokumen regulasi RS: "BAB INDIKATOR RESIKO KLINIS.docx".
Idempoten & mendukung multi-environment (lokal SQLite dan production Supabase).
"""
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu, RisikoUnit

logger = logging.getLogger(__name__)

UNITS_DATA = [
  {
    "key": "OK",
    "name": "Kamar Operasi (OK)",
    "official_name": "Instalasi Bedah Sentral (Kamar Operasi / OK)",
    "candidates": [
      "IBS",
      "KAMAR-OPERASI",
      "RUANG-OK",
      "OK"
    ],
    "parent": "DIR-MED",
    "data": "Capaian pengisian SSC real-time 81% dan penundaan operasi elektif 7,8%.",
    "masalah": "Time Out sering dicentang pasca-insisi dan keterlambatan lab pra-bedah.",
    "risiko": [
      "Kesalahan lokasi/prosedur pembedahan (Wrong Site/Procedure)",
      "Benda asing tertinggal dalam tubuh (Retained Surgical Items)",
      "Penundaan tindakan emergency operation (SC cito)",
      "Komplikasi anestesi & hipotermia pasca-bedah",
      "Infeksi Daerah Operasi (IDO) dari kamar bedah"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Penggunaan Alat Pelindung Diri (APD) (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Penundaan Operasi Elektif (≤ 5%)",
        "target": 5.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Insiden Wrong Site / Wrong Procedure / Wrong Surgery (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Benda Asing Tertinggal Pasca-Pembedahan (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Waktu Tanggap Operasi SC Emergensi ≤ 30 Menit (≥ 80%)",
        "target": 80.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Angka Kematian di Meja Operasi / MORT (< 0,1%)",
        "target": 0.1,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penerapan Sasaran Keselamatan Pasien / SKP 4 (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Pengisian Surgical Safety Checklist (SSC) (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penandaan Lokasi Operasi / Site Marking (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemberian Antibiotik Profilaksis ≤ 60 Menit Sebelum Insisi (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Persentase Ketersediaan Tim On-Call Cito Bedah/Anestesi ≤ 30 Menit (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Hipotermia Pasca-Operasi di Ruang Pulih / PACU (< 5%)",
        "target": 5.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "RANAP-BEDAH",
    "name": "Perawatan Rawat Inap Bedah",
    "official_name": "Bangsal Perawatan Bedah",
    "candidates": [
      "BANGSAL-BEDAH",
      "IRIN-BEDAH",
      "BEDAH-RANAP"
    ],
    "parent": "IRIN",
    "data": "Angka IDO bedah digestif 2,6% dan 28% pasien mengeluhkan nyeri VAS > 6 pada 6 jam pertama.",
    "masalah": "Teknik perawatan luka kurang steril dan koordinasi terapi nyeri lambat.",
    "risiko": [
      "Infeksi Daerah Operasi (IDO) pasca-rawat",
      "Nyeri pasca-operasi berat tidak tertangani",
      "Kejadian perdarahan pasca-bedah di bangsal",
      "Resiko pasien jatuh pasca-efek anestesi",
      "Kejadian Deep Vein Thrombosis (DVT) pasca-bedah mayor"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Infeksi Daerah Operasi / IDO (< 1,5%)",
        "target": 1.5,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Pasien Jatuh dengan Cedera di RS (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Manajemen Nyeri Terpadu Pasca-Operasi (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Re-operasi Tidak Terencana Pasca-Bedah Dalam < 24 Jam (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 6 (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Persentase Pasien Pasca-Operasi Skor Nyeri VAS ≤ 3 Dalam 6 Jam (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Audit Bundle Perawatan Luka Bedah Steril (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemantauan Tanda Vital & EWS Pasca-Operasi 24 Jam Pertama (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kepatuhan Mobilisasi Dini Pasca-Operasi Mayor (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Profilaksis Tromboemboli pada Bedah Risiko Tinggi (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "VK",
    "name": "Kamar Persalinan (VK)",
    "official_name": "Instalasi Kamar Bersalin (VK / PONEK)",
    "candidates": [
      "VK",
      "RUANG-BERSALIN-VK",
      "RUANG-BERSALIN"
    ],
    "parent": "DIR-MED",
    "data": "Waktu tanggap SC emergensi 42 menit dan pengisian Partograf digital baru 74%.",
    "masalah": "Penundaan tim panggilan on-call dan pengisian Partograf retrospektif.",
    "risiko": [
      "Perdarahan Pasca-Persalinan (Primary HPP)",
      "Asfiksia Neonatorum berat pasca-lahir",
      "Ruptur Uteri / Trauma jalan lahir derajat III-IV",
      "Keterlambatan penanganan Eklamsia/Preeklamsia",
      "Infeksi intrapartum / Ketuban Pecah Dini (KPD)"
    ],
    "inm": [
      {
        "nama": "Waktu Tanggap Operasi Seksio Sesarea Emergensi ≤ 30 Menit (≥ 80%)",
        "target": 80.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penggunaan APD (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Keselamatan Ibu dan Bayi pada Persalinan RS (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kematian Ibu Pasca-Persalinan / AKI di RS (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Kematian Janin / Asfiksia Lahir di RS (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penanganan Kegawatdaruratan Preeklamsia/Eklamsia (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Perdarahan Pasca-Persalinan Terkompensasi (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Pengisian Partograf Digital Secara Real-Time (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pelaksanaan Inisiasi Menyusu Dini (IMD) Minimal 1 Jam (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Waktu Respon Penanganan Perdarahan Kebidanan ≤ 10 Menit (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Robekan Perineum Derajat III/IV pada Persalinan Normal (< 2%)",
        "target": 2.0,
        "satuan": "%"
      },
      {
        "nama": "Ketersediaan Emergency Obstetric Kit Terverifikasi di VK (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "NIFAS",
    "name": "Rawat Inap Pasca Persalinan (Nifas)",
    "official_name": "Bangsal Perawatan Pasca Persalinan (Nifas)",
    "candidates": [
      "RUANG-NIFAS",
      "BANGSAL-NIFAS",
      "BANGSAL-OBGYN"
    ],
    "parent": "IRIN",
    "data": "Angka kejadian infeksi perineum 1,8% dan 32% ibu keluhkan dampingan laktasi kurang.",
    "masalah": "Personal higiene perineum lemah dan bidan sibuk saat peak hours.",
    "risiko": [
      "Infeksi luka perineum / luka operasi SC",
      "Perdarahan nifas sekunder (Secondary HPP)",
      "Kegagalan proses laktasi & bendungan ASI",
      "Depresi pasca-persalinan / Postpartum Blues tidak terdeteksi",
      "Infeksi Tali Pusat (Omphalitis) pada rawat gabung"
    ],
    "inm": [
      {
        "nama": "Kepuasan Pasien (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Infeksi Nifas / Puerperal Sepsis (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Keberhasilan Program Rawat Gabung Ibu dan Bayi (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Indeks Kepuasan Pasien Rawat Inap Kebidanan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Perdarahan Nifas Lanjut di Ruang Perawatan (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Cakupan Pemberian ASI Eksklusif Saat Pulang (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Audit Perawatan Luka Perineum dan Balutan SC Steril (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Persentase Pelaksanaan Konseling & Pendampingan Laktasi oleh Bidan (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemantauan Tinggi Fundus Uteri (TFU) & Lochea Tiap Shift (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Skrining Risiko Depresi Pasca-Melahirkan / EPDS (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kepatuhan Edukasi Tanda Bahaya Nifas Sebelum Pulang (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "HD",
    "name": "Kamar Hemodialisa (HD)",
    "official_name": "Unit Hemodialisa (Cuci Darah)",
    "candidates": [
      "HD",
      "HEMODIALISA"
    ],
    "parent": "UNIT-PENUNJANG",
    "data": "Angka insiden hipotensi intradiatilik 8,5% dan 1 kasus kesalahan set dialiser terpakai ulang (reuse).",
    "masalah": "Penarikan cairan (UFR) terlalu cepat dan sistem pemindaian barcode dialiser reuse lambat.",
    "risiko": [
      "Hipotensi/Syok intradiatilik berat",
      "Kesalahan penataan dialiser reuse antar-pasien",
      "Transmisi penyakit menular (Hepatitis B/C, HIV)",
      "Reaksi pirogenik / bacteremia saat dialisis",
      "Perdarahan / Akses vaskuler (AV Fistula) lepas"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penggunaan APD (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Serokonversi Hepatitis B/C pada Pasien HD Rutin (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Insiden Kesalahan Identifikasi & Pemakaian Dialiser Reuse (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Pirogenik saat Hemodialisis (< 0,1%)",
        "target": 0.1,
        "satuan": "%"
      },
      {
        "nama": "Angka Keselamatan Pasien Gagal Ginjal saat HD (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 1 (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Angka Kejadian Hipotensi Intradiatilik Berat (< 5%)",
        "target": 5.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemindaian Barcode Dialiser Reuse Sebelum Tindakan (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemeriksaan Kualitas Air RO (Reverse Osmosis) Berkalibrasi (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Komplikasi Akses Vaskular / Hematoma AV Fistula (< 2%)",
        "target": 2.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Adekuasi Hemodialisis (Kt/V ≥ 1,8) pada Pasien Rutin (≥ 80%)",
        "target": 80.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "ORTHOPEDI",
    "name": "Rawat Inap Orthopedi",
    "official_name": "Bangsal Perawatan Orthopedi",
    "candidates": [
      "BANGSAL-ORTHOPEDI",
      "ORTHOPEDI-RANAP"
    ],
    "parent": "IRIN",
    "data": "Insiden pasien jatuh pasca-operasi fraktur 1 kasus dan dekubitus tumit 1,2%.",
    "masalah": "Asesmen risiko jatuh tidak diperbarui dan reposisi tumit gips/imobilisasi tidak terpasang padding.",
    "risiko": [
      "Pasien jatuh pasca-imobilisasi/operasi fraktur",
      "Compartment Syndrome akibat gips/pembedahan",
      "Dislokasi implan / Prostesis pasca-operasi",
      "Dekubitus tumit / area penonjolan tulang",
      "Tromboemboli Vena (DVT / Emboli Paru)"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Pasien Jatuh di Bangsal Orthopedi (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Infeksi Implan Pembedahan Orthopedi (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pencegahan Tromboemboli Vena (DVT) Pasca-Bedah (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Compartment Syndrome Tidak Terdeteksi Dini (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 6 (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Re-asesmen Risiko Jatuh Morse & Penggunaan Alat Bantu (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemeriksaan Neurovaskuler Distal (NVD) Tiap Shift (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemasangan Bantal Tumit / Padding Anti-Dekubitus Imobilisasi (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Persentase Pelaksanaan Latihan Mobilisasi Dini / Fisioterapi H+1 Bedah (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penilaian Kestabilan Gips / Traksi Tulang oleh Perawat (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "MATA",
    "name": "Perawatan Mata (Eye Care)",
    "official_name": "Perawatan Mata (Eye Care)",
    "candidates": [
      "BANGSAL-MATA",
      "EYE-CARE",
      "MATA-RANAP"
    ],
    "parent": "IRIN",
    "data": "Angka kejadian Endophthalmitis pasca-operasi katarak 0,2% dan kesalahan penetesan obat tetes mata.",
    "masalah": "Teknik sterilisasi instrumen mata mikro kurang presisi dan salah mata (Right/Left Eye) saat obat.",
    "risiko": [
      "Endophthalmitis pasca-bedah katarak/vitrektomi",
      "Kesalahan lokasi mata yang ditindak (Wrong Eye)",
      "Peningkatan Tekanan Intraokular (TIO) mendadak",
      "Toksisitas / Kesalahan penetesan obat mata High Alert",
      "Kebutaan permanen akibat trauma/komplikasi tindakan"
    ],
    "inm": [
      {
        "nama": "Kepuasan Pasien (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Endophthalmitis Pasca-Operasi Katarak (< 0,1%)",
        "target": 0.1,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Kesalahan Lokasi Operasi Mata / Wrong Eye (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Insiden Medication Error Penetesan Obat Mata Kritis (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Standar Sterilisasi Instrumen Bedah Mata Mikro (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 4 (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Konfirmasi Sisi Mata (OD/OS) Sebelum Tindakan/Obat (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Teknik Aseptik Penetesan Obat Mata Pasca-Operasi (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pengukuran Tekanan Intraokular (TIO) Pra dan Pasca-Tindakan (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Keterlambatan Respon Keluhan Penurunan Visus Mendadak (< 15 menit)",
        "target": 15.0,
        "satuan": "Menit"
      },
      {
        "nama": "Kelengkapan Lembar Edukasi Pantangan Pasca-Operasi Mata Saat Pulang (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "NEUROLOGI",
    "name": "Rawat Inap Persyarafan (Neurologi)",
    "official_name": "Bangsal Perawatan Persyarafan (Neurologi)",
    "candidates": [
      "BANGSAL-SARAF",
      "NEUROLOGI-RANAP",
      "SARAF-RANAP"
    ],
    "parent": "IRIN",
    "data": "Angka aspirasi pneumonia pada pasien Stroke 3,2% dan dekubitus derajat 2 tercatat 1,5%.",
    "masalah": "Skrining disfagia (gangguan menelan) tidak dilakukan sebelum pemberian makan/minum pertama.",
    "risiko": [
      "Aspirasi Paru akibat Disfagia pasien Stroke",
      "Dekubitus derajat II-IV pada pasien imobilisasi/paralisis",
      "Pasien jatuh akibat gangguan keseimbangan/paresis",
      "Perburukan Defisit Neurologis tidak terdeteksi (GCS drop)",
      "Kejadian kejang berulang tanpa penanganan cepat"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Kejadian Aspirasi Pneumonia pada Pasien Stroke Inap (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Dekubitus Grade ≥ 2 pada Pasien Stroke/Neurologi (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Pasien Jatuh Cedera di Bangsal Neurologi (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penanganan Stroke Iskemik Akut / Door-to-Needle Time (≥ 80%)",
        "target": 80.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 6 (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Skrining Disfagia (Tes Menelan) Sebelum Pemberian Nutrisi Oral (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemantauan Skor GCS & Pupil Tiap Shift pada Pasien Kritis (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Protokol Alih Baring 2 Jam (Miki-Mika) & Matras Anti-Dekubitus (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Pemasangan Side-Rail & Gelang Kuning Risiko Jatuh (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Waktu Respon Penanganan Kejang Berulang / Status Epileptikus (< 5 menit)",
        "target": 5.0,
        "satuan": "Menit"
      }
    ]
  },
  {
    "key": "KARDIOLOGI",
    "name": "Rawat Inap Jantung (Kardiologi)",
    "official_name": "Bangsal Perawatan Jantung (Kardiologi)",
    "candidates": [
      "BANGSAL-JANTUNG",
      "KARDIOLOGI-RANAP",
      "JANTUNG-RANAP"
    ],
    "parent": "IRIN",
    "data": "Terjadi 1 kasus henti jantung tanpa respon cepat EWS dan overload cairan pada pasien Gagal Jantung.",
    "masalah": "Input lembar balance cairan menunggak dan skor EWS kardiologi tidak dihitung real-time.",
    "risiko": [
      "Henti jantung mendadak (Cardiac Arrest) tidak terdeteksi EWS",
      "Edema Paru Akut akibat overload cairan intravaskuler",
      "Aritmia letal (VT/VF) pasca-Infark Miokard",
      "Perdarahan akibat terapi Antikoagulan/Antiplatelet",
      "Pasien jatuh akibat hipotensi ortostatik/sinkop"
    ],
    "inm": [
      {
        "nama": "Kepuasan Pasien (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Keberhasilan Resusitasi Jantung Paru (ROS C) di Bangsal Jantung (≥ 60%)",
        "target": 60.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Henti Jantung Tidak Terdeteksi EWS di Rawat Inap (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Perdarahan Mayor Akibat Terapi Antikoagulan (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Penanganan Sindrom Koroner Akut (SKA) Sesuai Clinical Pathway (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 3 (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Pencatatan Balance Cairan 24 Jam pada Pasien Gagal Jantung (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kalkulasi Skor EWS Kardiologi & Monitoring EKG Kontinu (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Verifikasi Double Check Pemberian Obat Inotropik / Drip Obat Kritis (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Edukasi Batas Cairan & Diet Rendah Garam Saat Pulang (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Waktu Tanggap Tim Code Blue Bangsal Jantung ≤ 3 Menit (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "INTERNA",
    "name": "Rawat Inap Penyakit Dalam (Interna)",
    "official_name": "Bangsal Perawatan Penyakit Dalam (Interna)",
    "candidates": [
      "BANGSAL-INTERNA",
      "PENYAKIT-DALAM-RANAP",
      "INTERNA-RANAP"
    ],
    "parent": "IRIN",
    "data": "Kejadian hipoglikemia berat pada pasien Diabetes Melitus 2,8% dan phlebitis infus berkali-kali.",
    "masalah": "Pemberian insulin tidak sejajar dengan jam distribusi makanan dan penggantian kateter infus lambat.",
    "risiko": [
      "Hipoglikemia berat akibat insulin/OAD",
      "Phlebitis / Infeksi pemasangan kanula vena perifer",
      "Syok Septik tidak terdeteksi dini",
      "Pasien jatuh akibat kelemahan umum / Anemia berat",
      "Re-admisi < 30 hari akibat penyakit kronis terkompensasi"
    ],
    "inm": [
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Angka Kejadian Hipoglikemia Berat Selama Inap (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Kejadian Phlebitis di Bangsal Penyakit Dalam (≤ 1 permil)",
        "target": 1.0,
        "satuan": "‰"
      },
      {
        "nama": "Kepatuhan Penanganan Sepsis Dalam 1 Jam Pertama / Sepsis Bundle (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Readmission Pasien Kronis (DM/Kidney) Tanpa Indikasi Baru (< 5%)",
        "target": 5.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 3 (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Pengukuran Gula Darah Sewaktu (GDS) Sebelum Pemberian Insulin (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sinkronisasi Jam Injeksi Insulin dan Waktu Makan Pasien (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Monitoring Visual Infusion Phlebitis (VIP) Score Tiap Shift (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Re-asesmen EWS dan Pelaporan Early Warning Sepsis (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Persentase Kelengkapan Edukasi Manajemen Mandiri Penyakit Kronis Saat Pulang (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      }
    ]
  },
  {
    "key": "THT",
    "name": "Rawat Inap THT (Telinga Hidung Tenggorok)",
    "official_name": "Bangsal Perawatan THT (Telinga Hidung Tenggorok)",
    "candidates": [
      "BANGSAL-THT",
      "THT-RANAP"
    ],
    "parent": "IRIN",
    "data": "Pendarahan pasca-Tonsilektomi di bangsal 1,2% dan aspirasi jalan napas pada pasien pasca-Trakeostomi.",
    "masalah": "Pemantauan pendarahan tersembunyi (refleks menelan) terlambat dan pembersihan inner cannula trakeostomi tidak rutin.",
    "risiko": [
      "Perdarahan pasca-operasi Tonsilektomi/Adenoidektomi",
      "Sumbatan jalan napas / Dislokasi kanul Trakeostomi",
      "Aspirasi benda asing / Perdarahan ke saluran napas",
      "Infeksi stoma trakeostomi / Luka operasi THT",
      "Nyeri pasca-bedah THT berat yang menghambat asupan"
    ],
    "inm": [
      {
        "nama": "Kepuasan Pasien (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Kebersihan Tangan (≥ 85%)",
        "target": 85.0,
        "satuan": "%"
      }
    ],
    "rs": [
      {
        "nama": "Kejadian Perdarahan Pasca-Tonsilektomi Memerlukan Re-Bedah (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Sumbatan Jalan Napas Pasca-Operasi THT / Trakeostomi (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Angka Infeksi Stoma Trakeostomi / Luka Bedah THT (< 1%)",
        "target": 1.0,
        "satuan": "%"
      },
      {
        "nama": "Kejadian Aspirasi Saluran Napas di Bangsal THT (0%)",
        "target": 0.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Sasaran Keselamatan Pasien / SKP 2 (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      }
    ],
    "unit": [
      {
        "nama": "Kepatuhan Pemantauan Refleks Menelan & Perdarahan Pasca-Tonsilektomi Tiap Jam (≥ 98%)",
        "target": 98.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Perawatan & Suctioning Kanul Trakeostomi Steril (≥ 95%)",
        "target": 95.0,
        "satuan": "%"
      },
      {
        "nama": "Ketersediaan Set Darurat Pembebasan Jalan Napas / Tracheostomy Kit di Bangsal (100%)",
        "target": 100.0,
        "satuan": "%"
      },
      {
        "nama": "Kepatuhan Manajemen Nyeri Pasca-Bedah THT Agar Asupan Nutrisi Adekuat (≥ 90%)",
        "target": 90.0,
        "satuan": "%"
      },
      {
        "nama": "Kelengkapan Edukasi Larangan Batuk/Mengejan Pasca-Operasi THT Saat Pulang (100%)",
        "target": 100.0,
        "satuan": "%"
      }
    ]
  }
]

class Command(BaseCommand):
    help = 'Seed 132 indikator klinis & 55 risiko klinis 11 unit (BAB INDIKATOR RESIKO KLINIS)'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Hapus data BAB sebelumnya sebelum seed ulang')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SEED 132 INDIKATOR & 55 RISIKO KLINIS (11 UNIT) ==='))

        if options['reset']:
            self.stdout.write(self.style.WARNING('Membersihkan data indikator & risiko BAB sebelumnya...'))
            IndikatorMutu.objects.filter(kode_indikator__startswith='BAB-').delete()
            RisikoUnit.objects.filter(jenis_risiko__startswith='[BAB]').delete()

        # Build unit cache
        all_units = {u.code: u for u in UnitKerja.objects.all()}

        def get_or_create_unit(spec):
            for code in spec['candidates']:
                if code in all_units:
                    return all_units[code]
                u = UnitKerja.objects.filter(code=code).first()
                if u:
                    all_units[code] = u
                    return u
            
            # Auto-create if not found
            primary_code = spec['candidates'][0]
            parent = None
            if spec.get('parent'):
                parent = all_units.get(spec['parent']) or UnitKerja.objects.filter(code=spec['parent']).first()
                if not parent:
                    # fallback to any parent
                    parent = UnitKerja.objects.filter(code__in=['IRIN', 'DIR-MED', 'RANAP']).first()
            
            u = UnitKerja.objects.create(
                code=primary_code,
                name=spec['official_name'],
                parent=parent
            )
            all_units[primary_code] = u
            self.stdout.write(self.style.NOTICE(f"  + Auto-create Unit: [{primary_code}] {spec['official_name']}"))
            return u

        total_ind_created = 0
        total_risk_created = 0

        with transaction.atomic():
            for u_spec in UNITS_DATA:
                unit = get_or_create_unit(u_spec)
                key = u_spec['key']
                self.stdout.write(f"\n--> Unit [{unit.code}] {u_spec['name']}")

                # 1. Seed Indicators: 2 INM, 5 RS, 5 UNIT
                ind_objs = []
                
                # INM
                for i_idx, item in enumerate(u_spec['inm'], 1):
                    code = f"BAB-{key}-INM-{i_idx:02d}"
                    ind, created = IndikatorMutu.objects.get_or_create(
                        kode_indikator=code,
                        defaults={
                            'nama_indikator': item['nama'],
                            'unit': unit,
                            'jenis': 'NASIONAL',
                            'dimensi_mutu': 'AMAN',
                            'numerator': f"Jumlah kepatuhan {item['nama']} yang terverifikasi",
                            'denominator': f"Jumlah total kesempatan / target pemenuhan di unit {unit.name}",
                            'target_nilai': Decimal(str(item['target'])),
                            'satuan': item['satuan'],
                            'rencana_aksi': f"Sosialisasi SPO, audit kepatuhan mingguan, dan evaluasi hasil di unit {unit.name}.",
                            'pj': f"Penanggung Jawab Mutu {unit.name}",
                            'aktif': True,
                        }
                    )
                    ind_objs.append(ind)
                    if created: total_ind_created += 1

                # RS
                for i_idx, item in enumerate(u_spec['rs'], 1):
                    code = f"BAB-{key}-RS-{i_idx:02d}"
                    dim = 'KESELAMATAN' if 'insiden' in item['nama'].lower() or 'kematian' in item['nama'].lower() else 'EFEKTIF'
                    ind, created = IndikatorMutu.objects.get_or_create(
                        kode_indikator=code,
                        defaults={
                            'nama_indikator': item['nama'],
                            'unit': unit,
                            'jenis': 'IMP_RS',
                            'dimensi_mutu': 'AMAN',
                            'numerator': f"Jumlah kasus/capaian {item['nama']} yang terlaporkan",
                            'denominator': f"Jumlah populasi berisiko / seluruh tindakan di unit {unit.name}",
                            'target_nilai': Decimal(str(item['target'])),
                            'satuan': item['satuan'],
                            'rencana_aksi': f"Monitoring indikator mutu prioritas RS secara berkala dan pelaporan ke Komite Mutu.",
                            'pj': f"Ketua Tim Mutu Pelayanan Klinis {unit.name}",
                            'aktif': True,
                        }
                    )
                    ind_objs.append(ind)
                    if created: total_ind_created += 1

                # UNIT
                for i_idx, item in enumerate(u_spec['unit'], 1):
                    code = f"BAB-{key}-UNT-{i_idx:02d}"
                    ind, created = IndikatorMutu.objects.get_or_create(
                        kode_indikator=code,
                        defaults={
                            'nama_indikator': item['nama'],
                            'unit': unit,
                            'jenis': 'IMP_UNIT',
                            'dimensi_mutu': 'TEPAT_WAKTU' if 'waktu' in item['nama'].lower() or 'menit' in item['nama'].lower() else 'EFEKTIF',
                            'numerator': f"Capaian kepatuhan pelaksanaan {item['nama']}",
                            'denominator': f"Total seluruh proses/pasien di unit {unit.name}",
                            'target_nilai': Decimal(str(item['target'])),
                            'satuan': item['satuan'],
                            'rencana_aksi': f"Audit kepatuhan checklist harian dan penguatan SPO perawat/petugas.",
                            'pj': f"Kepala Ruangan {unit.name}",
                            'aktif': True,
                        }
                    )
                    ind_objs.append(ind)
                    if created: total_ind_created += 1

                self.stdout.write(f"    - Indikator: {len(ind_objs)} terdaftar (INM/RS/Unit)")

                # 2. Seed 5 Clinical Risks
                for r_idx, r_name in enumerate(u_spec['risiko'], 1):
                    # Tentukan tingkat keparahan & metode evaluasi
                    is_sentinel_prone = any(w in r_name.lower() for w in [
                        'wrong', 'kematian', 'henti jantung', 'syok', 'ruptur', 'asfiksia',
                        'benda asing', 'ketinggalan', 'perdarahan', 'sepsis', 'kebutaan', 'dislokasi', 'dvt'
                    ])
                    dampak = 5 if is_sentinel_prone else 4
                    prob = 3
                    
                    # Hubungkan ke indikator unit yang paling relevan jika ada
                    linked_ind = ind_objs[r_idx - 1] if r_idx - 1 < len(ind_objs) else (ind_objs[0] if ind_objs else None)
                    target_ind = linked_ind.target_nilai if linked_ind else Decimal('100.0')

                    # Metode FMEA untuk risiko berdampak tinggi / sentinel prone
                    metode = 'FMEA' if is_sentinel_prone else 'STANDAR'
                    deteksi = 3 if metode == 'FMEA' else None
                    rpn = (dampak * prob * deteksi) if metode == 'FMEA' else None

                    deskripsi = (
                        f"Potensi kejadian: {r_name} pada unit {u_spec['name']}. "
                        f"Berdasarkan baseline masalah: {u_spec['masalah'][:200]} "
                        f"dan data pendukung: {u_spec['data'][:200]}."
                    )

                    control = (
                        f"1. SPO pelayanan klinis dan keselamatan pasien di unit {u_spec['name']}.\n"
                        f"2. Verifikasi ganda (double-check) oleh petugas dan perawat shift.\n"
                        f"3. Pelaksanaan audit berkala kepatuhan checklist pelayanan."
                    )

                    rencana = (
                        f"1. Refresh training SPO & simulasi penanganan {r_name}.\n"
                        f"2. Pemasangan barrier proteksi dan visual alert di area tindakan.\n"
                        f"3. Monitoring real-time kepatuhan indikator mutu: {linked_ind.nama_indikator if linked_ind else '-'}.\n"
                        f"4. Audit mingguan dan pembahasan berkala pada morning report."
                    )

                    failure_mode = ""
                    if metode == 'FMEA':
                        failure_mode = (
                            f"Mode Kegagalan: Kegagalan deteksi dini / deviasi prosedur pada {r_name}.\n"
                            f"Penyebab Potensial: Beban kerja tinggi, kelelahan shift, kurangnya komunikasi efektif handover.\n"
                            f"Efek: Perburukan klinis pasien, cedera medis permanen / kematian, peningkatan lama rawat (LOS).\n"
                            f"Barrier saat ini: SPO unit dan checklist operasional."
                        )

                    tim_fmea = f"Ka. Ruang {u_spec['name']}, DPJP Utama, IPCN, Komite Mutu & Keselamatan Pasien" if metode == 'FMEA' else ""

                    r_obj, created = RisikoUnit.objects.get_or_create(
                        unit=unit,
                        kategori_risiko='KLINIS',
                        jenis_risiko=r_name,
                        defaults={
                            'tahun': 2026,
                            'periode': 'TRIWULAN_1',
                            'masalah': u_spec['masalah'],
                            'data_pendukung': u_spec['data'],
                            'deskripsi_risiko': deskripsi,
                            'dampak': dampak,
                            'probabilitas': prob,
                            'pengendalian_ada': control,
                            'strategi_mitigasi': 'KURANGI',
                            'rencana_aksi': rencana,
                            'pj_mitigasi': f"Ka. Ruangan & Tim Mutu {u_spec['name']}",
                            'biaya_mitigasi': Decimal('0'),
                            'status': 'IDENTIFIKASI',
                            'indikator_mutu_terkait': linked_ind,
                            'target_capaian_indikator': target_ind,
                            'metode_evaluasi': metode,
                            'tim_evaluasi': tim_fmea,
                            'deteksi_fmea': deteksi,
                            'rpn_fmea': rpn,
                            'failure_mode_fmea': failure_mode,
                        }
                    )
                    if created: total_risk_created += 1

                self.stdout.write(f"    - Risiko Klinis: {len(u_spec['risiko'])} risiko ter-seed")

        self.stdout.write(self.style.SUCCESS(
            f"\nSELESAI! Berhasil men-seed:\n"
            f"  - Total Indikator Baru: {total_ind_created} (total di sistem: {IndikatorMutu.objects.count()})\n"
            f"  - Total Risiko Baru   : {total_risk_created} (total di sistem: {RisikoUnit.objects.count()})"
        ))
