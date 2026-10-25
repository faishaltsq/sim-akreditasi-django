"""Staff intake service contracts (Task B2)."""

import re
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone


NIK_RE = re.compile(r'^\d{16}$', re.ASCII)


def validate_personal_data(data: dict) -> dict:
    """Normalize and validate personal intake fields. Returns normalized values
    or raises ValidationError with field errors."""
    errors = {}
    cleaned = {}

    nik = (data.get('nik') or '').strip()
    if nik:
        if not NIK_RE.match(nik):
            errors['nik'] = 'NIK harus berupa 16 digit angka ASCII.'
        else:
            cleaned['nik'] = nik

    nama_depan = (data.get('nama_depan') or '').strip()
    nama_belakang = (data.get('nama_belakang') or '').strip()
    if not nama_depan and not nama_belakang:
        errors['nama_depan'] = 'Nama depan atau nama belakang wajib diisi.'
    cleaned['nama_depan'] = nama_depan
    cleaned['nama_belakang'] = nama_belakang

    gelar_depan = (data.get('gelar_depan') or '').strip()
    gelar_belakang = (data.get('gelar_belakang') or '').strip()
    cleaned['gelar_depan'] = gelar_depan
    cleaned['gelar_belakang'] = gelar_belakang

    tempat_lahir = (data.get('tempat_lahir') or '').strip()
    cleaned['tempat_lahir'] = tempat_lahir

    tanggal_lahir = data.get('tanggal_lahir')
    if tanggal_lahir:
        try:
            parsed = timezone.datetime.strptime(str(tanggal_lahir), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            errors['tanggal_lahir'] = 'Tanggal lahir harus dalam format YYYY-MM-DD.'
        else:
            today = timezone.localdate()
            if parsed > today:
                errors['tanggal_lahir'] = 'Tanggal lahir tidak boleh di masa depan.'
            cleaned['tanggal_lahir'] = parsed
    else:
        cleaned['tanggal_lahir'] = None

    gender = data.get('gender') or ''
    cleaned['gender'] = gender

    agama = data.get('agama') or ''
    cleaned['agama'] = agama

    status_pernikahan = data.get('status_pernikahan') or ''
    cleaned['status_pernikahan'] = status_pernikahan

    telepon = (data.get('telepon') or '').strip()
    cleaned['telepon'] = telepon

    email = (data.get('email_terverifikasi') or '').strip().lower()
    cleaned['email_terverifikasi'] = email

    alamat_ktp = (data.get('alamat_ktp') or '').strip()
    cleaned['alamat_ktp'] = alamat_ktp

    alamat_domisili = (data.get('alamat_domisili') or '').strip()
    cleaned['alamat_domisili'] = alamat_domisili

    alamat_sama = bool(data.get('alamat_sama_dengan_ktp', False))
    cleaned['alamat_sama_dengan_ktp'] = alamat_sama
    if alamat_sama and not alamat_domisili:
        cleaned['alamat_domisili'] = alamat_ktp

    if errors:
        raise ValidationError(errors)

    return cleaned

def _as_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return timezone.datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValidationError({'tanggal': 'Format tanggal harus YYYY-MM-DD.'}) from None


def _as_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise ValidationError({'angka': 'Nilai numerik tidak valid.'}) from None


def finalize_staff_intake(*, actor, draft_id, expected_version, idempotency_key):
    """Commit one canonical employee from a completed five-step draft.

    Idempotent per ``idempotency_key``: a replay returns the recorded employee.
    """
    from django.contrib.auth import get_user_model
    from django.db import transaction

    from akreditasi.models import UnitKerja
    from sdm.akses import require_hc_capability
    from sdm.models import (
        DrafInputPegawai,
        IzinProfesiPegawai,
        MasterProfesiPegawai,
        Pegawai,
        PenempatanPegawai,
        PeristiwaSDM,
        ProfilPribadiPegawai,
        RiwayatKepegawaian,
        RiwayatPendidikanPegawai,
    )
    from sdm.services.penempatan import save_assignment

    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees')

    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValidationError({'idempotency': 'Kunci finalisasi wajib diisi.'})
    if type(expected_version) is not int or expected_version < 1:
        raise ValidationError({'version': 'Versi draf tidak valid.'})

    draft = DrafInputPegawai.objects.filter(
        owner=actor, pk=draft_id
    ).select_related('finalized_employee').first()
    if draft is None:
        raise ValidationError({'draft': 'Draf tidak ditemukan.'})

    if draft.state == 'FINALIZED':
        if draft.finalization_key == idempotency_key and draft.finalized_employee_id:
            return draft.finalized_employee
        raise ValidationError({'draft': 'Draf ini sudah diselesaikan.'})

    if draft.state != 'DRAFT':
        raise ValidationError({'draft': 'Draf tidak dalam status yang dapat diselesaikan.'})
    if draft.version != expected_version:
        raise ValidationError({'version': 'Versi draf tidak sesuai. Muat ulang dan coba lagi.'})
    if draft.expires_at and draft.expires_at <= timezone.now():
        draft.state = 'EXPIRED'
        draft.save(update_fields=['state', 'updated_at'])
        raise ValidationError({'draft': 'Draf telah kadaluarsa.'})

    data = draft.draft_data or {}
    missing = [key for key in ('1', '2', '3', '4', '5') if key not in data]
    if missing:
        raise ValidationError(
            {'steps': f'Langkah belum diselesaikan: {", ".join(missing)}.'}
        )

    step1, step2 = data['1'], data['2']
    step3 = data.get('3') or {}

    personal = validate_personal_data(step1)

    unit_pk = step2.get('unit_kerja')
    if not unit_pk:
        raise ValidationError({'unit': 'Unit kerja wajib dipilih.'})
    unit = UnitKerja.objects.filter(pk=unit_pk, is_active=True).first()
    if unit is None:
        raise ValidationError({'unit': 'Unit kerja tidak valid atau tidak aktif.'})
    require_hc_capability(actor, 'can_manage_hc_employees', unit=unit)

    sub_unit_pk = step2.get('sub_unit')
    placement_unit = unit
    unit_induk = None
    if sub_unit_pk:
        placement_unit = UnitKerja.objects.filter(
            pk=sub_unit_pk, is_active=True
        ).first()
        if placement_unit is None:
            raise ValidationError({'sub_unit': 'Sub-unit tidak valid atau tidak aktif.'})
        if placement_unit.parent_id != unit.pk:
            raise ValidationError({
                'sub_unit': 'Sub-unit harus merupakan turunan langsung unit kerja terpilih.'
            })
        require_hc_capability(
            actor, 'can_manage_hc_employees', unit=placement_unit
        )
        unit_induk = unit

    nip = (step2.get('nomor_pegawai') or '').strip()
    if nip and Pegawai.objects.filter(nomor_pegawai=nip).exists():
        raise ValidationError({'nomor_pegawai': 'Nomor pegawai sudah terdaftar.'})
    nik = personal.get('nik', '')
    if nik and ProfilPribadiPegawai.objects.filter(nik=nik).exists():
        raise ValidationError({'nik': 'NIK sudah terdaftar pada pegawai lain.'})

    nama = ' '.join(
        part for part in (
            personal.get('gelar_depan', ''), personal.get('nama_depan', ''),
            personal.get('nama_belakang', ''), personal.get('gelar_belakang', ''),
        ) if part
    )
    if not nama:
        raise ValidationError({'nama': 'Nama pegawai wajib diisi.'})

    try:
        fte = Decimal(str(step2.get('alokasi_fte') or '1.00'))
    except (ArithmeticError, ValueError):
        raise ValidationError({'alokasi_fte': 'Alokasi FTE tidak valid.'}) from None

    with transaction.atomic():
        locked = DrafInputPegawai.objects.select_for_update().get(pk=draft.pk)
        if locked.state == 'FINALIZED':
            if locked.finalization_key == idempotency_key and locked.finalized_employee_id:
                return locked.finalized_employee
            raise ValidationError({'draft': 'Draf ini sudah diselesaikan.'})
        if locked.state != 'DRAFT':
            raise ValidationError({'draft': 'Status draf berubah selama finalisasi.'})
        if locked.version != expected_version:
            raise ValidationError({'version': 'Draf telah diperbarui di tab lain.'})

        employee = Pegawai(
            nama_lengkap=nama,
            nomor_pegawai=nip,
            kategori=step2.get('kategori') or 'NON_PPA',
            profesi=(step2.get('profesi') or '').strip(),
            jabatan=(step2.get('jabatan') or '').strip(),
            status=step2.get('status') or 'AKTIF',
            data_origin='MANUAL',
        )
        master_code = (step2.get('profesi_master') or '').strip()
        if master_code:
            employee.profesi_master = MasterProfesiPegawai.objects.filter(
                code=master_code, is_active=True
            ).first()
        employee.full_clean()
        employee.save()

        placement = PenempatanPegawai(
            pegawai=employee,
            unit_kerja=placement_unit,
            unit_induk=unit_induk,
            tanggal_mulai=_as_date(step2.get('tanggal_mulai')) or timezone.localdate(),
            tanggal_selesai=_as_date(step2.get('tanggal_selesai')),
            alokasi_fte=fte,
        )
        save_assignment(placement)

        employment_history = RiwayatKepegawaian(
            pegawai=employee,
            kategori_pegawai=step2.get('kategori_pegawai') or 'TETAP',
            tanggal_tmt=_as_date(step2.get('tanggal_tmt')),
            tanggal_akhir=_as_date(step2.get('tanggal_akhir')),
            nomor_kontrak=step2.get('nomor_kontrak') or '',
            tanggal_mulai_kontrak=_as_date(step2.get('tanggal_mulai_kontrak')),
            tanggal_selesai_kontrak=_as_date(step2.get('tanggal_selesai_kontrak')),
            jam_kontrak_per_minggu=_as_decimal(step2.get('jam_kontrak_per_minggu')),
            jam_fulltime_referensi=_as_decimal(
                step2.get('jam_fulltime_referensi')
            ) or Decimal('40.00'),
            jabatan_struktural=step2.get('jabatan') or '',
            review_status='UNREVIEWED',
            provenance='Draf intake lima langkah.',
        )
        employment_history.full_clean()
        employment_history.save()

        personal_profile = ProfilPribadiPegawai(
            employee=employee,
            nik=personal.get('nik', ''),
            nama_depan=personal.get('nama_depan', ''),
            nama_belakang=personal.get('nama_belakang', ''),
            gelar_depan=personal.get('gelar_depan', ''),
            gelar_belakang=personal.get('gelar_belakang', ''),
            tempat_lahir=personal.get('tempat_lahir', ''),
            tanggal_lahir=personal.get('tanggal_lahir'),
            gender=personal.get('gender', ''),
            agama=personal.get('agama', ''),
            status_pernikahan=personal.get('status_pernikahan', ''),
            telepon=personal.get('telepon', ''),
            email_terverifikasi=personal.get('email_terverifikasi', ''),
            alamat_ktp=personal.get('alamat_ktp', ''),
            alamat_domisili=personal.get('alamat_domisili', ''),
            alamat_sama_dengan_ktp=personal.get('alamat_sama_dengan_ktp', True),
        )
        personal_profile.full_clean()
        personal_profile.save()

        if step3.get('pendidikan_tingkat'):
            education = RiwayatPendidikanPegawai(
                pegawai=employee,
                tingkat=step3['pendidikan_tingkat'],
                institusi=step3.get('pendidikan_institusi') or '',
                program_studi=step3.get('pendidikan_program') or '',
                tanggal_lulus=_as_date(step3.get('tanggal_lulus')),
            )
            education.full_clean()
            education.save()

        permit_rows = []
        default_profesi = (step3.get('izin_profesi') or '').strip()
        default_pemberi = (step3.get('pemberi_izin') or '').strip()
        if step3.get('izin_subtype'):
            permit_rows.append({
                'subtype': step3['izin_subtype'],
                'nomor_izin': (step3.get('nomor_izin') or '').strip(),
                'pemberi_izin': default_pemberi or 'Belum dicatat',
                'profesi': default_profesi or 'Belum dicatat',
                'validity_mode': step3.get('validity_mode') or 'DATED',
                'tanggal_terbit': _as_date(step3.get('tanggal_terbit')),
                'tanggal_berakhir': _as_date(step3.get('tanggal_berakhir')),
                'organisasi_praktik': step3.get('organisasi_praktik') or '',
                'lokasi_praktik': step3.get('lokasi_praktik') or '',
                'is_local_rs': bool(step3.get('is_local_rs')),
            })
        for index in range(6):
            prefix = f'sip-{index}-'
            if prefix + 'nomor_izin' not in step3:
                continue
            nomor = (step3.get(prefix + 'nomor_izin') or '').strip()
            if not nomor:
                continue
            permit_rows.append({
                'subtype': 'SIP',
                'nomor_izin': nomor,
                'pemberi_izin': default_pemberi or 'Belum dicatat',
                'profesi': default_profesi or 'Belum dicatat',
                'validity_mode': 'DATED',
                'tanggal_terbit': _as_date(step3.get(prefix + 'tanggal_terbit')),
                'tanggal_berakhir': _as_date(
                    step3.get(prefix + 'tanggal_berakhir')
                ),
                'organisasi_praktik': '',
                'lokasi_praktik': step3.get(prefix + 'lokasi_praktik') or '',
                'is_local_rs': bool(step3.get(prefix + 'is_local_rs')),
            })
        for row in permit_rows:
            permit = IzinProfesiPegawai(pegawai=employee, **row)
            permit.full_clean()
            permit.save()

        bind_intake_attachments(
            draft=locked, employee=employee, actor=actor
        )

        locked.state = 'FINALIZED'
        locked.finalized_employee = employee
        locked.finalization_key = idempotency_key
        locked.version = locked.version + 1
        locked.save(update_fields=[
            'state', 'finalized_employee', 'finalization_key', 'version', 'updated_at',
        ])

        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='employee_created',
            target_tipe='employee',
            target_id=str(employee.pk),
            status_sesudah=employee.status,
            alasan='Dibuat melalui wizard input lima langkah.',
        )

    return employee

