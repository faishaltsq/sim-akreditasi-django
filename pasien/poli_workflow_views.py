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
        'fields': [
            {'name': item.name, 'kind': item.kind, 'label': item.label or item.name,
             'choices': item.choices, 'minimum': item.minimum, 'maximum': item.maximum,
             'value': values.get(item.name, '')}
            for item in spec.fields
        ],
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
    })


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
