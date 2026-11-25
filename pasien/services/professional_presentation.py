"""Snapshot-only readers and bounded presentation data for step 9."""
from django.conf import settings
from copy import deepcopy
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from .professional_cppt import FIELDS,note_snapshot,verification_state_at,VERIFICATION_LABELS
from .professional_billing import professional_billing_summary
from pasien.workflow_schemas import KELUHAN_CPPT_LABELS,KEPATUHAN_TERAPI_LABELS

LABELS={'subjektif':'S — Subjektif','objektif':'O — Objektif','asesmen':'A — Asesmen','plan':'P — Rencana','asesmen_gizi':'Asesmen gizi','diagnosis_gizi':'Diagnosis gizi','intervensi':'Intervensi','monitoring':'Monitoring','evaluasi':'Evaluasi','kondisi_psikospiritual':'Kondisi psikospiritual','pendampingan':'Pendampingan','respon_pasien':'Respons pasien'}


def snapshot_professional_care(visit):
    notes=[]
    for note in visit.cppt.order_by('pk').prefetch_related('care_revisions__verification'):
        entry=note_snapshot(note)
        revision=next((r for r in note.care_revisions.all() if r.version==note.version),None)
        verification=getattr(revision,'verification',None) if revision else None
        entry.update(author_name=note.nama_ppa,profession=note.profesi,
                     verification={'verifier_id':verification.verifier_id,'verifier_name':verification.verifier_name,'at':verification.performed_at.isoformat(),'digest':verification.digest,'assignment_id':verification.assignment_id,'assignment_snapshot':verification.assignment_snapshot} if verification else None,
                     historical_unattributed=note.status=='LEGACY' and note.verifikasi_dpjp)
        notes.append(entry)
    return {'notes':notes,'billing':professional_billing_summary(visit),
            'actions':list(visit.tindakan_asesmen.order_by('pk').values('id','nama','execution_status','quantity','professional_service_id','professional_snapshot','price_snapshot','financial_status','execution_cppt_id','billing_item_id','performed_at','recorded_at')),
            'charges':list(visit.billing.order_by('pk').values('id','nama_item','kuantitas','harga_satuan','is_void','professional_price_snapshot')),
            'voids':list(visit.billing.filter(void_record__isnull=False).values('id','void_record__amount','void_record__reason','void_record__actor_id','void_record__created_at'))}


def professional_panel_context(visit,workflow,actor,revision=None):
    from pasien.models import PenugasanDpjpEpisode
    from sdm.services.professional_care import has_grant
    from .professional_execution import _professional_rollout
    from .professional_cppt import verification_state,VERIFICATION_LABELS
    enabled=_professional_rollout(visit,workflow)
    historical=bool(workflow and workflow.status=='FINAL' and revision)
    data=deepcopy(revision.snapshot.get('professional_care',{})) if historical else snapshot_professional_care(visit)
    if historical and 'professional_care' not in revision.snapshot:
        data={'actions':deepcopy(revision.snapshot.get('actions',[])),'notes':[{'id':row.get('id'),'format_code':'SOAP','status':'LEGACY','version':None,'author_name':row.get('nama_ppa',''),
                       'actual_at':row.get('tanggal'),'recorded_at':None,'author_id':row.get('created_by_id'),'professional_snapshot':{},
                       'content':{key:row.get(key,'') for key in FIELDS['SOAP']},'verification':None,'historical_unattributed':bool(row.get('verifikasi_dpjp'))}
                      for row in revision.snapshot.get('cppt',[])]}
    show=historical or enabled or bool(data.get('actions') and any(row.get('professional_service_id') for row in data['actions'])) or any(note.get('status')!='LEGACY' for note in data.get('notes',[]))
    # F6.1: jalur RAJAL_JANTUNG ikut dapat menulis CPPT profesional. Episode
    # rawat jalan lain tetap tertutup karena ``_writable`` menolaknya.
    rajal_line=bool(workflow and workflow.service_line=='RAJAL_JANTUNG')
    writable_visit=visit.jenis_kunjungan=='IGD' or (visit.jenis_kunjungan=='RAJAL' and rajal_line)
    editable=enabled and writable_visit and visit.status not in {'PULANG','RUJUK','MENINGGAL','BATAL'} and not historical and actor.profile.role!='ASESOR'
    today=timezone.localdate()
    dpjp=editable and PenugasanDpjpEpisode.objects.filter(visit=visit,doctor=actor,unit_id=visit.unit_kerja_id,is_active=True,valid_from__lte=today,valid_until__gte=today).exists()
    for note in data.get('notes',[]):
        reasons=note.get('content',{}).get('unavailable_reasons',{})
        note['fields']=[{'key':key,'label':LABELS[key],'value':note.get('content',{}).get(key) or ('Tidak tercatat: '+reasons[key] if reasons.get(key) else 'Belum tercatat')} for key in FIELDS.get(note.get('format_code'),FIELDS['SOAP'])]
        note['can_edit']=editable and note.get('author_id')==actor.pk and note.get('status')!='LEGACY'
        note['can_verify']=bool(dpjp and note.get('status')=='SIGNED' and not note.get('verification'))
        # F6.5: status kepatuhan 24 jam dihitung dari verifikasi_due_at vs
        # performed_at — tidak ada kolom status di basis data.
        _state = _note_proxy(note)
        note['verification_state']=verification_state_at(_state['due'], _state['performed_at'])
        note['verification_state_label']=VERIFICATION_LABELS.get(note['verification_state'],'')
        note['chips']=[{'code':code,'label':KELUHAN_CPPT_LABELS.get(code,code)} for code in note.get('content',{}).get('keluhan_chips',[])]
        note['kepatuhan_label']=KEPATUHAN_TERAPI_LABELS.get(note.get('content',{}).get('kepatuhan_terapi',''),'')
        note['kepatuhan_obat']=note.get('content',{}).get('kepatuhan_obat',{})
        note['has_tte']=bool(note.get('ttd_hash'))
    can_void=bool(editable and has_grant(actor,visit,'VOID_UNPAID_CHARGE',at=timezone.now()))
    return {'professional_show':show,'professional_enabled':enabled,'professional_can_edit':editable,
            'professional_data':data,'professional_notes':data.get('notes',[]),'professional_totals':data.get('billing'),
            'professional_can_void':can_void,'professional_note_formats':[{'code':code,'fields':[{'key':key,'label':LABELS[key]} for key in fields]} for code,fields in FIELDS.items()]}


