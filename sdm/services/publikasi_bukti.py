"""Sanitized KPS evidence packs and publication (Task A11)."""

import io
import json

import openpyxl
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from akreditasi.models import EvidenceFile, EvidenceReq, Framework
from sdm.akses import require_hc_capability
from sdm.models import Pegawai, PemetaanStandarSDM, PeristiwaSDM


def build_kps_pack(*, actor, employee_ids, framework_id, as_of=None):
    """Build a permission-filtered staff sample pack from reviewed active-edition
    mappings. Returns a dict artifact (workbook bytes + metadata) without
    publishing to public evidence URLs.

    Never publishes private HC file URLs; private originals stay in the vault.
    """
    require_hc_capability(actor, 'can_export_hc')

    framework = Framework.objects.filter(pk=framework_id, is_active=True).first()
    if framework is None:
        raise ValidationError({'framework': 'Kerangka tidak ditemukan atau tidak aktif.'})

    as_of = as_of or timezone.localdate()

    mappings = PemetaanStandarSDM.objects.filter(
        framework=framework, is_active=True
    ).select_related('rule', 'standard_item')

    rule_map = {
        mapping.rule_id: mapping for mapping in mappings
    }

    employees = Pegawai.objects.filter(pk__in=employee_ids)
    rows = []
    from sdm.services.kepatuhan import evaluate_employee_compliance

    for employee in employees:
        summary = evaluate_employee_compliance(employee, as_of=as_of)
        if not summary.has_data:
            continue
        employee_rules = []
        for result in summary.applicable:
            mapping = rule_map.get(result.rule.pk)
            employee_rules.append({
                'requirement': result.rule.name,
                'jenis_berkas_wajib': result.rule.jenis_berkas_wajib,
                'mapped_ep': mapping.standard_item.code if mapping else None,
                'mapped_ep_text': (
                    mapping.standard_item.description if mapping else None
                ),
                'state': result.state,
                'is_complete': result.is_satisfied,
                'reviewed': bool(mapping),
            })
        rows.append({
            'employee_id': str(employee.pk),
            'nama': employee.nama_lengkap,
            'profesi': employee.profesi,
            'kategori': employee.kategori,
            'completeness_pct': summary.completeness_pct,
            'rules': employee_rules,
        })

    artifact = {
        'generated_at': timezone.now().isoformat(),
        'framework_id': str(framework.pk),
        'framework_name': framework.name,
        'as_of': as_of.isoformat(),
        'actor_id': str(actor.pk),
        'employee_count': len(rows),
        'rows': rows,
    }

    # Render to a sanitized XLSX workbook (in-memory; not yet published).
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = 'Pack KPS'
    ws.append([
        'Employee ID', 'Nama', 'Profesi', 'Kategori',
        'Persyaratan', 'Jenis Berkas Wajib', 'EP Terkait',
        'Status', 'Terbukti', 'Direview',
    ])
    for row in rows:
        for rule in row['rules']:
            ws.append([
                row['employee_id'], row['nama'], row['profesi'], row['kategori'],
                rule['requirement'], rule['jenis_berkas_wajib'],
                rule['mapped_ep'] or '', rule['state'],
                'Ya' if rule['is_complete'] else 'Tidak',
                'Ya' if rule['reviewed'] else 'Tidak',
            ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    artifact['workbook_bytes'] = buffer.getvalue()
    artifact['workbook_hash'] = __import__('hashlib').sha256(
        artifact['workbook_bytes']
    ).hexdigest()
    return artifact


def publish_kps_artifact(*, actor, artifact, requirement_id):
    """Publish the artifact as a sanitized EvidenceFile only after review.

    The private original remains in the HC vault. Returns the EvidenceFile.
    """
    require_hc_capability(actor, 'can_export_hc')
    require_hc_capability(actor, 'can_verify_kps')

    from akreditasi.models import EvidenceReq

    requirement = EvidenceReq.objects.filter(pk=requirement_id).first()
    if requirement is None:
        raise ValidationError({'requirement': 'Elemen penilaian tidak ditemukan.'})

    # Never auto-approve: target review starts REVIEW, requiring owner approval.
    with transaction.atomic():
        evidence_file = EvidenceFile.objects.create(
            requirement=requirement,
            original_filename=f'pack-kps-{requirement.title[:40]}.xlsx',
            storage_key=f'kps-pack/{requirement_id}/{timezone.now().strftime("%Y%m%d%H%M%S")}.xlsx',
            sha256=artifact['workbook_hash'],
            size_bytes=len(artifact['workbook_bytes']),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            status='REVIEW',
        )
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='kps_artifact_published',
            target_tipe='requirement',
            target_id=str(requirement_id),
            alasan=f'framework={artifact["framework_name"]}; as_of={artifact["as_of"]}; employees={artifact["employee_count"]}',
        )
    return evidence_file
