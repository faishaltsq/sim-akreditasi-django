"""Level 2 transactional workflows (recruitment, PSV, privileging, orientation)."""
import logging
from string import Formatter

from django.contrib.auth import get_user_model

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from sdm.models import (
    ClinicalActionCode,
    KeputusanKredensial,
    Lamaran,
    Lowongan,
    Pegawai,
    MasterProfesiPegawai,
    DokumenPegawai,
    ProfilPribadiPegawai,
    UrutanNomorPegawai,
    VersiDokumen,
    PengajuanKredensial,
    PrivilegeSnapshot,
    PenugasanKlinis,
    PenugasanOrientasi,
    PenyelesaianOrientasi,
    PeristiwaSDM,
    ProgramOrientasi,
    RincianKewenangan,
    RiwayatSeleksi,
    VerifikasiSumber,
)
from sdm.storage import get_private_storage, _cleanup_uploaded_object


logger = logging.getLogger(__name__)


def move_application(application, *, target, actor, notes=''):
    """Transition one application, recording history; hiring is transactional."""
    require_hc_capability(
        actor, 'can_manage_hc_recruitment', unit=application.lowongan.unit_kerja_id
    )
    allowed = Lamaran.ALLOWED_TRANSITIONS.get(application.status, set())
    if target not in allowed:
        raise ValidationError({
            'status': f'Tahap {application.get_status_display()} tidak dapat langsung '
                      f'menjadi {dict(Lamaran.STATUS_CHOICES).get(target, target)}.'
        })

    with transaction.atomic():
        locked = Lamaran.objects.select_for_update().select_related(
            'lowongan__unit_kerja'
        ).get(pk=application.pk)
        if locked.status != application.status:
            raise ValidationError({'status': 'Lamaran berubah saat diproses.'})
        previous = locked.status
        locked.status = target
        locked.save(update_fields=['status', 'updated_at'])
        RiwayatSeleksi.objects.create(
            lamaran=locked,
            status_sebelum=previous,
            status_sesudah=target,
            catatan=notes,
            actor=actor,
        )
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='recruitment_stage_changed',
            target_tipe='application',
            target_id=str(locked.pk),
            status_sebelum=previous,
            status_sesudah=target,
            alasan='recruitment workflow transition',
        )
        if target == 'DITOLAK':
            _notify_penolakan(locked, notes)
    return locked


def _notify_penolakan(application, notes):
    """Email the candidate their application was not progressed.

    Only portal applicants carry an address; a directly recorded application
    is contacted by SDM through its own channel. A mail failure is swallowed
    because it must never undo a stage change already committed.
    """
    pelamar = getattr(application, 'pelamar', None)
    email = (getattr(pelamar, 'email', '') or '').strip()
    if not email:
        return
    subject = f'Lamaran Anda — {application.lowongan.judul}'
    message = (
        f'Yth. {application.nama_pelamar},\n\n'
        f'Terima kasih atas lamaran Anda untuk posisi '
        f'{application.lowongan.judul}.\n\n'
        'Setelah seleksi administrasi, kami belum dapat melanjutkan lamaran '
        'Anda pada tahap ini.\n\n'
    )
    if notes:
        message += f'Catatan tim: {notes}\n\n'
    message += (
        'Kami menghargai waktu dan minat Anda, dan mendorong Anda untuk '
        'mengikuti lowongan lain yang sesuai.\n\n'
        'Hormat kami,\nTim Rekrutmen'
    )
    try:
        send_mail(subject, message, None, [email], fail_silently=True)
    except Exception:
        logger.warning(
            'gagal mengirim email penolakan lamaran %s', application.pk,
            exc_info=True,
        )


