from django.test import TestCase
from akreditasi.models import Category, Framework, StandardItem


class CategoryEpGapTests(TestCase):
    def setUp(self):
        self.framework = Framework.objects.create(
            name='STARKES 2024', version='2024', edition='2024', is_active=True
        )

    def test_gap_is_zero_when_catalogue_matches_target(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=2
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP b'
        )
        self.assertEqual(category.ep_gap, 0)

    def test_gap_reports_missing_ep_rows(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=78
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        self.assertEqual(category.ep_gap, 77)

    def test_gap_is_zero_without_target(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=0
        )
        self.assertEqual(category.ep_gap, 0)

    def test_gap_never_goes_negative(self):
        category = Category.objects.create(
            framework=self.framework, code='KPS', name='KPS', target_ep_count=1
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP b'
        )
        self.assertEqual(category.ep_gap, 0)

    def test_sidebar_marks_categories_with_missing_ep(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile

        category = Category.objects.create(
            framework=self.framework, code='KPS', name='Kualifikasi & Pendidikan Staf',
            target_ep_count=78,
        )
        StandardItem.objects.create(
            category=category, sub_standard='KPS 1', code='KPS 1 EP a'
        )
        user = get_user_model().objects.create_user(username='gap-viewer')
        UserProfile.objects.create(user=user, role='ADMIN_RS')
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'belum terpasang')
