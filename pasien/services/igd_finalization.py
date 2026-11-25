"""Tanda tangan, disposisi dan revisi append-only episode IGD."""
import copy
import json
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.forms_igd_workflow import snapshot_visit_fields
from pasien.forms_igd_operations import SignatureForm, FinalizationForm, AddendumForm, RajalFinalizationForm
from pasien.models import Bed, IgdAssessmentRevision, DischargeRecord, POLIKLINIK_CHOICES
from pasien.workflow_schemas import (
    DISPOSISI_RAJAL_CHOICES, KONDISI_AKHIR_RAJAL_CHOICES,
    KONDISI_AKHIR_TO_KONDISI_PULANG, RAJAL_JANTUNG_STEP_NUMBERS,
    validate_disposisi_rajal,
)
from .igd_actions import validate, digest, require_doctor, DOCTORS, NURSES
from .igd_assessment_workflow import RAJAL_JANTUNG_SERVICE_LINE, WorkflowConflict, WorkflowValidation
from .poli_completeness import step_minimally_filled
from .poli_rbac import require_dpjp

EXEMPTIONS = {'triage','anamnesis','primary_survey','initial_vitals','screening','physical_exam','diagnosis','nursing','investigations','care','evaluation'}
#: Kunci pengecualian langkah RAJAL_JANTUNG (``step_1`` … ``step_10``).
RAJAL_EXEMPTIONS = frozenset(f'step_{number}' for number in RAJAL_JANTUNG_STEP_NUMBERS)

def _is_rajal(workflow):
    return workflow is not None and workflow.service_line == RAJAL_JANTUNG_SERVICE_LINE


def clinical_snapshot(visit, workflow):
    fields = snapshot_visit_fields()
    patient = {key:getattr(visit.pasien,key) for key in ('no_rm','nama_lengkap','tanggal_lahir','jenis_kelamin')}
    snapshot = {
        'schema_version':2, 'patient':patient,
        'visit':{name:getattr(visit,name) for name in fields},
        'no_kunjungan':visit.no_kunjungan, 'origin_unit_id':workflow.origin_unit_id,
        'diagnosis_provenance':visit.diagnosis_provenance, 'exemptions':workflow.exemptions,
        'diagnoses':list(visit.diagnoses.order_by('pk').values('id','kode','nama','mode','active','is_primary','provenance','updated_by_id','created_at','updated_at')),
        'observations':list(workflow.observations.order_by('pk').values('id','phase','observed_at','recorded_by_id','data','corrects_id')),
        'orders':list(visit.order_penunjang.order_by('pk').values('id','jenis','nama_pemeriksaan','prioritas','status','hasil_pemeriksaan','is_critical_value','critical_value_catatan','catalogue_snapshot','preparation','ordered_by_id','created_at','catatan_klinis','dokter_pengirim','destination_id','result_recorded_by_id','result_recorded_at','batch_id')),
        'cppt':list(visit.cppt.order_by('pk').values('id','profesi','nama_ppa','tanggal','subjektif','objektif','asesmen','plan','created_by_id','verifikasi_dpjp')),
        'actions':list(visit.tindakan_asesmen.order_by('pk').values('id','jenis','kode','nama','execution_status','execution_team','performed_by_id','performed_at','quantity','tarif_acuan','tarif','catatan_tarif','billing_item_id','standard_item_id','ep_status','ep_catatan','lokasi_anatomis','catatan_klinis','recorded_at','assistance_provenance')),
        'prescriptions':[{'id':rx.pk,'no_resep':rx.no_resep,'doctor_id':rx.dokter_peresep_id,'items':list(rx.items.order_by('pk').values('nama_obat','aturan_pakai','product_snapshot','regimen','quantity_decimal','reference_price','quantity_reason','kind'))} for rx in visit.resep_list.order_by('pk')],
        'attachments':list(visit.lampiran_asesmen.order_by('pk').values('id','jenis','nama_asli','file','diunggah_pada','diunggah_oleh_id')),
    }
    if _is_rajal(workflow):
        # ADR-9 butir 4: digest tanda tangan wajib mencakup nilai JSON yang diisi
        # klinisi. Bentuk snapshot rajal karena itu berbeda (schema_version 3);
        # snapshot IGD tetap schema_version 2 tanpa draft_payload.
        snapshot['schema_version'] = 3
        snapshot['draft_payload'] = workflow.draft_payload or {}
    if getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False) or visit.cppt.exclude(status='LEGACY').exists():
        from .professional_presentation import snapshot_professional_care
        snapshot['professional_care']=snapshot_professional_care(visit)
    return json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))