def _next_hire_number():
    today = timezone.localdate()
    sequences = list(UrutanNomorPegawai.objects.select_for_update().filter(
        is_active=True, period_start__lte=today,
    ).filter(Q(period_end__isnull=True) | Q(period_end__gte=today))[:2])
    if len(sequences) != 1:
        raise ValidationError({'nomor_pegawai': 'Konfigurasi nomor pegawai aktif harus tepat satu.'})
    sequence = sequences[0]
    try:
        fields = list(Formatter().parse(sequence.format_pattern))
        if not any(name == 'counter' for _, name, _, _ in fields):
            raise ValueError
        if any(name is not None and (
            name not in {'year', 'month', 'counter'} or conversion or '{' in spec or '}' in spec
        ) for _, name, spec, conversion in fields):
            raise ValueError
        number = sequence.format_pattern.format(
            year=today.year, month=today.month, counter=sequence.next_counter,
        )
    except (ValueError, KeyError, IndexError, AttributeError):
        raise ValidationError({'nomor_pegawai': 'Pola nomor pegawai tidak valid.'}) from None
    if not number.strip() or len(number) > 50:
        raise ValidationError({'nomor_pegawai': 'Hasil pola nomor pegawai tidak valid.'})
    if Pegawai.objects.filter(nomor_pegawai=number).exists():
        raise ValidationError({'nomor_pegawai': 'Nomor pegawai sudah digunakan; periksa counter.'})
    sequence.next_counter += 1
    sequence.save(update_fields=['next_counter', 'updated_at'])
    return number


def hire_application(application, *, actor, idempotency_key):
    """Hire atomically; copied private objects are removed if the transaction fails."""
    require_hc_capability(
        actor, 'can_manage_hc_recruitment', unit=application.lowongan.unit_kerja_id
    )
    if not idempotency_key:
        raise ValidationError({'idempotency_key': 'Kunci idempotensi wajib diisi.'})

    uploaded = []
    storage = None
    try:
        # A surrounding transaction could roll back after private objects were
        # uploaded, with no rollback callback available to remove those copies.
        with transaction.atomic(durable=True):
            locked = Lamaran.objects.select_for_update().select_related(
                'lowongan__unit_kerja', 'pelamar'
            ).get(pk=application.pk)
            require_hc_capability(actor, 'can_manage_hc_recruitment', unit=locked.lowongan.unit_kerja_id)
            if locked.status != 'DITERIMA':
                raise ValidationError({'status': 'Hanya lamaran diterima yang dapat direkrut.'})
            if locked.employee_id:
                return locked.employee
            if Lamaran.objects.filter(idempotency_key=idempotency_key).exclude(pk=locked.pk).exists():
                raise ValidationError({'idempotency_key': 'Permintaan rekrutmen duplikat.'})

            number = _next_hire_number()
            candidate = locked.pelamar
            if candidate and len(candidate.telepon) > 30:
                raise ValidationError({'telepon': 'Nomor telepon terlalu panjang untuk profil pegawai.'})
            User = get_user_model()
            if User.objects.filter(username=number).exists():
                raise ValidationError({'nomor_pegawai': 'Nama akun untuk nomor pegawai sudah digunakan.'})
            account = User.objects.create_user(
                username=number, email=candidate.email if candidate else '', password=None,
            )
            professions = list(MasterProfesiPegawai.objects.filter(
                nama__iexact=locked.lowongan.profesi, is_active=True,
            )[:2]) if locked.lowongan.profesi else []
            employee = Pegawai.objects.create(
                akun=account, nomor_pegawai=number, nama_lengkap=locked.nama_pelamar,
                kategori='PPA' if locked.lowongan.profesi else 'NON_PPA',
                profesi=locked.lowongan.profesi,
                profesi_master=professions[0] if len(professions) == 1 else None,
                status='AKTIF',
            )
            if candidate:
                ProfilPribadiPegawai.objects.create(
                    employee=employee, tanggal_lahir=candidate.tanggal_lahir,
                    telepon=candidate.telepon,
                )

            kinds = {
                'KTP': 'IDENTITY', 'IJAZAH': 'EDUCATION', 'TRANSKRIP': 'EDUCATION',
                'STR': 'CREDENTIAL', 'SIP': 'CREDENTIAL', 'SERTIFIKAT': 'TRAINING',
                'CV': 'PROFESSIONAL', 'LAINNYA': 'OTHER',
            }
            mimes = {'pdf': 'application/pdf', 'png': 'image/png',
                     'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}
            for source in locked.berkas.all():
                if not source.berkas:
                    continue
                if not 0 < source.berkas.size <= 5 * 1024 * 1024:
                    raise ValidationError({'berkas': 'Ukuran berkas pelamar tidak valid.'})
                filename = source.berkas.name.replace('\\', '/').rsplit('/', 1)[-1]
                extension = filename.rsplit('.', 1)[-1].lower()
                if extension not in mimes or source.jenis not in kinds:
                    raise ValidationError({'berkas': 'Jenis berkas pelamar tidak didukung.'})
                if storage is None:
                    storage = get_private_storage()
                with source.berkas.open('rb') as file_obj:
                    stored = storage.upload(
                        file_obj, owner_id=str(employee.pk), sensitivity='personnel',
                        filename=filename, content_type=mimes[extension], max_bytes=5 * 1024 * 1024,
                    )
                uploaded.append(stored.storage_key)
                document = DokumenPegawai.objects.create(
                    employee=employee, document_type=kinds[source.jenis],
                    jenis_berkas='OTHER' if source.jenis == 'LAINNYA' else source.jenis,
                    title=source.get_jenis_display(), sensitivity='personnel', created_by=actor,
                )
                VersiDokumen.objects.create(
                    document=document, version_number=1, original_filename=filename[:255],
                    storage_key=stored.storage_key, sha256=stored.sha256,
                    size_bytes=stored.size_bytes, content_type=stored.content_type,
                    created_by=actor,
                )

            from sdm.models import PenempatanPegawai
            from sdm.services.orientasi import auto_assign_orientation
            from sdm.services.penempatan import save_assignment

            save_assignment(PenempatanPegawai(
                pegawai=employee, unit_kerja=locked.lowongan.unit_kerja,
                tanggal_mulai=timezone.localdate(), alokasi_fte='1.00',
            ))
            auto_assign_orientation(employee, actor=actor, unit_kerja=locked.lowongan.unit_kerja)
            if not employee.orientations.exists():
                raise ValidationError({'program': 'Program orientasi aktif belum dikonfigurasi.'})
            locked.employee = employee
            locked.idempotency_key = idempotency_key
            locked.save(update_fields=['employee', 'idempotency_key', 'updated_at'])
            PeristiwaSDM.objects.create(
                actor=actor, jenis_peristiwa='recruitment_hired',
                target_tipe='application', target_id=str(locked.pk),
                status_sesudah='DITERIMA', alasan=f'employee_created={employee.pk}',
            )
    except Exception:
        for key in uploaded:
            _cleanup_uploaded_object(storage, key)
        raise
    return employee


def record_psv(employee, version, *, actor, issuer, reference, method, outcome):
    """Record a manual primary-source verification against an exact version."""
    require_hc_capability(
        actor, 'can_review_hc_credentials', employee=employee
    )
    if outcome not in dict(VerifikasiSumber.OUTCOME_CHOICES):
        raise ValidationError({'outcome': 'Hasil verifikasi tidak valid.'})
    if version.document.employee_id != employee.pk:
        raise ValidationError({'version': 'Versi dokumen bukan milik pegawai ini.'})

    record = VerifikasiSumber(
        employee=employee,
        version=version,
        issuer=issuer,
        reference=reference,
        method=method,
        outcome=outcome,
        verifier=actor,
    )
    record.full_clean()
    record.save()
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='psv_recorded',
        target_tipe='document_version',
        target_id=str(version.pk),
        status_sesudah=outcome,
        alasan=f'manual primary-source verification; method={method[:40]}',
    )
    return record


