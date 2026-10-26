"""Rekonsiliasi inventaris STARKES 2022 (legacy) ke instrumen STARKES 2024.

Seed 2022 menanam 299 ``StandardItem`` beserta 299 ``QualityRecord``. Sebagian
besar kode EP-nya sudah tidak ada di instrumen 2024: nomor standar digeser,
bab dipecah, dan penomoran EP berubah dari angka (``EP 1``) menjadi huruf
(``EP a``). Karena ``StandardItem.code`` unique, import 2024 yang naif akan
bertabrakan dengan baris legacy, dan kalau tabrakan diakali dengan menambah
suffix, kode EP tidak lagi cocok dengan fixture, filter ``sub_standard``,
maupun relasi ``QualityRecord``.

Modul ini menyelesaikan masalah itu secara struktural: setiap EP legacy
dipetakan ke EP 2024, bukan diberi namespace baru.

Dua tahap pemetaan, berurutan:

1. **Exact** — kode legacy yang setelah alias bab sudah merupakan kode 2024
   yang sah dipakai apa adanya. Ini yang menjaga ``SKP 1 EP 1`` dan
   ``PROGNAS 1 EP 1`` (2024 memang memakai huruf angka) tetap di tempatnya.
2. **Ordinal** — sisa EP dikelompokkan per standar, lalu dipasangkan menurut
   urutan dokumen dengan EP 2024 yang belum terpakai pada standar yang sama.

EP yang standarnya hilang total dari 2024 (mis. ``PPI 7.2.1``, ``ARK 7``)
tidak punya pasangan. Baris seperti itu hanya dihapus kalau benar-benar kosong;
kalau sudah berisi penilaian, modul ini menolak dan melaporkannya supaya
operator memutuskan sendiri — lebih baik berhenti daripada diam-diam menghapus
data akreditasi.
"""

from __future__ import annotations

from collections import defaultdict

from .instrumen_2024 import BAB_META, LEGACY_ALIASES


def alias_code(code):
    """Terjemahkan prefix bab legacy ke kode 2024 (``ARK 4`` -> ``AKP 4``)."""
    if not code:
        return code
    parts = code.split(' ', 1)
    prefix = LEGACY_ALIASES.get(parts[0].upper(), parts[0].upper())
    return prefix if len(parts) == 1 else f'{prefix} {parts[1]}'


def target_index(standards):
    """``{ep_code: standard_code}`` untuk seluruh EP di sumber 2024."""
    index = {}
    for std, eps in standards.items():
        for ep in eps:
            index[f"{std} EP {ep['letter']}"] = std
    return index


def plan_reconciliation(legacy_items, standards):
    """Rencanakan pemetaan EP legacy ke EP 2024.

    ``legacy_items`` adalah daftar ``StandardItem`` milik satu bab (sudah
    diurutkan pemanggil), ``standards`` adalah ``{kode_standar: [ep, ...]}``
    untuk bab yang sama.

    Mengembalikan ``{'retarget': [...], 'delete': [...], 'stats': {...}}``
    dengan ``retarget`` berisi ``{'item', 'code', 'sub_standard'}``.
    """
    index = target_index(standards)
    used = set()
    retarget = []
    remaining = []

    # Tahap 1 — kode yang sudah sah di 2024 dipakai apa adanya.
    for item in legacy_items:
        candidate = alias_code(item.code)
        if candidate in index and candidate not in used:
            used.add(candidate)
            retarget.append({'item': item, 'code': candidate,
                             'sub_standard': index[candidate]})
        else:
            remaining.append(item)

    # Tahap 2 — pasangkan menurut urutan di dalam standar yang sama.
    by_standard = defaultdict(list)
    for item in remaining:
        by_standard[alias_code(item.sub_standard or '')].append(item)

    delete = []
    for standard, items in by_standard.items():
        eps = standards.get(standard)
        if not eps:
            delete.extend(items)
            continue
        items.sort(key=lambda i: (i.order, i.code))
        candidates = [f"{standard} EP {ep['letter']}" for ep in eps
                      if f"{standard} EP {ep['letter']}" not in used]
        for item, code in zip(items, candidates):
            used.add(code)
            retarget.append({'item': item, 'code': code,
                             'sub_standard': standard})
        delete.extend(items[len(candidates):])

    return {
        'retarget': retarget,
        'delete': delete,
        'stats': {
            'retarget': len(retarget),
            'delete': len(delete),
            'create': len(index) - len(used),
        },
    }


def legacy_sources(prefix):
    """Kode kategori legacy yang menjadi sumber satu bab 2024.

    ``AKP`` disuplai oleh kategori ``AKP`` dan ``ARK``; ``PPK`` oleh ``PPK``
    dan ``IPKP``; ``MRMIK`` oleh ``MRMIK`` dan ``MIRM``.
    """
    codes = {prefix}
    for old, new in LEGACY_ALIASES.items():
        if new == prefix:
            codes.add(old)
    return codes


