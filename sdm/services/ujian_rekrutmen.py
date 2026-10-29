"""Fase C4: mesin ujian berbasis komputer (CBT) untuk rekrutmen.

Aturan yang dijaga:
- Pengacakan urutan ditentukan **sekali** saat sesi dibuat dan disimpan, jadi
  me-refresh halaman tidak mengocok kertas ulang di tengah pengerjaan.
- Batas waktu adalah timestamp server. Klien hanya menampilkannya; menutup
  browser tidak memperpanjang waktu.
- Submit setelah waktu habis ditolak. Nilai dihitung dari bobot soal, bukan
  dari jumlah jawaban benar.
"""
import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from sdm.models import JawabanUjian, PaketSoal, SesiUjian, Soal


def acak_urutan(paket):
    """Return a shuffled list of question ids for a packet."""
    ids = list(
        paket.soal.order_by('nomor').values_list('id', flat=True)
    )
    random.shuffle(ids)
    return [str(i) for i in ids]


def buat_sesi(lamaran, *, paket):
    """Open one exam session for an application.

    A second live session is never opened: the candidate finishes or the
    attempt is finalised first.
    """
    aktif = SesiUjian.objects.filter(
        lamaran=lamaran, status='BERLANGSUNG'
    ).first()
    if aktif is not None:
        return aktif

    with transaction.atomic():
        sesi = SesiUjian.objects.create(
            lamaran=lamaran,
            paket=paket,
            urutan_soal=acak_urutan(paket),
            batas_waktu=timezone.now() + timezone.timedelta(
                minutes=paket.durasi_menit
            ),
        )
    return sesi


def soal_untuk_sesi(sesi):
    """Return the packet's questions in this session's stored order."""
    urutan = sesi.urutan_soal or []
    if not urutan:
        return list(sesi.paket.soal.order_by('nomor'))
    by_id = {str(s.pk): s for s in sesi.paket.soal.all()}
    soal = [by_id[i] for i in urutan if i in by_id]
    # Soal baru yang ditambahkan setelah sesi dibuat tetap muncul di akhir.
    sisa = [s for s in sesi.paket.soal.all() if str(s.pk) not in set(urutan)]
    return soal + sisa


def catat_jawaban(sesi, soal_id, jawaban):
    """Record one answer, rejecting anything after the deadline or after the
    paper was already submitted."""
    if sesi.status != 'BERLANGSUNG' or sesi.is_kedaluwarsa():
        raise PermissionError(
            'Waktu ujian sudah habis.' if sesi.is_kedaluwarsa()
            else 'Sesi ujian sudah berakhir.'
        )
    jawaban = (jawaban or '').upper()
    if jawaban not in ('A', 'B', 'C', 'D'):
        raise ValueError('Jawaban tidak dikenal.')

    soal = Soal.objects.filter(pk=soal_id, paket=sesi.paket).first()
    if soal is None:
        raise ValueError('Soal tidak ada di paket ini.')

    obj, _ = JawabanUjian.objects.update_or_create(
        sesi=sesi, soal=soal, defaults={'jawaban': jawaban},
    )
    return obj


def catat_pindah_fokus(sesi):
    """Anti-cheating: count the candidate leaving the exam page."""
    if sesi.status != 'BERLANGSUNG':
        return sesi.pindah_fokus
    SesiUjian.objects.filter(pk=sesi.pk).update(
        pindah_fokus=sesi.pindah_fokus + 1
    )
    sesi.refresh_from_db()
    return sesi.pindah_fokus


def nilai_sesi(sesi):
    """Score a finished session on question weights, returning a percentage."""
    jawaban = {
        str(j.soal_id): j.jawaban for j in sesi.jawaban.all()
    }
    total_bobot = Decimal('0')
    perolehan = Decimal('0')
    for soal in sesi.paket.soal.all():
        total_bobot += soal.bobot
        if jawaban.get(str(soal.pk)) == soal.jawaban_benar:
            perolehan += soal.bobot
    if total_bobot == 0:
        return Decimal('0.00')
    return (perolehan / total_bobot * Decimal('100')).quantize(Decimal('0.01'))


def selesaikan_sesi(sesi, *, paksa=False):
    """Finalise a session: score it, then mark SELESAI or KEDALUWARSA."""
    if sesi.status != 'BERLANGSUNG':
        return sesi
    if not paksa and not sesi.is_kedaluwarsa():
        # Belum waktunya submit; front-end memakai aksi submit tersendiri.
        pass

    nilai = nilai_sesi(sesi)
    passing = Decimal(str(sesi.paket.passing_grade or 0))
    lulus = nilai >= passing
    sesi.status = 'KEDALUWARSA' if sesi.is_kedaluwarsa() else 'SELESAI'
    sesi.selesai_at = timezone.now()
    sesi.nilai = nilai
    sesi.lulus = lulus
    sesi.save(update_fields=[
        'status', 'selesai_at', 'nilai', 'lulus',
    ])
    return sesi


def ranking_lowongan(lowongan):
    """Candidates of one vacancy ranked by exam score (highest first).

    Only finished sessions are ranked; a running session is not a result.
    """
    sesi = (
        SesiUjian.objects.filter(
            lamaran__lowongan=lowongan,
            status__in=('SELESAI', 'KEDALUWARSA'),
            nilai__isnull=False,
        )
        .select_related('lamaran', 'lamaran__pelamar')
        .order_by('-nilai', 'selesai_at')
    )
    return list(sesi)