def rekomendasikan_kredensial(application, *, actor, catatan=''):
    """Committee recommendation step before the final director decision."""
    require_hc_capability(
        actor, 'can_review_hc_credentials', unit=application.unit_kerja_id
    )
    if application.status not in {'DIAJUKAN', 'DITINJAU'}:
        raise ValidationError({
            'status': 'Pengajuan belum pada tahap rekomendasi komite.'
        })
    with transaction.atomic():
        locked = PengajuanKredensial.objects.select_for_update().get(pk=application.pk)
        if locked.decided_at is not None:
            raise ValidationError({'status': 'Keputusan sudah final.'})
        if locked.status not in {'DIAJUKAN', 'DITINJAU'}:
            raise ValidationError({'status': 'Pengajuan tidak dapat direkomendasikan.'})
        locked.status = 'DIREKOMENDASI'
        locked.committee_notes = catatan or locked.committee_notes
        locked.save(update_fields=['status', 'committee_notes', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='credential_recommended',
            target_tipe='credential_request',
            target_id=str(locked.pk),
            status_sesudah='DIREKOMENDASI',
            alasan=catatan[:200] if catatan else 'komite merekomendasikan pengajuan',
        )
    return locked


def decide_credential(application, *, actor, outcome, notes=''):
    """Committee decision; immutable, and never derived from document review alone."""
    require_hc_capability(
        actor, 'can_review_hc_credentials', unit=application.unit_kerja_id
    )
    if outcome not in dict(KeputusanKredensial.OUTCOME_CHOICES):
        raise ValidationError({'outcome': 'Keputusan tidak valid.'})
    if application.status not in {'DIAJUKAN', 'DITINJAU', 'DIREKOMENDASI'}:
        raise ValidationError({'status': 'Pengajuan tidak dalam tahap keputusan.'})

    with transaction.atomic():
        locked = PengajuanKredensial.objects.select_for_update().get(pk=application.pk)
        if locked.decided_at is not None:
            raise ValidationError({'status': 'Keputusan sudah final.'})
        KeputusanKredensial.objects.create(
            pengajuan=locked,
            outcome=outcome,
            decided_by=actor,
            notes=notes,
        )
        locked.status = outcome
        locked.decided_by = actor
        locked.decided_at = timezone.now()
        locked.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='credential_decided',
            target_tipe='credential_request',
            target_id=str(locked.pk),
            status_sesudah=outcome,
            alasan='committee decision recorded',
        )
    return locked


