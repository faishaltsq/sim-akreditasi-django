"""Kontraindikasi kehamilan/menyusui pada resep (F3.3, matriks S3-L2-04, §9a).

Matriks menyebut lima kelompok obat yang memicu peringatan bila pasien hamil
atau menyusui: **ACEi, ARB, ARNI, Statin, Warfarin**.

**Sumber kebenaran (AMBIGU-17a, ADR-15).** Pemetaan produk → kelompok dibaca
dari kolom master ``ProdukFarmasi.pregnancy_class`` / ``pregnancy_contra`` yang
diisi oleh perintah ``python manage.py seed_pregnancy_contra``. Kode ini tidak
memuat daftar molekul.

**Urutan prioritas.** Kolom master **menang**. Pencocokan lama atas
``class_code``/``ingredient_code`` hanya jalan bila ``pregnancy_class`` kosong
(produk belum dipetakan, atau snapshot resep yang dibuat sebelum kolom ini
ada). Fallback itu dipertahankan supaya perilaku Rilis A1 tidak berubah, bukan
supaya menjadi jalur utama: katalog lokal hanya punya kelas kasar
``kardiovaskular-antihipertensi`` yang tidak memisahkan ACEi dari ARB, ARNI,
statin, atau warfarin, sehingga fallback tidak dapat menyalakan peringatan
untuk produk yang seharusnya memicunya.

**Status ratifikasi.** Daftar zat di perintah seed adalah **default
operasional** yang belum diratifikasi Komite Farmasi & Terapi (ADR-15). Setiap
baris yang dipetakan menyimpan sumbernya di ``pregnancy_class_source``.
"""
from klinis.expansion_models import PREGNANCY_CLASS_CODES
from pasien.workflow_schemas import KEHAMILAN_KONTRAINDIKASI

#: Lima kelompok obat dari matriks §9a, apa adanya. Alias dari daftar kanonik
#: di model supaya hanya ada satu sumber kode.
PREGNANCY_CONTRA_CLASSES = PREGNANCY_CLASS_CODES

#: Kalimat provenance untuk finding; menyebut sumber kelompoknya.
PREGNANCY_CONTRA_SOURCE = (
    'Kelompok kontraindikasi kehamilan: ' + ', '.join(PREGNANCY_CONTRA_CLASSES)
    + ' (matriks §9a; pemetaan zat per produk dari master formularium, ADR-15).'
)

def _tokens(value):
    """Token pembanding: huruf kecil, hanya alfanumerik."""
    return ''.join(char for char in str(value or '').lower() if char.isalnum())

def _legacy_groups(snapshot):
    """Pencocokan lama atas ``class_code``/``ingredient_code`` (fallback saja)."""
    hits = set()
    candidates = [snapshot.get('class_code')]
    candidates.extend(
        ingredient.get('ingredient_code')
        for ingredient in snapshot.get('ingredients') or []
        if isinstance(ingredient, dict)
    )
    for candidate in candidates:
        token = _tokens(candidate)
        if not token:
            continue
        for group in PREGNANCY_CONTRA_CLASSES:
            if token == _tokens(group) or token.startswith(_tokens(group)):
                hits.add(group)
    return hits

def contra_groups(snapshot):
    """Kelompok matriks yang cocok untuk satu snapshot produk.

    ``snapshot`` adalah ``product_snapshot`` yang sudah dipakai
    ``evaluate_prescription``: memuat ``pregnancy_class``, ``pregnancy_contra``,
    ``class_code``, dan ``ingredients``.
    """
    declared = str(snapshot.get('pregnancy_class') or '').strip().upper()
    if declared:
        return {declared} if declared in PREGNANCY_CONTRA_CLASSES else set()
    return _legacy_groups(snapshot)

def pregnancy_status(visit):
    """Status kehamilan/menyusui episode, dibaca dari draft langkah 3.

    Nilai langkah rajal tinggal di ``IgdAssessmentWorkflow.draft_payload``
    (ADR-9), bukan di kolom ``KunjunganPasien``; episode IGD tidak punya kunci
    ini dan karena itu mengembalikan string kosong.
    """
    workflow = getattr(visit, 'igd_workflow', None)
    if workflow is None:
        return ''
    payload = (workflow.draft_payload or {}).get('3') or {}
    status = payload.get('status_kehamilan_menyusui') or ''
    return status if status in KEHAMILAN_KONTRAINDIKASI else ''

def pregnancy_findings(visit, snapshots):
    """Finding ``PREGNANCY_CONTRA`` (blocking) untuk satu episode + resep.

    ``snapshots`` adalah daftar ``product_snapshot`` pada resep. Satu finding
    per kelompok, bukan per baris resep, supaya pesan tidak berulang.
    """
    status = pregnancy_status(visit)
    if not status:
        return []
    found = set()
    for snapshot in snapshots:
        if isinstance(snapshot, dict):
            found.update(contra_groups(snapshot))
    if not found:
        return []
    label = 'Hamil' if status == 'HAMIL' else 'Menyusui'
    return [{
        'code': 'PREGNANCY_CONTRA',
        'message': (
            f'Pasien {label}: resep memuat kelompok {", ".join(sorted(found))} '
            f'yang kontraindikasi. {PREGNANCY_CONTRA_SOURCE}'
        ),
        'blocking': True,
        'requires_ack': False,
    }]
