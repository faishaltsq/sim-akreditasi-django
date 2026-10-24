"""Builder tautan navigasi Integrated Control.

Fungsi murni: tidak menyentuh DB dan tidak membaca ``request``. Semua tautan
dibangun dari unit yang sudah di-resolve ``_resolve_unit``, sehingga query
string yang tidak tepercaya tidak pernah bocor ke ``href``.

Rute tujuan tetap menjadi batas integrasi: tidak ada halaman perantara baru.
"""
from urllib.parse import urlencode

from django.urls import reverse


def _action(key, label, route, *, scope, **query):
    href = reverse(route)
    if query:
        href += '?' + urlencode(query)
    return {'key': key, 'label': label, 'href': href, 'scope': scope}


def module_actions(portal, *, unit, year, is_manager=False,
                   allowed_patient_modules=None, layanan=None):
    """Tautan modul operasional untuk satu portal; kosong bila tidak relevan."""
    if unit is None:
        return []
    if portal == 'risiko':
        return [
            _action('risiko', 'Buka daftar risiko', 'akreditasi:risiko_daftar',
                    scope='Unit aktif', unit=unit.pk),
            _action('monev', 'Monitoring dan evaluasi', 'akreditasi:risiko_monev',
                    scope='Unit aktif', unit=unit.pk, tahun=year),
            _action('fmea', 'FMEA / RCA', 'akreditasi:risiko_fmea_rca',
                    scope='Unit aktif', unit=unit.pk),
            _action('insiden', 'Laporan insiden', 'akreditasi:insiden_daftar',
                    scope='Unit aktif', unit=unit.pk),
            _action('indikator', 'Indikator mutu', 'akreditasi:indikator_dashboard',
                    scope='Sesuai akses', tahun=year),
            _action('laporan', 'Laporan mutu', 'akreditasi:laporan_mutu_daftar',
                    scope='Sesuai akses'),
        ]
    if portal == 'dokumen':
        actions = [
            _action('dokumen', 'Buka dokumen akreditasi', 'akreditasi:dokumen_hub',
                    scope='Sesuai akses'),
        ]
        if is_manager:
            actions.append(_action('rekap', 'Rekap dan scoring', 'akreditasi:rekap',
                                   scope='Sesuai akses'))
        actions.append(_action('laporan', 'Laporan mutu', 'akreditasi:laporan_mutu_daftar',
                               scope='Sesuai akses'))
        return actions
    if portal == 'emr':
        from pasien.models import POLIKLINIK_CHOICES
        from .layanan_unit import POLI_UNIT_CODE

        allowed = set(allowed_patient_modules or ())
        layanan = layanan or {}
        choices = dict(POLIKLINIK_CHOICES)
        actions = []
        if 'rajal' in allowed:
            for choice, code in POLI_UNIT_CODE.items():
                if code and code == unit.code:
                    actions.append(_action(
                        'rajal', 'Buka poli', 'pasien:rajal_dashboard',
                        scope='Poli aktif', poli=choices[choice],
                    ))
                    break
        if unit.code == 'IGD' and 'igd' in allowed:
            actions.append(_action('igd', 'Buka IGD', 'pasien:igd_dashboard',
                                   scope='IGD RS'))
        if layanan.get('owns_beds') and 'ranap' in allowed:
            actions.append(_action('beds', 'Manajemen tempat tidur',
                                   'pasien:bed_management', scope='Seluruh RS'))
        return actions
    return []


def portal_navigation(portals, *, unit, active_portal, can_view_hc):
    """Tab antar sub-dasbor; tab Human Capital hanya bila pengguna berhak."""
    items = []
    labels = {'risiko': 'Risiko', 'emr': 'EMR', 'dokumen': 'Dokumen',
              'human_capital': 'Human Capital'}
    hub = reverse('akreditasi:kontrol_hub')
    suffix = '?' + urlencode({'unit': unit.pk}) if unit is not None else ''
    items.append({'key': 'hub', 'label': 'Ringkasan', 'href': hub + suffix,
                  'active': active_portal == 'hub'})
    for portal in portals:
        if portal['key'] == 'human_capital' and not can_view_hc:
            continue
        href = reverse(portal['url_name'])
        if portal['key'] != 'human_capital':
            href += suffix
        items.append({'key': portal['key'], 'label': labels[portal['key']],
                      'href': href, 'active': active_portal == portal['key']})
    return items