INTAKE_ARTIFACT_EXTENSIONS = {
    'FOTO_PROFIL': ('jpg', 'jpeg'),
    'KTP': ('pdf', 'jpg', 'jpeg'),
    'IJAZAH': ('pdf', 'jpg', 'jpeg'),
    'TRANSKRIP': ('pdf', 'jpg', 'jpeg'),
    'STR': ('pdf', 'jpg', 'jpeg'),
    'SIP': ('pdf', 'jpg', 'jpeg'),
    'SIPA': ('pdf', 'jpg', 'jpeg'),
    'KONTRAK': ('pdf', 'jpg', 'jpeg'),
    'SK_PENGANGKATAN': ('pdf', 'jpg', 'jpeg'),
    'SPK_RKK': ('pdf', 'jpg', 'jpeg'),
    'URAIAN_TUGAS': ('pdf', 'jpg', 'jpeg'),
    'SERTIFIKAT': ('pdf', 'jpg', 'jpeg'),
    'OTHER': ('pdf', 'jpg', 'jpeg'),
}
PHOTO_MAX_DIMENSION = 512
PHOTO_MIN_DIMENSION = 200
PHOTO_SOURCE_MAX_BYTES = 12_000_000
PHOTO_SOURCE_MAX_PIXELS = 20_000_000


