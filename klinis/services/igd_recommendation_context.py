"""Bounded clinical evidence for explicit IGD candidate review; no writes."""
import re
from pasien.forms_igd_workflow import STEPS, VITAL_FIELDS


def build_igd_recommendation_context(visit):
    patient = visit.pasien
    identifiers = [str(getattr(patient, name, '') or '') for name in
                   ('nama_lengkap', 'no_rm', 'nik', 'alamat', 'no_telepon')]

    def clean(value, depth=0):
        if depth > 4:
            return None
        if isinstance(value, dict):
            return {str(k)[:80]: clean(v, depth + 1) for k, v in list(value.items())[:40]
                    if not re.search(r'nama|nik|alamat|telepon|phone|no_rm|identity', str(k), re.I)}
        if isinstance(value, list):
            return [clean(v, depth + 1) for v in value[:40]]
        if isinstance(value, str):
            text = value[:2000]
            if re.search(r'ignore|system\s*prompt|instructions?|abaikan|https?://|[\w.+-]+@[\w.-]+|\d{8,}', text, re.I):
                return None
            for identifier in identifiers:
                if identifier:
                    text = re.sub(re.escape(identifier), '[redacted]', text, flags=re.I)
            return text
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return str(value)[:100]

    evidence = {}
    for step in range(2, 8):
        values = {name: clean(getattr(visit, name, None)) for name in STEPS[step][1]}
        evidence[str(step)] = {'source_step': step, 'available': any(v is not None and v != '' and v != {} and v != [] for v in values.values()), 'values': values}
    from pasien.models import IgdVitalObservation
    observation = IgdVitalObservation.objects.filter(workflow__kunjungan=visit, phase='INITIAL').order_by('-observed_at', '-pk').first()
    evidence['4']['observed_at'] = observation.observed_at.isoformat() if observation else None
    if observation:
        evidence['4']['values'] = {name: clean(observation.data.get(name)) for name in VITAL_FIELDS}
        evidence['4']['available'] = any(v is not None and v != '' for v in evidence['4']['values'].values())
    investigations = []
    for order in visit.order_penunjang.order_by('pk')[:30]:
        result = clean(order.hasil_pemeriksaan) if order.status == 'SELESAI' else None
        investigations.append({'source_step': 7, 'status': order.status,
                               'available': bool(result), 'result': result,
                               'observed_at': order.result_recorded_at.isoformat() if order.result_recorded_at else None})
    return {'schema_version': 1, 'evidence': evidence, 'investigations': investigations}
