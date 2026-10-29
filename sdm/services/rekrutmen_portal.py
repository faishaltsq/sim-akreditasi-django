"""Fase C2: portal pelamar publik (self-service, tanpa akun Django).

Aturan yang dijaga:
- Akses lewat token yang tersimpan di ``Pelamar.token``; token itulah
  kapabilitasnya, bukan hash. Tidak ada enumerasi id di URL publik.
- Unggahan dibatasi tipe (PDF/JPG/PNG) dan ukuran maksimum; file dibuang
  sebelum barisnya dibuat supaya tidak ada berkas yatim.
- Pelamar hanya melihat lamaran miliknya sendiri.
"""
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.utils import timezone

from sdm.models import BerkasPelamar, Lamaran, Lowongan, Pelamar

# Berkas yang boleh diunggah pelamar dan batas ukurannya (dokumen modul
# rekrutmen menyebut PDF/JPG). Satu tempat, bukan tersebar di form/view.
BERKAS_EXTENSI = ['pdf', 'jpg', 'jpeg', 'png']
BERKAS_MAKS_BYTE = 5 * 1024 * 1024  # 5 MB

VALIDATOR_BERKAS = FileExtensionValidator(allowed_extensions=BERKAS_EXTENSI)


def lowongan_terbuka():
    """Vacancies a candidate may apply to right now."""
    today = timezone.localdate()
    return (
        Lowongan.objects.filter(status='DIBUKA')
        .select_related('unit_kerja')
        .exclude(tanggal_buka__gt=today)
        .exclude(tanggal_tutup__lt=today)
        .order_by('-created_at')
    )


def dokumen_wajib(vacancy):
    """Required document kinds for a vacancy.

    STR/SIP are required for clinical professions only: the module document
    says "STR Aktif untuk Tenaga Kesehatan", so a non-clinical vacancy must not
    demand a licence the role does not use.
    """
    profesi = (vacancy.profesi or '').lower()
    klinis = any(
        kata in profesi
        for kata in ('dokter', 'perawat', 'bidan', 'apoteker', 'farmasi',
                     'ahli gizi', 'dietisien', 'nutrisionis', 'radiografer',
                     'elektromedis', 'analis', 'laboratorium', 'atlm',
                     'fisioterapi', 'terapi', 'psikolog', 'perekam',
                     'sanitarian', 'k3')
    )
    wajib = ['KTP', 'IJAZAH', 'CV']
    if klinis:
        wajib += ['STR', 'SIP']
    return wajib


def validate_berkas(file_obj):
    """Reject anything that is not an allowed document type or is too large."""
    if file_obj is None:
        return
    VALIDATOR_BERKAS(file_obj)
    if file_obj.size > BERKAS_MAKS_BYTE:
        raise ValidationError(
            f'Ukuran berkas melebihi {BERKAS_MAKS_BYTE // (1024 * 1024)} MB.'
        )


def create_application(*, vacancy, nama, email, telepon, files):
    """Register a candidate and their application in one transaction.

    ``files`` maps document kind -> UploadedFile. Missing required documents
    are reported back as a field error keyed by the document kind, so the
    candidate sees exactly which file is still absent instead of a generic
    failure. Already-uploaded documents are attached as ``BerkasPelamar``.
    """
    today = timezone.localdate()
    if vacancy.status != 'DIBUKA':
        raise ValidationError({'lowongan': 'Lowongan ini tidak dibuka.'})
    if vacancy.tanggal_buka and today < vacancy.tanggal_buka:
        raise ValidationError(
            {'lowongan': 'Pendaftaran belum dibuka untuk lowongan ini.'}
        )
    if vacancy.tanggal_tutup and today > vacancy.tanggal_tutup:
        raise ValidationError(
            {'lowongan': 'Pendaftaran untuk lowongan ini sudah ditutup.'}
        )

    wajib = dokumen_wajib(vacancy)
    kurang = [jenis for jenis in wajib if not files.get(jenis)]
    if kurang:
        raise ValidationError({
            jenis: f'Berkas {jenis} wajib diunggah.'
            for jenis in kurang
        })

    with transaction.atomic():
        pelamar = Pelamar.objects.create(
            nama_lengkap=nama.strip(), email=email.strip(), telepon=telepon.strip(),
        )
        lamaran = Lamaran.objects.create(
            lowongan=vacancy,
            pelamar=pelamar,
            nama_pelamar=pelamar.nama_lengkap,
            kontak=(f'{pelamar.email} / {pelamar.telepon}'.strip(' /')),
            status='MASUK',
        )
        for jenis, file_obj in files.items():
            if not file_obj:
                continue
            try:
                validate_berkas(file_obj)
            except ValidationError as exc:
                # Already validated at the field; re-raise keyed so the form
                # can attach it to the right upload input.
                raise ValidationError({jenis: exc.messages})
            BerkasPelamar.objects.create(
                lamaran=lamaran, jenis=jenis, berkas=file_obj,
            )
    return lamaran


def application_status(lamaran):
    """Per-document readiness plus the stage label for the candidate dashboard."""
    berkas = {
        b.jenis: b.get_status_display()
        for b in lamaran.berkas.all()
    }
    return {
        'lamaran': lamaran,
        'status': lamaran.get_status_display(),
        'berkas': berkas,
        'lengkap': all(
            state == 'Valid' for state in berkas.values()
        ) if berkas else False,
    }
