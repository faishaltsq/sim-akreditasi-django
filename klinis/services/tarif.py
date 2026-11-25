from decimal import Decimal
from klinis.models import KelompokLayanan, KasusTindakan, MasterIcd9
from pasien.models import BillingItem

#: Sumber baris billing otomatis, satu per **asal penulisan** (F4.0).
#:
#: Sebelum F4.0 kedua fungsi di modul ini menulis ``sumber='ASESMEN'`` dan
#: menyapu ``filter(kunjungan, sumber='ASESMEN')`` tanpa melihat kategori.
#: Akibatnya (a) baris penunjang ber-``ASESMEN`` ikut terhapus setiap kali
#: tindakan disimpan, dan (b) kedua fungsi saling menghapus baris pada
#: kunjungan yang sama. Kepemilikan sekarang dinyatakan di data, bukan
#: disimpulkan dari daftar yang kebetulan sedang disinkronkan.
SUMBER_ICD9 = 'ASESMEN'      # form teks bebas lama (sync_billing)
SUMBER_TINDAKAN = 'TINDAKAN'  # baris TindakanAsesmen (sync_billing_tindakan)
SUMBER_PENUNJANG = 'PENUNJANG'  # order katalog penunjang (F4.6)
#: Semua sumber yang ditulis kode, bukan petugas. Dipakai laporan/rekonsiliasi.
SUMBER_OTOMATIS = (SUMBER_ICD9, SUMBER_TINDAKAN, SUMBER_PENUNJANG)


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


def kelompok_for(kunjungan):
    """KelompokLayanan episode ini — nama publik dari ``_kelompok_for``.

    Dipakai pemanggil yang perlu menyebut kelompoknya (mis. daftar Master
    Tindakan Poli) tanpa menyalin aturan pencariannya.
    """
    return _kelompok_for(kunjungan)

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
    Merekonsiliasi baris BillingItem sesuai daftar icd9_kodes.

    Kepemilikan (F4.0): fungsi ini hanya memiliki baris
    ``kategori='JASA_MEDIS', sumber=SUMBER_ICD9``. Sapuan hapus dibatasi ke
    kepemilikan itu, sehingga baris turunan ``TindakanAsesmen``
    (``SUMBER_TINDAKAN``) dan baris penunjang (``SUMBER_PENUNJANG``) tidak
    ikut terhapus saat form teks bebas lama disimpan. Sebelum F4.0 sapuan ini
    menghapus **setiap** baris ``sumber='ASESMEN'`` pada kunjungan, termasuk
    baris yang ditulis fungsi lain.

    - Idempoten: memperbarui tarif jika sudah ada, membuat jika belum ada.
    - Menghapus baris miliknya yang tidak lagi dipilih pada kunjungan ini.
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
            sumber=SUMBER_ICD9,
            defaults={
                'nama_item': icd9.nama if icd9 else kode,
                'harga_satuan': nominal,
                'kuantitas': Decimal('1'),
                'dicatat_oleh': user,
            },
        )
        keep.append(item.pk)

    BillingItem.objects.filter(
        kunjungan=kunjungan, kategori='JASA_MEDIS', sumber=SUMBER_ICD9,
    ).exclude(pk__in=keep).delete()
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
    Menulis BillingItem dari baris TindakanAsesmen.

    Kepemilikan (F4.0): fungsi ini hanya memiliki baris
    ``kategori='JASA_MEDIS', sumber=SUMBER_TINDAKAN``. Sapuan hapus dibatasi ke
    kepemilikan itu, sehingga baris ICD-9 form lama (``SUMBER_ICD9``) dan baris
    penunjang (``SUMBER_PENUNJANG``) tidak ikut terhapus.

    Nominal yang dipakai adalah `tarif_efektif` (override bila ada). Baris tanpa
    nominal tidak pernah menulis Rp 0 dan baris billing lamanya dihapus.
    """
    keep = []
    for line in lines:
        nominal = line.tarif_efektif
        if nominal is None or nominal <= 0:
            if line.billing_item_id:
                BillingItem.objects.filter(
                    pk=line.billing_item_id, sumber=SUMBER_TINDAKAN,
                ).delete()
                line.billing_item = None
            continue

        item, _ = BillingItem.objects.update_or_create(
            kunjungan=kunjungan,
            kategori='JASA_MEDIS',
            kode_icd=line.kode,
            sumber=SUMBER_TINDAKAN,
            defaults={
                'nama_item': (line.nama or line.kode)[:200],
                'harga_satuan': nominal,
                'kuantitas': Decimal('1'),
                'dicatat_oleh': user,
            },
        )
        line.billing_item = item
        keep.append(item.pk)

    BillingItem.objects.filter(
        kunjungan=kunjungan, kategori='JASA_MEDIS', sumber=SUMBER_TINDAKAN,
    ).exclude(pk__in=keep).delete()
    return list(BillingItem.objects.filter(pk__in=keep))
