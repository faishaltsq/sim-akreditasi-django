"""Fase C3: matriks penapisan administrasi untuk lamaran masuk.

Aturan yang dijaga:
- Hasil saringan adalah **usulan**, bukan keputusan. Operator tetap yang
  memutuskan; sistem hanya menandai kriteria mana yang tidak terpenuhi.
- Kandidat yang tidak memenuhi satu kriteria wajib ditandai, bukan dibuang
  diam-diam, supaya jejak audit per tahap (KPS) tetap lengkap.
- Ketidaklengkapan berkas dilaporkan terpisah dari ketidaksesuaian kriteria.
"""
from django.utils import timezone

from sdm.models import BerkasPelamar, Pelamar, PenilaianTahap

# Kualifikasi pendidikan minimum yang dapat dibaca dari teks bebas lowongan.
PENDIDIKAN_MINIMUM_DARI_TEKS = [
    ('s3', 'S3'), ('doktor', 'S3'),
    ('s2', 'S2'), ('magister', 'S2'),
    ('s1', 'S1'), ('sarjana', 'S1'), ('d4', 'S1'),
    ('d3', 'D3'), ('diploma', 'D3'),
    ('sma', 'SMA_SMK'), ('smk', 'SMA_SMK'),
]


def _pendidikan_minimum(vacancy):
    """Derive the minimum education grade from the free-text qualification."""
    teks = (vacancy.kualifikasi_pendidikan or '').lower()
    for kunci, kode in PENDIDIKAN_MINIMUM_DARI_TEKS:
        if kunci in teks:
            return kode
    return None


def _usia(pelamar, today):
    if not pelamar.tanggal_lahir:
        return None
    return today.year - pelamar.tanggal_lahir.year - (
        (today.month, today.day) < (pelamar.tanggal_lahir.month, pelamar.tanggal_lahir.day)
    )


def screen_application(lamaran, *, today=None):
    """Return a screening verdict for one application.

    ``layak`` is a proposal: every unmet criterion is listed so the operator
    can see what failed. A candidate with missing data is reported as
    ``perlu_dilengkapi`` rather than silently failing.
    """
    today = today or timezone.localdate()
    vacancy = lamaran.lowongan
    pelamar = lamaran.pelamar

    masalah = []
    perlu_dilengkapi = []

    if pelamar is None:
        # Lamaran dicatat langsung oleh SDM tanpa data profil pelamar.
        return {
            'lamaran': lamaran,
            'layak': False,
            'perlu_dilengkapi': True,
            'masalah': ['Profil pelamar belum lengkap.'],
            'berkas': [],
        }

    # ── Pendidikan ──
    pendidikan_min = _pendidikan_minimum(vacancy)
    if pendidikan_min and pelamar.pendidikan_terakhir:
        if (
            Pelamar.URUTAN_PENDIDIKAN.get(pelamar.pendidikan_terakhir, 0)
            < Pelamar.URUTAN_PENDIDIKAN.get(pendidikan_min, 0)
        ):
            masalah.append(
                f'Pendidikan {pelamar.get_pendidikan_terakhir_display()} '
                f'di bawah minimum {pendidikan_min}.'
            )
    elif pendidikan_min:
        perlu_dilengkapi.append('Pendidikan terakhir belum diisi.')

    # ── IPK ──
    if vacancy.ipk_minimal is not None:
        if pelamar.ipk is None:
            perlu_dilengkapi.append('IPK belum diisi.')
        elif pelamar.ipk < vacancy.ipk_minimal:
            masalah.append(
                f'IPK {pelamar.ipk} di bawah minimum {vacancy.ipk_minimal}.'
            )

    # ── Usia ──
    if vacancy.batas_usia is not None:
        usia = _usia(pelamar, today)
        if usia is None:
            perlu_dilengkapi.append('Tanggal lahir belum diisi.')
        elif usia > vacancy.batas_usia:
            masalah.append(
                f'Usia {usia} tahun melebihi batas {vacancy.batas_usia} tahun.'
            )

    # ── Pengalaman ──
    if vacancy.pengalaman_minimal_bulan is not None:
        if pelamar.pengalaman_bulan is None:
            perlu_dilengkapi.append('Pengalaman kerja belum diisi.')
        elif pelamar.pengalaman_bulan < vacancy.pengalaman_minimal_bulan:
            masalah.append(
                f'Pengalaman {pelamar.pengalaman_bulan} bulan di bawah '
                f'minimum {vacancy.pengalaman_minimal_bulan} bulan.'
            )

    # ── Kelengkapan berkas ──
    berkas = list(
        lamaran.berkas.all().order_by('jenis')
    )
    belum_unggah = [
        b.jenis for b in berkas if not b.berkas
    ]
    for jenis in belum_unggah:
        masalah.append(f'Berkas {jenis} belum diunggah.')

    return {
        'lamaran': lamaran,
        'layak': not masalah and not perlu_dilengkapi,
        'perlu_dilengkapi': bool(perlu_dilengkapi),
        'masalah': masalah,
        'perlu_dilengkapi_pesan': perlu_dilengkapi,
        'berkas': berkas,
    }


def record_screening(lamaran, *, actor, usulan_lulus, catatan=''):
    """Persist the administrative screening verdict (append-only)."""
    return PenilaianTahap.objects.create(
        lamaran=lamaran,
        tahap='SELEKSI_ADMIN',
        hasil='LULUS' if usulan_lulus else 'TIDAK_LULUS',
        catatan=catatan,
        penguji=actor,
    )


def screening_queue(vacancy):
    """Applications of one vacancy awaiting administrative screening."""
    return (
        vacancy.applications
        .select_related('pelamar')
        .prefetch_related('berkas')
        .order_by('created_at')
    )


def berkas_summary(lamaran):
    """Per-document state counts for the screening matrix header."""
    counts = {'VALID': 0, 'PERLU_KLARIFIKASI': 0, 'TIDAK_LENGKAP': 0,
              'MENUNGGU': 0}
    for b in lamaran.berkas.all():
        counts[b.status] = counts.get(b.status, 0) + 1
    return counts
