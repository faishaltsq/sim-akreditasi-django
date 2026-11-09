"""Parser dan penyimpan baris tindakan asesmen (tarif editable + EP per item)."""

import re
from decimal import Decimal, InvalidOperation

from django.db import transaction

from akreditasi.models import AuditLog, StandardItem
from klinis.models import MasterIcd9, SikiIntervensi
from klinis.services.ep_tindakan import primary_for
from klinis.services.tarif import refresh_acuan, sync_billing_tindakan

from .models import TindakanAsesmen

_ROW_RE = re.compile(r'^tindakan_(\d+)_id$')
_EP_STATUS = {'TERPENUHI', 'BELUM', 'NA'}
_SUMBER = {'MASTER', 'SARAN', 'MANUAL'}
_JENIS = {'ICD9', 'SIKI', 'BEBAS'}


def _dec(raw):
    if raw in (None, ''):
        return None
    s = str(raw).strip().replace('Rp', '').replace(' ', '')
    if not s:
        return None
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', s):
        s = s.replace('.', '')
    try:
        value = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None


def has_tindakan_payload(request):
    """True bila form memakai UI baris tindakan (bukan form teks bebas lama)."""
    return any(key.startswith('tindakan_') for key in request.POST)


def parse_tindakan(request):
    """
    Baca baris tindakan dari POST terindeks `tindakan_<i>_*`.

    Kode ICD-9 ganda dalam satu kunjungan diabaikan (baris pertama menang),
    karena billing hanya boleh punya satu baris per kode.
    """
    rows = []
    seen_icd9 = set()
    indexes = sorted({int(m.group(1)) for key in request.POST if (m := _ROW_RE.match(key))})

    for i in indexes:
        if request.POST.get(f'tindakan_{i}_hapus') == '1':
            continue

        jenis = (request.POST.get(f'tindakan_{i}_jenis') or 'ICD9').upper()
        if jenis not in _JENIS:
            jenis = 'BEBAS'
        kode = (request.POST.get(f'tindakan_{i}_kode') or '').strip()

        if jenis == 'ICD9':
            if not kode or not MasterIcd9.objects.filter(kode=kode).exists():
                continue
            if kode in seen_icd9:
                continue
            seen_icd9.add(kode)

        sumber = (request.POST.get(f'tindakan_{i}_sumber') or 'MANUAL').upper()
        ep_status = (request.POST.get(f'tindakan_{i}_ep_status') or 'BELUM').upper()

        rows.append({
            'id': (request.POST.get(f'tindakan_{i}_id') or '').strip(),
            'jenis': jenis,
            'kode': kode,
            'nama': (request.POST.get(f'tindakan_{i}_nama') or '').strip()[:200],
            'sumber': sumber if sumber in _SUMBER else 'MANUAL',
            'tarif': _dec(request.POST.get(f'tindakan_{i}_tarif')),
            'catatan_tarif': (request.POST.get(f'tindakan_{i}_catatan_tarif') or '').strip(),
            'ep_sub': (request.POST.get(f'tindakan_{i}_ep_sub') or '').strip(),
            'ep_status': ep_status if ep_status in _EP_STATUS else 'BELUM',
            'ep_catatan': (request.POST.get(f'tindakan_{i}_ep_catatan') or '').strip(),
        })

    return rows


@transaction.atomic
def simpan_tindakan(kunjungan, rows, user=None):
    """
    Sinkronkan baris tindakan kunjungan dengan hasil parse POST.

    - Baris yang dikirim dengan `id` diperbarui; tanpa `id` dibuat baru.
    - Baris lama yang tidak dikirim lagi dihapus.
    - Override tarif tanpa catatan alasan menolak seluruh penyimpanan.
    - BillingItem ASESMEN selalu diturunkan dari `tarif_efektif` baris.
    """
    existing = {str(t.pk): t for t in kunjungan.tindakan_asesmen.all()}
    saved = []

    for urutan, row in enumerate(rows, start=1):
        is_new = not row['id'] or row['id'] not in existing
        line = TindakanAsesmen(kunjungan=kunjungan) if is_new else existing.pop(row['id'])

        line.urutan = urutan
        line.jenis = row['jenis']
        line.kode = row['kode']
        line.nama = row['nama'] or row['kode'] or 'Tindakan'
        line.sumber_data = row['sumber']
        line.tarif = row['tarif']
        line.catatan_tarif = row['catatan_tarif']
        line.ep_status = row['ep_status']
        line.ep_catatan = row['ep_catatan']
        line.diubah_oleh = user

        if row['jenis'] == 'ICD9':
            line.icd9 = MasterIcd9.objects.filter(kode=row['kode']).first()
            line.siki = None
        elif row['jenis'] == 'SIKI':
            line.icd9 = None
            line.siki = SikiIntervensi.objects.filter(kode=row['kode']).first()
        else:
            line.icd9 = None
            line.siki = None

        if row['ep_sub']:
            line.standard_item = StandardItem.objects.filter(sub_standard=row['ep_sub']).first()
        elif is_new:
            rule = primary_for(row['jenis'], row['kode'])
            line.standard_item = (
                StandardItem.objects.filter(sub_standard=rule.sub_standard).first()
                if rule else None
            )
        else:
            line.standard_item = None

        saved.append(line)

    refresh_acuan(kunjungan, saved)

    missing_notes = [
        line.kode or line.nama for line in saved
        if line.tarif is not None and line.tarif_acuan is not None
        and line.tarif != line.tarif_acuan and not line.catatan_tarif
    ]
    if missing_notes:
        raise ValueError(
            'Catatan alasan wajib diisi untuk perubahan tarif: '
            + ', '.join(missing_notes)
        )

    for line in saved:
        line.save()

    for line in existing.values():
        line.delete()

    sync_billing_tindakan(kunjungan, saved, user=user)

    for line in saved:
        line.save(update_fields=['billing_item'])
        if (line.tarif is not None and line.tarif_acuan is not None
                and line.tarif != line.tarif_acuan):
            AuditLog.objects.create(
                user=user,
                aksi='UPDATE',
                model_name='TindakanAsesmen',
                object_repr=f'{kunjungan.no_kunjungan} — {line.kode or line.nama}',
                detail=(f'Tarif diubah dari {line.tarif_acuan} menjadi {line.tarif}. '
                        f'Alasan: {line.catatan_tarif}'),
            )

    return saved
