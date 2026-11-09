from decimal import Decimal
from klinis.models import KelompokLayanan, KasusTindakan, MasterIcd9
from pasien.models import BillingItem


def _kelompok_for(kunjungan):
    """
    Menentukan KelompokLayanan untuk kunjungan:
    1. Utamakan pemetaan eksplisit UnitKerja kunjungan -> KelompokLayanan.unit_kerja
    2. Fallback ke pencocokan kode KelompokLayanan == jenis_kunjungan (misal: 'IGD')
    """
    KL = KelompokLayanan
    if kunjungan.unit_kerja_id:
        kl = KL.objects.filter(unit_kerja_id=kunjungan.unit_kerja_id).first()
        if kl:
            return kl
    return KL.objects.filter(kode=kunjungan.jenis_kunjungan.upper()).first()


def resolve_detail(kunjungan, icd9_kode):
    """
    Versi lengkap dari resolve(): mengembalikan dict berisi nominal, baris master,
    ICD-9, kelompok layanan, dan penjamin. None bila kelompok/kode tidak ditemukan.
    Dipakai API preview dan UI; `resolve()` tetap menjadi kontrak Decimal untuk
    pemanggil lama.
    """
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return None

    tindakan = (
        KasusTindakan.objects
        .filter(kasus__kelompok=kelompok, icd9__kode=icd9_kode)
        .select_related('icd9', 'kasus')
        .order_by('kasus__urutan', 'urutan')
        .first()
    )
    if not tindakan:
        return None

    nominal = tindakan.tarif_bpjs if kunjungan.penjamin == 'BPJS' else tindakan.tarif_umum
    return {
        'nominal': nominal,
        'tindakan': tindakan,
        'icd9': tindakan.icd9,
        'kelompok': kelompok,
        'penjamin': kunjungan.penjamin,
    }


def resolve(kunjungan, icd9_kode):
    """
    Mengambil tarif (Decimal) untuk kode ICD-9 dalam konteks kelompok layanan kunjungan dan penjamin:
    - Penjamin 'BPJS' -> tarif_bpjs
    - Penjamin lain (UMUM / ASURANSI) -> tarif_umum
    - Mengembalikan None jika kelompok/tindakan tidak ditemukan atau tarif tidak ditetapkan (bukan Rp 0).
    """
    detail = resolve_detail(kunjungan, icd9_kode)
    return detail['nominal'] if detail else None


def sync_billing(kunjungan, icd9_kodes, user=None):
    """
    Merekonsiliasi baris BillingItem dengan sumber='ASESMEN' sesuai daftar icd9_kodes.
    - Idempoten: memperbarui tarif jika sudah ada, membuat jika belum ada.
    - Menghapus BillingItem ASESMEN yang tidak lagi dipilih pada kunjungan ini.
    - Mengabaikan tindakan yang tarifnya None (tidak menuliskan Rp 0).
    """
    wanted = [k.strip() for k in icd9_kodes if k and k.strip()]
    keep = []
    for kode in wanted:
        nominal = resolve(kunjungan, kode)
        if nominal is None:
            continue
        icd9 = MasterIcd9.objects.filter(kode=kode).first()
        item, _ = BillingItem.objects.update_or_create(
            kunjungan=kunjungan,
            kategori='JASA_MEDIS',
            kode_icd=kode,
            sumber='ASESMEN',
            defaults={
                'nama_item': icd9.nama if icd9 else kode,
                'harga_satuan': nominal,
                'kuantitas': Decimal('1'),
                'dicatat_oleh': user,
            },
        )
        keep.append(item.pk)

    BillingItem.objects.filter(kunjungan=kunjungan, sumber='ASESMEN').exclude(pk__in=keep).delete()
    return list(BillingItem.objects.filter(pk__in=keep))


def refresh_acuan(kunjungan, lines):
    """
    Segarkan tarif_acuan dari master untuk baris ICD-9.

    Hanya `tarif_acuan` yang disentuh; `tarif` (override petugas) tidak pernah
    ditimpa. Baris SIKI/BEBAS tidak punya acuan master sehingga dibiarkan.
    """
    for line in lines:
        if line.jenis != 'ICD9' or not line.kode:
            continue
        detail = resolve_detail(kunjungan, line.kode)
        line.tarif_acuan = detail['nominal'] if detail else None


def sync_billing_tindakan(kunjungan, lines, user=None):
    """
    Menulis BillingItem ASESMEN dari baris TindakanAsesmen.

    Nominal yang dipakai adalah `tarif_efektif` (override bila ada). Baris tanpa
    nominal tidak pernah menulis Rp 0 dan baris billing lamanya dihapus.
    """
    keep = []
    for line in lines:
        nominal = line.tarif_efektif
        if nominal is None or nominal <= 0:
            if line.billing_item_id:
                BillingItem.objects.filter(pk=line.billing_item_id, sumber='ASESMEN').delete()
                line.billing_item = None
            continue

        item, _ = BillingItem.objects.update_or_create(
            kunjungan=kunjungan,
            kategori='JASA_MEDIS',
            kode_icd=line.kode,
            sumber='ASESMEN',
            defaults={
                'nama_item': (line.nama or line.kode)[:200],
                'harga_satuan': nominal,
                'kuantitas': Decimal('1'),
                'dicatat_oleh': user,
            },
        )
        line.billing_item = item
        keep.append(item.pk)

    BillingItem.objects.filter(kunjungan=kunjungan, sumber='ASESMEN').exclude(pk__in=keep).delete()
    return list(BillingItem.objects.filter(pk__in=keep))
