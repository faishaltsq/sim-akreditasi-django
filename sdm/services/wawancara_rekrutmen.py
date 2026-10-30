"""Fase C5: penjadwalan, undangan, scorecard, dan skor gabungan.

Aturan yang dijaga:
- Bobot setiap komponen skor adalah **konstanta yang bisa dikonfigurasi**, bukan
  angka yang ditanam di logika. Modul rekrutmen menulis
  "Seleksi Berkas + Tes CBT + Wawancara HRD + Wawancara User/Komite Profesi"
  tanpa menyebut persentase; bila komite belum menetapkan angka, bobot dibiarkan
  kosong dan skor gabungan tidak pernah ditampilkan sebagai keputusan.
- Sesi ujian yang masih berjalan tidak diperlakukan sebagai nilai.
- Wawancara di lowongan berbeda boleh memakai slot waktu yang sama.
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from sdm.models import JadwalWawancara, ScorecardWawancara, SesiUjian

# ── Konstanta bobot skor gabungan ──────────────────────────────────────────
# Kosong berarti "belum ditetapkan komite". Jangan mengisi angka tanpa SK:
# skor gabungan hanya dihitung bila semua bobot terisi dan berjumlah 100.
BOBOT_SKOR_GABUNGAN = {
    'SELEKSI_BERKAS': None,
    'TES_KOMPETENSI': None,
    'WAWANCARA_HRD': None,
    'WAWANCARA_USER': None,
}


def bobot_terkonfigurasi():
    """True when the weights are set and sum to exactly 100.

    A component the committee has not adopted may carry weight 0; what is not
    acceptable is a partial configuration that would silently rescale the rest.
    """
    nilai = list(BOBOT_SKOR_GABUNGAN.values())
    if any(v is None or v < 0 for v in nilai):
        return False
    return sum(nilai) == 100


def nilai_cbt(lamaran):
    """Latest finished CBT score for an application, or None."""
    sesi = (
        SesiUjian.objects.filter(
            lamaran=lamaran, status__in=('SELESAI', 'KEDALUWARSA'),
            nilai__isnull=False,
        )
        .order_by('-selesai_at')
        .first()
    )
    return float(sesi.nilai) if sesi else None


def nilai_wawancara(lamaran, jenis=None):
    """Mean of scorecard averages, optionally restricted to an interview role."""
    jadwal = getattr(lamaran, 'jadwal_wawancara', None)
    if jadwal is None:
        return None
    sheets = jadwal.scorecard.all()
    rata = [s.rata_rata() for s in sheets if jenis is None or s.jenis == jenis]
    rata = [r for r in rata if r is not None]
    if not rata:
        return None
    return float(sum(rata) / len(rata))


def nilai_seleksi_berkas(lamaran):
    """Score of the administrative stage, if one was recorded."""
    penilaian = lamaran.penilaian.filter(tahap='SELEKSI_ADMIN').first()
    if penilaian is None or penilaian.skor is None:
        return None
    return float(penilaian.skor)


def skor_gabungan(lamaran):
    """Weighted combined score, or None while any required part is missing.

    Only components with a nonzero weight are required. Unconfigured weights
    never produce a combined score.
    """
    if not bobot_terkonfigurasi():
        return None
    komponen = {
        'SELEKSI_BERKAS': nilai_seleksi_berkas(lamaran),
        'TES_KOMPETENSI': nilai_cbt(lamaran),
        'WAWANCARA_HRD': nilai_wawancara(lamaran, 'HRD'),
        'WAWANCARA_USER': nilai_wawancara(lamaran, 'USER'),
    }
    bobot = BOBOT_SKOR_GABUNGAN
    total = 0.0
    for kunci, nilai in komponen.items():
        bobot_komponen = bobot.get(kunci) or 0
        if bobot_komponen > 0 and nilai is None:
            return None
        if nilai is not None:
            total += nilai * bobot_komponen / 100
    return round(total, 2)


def jadwal_bentrok(*, lamaran, waktu, exclude=None):
    """Another slot in the same vacancy at the same time."""
    qs = JadwalWawancara.objects.filter(
        lamaran__lowongan_id=lamaran.lowongan_id, waktu=waktu
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.first()


def buat_jadwal(*, lamaran, waktu, mode='LURING', lokasi_tautan='',
                catatan='', penguji=(), actor=None):
    """Create an interview slot, rejecting a clash within the same vacancy."""
    if jadwal_bentrok(lamaran=lamaran, waktu=waktu):
        raise ValidationError({
            'waktu': 'Sudah ada wawancara lain pada waktu tersebut untuk '
                     'lowongan yang sama.',
        })
    jadwal = JadwalWawancara.objects.create(
        lamaran=lamaran, waktu=waktu, mode=mode,
        lokasi_tautan=lokasi_tautan, catatan=catatan, created_by=actor,
    )
    jadwal.penguji.set(penguji)
    return jadwal


def kirim_undangan(jadwal, *, actor=None):
    """Email the invitation to the candidate and every interviewer.

    A candidate without an address is skipped (SDM contacts them separately);
    a missing interviewer address is simply not mailed. Sending is recorded so
    the same invitation is not resent silently.
    """
    from django.core.mail import send_mail

    pelamar = jadwal.lamaran.pelamar
    penerima = []
    if pelamar is not None and pelamar.email:
        penerima.append(pelamar.email)
    penerima += [
        u.email for u in jadwal.penguji.all()
        if u.email and u.email not in penerima
    ]
    if not penerima:
        return 0

    subject = f'Undangan Wawancara — {jadwal.lamaran.lowongan.judul}'
    baris = [
        f'Wawancara untuk posisi {jadwal.lamaran.lowongan.judul}.',
        f'Waktu: {jadwal.waktu:%d %B %Y %H:%M}',
        f'Mode: {jadwal.get_mode_display()}',
    ]
    if jadwal.lokasi_tautan:
        label = 'Lokasi' if jadwal.mode == 'LURING' else 'Tautan'
        baris.append(f'{label}: {jadwal.lokasi_tautan}')
    if jadwal.catatan:
        baris.append(f'Catatan: {jadwal.catatan}')
    baris += ['', 'Hormat kami,', 'Tim Rekrutmen']

    terkirim = send_mail(
        subject, '\n'.join(baris), None, penerima, fail_silently=True,
    )
    if terkirim:
        JadwalWawancara.objects.filter(pk=jadwal.pk).update(
            undangan_terkirim_at=timezone.now()
        )
        jadwal.refresh_from_db()
    return terkirim


def catat_scorecard(*, jadwal, penguji, jenis=None, **nilai):
    """Create or update one interviewer's sheet for one interview.

    Values arrive as strings from the form, so they are coerced to Decimal
    here: leaving them as text would make the average raise TypeError.
    """
    catatan = nilai.pop('catatan', '')
    if jenis is not None and jenis not in dict(ScorecardWawancara.JENIS_CHOICES):
        raise ValidationError('Pilih jenis penguji HRD atau User / Komite.')
    bersih = {}
    for nama, value in nilai.items():
        if nama not in ScorecardWawancara.INDIKATOR:
            raise ValidationError(f'Indikator tidak dikenal: {nama}')
        field = ScorecardWawancara._meta.get_field(nama)
        bersih[nama] = field.clean(value if value not in (None, '') else None, None)
    defaults = {'catatan': catatan, **bersih}
    if jenis is not None:
        defaults['jenis'] = jenis
    sheet, _ = ScorecardWawancara.objects.update_or_create(
        jadwal=jadwal, penguji=penguji, defaults=defaults,
    )
    return sheet


def jadwal_mendatang(*, hari=7):
    """Interviews within the next N days, for the reminder command."""
    sekarang = timezone.now()
    return (
        JadwalWawancara.objects.filter(
            waktu__gte=sekarang,
            waktu__lte=sekarang + timedelta(days=hari),
        )
        .select_related('lamaran', 'lamaran__lowongan')
        .prefetch_related('penguji')
        .order_by('waktu')
    )
