"""F8.4 — panel pratinjau longitudinal RME untuk dasbor antrean.

Matriks §5 (Bagian F) menuntut ikon Detail membuka panel berisi riwayat
kunjungan, tren TTV/LVEF, badge alergi, dan daftar obat GDMT aktif. Semua
angkanya dibaca dari data yang sudah ada:

* **TTV** — episode POLI-JANTUNG menyimpan TTV di ``draft_payload`` langkah 4
  (ADR-9; jalur rajal tidak menulis kolom ``KunjunganPasien``), sedangkan
  kunjungan lama menyimpannya di kolom. Urutan sumber itu dipakai apa adanya,
  bukan dikarang.
* **LVEF** — ``OrderPenunjang.lvef`` (F4.3), hanya order yang benar-benar
  punya nilai.
* **Obat aktif** — seluruh baris resep terakhir berstatus ``SELESAI``.
* **Alergi** — ``AlergiPasienTerstruktur`` aktif ditambah kolom teks lama
  ``Pasien.alergi_obat``/``alergi_lain``.

Formularium GDMT hari ini tidak punya produk yang dapat diresepkan
(AMBIGU-19). Karena itu panel **menghitung** jumlah produk yang layak resep
dan menyatakan kosongnya bila memang nol — tidak ada baris obat karangan.
"""
from pasien.models import IgdAssessmentWorkflow, KunjunganPasien, OrderPenunjang, ResepElektronik
from pasien.services.igd_assessment_workflow import RAJAL_JANTUNG_SERVICE_LINE
from pasien.unit_scope import scope_kunjungan_qs

#: Riwayat kunjungan yang ditampilkan; bukan pagination UI, sekadar batas panel.
VISIT_HISTORY_LIMIT = 10

#: Kolom TTV yang dipakai panel; sama dengan kolom ``KunjunganPasien``.
TTV_FIELDS = ('ttv_sistole', 'ttv_diastole', 'ttv_nadi', 'ttv_spo2')
TTV_LABELS = {
    'ttv_sistole': 'Sistole',
    'ttv_diastole': 'Diastole',
    'ttv_nadi': 'Nadi',
    'ttv_spo2': 'SpO2',
}

def _present(value):
    return value is not None and value != ''

def _ttv_from_workflow(workflow):
    """TTV langkah 4 episode POLI-JANTUNG, atau ``None`` bila belum diisi."""
    if workflow is None or workflow.service_line != RAJAL_JANTUNG_SERVICE_LINE:
        return None
    values = (workflow.draft_payload or {}).get('4') or {}
    if not any(_present(values.get(name)) for name in TTV_FIELDS):
        return None
    return {name: values.get(name) for name in TTV_FIELDS if _present(values.get(name))}

def _ttv_from_visit(visit):
    values = {name: getattr(visit, name) for name in TTV_FIELDS if _present(getattr(visit, name))}
    return values or None

def _ttv_point(visit, workflow):
    """Satu titik tren TTV beserta sumbernya, atau ``None`` bila tak terukur."""
    from_workflow = _ttv_from_workflow(workflow)
    values = from_workflow or _ttv_from_visit(visit)
    if not values:
        return None
    return {
        'tanggal': visit.tanggal_masuk,
        'kunjungan': visit,
        'source': 'Asesmen POLI-JANTUNG (langkah 4)' if from_workflow else 'Kunjungan',
        'values': values,
    }

def active_allergies(pasien):
    """Baris alergi aktif: terstruktur lebih dulu, lalu kolom teks lama."""
    rows = []
    for allergy in pasien.structured_allergies.filter(active=True).order_by('pk'):
        code = allergy.ingredient_code or allergy.therapy_class_code or 'Zat tidak dikodekan'
        rows.append({
            'label': code,
            'reaction': allergy.reaction,
            'source': 'Terstruktur',
        })
    for field, label in (('alergi_obat', 'Alergi obat'), ('alergi_lain', 'Alergi lain')):
        text = (getattr(pasien, field) or '').strip()
        if text:
            rows.append({'label': label, 'reaction': text, 'source': 'Catatan lama'})
    return rows

def prescribable_gdmt_products():
    """Jumlah produk GDMT yang benar-benar dapat diresepkan hari ini.

    Dipakai untuk menyatakan sebab daftar obat kosong; angkanya dihitung dari
    katalog (``gdmt_panel``), bukan ditulis sebagai kalimat tetap.
    """
    from pasien.services.gdmt import gdmt_panel

    return sum(
        1
        for group in gdmt_panel()
        for product in group['products']
        if product['prescribable']
    )

def longitudinal_panel(visit, profile):
    """Susun data panel pratinjau untuk satu kunjungan.

    Riwayat dibatasi lingkup unit profil lewat ``scope_kunjungan_qs`` — panel
    tidak boleh menampilkan kunjungan yang tidak boleh dibuka pengguna.
    """
    visits = list(
        scope_kunjungan_qs(
            KunjunganPasien.objects.filter(pasien_id=visit.pasien_id), profile,
        )
        .select_related('unit_kerja')
        .order_by('-tanggal_masuk', '-pk')[:VISIT_HISTORY_LIMIT]
    )
    visit_ids = [row.pk for row in visits]
    workflows = {
        workflow.kunjungan_id: workflow
        for workflow in IgdAssessmentWorkflow.objects.filter(kunjungan_id__in=visit_ids)
    }

    history = []
    ttv_points = []
    for row in visits:
        workflow = workflows.get(row.pk)
        ttv = _ttv_point(row, workflow)
        history.append({
            'kunjungan': row,
            'ttv': ttv,
            'lvef': None,
            'workflow_status': workflow.status if workflow is not None else '',
        })
        if ttv is not None:
            ttv_points.append(ttv)

    lvef_points = [
        {'tanggal': order.created_at, 'kunjungan_id': order.kunjungan_id,
         'nama_pemeriksaan': order.nama_pemeriksaan, 'lvef': order.lvef}
        for order in OrderPenunjang.objects.filter(
            kunjungan_id__in=visit_ids, lvef__isnull=False,
        ).order_by('created_at', 'pk')
    ]
    latest_lvef = {}
    for point in lvef_points:
        latest_lvef[point['kunjungan_id']] = point['lvef']
    for entry in history:
        entry['lvef'] = latest_lvef.get(entry['kunjungan'].pk)

    prescription = (
        ResepElektronik.objects.filter(
            kunjungan_id__in=visit_ids, status='SELESAI',
        )
        .prefetch_related('items')
        .order_by('-tanggal_resep', '-pk')
        .first()
    )
    medications = [
        {'nama_obat': item.nama_obat, 'dosis': item.dosis,
         'aturan_pakai': item.aturan_pakai, 'jumlah': item.jumlah}
        for item in (prescription.items.all() if prescription is not None else [])
    ]

    return {
        'history': history,
        # Tren dibaca dari yang terlama ke terbaru supaya arah waktu alami.
        'ttv_points': list(reversed(ttv_points)),
        'lvef_points': lvef_points,
        'active_prescription': prescription,
        'active_medications': medications,
        # Alasan daftar kosong hanya dihitung saat daftar memang kosong.
        'prescribable_gdmt_products': None if medications else prescribable_gdmt_products(),
        'allergies': active_allergies(visit.pasien),
    }