def normalize_profile_photo(file_obj):
    """Return a bounded, EXIF-corrected JPEG for avatar use."""
    from io import BytesIO

    from PIL import Image, ImageOps, UnidentifiedImageError

    raw = file_obj.read(PHOTO_SOURCE_MAX_BYTES + 1)
    if not isinstance(raw, bytes) or not raw or len(raw) > PHOTO_SOURCE_MAX_BYTES:
        raise ValidationError({'foto': 'Berkas foto tidak valid atau terlalu besar.'})
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.width * source.height > PHOTO_SOURCE_MAX_PIXELS:
                raise ValidationError({'foto': 'Resolusi foto terlalu besar.'})
            source.verify()
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError({'foto': 'Berkas bukan gambar yang dapat dibaca.'}) from None
    if min(image.size) < PHOTO_MIN_DIMENSION:
        raise ValidationError({
            'foto': f'Ukuran foto minimal {PHOTO_MIN_DIMENSION}×{PHOTO_MIN_DIMENSION} piksel.'
        })
    image.thumbnail((PHOTO_MAX_DIMENSION, PHOTO_MAX_DIMENSION), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=85, optimize=True)
    return buffer.getvalue(), 'image/jpeg'


@transaction.atomic
def stage_intake_attachment(*, actor, draft_id, expected_version, file_obj, artifact_kind):
    """Upload one draft attachment into private storage; create no canonical rows."""
    from io import BytesIO

    from akreditasi.models import UnitKerja
    from django.db import IntegrityError
    from sdm.akses import require_hc_capability
    from sdm.models import DrafInputPegawai, LampiranDrafPegawai
    from sdm.storage import get_private_storage
    from sdm.storage_backend import PrivateStorageError


    if artifact_kind not in INTAKE_ARTIFACT_EXTENSIONS:
        raise ValidationError({'jenis': 'Jenis berkas tidak dikenali.'})
    if type(expected_version) is not int:
        raise ValidationError({'version': 'Versi draf tidak valid.'})

    draft = (
        DrafInputPegawai.objects.select_for_update()
        .filter(owner=actor, pk=draft_id)
        .first()
    )
    if draft is None:
        raise ValidationError({'draft': 'Draf tidak ditemukan.'})
    target_unit = UnitKerja.objects.filter(
        pk=((draft.draft_data or {}).get('2') or {}).get('unit_kerja')
    ).first()
    if target_unit is None:
        raise ValidationError({'draft': 'Unit kerja draf tidak valid.'})
    require_hc_capability(actor, 'can_view_hc', unit=target_unit)
    require_hc_capability(actor, 'can_manage_hc_employees', unit=target_unit)
    require_hc_capability(actor, 'can_manage_hc_documents', unit=target_unit)
    if draft.state != 'DRAFT':
        raise ValidationError({'draft': 'Draf tidak dapat menerima berkas.'})
    if draft.version != expected_version:
        raise ValidationError({'version': 'Draf telah diperbarui di tab lain.'})
    if draft.expires_at and draft.expires_at <= timezone.now():
        raise ValidationError({'draft': 'Draf telah kadaluarsa.'})
    if (
        artifact_kind in ('FOTO_PROFIL', 'KTP')
        and draft.attachments.filter(
            artifact_kind=artifact_kind, state='STAGED'
        ).exists()
    ):
        raise ValidationError({
            'berkas': 'Lampiran jenis ini sudah ada. Hapus lampiran lama sebelum mengganti.'
        })

    raw_name = getattr(file_obj, 'name', '')
    extension = raw_name.rsplit('.', 1)[-1].lower() if '.' in raw_name else ''
    if extension not in INTAKE_ARTIFACT_EXTENSIONS[artifact_kind]:
        allowed = ', '.join(INTAKE_ARTIFACT_EXTENSIONS[artifact_kind])
        raise ValidationError({'berkas': f'Format berkas harus salah satu dari: {allowed}.'})

    if artifact_kind == 'FOTO_PROFIL':
        data, content_type = normalize_profile_photo(file_obj)
    else:
        data = file_obj.read(5_242_881)
        if not isinstance(data, bytes) or len(data) > 5_242_880:
            raise ValidationError({'berkas': 'Maksimal 5 MiB per berkas.'})
        if extension == 'pdf':
            if not data.startswith(b'%PDF-'):
                raise ValidationError({'berkas': 'Berkas PDF tidak valid.'})
            content_type = 'application/pdf'
        else:
            if not data.startswith(b'\xff\xd8\xff'):
                raise ValidationError({'berkas': 'Berkas JPEG tidak valid.'})
            content_type = 'image/jpeg'

    # The private object is owned by the draft, not by an employee that does not
    # exist yet, so the storage scope uses a stable per-draft pseudo-owner.
    storage = get_private_storage()
    stored = storage.upload(
        BytesIO(data),
        owner_id=str(draft.pk),
        sensitivity='personnel',
        filename=f'{uuid.uuid4().hex}.{"jpg" if content_type == "image/jpeg" else "pdf"}',
        content_type=content_type,
        max_bytes=6_000_000,
    )

    try:
        return LampiranDrafPegawai.objects.create(
            draft=draft,
            artifact_kind=artifact_kind,
            storage_key=stored.storage_key,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            content_type=stored.content_type,
            original_filename=raw_name[:255] or 'berkas',
        )
    except Exception as exc:
        try:
            storage.delete(stored.storage_key)
        except PrivateStorageError:
            pass
        if isinstance(exc, IntegrityError) and artifact_kind in ('FOTO_PROFIL', 'KTP'):
            raise ValidationError({
                'berkas': 'Lampiran jenis ini sudah ada. Hapus lampiran lama sebelum mengganti.'
            }) from None
        raise


