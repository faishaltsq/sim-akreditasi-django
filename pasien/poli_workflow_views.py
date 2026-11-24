"""View asesmen POLI-JANTUNG (F1.6).

Route baru, mesin yang sama: ``get_visit``/``save_step``/``perform_action``
dipakai ulang dengan ``service_line='RAJAL_JANTUNG'``. Tidak ada satu pun view
IGD yang disentuh.

Flag rilis diperiksa **eksplisit** lewat ``POLI_JANTUNG_WORKFLOW_ENABLED``
(ADR-8). ``require_rollout()`` tidak dipakai karena hanya membaca
``IGD_WORKFLOW_ENABLED`` ketika episode belum punya workflow.
"""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .services.igd_assessment_workflow import (
    RAJAL_JANTUNG_SERVICE_LINE, WorkflowConflict, WorkflowValidation, get_visit, save_step,
)
from .services.poli_rbac import (
    DPJP, FILL_ROLES, ROLE_LABELS, authorize_step, resolve_role,
)
from .workflow_schemas import RAJAL_JANTUNG_STEPS

CLOSED_VISIT_STATUSES = ('PULANG', 'RUJUK', 'MENINGGAL', 'BATAL')


def require_poli_rollout():
    if not getattr(settings, 'POLI_JANTUNG_WORKFLOW_ENABLED', False):
        raise Http404


def _step_or_bad_request(raw, workflow):
    try:
        step = int(raw if raw is not None else (workflow.last_step if workflow else 1))
    except (TypeError, ValueError):
        return None
    return step if step in RAJAL_JANTUNG_STEPS else None


@login_required
@require_GET
@never_cache
def poli_workflow(request, pk):
    require_poli_rollout()
    visit, workflow = get_visit(pk, request.user, service_line=RAJAL_JANTUNG_SERVICE_LINE)
    step = _step_or_bad_request(request.GET.get('step'), workflow)
    if step is None:
        return HttpResponseBadRequest('Langkah tidak valid.')
    authorize_step(request.user, visit, step, 'read')
    role = resolve_role(request.user, visit)
    spec = RAJAL_JANTUNG_STEPS[step]
    values = (workflow.draft_payload or {}).get(str(step), {}) if workflow else {}
    can_fill = (
        role in FILL_ROLES[step]
        and (workflow is None or workflow.status != 'FINAL')
        and visit.status not in CLOSED_VISIT_STATUSES
    )
    return render(request, 'pasien/poli_workflow.html', {
        'kunjungan': visit,
        'pasien': visit.pasien,
        'workflow': workflow,
        'version': workflow.version if workflow else 0,
        'steps': [
            {'number': number, 'title': RAJAL_JANTUNG_STEPS[number].title,
             'current': number == step,
             'filled': bool((workflow.draft_payload or {}).get(str(number))) if workflow else False}
            for number in sorted(RAJAL_JANTUNG_STEPS)
        ],
        'step': step,
        'step_title': spec.title,
        'fields': [_field_view(item, values) for item in spec.fields],
        'can_fill': can_fill,
        'can_finalize': (
            role == DPJP
            and (workflow is None or workflow.status != 'FINAL')
            and visit.status not in CLOSED_VISIT_STATUSES
        ),
        'readonly': not can_fill,
        'role_label': ROLE_LABELS.get(role, 'Tanpa peran asesmen'),
        'is_final': bool(workflow and workflow.status == 'FINAL'),
        'missing_sections': [] if workflow is None else _missing(visit, workflow),
        'rollout_enabled': settings.POLI_JANTUNG_WORKFLOW_ENABLED,
        'clinical': _clinical_context(visit, values),
    })

def _field_view(item, values):
    """Satu field untuk template: kode pilihan + label yang terbaca manusia."""
    from pasien.workflow_schemas import STEP_LABELS

    labels = STEP_LABELS.get(item.name, {})
    value = values.get(item.name, '')
    view = {
        'name': item.name, 'kind': item.kind, 'label': item.label or item.name,
        'choices': [{'value': code, 'label': labels.get(code, code)} for code in item.choices],
        'minimum': item.minimum, 'maximum': item.maximum,
        'value': value,
    }
    if item.kind == 'multiselect':
        selected = value if isinstance(value, list) else []
        view['selected'] = selected
        view['choices'] = [
            {'value': code, 'label': labels.get(code, code), 'checked': code in selected}
            for code in item.choices
        ]
    elif item.kind == 'group':
        # Sub-field dirender sebagai ``<induk>.<anak>``; layanan menyatukannya
        # kembali menjadi dict sebelum validasi.
        group_values = value if isinstance(value, dict) else {}
        view['children'] = [
            _field_view(child, group_values) | {'name': f'{item.name}.{child.name}'}
            for child in item.children
        ]
    elif item.kind == 'markers':
        import json
        markers = value if isinstance(value, list) else []
        view['value'] = markers
        view['json'] = json.dumps(markers) if markers else ''
    return view


