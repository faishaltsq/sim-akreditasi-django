from datetime import date
from urllib.parse import urlparse

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from sdm.models import AktivitasOrientasi, HcGrant, Lamaran, Pelamar, ProgramOrientasi, UrutanNomorPegawai
from sdm.services.rekrutmen import hire_application
from sdm.tests.test_rekrutmen import LevelTwoBase


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PUBLIC_BASE_URL='https://arima.example.org')
class HiredActivationTests(LevelTwoBase):
    def setUp(self):
        super().setUp()
        self.config.can_view_hc = True
        self.config.can_manage_hc_employees = True
        self.config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        for capability in ('can_view_hc', 'can_manage_hc_employees'):
            HcGrant.objects.create(user=self.recruiter, capability=capability, unit_kerja=self.unit)
        candidate = Pelamar.objects.create(
            nama_lengkap='Pelamar Uji', email='hire@example.com',
            telepon='12345', tanggal_lahir=date(2000, 1, 2), pendidikan_terakhir='S1',
        )
        self.application = Lamaran.objects.create(
            lowongan=self.lowongan, pelamar=candidate,
            nama_pelamar=candidate.nama_lengkap, status='DITERIMA',
        )
        UrutanNomorPegawai.objects.create(
            scope='rekrutmen', period_start=date(2000, 1, 1),
            format_pattern='EMP-{year}-{counter:04d}',
        )
        program = ProgramOrientasi.objects.create(nama='Umum', jenis='UMUM')
        AktivitasOrientasi.objects.create(program=program, nama='Pengenalan')
        self.employee = hire_application(self.application, actor=self.recruiter, idempotency_key='hire')
        self.url = reverse('sdm:hired_account_invite', args=[self.application.pk])

    def test_hire_receives_link_and_activates_existing_account(self):
        self.assertFalse(self.employee.akun.has_usable_password())
        self.client.force_login(self.recruiter)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['hire@example.com'])
        self.assertIn(self.employee.akun.username, mail.outbox[0].body)
        link = next(word for word in mail.outbox[0].body.split() if word.startswith('https://arima.example.org/'))
        self.client.logout()
        response = self.client.post(urlparse(link).path, {
            'new_password1': 'StrongPass123!', 'new_password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.employee.akun.refresh_from_db()
        self.assertTrue(self.employee.akun.check_password('StrongPass123!'))
        self.assertEqual(self.employee.akun.profile.role, 'STAF_NAKES')
        self.assertEqual(self.employee.akun.profile.unit_kerja, self.unit)
        self.assertEqual(self.client.post(urlparse(link).path, {
            'new_password1': 'OtherPass123!', 'new_password2': 'OtherPass123!',
        }).status_code, 200)
        self.employee.akun.refresh_from_db()
        self.assertTrue(self.employee.akun.check_password('StrongPass123!'))

    def test_recruiter_without_unit_grant_cannot_send(self):
        outsider = self._user('other-recruiter')
        for capability in ('can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_recruitment'):
            HcGrant.objects.create(user=outsider, capability=capability, unit_kerja=self.other)
        self.client.force_login(outsider)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)

    def test_get_does_not_send_invitation(self):
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(len(getattr(mail, 'outbox', [])), 0)
