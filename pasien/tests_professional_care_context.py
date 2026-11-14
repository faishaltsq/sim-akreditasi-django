from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from pasien.professional_test_support import ProfessionalCareCase


class ProfessionalContextTest(ProfessionalCareCase):
    def test_issued_personal_privilege_allows(self):
        context=self.context()
        self.assertEqual(context['performer_id'],str(self.employee.pk))
        self.assertEqual(context['spk_id'],str(self.spk.pk))
        self.assertEqual(context['grade_id'],str(self.grade.pk))

    def test_profile_without_employee_denied(self):
        self.employee.akun=None;self.employee.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_grade_missing_denied(self):
        self.employee.jenjang_master=None;self.employee.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_revoked_spk_denied(self):
        self.spk.is_active=False;self.spk.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_expired_snapshot_denied(self):
        self.snapshot.valid_until=timezone.localdate()-timedelta(days=1);self.snapshot.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_catalogue_is_not_an_individual_grant(self):
        self.privilege.status_spk='TIDAK_DIBERIKAN';self.privilege.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_supervision_cannot_be_self_certified(self):
        self.privilege.status_spk='DISETUJUI_SUPERVISI';self.privilege.save()
        with self.assertRaises(PermissionDenied):self.context()
        with self.assertRaises(PermissionDenied):self.context(supervisor=self.employee.pk)

    def test_no_mapping_denied(self):
        self.mapping.is_active=False;self.mapping.save()
        with self.assertRaises(PermissionDenied):self.context()

    def test_other_performer_without_grant_denied(self):
        from uuid import uuid4
        with self.assertRaises(PermissionDenied):self.context(performer=uuid4())

    def test_quote_unknown_is_none_not_zero(self):
        from klinis.services.professional_tariffs import quote_professional_service
        quote=quote_professional_service(self.visit,self.context(),self.service,at=timezone.now())
        self.assertEqual(quote['status'],'UNPRICED')
        self.assertIsNone(quote['unit_total'])
        self.assertTrue(quote['fingerprint'])
