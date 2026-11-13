from decimal import Decimal
from uuid import uuid4
from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, override_settings
from klinis.models import MasterIcd10, SdkiDiagnosis, SlkiLuaran, SikiIntervensi, Pemetaan3S
from pasien.tests_igd_workflow import IgdWorkflowTest


class QuantityTest(SimpleTestCase):
    def test_fixed_fractional_quantity(self):
        from pasien.services.prescriptions import calculate_quantity
        result = calculate_quantity({'schema_version':1,'frequency':'FIXED','times_per_day':'2',
            'dose':'0.5','dose_unit':'tablet','duration_days':'3'}, {'dispense_unit':'tablet','dose_unit':'tablet'})
        self.assertEqual(result['quantity'], Decimal('3'))

    def test_prn_and_unknown_conversion_are_not_guessed(self):
        from pasien.services.prescriptions import calculate_quantity
        for regimen in [
            {'schema_version':1,'frequency':'PRN','dose':'1','dose_unit':'tablet','duration_days':'3'},
            {'schema_version':1,'frequency':'FIXED','times_per_day':'2','dose':'100','dose_unit':'mg','duration_days':'3'},
        ]:
            self.assertTrue(calculate_quantity(regimen, {'dispense_unit':'tablet','dose_unit':'tablet'})['requires_manual_quantity'])

    def test_nonfinite_and_negative_values_rejected(self):
        from pasien.services.prescriptions import calculate_quantity
        for value in ['NaN','Infinity','-1','0']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_quantity({'schema_version':1,'frequency':'FIXED','times_per_day':'2',
                    'dose':value,'dose_unit':'tablet','duration_days':'3'}, {'dispense_unit':'tablet','dose_unit':'tablet'})


class ComponentPlanningTest(IgdWorkflowTest):
    def test_nursing_component_modes_are_independent(self):
        from pasien.services.igd_assessment_workflow import save_step
        self.user.profile.profesi = 'PERAWAT'
        self.user.profile.save(update_fields=['profesi'])
        self.visit.diagnosa_masuk = 'Diagnosis manual lama'
        self.visit.save(update_fields=['diagnosa_masuk'])
        sdki = SdkiDiagnosis.objects.create(kode='D.QA', nama='Diagnosis uji')
        slki = SlkiLuaran.objects.create(kode='L.QA', nama='Luaran uji')
        siki = SikiIntervensi.objects.create(kode='I.QA', nama='Intervensi uji')
        Pemetaan3S.objects.create(sdki=sdki, slki=slki, siki=siki)
        save_step(self.visit.pk,self.user,8,{'component_modes':{'sdki':'MASTER','slki':'MANUAL','siki':'MASTER'},
            'diagnosa_keperawatan_sdki':'D.QA','luaran_keperawatan_slki':'Target manual',
            'intervensi_keperawatan_siki':'I.QA'},0)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.diagnosa_masuk,'Diagnosis manual lama')
        self.assertEqual(self.visit.luaran_keperawatan_slki,'Target manual')
        self.assertEqual(self.visit.diagnosis_provenance['components']['siki']['mode'],'MASTER')

    def test_nurse_cannot_write_medical_component(self):
        from pasien.services.igd_assessment_workflow import save_step
        self.user.profile.profesi='PERAWAT'
        self.user.profile.save(update_fields=['profesi'])
        with self.assertRaises(PermissionDenied):
            save_step(self.visit.pk,self.user,8,{'component_modes':{'medical':'MANUAL'},'diagnosa_masuk':'Forged'},0)


class AncillaryTest(IgdWorkflowTest):
    def item(self):
        Node=apps.get_model('klinis','KategoriPenunjang'); Item=apps.get_model('klinis','ItemPenunjang')
        a=Node.objects.create(kode='LAB-QA',nama='Laboratorium',level=1)
        b=Node.objects.create(kode='KLINIK-QA',nama='Klinik',level=2,parent=a)
        c=Node.objects.create(kode='HEM-QA',nama='Hematologi',level=3,parent=b)
        return Item.objects.create(kode='CBC-QA',nama='Darah lengkap',group=c,jenis_order='LAB',
            destination=self.unit,active=True,source_version='fixture',reviewed_by=self.user)

    def test_batch_order_is_atomic_and_replay_safe(self):
        from pasien.services.igd_actions import perform_action
        item=self.item(); key=str(uuid4())
        fields={'items':[{'item_id':item.pk,'prioritas':'CITO','indication':'Demam uji','preparation':{}}]}
        first=perform_action(self.visit.pk,self.user,'order_batch',fields,0,key)
        replay=perform_action(self.visit.pk,self.user,'order_batch',fields,0,key)
        self.assertEqual(first['order_ids'],replay['order_ids'])
        self.assertEqual(self.visit.order_penunjang.count(),1)
        self.assertFalse(self.visit.billing.exists())
        bad={'items':[fields['items'][0],{**fields['items'][0],'item_id':999999}]}
        with self.assertRaises(ValueError):
            perform_action(self.visit.pk,self.user,'order_batch',bad,first['version'],str(uuid4()))
        self.assertEqual(self.visit.order_penunjang.count(),1)

    def test_inactive_parent_and_wrong_path_rejected(self):
        from klinis.services.penunjang_catalogue import resolve_items
        item=self.item(); item.group.active=False; item.group.save()
        with self.assertRaises(ValueError):
            resolve_items(self.user,[item.pk])