def sign(visit, workflow, user, data):
    values = validate(SignatureForm, data)
    section = values['section']
    if _is_rajal(workflow):
        # ADR-11: hanya DPJP yang menandatangani penutupan klinis rawat jalan.
        require_dpjp(user, visit)
        if section != 'MEDIS':
            raise PermissionDenied('Tanda tangan asesmen POLI-JANTUNG hanya oleh DPJP (bagian medis).')
    elif section == 'MEDIS':
        require_doctor(user)
    elif user.profile.profesi not in NURSES:
        raise PermissionDenied('Tanda tangan keperawatan hanya untuk perawat/bidan.')
    exemptions = values['exemptions']
    if exemptions is not None:
        allowed = RAJAL_EXEMPTIONS if _is_rajal(workflow) else EXEMPTIONS
        if not isinstance(exemptions,dict) or set(exemptions) - allowed or any(not isinstance(v,str) or not 5 <= len(v.strip()) <= 2000 for v in exemptions.values()):
            raise WorkflowValidation({'exemptions':['Gunakan objek alasan minimal lima karakter per bagian yang tidak dapat dinilai.']})
        if section != 'MEDIS' and exemptions != workflow.exemptions:
            raise PermissionDenied('Perubahan pengecualian episode memerlukan dokter.')
        if workflow.exemptions != exemptions:
            workflow.exemptions = exemptions
            workflow.signatures = {}
    signature = {'user_id':user.pk, 'name':user.get_full_name() or user.username,
                 'profession':user.profile.profesi, 'signed_at':timezone.now().isoformat(),
                 'content_digest':digest(clinical_snapshot(visit,workflow))}
    workflow.signatures = {**workflow.signatures, section:signature}
    return {'signed_section':section}


def missing_rajal_sections(workflow):
    """Kelengkapan episode RAJAL_JANTUNG: tiap langkah wajib punya satu nilai.

    Sengaja **tidak** memakai ``physical_exam.exam_present`` — pemeriksaan fisik
    IGD bertingkat per regio, sedangkan kerangka rajal (F1) belum punya bentuk
    itu. Kelengkapan di sini berarti "setiap langkah punya minimal satu nilai
    terisi" (predikat bersama ``poli_completeness.step_minimally_filled``,
    F8.2), ditambah kondisi akhir wajib pada langkah 10. F2/F3 dapat
    memperketat pemeriksaan per langkah tanpa mengubah kontrak ini.
    """
    draft = workflow.draft_payload or {}
    exemptions = workflow.exemptions or {}
    missing = []
    for number in RAJAL_JANTUNG_STEP_NUMBERS:
        key = f'step_{number}'
        if key in exemptions:
            continue
        if not step_minimally_filled(draft.get(str(number))):
            missing.append(key)
    if not (draft.get('10') or {}).get('kondisi_akhir_rajal') and 'step_10' not in exemptions and 'step_10' not in missing:
        missing.append('step_10')
    elif (draft.get('10') or {}).get('disposisi') not in DISPOSISI_RAJAL_CHOICES and 'step_10' not in exemptions and 'step_10' not in missing:
        # F7.2: penutupan episode selalu punya satu cabang disposisi; tanpa itu
        # dokumen pulang/rawat inap/rujukan tidak dapat ditentukan.
        missing.append('step_10')
    return missing

