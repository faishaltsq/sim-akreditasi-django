"""Human Capital navigation registry (Task A2).

Single source of truth for the ten-group HC navigation tree. Consumed by the
context processor, dashboard cards, and _navigasi partial. Uses the same
authorization resolver as object access, so menu visibility is never the
enforcement boundary.
"""

from dataclasses import dataclass, field

from django.urls import NoReverseMatch, reverse

from sdm.akses import require_hc_capability

GROUP_ICONS = {
    'dasbor': 'bi-house-door-fill',
    'perencanaan': 'bi-diagram-3-fill',
    'database': 'bi-people-fill',
    'presensi': 'bi-clock-fill',
    'kredensial': 'bi-award-fill',
    'kinerja': 'bi-bar-chart-line-fill',
    'uraian_tugas': 'bi-file-text-fill',
    'k3': 'bi-shield-fill-cross',
    'portal': 'bi-box-arrow-in-right',
    'laporan': 'bi-file-earmark-bar-graph-fill',
}


@dataclass
class NavItem:
    key: str
    label: str
    url_name: str | None = None
    url_kwargs: dict = field(default_factory=dict)
    capability: str | None = None
    unit: object = None  # resolved at render time
    employee: object = None  # resolved at render time
    children: list = field(default_factory=list)
    icon: str = 'bi-circle'
    disabled_reason: str = ''


@dataclass
class NavGroup:
    key: str
    label: str
    icon: str
    items: list = field(default_factory=list)
    disabled_reason: str = ''


def _url(item: NavItem):
    if not item.url_name:
        return None
    try:
        return reverse('sdm:' + item.url_name, kwargs=item.url_kwargs)
    except NoReverseMatch:
        return None


def _authorized(user, item: NavItem):
    """True if the caller may see this item (menu discovery, not enforcement)."""
    if item.disabled_reason:
        return False
    if item.capability:
        try:
            require_hc_capability(
                user,
                item.capability,
                unit=item.unit,
                employee=item.employee,
            )
        except PermissionDenied:
            return False
    return True


from django.core.exceptions import PermissionDenied  # noqa: E402


