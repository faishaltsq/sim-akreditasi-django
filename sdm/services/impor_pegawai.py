"""Excel staff import service (Task B5)."""

import hashlib
import io
import json
import zipfile
from decimal import Decimal

import openpyxl
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from akreditasi.models import UnitKerja
from sdm.models import (
    BatchImporPegawai,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    RiwayatKepegawaian,
)
from sdm.services.penempatan import save_assignment

TEMPLATE_VERSION = '1'
MAX_ROWS = 2000
MAX_WORKBOOK_BYTES = 5_242_880  # 5 MiB
MAX_ZIP_UNCOMPRESSED = 50_000_000  # 50 MiB


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def preview_staff_import(*, actor, workbook, idempotency_key):
    """Parse/validate workbook into an immutable preview. Creates no canonical rows."""
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees')

    raw = workbook.read(MAX_WORKBOOK_BYTES + 1)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_WORKBOOK_BYTES:
        raise ValidationError({
            'file': f'Berkas melebihi batas {MAX_WORKBOOK_BYTES} byte.'
        })
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            expanded = sum(item.file_size for item in archive.infolist())
            if expanded > MAX_ZIP_UNCOMPRESSED:
                raise ValidationError({
                    'file': 'Ukuran hasil ekstraksi workbook melebihi batas.'
                })
    except zipfile.BadZipFile:
        raise ValidationError({'file': 'Berkas XLSX tidak valid.'}) from None

    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    except Exception as exc:
        raise ValidationError({'file': f'Gagal membaca berkas Excel: {exc}'})

    if 'Staf' not in wb.sheetnames:
        raise ValidationError({'file': "Lembar kerja 'Staf' tidak ditemukan."})

    sheet = wb['Staf']
    header = [str(c.value).strip() if c.value is not None else '' for c in next(sheet.iter_rows(min_row=1, max_row=1))]
    required = [
        'nomor_pegawai', 'nama_lengkap', 'kategori', 'profesi', 'jabatan', 'status',
        'kategori_pegawai', 'unit_code', 'tanggal_mulai', 'alokasi_fte',
    ]
    missing = [f for f in required if f not in header]
    if missing:
        raise ValidationError({'file': f'Kolom wajib hilang: {", ".join(missing)}'})

    idx = {name: i for i, name in enumerate(header)}
    units = {
        u.code: u
        for u in visible_units(actor, capability='can_manage_hc_employees')
    }

    errors = []
    rows = []
    row_count = 0
    seen_nips = set()

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if all(v is None for v in row):
            continue
        row_count += 1
        if row_count > MAX_ROWS:
            raise ValidationError({'file': f'Maksimum {MAX_ROWS} baris staf per berkas.'})

        def cell(name):
            return row[idx[name]]

        nip = str(cell('nomor_pegawai') or '').strip()
        nama = str(cell('nama_lengkap') or '').strip()
        kategori = str(cell('kategori') or '').strip()
        unit_code = str(cell('unit_code') or '').strip()
        tanggal_mulai = cell('tanggal_mulai')
        alokasi_fte = cell('alokasi_fte')

        row_errors = []
        if not nip:
            row_errors.append('Nomor pegawai kosong')
        elif nip in seen_nips:
            row_errors.append('Nomor pegawai duplikat dalam berkas')
        else:
            seen_nips.add(nip)

        if not nama:
            row_errors.append('Nama lengkap kosong')
        if kategori not in dict(Pegawai.KATEGORI_CHOICES):
            row_errors.append(f'Kategori tidak valid: {kategori}')
        if unit_code not in units:
            row_errors.append(f'Unit tidak diketahui: {unit_code}')

        try:
            tgl = timezone.datetime.strptime(str(tanggal_mulai), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            row_errors.append('Tanggal mulai harus berformat YYYY-MM-DD')
            tgl = None

        try:
            fte = Decimal(str(alokasi_fte))
            if not (Decimal('0.01') <= fte <= Decimal('1.00')):
                row_errors.append('Alokasi FTE harus 0.01–1.00')
        except (ArithmeticError, ValueError):
            row_errors.append('Alokasi FTE tidak valid')
            fte = None

        # Existing conflict check
        if nip and Pegawai.objects.filter(nomor_pegawai=nip).exists():
            row_errors.append('Nomor pegawai sudah terdaftar')

        rows.append({
            'nomor_pegawai': nip,
            'nama_lengkap': nama,
            'kategori': kategori,
            'profesi': str(cell('profesi') or '').strip(),
            'jabatan': str(cell('jabatan') or '').strip(),
            'status': str(cell('status') or 'AKTIF').strip(),
            'kategori_pegawai': str(cell('kategori_pegawai') or 'TETAP').strip(),
            'unit_code': unit_code,
            'unit_pk': str(units[unit_code].pk) if unit_code in units else '',
            'tanggal_mulai': tgl.isoformat() if tgl else '',
            'tanggal_selesai': str(cell('tanggal_selesai') or '').strip(),
            'alokasi_fte': str(fte) if fte is not None else '',
            'errors': row_errors,
            'action': 'BLOCKED' if row_errors else 'CREATE',
        })
        if row_errors:
            errors.extend([f'Baris {row_count + 1}: {e}' for e in row_errors])

    file_hash = _sha256_bytes(raw)
    preview_hash = _sha256_bytes(
        json.dumps({'rows': rows, 'template_version': TEMPLATE_VERSION}).encode()
    )
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValidationError({'batch': 'Kunci idempotensi wajib diisi.'})
    if len(idempotency_key) > 100:
        raise ValidationError({'batch': 'Kunci idempotensi terlalu panjang.'})

    defaults = {
        'uploader': actor,
        'template_version': TEMPLATE_VERSION,
        'file_hash': file_hash,
        'preview_hash': preview_hash,
        'state': 'PREVIEWED' if not errors else 'BLOCKED',
        'row_create': sum(1 for r in rows if r['action'] == 'CREATE'),
        'row_blocked': sum(1 for r in rows if r['action'] == 'BLOCKED'),
        'decisions': rows,
    }
    batch, created = BatchImporPegawai.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults=defaults,
    )
    if not created:
        if batch.uploader_id == actor.pk and batch.file_hash == file_hash:
            return batch
        raise ValidationError({
            'batch': 'Permintaan pratinjau tidak dapat digunakan.'
        })
    return batch


