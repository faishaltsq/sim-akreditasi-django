"""Jenjang-based preseptor eligibility (plan RKK Fase R2)."""
from sdm.models import HcGrant, MasterJenjangProfesi, Pegawai, PenempatanPegawai


def eligible_preceptors(unit_kerja):
    """Pegawai aktif di `unit_kerja` yang boleh memverifikasi logbook.

    Kebijakan (master RKK): jenjang dengan urutan >= jenjang.preceptor_min_urutan
    pada profesinya sendiri, atau pemegang grant `can_review_hc_credentials`
    untuk unit tersebut.
    """
    unit_id = getattr(unit_kerja, 'pk', unit_kerja)
    placement_units = PenempatanPegawai.objects.filter(
        unit_kerja_id=unit_id, tanggal_selesai__isnull=True,
    ).values('pegawai_id')

    qualified_pk = [
        pegawai.pk
        for pegawai in Pegawai.objects.filter(
            pk__in=placement_units, status='AKTIF',
        ).select_related('jenjang_master')
        if (jen := pegawai.jenjang_master) is not None
        and jen.urutan >= jen.preceptor_min_urutan
    ]
    granted_user_ids = HcGrant.objects.filter(
        capability='can_review_hc_credentials', is_active=True,
        unit_kerja_id=unit_id,
    ).values_list('user_id', flat=True)
    granted_pk = set(
        Pegawai.objects.filter(
            akun_id__in=granted_user_ids, status='AKTIF',
            pk__in=placement_units,
        ).values_list('pk', flat=True)
    )
    return Pegawai.objects.filter(
        pk__in=set(qualified_pk) | granted_pk,
    ).select_related('jenjang_master', 'profesi_master')
