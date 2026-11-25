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
            item = StandardItem.objects.filter(sub_standard=row['ep_sub']).first()
            if not item:
                root_sub = row['ep_sub'].split('.')[0].strip()
                item = StandardItem.objects.filter(sub_standard=root_sub).first()
            line.standard_item = item
        elif is_new:
            rule = primary_for(row['jenis'], row['kode'])
            if rule:
                item = StandardItem.objects.filter(sub_standard=rule.sub_standard).first()
                if not item:
                    root_sub = rule.sub_standard.split('.')[0].strip()
                    item = StandardItem.objects.filter(sub_standard=root_sub).first()
                line.standard_item = item
            else:
                line.standard_item = None
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

# ── F6.6 (S9-L2-01/S9-L2-02): tindakan poliklinik ber-tarif ──────────────────
#
# Jalur ini **tidak** menggantikan ``simpan_tindakan`` (form teks bebas IGD).
# Ia menambahkan satu tindakan poli jantung dari Master Tindakan Poli, mengambil
# nominal dari salinan ``KasusTindakan`` kelompok layanan episode (BPJS →
# ``tarif_bpjs``, selain itu → ``tarif_umum``), menautkan EP dari
# ``AturanEpTindakan``, lalu menulis ``BillingItem`` lewat penulis yang sama
# (``sync_billing_tindakan``, ``sumber='TINDAKAN'``).
#
# Tidak ada kode, nama, atau nominal yang dikarang di sini: pilihan datang dari
# salinan master kelompok, dan kode tanpa baris tarif tidak menghasilkan Rp 0.

#: Pelaksana matriks S9-L2-01. ``NAKES_LAIN`` belum punya nilai pada
#: ``TindakanAsesmen.execution_team`` (hanya MEDIS/KEPERAWATAN), jadi ia
#: ditolak dengan sebab eksplisit alih-alih dipetakan diam-diam ke perawat.
PELAKSANA_TEAM = {'DOKTER': 'MEDIS', 'PERAWAT': 'KEPERAWATAN'}
PELAKSANA_MATRIX = ('DOKTER', 'PERAWAT', 'NAKES_LAIN')


def tindakan_poli_options(visit):
    """Master Tindakan Poli untuk episode ini (kode + nama + nominal penjamin)."""
    from klinis.models import KasusTindakan
    from klinis.services.tarif import kelompok_for

    kelompok = kelompok_for(visit)
    if kelompok is None:
        return []
    rows = (
        KasusTindakan.objects
        .filter(kasus__kelompok=kelompok)
        .select_related('icd9')
        .order_by('kasus__urutan', 'urutan')
    )
    options = {}
    for row in rows:
        if row.icd9_id is None or row.icd9.kode in options:
            continue
        nominal = row.tarif_bpjs if visit.penjamin == 'BPJS' else row.tarif_umum
        options[row.icd9.kode] = {
            'kode': row.icd9.kode, 'nama': row.icd9.nama, 'nominal': nominal,
        }
    return list(options.values())


def _ep_standard_item(sub_standard):
    item = StandardItem.objects.filter(sub_standard=sub_standard).first()
    if item is None:
        item = StandardItem.objects.filter(sub_standard=sub_standard.split('.')[0].strip()).first()
    return item


@transaction.atomic
def tambah_tindakan_poli(visit, actor, *, kode, pelaksana, quantity=Decimal('1'), catatan=''):
    """Tambah satu tindakan poli jantung; idempoten per kode ICD-9.

    Mengembalikan ``TindakanAsesmen`` yang sudah tertaut ke ``BillingItem``.
    Kode yang tidak ada di salinan kelompok episode **tidak** ditagih: tarif
    belum ditetapkan, bukan Rp 0 (ADR-4/ADR-10).
    """
    from django.core.exceptions import PermissionDenied, ValidationError
    from klinis.models import MasterIcd9
    from klinis.services.tarif import resolve_detail
    from sdm.services.professional_care import require_scope
    from .services.poli_rbac import authorize_step

    require_scope(actor, visit)
    authorize_step(actor, visit, 9, 'fill')
    kode = (kode or '').strip()
    if not MasterIcd9.objects.filter(kode=kode).exists():
        raise ValidationError('Kode ICD-9-CM tidak ada di master.')
    detail = resolve_detail(visit, kode)
    if detail is None:
        raise ValidationError(
            'Tarif tindakan ini belum ditetapkan untuk kelompok layanan/penjamin episode.'
        )
    if pelaksana == 'NAKES_LAIN':
        raise ValidationError(
            'Pelaksana "Nakes Lain" belum punya nilai pada TindakanAsesmen.execution_team '
            '(hanya MEDIS/KEPERAWATAN); pilih Dokter atau Perawat.'
        )
    if pelaksana not in PELAKSANA_TEAM:
        raise ValidationError('Pelaksana tindakan tidak dikenal.')
    try:
        quantity = Decimal(str(quantity))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError('Kuantitas tindakan tidak valid.') from exc
    if quantity <= 0:
        raise ValidationError('Kuantitas tindakan harus lebih dari nol.')

    line = (
        TindakanAsesmen.objects.select_for_update()
        .filter(kunjungan=visit, jenis='ICD9', kode=kode)
        .first()
    )
    if line is not None and line.execution_status == 'PERFORMED':
        raise PermissionDenied('Tindakan sudah dilaksanakan; koreksi lewat jalur pembatalan beralasan.')
    if line is None:
        sequence = (visit.tindakan_asesmen.count() or 0) + 1
        line = TindakanAsesmen(kunjungan=visit, jenis='ICD9', kode=kode, urutan=sequence)

    line.nama = detail['icd9'].nama[:200]
    line.sumber_data = 'MASTER'
    line.tarif_acuan = detail['nominal']
    line.tarif = None
    line.tarif_penjamin = visit.penjamin
    line.quantity = quantity
    line.execution_status = 'PLANNED'
    line.execution_team = PELAKSANA_TEAM[pelaksana]
    line.diubah_oleh = actor
    if catatan:
        line.catatan_klinis = catatan[:2000]
    if not line.standard_item_id:
        rule = primary_for('ICD9', kode)
        if rule:
            line.standard_item = _ep_standard_item(rule.sub_standard)
    line.save()

    # Penulis billing memiliki seluruh baris ``sumber='TINDAKAN'``; karena itu
    # daftar yang disinkronkan adalah seluruh baris episode, bukan hanya baris
    # yang baru disentuh.
    lines = list(visit.tindakan_asesmen.order_by('pk'))
    sync_billing_tindakan(visit, lines, user=actor)
    for row in lines:
        row.save(update_fields=['billing_item'])
    line.refresh_from_db()
    return line