def missing_sections(visit, workflow):
    if _is_rajal(workflow):
        return missing_rajal_sections(workflow)
    from pasien.physical_exam import exam_present
    def measured(phase):
        observation = workflow.observations.filter(phase=phase).order_by('-observed_at','-pk').first()
        return bool(observation and any(value is not None and value != '' for value in observation.data.values()))
    checks = {
        'triage': bool(visit.triase_skala and (visit.triase_kategori or visit.triage)),
        'anamnesis': bool(visit.anamnesis_rps.strip()),
        'primary_survey': bool(visit.fisik_airway.strip()),
        'initial_vitals': measured('INITIAL'),
        'screening': bool(visit.skrining_alergi_status not in ('','BELUM') and visit.skrining_gizi_mst is not None and visit.skrining_jatuh_skor is not None),
        'physical_exam': exam_present(visit.fisik_head_to_toe,visit.secondary_survey_detail,visit.fisik_lokalis),
        'diagnosis': bool(visit.diagnosa_masuk.strip()),
        'nursing': bool(visit.diagnosa_keperawatan_sdki.strip() and visit.luaran_keperawatan_slki.strip() and visit.intervensi_keperawatan_siki.strip()),
        'investigations':visit.order_penunjang.exists(),
        'care':visit.cppt.filter(status='SIGNED').exists() if getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False) else visit.cppt.exists(),
        'evaluation':bool(visit.disposisi_kondisi_akhir and visit.evaluasi_respon_terapi.strip() and measured('EVALUATION')),
    }
    return [name for name,present in checks.items() if not present and name not in workflow.exemptions]


def _release_bed(visit):
    if visit.bed_id:
        bed = Bed.objects.select_for_update().get(pk=visit.bed_id)
        bed.status = 'STERILISASI'
        bed.save(update_fields=['status'])
        visit.bed = None


def apply_disposition(visit, user, values):
    outcome = values['outcome']
    now = timezone.now()
    if outcome == 'NONE':
        return
    expected = {'PULANG':'RAWAT_JALAN','PAPS':'PAPS','RANAP':'RAWAT_INAP','RUJUK':'RUJUK','CONSULT':'KONSUL','TRANSFER':'TRANSFER','MENINGGAL':'MENINGGAL'}[outcome]
    if visit.disposisi_tindak_lanjut != expected:
        raise WorkflowValidation({'outcome':['Simpan rencana disposisi yang sesuai pada langkah 11 sebelum finalisasi.']})
    if outcome in ('PULANG','PAPS'):
        if outcome == 'PAPS' and not (values['paps_alasan'] and values['paps_nama_penolak']):
            raise WorkflowValidation({'paps_alasan':['Alasan dan nama penolak wajib untuk PAPS.']})
        visit.discharge_patient(kondisi='APS' if outcome == 'PAPS' else 'MEMBAIK', resume=values['resume'],
                                user=user, edukasi=values['edukasi'], obat=values['obat'], kontrol=values['kontrol'])
        record = visit.discharge
        record.status_clearance = 'PROSES'
        record.paps_alasan, record.paps_nama_penolak = values['paps_alasan'], values['paps_nama_penolak']
        record.save()
    elif outcome == 'RANAP':
        bed = Bed.objects.select_for_update().select_related('ruangan').filter(pk=values['bed_id']).first()
        if bed is None or bed.status != 'TERSEDIA' or not bed.ruangan.unit_kerja_id or not values['dpjp']:
            raise WorkflowValidation({'bed_id':['Pilih bed tersedia dengan unit tujuan dan DPJP yang jelas.']})
        visit.admit_to_ranap(bed, dpjp=values['dpjp'])
        visit.unit_kerja_id = bed.ruangan.unit_kerja_id
    elif outcome in ('CONSULT','TRANSFER'):
        poli = visit.disposisi_kontrol_poli
        if poli not in dict(POLIKLINIK_CHOICES):
            raise WorkflowValidation({'disposisi_kontrol_poli':['Pilih poli tujuan yang valid.']})
        visit.konsul_ke_poli = poli
        visit.konsul_catatan = values['resume']
        if outcome == 'TRANSFER':
            from akreditasi.layanan_unit import POLI_UNIT_CODE
            from pasien.services.antrean import allocate_queue_number
            unit = UnitKerja.objects.filter(code=POLI_UNIT_CODE.get(poli)).first()
            if unit is None:
                raise WorkflowValidation({'disposisi_kontrol_poli':['Unit poli tujuan belum dikonfigurasi.']})
            visit.jenis_kunjungan, visit.status, visit.poliklinik = 'RAJAL','DAFTAR',poli
            visit.unit_kerja = unit
            visit.nomor_antrean = allocate_queue_number('RAJAL', poli)
            visit.status_antrean = 'MENUNGGU'
        else:
            visit.status = 'DISPOSISI'
    else:
        if outcome == 'RUJUK':
            if not visit.disposisi_rujuk_rs.strip() or not visit.disposisi_rujuk_alasan.strip():
                raise WorkflowValidation({'disposisi_rujuk_rs':['RS dan alasan rujukan wajib.']})
            visit.status = 'RUJUK'
            visit.sisrute_rs_tujuan, visit.sisrute_alasan = visit.disposisi_rujuk_rs, visit.disposisi_rujuk_alasan
        else:
            if not visit.waktu_kematian or visit.waktu_kematian > now or not visit.penyebab_kematian.strip():
                raise WorkflowValidation({'waktu_kematian':['Waktu kematian yang valid dan keterangan penyebab wajib diisi.']})
            visit.status = 'MENINGGAL'
        _release_bed(visit)
        visit.tanggal_keluar = visit.waktu_kematian if outcome == 'MENINGGAL' else now
        DischargeRecord.objects.create(kunjungan=visit, tanggal_discharge=visit.tanggal_keluar,
            kondisi_pulang='MENINGGAL' if outcome == 'MENINGGAL' else 'RUJUK', resume_medis=values['resume'],
            status_clearance='PROSES', dibuat_oleh=user,
            total_tagihan=sum((b.subtotal for b in visit.billing.all()),0))
    if outcome not in ('TRANSFER','CONSULT'):
        visit.status_antrean = 'SELESAI'
    visit.save()


