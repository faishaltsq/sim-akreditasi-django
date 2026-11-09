"""Resolver aturan EP akreditasi untuk satu baris tindakan asesmen."""

from akreditasi.models import StandardItem
from klinis.models import AturanEpTindakan


def _valid_sub_standards():
    return set(StandardItem.objects.values_list('sub_standard', flat=True).distinct())


def resolve_for(jenis, kode):
    """
    Aturan EP untuk satu tindakan.

    Urutan pencarian: aturan dengan jenis + kode yang sama, lalu wildcard
    (jenis='ANY', kode=''). Aturan yang menunjuk sub_standard yang tidak ada di
    katalog akreditasi dibuang, sehingga kode seperti 'PAP 2.1' atau 'KPR 3'
    tidak pernah menghasilkan tautan hantu.
    """
    valid = _valid_sub_standards()
    kode = (kode or '').strip()
    rules = list(
        AturanEpTindakan.objects.filter(jenis=jenis, kode=kode).order_by('urutan')
    )
    if not rules:
        rules = list(
            AturanEpTindakan.objects.filter(jenis='ANY', kode='').order_by('urutan')
        )
    return [rule for rule in rules if rule.sub_standard in valid]


def primary_for(jenis, kode):
    """EP utama (urutan terkecil) untuk satu tindakan, atau None."""
    rules = resolve_for(jenis, kode)
    return rules[0] if rules else None
