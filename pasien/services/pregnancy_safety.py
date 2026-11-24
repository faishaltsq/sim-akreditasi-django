"""Kontraindikasi kehamilan/menyusui pada resep (F3.3, matriks S3-L2-04, §9a).

Matriks menyebut lima kelompok obat yang memicu peringatan bila pasien hamil
atau menyusui: **ACEi, ARB, ARNI, Statin, Warfarin**. Yang **tidak** diberikan
matriks adalah pemetaan produk katalog ke kelompok itu.

Karena itu modul ini tidak memuat daftar molekul. Ia mencocokkan kelompok
matriks terhadap **data yang sudah ada di katalog**: ``class_code`` produk dan
``ingredient_code`` komponennya, dinormalkan (huruf kecil, hanya alfanumerik).
Bila katalog menamai kelasnya ``ACEI``, ``ARB``, ``ARNI``, ``STAIN``, atau
``WARFARIN`` — atau memberi awalan itu pada kode zat — peringatan menyala.

Konsekuensi yang harus diketahui operator: katalog lokal hari ini hanya punya
kelas kasar ``kardiovaskular-antihipertensi``, yang **tidak** memisahkan ACEi
dari ARB, ARNI, statin, atau warfarin. Selama kelas per-zat belum ada di master,
aturan ini tidak akan menyala untuk produk yang seharusnya memicunya. Itu
dilaporkan sebagai AMBIGU-17, bukan ditambal dengan daftar molekul karangan:
salah mencocokkan obat kehamilan adalah kesalahan klinis, bukan kesalahan
tampilan.
"""
from pasien.workflow_schemas import KEHAMILAN_KONTRAINDIKASI

#: Lima kelompok obat dari matriks §9a, apa adanya.
PREGNANCY_CONTRA_CLASSES = ('ACEI', 'ARB', 'ARNI', 'STATIN', 'WARFARIN')

#: Kalimat provenance untuk finding; menyebut sumber kelompoknya.
PREGNANCY_CONTRA_SOURCE = (
    'Kelompok kontraindikasi kehamilan: ' + ', '.join(PREGNANCY_CONTRA_CLASSES)
    + ' (matriks §9a). Pemetaan produk ke kelompok bergantung pada kelas/zat '
      'di katalog formularium.'
)

def _tokens(value):
    """Token pembanding: huruf kecil, hanya alfanumerik."""
    return ''.join(char for char in str(value or '').lower() if char.isalnum())

def _matches(token):
    """True bila token memuat salah satu kelompok matriks sebagai kata utuh."""
    return any(token == _tokens(group) or token.startswith(_tokens(group))
               for group in PREGNANCY_CONTRA_CLASSES)

def contra_groups(snapshot):
    """Kelompok matriks yang cocok untuk satu snapshot produk.

    ``snapshot`` adalah ``product_snapshot`` yang sudah dipakai
    ``evaluate_prescription``: memuat ``class_code`` dan ``ingredients``.
    """
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
