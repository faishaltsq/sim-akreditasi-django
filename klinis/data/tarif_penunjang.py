"""Pemetaan otoritatif item katalog penunjang -> prosedur ICD-9 master tarif.

Modul ini sengaja hanya memuat **relasi**, bukan nominal. Nominalnya dibaca
saat seeding dari ``klinis/data/master_tarif.py`` (baris ``KasusTindakan``
kelompok JANTUNG dengan nama prosedur yang sama), sehingga tidak ada angka
yang ditulis tangan di sini dan master tarif tetap menjadi satu-satunya
sumber harga.

Hanya item yang prosedurnya benar-benar ada di kelompok JANTUNG yang boleh
dicantumkan. Item laboratorium tidak punya padanan ICD-9 di master tarif,
sehingga tidak punya baris tarif — order tetap boleh dikirim, tagihan ditunda
("tarif belum ditetapkan"), bukan Rp 0.
"""
from datetime import date

# Tanggal berlaku baris tarif A2. Tetap (bukan timezone.localdate()) supaya
# menjalankan seed dua kali tidak membuat periode baru — idempotensi A2.
BERLAKU_SEJAK = date(2026, 11, 24)

TARIF_PENUNJANG = [
    {
        'item_kode': 'penunjang-diagnostik-elektrofisiologi-kardiologi-1',
        'icd9_kode': '89.52',
        'nama_prosedur': 'EKG 12 Lead',
        'dasar': (
            'Item "Elektrokardiogram (EKG 12-Lead)" adalah prosedur 89.52 '
            'EKG 12 Lead. Baris "Pemantauan EKG Kontinu & Rekam Panjang" '
            'memakai kode yang sama tetapi prosedur berbeda, jadi tidak dipakai.'
        ),
    },
    {
        'item_kode': 'penunjang-diagnostik-radiologi-pencitraan-ultrasonografi-usg-7',
        'icd9_kode': '88.72',
        'nama_prosedur': 'Ekokardiografi Doppler',
        'dasar': (
            'Item "Echocardiography (USG Jantung)" adalah ekokardiografi '
            'transtorakal standar. Baris TEE (1.200.000) adalah prosedur '
            'terpisah yang tidak ada di katalog, jadi tidak dipakai.'
        ),
    },
]
