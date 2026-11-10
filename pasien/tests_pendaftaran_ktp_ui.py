from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from akreditasi.models import UnitKerja
from accounts.models import UserProfile


class PendaftaranKtpUiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='petugas_ui', password='password123')
        self.unit_admisi, _ = UnitKerja.objects.get_or_create(
            code='ADMISI',
            defaults={'name': 'Unit Pendaftaran & Admisi', 'level': 3}
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='ADMIN_RS',
            unit_kerja=self.unit_admisi
        )
        self.client.login(username='petugas_ui', password='password123')

    def test_pendaftaran_dashboard_renders_ktp_ocr_and_sticky_footer(self):
        url = reverse('pasien:pendaftaran_dashboard')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')

        # 1. Enctype multipart for KTP upload
        self.assertIn('enctype="multipart/form-data"', content)

        # 2. KTP upload / scan triggers & modal
        self.assertIn('modalScanKtp', content)
        self.assertIn('btnBukaModalKtp', content)
        self.assertIn('foto_ktp', content)

        # 3. Flexible date & real-time age indicator
        self.assertIn('tglLahirBaru', content)
        self.assertIn('badgeUsiaBaru', content)

        # 4. Sticky submit footer for Kotak 2
        self.assertIn('sticky-action-footer', content)

        # 5. STARKES SKP 1 & MRMIK verification badges
        self.assertIn('SKP 1', content)
        self.assertIn('MRMIK', content)
