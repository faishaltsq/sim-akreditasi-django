"""Excel staff import service (Task B5)."""

import hashlib
import io
import json

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
)

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

    raw = workbook.read()
    if len(raw) > MAX_WORKBOOK_BYTES:
        raise ValidationError({'file': f'Berkas melebihi batas {MAX_WORKBOOK_BYTES} byte.'})

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
    units = {u.code: u for u in UnitKerja.objects.all()}

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
            fte = float(alokasi_fte)
            if not (0.01 <= fte <= 1.00):
                row_errors.append('Alokasi FTE harus 0.01–1.00')
        except (TypeError, ValueError):
            row_errors.append('Alokasi FTE tidak valid')

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
            'alokasi_fte': str(fte) if 'fte' in locals() else '',
            'errors': row_errors,
            'action': 'BLOCKED' if row_errors else 'CREATE',
        })
        if row_errors:
            errors.extend([f'Baris {row_count + 1}: {e}' for e in row_errors])

    file_hash = _sha256_bytes(raw)
    preview_hash = _sha256_bytes(
        json.dumps({'rows': rows, 'template_version': TEMPLATE_VERSION}).encode()
    )
    batch = BatchImporPegawai.objects.create(
        uploader=actor,
        template_version=TEMPLATE_VERSION,
        file_hash=file_hash,
        idempotency_key=idempotency_key,
        preview_hash=preview_hash,
        state='PREVIEWED' if not errors else 'BLOCKED',
        row_create=sum(1 for r in rows if r['action'] == 'CREATE'),
        row_blocked=sum(1 for r in rows if r['action'] == 'BLOCKED'),
        decisions=rows,
    )
    return batch


def apply_staff_import(*, actor, batch_id, preview_hash):
    """Apply only approved error-free CREATE rows; revalidate hash/scope.

    Idempotent: applying an already-applied batch with the same preview hash
    returns the recorded batch without re-creating rows.
    """
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees')

    try:
        batch = BatchImporPegawai.objects.get(pk=batch_id)
    except BatchImporPegawai.DoesNotExist:
        raise ValidationError({'batch': 'Batch impor tidak ditemukan.'})

    if batch.preview_hash != preview_hash:
        raise ValidationError({'batch': 'Hash pratinjau tidak sesuai; pratinjau telah berubah.'})

    # Already applied: return recorded result (idempotent repeat apply).
    if batch.state == 'APPLIED':
        return batch

    if batch.state != 'PREVIEWED':
        raise ValidationError({'batch': 'Batch tidak dalam status yang dapat diimpor.'})

    with transaction.atomic():
        batch.refresh_from_db()
        if batch.state == 'APPLIED':
            return batch
        if batch.preview_hash != preview_hash:
            raise ValidationError({'batch': 'Hash pratinjau tidak sesuai; pratinjau telah berubah.'})

        created = updated = blocked = 0
        for decision in batch.decisions or []:
            if decision.get('action') != 'CREATE' or decision.get('errors'):
                blocked += 1
                continue
            nip = decision['nomor_pegawai']
            unit = UnitKerja.objects.get(pk=decision['unit_pk'])
            require_hc_capability(actor, 'can_manage_hc_employees', unit=unit)

            try:
                fte = float(decision['alokasi_fte'])
            except (TypeError, ValueError):
                fte = 1.00

            Pegawai.objects.create(
                nomor_pegawai=nip,
                nama_lengkap=decision['nama_lengkap'],
                kategori=decision['kategori'],
                profesi=decision['profesi'],
                jabatan=decision['jabatan'],
                status=decision['status'],
                data_origin='VERIFIED_IMPORT',
            )
            employee = Pegawai.objects.get(nomor_pegawai=nip)
            PenempatanPegawai.objects.create(
                pegawai=employee,
                unit_kerja=unit,
                tanggal_mulai=decision['tanggal_mulai'] or timezone.localdate(),
                tanggal_selesai=decision['tanggal_selesai'] or None,
                alokasi_fte=fte,
            )
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
