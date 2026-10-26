"""Employee document requirement evaluation (HC-03) and expiry bands (HC-04)."""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

from sdm.models import AturanDokumen, DokumenPegawai, VersiDokumen


STATE_MISSING = 'MISSING'
STATE_PENDING = 'PENDING'
STATE_REJECTED = 'REJECTED'
STATE_VALID = 'VALID'
STATE_EXPIRING = 'EXPIRING'
STATE_EXPIRED = 'EXPIRED'
STATE_NOT_APPLICABLE = 'NOT_APPLICABLE'

STATE_LABELS = {
    STATE_MISSING: 'Belum ada',
    STATE_PENDING: 'Menunggu tinjauan',
    STATE_REJECTED: 'Ditolak',
    STATE_VALID: 'Valid',
    STATE_EXPIRING: 'Akan kedaluwarsa',
    STATE_EXPIRED: 'Kedaluwarsa',
    STATE_NOT_APPLICABLE: 'Tidak berlaku',
}

EXPIRING_WINDOW_DAYS = 30


@dataclass(frozen=True)
class RequirementResult:
    rule: AturanDokumen
    state: str
    version: VersiDokumen | None = None

    @property
    def label(self):
        return STATE_LABELS[self.state]

    @property
    def is_satisfied(self):
        return self.state == STATE_VALID


@dataclass
class ComplianceSummary:
    results: list = field(default_factory=list)

    @property
    def applicable(self):
        return [r for r in self.results if r.state != STATE_NOT_APPLICABLE]

    @property
    def satisfied(self):
        return [r for r in self.applicable if r.is_satisfied]

    @property
    def uploaded(self):
        return [r for r in self.applicable if r.version is not None]

    @property
    def completeness_pct(self):
        total = len(self.applicable)
        if not total:
            return None
        return round(len(self.satisfied) / total * 100, 1)

    @property
    def upload_pct(self):
        total = len(self.applicable)
        if not total:
            return None
        return round(len(self.uploaded) / total * 100, 1)

    @property
    def has_data(self):
        return bool(self.applicable)


def _active_rules(ruleset=None):
    queryset = AturanDokumen.objects.filter(is_active=True)
    if ruleset is not None:
        ids = [rule.pk for rule in ruleset if getattr(rule, 'pk', None)]
        queryset = queryset.filter(pk__in=ids)
    latest = {}
    for rule in queryset.order_by('version'):
        key = (
            rule.document_type, rule.jenis_berkas_wajib,
            rule.name, rule.kategori, rule.profesi,
        )
        latest[key] = rule
    return list(latest.values())


def _latest_version(employee, rule):
    sensitivity = 'health' if rule.document_type == 'HEALTH' else 'personnel'
    return VersiDokumen.objects.filter(
        document__employee=employee,
        document__document_type=rule.document_type,
        document__jenis_berkas=rule.jenis_berkas_wajib,
        document__sensitivity=sensitivity,
    ).select_related('document').order_by('-version_number', '-pk').first()


def _evaluate_version(rule, version, *, as_of):
    if version is None:
        return RequirementResult(rule, STATE_MISSING)
    if version.status == 'PENDING':
        return RequirementResult(rule, STATE_PENDING, version)
    if version.status == 'REJECTED':
        return RequirementResult(rule, STATE_REJECTED, version)
    if version.status == 'SUPERSEDED':
        return RequirementResult(rule, STATE_MISSING)

    policy = rule.validity_policy
    if policy == 'NOT_APPLICABLE':
        return RequirementResult(rule, STATE_NOT_APPLICABLE, version)
    if policy == 'LIFETIME':
        return RequirementResult(rule, STATE_VALID, version)

    if version.valid_until is None:
        return RequirementResult(rule, STATE_PENDING, version)
    if version.valid_until < as_of:
        return RequirementResult(rule, STATE_EXPIRED, version)
    if version.valid_until <= as_of + timedelta(days=EXPIRING_WINDOW_DAYS):
        return RequirementResult(rule, STATE_EXPIRING, version)
    return RequirementResult(rule, STATE_VALID, version)


def evaluate_employee_compliance(employee, *, as_of=None, ruleset=None):
    """Return one result per applicable rule; uploaded and verified stay distinct."""
    as_of = as_of or timezone.localdate()
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of)

    results = []
    for rule in _active_rules(ruleset):
        if not rule.applies_to(employee):
            results.append(RequirementResult(rule, STATE_NOT_APPLICABLE))
            continue
        version = _latest_version(employee, rule)
        results.append(_evaluate_version(rule, version, as_of=as_of))
    return ComplianceSummary(results)


def expiry_bands(*, as_of=None):
    """Disjoint 0-30/31-60/61-90 bands plus expired; lifetime documents are exempt."""
    as_of = as_of or timezone.localdate()
    d30 = as_of + timedelta(days=30)
    d60 = as_of + timedelta(days=60)
    d90 = as_of + timedelta(days=90)

    versions = VersiDokumen.objects.filter(
        status='VERIFIED', valid_until__isnull=False,
    ).exclude(document__sensitivity='health').select_related('document__employee')

    bands = {'expired': [], 'lt_30': [], 'lt_60': [], 'lt_90': []}
    for version in versions:
        if version.valid_until < as_of:
            bands['expired'].append(version)
        elif version.valid_until <= d30:
            bands['lt_30'].append(version)
        elif version.valid_until <= d60:
            bands['lt_60'].append(version)
        elif version.valid_until <= d90:
            bands['lt_90'].append(version)
    return bands


def documents_for_employee(employee, *, include_health=False):
    queryset = DokumenPegawai.objects.filter(employee=employee)
    if not include_health:
        queryset = queryset.exclude(sensitivity='health').exclude(
            document_type='HEALTH'
        )
    return queryset.order_by('-created_at', '-pk')