def _planned_kontrol(visit):
    """Tanggal kontrol yang sudah diterbitkan Langkah 8 (F5.6), bila ada.

    ``discharge_patient`` memakai ``update_or_create`` sehingga kolom
    ``jadwal_kontrol`` akan dikosongkan bila form finalisasi tidak mengisinya.
    SKDP yang sudah terbit tidak boleh hilang karena itu; tanggal rencananya
    dipertahankan sampai ada nilai pengganti.
    """
    record = getattr(visit, 'discharge', None)
    if record is None or not record.skdp_nomor:
        return None
    return record.jadwal_kontrol

#: S10-L2-01 → ``InsidenKeselamatan.jenis_insiden``. Hanya dua opsi matriks
#: yang punya padanan langsung di model insiden yang sudah ada; "Risiko
#: Kepatuhan / Alur Pelayanan Tercatat" belum punya jenis padanan (AMBIGU-22),
#: sehingga nilainya tetap tersimpan di ``draft_payload`` tetapi tidak membuat
#: baris insiden dengan jenis karangan.
INSIDEN_JENIS_MAP = {'KNC': 'KNC', 'KTD_SENTINEL': 'KTD'}

#: Indikator PDCA unit yang diumpan F7.7 (dibuat oleh
#: ``seed_poli_jantung_ep``). Bila baris tidak ada, pengumpanan dilewati —
#: definisi indikator tidak pernah dikarang di kode.
INDIKATOR_WAKTU_TUNGGU = 'IMU-POLJAN-01'
INDIKATOR_NILAI_KRITIS = 'IMU-POLJAN-02'
#: Batas SLA dari matriks §7 ("Waktu tunggu pelayanan rawat jalan <= 60 menit").
WAIT_MINUTES_TARGET = 60
#: Batas SLA dari matriks §7 ("Lapor nilai kritis ke DPJP <= 30 menit").
CRITICAL_MINUTES_TARGET = 30

def _rajal_documents(disposition):
    """Dokumen per cabang disposisi — semuanya memakai pencetak yang sudah ada."""
    return {
        'PULANG': ('pasien:resume_pdf', 'pasien:cetak_skdp', 'pasien:poli_edukasi_pdf'),
        'RAWAT_INAP': ('pasien:cetak_spri', 'pasien:cetak_general_consent'),
        'RUJUK_ANTAR_POLI': ('pasien:resume_pdf',),
        'RUJUK_KELUAR': ('pasien:resume_pdf',),
    }[disposition]