class PrescriptionTest(IgdWorkflowTest):
    def product(self, code='PARA-QA', ingredient='para'):
        Class=apps.get_model('klinis','KelasTerapiObat'); Generic=apps.get_model('klinis','GenerikObat')
        Product=apps.get_model('klinis','ProdukFarmasi'); Ingredient=apps.get_model('klinis','KomposisiProdukFarmasi')
        cls,_=Class.objects.get_or_create(kode='ANALGESIK-QA',defaults={'nama':'Analgesik'})
        generic=Generic.objects.create(kode=code,nama='Paracetamol 500 mg',kelas=cls,bentuk='TABLET',dispense_unit='tablet')
        product=Product.objects.create(kode=code,nama=code,generik=generic,kind='OBAT',active=True,
            source_version='fixture',reviewed_by=self.user,price=Decimal('1000'),allowed_routes=['PO'])
        Ingredient.objects.create(produk=product,ingredient_code=ingredient,nama=ingredient,strength=Decimal('500'),unit='mg')
        return product

    def create_draft(self, product):
        from pasien.services.igd_actions import perform_action
        apps.get_model('pasien','PharmacyServiceGrant').objects.get_or_create(user=self.user,unit=self.unit)
        return perform_action(self.visit.pk,self.user,'prescription_save',{'serving_unit_id':self.unit.pk,'lines':[{'product_id':product.pk,
            'regimen':{'schema_version':1,'frequency':'FIXED','times_per_day':'2','dose':'1',
            'dose_unit':'tablet','duration_days':'3','route':'PO','timing':'PC'},'kind':'OBAT'}]},0,str(uuid4()))

    def test_draft_submit_dispense_and_completion_no_duplicate_charge(self):
        from pasien.services.igd_actions import perform_action
        from pasien.services.prescriptions import transition_prescription
        result=self.create_draft(self.product())
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        self.assertEqual(rx.status,'DRAFT'); self.assertFalse(self.visit.billing.exists())
        self.visit.skrining_alergi_status='TIDAK_ADA'
        self.visit.save(update_fields=['skrining_alergi_status'])
        submitted=perform_action(self.visit.pk,self.user,'prescription_submit',{'prescription_id':rx.pk,
            'acknowledgements':[]},result['version'],str(uuid4()))
        rx.refresh_from_db(); self.assertEqual(rx.status,'DIKIRIM')
        self.user.profile.profesi='APOTEKER'; self.user.profile.save(update_fields=['profesi'])
        transition_prescription(self.user,rx.pk,'dispensing',rx.version,str(uuid4()))
        rx.refresh_from_db(); key=str(uuid4())
        transition_prescription(self.user,rx.pk,'selesai',rx.version,key)
        transition_prescription(self.user,rx.pk,'selesai',rx.version,key)
        self.assertEqual(self.visit.billing.count(),1)
        self.assertEqual(self.visit.billing.get().kuantitas,Decimal('6'))

    def test_allergy_and_duplicate_ingredient_detected(self):
        from pasien.services.medication_safety import evaluate_prescription
        result=self.create_draft(self.product())
        rx=apps.get_model('pasien','ResepElektronik').objects.get(pk=result['prescription_id'])
        apps.get_model('pasien','AlergiPasienTerstruktur').objects.create(pasien=self.patient,
            ingredient_code='para',reaction='Ruam',recorded_by=self.user)
        risk=evaluate_prescription(rx)
        self.assertIn('ALLERGY', [r['code'] for r in risk])
        self.assertTrue(next(r for r in risk if r['code']=='ALLERGY')['blocking'])

    def test_nurse_cannot_create_prescription(self):
        from pasien.services.igd_actions import perform_action
        self.user.profile.profesi='PERAWAT';self.user.profile.save(update_fields=['profesi'])
        with self.assertRaises(PermissionDenied):
            perform_action(self.visit.pk,self.user,'prescription_save',{'lines':[]},0,str(uuid4()))
