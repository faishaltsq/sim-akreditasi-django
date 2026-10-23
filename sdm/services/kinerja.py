"""Level 3 workflows: appraisals, training needs, and learning management."""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability
from sdm.models import (
    ButirPenilaian,
    EvaluasiDiklat,
    KehadiranDiklat,
    KebutuhanPelatihan,
    PenilaianKinerja,
    PeristiwaSDM,
    PesertaDiklat,
    SertifikatDiklat,
    SumberKebutuhanPelatihan,
)

TNA_RULE_VERSION = 'tna-rules-v1'


def finalize_appraisal(appraisal, *, actor):
    require_hc_capability(
        actor, 'can_manage_hc_appraisals', employee=appraisal.employee
    )
    with transaction.atomic():
        locked = PenilaianKinerja.objects.select_for_update().get(pk=appraisal.pk)
        if locked.status == 'FINAL':
            raise ValidationError({'status': 'Penilaian sudah final.'})
        items = list(locked.items.all())
        if not items:
            raise ValidationError({'items': 'Penilaian harus memiliki butir.'})
        if any(item.score is None for item in items):
            raise ValidationError({
                'items': 'Semua butir harus dinilai sebelum finalisasi.'
            })
        if locked.reviewer_id is None:
            raise ValidationError({'reviewer': 'Penilai wajib ditetapkan.'})

        locked.status = 'FINAL'
        locked.finalized_at = timezone.now()
        locked.save(update_fields=['status', 'finalized_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='appraisal_finalized',
            target_tipe='appraisal',
            target_id=str(locked.pk),
            status_sebelum='DRAFT',
            status_sesudah='FINAL',
            alasan=f'weighted_score={locked.weighted_score}',
        )
    return locked


def acknowledge_appraisal(appraisal, *, actor):
    if appraisal.employee.akun_id != getattr(actor, 'pk', None):
        raise PermissionDenied('Hanya pegawai yang dinilai dapat mengakui.')
    if appraisal.status != 'FINAL':
        raise ValidationError({'status': 'Hanya penilaian final dapat diakui.'})
    appraisal.acknowledged_at = timezone.now()
    appraisal.save(update_fields=['acknowledged_at'])
    return appraisal


def file_appeal(appraisal, *, actor, notes):
    if appraisal.employee.akun_id != getattr(actor, 'pk', None):
        raise PermissionDenied('Hanya pegawai yang dinilai dapat mengajukan keberatan.')
    if appraisal.status != 'FINAL':
        raise ValidationError({'status': 'Keberatan hanya untuk penilaian final.'})
    if not notes.strip():
        raise ValidationError({'appeal_notes': 'Alasan keberatan wajib diisi.'})
    appraisal.appeal_notes = notes
    appraisal.save(update_fields=['appeal_notes'])
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='appraisal_appealed',
        target_tipe='appraisal',
        target_id=str(appraisal.pk),
        alasan='employee appeal recorded',
    )
    return appraisal


def propose_training_needs(*, unit, actor, period=None, manual_needs=None):
    """Rule-based TNA proposals; every need keeps its source and rule version."""
    require_hc_capability(actor, 'can_manage_hc_training', unit=unit.pk)
    created = []

    with transaction.atomic():
        finalized = PenilaianKinerja.objects.filter(
            employee__penempatan__unit_kerja=unit,
            status='FINAL',
        ).distinct()
        if period is not None:
            finalized = finalized.filter(periode=period)

        for appraisal in finalized.select_related('employee'):
            score = appraisal.weighted_score
            if score is None or score >= Decimal('3.00'):
                continue
            need, was_created = KebutuhanPelatihan.objects.get_or_create(
                employee=appraisal.employee,
                topik='Peningkatan kinerja klinis',
                rule_version=TNA_RULE_VERSION,
                defaults={
                    'unit_kerja': unit,
                    'alasan_agregat': (
                        f'Skor kinerja {score} di bawah ambang 3,00 pada periode '
                        f'{appraisal.periode.nama}.'
                    ),
                    'source_refs': [{'type': 'appraisal', 'id': str(appraisal.pk)}],
                },
            )
            if was_created:
                SumberKebutuhanPelatihan.objects.create(
                    need=need, source_type='appraisal',
                    source_id=str(appraisal.pk), source_date=appraisal.finalized_at.date()
                    if appraisal.finalized_at else None,
                )
                created.append(need)

        for manual in manual_needs or []:
            topic = (manual.get('topik') or '').strip()
            if not topic:
                continue
            need, was_created = KebutuhanPelatihan.objects.get_or_create(
                employee=manual['employee'],
                topik=topic,
                rule_version=TNA_RULE_VERSION,
                defaults={
                    'unit_kerja': unit,
                    'alasan_agregat': manual.get('alasan', ''),
                    'source_refs': [{'type': 'manual', 'id': manual.get('ref', '')}],
                },
            )
            if was_created:
                SumberKebutuhanPelatihan.objects.create(
                    need=need, source_type='manual',
                    source_id=manual.get('ref', ''), note=manual.get('alasan', ''),
                )
                created.append(need)

    return created


