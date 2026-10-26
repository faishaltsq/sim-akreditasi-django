from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


HC_CAPABILITY_CHOICES = [
    ('can_view_hc', 'Lihat data SDM'),
    ('can_manage_hc_employees', 'Kelola data pegawai'),
    ('can_manage_hc_documents', 'Kelola dokumen kepegawaian'),
    ('can_plan_hc_workforce', 'Kelola perencanaan ketenagaan'),
    ('can_verify_hc_formasi', 'Verifikasi tinjauan formasi (HRD)'),
    ('can_verify_hc_formasi_budget', 'Verifikasi anggaran formasi (Keuangan)'),
    ('can_approve_hc_formasi', 'Pengesahan formasi (Direktur)'),
    ('can_manage_hc_recruitment', 'Kelola rekrutmen'),
    ('can_review_hc_credentials', 'Tinjau kredensial'),
    ('hc_verify_credentials', 'Verifikasi Kredensial (SDM)'),
    ('hc_review_subkomite', 'Review Subkomite Kredensial'),
    ('hc_recommend_komite', 'Rekomendasi Ketua Komite'),
    ('hc_approve_credentials', 'Pengesahan Kredensial (Direktur)'),
    ('can_manage_hc_orientation', 'Kelola orientasi'),
    ('can_manage_hc_appraisals', 'Kelola penilaian kinerja'),
    ('can_manage_hc_training', 'Kelola pelatihan'),
    ('can_view_hc_analytics', 'Lihat analitik SDM'),
    ('can_manage_hc_talent', 'Kelola talent dan suksesi'),
    ('can_export_hc', 'Ekspor data SDM'),
    ('hc_health_read', 'Baca data kesehatan kerja'),
    ('hc_health_write', 'Kelola data kesehatan kerja'),
    ('hc_health_break_glass', 'Akses darurat kesehatan kerja'),
]


class HcGrant(models.Model):
    CAPABILITY_CHOICES = HC_CAPABILITY_CHOICES

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='hc_grants',
        verbose_name='Akun Penerima',
    )
    capability = models.CharField(
        'Kapabilitas', max_length=40, choices=HC_CAPABILITY_CHOICES
    )
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='hc_grants',
        verbose_name='Unit Lingkup',
        help_text='Kosong hanya untuk lingkup rumah sakit yang diberikan secara eksplisit.',
    )
    include_descendants = models.BooleanField(
        'Termasuk unit turunan', default=False
    )
    valid_from = models.DateField('Berlaku Mulai', default=timezone.localdate)
    valid_until = models.DateField('Berlaku Sampai', null=True, blank=True)
    is_active = models.BooleanField('Aktif', default=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hc_grants_given',
        verbose_name='Pemberi Hak',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Hak Akses Human Capital'
        verbose_name_plural = 'Hak Akses Human Capital'
        ordering = ['user_id', 'capability']
        indexes = [
            models.Index(
                fields=['user', 'capability', 'is_active'],
                name='hcgrant_usr_cap_act_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True)
                | Q(valid_until__gte=F('valid_from')),
                name='sdm_hcgrant_validity_order',
            ),
        ]

    def __str__(self):
        scope = self.unit_kerja.code if self.unit_kerja_id else 'RS'
        return f'{self.user_id}: {self.capability} [{scope}]'
