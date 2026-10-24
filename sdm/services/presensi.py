"""Shift/attendance service contracts (Task A10)."""

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from sdm.akses import require_hc_capability
from sdm.models import (
    KoreksiPresensi,
    LokasiPresensi,
    PenugasanShift,
    PeristiwaPresensi,
    ShiftDinas,
)


def record_attendance(*, actor, shift_id, event, recorded_at, position,
                      idempotency_key):
    """Record a check-in/out event with server receipt time and optional position.

    Declined/poor position falls back to explicit manual review rather than
    inventing a verified location. Idempotent per key.
    """
    if event not in {'CHECK_IN', 'CHECK_OUT'}:
        raise ValidationError({'event': 'Peristiwa presensi tidak valid.'})
    if not idempotency_key:
        raise ValidationError({'idempotency_key': 'Kunci idempotensi wajib.'})

    assignment = PenugasanShift.objects.select_related(
        'shift__unit_kerja', 'employee'
    ).filter(pk=shift_id, is_active=True).first()
    if assignment is None:
        raise ValidationError({'shift': 'Penugasan shift tidak ditemukan.'})

    require_hc_capability(actor, 'can_view_hc', unit=assignment.shift.unit_kerja)

    existing = PeristiwaPresensi.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    now = timezone.now()
    event_at = recorded_at or now
    if isinstance(event_at, str):
        try:
            event_at = datetime.fromisoformat(event_at)
        except ValueError:
            raise ValidationError({'recorded_at': 'Format waktu tidak valid.'})

    lat = lon = accuracy = None
    within_radius = None
    note = ''
    source = 'WEB'
    if position:
        try:
            lat = position.get('latitude')
            lon = position.get('longitude')
            accuracy = position.get('accuracy_meter')
        except AttributeError:
            raise ValidationError({'position': 'Data posisi tidak valid.'})
        location = LokasiPresensi.objects.filter(
            unit_kerja=assignment.shift.unit_kerja, is_active=True
        ).first()
        if location and lat is not None and lon is not None:
            within_radius = _within_radius(location, lat, lon)
        elif location:
            within_radius = False
            note = 'Posisi tidak tersedia; perlu tinjauan manual.'
            source = 'MANUAL_REVIEW'
    else:
        note = 'Posisi tidak diberikan; perlu tinjauan manual.'
        source = 'MANUAL_REVIEW'

    with transaction.atomic():
        event_obj = PeristiwaPresensi.objects.create(
            assignment=assignment,
            event=event,
            event_at=event_at,
            recorded_at=now,
            source=source,
            latitude=lat,
            longitude=lon,
            accuracy_meter=accuracy,
            within_radius=within_radius,
            location_note=note,
            idempotency_key=idempotency_key,
            recorded_by=actor,
        )
    return event_obj


def _within_radius(location, lat, lon):
    try:
        lat_f, lon_f = float(lat), float(lon)
        loc_lat, loc_lon = float(location.latitude), float(location.longitude)
    except (TypeError, ValueError):
        return False
    # Equirectangular approximation adequate for a 150 m radius.
    import math

    dlat = math.radians(lat_f - loc_lat)
    dlon = math.radians(lon_f - loc_lon) * math.cos(math.radians((lat_f + loc_lat) / 2))
    distance = 6371000 * math.sqrt(dlat * dlat + dlon * dlon)
    return distance <= float(location.radius_meter)


def correct_attendance(*, actor, event_id, corrected_event_at, reason):
    """Append-only correction; requires reviewed attendance capability."""
    event = PeristiwaPresensi.objects.select_related(
        'assignment__shift__unit_kerja'
    ).filter(pk=event_id).first()
    if event is None:
        raise ValidationError({'event': 'Peristiwa presensi tidak ditemukan.'})

    require_hc_capability(
        actor, 'can_manage_hc_employees', unit=event.assignment.shift.unit_kerja
    )
    if not (reason or '').strip():
        raise ValidationError({'reason': 'Alasan koreksi wajib.'})

    if isinstance(corrected_event_at, str):
        try:
            corrected_event_at = datetime.fromisoformat(corrected_event_at)
        except ValueError:
            raise ValidationError({'corrected_event_at': 'Format waktu tidak valid.'})

    return KoreksiPresensi.objects.create(
        event=event,
        corrected_event_at=corrected_event_at,
        reason=reason.strip(),
        reviewed_by=actor,
    )


def effective_work_minutes(assignment, *, as_of=None):
    """Derive approved minutes from paired events plus reviewed corrections."""
    events = list(
        PeristiwaPresensi.objects.filter(assignment=assignment).order_by('event_at')
    )
    if not events:
        return {'minutes': 0, 'is_complete': False, 'reason': 'Belum ada peristiwa presensi.'}

    check_in = next((e for e in events if e.event == 'CHECK_IN'), None)
    check_out = next((e for e in reversed(events) if e.event == 'CHECK_OUT'), None)
    if check_in is None or check_out is None:
        return {
            'minutes': 0,
            'is_complete': False,
            'reason': 'Presensi masuk/keluar belum lengkap.',
        }

    start = _corrected_time(check_in)
    end = _corrected_time(check_out)
    if end <= start:
        return {
            'minutes': 0,
            'is_complete': False,
            'reason': 'Waktu keluar tidak setelah waktu masuk.',
        }
    minutes = int((end - start).total_seconds() // 60)
    return {'minutes': minutes, 'is_complete': True, 'reason': ''}


def _corrected_time(event):
    correction = event.corrections.order_by('-reviewed_at', '-pk').first()
    return correction.corrected_event_at if correction else event.event_at