def _note_proxy(note):
    """Nilai pembanding untuk ``verification_state_at`` dari catatan snapshot."""
    from django.utils.dateparse import parse_datetime

    due = note.get('verifikasi_due_at')
    at = (note.get('verification') or {}).get('at')
    return {
        'due': parse_datetime(due) if isinstance(due, str) else due,
        'performed_at': parse_datetime(at) if isinstance(at, str) else at,
    }


# ── F6.2–F6.8: data Langkah 9 (CPPT multiprofesi & billing) ───────────────────
#
# Seluruh daftar di bawah berasal dari matriks (``workflow_schemas``), katalog
# (``KasusTindakan`` kelompok episode), atau rekam episode itu sendiri. Tidak
# ada keluhan, status kepatuhan, kode tindakan, atau ambang yang dikarang di
# sini; yang tidak tersedia dinyatakan tidak tersedia.

#: Kolom TTV yang ditampilkan O otomatis (matriks S9-L1-11).
CPPT_VITAL_KEYS = (
    ('ttv_sistole', 'TD sistolik'), ('ttv_diastole', 'TD diastolik'),
    ('ttv_nadi', 'Nadi'), ('ttv_rr', 'RR'), ('ttv_suhu', 'Suhu'),
    ('ttv_spo2', 'SpO₂'), ('berat_badan', 'BB'),
)


def latest_vitals(visit, workflow=None):
    """TTV terbaru episode + MAP terhitung (S9-L1-11).

    Jalur RAJAL_JANTUNG menyimpan TTV di ``draft_payload`` langkah 4 (ADR-9),
    bukan kolom ``KunjunganPasien``. Jalur IGD memakai kolom model. Sumbernya
    dipilih dari jalur layanan, bukan ditebak dari nilai yang kebetulan ada.
    """
    from pasien.models import hitung_map

    if workflow is not None and workflow.service_line == 'RAJAL_JANTUNG':
        step4 = (workflow.draft_payload or {}).get('4') or {}
        values = {key: step4.get(key) for key, _label in CPPT_VITAL_KEYS}
        source = 'draft_payload.4'
    else:
        values = {key: getattr(visit, key, None) for key, _label in CPPT_VITAL_KEYS}
        source = 'kunjungan'
    rows = [
        {'key': key, 'label': label, 'value': values.get(key)}
        for key, label in CPPT_VITAL_KEYS if values.get(key) not in (None, '')
    ]
    return {
        'rows': rows,
        'source': source,
        'map': hitung_map(values.get('ttv_sistole'), values.get('ttv_diastole')),
        'measured_at': (workflow.updated_at.isoformat()
                        if source == 'draft_payload.4' and workflow.updated_at else None),
    }


def recent_investigations(visit, limit=3):
    """Tiga hasil penunjang terakhir yang sudah selesai (S9-L1-13)."""
    rows = (
        visit.order_penunjang
        .filter(status='SELESAI')
        .order_by('-created_at', '-pk')
        .values('id', 'nama_pemeriksaan', 'jenis', 'hasil_pemeriksaan',
                'interpretasi', 'lvef', 'is_critical_value', 'created_at')[:limit]
    )
    return [
        {**row, 'created_at': row['created_at'].isoformat() if row['created_at'] else None}
        for row in rows
    ]