@transaction.atomic
def remove_intake_attachment(*, actor, attachment_id, expected_version):
    """Delete a staged object and its row; refuse once bound."""
    from akreditasi.models import UnitKerja
    from sdm.akses import require_hc_capability
    from sdm.models import DrafInputPegawai, LampiranDrafPegawai
    from sdm.storage import get_private_storage
    from sdm.storage_backend import PrivateStorageError

    # Use the same lock order as finalization: draft first, attachment second.
    draft = (
        DrafInputPegawai.objects.select_for_update()
        .filter(owner=actor, attachments__pk=attachment_id)
        .first()
    )
    if draft is None:
        raise ValidationError({'lampiran': 'Lampiran tidak ditemukan.'})
    target_unit = UnitKerja.objects.filter(
        pk=((draft.draft_data or {}).get('2') or {}).get('unit_kerja')
    ).first()
    if target_unit is None:
        raise ValidationError({'draft': 'Unit kerja draf tidak valid.'})
    require_hc_capability(actor, 'can_view_hc', unit=target_unit)
    require_hc_capability(actor, 'can_manage_hc_employees', unit=target_unit)
    require_hc_capability(actor, 'can_manage_hc_documents', unit=target_unit)
    attachment = (
        LampiranDrafPegawai.objects.select_for_update()
        .filter(pk=attachment_id, draft=draft)
        .first()
    )
    if attachment is None:
        raise ValidationError({'lampiran': 'Lampiran tidak ditemukan.'})
    if attachment.state != 'STAGED':
        raise ValidationError({'lampiran': 'Lampiran sudah terhubung ke dokumen.'})
    if draft.version != expected_version:
        raise ValidationError({'version': 'Draf telah diperbarui di tab lain.'})

    try:
        get_private_storage().delete(attachment.storage_key)
    except PrivateStorageError:
        # Keep the row STAGED so cleanup can be retried; deleting metadata here
        # would create an untraceable private-storage orphan.
        raise ValidationError({
            'lampiran': 'Berkas belum dapat dihapus dari penyimpanan. Coba lagi.'
        }) from None
    attachment.state = 'DELETED'
    attachment.save(update_fields=['state'])
    return draft.pk