def navigation_tree(user, *, unit=None, employee=None):
    """Return the ten-group HC navigation tree filtered by authorization."""
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return []

    def item(key, label, *, url_name=None, url_kwargs=None, capability=None, icon='bi-circle', disabled_reason=''):
        return NavItem(
            key=key,
            label=label,
            url_name=url_name,
            url_kwargs=url_kwargs or {},
            capability=capability,
            unit=unit,
            employee=employee,
            icon=icon,
            disabled_reason=disabled_reason,
        )

    tree = [
        NavGroup(
            key='dasbor',
            label='Dasbor & Analitik',
            icon=GROUP_ICONS['dasbor'],
            items=[
                item('dasbor_ringkasan', 'Ringkasan, EWS & Tugas', url_name='dashboard',
                     capability='can_view_hc'),
                item('dasbor_analitik', 'Analitik, Talent & Skenario', url_name='analitik_dashboard',
                     capability='can_view_hc_analytics'),
            ],
        ),
        NavGroup(
            key='perencanaan',
            label='Perencanaan & Formasi',
            icon=GROUP_ICONS['perencanaan'],
            items=[
                item('perencanaan_beban_kerja', 'Beban Kerja, Kalkulator FTE, Peta & Gap',
                     capability='can_plan_hc_workforce'),
                item('perencanaan_formasi', 'Usulan Formasi, Rekrutmen & Seleksi',
                     url_name='formasi_list',
                     capability='can_plan_hc_workforce'),
            ],
        ),
        NavGroup(
            key='database',
            label='Database & e-File',
            icon=GROUP_ICONS['database'],
            items=[
                item('database_direktori', 'Direktori', url_name='pegawai_list',
                     capability='can_view_hc'),
                item('database_tambah_staf', 'Tambah Staf', url_name='pegawai_create',
                     capability='can_manage_hc_employees'),
                item('database_impor_excel', 'Impor Excel',
                     capability='can_manage_hc_employees'),
                item('database_profil_legalitas', 'Profil, Legalitas, Pendidikan & Riwayat',
                     capability='can_view_hc'),
                item('database_magres', 'Mahasiswa / Residen / Magang',
                     capability='can_view_hc'),
            ],
        ),
        NavGroup(
            key='presensi',
            label='Presensi & Operasional Shift',
            icon=GROUP_ICONS['presensi'],
            disabled_reason='Belum diaktifkan',
            items=[
                item('presensi_jadwal', 'Jadwal Dinas, Presensi & Koreksi', capability='can_view_hc'),
                item('presensi_jam_efektif', 'Jam Efektif & Ekspor Remunerasi', capability='can_export_hc'),
            ],
        ),
        NavGroup(
            key='kredensial',
            label='Kredensial & Kewenangan Klinis',
            icon=GROUP_ICONS['kredensial'],
            items=[
                item('kredensial_pengajuan', 'Pengajuan Saya, Verifikasi & Komite',
                     capability='can_review_hc_credentials'),
                item('kredensial_rk', 'RKK, Penerbitan/Rekredensial SPK & Peta Kewenangan',
                     capability='can_review_hc_credentials'),
            ],
        ),
        NavGroup(
            key='kinerja',
            label='Kinerja, Orientasi & Pengembangan',
            icon=GROUP_ICONS['kinerja'],
            items=[
                item('kinerja_orientasi', 'Orientasi, KPI/SKP, OPPE & FPPE',
                     capability='can_manage_hc_appraisals'),
                item('kinerja_tna', 'TNA, Kalender Diklat, Kehadiran & Sertifikasi',
                     capability='can_manage_hc_training'),
            ],
        ),
        NavGroup(
            key='uraian_tugas',
            label='Uraian Tugas & Akses RME',
            icon=GROUP_ICONS['uraian_tugas'],
            items=[
                item('uraian_tugas_master', 'Master/Versi Jobdesc & Penerimaan Staf',
                     capability='can_view_hc'),
                item('uraian_tugas_klinis', 'Kebijakan Akses Klinis & Riwayat Keputusan',
                     capability='can_view_hc'),
            ],
        ),
        NavGroup(
            key='k3',
            label='Kesehatan & Keselamatan Staf',
            icon=GROUP_ICONS['k3'],
            items=[
                item('k3_risiko', 'Risiko K3, Insiden & Tindak Lanjut',
                     capability='hc_health_write'),
                item('k3_mcu', 'MCU / Imunisasi',
                     capability='hc_health_write'),
            ],
        ),
        NavGroup(
            key='portal',
            label='Portal Mandiri',
            icon=GROUP_ICONS['portal'],
            items=[
                item('portal_profil', 'Profil Saya, Dokumen & Notifikasi',
                     url_name='pegawai_detail', url_kwargs={'employee_id': employee} if employee else None,
                     capability='can_view_hc'),
                item('portal_pelatihan_cuti', 'Usulan Pelatihan & Cuti',
                     capability='can_view_hc'),
            ],
        ),
        NavGroup(
            key='laporan',
            label='Laporan & Bukti Akreditasi',
            icon=GROUP_ICONS['laporan'],
            items=[
                item('laporan_audit', 'Audit e-File, STR/SIP & Jam Pelatihan Tahunan',
                     capability='can_view_hc_analytics'),
                item('laporan_kps', 'Paket Sampel KPS & Publikasi Bukti Teredaksi',
                     capability='can_export_hc'),
            ],
        ),
    ]

    result = []
    for group in tree:
        visible_items = [it for it in group.items if _authorized(user, it)]
        if not visible_items:
            continue
        result.append(NavGroup(
            key=group.key,
            label=group.label,
            icon=group.icon,
            items=visible_items,
            disabled_reason=group.disabled_reason,
        ))
    return result