def apply_staff_import(*, actor, batch_id, preview_hash):
    """Apply only approved error-free CREATE rows; revalidate hash/scope.

    Idempotent: applying an already-applied batch with the same preview hash
    returns the recorded batch without re-creating rows.
    """
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees')

    batch = BatchImporPegawai.objects.filter(
        pk=batch_id, uploader=actor
    ).first()
    if batch is None:
        raise ValidationError({'batch': 'Batch impor tidak ditemukan.'})

    with transaction.atomic():
        batch = BatchImporPegawai.objects.select_for_update().get(
            pk=batch_id, uploader=actor
        )
        if batch.preview_hash != preview_hash:
            raise ValidationError({
                'batch': 'Hash pratinjau tidak sesuai; pratinjau telah berubah.'
            })
        if batch.state == 'APPLIED':
            return batch
        if batch.state != 'PREVIEWED':
            raise ValidationError({
                'batch': 'Batch tidak dalam status yang dapat diimpor.'
            })

        created = updated = blocked = 0
        for decision in batch.decisions or []:
            if decision.get('action') != 'CREATE' or decision.get('errors'):
                blocked += 1
                continue
            nip = decision['nomor_pegawai']
            unit = UnitKerja.objects.get(pk=decision['unit_pk'])
            require_hc_capability(actor, 'can_manage_hc_employees', unit=unit)

            try:
                fte = Decimal(str(decision['alokasi_fte'] or '1.00'))
            except (ArithmeticError, ValueError):
                raise ValidationError({
                    'alokasi_fte': f'Baris {nip}: alokasi FTE tidak valid.'
                }) from None

            employee = Pegawai(
                nomor_pegawai=nip,
                nama_lengkap=decision['nama_lengkap'],
                kategori=decision['kategori'],
                profesi=decision['profesi'],
                jabatan=decision['jabatan'],
                status=decision['status'],
                data_origin='VERIFIED_IMPORT',
            )
            employee.full_clean()
            employee.save()
            save_assignment(PenempatanPegawai(
                pegawai=employee,
                unit_kerja=unit,
                tanggal_mulai=decision['tanggal_mulai'] or timezone.localdate(),
                tanggal_selesai=decision['tanggal_selesai'] or None,
                alokasi_fte=fte,
            ))
            employment_history = RiwayatKepegawaian(
                pegawai=employee,
                kategori_pegawai=decision['kategori_pegawai'],
                tanggal_tmt=decision['tanggal_mulai'] or timezone.localdate(),
                tanggal_akhir=decision['tanggal_selesai'] or None,
                jabatan_struktural=decision['jabatan'],
                review_status='UNREVIEWED',
                provenance='Impor Excel terverifikasi.',
            )
            employment_history.full_clean()
            employment_history.save()
            PeristiwaSDM.objects.create(
                actor=actor,
                jenis_peristiwa='employee_created',
                target_tipe='employee',
                target_id=str(employee.pk),
                status_sesudah=decision['status'],
                alasan='Dibuat melalui impor Excel.',
            )
            created += 1

        batch.state = 'APPLIED'
        batch.row_create = created
        batch.row_update = updated
        batch.row_blocked = blocked
        batch.save(update_fields=[
            'state', 'row_create', 'row_update', 'row_blocked', 'updated_at'
        ])

    return batch