INTAKE_DOCUMENT_META = {
    'FOTO_PROFIL': ('IDENTITY', 'FOTO', 'Pas Foto Resmi'),
    'KTP': ('IDENTITY', 'KTP', 'KTP'),
    'IJAZAH': ('EDUCATION', 'IJAZAH', 'Ijazah'),
    'TRANSKRIP': ('EDUCATION', 'TRANSKRIP', 'Transkrip Nilai'),
    'STR': ('CREDENTIAL', 'STR', 'STR'),
    'SIP': ('CREDENTIAL', 'SIP', 'SIP'),
    'SIPA': ('CREDENTIAL', 'SIPA', 'SIPA'),
    'KONTRAK': ('CONTRACT', 'KONTRAK', 'Kontrak Kerja'),
    'SK_PENGANGKATAN': ('CONTRACT', 'SK_PENGANGKATAN', 'SK Pengangkatan'),
    'SPK_RKK': ('CREDENTIAL', 'SPK_RKK', 'SPK RKK'),
    'URAIAN_TUGAS': ('OTHER', 'URAIAN_TUGAS', 'Uraian Tugas'),
    'SERTIFIKAT': ('TRAINING', 'SERTIFIKAT', 'Sertifikat'),
    'OTHER': ('OTHER', 'OTHER', 'Dokumen Pendukung'),
}