def _record_incident(visit, workflow, user, now):
    """S10-L2-01 → satu baris ``InsidenKeselamatan`` untuk episode ini.

    Idempoten: kunci ``kunjungan`` (FK aditif) memastikan satu episode hanya
    punya satu laporan otomatis, walau finalisasi diulang setelah addendum.
    """
    from akreditasi.risiko_models import InsidenKeselamatan

    pilihan = (workflow.draft_payload or {}).get('10', {}).get('insiden_keselamatan')
    jenis = INSIDEN_JENIS_MAP.get(pilihan)
    if not jenis:
        return None
    unit = visit.unit_kerja or workflow.origin_unit
    row, _created = InsidenKeselamatan.objects.get_or_create(
        kunjungan=visit,
        defaults={
            'unit': unit,
            'tanggal_kejadian': timezone.localdate(now),
            'waktu_kejadian': timezone.localtime(now).time().replace(microsecond=0),
            'jenis_insiden': jenis,
            # Keparahan tidak ditetapkan matriks untuk laporan otomatis;
            # nilai paling rendah yang tersedia dipakai agar baris tetap sah
            # tanpa mengarang grading klinis.
            'tingkat_keparahan': 'TIDAK_CEDERA' if jenis == 'KNC' else 'MODERAT',
            'lokasi_kejadian': f'Poli Jantung — {visit.no_kunjungan}',
            'deskripsi_kejadian': (
                f'Laporan otomatis Langkah 10 (S10-L2-01): {pilihan} '
                f'pada kunjungan {visit.no_kunjungan}.'
            ),
            'pasien_terpapar': jenis != 'KNC',
            'pelapor_anonim': False,
        },
    )
    return row

def _record_ep_evidence(visit, workflow, user, now):
    """F7.5 — bukti EP asesmen sebagai baris ``KorelasiEpAsesmen``.

    Aturan datang dari tabel ``AturanEpAsesmen`` (ADR-7); kode Python tidak
    memuat satu pun sub-standar. Status diturunkan dari kontrak kelengkapan
    yang sama dengan gerbang finalisasi: episode yang lolos finalisasi adalah
    episode lengkap, sehingga setiap aturan wajib berstatus TERPENUHI.
    """
    from akreditasi.models import StandardItem
    from klinis.models import AturanEpAsesmen
    from pasien.models import KorelasiEpAsesmen

    complete = not missing_rajal_sections(workflow)
    rows = []
    rules = AturanEpAsesmen.objects.filter(
        layanan__in=('', RAJAL_JANTUNG_SERVICE_LINE), wajib=True,
    ).order_by('urutan', 'sub_standard')
    for rule in rules:
        item = StandardItem.objects.filter(sub_standard=rule.sub_standard).first()
        if item is None:
            # Resolver ADR-7: aturan yang menunjuk sub-standar di luar katalog
            # aktif dibuang, bukan ditautkan ke EP karangan.
            continue
        status = 'TERPENUHI' if complete else 'BELUM'
        catatan = (
            f'{rule.label} — bukti: asesmen 10 langkah POLI-JANTUNG '
            f'{"lengkap" if complete else "belum lengkap"} '
            f'(versi {workflow.version}).'
        )
        KorelasiEpAsesmen.objects.update_or_create(
            kunjungan=visit, standard_item=item,
            defaults={
                'status': status, 'catatan': catatan,
                'diverifikasi_oleh': user, 'diverifikasi_pada': now,
            },
        )
        rows.append({
            'sub_standard': rule.sub_standard, 'code': item.code,
            'status': status, 'catatan': catatan,
            'verified_at': now.isoformat(),
        })
    return rows

def _waiting_minutes(visit):
    """AMBIGU-09: ``registrasi_selesai_at`` → CPPT pertama berstatus SIGNED."""
    start = visit.registrasi_selesai_at
    if start is None:
        return None
    first_signed = (
        visit.cppt.filter(status='SIGNED').order_by('tanggal', 'pk').first()
    )
    if first_signed is None:
        return None
    return (first_signed.tanggal - start).total_seconds() / 60.0

def _month_bounds(now):
    from datetime import date

    start = date(now.year, now.month, 1)
    end = date(now.year + (now.month == 12), (now.month % 12) + 1, 1)
    return start, end

def _finished_rajal_visits(unit_id, now):
    from pasien.models import KunjunganPasien

    start, end = _month_bounds(now)
    return (
        KunjunganPasien.objects
        .filter(
            unit_kerja_id=unit_id,
            igd_workflow__service_line=RAJAL_JANTUNG_SERVICE_LINE,
            igd_workflow__status='FINAL',
            tanggal_kunjungan__gte=start, tanggal_kunjungan__lt=end,
        )
        .prefetch_related('cppt', 'order_penunjang')
    )