def approve_training_need(need, *, actor):
    require_hc_capability(actor, 'can_manage_hc_training', unit=need.unit_kerja_id)
    if need.status != 'DIUSULKAN':
        raise ValidationError({'status': 'Hanya usulan yang dapat disetujui.'})
    need.status = 'DISETUJUI'
    need.approved_by = actor
    need.save(update_fields=['status', 'approved_by'])
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='training_need_approved',
        target_tipe='training_need',
        target_id=str(need.pk),
        status_sebelum='DIUSULKAN',
        status_sesudah='DISETUJUI',
        alasan='HR approval',
    )
    return need


def register_participant(session, employee, *, actor):
    require_hc_capability(actor, 'can_manage_hc_training', employee=employee)
    if session.participants.count() >= session.kapasitas:
        raise ValidationError({'session': 'Kapasitas sesi sudah penuh.'})
    participant, created = PesertaDiklat.objects.get_or_create(
        sesi=session, employee=employee
    )
    if created:
        participant.qr_token = secrets.token_urlsafe(24)
        participant.qr_expires_at = timezone.now() + timedelta(hours=12)
        participant.save(update_fields=['qr_token', 'qr_expires_at'])
    return participant


def record_attendance(participant, *, actor, minutes, correction_reason=''):
    require_hc_capability(actor, 'can_manage_hc_training', employee=participant.employee)
    if minutes < 0:
        raise ValidationError({'minutes': 'Menit kehadiran tidak boleh negatif.'})
    attendance, _ = KehadiranDiklat.objects.get_or_create(peserta=participant)
    if attendance.hadir and not correction_reason.strip():
        raise ValidationError({
            'correction_reason': 'Koreksi kehadiran memerlukan alasan.'
        })
    attendance.hadir = minutes > 0
    attendance.menit_hadir = minutes
    attendance.dicatat_oleh = actor
    attendance.koreksi_alasan = correction_reason
    attendance.save()
    participant.status = 'HADIR' if minutes > 0 else participant.status
    participant.save(update_fields=['status'])
    return attendance


def complete_training(participant, *, actor, score, passed, notes=''):
    """Issue completion only with attendance and evaluation, never registration alone."""
    require_hc_capability(actor, 'can_manage_hc_training', employee=participant.employee)
    attendance = getattr(participant, 'attendance', None)
    if attendance is None or not attendance.hadir:
        raise ValidationError({'attendance': 'Kehadiran belum tercatat.'})
    if score is None:
        raise ValidationError({'score': 'Nilai evaluasi wajib diisi.'})

    with transaction.atomic():
        evaluasi, _ = EvaluasiDiklat.objects.get_or_create(peserta=participant)
        evaluasi.nilai = score
        evaluasi.lulus = passed
        evaluasi.catatan = notes
        evaluasi.evaluated_at = timezone.now()
        evaluasi.save()
        participant.status = 'LULUS' if passed else 'TIDAK_LULUS'
        participant.save(update_fields=['status'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='training_completed',
            target_tipe='training_participant',
            target_id=str(participant.pk),
            status_sesudah=participant.status,
            alasan=f'score={score}',
        )
    return evaluasi


def check_in_by_token(token, *, session, actor):
    """Session-bound QR check-in; a token cannot enrol a different employee."""
    require_hc_capability(actor, 'can_manage_hc_training', employee=None)
    participant = PesertaDiklat.objects.select_related('sesi', 'employee').filter(
        qr_token=token
    ).first()
    if participant is None:
        raise ValidationError({'token': 'Token tidak dikenal.'})
    if participant.sesi_id != session.pk:
        raise ValidationError({'token': 'Token bukan untuk sesi ini.'})
    if participant.qr_expires_at is None or participant.qr_expires_at < timezone.now():
        raise ValidationError({'token': 'Token sudah kedaluwarsa.'})
    require_hc_capability(actor, 'can_manage_hc_training', employee=participant.employee)
    attendance, _ = KehadiranDiklat.objects.get_or_create(peserta=participant)
    if not attendance.hadir:
        attendance.hadir = True
        attendance.dicatat_oleh = actor
        attendance.save()
        participant.status = 'HADIR'
        participant.save(update_fields=['status'])
    return participant


def issue_certificate(participant, *, actor, number=None):
    """Issue one certificate, only after a passing evaluation."""
    require_hc_capability(actor, 'can_manage_hc_training', employee=participant.employee)
    evaluation = getattr(participant, 'evaluation', None)
    if evaluation is None or not evaluation.lulus:
        raise ValidationError({
            'evaluation': 'Sertifikat hanya terbit setelah evaluasi lulus.'
        })
    existing = SertifikatDiklat.objects.filter(peserta=participant).first()
    if existing:
        return existing
    nomor = number or (
        f"DIKLAT/{participant.sesi.program_id}/"
        f"{timezone.localdate():%Y%m}/{participant.pk.hex[:8].upper()}"
    )
    if SertifikatDiklat.objects.filter(nomor=nomor).exists():
        raise ValidationError({'number': 'Nomor sertifikat sudah digunakan.'})
    certificate = SertifikatDiklat.objects.create(
        peserta=participant, nomor=nomor, issued_by=actor
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='training_certificate_issued',
        target_tipe='training_participant',
        target_id=str(participant.pk),
        status_sesudah='CERTIFIED',
        alasan=f'certificate={nomor}',
    )
    return certificate