def bind_intake_attachments(*, draft, employee, actor):
    """Bind all staged objects inside the caller's finalization transaction."""
    from sdm.models import DokumenPegawai, PeristiwaSDM, VersiDokumen

    versions = []
    attachments = draft.attachments.select_for_update().filter(state='STAGED')
    step5 = (draft.draft_data or {}).get('5') or {}
    for attachment in attachments:
        document_type, kind, default_title = INTAKE_DOCUMENT_META[attachment.artifact_kind]
        title = default_title
        if attachment.artifact_kind not in ('FOTO_PROFIL', 'KTP'):
            title = (step5.get('dokumen_judul') or '').strip() or default_title
        document = DokumenPegawai(
            employee=employee,
            document_type=document_type,
            jenis_berkas=kind,
            title=title,
            sensitivity='personnel',
            created_by=actor,
        )
        document.full_clean()
        document.save()
        version = VersiDokumen(
            document=document,
            version_number=1,
            original_filename=attachment.original_filename,
            storage_key=attachment.storage_key,
            sha256=attachment.sha256,
            size_bytes=attachment.size_bytes,
            content_type=attachment.content_type,
            status='PENDING',
            created_by=actor,
        )
        version.full_clean()
        version.save()
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='private_document_uploaded',
            target_tipe='document_version',
            target_id=str(version.pk),
            status_sesudah='PENDING',
            alasan='sensitivity=personnel; source=intake',
        )
        attachment.state = 'BOUND'
        attachment.bound_version = version
        attachment.save(update_fields=['state', 'bound_version'])
        if attachment.artifact_kind == 'FOTO_PROFIL':
            profile = employee.profil_pribadi
            profile.foto_profil_versi = version
            profile.save(update_fields=['foto_profil_versi', 'updated_at'])
        versions.append(version)
    return versions

