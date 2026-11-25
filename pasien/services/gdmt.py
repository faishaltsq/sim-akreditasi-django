"""Pintasan regimen GDMT Langkah 8 (F5.4, matriks S9-L1-19).

**Apa yang dibangun di sini.** Mekanisme, bukan daftar obat. Panel GDMT
menampilkan **kelompok** obat, dan isi tiap kelompok dibaca dari katalog
``ProdukFarmasi`` lewat kolom master ``pregnancy_class`` (diisi perintah
``seed_pregnancy_contra``) — tidak ada satu pun nama molekul di berkas ini.
Kelompok yang tidak punya satu baris katalog dilaporkan sebagai
``belum_ada`` dan dirender apa adanya, bukan diganti opsi karangan.

**Mengapa lima kelompok itu.** Matriks menyebut "GDMT" sebagai konsep
(S9-L1-19, S8-L2-02, §PDCA) tetapi **tidak** mendaftar kelas obat GDMT.
Satu-satunya daftar kelas obat ber-kode di korpus spesifikasi adalah lima
kelompok matriks §9a yang sudah menjadi master ``PREGNANCY_CLASS_CODES``
(ACEI, ARB, ARNI, STATIN, WARFARIN). Daftar itu dipakai apa adanya di sini
supaya tidak ada daftar kedua yang dapat menyimpang; kekurangan cakupannya
dicatat sebagai AMBIGU-19, bukan ditambal diam-diam.

**Dosis tidak dikarang.** Matriks hanya memberi empat pilihan penyesuaian
(``GDMT_PENYESUAIAN_CHOICES``). Nilai dosis tetap diisi pengguna pada baris
draf resep; pintasan hanya mengisi/memperbarui baris itu.
"""
from klinis.expansion_models import PREGNANCY_CLASS_CODES
from klinis.models import ProdukFarmasi
from pasien.workflow_schemas import GDMT_PENYESUAIAN_CHOICES, GDMT_PENYESUAIAN_LABELS

#: Kelompok obat yang ditampilkan panel. Alias dari daftar kanonik master,
#: bukan salinan: menambah kelompok cukup di ``PREGNANCY_CLASS_CODES``.
GDMT_GROUPS = PREGNANCY_CLASS_CODES

GDMT_GROUP_LABELS = {
    'ACEI': 'ACE Inhibitor',
    'ARB': 'Angiotensin Receptor Blocker',
    'ARNI': 'Angiotensin Receptor-Neprilysin Inhibitor',
    'STATIN': 'Statin',
    'WARFARIN': 'Warfarin',
}

#: Kalimat status untuk kelompok tanpa satu pun baris katalog.
EMPTY_GROUP_LABEL = 'Belum ada di formularium'


def _product_row(product):
    """Satu baris panel: identitas produk + kelayakan resep yang dapat dibaca."""
    # ``product_snapshot`` menolak produk yang belum aktif/direview, jadi
    # kelayakan dihitung dari kolom yang sama tanpa melempar.
    prescribable = bool(
        product.active and product.reviewed_by_id and product.source_version
        and product.generik.active and product.generik.kelas.active
    )
    return {
        'id': product.pk,
        'kode': product.kode,
        'nama': product.nama,
        'generik': product.generik.nama,
        'unit': product.generik.dispense_unit,
        'allowed_routes': list(product.allowed_routes or []),
        'prescribable': prescribable,
        'status': '' if prescribable else 'Produk belum aktif/direview — belum dapat diresepkan.',
    }


def gdmt_panel():
    """Panel GDMT: kelompok → produk katalog, plus status kosong eksplisit.

    Urutan kelompok mengikuti ``GDMT_GROUPS``; urutan produk mengikuti kode
    katalog supaya layar stabil antar pemuatan.
    """
    rows = (
        ProdukFarmasi.objects
        .select_related('generik__kelas')
        .filter(kind='OBAT', pregnancy_class__in=GDMT_GROUPS)
        .order_by('kode')
    )
    by_group = {group: [] for group in GDMT_GROUPS}
    for product in rows:
        by_group[product.pregnancy_class].append(_product_row(product))
    return [
        {
            'code': group,
            'label': GDMT_GROUP_LABELS.get(group, group),
            'products': by_group[group],
            'empty': not by_group[group],
            'empty_label': '' if by_group[group] else EMPTY_GROUP_LABEL,
        }
        for group in GDMT_GROUPS
    ]


def empty_gdmt_groups():
    """Kode kelompok yang tidak punya satu pun produk katalog.

    Dipakai laporan dan tes: celah formularium harus dapat disebut, bukan
    disembunyikan di dalam HTML.
    """
    return [item['code'] for item in gdmt_panel() if item['empty']]


def adjustment_choices():
    """Empat pilihan penyesuaian dosis matriks S9-L1-19, dengan labelnya."""
    return [
        {'value': code, 'label': GDMT_PENYESUAIAN_LABELS[code]}
        for code in GDMT_PENYESUAIAN_CHOICES
    ]


def adjustment_note(code, note=''):
    """Teks catatan klinis untuk satu pilihan penyesuaian.

    Disimpan pada ``regimen['instructions']`` baris draf resep — kunci yang
    sudah diterima ``calculate_quantity`` dan sudah ikut di ``product_snapshot``
    serta audit resep. Tidak ada kolom baru dan tidak ada dosis yang dikarang.
    """
    if code not in GDMT_PENYESUAIAN_CHOICES:
        raise ValueError('Penyesuaian GDMT tidak dikenal.')
    label = GDMT_PENYESUAIAN_LABELS[code]
    text = f'GDMT: {label}'
    note = str(note or '').strip()
    return f'{text} — {note}' if note else text
