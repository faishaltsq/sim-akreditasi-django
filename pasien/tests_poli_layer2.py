"""Langkah 3–6 Lapis 2 kardiologi (F3) — matriks S3-L2 .. S6-L2.

Setiap tes menyatakan satu perilaku yang dapat diamati: isi ``draft_payload``,
daftar finding keselamatan, atau HTML yang dirender ulang. Nilai yang tidak
diberikan matriks **tidak** diuji karena tidak boleh ada: klasifikasi Indeks
Brinkman (AMBIGU-03) sengaja tidak ada di kode, dan tes di bawah menegaskan
ketiadaan itu. AMBIGU-17 ditutup oleh keputusan produk pada Rilis A2: lokasi
murmur memakai lima kode tertutup (A1) dan pemetaan kelompok kontraindikasi
kehamilan dibaca dari kolom master, bukan daftar molekul di kode (A2).
"""
import json
from decimal import Decimal

from django.apps import apps
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from klinis.models import (
    GenerikObat, KelasTerapiObat, KomposisiProdukFarmasi, ProdukFarmasi,
)
from pasien.models import KunjunganPasien, ResepDetail, ResepElektronik, indeks_brinkman
from pasien.services.igd_assessment_workflow import WorkflowValidation, save_step
from pasien.services.medication_safety import evaluate_prescription
from pasien.services.prescriptions import review_risks
from pasien.services.pregnancy_safety import contra_groups, pregnancy_status
from pasien.workflow_schemas import (
    FAKTOR_RISIKO_CHOICES, MURMUR_DERAJAT_CHOICES, OBAT_RUTIN_CHOICES,
    RAJAL_JANTUNG_STEPS, RIWAYAT_JANTUNG_CHOICES,
)

from .tests_poli_workflow import TEST_STORAGES, PoliFixture

class IndeksBrinkmanTest(SimpleTestCase):
    """F3.2: rumus murni; klasifikasi tetap terbuka (AMBIGU-03)."""

    def test_plan_examples_return_raw_numbers(self):
        self.assertEqual(indeks_brinkman(20, 15), 300)
        self.assertEqual(indeks_brinkman(5, 4), 20)

    def test_missing_or_invalid_input_yields_none(self):
        self.assertIsNone(indeks_brinkman(None, 15))
        self.assertIsNone(indeks_brinkman(20, None))
        self.assertIsNone(indeks_brinkman(-1, 15))
        self.assertIsNone(indeks_brinkman('banyak', 15))

    def test_no_classification_band_is_exposed(self):
        """AMBIGU-03 belum ditutup: fungsi tidak boleh mengembalikan kategori."""
        self.assertIsInstance(indeks_brinkman(20, 15), (int, float))
        self.assertNotIsInstance(indeks_brinkman(20, 15), str)
        self.assertFalse(hasattr(__import__('pasien.models', fromlist=['x']), 'brinkman_kategori'))

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RajalLapisDuaFixture(PoliFixture):
    def save(self, step, fields, version=0):
        return save_step(self.visit.pk, self.nurse, step, fields, version,
                         service_line='RAJAL_JANTUNG')

class StepTwoOnsetPemicuTest(RajalLapisDuaFixture):
    """F3.1: onset & pemicu — matriks menempatkannya di Langkah 2 Lapis 2."""

    def test_onset_and_trigger_are_stored(self):
        workflow = self.save(2, {'onset_gejala': '30M_6J', 'pemicu_gejala': 'AKTIVITAS_SEDANG_BERAT'})
        self.assertEqual(workflow.draft_payload['2']['onset_gejala'], '30M_6J')
        self.assertEqual(workflow.draft_payload['2']['pemicu_gejala'], 'AKTIVITAS_SEDANG_BERAT')

    def test_value_outside_matrix_options_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(2, {'onset_gejala': 'SEJAK_KECIL'})
        self.assertIn('onset_gejala', ctx.exception.errors)