def build_staff_profile(employee, *, viewer):
    """Assemble the Digital Staff Profile with field-level permissions."""
    from django.core.exceptions import PermissionDenied

    from sdm.akses import require_hc_capability
    from sdm.services.kepatuhan import documents_for_employee

    can_view_personal = employee.akun_id == viewer.pk
    if not can_view_personal:
        try:
            require_hc_capability(
                viewer, 'can_manage_hc_employees', employee=employee
            )
            can_view_personal = True
        except PermissionDenied:
            can_view_personal = False

    personal_record = getattr(employee, 'profil_pribadi', None)
    # Never pass the restricted model instance to a template that may render it
    # for a view-only sibling. The presence flag supports an honest empty state.
    personal = personal_record if can_view_personal else None
    employment = employee.riwayat_kepegawaian.order_by('-tanggal_tmt', '-pk').first()
    education = list(
        employee.riwayat_pendidikan.select_related(
            'ijazah_versi', 'transkrip_versi'
        ).order_by('-tanggal_lulus', '-pk')
    )
    permits = list(
        employee.izin_profesi.order_by('subtype', 'nomor_izin')
    )

    nik = getattr(personal_record, 'nik', '') or ''
    masked_nik = 'Tersembunyi'
    if nik and can_view_personal:
        masked_nik = nik

    tenure_days = None
    tmt = getattr(employment, 'tanggal_tmt', None)
    if tmt:
        tenure_days = (timezone.localdate() - tmt).days

    invitation = employee.invitations.order_by('-created_at').first()

    return {
        'personal': personal,
        'employment': employment,
        'education': education,
        'permits': permits,
        'documents': documents_for_employee(employee).prefetch_related('versions'),
        'invitation': invitation if can_view_personal else None,
        'can_view_personal': can_view_personal,
        'has_personal_record': personal_record is not None,
        'masked_nik': masked_nik,
        'tenure_days': tenure_days,
    }