def _clinical_context(visit, values):
    """Nilai turunan yang ditampilkan bersama draft (F2.2–F2.6, ADR-6).

    Dihitung dari ``draft_payload`` langkah 4/5 yang sedang dibuka, bukan dari
    kolom model: jalur rajal tidak menyimpan TTV ke ``KunjunganPasien``.
    """
    from pasien.models import (
        hitung_imt, hitung_map, imt_kategori, indeks_brinkman, map_kategori, ttv_alerts,
    )
    from pasien.clinical_thresholds import hipertensi_threshold_source
    from pasien.forms_igd_workflow import MORSE_SEDANG_MIN, MORSE_TINGGI_MIN, MST_BERISIKO_MIN
    from pasien.services.pregnancy_safety import PREGNANCY_CONTRA_CLASSES, pregnancy_status
    from pasien.workflow_schemas import STEP_LABELS

    sistole, diastole = values.get('ttv_sistole'), values.get('ttv_diastole')
    berat, tinggi = values.get('berat_badan'), values.get('tinggi_badan')
    imt = hitung_imt(berat, tinggi)
    morse = values.get('skrining_jatuh_skor')
    mst = values.get('skrining_gizi_mst')
    # F3: nilai langkah 3 ditampilkan di panel untuk semua langkah, bukan hanya
    # saat langkah 3 dibuka — peringatan kehamilan harus terlihat saat menulis.
    workflow = getattr(visit, 'igd_workflow', None)
    step3 = ((workflow.draft_payload or {}).get('3') or {}) if workflow else {}
    kehamilan = pregnancy_status(visit)
    return {
        'map_value': hitung_map(sistole, diastole),
        'map_kategori': map_kategori(sistole, diastole),
        # ADR-14: ambang hipertensi berasal dari konfigurasi, jadi sumbernya
        # wajib ikut tampil — bukan angka telanjang tanpa provenance.
        'map_kategori_source': hipertensi_threshold_source(),
        'imt': imt,
        'imt_kategori': imt_kategori(imt),
        'morse_grade': (
            '' if morse is None
            else 'TINGGI' if morse >= MORSE_TINGGI_MIN
            else 'SEDANG' if morse >= MORSE_SEDANG_MIN else 'RENDAH'
        ),
        'mst_score': mst,
        'mst_berisiko': None if mst is None else mst >= MST_BERISIKO_MIN,
        'alerts': ttv_alerts(
            sistole=sistole, diastole=diastole, nadi=values.get('ttv_nadi'),
            spo2=values.get('ttv_spo2'), skala_nyeri=values.get('ttv_skala_nyeri'),
        ),
        'red_flag_label': STEP_LABELS['red_flag_kardio'].get(visit.red_flag_kardio, ''),
        'door_to_ecg': visit.door_to_ecg_indicator(),
        # F3.2: indeks Brinkman sebagai angka mentah; klasifikasi masih
        # AMBIGU-03 sehingga tidak ada band yang ditampilkan.
        'brinkman': indeks_brinkman(
            step3.get('batang_per_hari'), step3.get('tahun_merokok'),
        ),
        'brinkman_komponen': (
            step3.get('batang_per_hari'), step3.get('tahun_merokok'),
        ),
        # F3.3: peringatan kontraindikasi — kelompoknya disebut apa adanya.
        'kehamilan_label': STEP_LABELS['status_kehamilan_menyusui'].get(kehamilan, ''),
        'kehamilan_kontraindikasi': list(PREGNANCY_CONTRA_CLASSES) if kehamilan else [],
        'kehamilan_status': kehamilan,
        # F3.4: rekonsiliasi obat rutin tampil di panel kanan.
        'kepatuhan_obat_label': STEP_LABELS['kepatuhan_obat'].get(step3.get('kepatuhan_obat') or '', ''),
        'obat_rutin_labels': [
            STEP_LABELS['obat_rutin'].get(code, code)
            for code in (step3.get('obat_rutin') or [])
        ],
        'obat_rutin_terakhir': step3.get('obat_rutin_terakhir') or '',
    }


def _missing(visit, workflow):
    from .services.igd_finalization import missing_sections
    return missing_sections(visit, workflow)


@login_required
@require_POST
@never_cache
def poli_workflow_draft(request, pk, step):
    require_poli_rollout()
    if request.content_type != 'application/json':
        return JsonResponse({'success': False, 'error': 'Gunakan JSON.'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get('fields'), dict) or 'version' not in data:
            raise ValueError('Payload harus berisi fields dan version.')
        if set(data) - {'fields', 'version'}:
            raise ValueError('Atribut payload tidak valid.')
        workflow = save_step(
            pk, request.user, step, data['fields'], data['version'],
            service_line=RAJAL_JANTUNG_SERVICE_LINE,
        )
    except WorkflowConflict as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=409)
    except WorkflowValidation as exc:
        return JsonResponse({'success': False, 'error': str(exc), 'fields': exc.errors}, status=400)
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': 'Payload atau nilai field tidak valid.'}, status=400)
    return JsonResponse({
        'success': True,
        'version': workflow.version,
        'values': (workflow.draft_payload or {}).get(str(step), {}),
        'saved_at': workflow.updated_at.isoformat(),
        'step': workflow.last_step,
    })


@login_required
@require_POST
@never_cache
def poli_workflow_action(request, pk):
    require_poli_rollout()
    from .services.igd_actions import perform_action
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict) or set(body) - {'operation', 'fields', 'version', 'request_id'}:
            raise ValueError('body')
        result = perform_action(
            pk, request.user, body.get('operation'), body.get('fields'), body.get('version'),
            body.get('request_id'), service_line=RAJAL_JANTUNG_SERVICE_LINE,
        )
    except WorkflowConflict as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=409)
    except WorkflowValidation as exc:
        return JsonResponse({'success': False, 'error': str(exc), 'fields': exc.errors}, status=400)
    except (ValueError, TypeError, UnicodeDecodeError):
        return JsonResponse({'success': False, 'error': 'Payload aksi tidak valid.'}, status=400)
    except ValidationError as exc:
        return JsonResponse({'success': False, 'error': ' '.join(exc.messages)}, status=400)
    except ObjectDoesNotExist:
        return JsonResponse({'success': False, 'error': 'Objek tidak ditemukan pada lingkup ini.'}, status=404)
    return JsonResponse({'success': True, **result})
