"""F4.6 (ADR-4/ADR-10): tagihan otomatis dari order penunjang katalog.

Aturan yang ditegaskan ADR-4 dan tidak boleh dilonggarkan:

- Item tanpa ``TarifPenunjang`` **tidak** menagih. Order tetap sah dan
  dikirim; tagihannya menyusul (``charge_state='PENDING'``), bukan Rp 0 dan
  bukan nominal karangan.
- Satu order memiliki paling banyak satu baris tagihan, ditautkan lewat
  ``OrderPenunjang.billing_item``. Mengirim ulang batch yang sama tidak
  menggandakan baris.
- Baris ditulis dengan ``sumber=SUMBER_PENUNJANG`` (F4.0), sehingga sapuan
  hapus milik ``sync_billing``/``sync_billing_tindakan`` tidak menyentuhnya.

Kategori tagihan mengikuti ``jenis_order`` katalog. Pemetaan ini sengaja
eksplisit: ``BillingItem.KATEGORI`` tidak punya nilai ``EKG``, dan menebak
kategori berarti angka masuk ke kelompok laporan yang salah.
"""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from klinis.models import TarifPenunjang
from klinis.services.tarif import SUMBER_PENUNJANG
from pasien.models import BillingItem, OrderPenunjang

from .igd_assessment_workflow import WorkflowValidation

#: ``jenis_order`` katalog → ``BillingItem.KATEGORI``.
KATEGORI_PER_JENIS = {
    'LAB': 'LAB',
    'RADIOLOGI': 'RADIOLOGI',
    'EKG': 'JASA_MEDIS',
    'LAINNYA': 'LAINNYA',
}

#: Penjamin yang dikenal ``TarifPenunjang``; selain ini ditagih sebagai UMUM
#: (ADR-10: satu nominal per item sampai tabel tarif resmi per penjamin ada).
PENJAMIN_DIKENAL = ('UMUM', 'BPJS', 'ASURANSI')
PENJAMIN_DASAR = 'UMUM'


def tarif_aktif(item, penjamin, hari=None):
    """Baris ``TarifPenunjang`` yang berlaku hari ini, atau ``None``."""
    hari = hari or timezone.localdate()
    kode = penjamin if penjamin in PENJAMIN_DIKENAL else PENJAMIN_DASAR
    baris = (
        TarifPenunjang.objects
        .filter(item=item, penjamin=kode, valid_from__lte=hari)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=hari))
        .order_by('-valid_from')
        .first()
    )
    if baris is None and kode != PENJAMIN_DASAR:
        return tarif_aktif(item, PENJAMIN_DASAR, hari)
    return baris


def nominal_order(order, hari=None):
    """Nominal tagihan satu order, atau ``None`` bila tarif belum ditetapkan."""
    item = order.catalogue_item
    if item is None:
        return None
    baris = tarif_aktif(item, order.kunjungan.penjamin, hari)
    return baris.nominal if baris else None


def charge_order(order, user=None, hari=None):
    """Buat/perbarui tagihan satu order katalog. Return baris atau ``None``.

    ``None`` berarti tarif belum ditetapkan; itu bukan kegagalan order.
    """
    nominal = nominal_order(order, hari)
    if nominal is None or nominal <= 0:
        return None
    kategori = KATEGORI_PER_JENIS.get(order.jenis, 'LAINNYA')
    item = order.catalogue_item
    baris = BillingItem.objects.filter(
        pk=order.billing_item_id, kategori=kategori, sumber=SUMBER_PENUNJANG,
    ).first() if order.billing_item_id else None
    if baris is None:
        baris = BillingItem.objects.create(
            kunjungan=order.kunjungan,
            kategori=kategori,
            nama_item=f'Pemeriksaan {order.get_jenis_display()}: {order.nama_pemeriksaan}',
            kuantitas=Decimal('1'),
            harga_satuan=nominal,
            kode_icd=item.kode[:20] if item else '',
            sumber=SUMBER_PENUNJANG,
            dicatat_oleh=user,
        )
    else:
        baris.nama_item = f'Pemeriksaan {order.get_jenis_display()}: {order.nama_pemeriksaan}'
        baris.harga_satuan = nominal
        baris.kode_icd = item.kode[:20] if item else ''
        baris.dicatat_oleh = user or baris.dicatat_oleh
        baris.save()
    order.billing_item = baris
    order.save(update_fields=['billing_item'])
    return baris


def charge_batch(order_ids, user=None):
    """Tagih satu batch order. Return ``{order_id: BillingItem|None}``."""
    hasil = {}
    for order in OrderPenunjang.objects.filter(pk__in=order_ids).select_related(
            'kunjungan', 'catalogue_item'):
        hasil[order.pk] = charge_order(order, user=user)
    return hasil


def release_order(order):
    """Batalkan tagihan satu order tanpa menyentuh baris milik asal lain."""
    if not order.billing_item_id:
        return False
    # FK-nya PROTECT, jadi tautan dilepas lebih dulu; kalau tidak, penghapusan
    # baris tagihan ditolak oleh tautan order itu sendiri.
    baris_id = order.billing_item_id
    order.billing_item = None
    order.save(update_fields=['billing_item'])
    BillingItem.objects.filter(pk=baris_id, sumber=SUMBER_PENUNJANG).delete()
    return True
