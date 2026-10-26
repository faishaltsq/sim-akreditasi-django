"""D-4: the 13 credential evidence documents and their STARKES EP mapping.

The list mirrors the "13 dokumen bukti proses kredensial" table from
``Lakukan perbaikan saat pengajuan kredensial.docx``. Standards are declared
exactly as written there; ``map_to_catalog`` resolves them against the live
catalogue and reports anything missing instead of inventing an EP.
"""
from akreditasi.models import StandardItem

DOKUMEN_BUKTI = [
    {
        'kode': 'WHITE_PAPER',
        'label': 'Master White Paper & Panduan Kualifikasi Staf',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12'],
        'ep': 'EP 1 — Menetapkan proses kredensial berdasarkan buku putih dan '
              'kualifikasi yang dipersyaratkan.',
    },
    {
        'kode': 'FORM_PENGAJUAN',
        'label': 'Formulir Pengajuan Kredensial / Rekredensial Mandiri',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12'],
        'ep': 'EP 1 — Bukti pengajuan rincian kewenangan klinis oleh staf '
              'berdasarkan kualifikasi dan rekam jejak.',
    },
    {
        'kode': 'PSV',
        'label': 'Dokumen Hasil Verifikasi Sumber Primer (PSV)',
        'standar': ['KPS 5'],
        'ep': 'EP 1 & EP 2 — Bukti keabsahan ijazah, STR, dan izin praktik dari '
              'institusi penerbit resmi.',
    },
    {
        'kode': 'EFILE',
        'label': 'Berkas Arsip e-File Kepegawaian (Folder B & C)',
        'standar': ['KPS 5', 'KPS 6', 'KPS 7'],
        'ep': 'EP 2 — Kelengkapan dokumen kualifikasi dan izin praktik yang '
              'terverifikasi dalam sistem.',
    },
    {
        'kode': 'LOGBOOK',
        'label': 'Logbook Klinis & Portofolio Pengalaman Staf',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12'],
        'ep': 'EP 1 & EP 2 — Rekam jejak jumlah penanganan kasus dan portofolio '
              'kompetensi klinis pemohon.',
    },
    {
        'kode': 'SELF_ASSESSMENT_RKK',
        'label': 'Formulir Self-Assessment RKK',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12'],
        'ep': 'EP 2 — Daftar usulan kewenangan klinis yang rinci untuk setiap staf.',
    },
    {
        'kode': 'BERITA_ACARA_PEER_REVIEW',
        'label': 'Berita Acara Hasil Peer Review / Asesmen Panel Mitra Bestari',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12', 'KPS 13'],
        'ep': 'EP 1 & EP 2 — Catatan penelaahan kompetensi, portofolio, dan rekam '
              'jejak kinerja secara obyektif oleh mitra bestari.',
    },
    {
        'kode': 'MONITORING_SUPERVISI',
        'label': 'Formulir Monitoring Supervisi Klinis & Catatan Syarat Khusus',
        'standar': ['KPS 11', 'KPS 13', 'KPS 14'],
        'ep': 'EP 1 & EP 2 — Rekaman pemantauan pelayanan klinis yang memerlukan '
              'supervisi atau batasan wewenang.',
    },
    {
        'kode': 'REKOMENDASI_KOMITE',
        'label': 'Surat Rekomendasi Kredensial dari Ketua Komite',
        'standar': ['KPS 7', 'TKRS 8'],
        'ep': 'EP 3 — Rekomendasi tertulis penugasan klinis dari ketua komite '
              'profesi kepada pimpinan rumah sakit.',
    },
    {
        'kode': 'SPK_RKK',
        'label': 'Surat Penugasan Klinis (SPK) & Rincian Kewenangan Klinis '
                 '(E-SPK & E-RKK) Terverifikasi QR Code',
        'standar': ['KPS 7', 'KPS 10', 'KPS 12', 'KPS 14', 'KPS 17'],
        'ep': 'EP 3 (KPS 7/10/12) & EP 1–2 (KPS 14/17) — Penetapan resmi penugasan '
              'klinis dan rincian kewenangan oleh Direktur Utama.',
    },
    {
        'kode': 'EWS_REMINDER',
        'label': 'Log Notifikasi EWS & Reminder Re-Kredensial',
        'standar': ['KPS 7', 'KPS 11'],
        'ep': 'EP 3 (KPS 7) — Bukti pemantauan berkala dan pembaruan kewenangan '
              'klinis sebelum masa berlaku SPK berakhir.',
    },
    {
        'kode': 'AUDIT_RME',
        'label': 'Laporan Audit Log Akses RME & Matriks Pengamanan',
        'standar': ['KPS 10', 'ARK 4', 'PMKP 8', 'MRMIK 2'],
        'ep': 'KPS 10 EP 3, ARK 4 EP 1–2, PMKP 8 EP 1, MRMIK 2 EP 1–2 — Bukti '
              'pembatasan akses operasional nyata dan keamanan data rekam medis.',
    },
    {
        'kode': 'DIREKTORI_KEWENANGAN',
        'label': 'Direktori & Peta Sebaran Kewenangan Klinis Unit Pelayanan',
        'standar': ['KPS 10', 'TKRS 5', 'KPS 3', 'TKRS 11'],
        'ep': 'KPS 10 EP 1 & 4, TKRS 5 EP 2, KPS 3 EP 1, TKRS 11 EP 3 — Bukti '
              'ketersediaan penugasan staf kompeten yang mudah diakses.',
    },
]


def _standard_exists(sub_standard):
    return StandardItem.objects.filter(sub_standard=sub_standard).exists()


def map_to_catalog():
    """Resolve each document's standards against the live EP catalogue.

    A standard with no catalogue rows is reported in ``unmatched``; it is
    never silently dropped, because a missing EP means the evidence claim is
    unverifiable, not that the requirement passed.
    """
    rows = []
    for entry in DOKUMEN_BUKTI:
        matched, unmatched = [], []
        for standard in entry['standar']:
            (matched if _standard_exists(standard) else unmatched).append(standard)
        rows.append({
            **entry,
            'matched': matched,
            'unmatched': unmatched,
        })
    return rows