def marked_anatomy(visit):
    """Penanda anatomi bertanda milik episode (S9-L1-14, langkah 6)."""
    return list(visit.penanda_anatomi or [])


def cppt_objective_default(visit, workflow=None):
    """Teks awal komponen O — bukan input manual (F6.2).

    Dibangun dari tiga sumber yang sudah tercatat: TTV terbaru + MAP, ringkasan
    hasil penunjang terakhir, dan penanda anatomi. Bagian yang belum ada
    disebut apa adanya, bukan dikosongkan tanpa keterangan.
    """
    vitals = latest_vitals(visit, workflow)
    lines = []
    if vitals['rows']:
        parts = [f'{row["label"]} {row["value"]}' for row in vitals['rows']]
        if vitals['map'] is not None:
            parts.append(f'MAP {vitals["map"]} mmHg')
        lines.append('TTV terbaru: ' + '; '.join(parts) + '.')
    else:
        lines.append('TTV terbaru belum tercatat.')
    results = recent_investigations(visit)
    if results:
        lines.append('Penunjang terakhir:')
        for row in results:
            summary = (row['interpretasi'] or row['hasil_pemeriksaan'] or '').strip()
            suffix = f' — {summary}' if summary else ' — hasil belum diinterpretasi'
            critical = ' [NILAI KRITIS]' if row['is_critical_value'] else ''
            lvef = f' (LVEF {row["lvef"]}%)' if row['lvef'] is not None else ''
            lines.append(f'- {row["nama_pemeriksaan"]}{lvef}{suffix}{critical}')
    else:
        lines.append('Belum ada hasil penunjang selesai.')
    markers = marked_anatomy(visit)
    if markers:
        lines.append('Penanda anatomi: ' + '; '.join(
            f'{marker.get("label") or marker.get("kind", "penanda")} '
            f'({marker.get("side", "-")}, x={marker.get("x")}, y={marker.get("y")})'
            for marker in markers
        ) + '.')
    else:
        lines.append('Belum ada penanda anatomi bertanda.')
    return '\n'.join(lines)


def active_drugs(visit):
    """Obat aktif pasien untuk penandaan kepatuhan (S9-L1-10).

    Definisi yang dipakai adalah definisi rencana F8.4: obat aktif = baris
    resep dari resep **terakhir berstatus SELESAI**. Bila belum ada resep
    selesai, daftar kosong dan panel menyebut sebabnya — formularium yang belum
    diaktifkan tidak ditambal dengan obat karangan.
    """
    resep = (
        visit.resep_list
        .filter(status='SELESAI')
        .prefetch_related('items')
        .order_by('-tanggal_resep', '-pk')
        .first()
    )
    if resep is None:
        return {'resep': None, 'items': [], 'reason': 'Belum ada resep berstatus selesai untuk episode ini.'}
    return {
        'resep': resep,
        'items': [
            {'id': item.pk, 'nama': item.nama_obat, 'dosis': item.dosis,
             'aturan_pakai': item.aturan_pakai}
            for item in resep.items.order_by('pk')
        ],
        'reason': '',
    }


def step9_context(visit, workflow, actor, revision=None):
    """Data Langkah 9: O otomatis, chip S, kepatuhan, tindakan, TTE, panel kanan."""
    from pasien.asesmen_tindakan import tindakan_poli_options
    from pasien.workflow_schemas import (
        KELUHAN_CPPT_CHOICES, KELUHAN_CPPT_LABELS,
        KEPATUHAN_TERAPI_CHOICES, KEPATUHAN_TERAPI_LABELS,
    )
    from .poli_rbac import DPJP, authorize_step, resolve_role

    panel = professional_panel_context(visit, workflow, actor, revision)
    role = resolve_role(actor, visit)
    drugs = active_drugs(visit)
    can_fill = False
    try:
        authorize_step(actor, visit, 9, 'fill')
        can_fill = True
    except PermissionDenied:
        can_fill = False
    return {
        **panel,
        'cppt_vitals': latest_vitals(visit, workflow),
        'cppt_objective_default': cppt_objective_default(visit, workflow),
        'cppt_investigations': recent_investigations(visit),
        'cppt_markers': marked_anatomy(visit),
        'keluhan_choices': [
            {'code': code, 'label': KELUHAN_CPPT_LABELS[code]}
            for code in KELUHAN_CPPT_CHOICES
        ],
        'kepatuhan_choices': [
            {'code': code, 'label': KEPATUHAN_TERAPI_LABELS[code]}
            for code in KEPATUHAN_TERAPI_CHOICES
        ],
        'active_drugs': drugs['items'],
        'active_drugs_reason': drugs['reason'],
        'active_resep_id': drugs['resep'].pk if drugs['resep'] else None,
        'tindakan_options': tindakan_poli_options(visit),
        'tindakan_lines': list(
            visit.tindakan_asesmen.order_by('pk').values(
                'id', 'kode', 'nama', 'execution_status', 'execution_team',
                'quantity', 'tarif_acuan', 'financial_status', 'billing_item_id',
                'standard_item__code', 'ep_status',
            )
        ),
        'pelaksana_choices': [
            {'code': 'DOKTER', 'label': 'Dokter'},
            {'code': 'PERAWAT', 'label': 'Perawat'},
        ],
        'pelaksana_unavailable': [
            {'code': 'NAKES_LAIN', 'label': 'Nakes Lain',
             'reason': 'Belum punya nilai pada TindakanAsesmen.execution_team.'},
        ],
        'can_fill_step9': can_fill,
        'can_verify_step9': role == DPJP,
        'cppt_services': actor_services(actor, visit),
        'right_panel': right_panel_context(visit, workflow),
    }


