"""F0.8 — fondasi tarif Poliklinik Jantung (idempoten).

Tiga hal disiapkan sekaligus:

1. ``KelompokLayanan(kode='POLI_JANTUNG')`` terikat ke UnitKerja POLI-JANTUNG.
   Sebelum ini ``_kelompok_for`` tidak menemukan kelompok untuk kunjungan
   rawat jalan (fallback ``kode='RAJAL'`` tidak ada), sehingga ``resolve()``
   selalu ``None``.
2. Salinan ``KasusTersering``/``KasusTindakan`` kelompok JANTUNG ke
   POLI_JANTUNG. ``resolve()`` membaca ``KasusTindakan`` per kelompok, jadi
   membuat baris kelompok saja tidak cukup.
3. ``TarifPenunjang`` untuk item katalog yang prosedurnya punya harga
   otoritatif di ``master_tarif``.

Tidak ada nominal yang dikarang: harga dibaca dari master tarif, dan item
tanpa padanan ICD-9 tidak mendapat baris sama sekali (tarif belum ditetapkan,
bukan Rp 0).
"""
from decimal import Decimal

from django.db import transaction

from akreditasi.models import UnitKerja
from klinis.data.master_tarif import KASUS
from klinis.data.tarif_penunjang import BERLAKU_SEJAK, TARIF_PENUNJANG
from klinis.models import (
    ItemPenunjang, KasusTersering, KasusTindakan, KelompokLayanan, TarifPenunjang,
)

KODE_KELOMPOK = 'POLI_JANTUNG'
NAMA_KELOMPOK = 'Poliklinik Spesialis Jantung & Pembuluh Darah'
KODE_UNIT = 'POLI-JANTUNG'
KODE_SUMBER = 'JANTUNG'
PENJAMIN_DASAR = 'UMUM'

def _unit_kerja():
    unit = UnitKerja.objects.filter(code=KODE_UNIT).first()
    if unit is None:
        raise ValueError(
            f'UnitKerja {KODE_UNIT} tidak ditemukan; siapkan unit lebih dulu.'
        )
    return unit

def _nominal_master(icd9_kode, nama_prosedur):
    """Nominal tarif_umum dari baris master JANTUNG yang namanya tepat sama."""
    nominal = {
        Decimal(tarif_umum)
        for kasus in KASUS
        if kasus['kelompok'] == KODE_SUMBER
        for kode, nama, tarif_umum, _bpjs, _satuan in kasus['tindakan']
        if kode == icd9_kode and nama == nama_prosedur
    }
    if not nominal:
        raise ValueError(
            f'Prosedur {icd9_kode} "{nama_prosedur}" tidak ada di kelompok {KODE_SUMBER}.'
        )
    if len(nominal) != 1:
        raise ValueError(
            f'Nominal {icd9_kode} "{nama_prosedur}" tidak tunggal: {sorted(nominal)}.'
        )
    harga = nominal.pop()
    if harga <= 0:
        raise ValueError(f'Nominal {icd9_kode} "{nama_prosedur}" tidak positif: {harga}.')
    return harga

def _salin_kasus(sumber, tujuan):
    """Salin kasus + tindakan apa adanya (tanpa penyesuaian nominal)."""
    jumlah_kasus = jumlah_tindakan = 0
    for kasus in sumber.kasus.order_by('urutan'):
        salinan, _ = KasusTersering.objects.update_or_create(
            kelompok=tujuan,
            urutan=kasus.urutan,
            defaults={
                'icd10': kasus.icd10,
                'sdki_kode': kasus.sdki_kode,
                'sdki_nama': kasus.sdki_nama,
                'tatalaksana': kasus.tatalaksana,
                'kewenangan': kasus.kewenangan,
                'perlu_verifikasi': kasus.perlu_verifikasi,
                'catatan_sumber': kasus.catatan_sumber,
            },
        )
        jumlah_kasus += 1
        for tindakan in kasus.tindakan.order_by('urutan'):
            KasusTindakan.objects.update_or_create(
                kasus=salinan,
                icd9=tindakan.icd9,
                urutan=tindakan.urutan,
                defaults={
                    'tarif_umum': tindakan.tarif_umum,
                    'tarif_bpjs': tindakan.tarif_bpjs,
                    'satuan': tindakan.satuan,
                },
            )
            jumlah_tindakan += 1
    return jumlah_kasus, jumlah_tindakan

def _seed_tarif_penunjang(tujuan):
    jumlah = 0
    dilewati = []
    for row in TARIF_PENUNJANG:
        item = ItemPenunjang.objects.filter(kode=row['item_kode']).first()
        if item is None:
            dilewati.append(row['item_kode'])
            continue
        harga = _nominal_master(row['icd9_kode'], row['nama_prosedur'])
        if not KasusTindakan.objects.filter(
                kasus__kelompok=tujuan, icd9__kode=row['icd9_kode'], tarif_umum=harga).exists():
            raise ValueError(
                f'Salinan POLI_JANTUNG tidak memuat {row["icd9_kode"]} bertarif {harga}.'
            )
        TarifPenunjang.objects.update_or_create(
            item=item,
            penjamin=PENJAMIN_DASAR,
            valid_from=BERLAKU_SEJAK,
            defaults={'nominal': harga, 'valid_to': None},
        )
        jumlah += 1
    return jumlah, dilewati

@transaction.atomic
def seed():
    """Jalankan seluruh fondasi tarif POLI-JANTUNG; aman diulang."""
    unit = _unit_kerja()
    kelompok, _ = KelompokLayanan.objects.update_or_create(
        kode=KODE_KELOMPOK,
        defaults={'nama': NAMA_KELOMPOK, 'unit_kerja': unit, 'urutan': 15},
    )
    sumber = KelompokLayanan.objects.filter(kode=KODE_SUMBER).first()
    if sumber is None:
        raise ValueError(
            f'KelompokLayanan {KODE_SUMBER} belum ada; jalankan seed_katalog_klinis lebih dulu.'
        )
    jumlah_kasus, jumlah_tindakan = _salin_kasus(sumber, kelompok)
    jumlah_tarif, dilewati = _seed_tarif_penunjang(kelompok)
    tanpa_tarif = ItemPenunjang.objects.exclude(
        pk__in=TarifPenunjang.objects.values('item_id')).count()
    return {
        'kelompok': kelompok.kode,
        'unit': unit.code,
        'kasus': jumlah_kasus,
        'tindakan': jumlah_tindakan,
        'tarif_penunjang': jumlah_tarif,
        'item_tanpa_tarif': tanpa_tarif,
        'item_katalog_tidak_ada': dilewati,
    }