def _write_indicator(kode, now, patuh, catatan):
    """Tulis satu ``CatatanIndikator`` dari daftar ``patuh`` (bool per kasus).

    Angka adalah hasil hitung ulang seluruh episode bulan itu, bukan penambahan
    buta — sehingga finalisasi ulang setelah addendum tidak menggandakan angka.
    """
    from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu

    indikator = IndikatorMutu.objects.filter(kode_indikator=kode).first()
    if indikator is None:
        return None
    denominator = len(patuh)
    numerator = sum(1 for value in patuh if value)
    if not denominator:
        return None
    record, _created = CatatanIndikator.objects.update_or_create(
        indikator=indikator, bulan=now.month, tahun=now.year,
        defaults={
            'nilai_numerator': numerator, 'nilai_denominator': denominator,
            'catatan': catatan,
        },
    )
    return record

def _record_unit_indicators(visit, now):
    """F7.7 — umpan indikator PDCA unit Poli Jantung untuk bulan berjalan.

    Dua metrik diumpan; yang ketiga ("kelengkapan asesmen awal <= 24 jam")
    sengaja **tidak** diumpan karena matriks tidak memberi definisi
    terukurnya — dilaporkan sebagai AMBIGU-23, bukan dikarang.

    * Waktu tunggu (matriks §7, AMBIGU-09): ``registrasi_selesai_at`` →
      ``CPPT`` pertama ``SIGNED``; patuh bila <= 60 menit.
    * Lapor nilai kritis (matriks §7): ``critical_found_at`` →
      ``critical_reported_at``; patuh bila <= 30 menit.
    """
    unit_id = visit.unit_kerja_id
    if unit_id is None:
        return {}
    selesai = list(_finished_rajal_visits(unit_id, now))
    results = {}

    wait_pairs = []
    for row in selesai:
        minutes = _waiting_minutes(row)
        if minutes is None:
            continue
        wait_pairs.append(minutes <= WAIT_MINUTES_TARGET)
    record = _write_indicator(
        INDIKATOR_WAKTU_TUNGGU, now, wait_pairs,
        f'Dihitung otomatis F7.7 dari {len(selesai)} kunjungan POLI-JANTUNG '
        f'selesai bulan {now.month}/{now.year} '
        '(AMBIGU-09: registrasi selesai → CPPT pertama SIGNED; ambang 60 menit).',
    )
    if record is not None:
        results[INDIKATOR_WAKTU_TUNGGU] = record.pk

    critical_pairs = []
    for row in selesai:
        for order in row.order_penunjang.all():
            if not order.is_critical_value:
                continue
            if order.critical_found_at is None or order.critical_reported_at is None:
                continue
            minutes = (order.critical_reported_at - order.critical_found_at).total_seconds() / 60.0
            critical_pairs.append(minutes <= CRITICAL_MINUTES_TARGET)
    record = _write_indicator(
        INDIKATOR_NILAI_KRITIS, now, critical_pairs,
        f'Dihitung otomatis F7.7 dari nilai kritis POLI-JANTUNG bulan '
        f'{now.month}/{now.year} (matriks §7: lapor <= 30 menit).',
    )
    if record is not None:
        results[INDIKATOR_NILAI_KRITIS] = record.pk
    return results