class StepThreeRiwayatTest(RajalLapisDuaFixture):
    """F3.1/F3.2: riwayat jantung & faktor risiko multi-select, rokok, Brinkman."""

    def test_multi_select_stores_declared_codes_as_list(self):
        workflow = self.save(3, {
            'riwayat_jantung': ['PJK', 'PCI_STENT_CABG'],
            'faktor_risiko_kardio': ['HIPERTENSI', 'DISLIPIDEMIA'],
        })
        self.assertEqual(workflow.draft_payload['3']['riwayat_jantung'], ['PJK', 'PCI_STENT_CABG'])
        self.assertEqual(workflow.draft_payload['3']['faktor_risiko_kardio'],
                         ['HIPERTENSI', 'DISLIPIDEMIA'])

    def test_multi_select_rejects_code_outside_matrix(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(3, {'riwayat_jantung': ['PJK', 'KARANGAN']})
        self.assertIn('riwayat_jantung', ctx.exception.errors)

    def test_multi_select_rejects_duplicates_and_non_list(self):
        for value in (['PJK', 'PJK'], 'PJK'):
            with self.subTest(value=value), self.assertRaises(WorkflowValidation) as ctx:
                self.save(3, {'faktor_risiko_kardio': value})
            self.assertIn('faktor_risiko_kardio', ctx.exception.errors)

    def test_every_declared_option_is_accepted(self):
        workflow = self.save(3, {
            'riwayat_jantung': list(RIWAYAT_JANTUNG_CHOICES),
            'faktor_risiko_kardio': list(FAKTOR_RISIKO_CHOICES),
        })
        self.assertEqual(workflow.draft_payload['3']['riwayat_jantung'], list(RIWAYAT_JANTUNG_CHOICES))

    def test_smoking_status_feeds_brinkman_without_band(self):
        workflow = self.save(3, {
            'status_merokok': 'AKTIF', 'batang_per_hari': 20, 'tahun_merokok': 15,
        })
        payload = workflow.draft_payload['3']
        self.assertEqual(payload['status_merokok'], 'AKTIF')
        self.assertEqual(indeks_brinkman(payload['batang_per_hari'], payload['tahun_merokok']), 300)
        self.assertNotIn('kategori_brinkman', payload)

    def test_smoking_status_outside_matrix_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(3, {'status_merokok': 'KADANG'})
        self.assertIn('status_merokok', ctx.exception.errors)

    def test_pregnancy_screening_is_stored_with_matrix_options(self):
        workflow = self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        self.assertEqual(workflow.draft_payload['3']['status_kehamilan_menyusui'], 'HAMIL')
        with self.assertRaises(WorkflowValidation):
            self.save(3, {'status_kehamilan_menyusui': 'MUNGKIN'}, workflow.version)

    def test_medication_reconciliation_is_stored(self):
        workflow = self.save(3, {
            'kepatuhan_obat': 'ADA_TIDAK_PATUH',
            'obat_rutin': ['ANTIPLATELET', 'STATIN'],
            'obat_rutin_terakhir': 'Malam sebelum kunjungan',
        })
        payload = workflow.draft_payload['3']
        self.assertEqual(payload['kepatuhan_obat'], 'ADA_TIDAK_PATUH')
        self.assertEqual(payload['obat_rutin'], ['ANTIPLATELET', 'STATIN'])
        self.assertEqual(payload['obat_rutin_terakhir'], 'Malam sebelum kunjungan')

    def test_every_declared_medication_group_is_accepted(self):
        workflow = self.save(3, {'obat_rutin': list(OBAT_RUTIN_CHOICES)})
        self.assertEqual(workflow.draft_payload['3']['obat_rutin'], list(OBAT_RUTIN_CHOICES))

class StepSixFisikKardioTest(RajalLapisDuaFixture):
    """F3.5/F3.6: dict ``fisik_kardio`` dan penanda anatomi tervalidasi."""

    def test_murmur_grade_and_location_are_stored_as_dict(self):
        workflow = self.save(6, {'fisik_kardio': {
            'murmur_derajat': '2/6', 'murmur_lokasi': 'MITRAL',
            'jvp': 'MENINGKAT', 'edema_ekstremitas': 'PRETIBIAL_RINGAN',
            'perfusi_perifer': 'AKRAL_HANGAT_CRT_NORMAL',
        }})
        stored = workflow.draft_payload['6']['fisik_kardio']
        self.assertEqual(stored['murmur_derajat'], '2/6')
        self.assertEqual(stored['murmur_lokasi'], 'MITRAL')
        self.assertEqual(stored['jvp'], 'MENINGKAT')

    def test_dotted_form_keys_are_nested_by_the_service(self):
        workflow = self.save(6, {
            'fisik_kardio.murmur_derajat': '4/6',
            'fisik_kardio.murmur_lokasi': 'AORTA',
        })
        self.assertEqual(workflow.draft_payload['6']['fisik_kardio'],
                         {'murmur_derajat': '4/6', 'murmur_lokasi': 'AORTA'})

    def test_murmur_grade_outside_one_to_six_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_derajat': '7/6'}})
        self.assertIn('fisik_kardio', ctx.exception.errors)

    def test_unknown_sub_key_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_warna': 'merah'}})
        self.assertIn('fisik_kardio', ctx.exception.errors)

    def test_marker_list_uses_igd_validation(self):
        marker = {'side': 'FRONT', 'x': 0.42, 'y': 0.55, 'kind': 'NYERI', 'label': 'Prekordial'}
        workflow = self.save(6, {'penanda_anatomi': [marker]})
        self.assertEqual(workflow.draft_payload['6']['penanda_anatomi'], [marker])

    def test_more_than_one_hundred_markers_is_rejected(self):
        marker = {'side': 'FRONT', 'x': 0.1, 'y': 0.1, 'kind': 'LUKA', 'label': 'x'}
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'penanda_anatomi': [marker] * 101})
        self.assertEqual(ctx.exception.errors['penanda_anatomi'],
                         ['Maksimal 100 penanda dalam daftar.'])

    def test_marker_outside_normalised_coordinates_is_rejected(self):
        for bad in ({'side': 'FRONT', 'x': 2, 'y': 0.3, 'kind': 'LUKA', 'label': 'X'},
                    {'side': 'FRONT', 'x': -0.1, 'y': 0.3, 'kind': 'LUKA', 'label': 'X'},
                    {'side': 'SIDE', 'x': 0.2, 'y': 0.3, 'kind': 'LUKA', 'label': 'X'}):
            with self.subTest(marker=bad), self.assertRaises(WorkflowValidation) as ctx:
                self.save(6, {'penanda_anatomi': [bad]})
            self.assertEqual(ctx.exception.errors['penanda_anatomi'],
                             ['Koordinat/label penanda tidak valid.'])

    def test_marker_kind_set_is_the_existing_schema_not_a_new_one(self):
        """Penanda memakai kind yang sudah ada; tidak ada kind kardiologi baru."""
        spec = RAJAL_JANTUNG_STEPS[6]
        field = next(item for item in spec.fields if item.name == 'penanda_anatomi')
        self.assertEqual(field.kind, 'markers')
        from pasien.anatomy_markers import KINDS
        self.assertEqual(KINDS, ('LUKA', 'NYERI', 'LAINNYA'))

