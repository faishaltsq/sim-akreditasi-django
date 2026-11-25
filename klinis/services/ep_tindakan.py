"""Resolver aturan EP akreditasi untuk satu baris tindakan asesmen."""

from django.db.models import Q

from akreditasi.models import StandardItem
from klinis.models import AturanEpTindakan

def _valid_sub_standards():
    return set(StandardItem.objects.values_list('sub_standard', flat=True).distinct())

def _scope_filter(service_line):
    """Aturan berlaku bila cakupannya global atau sama dengan jalur pemanggil."""
    return Q(layanan='') | Q(layanan=service_line or '')

def resolve_for(jenis, kode, service_line=None):
    """
    Aturan EP untuk satu tindakan.

    Urutan pencarian: aturan dengan jenis + kode yang sama, lalu wildcard
    (jenis='ANY', kode=''). Aturan yang menunjuk sub_standard yang tidak ada di
    katalog akreditasi dibuang, sehingga kode seperti 'PAP 2.1' atau 'KPR 3'
    tidak pernah menghasilkan tautan hantu.

    ``service_line`` menyaring cakupan (F7.5). Pemanggil lama yang tidak
    mengirimnya hanya melihat aturan global — perilaku IGD tidak bergeser.
    """
    valid = _valid_sub_standards()
    kode = (kode or '').strip()
    rules = list(
        AturanEpTindakan.objects
        .filter(_scope_filter(service_line), jenis=jenis, kode=kode)
        .order_by('urutan')
    )
    if not rules:
        rules = list(
            AturanEpTindakan.objects
            .filter(_scope_filter(service_line), jenis='ANY', kode='')
            .order_by('urutan')
        )
    return [rule for rule in rules if rule.sub_standard in valid]

def primary_for(jenis, kode, service_line=None):
    """EP utama (urutan terkecil) untuk satu tindakan, atau None."""
    rules = resolve_for(jenis, kode, service_line)
    return rules[0] if rules else None