def right_panel_context(visit, workflow):
    """Panel kanan (S9-L2-03): regulasi, consent, brosur, unggahan pendukung.

    Regulasi dibaca dari perpustakaan bukti akreditasi yang **sudah ada**:
    ``EvidenceFile`` dengan ``EvidenceReq.category_type='R'`` (SK, Pedoman,
    SPO) berstatus ``VALID``. Tidak ada perpustakaan dokumen baru yang dibuat
    untuk ini.
    """
    from akreditasi.models import EvidenceFile

    regulations = list(
        EvidenceFile.objects
        .filter(requirement__category_type='R', status='VALID')
        .select_related('requirement')
        .order_by('requirement__standard_item__code', 'requirement_id', '-uploaded_at')
        .values('id', 'file_name', 'version', 'uploaded_at',
                'requirement__title', 'requirement__standard_item__code')
    )
    for row in regulations:
        row['uploaded_at'] = row['uploaded_at'].isoformat() if row['uploaded_at'] else None
    values = (workflow.draft_payload or {}).get('9', {}) if workflow else {}
    return {
        'regulations': regulations,
        'consent_actions': list(
            visit.tindakan_asesmen.order_by('pk').values('id', 'kode', 'nama')
        ),
        'consent_patient': {
            'nama': visit.pasien.nama_lengkap,
            'no_rm': visit.pasien.no_rm,
            # Nilai mentah: field ini hanya dirender (``|date``), dan bentuk
            # ``date``/``str`` keduanya harus lolos tanpa konversi khusus.
            'tanggal_lahir': visit.pasien.tanggal_lahir,
            'alamat': visit.pasien.alamat or '',
        },
        'edukasi_codes': values.get('edukasi') or [],
        'attachments': list(
            visit.lampiran_asesmen.order_by('-diunggah_pada').values(
                'id', 'nama_asli', 'jenis', 'ukuran', 'diunggah_pada'),
        ),
        'upload_limits': {'max_bytes': 10 * 1024 * 1024,
                          'extensions': ['.pdf', '.png', '.jpg', '.jpeg']},
    }


def actor_services(actor, visit):
    """Layanan profesional yang dapat dipakai akun ini pada episode ini.

    Filter sama dengan pemilih layanan IGD (``professional_views.
    igd_professional_catalogue``): pemetaan kewenangan untuk jenjang pegawai
    terverifikasi, ditambah grant layanan pendukung. Kewenangan efektif tetap
    diperiksa ulang oleh ``resolve_professional_context`` saat menyimpan.
    """
    from django.db.models import Q
    from klinis.models import LayananProfesional, ProfessionalCareGrant
    from sdm.models import Pegawai

    grades = list(
        Pegawai.objects
        .filter(akun=actor, status='AKTIF', akun__is_active=True,
                jenjang_master__isnull=False)
        .values_list('jenjang_master_id', flat=True)[:2]
    )
    support = ProfessionalCareGrant.objects.filter(
        user=actor, unit_id=visit.unit_kerja_id, capability='SUPPORT_SERVICE', is_active=True,
    ).values('service_id')
    if not grades and not support:
        return []
    return list(
        LayananProfesional.objects
        .filter(
            Q(authority_mappings__catalog_item__jenjang_id__in=grades,
              authority_mappings__is_active=True) | Q(pk__in=support),
            is_active=True, reviewed_by__isnull=False, reviewed_at__isnull=False,
        )
        .exclude(source_version='')
        .distinct().order_by('code')
        .values('id', 'code', 'name', 'group', 'note_format')
    )