def _apply_rajal_disposition(visit, user, payload, values, kondisi, now):
    """S10-L1-05 — empat cabang, masing-masing memakai jalur yang sudah ada.

    Tidak ada pencetak baru: tiap cabang hanya menunjuk route cetak yang sudah
    dipakai dasbor IGD/rawat jalan.
    """
    disposition = payload['disposisi']
    resume = values['resume']
    if disposition == 'PULANG':
        visit.discharge_patient(
            kondisi=kondisi, resume=resume, user=user,
            edukasi=values['edukasi'], obat=values['obat'],
            kontrol=values['kontrol'] or _planned_kontrol(visit),
        )
        record = visit.discharge
        record.status_clearance = 'PROSES'
        record.save(update_fields=['status_clearance'])
        visit.status_antrean = 'SELESAI'
        visit.save(update_fields=['status', 'status_antrean'])
    elif disposition == 'RAWAT_INAP':
        bed = (
            Bed.objects.select_for_update().select_related('ruangan')
            .filter(pk=values['bed_id']).first()
        )
        dpjp = values.get('dpjp') or visit.dpjp
        if bed is None or bed.status != 'TERSEDIA' or not bed.ruangan.unit_kerja_id or not dpjp:
            raise WorkflowValidation({'bed_id': [
                'Pilih bed tersedia dengan unit tujuan dan DPJP yang jelas.'
            ]})
        visit.admit_to_ranap(bed, dpjp=dpjp)
        visit.unit_kerja = bed.ruangan.unit_kerja
        visit.status_antrean = 'SELESAI'
        visit.save(update_fields=['unit_kerja', 'status_antrean'])
    elif disposition == 'RUJUK_ANTAR_POLI':
        visit.konsul_ke_poli = payload['disposisi_poli']
        visit.konsul_catatan = payload['disposisi_alasan']
        visit.status = 'DISPOSISI'
        visit.status_antrean = 'SELESAI'
        visit.tanggal_keluar = now
        visit.save()
        _write_rajal_discharge(visit, user, values, kondisi, now)
    else:  # RUJUK_KELUAR
        visit.status = 'RUJUK'
        visit.status_antrean = 'SELESAI'
        visit.tanggal_keluar = now
        visit.sisrute_rs_tujuan = payload['disposisi_rs_tujuan']
        visit.sisrute_alasan = payload['disposisi_alasan']
        visit.save()
        # ``DischargeRecord.RUJUK`` berarti "dirujuk ke RS lain" — fakta
        # disposisi, bukan proyeksi kondisi klinis.
        _write_rajal_discharge(visit, user, values, 'RUJUK', now)
    return {
        'branch': disposition,
        'kondisi_akhir': payload.get('kondisi_akhir_rajal'),
        'kondisi_pulang': getattr(getattr(visit, 'discharge', None), 'kondisi_pulang', ''),
        'status_after': visit.status,
        'service_after': visit.jenis_kunjungan,
        'documents': list(_rajal_documents(disposition)),
    }

def _write_rajal_discharge(visit, user, values, kondisi, now):
    """DischargeRecord untuk cabang yang tidak memakai ``discharge_patient``."""
    DischargeRecord.objects.update_or_create(
        kunjungan=visit,
        defaults={
            'tanggal_discharge': now,
            'kondisi_pulang': kondisi,
            'resume_medis': values['resume'] or 'Pelayanan selesai.',
            'edukasi_pulang': values['edukasi'],
            'obat_pulang': values['obat'],
            'jadwal_kontrol': values['kontrol'] or _planned_kontrol(visit),
            'total_tagihan': sum((b.subtotal for b in visit.billing.all()), 0),
            'status_clearance': 'PROSES',
            'dibuat_oleh': user,
        },
    )

