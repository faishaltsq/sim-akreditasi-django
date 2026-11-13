"""Visit-owned diagnosis changes; caller owns the workflow transaction and lock."""
import json

from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from akreditasi.models import AuditLog
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from klinis.models import MasterIcd10
from pasien.models import DiagnosisKunjungan
from .igd_assessment_workflow import WorkflowValidation


def invalid(message):
    raise WorkflowValidation({'changes': [message]})


def set_diagnoses(visit, workflow, user, data):
    if user.profile.profesi not in {'DOKTER_UMUM', 'DOKTER_SPESIALIS'}:
        raise PermissionDenied('Penetapan diagnosis medis memerlukan dokter.')
    if set(data) != {'changes'} or not isinstance(data['changes'], list) or not 1 <= len(data['changes']) <= 30:
        invalid('Kirim satu sampai 30 perubahan diagnosis.')
    rows = {row.pk: row for row in visit.diagnoses.select_for_update().all()}
    audit_fields = ('id', 'kode', 'nama', 'mode', 'active', 'is_primary', 'provenance', 'updated_by_id')
    before = [{field: getattr(row, field) for field in audit_fields} for row in rows.values()]
    working = {pk: {'row': row, 'active': row.active, 'primary': row.is_primary} for pk, row in rows.items()}
    seen = set()
    staged = []
    for change in data['changes']:
        if not isinstance(change, dict):
            invalid('Perubahan diagnosis harus berupa objek.')
        op = change.get('op')
        allowed = {'op', 'id'} if op == 'cancel' else {'op', 'id', 'temp_id', 'mode', 'text', 'code', 'is_primary', 'ai_ticket'}
        if op not in {'upsert', 'cancel'} or set(change) - allowed:
            invalid('Operasi atau atribut diagnosis tidak dikenal.')
        pk = change.get('id')
        if pk is not None:
            if type(pk) is not int or pk <= 0 or pk not in rows or not rows[pk].active:
                invalid('Diagnosis tidak ditemukan pada episode aktif ini.')
            identity = ('id', pk)
            row = rows[pk]
        else:
            temp = change.get('temp_id')
            if op == 'cancel' or not isinstance(temp, str) or not 1 <= len(temp) <= 80:
                invalid('Diagnosis baru memerlukan ID sementara yang unik.')
            identity = ('temp', temp)
            row = DiagnosisKunjungan(kunjungan=visit)
        if identity in seen:
            invalid('ID diagnosis berulang dalam satu permintaan.')
        seen.add(identity)
        if op == 'cancel':
            working[pk]['active'] = False
            working[pk]['primary'] = False
            staged.append((row, {'active': False, 'is_primary': False}))
            continue
        mode = change.get('mode')
        if mode not in {'MANUAL', 'MASTER', 'AI'} or type(change.get('is_primary')) is not bool:
            invalid('Pilih mode dan penanda diagnosis utama yang valid.')
        text = change.get('text', '')
        if not isinstance(text, str) or len(text) > 2000:
            invalid('Diagnosis maksimal 2.000 karakter.')
        code = change.get('code', '')
        if not isinstance(code, str) or len(code) > 10:
            invalid('Kode diagnosis tidak valid.')
        master = None
        if mode != 'MANUAL':
            master = MasterIcd10.objects.filter(kode=code).first()
            if master is None:
                invalid('Kode ICD-10 tidak ditemukan pada master.')
            text = master.nama
        elif not text.strip() or code:
            invalid('Diagnosis manual memerlukan teks tanpa kode master.')
        provenance = {'accepted_by': user.pk, 'accepted_at': timezone.now().isoformat(), 'mode': mode}
        if mode == 'AI' and row.pk and row.mode=='AI' and row.kode==code and row.nama==text and not change.get('ai_ticket'):
            provenance=row.provenance
        elif mode == 'AI':
            try:
                try:
                    claims = signing.loads(change.get('ai_ticket', ''), salt='igd-ai-target', max_age=900)
                    claims['medical'] = claims['codes'] if claims.get('target')=='medical' else []
                except signing.BadSignature:
                    claims = signing.loads(change.get('ai_ticket', ''), salt='igd-ai-suggestion', max_age=900)
                if (claims['visit'] != visit.pk or claims['user'] != user.pk or
                        claims['version'] != workflow.version or code not in claims['medical'] or
                        claims.get('target', 'medical') != 'medical'):
                    raise ValueError('binding')
            except (signing.BadSignature, ValueError, TypeError, KeyError) as exc:
                invalid('Kandidat AI kedaluwarsa atau tidak sesuai diagnosis/episode.')
            provenance['candidate_code'] = code
        elif 'ai_ticket' in change:
            invalid('Tiket AI hanya digunakan pada mode AI.')
        values = {'active': True, 'is_primary': change['is_primary'], 'mode': mode,
                  'icd10': master, 'kode': code, 'nama': text.strip(), 'provenance': provenance}
        working[pk if pk is not None else identity] = {'row': row, 'active': True, 'primary': change['is_primary']}
        staged.append((row, values))
    active = [item for item in working.values() if item['active']]
    if len(active) > 30 or sum(item['primary'] for item in active) > 1:
        invalid('Maksimal 30 diagnosis aktif dan satu diagnosis utama.')
    # Demote before promotion so a primary switch cannot violate the partial unique constraint.
    visit.diagnoses.filter(is_primary=True).update(is_primary=False)
    changed_ids = []
    for row, values in staged:
        for name, value in values.items():
            setattr(row, name, value)
        row.updated_by = user
        row.save()
        changed_ids.append(row.pk)
    # An omitted primary remains primary unless explicitly changed or cancelled.
    for item in working.values():
        if item['row'].pk not in changed_ids and item['active'] and item['primary']:
            visit.diagnoses.filter(pk=item['row'].pk).update(is_primary=True)
    primary = visit.diagnoses.filter(active=True, is_primary=True).first()
    label = (f'{primary.kode} — {primary.nama}' if primary.kode else primary.nama) if primary else ''
    visit.diagnosa_masuk = label if len(label) <= 300 else label[:299] + '…'
    visit.save(update_fields=['diagnosa_masuk'])
    AuditLog.objects.create(user=user, aksi='UPDATE', model_name='DiagnosisKunjungan',
        object_repr=f'Diagnosis episode #{visit.pk}', detail=json.dumps({
            'before': before, 'after': list(visit.diagnoses.order_by('pk').values(*audit_fields)),
        }, cls=DjangoJSONEncoder))
    return {'diagnosis_ids': changed_ids}