class StepSixMurmurLokasiTest(RajalLapisDuaFixture):
    """A1 (AMBIGU-17b): lokasi murmur lima kode tertutup + teks untuk LAINNYA."""

    def test_valid_code_is_stored_as_code(self):
        workflow = self.save(6, {'fisik_kardio': {'murmur_lokasi': 'PULMONAL'}})
        self.assertEqual(workflow.draft_payload['6']['fisik_kardio'],
                         {'murmur_lokasi': 'PULMONAL'})

    def test_lainnya_stores_the_free_text(self):
        workflow = self.save(6, {'fisik_kardio': {
            'murmur_lokasi': 'LAINNYA',
            'murmur_lokasi_lainnya': 'Fokus aorta asendens, menjalar ke karotis',
        }})
        self.assertEqual(workflow.draft_payload['6']['fisik_kardio'], {
            'murmur_lokasi': 'LAINNYA',
            'murmur_lokasi_lainnya': 'Fokus aorta asendens, menjalar ke karotis',
        })

    def test_value_outside_the_closed_list_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_lokasi': 'Apeks'}})
        self.assertIn('fisik_kardio', ctx.exception.errors)

    def test_lainnya_without_text_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_lokasi': 'LAINNYA'}})
        self.assertIn('murmur_lokasi_lainnya', ctx.exception.errors['fisik_kardio'][0])
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_lokasi': 'LAINNYA',
                                          'murmur_lokasi_lainnya': '   '}})
        self.assertIn('murmur_lokasi_lainnya', ctx.exception.errors['fisik_kardio'][0])

    def test_standard_code_with_stray_text_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(6, {'fisik_kardio': {'murmur_lokasi': 'MITRAL',
                                          'murmur_lokasi_lainnya': 'sisa teks'}})
        self.assertIn('murmur_lokasi_lainnya', ctx.exception.errors['fisik_kardio'][0])

    def test_switching_away_from_lainnya_drops_the_stale_text(self):
        self.save(6, {'fisik_kardio': {'murmur_lokasi': 'LAINNYA',
                                       'murmur_lokasi_lainnya': 'Prekordial kiri'}})
        workflow = self.save(6, {'fisik_kardio': {'murmur_lokasi': 'TRIKUSPID'}}, version=1)
        self.assertEqual(workflow.draft_payload['6']['fisik_kardio'],
                         {'murmur_lokasi': 'TRIKUSPID'})

