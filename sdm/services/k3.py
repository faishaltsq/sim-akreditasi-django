"""Level 4 staff-safety workflows with an explicit clinical boundary."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_any_hc_capability, require_hc_capability
from sdm.models import (
    AksesDaruratK3,
    ImunisasiPegawai,
    InsidenK3Pegawai,
    PemeriksaanKesehatanKerja,
    PeristiwaSDM,
    TindakLanjutK3,
)

FITNESS_SUMMARY_CHOICES = {
    'FIT': 'Fit untuk bekerja',
    'FIT_DENGAN_CATATAN': 'Fit dengan catatan',
    'TIDAK_FIT': 'Tidak fit',
    'PERLU_PEMERIKSAAN_ULANG': 'Perlu pemeriksaan ulang',
}


def _require_clinician(user, employee, capability='hc_health_write'):
    """Health capabilities never derive from generic roles or superuser status."""
    require_hc_capability(user, capability, employee=employee)


def record_immunization(employee, *, actor, jenis, dosis_ke, tanggal,
                        berlaku_sampai=None, pemberi=''):
    _require_clinician(actor, employee)
    record = ImunisasiPegawai(
        employee=employee,
        jenis=jenis,
        dosis_ke=dosis_ke,
        tanggal=tanggal,
        berlaku_sampai=berlaku_sampai,
        pemberi=pemberi,
    )
    record.full_clean()
    record.save()
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='health_immunization_recorded',
        target_tipe='employee',
        target_id=str(employee.pk),
        status_sesudah='RECORDED',
        alasan='occupational immunization recorded',
    )
    return record


def record_health_exam(employee, *, actor, tanggal, status_kebugaran,
                       ringkasan_klinis='', berlaku_sampai=None, pemeriksa=''):
    _require_clinician(actor, employee)
    if status_kebugaran not in FITNESS_SUMMARY_CHOICES:
        raise ValidationError({'status_kebugaran': 'Status kebugaran tidak valid.'})
    exam = PemeriksaanKesehatanKerja(
        employee=employee,
        tanggal=tanggal,
        status_kebugaran=status_kebugaran,
        ringkasan_klinis=ringkasan_klinis,
        berlaku_sampai=berlaku_sampai,
        pemeriksa=pemeriksa,
    )
    exam.full_clean()
    exam.save()
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='health_exam_recorded',
        target_tipe='employee',
        target_id=str(employee.pk),
        status_sesudah=status_kebugaran,
        alasan='occupational health examination recorded',
    )
    return exam


def fitness_summary(employee, *, user):
    """Return only approved fitness/due summaries outside the clinical boundary."""
    exam = employee.health_exams.order_by('-tanggal').first()
    if exam is None:
        return None
    return {
        'status_kebugaran': exam.get_status_kebugaran_display(),
        'tanggal': exam.tanggal,
        'berlaku_sampai': exam.berlaku_sampai,
        'due': bool(exam.berlaku_sampai and exam.berlaku_sampai < timezone.localdate()),
    }


def report_incident(employee, *, actor, unit_kerja, kategori, deskripsi,
                    tanggal=None):
    require_any_hc_capability(
        actor,
        ('can_view_hc', 'hc_health_write'),
        unit=unit_kerja.pk,
    )
    if kategori not in dict(InsidenK3Pegawai.KATEGORI_CHOICES):
        raise ValidationError({'kategori': 'Kategori insiden tidak valid.'})
    incident = InsidenK3Pegawai(
        employee=employee,
        unit_kerja=unit_kerja,
        kategori=kategori,
        deskripsi=deskripsi,
        tanggal=tanggal or timezone.localdate(),
    )
    incident.full_clean()
    incident.save()
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='k3_incident_reported',
        target_tipe='k3_incident',
        target_id=str(incident.pk),
        status_sesudah='BARU',
        alasan='staff safety incident intake',
    )
    return incident


def assign_investigation(incident, *, actor, investigator):
    require_hc_capability(
        actor, 'hc_health_write', unit=incident.unit_kerja_id
    )
    with transaction.atomic():
        locked = InsidenK3Pegawai.objects.select_for_update().get(pk=incident.pk)
        if locked.status not in {'BARU', 'INVESTIGASI'}:
            raise ValidationError({'status': 'Insiden tidak dalam tahap investigasi.'})
        locked.assigned_to = investigator
        locked.status = 'INVESTIGASI'
        locked.save(update_fields=['assigned_to', 'status', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='k3_incident_assigned',
            target_tipe='k3_incident',
            target_id=str(locked.pk),
            status_sebelum='BARU',
            status_sesudah='INVESTIGASI',
            alasan='investigator assigned',
        )
    return locked


def add_followup(incident, *, actor, tindakan, penanggung_jawab='', tenggat=None):
    require_hc_capability(
        actor, 'hc_health_write', unit=incident.unit_kerja_id
    )
    followup = TindakLanjutK3.objects.create(
        insiden=incident,
        tindakan=tindakan,
        penanggung_jawab=penanggung_jawab,
        tenggat=tenggat,
    )
    incident.status = 'TINDAK_LANJUT'
    incident.save(update_fields=['status', 'updated_at'])
    return followup


def close_incident(incident, *, actor, notes=''):
    require_hc_capability(
        actor, 'hc_health_write', unit=incident.unit_kerja_id
    )
    if incident.status != 'TINDAK_LANJUT':
        raise ValidationError({'status': 'Insiden harus memiliki tindak lanjut sebelum ditutup.'})
    if incident.followups.filter(selesai=False).exists():
        raise ValidationError({'status': 'Masih ada tindak lanjut yang belum selesai.'})
    with transaction.atomic():
        incident.status = 'SELESAI'
        incident.closed_at = timezone.now()
        incident.save(update_fields=['status', 'closed_at', 'updated_at'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='k3_incident_closed',
            target_tipe='k3_incident',
            target_id=str(incident.pk),
            status_sebelum='TINDAK_LANJUT',
            status_sesudah='SELESAI',
            alasan=notes[:200] or 'reviewed closure',
        )
    return incident


def request_break_glass(employee, *, actor, reason, hours=4):
    """Explicit emergency access with reason, expiry, and later review."""
    if not (reason or '').strip():
        raise ValidationError({'reason': 'Alasan darurat wajib dicatat.'})
    if not 1 <= hours <= 24:
        raise ValidationError({'hours': 'Durasi akses darurat 1–24 jam.'})
    require_hc_capability(actor, 'hc_health_break_glass', employee=employee)
    access = AksesDaruratK3.objects.create(
        user=actor,
        employee=employee,
        alasan=reason,
        expires_at=timezone.now() + timedelta(hours=hours),
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='health_break_glass_requested',
        target_tipe='employee',
        target_id=str(employee.pk),
        status_sesudah='GRANTED',
        alasan='break-glass access requested',
    )
    return access


def review_break_glass(access, *, reviewer, notes=''):
    if not getattr(reviewer, 'is_superuser', False):
        require_hc_capability(
            reviewer, 'hc_health_read', employee=access.employee
        )
    if access.reviewed_at is not None:
        raise ValidationError({'status': 'Akses darurat sudah ditinjau.'})
    access.reviewed_by = reviewer
    access.reviewed_at = timezone.now()
    access.review_notes = notes
    access.save(update_fields=['reviewed_by', 'reviewed_at', 'review_notes'])
    PeristiwaSDM.objects.create(
        actor=reviewer,
        jenis_peristiwa='health_break_glass_reviewed',
        target_tipe='employee',
        target_id=str(access.employee_id),
        status_sesudah='REVIEWED',
        alasan='break-glass review completed',
    )
    return access


def can_read_clinical_detail(user, employee):
    """Clinical detail requires an explicit health read grant, not a role."""
    try:
        require_hc_capability(user, 'hc_health_read', employee=employee)
    except PermissionDenied:
        return False
    return True