def issue_spk(application, *, actor, nomor_spk, berlaku_mulai, berlaku_sampai=None):
    """Issue a numbered SPK only after an approved committee decision."""
    require_hc_capability(
        actor, 'can_review_hc_credentials', unit=application.unit_kerja_id
    )
    with transaction.atomic():
        locked = PengajuanKredensial.objects.select_for_update().select_related(
            'employee'
        ).get(pk=application.pk)
        if locked.status != 'DISETUJUI':
            raise ValidationError({
                'status': 'SPK hanya dapat diterbitkan setelah keputusan komite disetujui.'
            })
        decision = getattr(locked, 'decision', None)
        if decision is None or decision.outcome != 'DISETUJUI':
            raise ValidationError({'decision': 'Keputusan komite tidak sah.'})

        expired = locked.employee.documents.filter(
            document_type='CREDENTIAL',
            versions__status='VERIFIED',
            versions__valid_until__lt=timezone.localdate(),
        ).exists()
        if expired:
            raise ValidationError({
                'employee': 'Terdapat dokumen kredensial kedaluwarsa; perbarui sebelum SPK.'
            })

        next_version = PenugasanKlinis.objects.filter(
            employee=locked.employee
        ).count() + 1
        assignment = PenugasanKlinis.objects.create(
            employee=locked.employee,
            unit_kerja=locked.unit_kerja,
            decision=decision,
            nomor_spk=nomor_spk,
            versi=next_version,
            berlaku_mulai=berlaku_mulai,
            berlaku_sampai=berlaku_sampai,
            issued_by=actor,
        )
        assignment.full_clean()
        assignment.save()
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='spk_issued',
            target_tipe='clinical_assignment',
            target_id=str(assignment.pk),
            status_sesudah='AKTIF',
            alasan=f'spk_number={nomor_spk}',
        )
    return assignment


