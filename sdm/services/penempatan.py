from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from sdm.models import Pegawai, PenempatanPegawai


MAX_EMPLOYEE_FTE = Decimal('1.00')


def _overlapping_assignments(assignment):
    queryset = PenempatanPegawai.objects.filter(
        pegawai_id=assignment.pegawai_id
    ).exclude(pk=assignment.pk)
    if assignment.tanggal_selesai is not None:
        queryset = queryset.filter(tanggal_mulai__lte=assignment.tanggal_selesai)
    return queryset.filter(
        Q(tanggal_selesai__isnull=True)
        | Q(tanggal_selesai__gte=assignment.tanggal_mulai)
    ).only('tanggal_mulai', 'tanggal_selesai', 'alokasi_fte')


def _validate_peak_allocation(assignments):
    changes_by_date = defaultdict(lambda: Decimal('0.00'))
    for item in assignments:
        changes_by_date[item.tanggal_mulai] += item.alokasi_fte
        if item.tanggal_selesai is not None:
            changes_by_date[item.tanggal_selesai + timedelta(days=1)] -= item.alokasi_fte

    current_total = Decimal('0.00')
    for effective_date in sorted(changes_by_date):
        current_total += changes_by_date[effective_date]
        if current_total > MAX_EMPLOYEE_FTE:
            raise ValidationError({
                'alokasi_fte': 'Total alokasi FTE pegawai pada tanggal yang bertumpang tindih tidak boleh melebihi 1,00.'
            })


def save_assignment(assignment):
    """Validate and persist one placement while serializing writes per employee."""
    if not assignment.pegawai_id:
        raise ValidationError({'pegawai': 'Pegawai wajib dipilih.'})

    with transaction.atomic():
        if assignment.pk:
            existing_employee_id = PenempatanPegawai.objects.filter(
                pk=assignment.pk
            ).values_list('pegawai_id', flat=True).first()
            if existing_employee_id is None:
                raise ValidationError({'id': 'Penempatan tidak ditemukan.'})
            if existing_employee_id != assignment.pegawai_id:
                raise ValidationError({
                    'pegawai': 'Pegawai pada penempatan yang sudah ada tidak dapat diganti.'
                })

        try:
            Pegawai.objects.select_for_update().get(pk=assignment.pegawai_id)
        except Pegawai.DoesNotExist:
            raise ValidationError({'pegawai': 'Pegawai tidak ditemukan.'}) from None

        assignment.full_clean()
        overlaps = _overlapping_assignments(assignment)
        _validate_peak_allocation([*overlaps, assignment])
        is_new = assignment.pk is None
        assignment.save()

    if is_new:
        # Mutasi/penempatan baru: pastikan orientasi khusus unit berjalan
        # (idempoten; tidak menggagalkan penempatan bila program belum ada).
        from sdm.services.orientasi import auto_assign_orientation
        try:
            auto_assign_orientation(
                assignment.pegawai, actor=assignment.pegawai.akun or None,
                unit_kerja=assignment.unit_kerja,
            )
        except ValidationError:
            pass

    return assignment
