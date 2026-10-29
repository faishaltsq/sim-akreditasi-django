"""Legal EWS: license/SPK status and urgent reminders (Task A3)."""

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from sdm.models import (
    IzinProfesiPegawai,
    Pegawai,
    PenugasanKlinis,
    PengingatSDM,
    VersiDokumen,
)

EXPIRED = 'expired'
ZERO_SEVEN = '0-7'
EIGHT_THIRTY = '8-30'
THIRTY_NINETY = '31-90'
VALID = 'valid'
UNKNOWN = 'unknown'

LEGAL_BANDS = (EXPIRED, ZERO_SEVEN, EIGHT_THIRTY, THIRTY_NINETY)
LEGAL_LABELS = {
    EXPIRED: 'Kedaluwarsa',
    ZERO_SEVEN: '0–7 hari',
    EIGHT_THIRTY: '8–30 hari',
    THIRTY_NINETY: '31–90 hari',
    VALID: 'Berlaku',
    UNKNOWN: 'Tidak diketahui',
}


@dataclass(frozen=True)
class LegalStatus:
    employee_id: str
    as_of: str
    items: list

    def by_subtype(self, subtype):
        return [i for i in self.items if i.get('subtype') == subtype]

    def expired_or_urgent(self):
        return [i for i in self.items if i.get('band') in {EXPIRED, ZERO_SEVEN, EIGHT_THIRTY}]


def legal_status(employee, *, as_of=None, practice_site=None):
    """Compute legal/permit status per exact typed license and SPK.

    Never uses filename matching; consumes B2/B3 IzinProfesiPegawai and
    KeputusanKredensial with practice-site and validity-mode awareness.
    """
    as_of = as_of or timezone.localdate()

    items = []

    # Typed professional licenses (STR/SIP/SIPA/OTHER)
    for izin in IzinProfesiPegawai.objects.filter(pegawai=employee).order_by('subtype', 'nomor_izin'):
        # Practice-site filter: if a site is requested, only local-RS or matching site counts.
        if practice_site is not None and not izin.is_local_rs:
            continue
        band = _license_band(izin, as_of)
        items.append({
            'subtype': izin.subtype,
            'nomor_izin': izin.nomor_izin,
            'profesi': izin.profesi,
            'pemberi_izin': izin.pemberi_izin,
            'validity_mode': izin.validity_mode,
            'tanggal_terbit': izin.tanggal_terbit.isoformat() if izin.tanggal_terbit else None,
            'tanggal_berakhir': izin.tanggal_berakhir.isoformat() if izin.tanggal_berakhir else None,
            'is_local_rs': izin.is_local_rs,
            'organisasi_praktik': izin.organisasi_praktik,
            'lokasi_praktik': izin.lokasi_praktik,
            'state': band if band != VALID else VALID,
            'band': band,
            'label': LEGAL_LABELS[band],
            'source': 'izin_profesi',
        })

    # SPK / clinical privilege decisions (revocation-aware)
    for sk in PenugasanKlinis.objects.filter(employee=employee).order_by('-issued_at', '-pk'):
        band = _spk_band(sk, as_of)
        items.append({
            'subtype': 'SPK',
            'nomor_izin': sk.nomor_spk or '',
            'profesi': '',
            'pemberi_izin': '',
            'validity_mode': 'DATED',
            'tanggal_terbit': sk.issued_at.date().isoformat() if sk.issued_at else None,
            'tanggal_berakhir': sk.berlaku_sampai.isoformat() if sk.berlaku_sampai else None,
            'is_local_rs': True,
            'organisasi_praktik': sk.unit_kerja.name if sk.unit_kerja else '',
            'lokasi_praktik': sk.unit_kerja.name if sk.unit_kerja else '',
            'state': band,
            'band': band,
            'label': LEGAL_LABELS[band],
            'source': 'spk',
            'revoked': not bool(getattr(sk, 'is_active', True)),
        })

    if not items:
        items.append({
            'subtype': None,
            'nomor_izin': '',
            'profesi': '',
            'pemberi_izin': '',
            'validity_mode': None,
            'tanggal_terbit': None,
            'tanggal_berakhir': None,
            'is_local_rs': False,
            'organisasi_praktik': '',
            'lokasi_praktik': '',
            'state': UNKNOWN,
            'band': UNKNOWN,
            'label': LEGAL_LABELS[UNKNOWN],
            'source': 'none',
        })

    return LegalStatus(
        employee_id=str(employee.pk),
        as_of=as_of.isoformat(),
        items=items,
    )


def _license_band(izin, as_of):
    if izin.validity_mode == 'LIFETIME':
        return VALID
    if not izin.tanggal_berakhir:
        return UNKNOWN
    if izin.tanggal_berakhir < as_of:
        return EXPIRED
    delta = (izin.tanggal_berakhir - as_of).days
    if delta <= 7:
        return ZERO_SEVEN
    if delta <= 30:
        return EIGHT_THIRTY
    if delta <= 90:
        return THIRTY_NINETY
    return VALID