def terbitkan_spk_lengkap(application, *, actor, nomor_spk, berlaku_mulai,
                         berlaku_sampai=None):
    """Issue an SPK and derive one PrivilegeSnapshot per approved privilege line.

    Wraps issue_spk (the single issuance path): committee-approved lines map to
    snapshots (MANDIRI/DISETUJUI_MANDIRI, SUPERVISI/DISETUJUI_SUPERVISI,
    MANDIRI_TERBATAS/DISETUJUI_MANDIRI_TERBATAS) with ClinicalActionCode synced
    from KatalogTindakan; TIDAK_DIBERIKAN lines get no snapshot, and a granted
    line without a catalog item is rejected rather than silently coded EXT-*.
    One atomic transaction for decision + snapshots.
    """
    require_hc_capability(
        actor, 'can_review_hc_credentials', unit=application.unit_kerja_id
    )
    with transaction.atomic():
        assignment = issue_spk(
            application, actor=actor, nomor_spk=nomor_spk,
            berlaku_mulai=berlaku_mulai, berlaku_sampai=berlaku_sampai,
        )
        granted_codes = []
        for rincian in application.privileges.select_related('catalog_item'):
            if not rincian.status_spk or rincian.status_spk == 'TIDAK_DIBERIKAN':
                continue
            if rincian.catalog_item_id is None:
                # A granted line must map back to the RKK catalog; EXT-* codes
                # would leave the audit trail unlinkable (KPS 8/10/12/14/16).
                raise ValidationError({
                    'privileges': (
                        f'Rincian "{rincian.kewenangan}" belum ditautkan ke katalog '
                        'RKK; lengkapi katalog sebelum menerbitkan SPK.'
                    )
                })
            kode = rincian.catalog_item.kode
            label = rincian.catalog_item.nama
            action, _ = ClinicalActionCode.objects.get_or_create(
                code=kode, defaults={'label': label[:100]},
            )
            PrivilegeSnapshot.objects.get_or_create(
                pegawai=application.employee,
                unit_kerja=application.unit_kerja,
                action_code=action,
                valid_from=berlaku_mulai,
                defaults={
                    'valid_until': berlaku_sampai,
                    'granted_by': actor,
                    'source_decision': assignment,
                },
            )
            granted_codes.append(kode)
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='spk_privileges_mapped',
            target_tipe='clinical_assignment',
            target_id=str(assignment.pk),
            status_sesudah='AKTIF',
            alasan=f'privilege_snapshots={len(granted_codes)}',
        )
    return assignment


def revoke_spk(assignment, *, actor, reason):
    require_hc_capability(
        actor, 'can_review_hc_credentials', unit=assignment.unit_kerja_id
    )
    with transaction.atomic():
        locked = PenugasanKlinis.objects.select_for_update().get(pk=assignment.pk)
        if not locked.is_active:
            raise ValidationError({'status': 'SPK sudah tidak aktif.'})
        locked.is_active = False
        locked.save(update_fields=['is_active'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='spk_revoked',
            target_tipe='clinical_assignment',
            target_id=str(locked.pk),
            status_sebelum='AKTIF',
            status_sesudah='DICABUT',
            alasan=reason[:200],
        )
    return locked


def start_orientation(employee, program, *, actor, unit_kerja=None):
    """Assign an orientation program; previous assignments stay in history."""
    require_hc_capability(
        actor, 'can_manage_hc_orientation', unit=unit_kerja or program.unit_kerja_id
    )
    if not program.activities.exists():
        raise ValidationError({'program': 'Program belum memiliki aktivitas.'})
    from datetime import timedelta

    tenggat = timezone.localdate() + timedelta(
        days=program.durasi_hari or program.berlaku_hari
    )
    assignment = PenugasanOrientasi.objects.create(
        employee=employee,
        program=program,
        unit_kerja=unit_kerja or program.unit_kerja,
        tenggat=tenggat,
    )
    for activity in program.activities.all():
        PenyelesaianOrientasi.objects.create(
            assignment=assignment, activity=activity, selesai=False
        )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='orientation_started',
        target_tipe='orientation_assignment',
        target_id=str(assignment.pk),
        status_sesudah='BERJALAN',
        alasan=f'program={program.pk}',
    )
    return assignment


def complete_activity(completion, *, actor, notes=''):
    require_hc_capability(
        actor, 'can_manage_hc_orientation', employee=completion.assignment.employee
    )
    with transaction.atomic():
        locked = PenyelesaianOrientasi.objects.select_for_update().get(pk=completion.pk)
        locked.selesai = True
        locked.selesai_at = timezone.now()
        locked.signer = actor
        locked.notes = notes
        locked.save(update_fields=['selesai', 'selesai_at', 'signer', 'notes'])
        assignment = locked.assignment
        required = assignment.program.activities.filter(wajib=True).count()
        done = assignment.completions.filter(
            selesai=True, activity__wajib=True
        ).count()
        if required and done >= required and assignment.status == 'BERJALAN':
            assignment.status = 'SELESAI'
            assignment.save(update_fields=['status'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='orientation_activity_completed',
            target_tipe='orientation_completion',
            target_id=str(locked.pk),
            status_sesudah='SELESAI',
            alasan='activity sign-off',
        )
    return locked