class StepFiveBiopsikososialTest(RajalLapisDuaFixture):
    """F3.7: psikologis, spiritual, dan dukungan sosial."""

    def test_biopsychosocial_fields_are_stored(self):
        workflow = self.save(5, {
            'kondisi_psikologis': 'CEMAS_RINGAN_SEDANG',
            'kebutuhan_spiritual': 'ADA',
            'keterangan_spiritual': 'Minta pendampingan rohani sebelum tindakan',
            'dukungan_sosial': 'TERBATAS',
        })
        payload = workflow.draft_payload['5']
        self.assertEqual(payload['kondisi_psikologis'], 'CEMAS_RINGAN_SEDANG')
        self.assertEqual(payload['kebutuhan_spiritual'], 'ADA')
        self.assertEqual(payload['dukungan_sosial'], 'TERBATAS')

    def test_social_support_alone_is_enough_and_optional(self):
        workflow = self.save(5, {'dukungan_sosial': 'BAIK'})
        self.assertEqual(workflow.draft_payload['5'], {'dukungan_sosial': 'BAIK'})

    def test_psychological_option_outside_matrix_is_rejected(self):
        with self.assertRaises(WorkflowValidation) as ctx:
            self.save(5, {'kondisi_psikologis': 'MARAH'})
        self.assertIn('kondisi_psikologis', ctx.exception.errors)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class PregnancyContraindicationTest(RajalLapisDuaFixture):
    """F3.3: status hamil/menyusui + peringatan kontraindikasi memblokir kirim."""

    def make_prescription(self, *, class_code, ingredient='ramipril', nama='Ramipril 5 mg'):
        cls = KelasTerapiObat.objects.create(kode=class_code, nama=f'Kelas {class_code}')
        generic = GenerikObat.objects.create(
            kode=f'g-{class_code}', nama=nama, kelas=cls, bentuk='TABLET', dispense_unit='tablet',
        )
        product = ProdukFarmasi.objects.create(
            kode=f'p-{class_code}', nama=nama, generik=generic, kind='OBAT', active=True,
            source_version='fixture', reviewed_by=self.nurse, price=Decimal('1000'),
            allowed_routes=['PO'],
        )
        KomposisiProdukFarmasi.objects.create(
            produk=product, ingredient_code=ingredient, nama=ingredient,
            strength=Decimal('5'), unit='mg',
        )
        self.visit.skrining_alergi_status = 'TIDAK_ADA'
        self.visit.save(update_fields=['skrining_alergi_status'])
        rx = ResepElektronik.objects.create(
            no_resep=f'RX-{class_code}', kunjungan=self.visit, dokter_peresep=self.dpjp_user,
            jenis_resep='RAWAT_JALAN', status='DRAFT', serving_unit=self.unit,
        )
        ResepDetail.objects.create(
            resep=rx, product=product, nama_obat=nama, dosis='5 mg', aturan_pakai='1x1',
            jumlah=30, harga_satuan=Decimal('1000'), kind='OBAT',
            quantity_decimal=Decimal('30'), reference_price=Decimal('1000'),
            product_snapshot={
                'id': product.pk, 'class_code': class_code, 'flags': [],
                'ingredients': [{'ingredient_code': ingredient, 'strength': '5', 'unit': 'mg'}],
            },
        )
        return rx

    def test_pregnant_patient_with_ace_inhibitor_is_blocked(self):
        self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        self.assertEqual(pregnancy_status(self.visit), 'HAMIL')
        rx = self.make_prescription(class_code='ACEI')

        findings = evaluate_prescription(rx)
        codes = [finding['code'] for finding in findings]
        self.assertIn('PREGNANCY_CONTRA', codes)
        finding = next(item for item in findings if item['code'] == 'PREGNANCY_CONTRA')
        self.assertTrue(finding['blocking'])
        self.assertIn('ACEI', finding['message'])

        # Memblokir pengiriman: jalur submit memanggil review_risks lebih dulu.
        with self.assertRaises(ValueError):
            review_risks(rx, self.dpjp_user, [])

    def test_breastfeeding_patient_with_statin_is_blocked(self):
        self.save(3, {'status_kehamilan_menyusui': 'MENYUSUI'})
        rx = self.make_prescription(class_code='STATIN', ingredient='simvastatin',
                                    nama='Simvastatin 20 mg')
        codes = [finding['code'] for finding in evaluate_prescription(rx)]
        self.assertIn('PREGNANCY_CONTRA', codes)

    def test_not_pregnant_patient_is_not_warned(self):
        self.save(3, {'status_kehamilan_menyusui': 'TIDAK_HAMIL_TIDAK_MENYUSUI'})
        rx = self.make_prescription(class_code='ACEI')
        codes = [finding['code'] for finding in evaluate_prescription(rx)]
        self.assertNotIn('PREGNANCY_CONTRA', codes)

    def test_pregnant_patient_without_contraindicated_class_is_not_warned(self):
        self.save(3, {'status_kehamilan_menyusui': 'HAMIL'})
        rx = self.make_prescription(class_code='ANALGESIK', ingredient='paracetamol',
                                    nama='Paracetamol 500 mg')
        codes = [finding['code'] for finding in evaluate_prescription(rx)]
        self.assertNotIn('PREGNANCY_CONTRA', codes)

    def test_matching_is_data_driven_from_catalogue_codes(self):
        self.assertEqual(contra_groups({'class_code': 'ACEI'}), {'ACEI'})
        self.assertEqual(
            contra_groups({'ingredients': [{'ingredient_code': 'warfarin'}]}), {'WARFARIN'})
        self.assertEqual(contra_groups({'class_code': 'kardiovaskular-antihipertensi'}), set())

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class LapisDuaRenderTest(RajalLapisDuaFixture):
    """Nilai yang tersimpan dirender ulang dengan pilihan yang sama."""

    def get_step(self, step):
        self.client.force_login(self.nurse)
        response = self.client.get(reverse('pasien:poli_workflow', args=[self.visit.pk]),
                                   {'step': step})
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_multiselect_renders_checked_options(self):
        self.save(3, {'riwayat_jantung': ['PJK'], 'faktor_risiko_kardio': ['HIPERTENSI']})
        body = self.get_step(3)
        self.assertIn('type="checkbox" name="riwayat_jantung" value="PJK" checked', body)
        self.assertIn('type="checkbox" name="faktor_risiko_kardio" value="HIPERTENSI" checked', body)
        self.assertIn('type="checkbox" name="riwayat_jantung" value="GAGAL_JANTUNG"', body)

    def test_murmur_selection_renders_as_selected_option(self):
        self.save(6, {'fisik_kardio': {'murmur_derajat': '2/6', 'murmur_lokasi': 'MITRAL'}})
        body = self.get_step(6)
        self.assertIn('name="fisik_kardio.murmur_derajat"', body)
        self.assertIn('<option value="2/6" selected>2/6</option>', body)
        self.assertIn('<option value="MITRAL" selected>', body)

    def test_free_text_field_is_hidden_unless_lainnya_is_chosen(self):
        self.save(6, {'fisik_kardio': {'murmur_lokasi': 'MITRAL'}})
        body = self.get_step(6)
        self.assertIn('data-poli-show-when="fisik_kardio.murmur_lokasi"', body)
        self.assertIn('name="fisik_kardio.murmur_lokasi_lainnya"', body)
        self.assertIn('data-poli-show-value="LAINNYA"', body)

    def test_lainnya_renders_the_free_text_with_its_value(self):
        self.save(6, {'fisik_kardio': {'murmur_lokasi': 'LAINNYA',
                                       'murmur_lokasi_lainnya': 'Prekordial kiri'}})
        body = self.get_step(6)
        self.assertIn('<option value="LAINNYA" selected>', body)
        self.assertIn('value="Prekordial kiri"', body)

    def test_panel_shows_brinkman_and_pregnancy_warning(self):
        self.save(3, {
            'batang_per_hari': 20, 'tahun_merokok': 15,
            'status_kehamilan_menyusui': 'HAMIL',
            'kepatuhan_obat': 'ADA_PATUH', 'obat_rutin': ['ANTIPLATELET'],
        })
        body = self.get_step(4)
        self.assertIn('Indeks Brinkman', body)
        self.assertIn('300', body)
        self.assertIn('Kontraindikasi kehamilan', body)
        self.assertIn('ACEI', body)
        self.assertIn('Antiplatelet', body)

    def test_marker_json_round_trips(self):
        marker = {'side': 'FRONT', 'x': 0.42, 'y': 0.55, 'kind': 'NYERI', 'label': 'Prekordial'}
        self.save(6, {'penanda_anatomi': [marker]})
        body = self.get_step(6)
        self.assertIn(json.dumps([marker]), body.replace('&quot;', '"'))
