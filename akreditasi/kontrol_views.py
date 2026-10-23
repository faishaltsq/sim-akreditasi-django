"""
View dasbor eksekutif "ARIMA HOSPITAL INTEGRATED CONTROL".

Satu pintu masuk (``kontrol_hub``) → tiga sub-dasbor: risiko, EMR, dokumen.
Semua halaman di sini memakai shell tanpa sidebar (``kontrol/base_kontrol.html``);
setelah memilih unit, tautan "buka modul" mengarah ke halaman lama yang tetap
bersidebar.

Tidak ada model baru dan tidak ada migration — angka dibaca lewat
``kontrol_data``.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .kontrol_data import build_unit_snapshot, sample_units, snapshot_cached
from .models import UnitKerja
from .security_utils import rate_limit

SUBDASHBOARDS = (
    {
        'key': 'risiko',
        'url_name': 'akreditasi:kontrol_risiko',
        'title': 'Integrated Risk & Patient Safety Control',
        'subtitle': 'Risiko, insiden, RTL, indikator mutu — dengan AI',
        'icon': 'bi-shield-fail',
        'accent': 'linear-gradient(135deg,#7f1d1d,#dc2626)',
    },
    {
        'key': 'emr',
        'url_name': 'akreditasi:kontrol_emr',
        'title': 'Smart EMR & Clinical Quality STARKES',
        'subtitle': 'Kunjungan aktif, CPPT, asesmen, kredensial PPA — dengan AI',
        'icon': 'bi-activity',
        'accent': 'linear-gradient(135deg,#0c4a6e,#0ea5e9)',
    },
    {
        'key': 'dokumen',
        'url_name': 'akreditasi:kontrol_dokumen',
        'title': 'Electronic Accreditation Document & Automation Hub',
        'subtitle': 'Kepatuhan EP, bukti, registry mutu — dengan AI',
        'icon': 'bi-folder2-open',
        'accent': 'linear-gradient(135deg,#3f2d1a,#b45309)',
    },
    {
        'key': 'human_capital',
        'url_name': 'sdm:dashboard',
        'title': 'Arima Human Capital',
        'subtitle': 'Perencanaan tenaga, kepegawaian, kredensial, diklat, dan kesehatan kerja',
        'icon': 'bi-people-fill',
        'accent': 'linear-gradient(135deg,#134e4a,#0d9488)',
        'requires_hc': True,
    },
)


def _profile(request):
    return getattr(request.user, 'profile', None)


def _resolve_unit(request, profile):
    """Unit aktif: paksa unit milik user unit-scoped, selain itu dari ?unit=."""
    requested = request.GET.get('unit')
    if profile is not None and profile.is_unit_scoped and profile.unit_kerja_id:
        forced = profile.unit_kerja
        if requested and str(forced.pk) != str(requested):
            messages.info(request, f'Cakupan akun dibatasi ke {forced.name}.')
        return forced

    if requested:
        unit = UnitKerja.objects.filter(pk=requested, is_active=True).first()
        if unit:
            return unit

    units = sample_units(1)
    return units[0] if units else None


def _common_context(request, unit, profile):
    units = list(sample_units(12))
    if profile is not None and profile.is_unit_scoped and profile.unit_kerja:
        units = [profile.unit_kerja]
    elif unit and unit not in units:
        units = [unit] + units
    return {
        'unit': unit,
        'unit_options': units,
        'profile': profile,
        'subdashboards': SUBDASHBOARDS,
        'is_unit_scoped': bool(profile and profile.is_unit_scoped),
    }


@login_required
def kontrol_hub(request):
    profile = _profile(request)
    unit = _resolve_unit(request, profile)
    snapshot = snapshot_cached(unit, profile) if unit else None

    portal_cards = []
    if snapshot:
        risk = snapshot['risk']
        emr = snapshot['emr']
        ep = snapshot['ep']
        ind = snapshot['indicator']

        metrics = {
            'risiko': {
                'headline': risk['high_count'] if risk['total'] else '—',
                'headline_label': 'risiko tinggi / sangat tinggi',
                'foot': (f"{risk['overdue_rtl']} RTL lewat tenggat · "
                         f"{snapshot['incident']['open']} insiden terbuka"
                         if risk['total'] else 'Belum ada risiko terdaftar di unit ini'),
                'band': ('watch' if not risk['total'] else
                         'critical' if risk['high_count'] else 'good'),
                'band_label': ('Belum ada data' if not risk['total'] else
                               'Perlu tindakan' if risk['high_count'] else 'Terkendali'),
            },
            'emr': {
                'headline': emr['active_total'] if emr['active_total'] else '—',
                'headline_label': 'kunjungan aktif',
                'foot': (f"{emr['cppt_gap']} tanpa CPPT · {emr['assessment_gap']} tanpa asesmen risiko"
                         if emr['active_total'] else 'Belum ada kunjungan aktif'),
                'band': ('watch' if not emr['active_total'] else
                         'watch' if (emr['cppt_gap'] or 0) else 'good'),
                'band_label': ('Belum ada data' if not emr['active_total'] else
                               'Perlu tindakan' if (emr['cppt_gap'] or 0) else 'Terkendali'),
            },
            'dokumen': {
                'headline': f"{ep['pct']}%" if ep['pct'] is not None else '—',
                'headline_label': 'cakupan EP RS',
                'foot': (f"{ep['unit_filled']} item berskor di unit ini · "
                         f"{ep['evidence_total']} dokumen bukti"),
                'band': 'watch',
                'band_label': ('Belum ada data' if ep['pct'] is None else
                               'Jauh dari target' if ep['pct'] < 50 else
                               'Perlu dorongan' if ep['pct'] < 80 else 'Baik'),
            },
        }

        for item in SUBDASHBOARDS:
            if item.get('requires_hc') and not _can_view_human_capital(request.user):
                continue
            base = dict(item)
            card = metrics.get(item['key'], {})
            card.update(base)
            card['url'] = reverse(item['url_name'])
            if item.get('requires_hc'):
                card.update(_human_capital_card(request.user, unit))
            card.setdefault('band', 'watch')
            card.setdefault('band_label', '')
            card.setdefault('headline', '—')
            card.setdefault('headline_label', '')
            card.setdefault('foot', '')
            portal_cards.append(card)

    return render(request, 'akreditasi/kontrol/hub.html', {
        **_common_context(request, unit, profile),
        'snapshot': snapshot,
        'portal_cards': portal_cards,
    })


def _can_view_human_capital(user):
    from sdm.akses import visible_units

    return visible_units(user, capability='can_view_hc').exists()


def _human_capital_card(user, unit):
    """Build the fourth card metric from real, permission-scoped HC data."""
    from sdm.services.dashboard import build_hc_dashboard

    try:
        metrics = build_hc_dashboard(user, filters={'unit': unit})
    except Exception:
        return {
            'headline': '—',
            'headline_label': 'data belum tersedia',
            'foot': 'Buka Arima Human Capital untuk detail lingkup Anda.',
            'band': 'watch',
            'band_label': 'Belum ada data',
        }

    if not metrics['has_employees']:
        return {
            'headline': '—',
            'headline_label': 'pegawai dalam lingkup',
            'foot': 'Belum ada data pegawai pada unit ini.',
            'band': 'watch',
            'band_label': 'Belum ada data',
        }

    compliance = metrics['compliance_pct']
    foot_parts = [f"{metrics['pending_reviews']} dokumen menunggu tinjauan"]
    if metrics['expired']:
        foot_parts.append(f"{metrics['expired']} kedaluwarsa")
    return {
        'headline': metrics['active_employees'],
        'headline_label': 'pegawai aktif',
        'foot': ' · '.join(foot_parts),
        'band': (
            'critical' if metrics['expired']
            else 'watch' if (compliance is not None and compliance < 100)
            else 'good'
        ),
        'band_label': (
            'Perlu tindakan' if metrics['expired']
            else 'Belum lengkap' if (compliance is not None and compliance < 100)
            else 'Terkendali'
        ),
    }


def _briefing(request, unit, profile):
    snapshot = snapshot_cached(unit, profile) if unit else None
    return {
        **_common_context(request, unit, profile),
        'snapshot': snapshot,
    }


def _portal(request, template, portal_key):
    profile = _profile(request)
    unit = _resolve_unit(request, profile)
    if unit is None:
        messages.warning(request, 'Belum ada unit kerja aktif untuk ditampilkan.')
        return redirect('akreditasi:kontrol_hub')
    ctx = _briefing(request, unit, profile)
    ctx['active_portal'] = portal_key
    return render(request, template, ctx)


@login_required
def kontrol_risiko(request):
    return _portal(request, 'akreditasi/kontrol/risiko.html', 'risiko')


@login_required
def kontrol_emr(request):
    return _portal(request, 'akreditasi/kontrol/emr.html', 'emr')


@login_required
def kontrol_dokumen(request):
    return _portal(request, 'akreditasi/kontrol/dokumen.html', 'dokumen')


def _parse_tanggal(raw):
    """'YYYY-MM-DD' → date; apa pun yang tidak valid → hari ini (lokal)."""
    from datetime import date
    from django.utils import timezone

    if raw:
        try:
            return date.fromisoformat(raw)
        except (TypeError, ValueError):
            pass
    return timezone.localdate()


@login_required
def kontrol_layanan(request):
    """Daftar layanan pasien satu unit pada satu tanggal.

    Tanggal bisa digeser lewat ``?tanggal=``; nilai tidak valid jatuh ke hari
    ini, bukan 500. Unit selalu lewat ``_resolve_unit`` supaya akun unit-scoped
    tidak bisa membaca unit lain dengan mengubah query string.
    """
    from datetime import timedelta
    from django.utils import timezone
    from .kontrol_data import _layanan_block

    profile = _profile(request)
    unit = _resolve_unit(request, profile)
    if unit is None:
        messages.warning(request, 'Belum ada unit kerja aktif untuk ditampilkan.')
        return redirect('akreditasi:kontrol_hub')

    tanggal = _parse_tanggal(request.GET.get('tanggal'))
    snapshot = snapshot_cached(unit, profile)
    # Snapshot sudah memuat blok untuk hari ini; tanggal lain dihitung ad hoc
    # supaya cache harian tidak perlu dipecah per tanggal.
    if tanggal != timezone.localdate():
        snapshot = dict(snapshot)
        snapshot['layanan'] = _layanan_block(unit, on_date=tanggal)

    layanan = snapshot['layanan']
    status_filter = request.GET.get('status', '')
    items = layanan['items']
    if status_filter:
        items = [i for i in items if i['status'] == status_filter]

    ctx = _common_context(request, unit, profile)
    ctx.update({
        'snapshot': snapshot,
        'layanan': layanan,
        'items': items,
        'tanggal': tanggal,
        'prev_date': tanggal - timedelta(days=1),
        'next_date': tanggal + timedelta(days=1),
        'is_today': tanggal == timezone.localdate(),
        'filter_status': status_filter,
        'status_pilihan': [
            ('DAFTAR', 'Terdaftar'), ('TRIAGE', 'Triage'), ('ASESMEN', 'Asesmen'),
            ('RANAP', 'Rawat Inap'), ('PULANG', 'Pulang'), ('RUJUK', 'Dirujuk'),
        ],
        'active_portal': 'emr',
    })
    return render(request, 'akreditasi/kontrol/layanan.html', ctx)


AI_CACHE_SECONDS = 600


@require_POST
@login_required
@rate_limit(max_calls=6, window=3600, scope='kontrol_ai')
def kontrol_ringkasan_ai(request):
    """Ringkasan naratif satu unit. Angka dikirim sebagai teks, bukan dihitung AI."""
    profile = _profile(request)
    unit = _resolve_unit(request, profile)
    if unit is None:
        return JsonResponse({'ok': False, 'error': 'Belum ada unit kerja aktif.'}, status=400)

    portal = (request.POST.get('portal') or 'risiko').strip()
    if portal not in {d['key'] for d in SUBDASHBOARDS}:
        return JsonResponse({'ok': False, 'error': 'Portal tidak dikenal.'}, status=400)

    cache_key = f'kontrol:ai:v1:{unit.pk}:{portal}:{profile.unit_kerja_id if profile else 0}'
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({'ok': True, 'data': cached, 'cached': True})

    snapshot = build_unit_snapshot(unit, profile)
    from .ai_service import generate_kontrol_ringkasan

    result = generate_kontrol_ringkasan(request.user, snapshot, portal)
    if not result['success']:
        return JsonResponse({'ok': False, 'error': 'Gagal membuat ringkasan AI.'}, status=502)

    data = result['data']
    if not isinstance(data, dict):
        return JsonResponse({'ok': False, 'error': 'Respons AI tidak valid.'}, status=502)

    payload = {
        'ringkasan': str(data.get('ringkasan') or '')[:2000],
        'risiko_utama': [str(x)[:300] for x in (data.get('risiko_utama') or [])][:5],
        'aksi_minggu_ini': [str(x)[:300] for x in (data.get('aksi_minggu_ini') or [])][:5],
        'batas_data': str(data.get('batas_data') or '')[:600],
    }
    cache.set(cache_key, payload, AI_CACHE_SECONDS)
    return JsonResponse({'ok': True, 'data': payload, 'cached': False})