def _spk_band(sk, as_of):
    if not bool(getattr(sk, 'is_active', True)):
        return EXPIRED
    end = getattr(sk, 'berlaku_sampai', None)
    if not end:
        return UNKNOWN
    if end < as_of:
        return EXPIRED
    delta = (end - as_of).days
    if delta <= 7:
        return ZERO_SEVEN
    if delta <= 30:
        return EIGHT_THIRTY
    if delta <= 90:
        return THIRTY_NINETY
    return VALID


BLOCKING_BANDS = {EXPIRED, ZERO_SEVEN, EIGHT_THIRTY, THIRTY_NINETY}


def placement_legal_blockers(employee, *, unit_kerja=None, as_of=None):
    """Blockers for placing/keeping an employee in a unit: only expired or
    expiring licenses (STR/SIP/SIPA) and revoked SPK count. A license with no
    recorded expiry is unknown, not a violation, and never blocks.
    """
    status = legal_status(employee, as_of=as_of)
    blockers = []
    for item in status.items:
        if item['source'] == 'none':
            continue
        if item.get('revoked') or item['band'] not in BLOCKING_BANDS:
            continue
        blockers.append({
            'subtype': item['subtype'],
            'nomor': item['nomor_izin'],
            'label': item['label'],
            'alasan': (
                f"{item['subtype']} {item['nomor_izin'] or ''}".strip()
                + f" berstatus {item['label'].lower()}"
            ),
        })
    return blockers


def sync_legal_reminders(*, employee, actor, as_of=None):
    """Create/refresh idempotent legal reminders for expired/urgent licenses and SPK.

    Band legal dipetakan ke band PengingatSDM yang sah; pegawai tanpa akun
    dilewati (tidak ada penerima in-app) tanpa menggagalkan pemanggil.
    Pengarsipan hanya menyentuh pengingat legalitas milik pegawai ini, sehingga
    pengingat dokumen/SPK/orientasi lain tidak ikut tertandai sudah dibaca.
    """
    from sdm.models.pengingat import LEGAL_BAND_MAP
    as_of = as_of or timezone.localdate()
    status = legal_status(employee, as_of=as_of)
    recipient = getattr(employee, 'akun', None)
    if recipient is None:
        return {'created': 0, 'updated': 0, 'archived': 0}
    created = updated = 0
    urgent_keys = set()
    for item in status.items:
        if item['source'] == 'none' or item['state'] == VALID:
            continue
        band = LEGAL_BAND_MAP.get(item['band'])
        if band is None:
            continue
        alasan = f"{item['label']}: {item['nomor_izin'] or item['subtype']}"
        key = PengingatSDM.build_key(
            employee_id=employee.pk,
            version_id=f"legal:{item['source']}:{item['nomor_izin'] or item['subtype']}",
            band=band,
            target_type='DOCUMENT',
        )
        urgent_keys.add(key)
        due_date = (
            date.fromisoformat(item['tanggal_berakhir'])
            if item['tanggal_berakhir'] else as_of
        )
        obj, was_created = PengingatSDM.objects.get_or_create(
            idempotency_key=key,
            defaults={
                'employee': employee,
                'version': None,
                'band': band,
                'target_type': 'DOCUMENT',
                'recipient': recipient,
                'due_date': due_date,
                'alasan': alasan,
            },
        )
        if was_created:
            created += 1
        elif obj.band != band or obj.alasan != alasan or obj.due_date != due_date:
            obj.band = band
            obj.alasan = alasan
            obj.due_date = due_date
            obj.save(update_fields=['band', 'alasan', 'due_date'])
            updated += 1
    # Arsipkan hanya pengingat legalitas milik pegawai ini yang tak lagi urgen.
    # Filter ':legal:' (bukan 'DOCUMENT:') agar pengingat dokumen biasa milik
    # pegawai yang sama tidak ikut tertandai sudah dibaca.
    archived = PengingatSDM.objects.filter(
        employee=employee, recipient=recipient, read_at__isnull=True,
        idempotency_key__contains=':legal:',
    ).exclude(idempotency_key__in=urgent_keys).update(read_at=as_of)
    return {'created': created, 'updated': updated, 'archived': archived}


def sync_legal_reminders_all(*, as_of=None):
    """Bulk entry point: refresh legal reminders for every employee with an account.

    Mirrors the other bulk sync helpers in sdm.models.pengingat: one queryset
    plus per-employee delegation, returning an aggregate dict.
    """
    as_of = as_of or timezone.localdate()
    totals = {'created': 0, 'updated': 0, 'archived': 0}
    employees = Pegawai.objects.filter(
        akun__isnull=False, akun__is_active=True
    ).select_related('akun')
    for employee in employees:
        result = sync_legal_reminders(
            employee=employee, actor=None, as_of=as_of
        )
        for key in totals:
            totals[key] += result.get(key, 0)
    return totals
