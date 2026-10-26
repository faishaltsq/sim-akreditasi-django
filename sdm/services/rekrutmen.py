"""Level 2 transactional workflows (recruitment, PSV, privileging, orientation)."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from sdm.models import (
    ClinicalActionCode,
    KeputusanKredensial,
    Lamaran,
    Lowongan,
    Pegawai,
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
    return locked


def hire_application(application, *, actor, idempotency_key):
    """Create exactly one employee for an accepted application."""
    require_hc_capability(
        actor, 'can_manage_hc_recruitment', unit=application.lowongan.unit_kerja_id
    )
    if application.status != 'DITERIMA':
        raise ValidationError({'status': 'Hanya lamaran diterima yang dapat direkrut.'})
    if not idempotency_key:
        raise ValidationError({'idempotency_key': 'Kunci idempotensi wajib diisi.'})

    with transaction.atomic():
        locked = Lamaran.objects.select_for_update().select_related(
            'lowongan__unit_kerja'
        ).get(pk=application.pk)
        if locked.employee_id:
            return locked.employee
        if Lamaran.objects.filter(
            idempotency_key=idempotency_key
        ).exclude(pk=locked.pk).exists():
            raise ValidationError({'idempotency_key': 'Permintaan rekrutmen duplikat.'})

        employee = Pegawai.objects.create(
            nama_lengkap=locked.nama_pelamar,
            kategori='PPA' if locked.lowongan.profesi else 'NON_PPA',
            profesi=locked.lowongan.profesi,
            status='AKTIF',
        )
        from sdm.models import PenempatanPegawai
        from sdm.services.penempatan import save_assignment

        save_assignment(PenempatanPegawai(
            pegawai=employee,
            unit_kerja=locked.lowongan.unit_kerja,
            tanggal_mulai=timezone.localdate(),
            alokasi_fte='1.00',
        ))
        locked.employee = employee
        locked.idempotency_key = idempotency_key
        locked.save(update_fields=['employee', 'idempotency_key', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='recruitment_hired',
            target_tipe='application',
            target_id=str(locked.pk),
            status_sesudah='DITERIMA',
            alasan=f'employee_created={employee.pk}',
        )
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

    tenggat = timezone.localdate() + timedelta(days=program.berlaku_hari)
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
