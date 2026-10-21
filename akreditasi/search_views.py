"""Pencarian terpadu ARIMA (V3).

Satu endpoint baca-only yang menggali lima sumber data nyata — Elemen
Penilaian, Dokumen Bukti, Risiko PDCA, Unit Kerja, dan Insiden/Temuan.

Aturan lingkupnya persis mengikuti halaman sumbernya (bukan aturan baru):

* ``risiko_daftar`` membatasi pengguna unit-scoped pada unitnya sendiri,
  unit bawahan, dan seluruh leluhurnya — pencarian risiko memakai
  ``scoped_unit_ids()`` yang sama;
* ``ep_list``, ``dokumen_hub``, ``unit_tree`` dan ``insiden_daftar``
  ber-turnstile ``@login_required`` tanpa pembatasan unit, jadi
  pencarian untuk sumber tersebut juga terbuka bagi seluruh pengguna
  terautentikasi.

Tidak ada data dummy: setiap baris berasal dari query ORM dan membawa URL
detail yang benar-benar ada.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

from .models import EvidenceFile, StandardItem, UnitKerja
from .risiko_models import InsidenKeselamatan, RisikoUnit

#: Batas hasil per sumber, agar halaman tetap ringan di DB besar.
MAX_PER_GROUP = 8
#: Minimal panjang kata kunci agar tidak membanjiri query.
MIN_QUERY_LEN = 2


def scoped_unit_ids(profile):
    """ID unit yang boleh dilihat ``profile`` untuk sumber ber-scope unit.

    Mengembalikan ``None`` untuk pengguna tanpa pembatasan unit
    (Admin RS, Super Admin, Direktur, Asesor, dll.). Pola identik dengan
    pengumpulan ID pada ``risiko_views.risiko_daftar``: unit sendiri,
    unit anak (bawahan), dan rantai parent ke atas.
    """
    if not (profile and profile.is_unit_scoped and profile.unit_kerja):
        return None

    unit = profile.unit_kerja
    ids = {unit.id}
    for child in UnitKerja.objects.filter(parent=unit).values_list('id', flat=True):
        ids.add(child)
    ancestor = unit.parent
    while ancestor:
        ids.add(ancestor.id)
        ancestor = ancestor.parent
    return list(ids)


def _hit(grup, judul, sub, meta, url, ikon):
    return {
        'grup': grup, 'judul': judul, 'sub': sub or '',
        'meta': meta or '', 'url': url, 'ikon': ikon,
    }


def _first_line(text, limit=110):
    """Baris non-kosong pertama dari field teks multi-baris, dipotong aman."""
    for line in (t.strip() for t in (text or '').splitlines()):
        if line:
            return line if len(line) <= limit else line[:limit - 1] + '…'
    return ''


def _search_ep(q):
    qs = StandardItem.objects.select_related('category', 'record').filter(
        Q(code__icontains=q) |
        Q(description__icontains=q) |
        Q(sub_title__icontains=q)
    )
    out = []
    for item in qs.order_by('category__order', 'order', 'code')[:MAX_PER_GROUP]:
        record = getattr(item, 'record', None)
        out.append(_hit(
            'Elemen Penilaian (EP)',
            item.code,
            item.sub_title,
            'Skor %s/10 · %s' % (record.score if record else '—',
                                 item.category.name if item.category else 'Tanpa kategori'),
            reverse('akreditasi:ep_detail', args=[item.id]),
            'bi-list-check',
        ))
    return out


def _search_dokumen(q):
    qs = EvidenceFile.objects.select_related(
        'requirement__standard_item__category',
    ).filter(
        Q(file_name__icontains=q) |
        Q(requirement__title__icontains=q) |
        Q(requirement__standard_item__code__icontains=q)
    )
    out = []
    for doc in qs.order_by('-uploaded_at')[:MAX_PER_GROUP]:
        std = doc.requirement.standard_item
        out.append(_hit(
            'Dokumen Bukti (RDWOS)',
            doc.file_name,
            doc.requirement.title,
            '%s · rev %d · %s' % (std.code, doc.version, doc.get_status_display()),
            reverse('akreditasi:ep_detail', args=[std.id]),
            'bi-archive-fill',
        ))
    return out


def _search_risiko(q, unit_ids):
    qs = RisikoUnit.objects.select_related('unit').filter(
        Q(masalah__icontains=q) |
        Q(deskripsi_risiko__icontains=q) |
        Q(jenis_risiko__icontains=q) |
        Q(kategori_risiko__icontains=q) |
        Q(pj_mitigasi__icontains=q) |
        Q(strategi_mitigasi__icontains=q)
    )
    if unit_ids is not None:
        qs = qs.filter(unit_id__in=unit_ids)
    out = []
    for risiko in qs.order_by('-updated_at')[:MAX_PER_GROUP]:
        out.append(_hit(
            'Risiko PDCA',
            _first_line(risiko.masalah or risiko.deskripsi_risiko),
            risiko.get_kategori_risiko_display(),
            '%s · %s · %s' % (
                risiko.unit.name if risiko.unit else 'Tanpa unit',
                risiko.get_periode_display(),
                risiko.get_status_display(),
            ),
            reverse('akreditasi:risiko_detail', args=[risiko.id]),
            'bi-clipboard2-pulse-fill',
        ))
    return out


def _search_unit(q):
    qs = UnitKerja.objects.filter(
        Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q)
    )
    out = []
    for unit in qs.order_by('code')[:MAX_PER_GROUP]:
        out.append(_hit(
            'Unit Kerja',
            unit.name,
            unit.get_tipe_unit_display(),
            '%s · PIC %s' % (unit.code, unit.pic_name or '—'),
            reverse('akreditasi:unit_tree'),
            'bi-building',
        ))
    return out


def _search_temuan(q):
    """Insiden & temuan lapangan — sumbernya tidak punya FK unit,
    sama persis dengan tampilan pada ``insiden_daftar``."""
    qs = InsidenKeselamatan.objects.filter(
        Q(deskripsi_kejadian__icontains=q) |
        Q(jenis_insiden__icontains=q) |
        Q(lokasi_kejadian__icontains=q) |
        Q(tindakan_segera__icontains=q)
    )
    out = []
    for insiden in qs.order_by('-tanggal_kejadian')[:MAX_PER_GROUP]:
        out.append(_hit(
            'Temuan & Insiden',
            _first_line(insiden.deskripsi_kejadian),
            insiden.get_jenis_insiden_display(),
            '%s · Keparahan %s · %s' % (
                insiden.tanggal_kejadian.strftime('%d %b %Y'),
                insiden.get_tingkat_keparahan_display(),
                insiden.get_status_investigasi_display(),
            ),
            reverse('akreditasi:insiden_detail', args=[insiden.id]),
            'bi-shield-exclamation',
        ))
    return out


@login_required
def pencarian(request):
    """Pencarian lintas modul, hasil digabung per sumber."""
    q = request.GET.get('q', '').strip()
    profile = getattr(request.user, 'profile', None)
    unit_ids = scoped_unit_ids(profile)

    groups, total = [], 0
    if len(q) >= MIN_QUERY_LEN:
        for label, hits in (
            ('Elemen Penilaian (EP)', _search_ep(q)),
            ('Dokumen Bukti (RDWOS)', _search_dokumen(q)),
            ('Risiko PDCA', _search_risiko(q, unit_ids)),
            ('Unit Kerja', _search_unit(q)),
            ('Temuan & Insiden', _search_temuan(q)),
        ):
            if hits:
                groups.append({'label': label, 'items': hits, 'jumlah': len(hits)})
                total += len(hits)

    return render(request, 'akreditasi/pencarian.html', {
        'q': q,
        'groups': groups,
        'total_results': total,
        'is_unit_scoped': unit_ids is not None,
        'min_query_len': MIN_QUERY_LEN,
        'max_per_group': MAX_PER_GROUP,
    })
