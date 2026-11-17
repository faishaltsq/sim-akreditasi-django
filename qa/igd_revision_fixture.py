"""Synthetic IGD fixture CLI. No application routes or operational DB writes.

Run with the project venv: bootstrap, serve, readback, mutate-master.
Private sessions and database ownership are stored only under OWNED_ROOT.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlsplit
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
OWNED_ROOT = Path('C:/Users/cubeb/AppData/Local/hermes/cache/scratch/arima_revision_20261116').resolve()
OWNER = 'arima-igd-revision-browser-v1'
LEGACY = {'tatalaksana_resusitasi': 'SYNTHETIC historical stabilization retained',
          'tatalaksana_terapi': 'SYNTHETIC historical pharmacotherapy retained',
          'tatalaksana_tindakan_check': ['O2']}


def validate_private_path(path):
    target = Path(path).resolve()
    if not target.is_relative_to(OWNED_ROOT) or target == OWNED_ROOT:
        raise ValueError('Private state/evidence must stay inside the owned scratch directory.')
    return target


def validate_base_url(base):
    url = urlsplit(base)
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or
            url.username or url.password or url.path or url.query or url.fragment):
        raise ValueError('Only an explicit http://127.0.0.1:PORT origin is permitted.')
    return url.port


def validate_database(config, *, pg_name=None):
    engine = config.get('ENGINE')
    name = config.get('NAME')
    test = config.get('TEST', {}).get('NAME')
    if engine == 'django.db.backends.sqlite3':
        name = Path(name).resolve()
        if name != OWNED_ROOT / 'browser.sqlite3' or not test or Path(test).resolve() != OWNED_ROOT / 'test_browser.sqlite3':
            raise ValueError('Refusing non-owned SQLite database or test database.')
        return {'vendor': 'sqlite', 'name': str(name), 'test_name': str(Path(test).resolve())}
    if engine == 'django.db.backends.postgresql':
        if (not pg_name or name != pg_name or not re.fullmatch(r'arima_revision_browser(?:_[a-z0-9]+)?', str(name)) or
                config.get('HOST') not in ('127.0.0.1', '::1') or not str(config.get('PORT', '')).isdigit() or
                test != 'test_' + str(name)):
            raise ValueError('PostgreSQL requires explicit matching isolated name, loopback host/port and distinct test name.')
        if not 1 <= int(config['PORT']) <= 65535:
            raise ValueError('Invalid PostgreSQL port.')
        return {'vendor': 'postgresql', 'host': config['HOST'], 'port': str(config['PORT']), 'name': name, 'test_name': test}
    raise ValueError('Unsupported fixture database engine.')


def require_new_target(identity, *, reuse_owned, marker_matches):
    exists = identity['vendor'] == 'sqlite' and Path(identity['name']).exists()
    if exists and not (reuse_owned and marker_matches):
        raise ValueError('Existing database refused; reviewed --reuse-owned requires matching private ownership state.')
    if reuse_owned and not marker_matches:
        raise ValueError('Reviewed reuse requires matching private ownership state.')


def dump_private(path, data):
    path = validate_private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True, default=str), encoding='utf-8')
    os.chmod(path, 0o600)


def load_state(path):
    state = json.loads(validate_private_path(path).read_text(encoding='utf-8'))
    if state.get('owner') != OWNER or state.get('synthetic') is not True:
        raise ValueError('State is not an owned synthetic fixture.')
    validate_base_url(state['base_url'])
    return state


def setup(settings_module, pg_name=None):
    # Import through the scratch settings wrapper; never import operational settings directly.
    if not re.fullmatch(r'revision_browser_settings(?:_[a-z0-9]+)?', settings_module):
        raise ValueError('Use an owned revision_browser_settings module in scratch.')
    sys.path[:0] = [str(REPO), str(OWNED_ROOT)]
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    from django.conf import settings
    identity = validate_database(settings.DATABASES['default'], pg_name=pg_name)
    import django
    django.setup()
    return identity


def seed(identity, base_url, settings_module):
    from django.contrib.auth.models import User
    from django.test import Client
    from django.utils import timezone
    from accounts.models import UserProfile
    from akreditasi.models import UnitKerja
    from pasien.professional_test_support import ProfessionalCareCase
    from pasien.models import (Pasien, KunjunganPasien, PharmacyServiceGrant,
                               PenugasanDpjpEpisode, TindakanAsesmen)
    from klinis.models import (KategoriPenunjang, ItemPenunjang, KelasTerapiObat,
        GenerikObat, ProdukFarmasi, KomposisiProdukFarmasi, KeanggotaanFormularium,
        MasterIcd10, MasterIcd9, KelompokLayanan, KasusTersering, KasusTindakan,
        SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S, TarifLayananProfesi)
    from sdm.models import ClinicalActionCode, PrivilegeSnapshot
    ProfessionalCareCase.setUpTestData()
    f = ProfessionalCareCase
    f.service.name = 'SYNTHETIC Professional Care'
    f.service.save(update_fields=['name'])
    units = {}
    for label in ('pharmacy', 'unrelated_pharmacy', 'lab', 'other'):
        units[label] = UnitKerja.objects.create(code='QAR-' + label.upper(), name='SYNTHETIC ' + label, level=3)
    users = {'doctor': f.user}
    for role, profession, unit, profile_role in [
            ('nurse', 'PERAWAT', f.unit, 'STAF_NAKES'),
            ('pharmacist', 'APOTEKER', units['pharmacy'], 'STAF_NAKES'),
            ('unrelated_pharmacist', 'APOTEKER', units['unrelated_pharmacy'], 'STAF_NAKES'),
            ('reviewer', 'APOTEKER', units['pharmacy'], 'STAF_NAKES'),
            ('lab', 'ATLM', units['lab'], 'STAF_NAKES'),
            ('wrong_doctor', 'DOKTER_UMUM', units['other'], 'STAF_NAKES'),
            ('admin', '', f.unit, 'ADMIN_RS'), ('assessor', '', f.unit, 'ASESOR')]:
        user = User.objects.create_user('synthetic-revision-' + role)
        UserProfile.objects.update_or_create(user=user, defaults={'role': profile_role, 'profesi': profession, 'unit_kerja': unit})
        users[role] = user
    for role, unit in [('pharmacist', units['pharmacy']), ('unrelated_pharmacist', units['unrelated_pharmacy']), ('reviewer', units['pharmacy'])]:
        PharmacyServiceGrant.objects.create(user=users[role], unit=unit, can_ppra_review=role == 'reviewer')
    today = timezone.localdate()
    TarifLayananProfesi.objects.create(service=f.service, unit=f.unit, profession=f.profession, grade=f.grade,
        payor='UMUM', valid_from=today, jasa_sarana=50000, jasa_pelayanan=150000, is_free=False,
        review_state='APPROVED', is_active=True, reviewed_by=users['reviewer'], reviewed_at=timezone.now(), source_version=OWNER)
    verify_code, _ = ClinicalActionCode.objects.get_or_create(code='verify_cppt', defaults={'label': 'Synthetic verify CPPT'})
    PrivilegeSnapshot.objects.create(pegawai=f.employee, unit_kerja=f.unit, action_code=verify_code, valid_from=today, source_decision=f.spk)
    visits = {}; patient_rm = {}; plans = {}
    for label in ('desktop', 'tablet', 'mobile', 'nursing', 'rx', 'interval', 'prn', 'ancillary', 'race', 'professional', 'legacy', 'snapshot', 'roles'):
        patient = Pasien.objects.create(no_rm='QAR-' + label.upper(), nama_lengkap='SYNTHETIC IGD ' + label,
            tanggal_lahir='1990-01-01', jenis_kelamin='L')
        visit = KunjunganPasien.objects.create(pasien=patient, no_kunjungan='QAR-' + label.upper(),
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), unit_kerja=f.unit, created_by=f.user,
            skrining_alergi_status='TIDAK_ADA', **(LEGACY if label in ('legacy', 'snapshot') else {}))
        visits[label] = visit.pk; patient_rm[label] = patient.no_rm
        PenugasanDpjpEpisode.objects.create(visit=visit, doctor=f.user, unit=f.unit, assignment_type='PRIMARY',
            valid_from=today, valid_until=today, source_version=OWNER, assigned_by=users['reviewer'], is_active=True)
        if label == 'professional':
            plans[label] = TindakanAsesmen.objects.create(kunjungan=visit, urutan=1, jenis='BEBAS',
                kode=f.service.code, nama=f.service.name, execution_status='PLANNED', execution_team='MEDIS', tarif_penjamin='UMUM').pk
    root = KategoriPenunjang.objects.create(kode='QAR-LAB', nama='SYNTHETIC Laboratory', level=1)
    installation = KategoriPenunjang.objects.create(kode='QAR-LAB-INST', nama='SYNTHETIC Clinical Lab', level=2, parent=root)
    group = KategoriPenunjang.objects.create(kode='QAR-LAB-GROUP', nama='SYNTHETIC Hematology', level=3, parent=installation)
    other_group = KategoriPenunjang.objects.create(kode='QAR-LAB-OTHER', nama='SYNTHETIC Other Group', level=3, parent=installation)
    item = ItemPenunjang.objects.create(kode='QAR-CBC', nama='CBC Synthetic', group=group, jenis_order='LAB',
        destination=units['lab'], active=True, source_version=OWNER, source_note='Explicitly synthetic, not a clinical catalogue activation', reviewed_by=f.user)
    metadata = ItemPenunjang.objects.create(kode='QAR-REFERRAL', nama='SYNTHETIC Referral Specimen', group=other_group,
        jenis_order='LAB', destination=units['lab'], active=True, source_version=OWNER, reviewed_by=f.user,
        preparation_schema={'required': ['specimen', 'external_destination']}, variants={'specimen': ['SYNTHETIC EDTA', 'SYNTHETIC Serum']})
    # More than the actual catalogue page size (50), exclusively in the disposable DB.
    for index in range(55):
        ItemPenunjang.objects.create(kode=f'QAR-PAGE-{index:03}', nama=f'SYNTHETIC Paged Item {index:03}',
            group=group, jenis_order='LAB', destination=units['lab'], active=True, source_version=OWNER, reviewed_by=f.user)
    products = {}
    for label, flags in [('normal', []), ('risk', ['LASA', 'HIGH_ALERT']), ('restricted', ['PPRA'])]:
        cls = KelasTerapiObat.objects.create(kode='QAR-' + label, nama='SYNTHETIC Class ' + label)
        generic = GenerikObat.objects.create(kode='QAR-' + label, nama='SYNTHETIC Generic ' + label,
            kelas=cls, bentuk='TABLET', dispense_unit='tablet', strength='500 mg')
        product = ProdukFarmasi.objects.create(kode='QAR-' + label, nama='Product Synthetic ' + label, generik=generic,
            kind='OBAT', active=True, source_version=OWNER, reviewed_by=f.user, price='1000', allowed_routes=['PO'],
            flags=flags, tall_man_label='SYNthetic RISK' if flags else '')
        KomposisiProdukFarmasi.objects.create(produk=product, ingredient_code='synthetic-' + label, nama='SYNTHETIC ingredient ' + label, strength='500', unit='mg')
        KeanggotaanFormularium.objects.create(produk=product, jenis='RS', source_version=OWNER, valid_from=today, reviewed_by=f.user)
        products[label] = [cls.pk, generic.pk, product.pk]
    icd10 = MasterIcd10.objects.create(kode='QAR.1', nama='SYNTHETIC Linked Diagnosis')
    icd9 = MasterIcd9.objects.create(kode='QAR.9', nama='SYNTHETIC Linked Procedure')
    unrelated = MasterIcd9.objects.create(kode='QAR.8', nama='SYNTHETIC Unrelated Procedure')
    f.service.icd9 = icd9; f.service.save(update_fields=['icd9'])
    group_services = KelompokLayanan.objects.create(kode='QAR-IGD', nama='SYNTHETIC IGD Case Group', unit_kerja=f.unit)
    case = KasusTersering.objects.create(kelompok=group_services, urutan=1, icd10=icd10, catatan_sumber=OWNER)
    KasusTindakan.objects.create(kasus=case, icd9=icd9, urutan=1, tarif_umum='200000', satuan='tindakan')
    sdki = SdkiDiagnosis.objects.create(kode='D.QAR', nama='SYNTHETIC Nursing Diagnosis')
    slki = SlkiLuaran.objects.create(kode='L.QAR', nama='SYNTHETIC Nursing Outcome')
    siki = SikiIntervensi.objects.create(kode='I.QAR', nama='SYNTHETIC Nursing Intervention')
    Pemetaan3S.objects.create(sdki=sdki, slki=slki, siki=siki)
    sessions = {}
    for role, user in users.items():
        client = Client(); client.force_login(user)
        sessions[role] = {'id': user.pk, 'session': client.cookies['sessionid'].value}
    return {'owner': OWNER, 'synthetic': True, 'run_id': str(uuid4()), 'created_at': timezone.now().isoformat(),
        'base_url': base_url, 'settings': settings_module, 'database': identity, 'users': sessions, 'visits': visits,
        'patient_rm': patient_rm, 'pharmacy_unit': units['pharmacy'].pk,
        'catalogue': {**products, 'ancillary': [root.pk, installation.pk, group.pk, item.pk],
            'ancillary_metadata': [root.pk, installation.pk, other_group.pk, metadata.pk],
            'icd10': {'id': icd10.pk, 'code': icd10.kode, 'name': icd10.nama},
            'icd9': {'id': icd9.pk, 'code': icd9.kode, 'name': icd9.nama}, 'unrelated_icd9': unrelated.kode,
            'nursing': {'sdki': sdki.kode, 'slki': slki.kode, 'siki': siki.kode}},
        'professional': {'service': f.service.pk, 'actor': f.user.pk, 'employee': f.employee.pk, 'grade': f.grade.pk, 'plans': plans},
        'legacy': LEGACY, 'python': str(REPO / '.venv/Scripts/python.exe'), 'repo': str(REPO)}


def bootstrap(args, identity):
    from django.core.management import call_command
    from django.db import connection, transaction
    state_path = validate_private_path(args.state)
    old = load_state(state_path) if state_path.exists() else None
    matches = bool(old and old['database'] == identity and old['settings'] == args.settings)
    require_new_target(identity, reuse_owned=args.reuse_owned, marker_matches=matches)
    if old and not args.reuse_owned:
        raise ValueError('Existing private state refused; choose a new state path or reviewed reuse.')
    if args.reuse_owned:
        if identity['vendor'] == 'sqlite' and not Path(identity['name']).is_file():
            raise ValueError('Reuse database missing.')
        from django.contrib.sessions.models import Session
        if not all(Session.objects.filter(session_key=user['session']).exists() for user in old['users'].values()):
            raise ValueError('Reuse fixture sessions are missing.')
        print(json.dumps({'reused': True, 'state': str(state_path), 'database': identity}))
        return
    # PG may already be provisioned, but must have an empty schema before full migrate.
    if identity['vendor'] == 'postgresql' and connection.introspection.table_names():
        raise ValueError('New PostgreSQL fixture schema must be empty; existing targets require reviewed owned reuse.')
    print(json.dumps({'asserted_database': identity, 'synthetic': True}), flush=True)
    call_command('migrate', interactive=False, verbosity=1)
    with transaction.atomic():
        state = seed(identity, args.base_url, args.settings)
    dump_private(state_path, state)
    from django.db.migrations.executor import MigrationExecutor
    pending = MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
    assert not pending, 'Full normal migrate graph must be complete'
    print(json.dumps({'bootstrapped': True, 'state': str(state_path), 'database': identity, 'visits': len(state['visits']), 'roles': list(state['users']), 'migration_pending': len(pending)}))


def check_owned_state(args, identity):
    state = load_state(args.state)
    if state['database'] != identity or state['settings'] != args.settings:
        raise ValueError('State/database/settings mismatch.')
    if identity['vendor'] == 'sqlite' and not Path(identity['name']).is_file():
        raise ValueError('Owned database does not exist.')
    return state


def readback(state, visit_label=None):
    from django.core.serializers.json import DjangoJSONEncoder
    from pasien.models import KunjunganPasien, IgdAssessmentWorkflow, VerifikasiCppt
    visits = state['visits'] if visit_label is None else {visit_label: state['visits'][visit_label]}
    result = {'synthetic': True, 'database': state['database'], 'visits': {}}
    for label, pk in visits.items():
        visit = KunjunganPasien.objects.get(pk=pk)
        if not visit.pasien.no_rm.startswith('QAR-'):
            raise ValueError('Not a synthetic visit.')
        wf = IgdAssessmentWorkflow.objects.filter(kunjungan=visit).first()
        result['visits'][label] = {
            'id': pk, 'legacy': {key: getattr(visit, key) for key in LEGACY},
            'nursing': {key: getattr(visit, key) for key in ('diagnosa_keperawatan_sdki', 'luaran_keperawatan_slki', 'intervensi_keperawatan_siki', 'diagnosis_provenance')},
            'workflow': {'version': wf.version, 'status': wf.status} if wf else None,
            'diagnoses': list(visit.diagnoses.values('id', 'kode', 'nama', 'active', 'is_primary', 'mode')),
            'orders': list(visit.order_penunjang.values('id', 'prioritas', 'preparation', 'catalogue_snapshot', 'status', 'destination_id')),
            'actions': list(visit.tindakan_asesmen.values('id', 'execution_status', 'billing_item_id', 'execution_cppt_id', 'catatan_klinis', 'execution_team')),
            'charges': list(visit.billing.values('id', 'sumber', 'kuantitas', 'harga_satuan', 'is_void')),
            'prescriptions': [{'id': rx.pk, 'status': rx.status, 'version': rx.version,
                'items': list(rx.items.values('id', 'product_id', 'regimen', 'quantity_decimal', 'billing_item_id')),
                'operations': rx.operations.count()} for rx in visit.resep_list.all()],
            'notes': list(visit.cppt.values('id', 'status', 'version', 'verifikasi_dpjp', 'subjektif', 'objektif', 'asesmen', 'plan')),
            'verification_count': VerifikasiCppt.objects.filter(revision__note__kunjungan=visit).count(),
            'revisions': [{'id': row.pk, 'digest': hashlib.sha256(json.dumps(row.snapshot, sort_keys=True, cls=DjangoJSONEncoder).encode()).hexdigest(), 'legacy': {key: row.snapshot.get('visit', {}).get(key) for key in LEGACY}} for row in wf.revisions.all()] if wf else []}
    return result


def serve(state):
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.wsgi import get_wsgi_application
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import make_server, WSGIServer
    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = False
    port = validate_base_url(state['base_url'])
    # Reserve the actual listening socket atomically; never bind a wildcard interface.
    server = make_server('127.0.0.1', port, StaticFilesHandler(get_wsgi_application()), server_class=ThreadedServer)
    print(json.dumps({'ready': True, 'base_url': state['base_url'], 'database': state['database']}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def mutate_master(state):
    from klinis.models import ProdukFarmasi
    from sdm.models import Pegawai, MasterJenjangProfesi
    from pasien.models import IgdAssessmentWorkflow
    if not IgdAssessmentWorkflow.objects.filter(kunjungan_id=state['visits']['snapshot'], status='FINAL').exists():
        raise ValueError('Snapshot visit must be signed/final before synthetic master mutation.')
    ProdukFarmasi.objects.filter(pk=state['catalogue']['normal'][-1], source_version=OWNER).update(nama='SYNTHETIC changed master', price='2345', flags=['LASA'])
    Pegawai.objects.filter(pk=state['professional']['employee']).update(nama_lengkap='SYNTHETIC changed performer')
    MasterJenjangProfesi.objects.filter(pk=state['professional']['grade']).update(nama='SYNTHETIC changed grade')
    product = ProdukFarmasi.objects.get(pk=state['catalogue']['normal'][-1], source_version=OWNER)
    employee = Pegawai.objects.get(pk=state['professional']['employee'])
    grade = MasterJenjangProfesi.objects.get(pk=state['professional']['grade'])
    print(json.dumps({'synthetic_master_mutated': True, 'readback': {
        'product': {'id': product.pk, 'nama': product.nama, 'price': str(product.price), 'flags': product.flags},
        'performer': {'id': employee.pk, 'nama': employee.nama_lengkap},
        'grade': {'id': grade.pk, 'nama': grade.nama}}}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['bootstrap', 'serve', 'readback', 'mutate-master'])
    parser.add_argument('--settings', default='revision_browser_settings')
    parser.add_argument('--pg-name', help='Explicit reviewed isolated PostgreSQL database name; no provisioning')
    parser.add_argument('--state', default=str(OWNED_ROOT / 'fixture_state.json'))
    parser.add_argument('--base-url', default='http://127.0.0.1:18776')
    parser.add_argument('--reuse-owned', action='store_true', help='Reviewed reuse only; does not migrate, reseed or reset')
    parser.add_argument('--visit', help='Bounded readback label from state')
    parser.add_argument('--evidence', help='Private scratch JSON destination for readback')
    args = parser.parse_args()
    validate_private_path(args.state); validate_base_url(args.base_url)
    identity = setup(args.settings, args.pg_name)
    if args.command == 'bootstrap':
        bootstrap(args, identity)
        return
    state = check_owned_state(args, identity)
    if args.command == 'serve':
        serve(state)
    elif args.command == 'mutate-master':
        mutate_master(state)
    else:
        from django.core.serializers.json import DjangoJSONEncoder
        result = readback(state, args.visit)
        text = json.dumps(result, indent=2, cls=DjangoJSONEncoder)
        if args.evidence:
            dump_private(args.evidence, json.loads(text))
        print(text)


if __name__ == '__main__':
    main()