def _is_empty(item, QualityRecord):
    """True bila EP ini belum pernah dinilai sama sekali.

    Seed 2022 menulis ``eval_notes`` berisi ``"Belum dinilai. Unit pengampu: ..."``
    untuk setiap EP. Itu teks yang dihasilkan mesin, bukan penilaian, jadi tidak
    boleh dianggap sebagai isi.
    """
    record = QualityRecord.objects.filter(standard_item=item).first()
    if record is None:
        return not item.evidence_reqs.exists()
    if item.evidence_reqs.filter(files__isnull=False).exists():
        return False
    if record.score or record.baseline_data or record.action_plan \
            or record.risk_mitigation or record.quality_target:
        return False
    notes = (record.eval_notes or '').strip()
    return not notes or notes.startswith('Belum dinilai')


def reconcile(framework, standards, *, Category, StandardItem, QualityRecord,
              dry_run=False):
    """Pindahkan EP legacy ke kategori 2024 milik ``framework``.

    ``standards`` boleh berisi sebagian bab saja (import ``--category``);
    hanya prefix yang muncul di situ yang direkonsiliasi.

    Mengembalikan laporan ``dict``; pada ``dry_run`` tidak ada yang ditulis.
    """
    prefixes = sorted({code.split()[0] for code in standards})
    report = {'retarget': 0, 'delete': 0, 'create': 0,
              'categories_removed': 0, 'blocked': [], 'per_bab': {}}

    for prefix in prefixes:
        meta = BAB_META[prefix]
        # ``framework`` boleh berupa instance yang belum disimpan (dry-run pada
        # database yang belum punya framework 2024). Django menolak instance
        # tersimpan-pun-belum dipakai sebagai nilai filter relasi, jadi query
        # hanya dijalankan bila PK-nya ada.
        target_cat = None
        if framework.pk is not None:
            target_cat = Category.objects.filter(
                framework=framework, code=prefix).first()
        if target_cat is None:
            if dry_run:
                # Kategori belum ada, tapi laporan tetap harus menghitung
                # rencana sebenarnya: pada dry-run tidak ada yang ditulis, jadi
                # ``target_cat`` boleh tetap None.
                pass
            else:
                target_cat = Category.objects.create(
                    framework=framework, code=prefix, name=meta['name'],
                    order=meta['order'], kelompok=meta['kelompok'])

        # EP legacy = item yang masih berada di luar framework ini.
        legacy_qs = (StandardItem.objects
                     .filter(category__code__in=legacy_sources(prefix))
                     .select_related('category')
                     .order_by('order', 'code'))
        if framework.pk is not None:
            legacy_qs = legacy_qs.exclude(category__framework=framework)
        legacy_items = list(legacy_qs)

        chapter_standards = {c: v for c, v in standards.items()
                             if c.split()[0] == prefix}
        plan = plan_reconciliation(legacy_items, chapter_standards)
        stats = plan['stats']

        # Baris tanpa pasangan hanya boleh hilang kalau memang kosong.
        blocked = [item.code for item in plan['delete']
                   if not _is_empty(item, QualityRecord)]
        report['blocked'].extend(blocked)

        if not dry_run and not blocked:
            # Dua tahap: kosongkan dulu kode lama, baru pasang kode 2024.
            # Tanpa ini, penomoran ulang bisa bertabrakan sesaat dengan baris
            # legacy lain yang belum sempat diproses.
            for entry in plan['retarget']:
                if entry['item'].code != entry['code']:
                    StandardItem.objects.filter(pk=entry['item'].pk).update(
                        code=f"__rec__{entry['item'].pk}")
            for entry in plan['retarget']:
                StandardItem.objects.filter(pk=entry['item'].pk).update(
                    code=entry['code'],
                    sub_standard=entry['sub_standard'],
                    category=target_cat)
            for item in plan['delete']:
                item.delete()

        report['retarget'] += stats['retarget']
        report['delete'] += stats['delete']
        report['create'] += stats['create']
        report['per_bab'][prefix] = stats

    if report['blocked'] or dry_run:
        return report

    # Kategori legacy yang sudah kosong dibuang supaya ``Category.code`` unik
    # lagi. Ini yang membuat ``Category.objects.get(code='TKRS')`` tidak
    # ambigu setelah 2022 dan 2024 sempat hidup berdampingan.
    emptied = (Category.objects
               .exclude(framework=framework)
               .filter(items__isnull=True))
    report['categories_removed'] = emptied.count()
    emptied.delete()

    Framework = framework.__class__
    Framework.objects.exclude(pk=framework.pk).filter(
        categories__isnull=True).delete()
    return report
