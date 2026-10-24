"""Catalogue UI layer (Track C) — Bahasa Indonesia.

Four function-based views, all ``login_required``:

* ``katalog_daftar``      — list all Frameworks (edition, lifecycle, source hash,
                            reviewed status, active badge). Uses ``resolve_catalogue``
                            to know the active one.
* ``katalog_pemetaan``    — edition-mapping review UI. Lists PemetaanEdisi and allows
                            POST to create/update a mapping via ``review_edition_mapping``.
* ``katalog_validasi``    — source validation UI. Lists SumberKatalog entries.
* ``katalog_pengumuman``  — activation announcement UI. Lists AktivasiKatalog receipts.

Writes are gated by ``require_catalogue_write`` (rejects archived/staged writes).
Non-mutating GET is fine on any readable framework.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .catalogue import require_catalogue_write, resolve_catalogue
from .catalogue_services import review_edition_mapping
from .models import AktivasiKatalog, Framework, PemetaanEdisi, SumberKatalog, StandardItem

MUTATE_OP = 'create'  # PemetaanEdisi create/update is a catalogue mutation.


def _hash_short(value, length=16):
    """Tampilkan hash SHA-256 yang dipotong untuk UI."""
    if not value:
        return '—'
    return f"{value[:length]}…"


@login_required
def katalog_daftar(request):
    """Daftar semua Framework katalog (baca saja, semua framework dapat dibaca)."""
    try:
        active = resolve_catalogue(request.user)
    except PermissionDenied:
        active = None

    frameworks = (
        Framework.objects.all()
        .select_related('reviewed_by')
        .order_by('-version', 'pk')
    )

    return render(
        request,
        'akreditasi/katalog/daftar.html',
        {
            'frameworks': frameworks,
            'active': active,
        },
    )


@login_required
def katalog_pemetaan(request):
    """UI review pemetaan edisi: daftar PemetaanEdisi + POST create/update."""
    try:
        active = resolve_catalogue(request.user)
    except PermissionDenied:
        active = None

    mappings = (
        PemetaanEdisi.objects.all()
        .select_related('source_framework', 'target_framework', 'reviewer')
        .order_by('-reviewed_at', 'pk')
    )

    if request.method == 'POST':
        # Tulis katalog: hanya diperbolehkan pada edisi AKTIF.
        if active is None or active.lifecycle != 'ACTIVE':
            messages.error(
                request,
                "Tidak ada katalog AKTIF. Pemetaan edisi hanya boleh ditulis pada katalog yang aktif.",
            )
            return redirect('akreditasi:katalog_pemetaan')

        try:
            require_catalogue_write(
                request.user, item=active, operation=MUTATE_OP
            )
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc) or "Operasi katalog ditolak.")
            return redirect('akreditasi:katalog_pemetaan')

        source_item_id = request.POST.get('source_item_id')
        target_item_id = request.POST.get('target_item_id')
        classification = request.POST.get('classification', 'UNRESOLVED')
        score_policy = request.POST.get('score_policy', 'CARRY_ASSESSMENT')
        reason = request.POST.get('reason', '')
        evidence_rule_map = {}
        raw_erm = request.POST.get('evidence_rule_map', '').strip()
        if raw_erm:
            import json

            try:
                evidence_rule_map = json.loads(raw_erm)
            except ValueError:
                evidence_rule_map = {}

        try:
            source_item = get_object_or_404(StandardItem, pk=source_item_id)
            target_item = get_object_or_404(StandardItem, pk=target_item_id)
        except (ValueError, TypeError):
            messages.error(request, "Item sumber dan target harus dipilih.")
            return redirect('akreditasi:katalog_pemetaan')

        try:
            review_edition_mapping(
                actor=request.user,
                source_item_ids=[source_item.pk],
                target_item_ids=[target_item.pk],
                classification=classification,
                evidence_rule_map=evidence_rule_map,
                score_policy=score_policy,
                reason=reason,
            )
            messages.success(
                request,
                f"Pemetaan {source_item.code} → {target_item.code} telah direview dan disimpan.",
            )
        except Exception as exc:  # ValidationError dari service layer
            messages.error(request, f"Gagal menyimpan pemetaan: {exc}")

        return redirect('akreditasi:katalog_pemetaan')

    classifications = PemetaanEdisi.CLASSIFICATION_CHOICES
    score_policies = PemetaanEdisi.SCORE_POLICY_CHOICES
    source_items = StandardItem.objects.select_related('category__framework').order_by(
        'category__framework__version', 'code'
    )
    target_items = StandardItem.objects.select_related('category__framework').order_by(
        'category__framework__version', 'code'
    )

    return render(
        request,
        'akreditasi/katalog/pemetaan.html',
        {
            'mappings': mappings,
            'active': active,
            'classifications': classifications,
            'score_policies': score_policies,
            'source_items': source_items,
            'target_items': target_items,
        },
    )


@login_required
def katalog_validasi(request):
    """UI validasi sumber: daftar SumberKatalog dengan sha256, halaman, status review, dan anomali."""
    sumber_list = (
        SumberKatalog.objects.all()
        .select_related('framework', 'reviewed_by')
        .order_by('-extracted_at', 'pk')
    )

    validated = []
    for s in sumber_list:
        anomalies = []
        if not s.sha256:
            anomalies.append('SHA-256 belum tersedia')
        if s.pages <= 0:
            anomalies.append('Jumlah halaman tidak tercatat')
        if not s.reviewed:
            anomalies.append('Belum direview')
        if not s.source_path:
            anomalies.append('Path sumber kosong')
        validated.append(
            {
                'entry': s,
                'anomalies': anomalies,
                'hash_short': _hash_short(s.sha256),
            }
        )

    return render(
        request,
        'akreditasi/katalog/validasi.html',
        {
            'validated': validated,
            'total_count': len(validated),
            'reviewed_count': sum(1 for v in validated if v['entry'].reviewed),
            'unreviewed_count': sum(1 for v in validated if not v['entry'].reviewed),
            'anomaly_count': sum(1 for v in validated if v['anomalies']),
        },
    )


@login_required
def katalog_pengumuman(request):
    """UI pengumuman aktivasi: daftar AktivasiKatalog (receipt aktivasi katalog)."""
    receipts = (
        AktivasiKatalog.objects.all()
        .select_related('framework', 'actor', 'previous_framework')
        .order_by('-activated_at', 'pk')
    )

    return render(
        request,
        'akreditasi/katalog/pengumuman.html',
        {
            'receipts': receipts,
        },
    )