def _finalize_rajal(visit, workflow, user, data):
    """Tutup episode rawat jalan jantung: DPJP-only, kondisi akhir dari langkah 10."""
    require_dpjp(user, visit)
    values = validate(RajalFinalizationForm, data)
    snapshot = clinical_snapshot(visit, workflow)
    fingerprint = digest(snapshot)
    errors = missing_rajal_sections(workflow)
    signature = workflow.signatures.get('MEDIS', {})
    if signature.get('content_digest') != fingerprint:
        errors.append('Tanda tangan MEDIS untuk data terkini')
    payload = (workflow.draft_payload or {}).get('10', {})
    kondisi = payload.get('kondisi_akhir_rajal')
    if kondisi not in KONDISI_AKHIR_RAJAL_CHOICES:
        errors.append('Kondisi akhir rawat jalan wajib dipilih pada langkah 10.')
    branch_errors = validate_disposisi_rajal(payload)
    if branch_errors:
        errors.extend(message for messages in branch_errors.values() for message in messages)
    if errors:
        raise WorkflowValidation({'finalisasi': errors})
    now = timezone.now()
    kondisi_pulang = KONDISI_AKHIR_TO_KONDISI_PULANG[kondisi]
    disposition = _apply_rajal_disposition(visit, user, payload, values, kondisi_pulang, now)
    # F7.4/F7.5/F7.7 — bukti mutu ditulis sebelum revisi final agar snapshot
    # memuat keadaan yang benar-benar tersimpan. Status FINAL disimpan lebih
    # dulu supaya agregat indikator (yang menyaring `status='FINAL'`) sudah
    # menghitung episode ini sendiri.
    workflow.status, workflow.finalized_by, workflow.finalized_at, workflow.last_step = (
        'FINAL', user, now, 10,
    )
    workflow.save(update_fields=['status', 'finalized_by', 'finalized_at', 'last_step', 'updated_at'])
    incident = _record_incident(visit, workflow, user, now)
    ep_evidence = _record_ep_evidence(visit, workflow, user, now)
    indicators = _record_unit_indicators(visit, now)
    snapshot['signatures'] = copy.deepcopy(workflow.signatures)
    snapshot['disposition'] = {
        **disposition,
        'resume': values['resume'],
        'finalized_by': user.pk,
        'finalized_at': now.isoformat(),
    }
    snapshot['ep_evidence'] = ep_evidence
    snapshot['incident_id'] = incident.pk if incident else None
    snapshot['indicator_records'] = indicators
    revision = IgdAssessmentRevision.objects.create(
        workflow=workflow, revision=1, snapshot=snapshot, signed_by=user,
    )
    return {
        'revision_id': revision.pk,
        'kondisi_akhir': kondisi,
        'disposition': disposition['branch'],
        'documents': disposition['documents'],
    }

def finalize(visit, workflow, user, data):
    if _is_rajal(workflow):
        return _finalize_rajal(visit, workflow, user, data)
    require_doctor(user)
    values = validate(FinalizationForm,data)
    snapshot = clinical_snapshot(visit,workflow)
    fingerprint = digest(snapshot)
    errors = missing_sections(visit,workflow)
    for section in ('MEDIS', 'KEPERAWATAN') if visit.diagnosa_keperawatan_sdki.strip() else ('MEDIS',):
        signature = workflow.signatures.get(section,{})
        if signature.get('content_digest') != fingerprint:
            errors.append(f'Tanda tangan {section} untuk data terkini')
    if errors:
        raise WorkflowValidation({'finalisasi':errors})
    # Capture signed clinical content before administrative transfer changes ownership.
    apply_disposition(visit,user,values)
    snapshot['signatures'] = copy.deepcopy(workflow.signatures)
    snapshot['disposition'] = {**values,'status_after':visit.status,'service_after':visit.jenis_kunjungan,
                               'bed_after':visit.bed_id,'finalized_by':user.pk,'finalized_at':timezone.now().isoformat()}
    revision = IgdAssessmentRevision.objects.create(workflow=workflow, revision=1, snapshot=snapshot, signed_by=user)
    workflow.status, workflow.finalized_by, workflow.finalized_at, workflow.last_step = 'FINAL',user,timezone.now(),11
    return {'revision_id':revision.pk,'outcome':values['outcome']}


def addendum(visit, workflow, user, data):
    values = validate(AddendumForm,data)
    if workflow.status != 'FINAL':
        raise WorkflowConflict('Addendum hanya untuk dokumentasi final.')
    if _is_rajal(workflow):
        require_dpjp(user, visit)
        if values['section'] != 'MEDIS':
            raise PermissionDenied('Addendum asesmen POLI-JANTUNG hanya oleh DPJP (bagian medis).')
    elif values['section'] == 'MEDIS':
        require_doctor(user)
    elif user.profile.profesi not in NURSES:
        raise PermissionDenied('Addendum keperawatan memerlukan perawat/bidan.')
    previous = workflow.revisions.order_by('-revision').first()
    if previous is None:
        raise WorkflowConflict('Snapshot final tidak ditemukan.')
    snapshot = copy.deepcopy(previous.snapshot)
    snapshot.setdefault('addenda',[]).append({**values,'author_id':user.pk,'author':user.get_full_name() or user.username,
        'profession':user.profile.profesi,'signed_at':timezone.now().isoformat()})
    revision = IgdAssessmentRevision.objects.create(workflow=workflow,revision=previous.revision+1,
        snapshot=snapshot,reason=values['reason'],signed_by=user)
    return {'revision_id':revision.pk}
