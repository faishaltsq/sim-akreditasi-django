# Implementation Plan: UX Asesmen Awal IGD + Menu Sidebar Jadwal/Logbook

**Tanggal:** 2026-11-04
**Sumber dokumen user:**
1. `Penambahan di arima asesmen awal igd.docx` — usulan UX formulir asesmen awal IGD
2. `Tambahan menu di pendaftaran.docx` — bridging + jadwal/logbook + RME/antrean (sudah dikerjakan sebelumnya; sisa: menu sidebar)

---

## ANALISIS (Gap Analysis)

### Dokumen 1 — Asesmen Awal IGD

Formulir existing: modal `#modalAsesmenAwal{{ k.pk }}` di `templates/pasien/igd_dashboard.html` (7 tab pill: Anamnesis, Fisik, Bio, Diagnosis, Triase, Secondary, SBAR; ~930 baris) + form paralel di `templates/pasien/kunjungan_detail.html` (seksi A–E). View: `pasien/views.py:1966` (`igd_asesmen_awal_save`). Field: `KunjunganPasien` (`pasien/models.py:361-493`).

| Usulan dokumen | Status existing | Keputusan |
|---|---|---|
| 1. Multi-step wizard (4 langkah) | ✅ Sudah 7 tab pill | Skip — sudah terpenuhi |
| 2. Smart default "Set Normal / Baik" | ❌ Belum ada | Task 2 |
| 3. Auto-calc MST + slider nyeri berwarna | ❌ MST & nyeri masih input angka manual | Task 1 |
| 4. Auto-fill alergi dari data pasien | ⚠️ Alergi ada di master (`Pasien.alergi_obat/alergi_lain`) tapi tidak tampil di form asesmen | Task 3 |
| 4b. Tombol "Salin dari Asesmen Sebelumnya" | ❌ Belum ada | Task 3 |

### Dokumen 2 — Tambahan menu pendaftaran

Bridging V-Claim/SatuSehat, Jadwal Dinus, Logbook, RME ringkas, Antrean: **sudah diimplementasikan** (10 commit terakhir, 123 tests OK). Sisa eksplisit dari dokumen: *"Jadwal Dinas dan Logbook Harian (pakai yang sudah ada) menunya ada di side kiri dimunculkan"* — saat ini hanya Tab 8 di dalam dasbor, **belum ada entri menu di sidebar** (`templates/includes/sidebar.html`).

| Sisa kebutuhan | Status | Keputusan |
|---|---|---|
| Menu sidebar Jadwal Dinas & Logbook | ❌ Hanya Tab 8 internal | Task 4 |

---

## DESAIN

- **Tanpa model/migrasi baru.** MST & nyeri sudah jadi field `KunjunganPasien` (`skrining_gizi_mst`, `ttv_skala_nyeri`).
- **MST dihitung ulang di server** (`igd_asesmen_awal_save`) dari 2 pertanyaan (`mst_q1`, `mst_q2`) — client-side JS hanya untuk tampilan live. POST lama yang hanya kirim `skrining_gizi_mst` tetap diterima (backward-compat).
- **Slider nyeri 0–10** menggantikan/menyanding number input existing; warna badge: 0 hijau, 1–3 kuning, 4–6 oranye, 7–10 merah.
- **Smart default** mengisi: keadaan_umum=Baik, kesadaran=Compos Mentis, nyeri=0, MST q1/q2=0, TTV standar (TD 120/80, nadi 80, suhu 36.5, SpO2 98). Petugas tetap bisa ubah per-field.
- **Alergi banner**: tampil di atas form jika `pasien.alergi_obat`/`alergi_lain` terisi; info-read-only (sumber data tetap master pasien).
- **Salin dari Asesmen Sebelumnya**: endpoint baru `pasien:igd_asesmen_copy_prev` mengambil kunjungan terakhir (selain kunjungan ini, `tanggal_masuk` terbaru) milik pasien yang sama, menyalin field asesmen non-klinis: `keadaan_umum`, `kesadaran`, `nyeri_karakteristik`, `fungsional_adl`, `skrining_gizi_mst`, `skrining_jatuh_skor`, `skrining_jatuh_grade`, `anamnesis_rps`, `anamnesis_rpd`, `anamnesis_rpk`, `anamnesis_obat`, `status_psikososial`. TTV & diagnosis **tidak** disalin (data sesi ini).
- **Sidebar**: 2 entri di grup Pendaftaran (`templates/includes/sidebar.html`) → `pasien:pendaftaran_dashboard?tab=shift`; view mengaktifkan Tab 8 saat `?tab=shift` (satu baris template conditional `active`).
  - `ponytail:` link ke tab existing, bukan halaman baru. Tambah halaman dedicated hanya bila butuh riwayat lintas-tanggal.

---

## TASKS

### Task 1: MST auto-calc (2 pertanyaan → skor + status label)

**Files:**
- Modify: `templates/pasien/igd_dashboard.html` (Tab 3, section "Skrining Gizi (MST)" ~baris 1603)
- Modify: `pasien/views.py` (`igd_asesmen_awal_save`)
- Test: `pasien/tests_asesmen_awal_ux.py` (baru)
- Modify: `templates/pasien/kunjungan_detail.html` (section C ~baris 460) — mirror

**Step 1: Tulis test (gagal dulu).**

```python
class MstAutoCalcTest(TestCase):
    def setUp(self):
        self.pasien = Pasien.objects.create(no_rm='RM-MST-001', nik='3201000000000101',
            nama_lengkap='Mst Pasien', tanggal_lahir='1990-01-01', jenis_kelamin='L')
        self.k = KunjunganPasien.objects.create(pasien=self.pasien, jenis_kunjungan='IGD',
            no_kunjungan='IGD-MST-001', tanggal_masuk=timezone.now())
        self.client.force_login(User.objects.create_user('mstuser'))

    def _post(self, **extra):
        return self.client.post(reverse('pasien:igd_asesmen_awal_save', args=[self.k.pk]),
                                {'anamnesis_rps': 'Sakit', **extra})

    def test_mst_score_computed_from_two_questions(self):
        self._post(mst_q1='2', mst_q2='1')
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 3)

    def test_mst_zero_when_no_risk_answers(self):
        self._post(mst_q1='0', mst_q2='0')
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 0)

    def test_legacy_manual_score_still_accepted(self):
        self._post(skrining_gizi_mst='4')  # POST lama tanpa mst_q*
        self.k.refresh_from_db()
        self.assertEqual(self.k.skrining_gizi_mst, 4)
```

**Step 2: Run — expect gagal** (`skrining_gizi_mst` tetap 0 / tidak ter-set dari mst_q*).

**Step 3: Implementasi.**

Template (igd_dashboard + kunjungan_detail) — ganti input angka tunggal:

```html
<div class="row g-2">
    <div class="col-md-6">
        <label class="form-label small fw-semibold">1. Penurunan berat badan tidak diinginkan?</label>
        <select name="mst_q1" class="form-select form-select-sm" id="mstQ1_{{ k.pk }}">
            <option value="0">Tidak ada penurunan (0)</option>
            <option value="1">Ya, 1–5 kg (1)</option>
            <option value="2">Tidak yakin / > 5 kg (2)</option>
        </select>
    </div>
    <div class="col-md-6">
        <label class="form-label small fw-semibold">2. Asupan makan berkurang (kurang nafsu makan)?</label>
        <select name="mst_q2" class="form-select form-select-sm" id="mstQ2_{{ k.pk }}">
            <option value="0">Tidak (0)</option>
            <option value="1">Ya (1)</option>
        </select>
    </div>
    <div class="col-12">
        <div class="alert alert-success py-1 px-2 mb-0 small" id="mstResult_{{ k.pk }}">
            Total MST: <strong>{{ k.skrining_gizi_mst|default:0 }}</strong> —
            {% if k.skrining_gizi_mst and k.skrining_gizi_mst >= 2 %}
                <span class="text-danger fw-bold">Risiko Malnutrisi Tinggi — Konsul Ahli Gizi</span>
            {% else %}
                <span class="text-success">Risiko Malnutrisi Rendah</span>
            {% endif %}
        </div>
    </div>
</div>
```

JS (script block template, scoped per modal — gunakan querySelector dalam modal yang sama):

```javascript
// MST auto-calc
document.querySelectorAll('[id^="mstQ1_"]').forEach(function(q1) {
    var pk = q1.id.split('_')[1];
    var q2 = document.getElementById('mstQ2_' + pk);
    var out = document.getElementById('mstResult_' + pk);
    function hitung() {
        var total = (parseInt(q1.value) || 0) + (parseInt(q2.value) || 0);
        out.className = 'alert py-1 px-2 mb-0 small ' + (total >= 2 ? 'alert-danger' : 'alert-success');
        out.innerHTML = 'Total MST: <strong>' + total + '</strong> — ' +
            (total >= 2 ? '<span class="fw-bold">Risiko Malnutrisi Tinggi — Konsul Ahli Gizi</span>'
                        : '<span>Risiko Malnutrisi Rendah</span>');
    }
    q1.addEventListener('change', hitung);
    q2.addEventListener('change', hitung);
});
```

View (`igd_asesmen_awal_save`, dekat blok skrining existing):

```python
# Skrining Gizi (MST) — hitung ulang dari 2 pertanyaan; fallback input manual legacy
q1 = request.POST.get('mst_q1', '').strip()
q2 = request.POST.get('mst_q2', '').strip()
if q1.isdigit() and q2.isdigit():
    k.skrining_gizi_mst = min(int(q1) + int(q2), 5)
elif request.POST.get('skrining_gizi_mst', '').strip().isdigit():
    k.skrining_gizi_mst = min(int(request.POST['skrining_gizi_mst']), 5)
```

**Step 4: Run — expect hijau.**
**Step 5: Commit** `feat(pasien): auto-calculate MST nutrition score from screening questions`

---

### Task 2: Smart default "Set Normal / Baik" + slider nyeri berwarna

**Files:**
- Modify: `templates/pasien/igd_dashboard.html` (Tab 3 header section + script)
- Modify: `templates/pasien/kunjungan_detail.html` (section A/B — mirror)
- Test: `pasien/tests_asesmen_awal_ux.py`

**Step 1: Test.**

```python
class SmartDefaultUiTest(TestCase):
    def test_igd_dashboard_has_smart_default_and_pain_slider(self):
        # login + 1 kunjungan IGD aktif
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'setNormalAsesmen')      # tombol smart default
        self.assertContains(res, 'type="range"')          # slider nyeri
        self.assertContains(res, 'skorNyeriBadge')        # badge warna nyeri
        self.assertContains(res, 'Set Normal / Baik')
```

**Step 2: Run — expect gagal** (assertContains).

**Step 3: Implementasi.**

Tombol (atas Tab 3 / section A):

```html
<button type="button" class="btn btn-outline-success btn-sm" id="setNormalAsesmen_{{ k.pk }}"
        title="Isi otomatis parameter normal">
    ⚡ Set Normal / Baik
</button>
```

Slider nyeri (ganti number input `ttv_skala_nyeri`, keep name sama):

```html
<input type="range" class="form-range" min="0" max="10" step="1"
       name="ttv_skala_nyeri" id="skorNyeri_{{ k.pk }}"
       value="{{ k.ttv_skala_nyeri|default:0 }}"
       oninput="updateSkorNyeri('{{ k.pk }}', this.value)">
<span class="badge" id="skorNyeriBadge_{{ k.pk }}">0 — Tidak ada nyeri</span>
```

JS:

```javascript
function updateSkorNyeri(pk, val) {
    var badge = document.getElementById('skorNyeriBadge_' + pk);
    var cls = 'bg-success', ket = 'Tidak ada nyeri';
    if (val >= 1 && val <= 3) { cls = 'bg-warning text-dark'; ket = 'Nyeri ringan'; }
    else if (val >= 4 && val <= 6) { cls = 'bg-orange text-dark'; ket = 'Nyeri sedang'; }
    else if (val >= 7) { cls = 'bg-danger'; ket = 'Nyeri berat'; }
    badge.className = 'badge ' + cls;
    badge.innerText = val + ' — ' + ket;
}

function setNormalAsesmen(pk) {
    var set = function(name, val) {
        var el = document.querySelector('#modalAsesmenAwal' + pk + ' [name="' + name + '"]');
        if (el) el.value = val;
    };
    var check = function(name, val) {
        var el = document.querySelector('#modalAsesmenAwal' + pk + ' ' +
            '[name="' + name + '"][value="' + val + '"]');
        if (el) el.checked = true;
    };
    check('keadaan_umum', 'Baik');
    check('kesadaran', 'Compos Mentis');
    check('nyeri_karakteristik', 'Hilang-Timbul');
    check('fungsional_adl', 'Mandiri');
    set('mst_q1', '0'); set('mst_q2', '0');
    set('ttv_sistole', '120'); set('ttv_diastole', '80');
    set('ttv_nadi', '80'); set('ttv_suhu', '36.5'); set('ttv_spo2', '98');
    updateSkorNyeri(pk, 0);
    // trigger hitung MST agar label ikut refresh
    var q1 = document.getElementById('mstQ1_' + pk);
    if (q1) q1.dispatchEvent(new Event('change'));
}
```

Wire: `onclick="setNormalAsesmen('{{ k.pk }}')"` pada tombol; panggil `updateSkorNyeri('{{ k.pk }}', {{ k.ttv_skala_nyeri|default:0 }})` saat modal load (script inline bawah modal).

**Step 4: Run — expect hijau.**
**Step 5: Commit** `feat(ui): smart default & color pain slider on IGD initial assessment`

---

### Task 3: Alergi banner + "Salin dari Asesmen Sebelumnya"

**Files:**
- Modify: `pasien/views.py` (view baru `igd_asesmen_copy_prev`), `pasien/urls.py`
- Modify: `templates/pasien/igd_dashboard.html` (banner + tombol di header modal)
- Test: `pasien/tests_asesmen_awal_ux.py`

**Step 1: Test.**

```python
class AlergiDanCopyPrevTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('asesmenuser')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(no_rm='RM-COPY-001', nik='3201000000000102',
            nama_lengkap='Copy Prev', tanggal_lahir='1985-03-03', jenis_kelamin='P',
            alergi_obat='Debu, Udang')
        self.prev = KunjunganPasien.objects.create(pasien=self.pasien, jenis_kunjungan='IGD',
            no_kunjungan='IGD-PREV', tanggal_masuk=timezone.now() - timedelta(days=5),
            anamnesis_rps='Batuk sejak seminggu', keadaan_umum='Sedang',
            kesadaran='Compos Mentis', skrining_gizi_mst=2, status_psikososial='Cemas / Gelisah')
        self.k = KunjunganPasien.objects.create(pasien=self.pasien, jenis_kunjungan='IGD',
            no_kunjungan='IGD-NEW', tanggal_masuk=timezone.now())

    def test_alergi_banner_shown_in_igd_dashboard(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertContains(res, 'Debu, Udang')

    def test_copy_from_previous_assessment(self):
        res = self.client.get(reverse('pasien:igd_asesmen_copy_prev', args=[self.k.pk]))
        self.assertRedirects(res, reverse('pasien:igd_dashboard'))
        self.k.refresh_from_db()
        self.assertEqual(self.k.anamnesis_rps, 'Batuk sejak seminggu')
        self.assertEqual(self.k.keadaan_umum, 'Sedang')
        self.assertEqual(self.k.skrining_gizi_mst, 2)
        self.assertEqual(self.k.status_psikososial, 'Cemas / Gelisah')

    def test_copy_prev_no_previous_is_noop(self):
        k2 = KunjunganPasien.objects.create(pasien=Pasien.objects.create(
            no_rm='RM-COPY-002', nik='3201000000000103', nama_lengkap='No Prev',
            tanggal_lahir='1990-01-01', jenis_kelamin='L'),
            jenis_kunjungan='IGD', no_kunjungan='IGD-NOPREV', tanggal_masuk=timezone.now())
        res = self.client.get(reverse('pasien:igd_asesmen_copy_prev', args=[k2.pk]))
        self.assertEqual(res.status_code, 302)  # redirect dengan pesan, tidak error
```

**Step 2: Run — expect gagal** (NoReverseMatch).

**Step 3: Implementasi.**

`urls.py`:

```python
path('kunjungan/<int:pk>/asesmen-copy-prev/', views.igd_asesmen_copy_prev, name='igd_asesmen_copy_prev'),
```

`views.py`:

```python
COPY_PREV_FIELDS = [
    'keadaan_umum', 'kesadaran', 'nyeri_karakteristik', 'fungsional_adl',
    'skrining_gizi_mst', 'skrining_jatuh_skor', 'skrining_jatuh_grade',
    'anamnesis_rps', 'anamnesis_rpd', 'anamnesis_rpk', 'anamnesis_obat',
    'status_psikososial',
]

@login_required
def igd_asesmen_copy_prev(request, pk):
    """Salin field asesmen non-klinis dari kunjungan terakhir pasien yang sama."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    prev = (KunjunganPasien.objects
            .filter(pasien=k.pasien, tanggal_masuk__lt=k.tanggal_masuk)
            .exclude(pk=k.pk).order_by('-tanggal_masuk').first())
    if prev is None:
        messages.info(request, 'Belum ada asesmen sebelumnya untuk pasien ini.')
        return redirect('pasien:igd_dashboard')
    for f in COPY_PREV_FIELDS:
        setattr(k, f, getattr(prev, f))
    k.save()
    messages.success(request, f'Asesmen disalin dari kunjungan {prev.no_kunjungan}.')
    return redirect('pasien:igd_dashboard')
```

Template — banner alergi + tombol copy di header modal (sebelum nav tabs):

```html
{% if k.pasien.alergi_obat or k.pasien.alergi_lain %}
<div class="alert alert-danger d-flex align-items-center gap-2 mb-2 py-1 small">
    <i class="bi bi-exclamation-triangle-fill"></i>
    <span><strong>Riwayat Alergi:</strong> {{ k.pasien.alergi_obat }}{% if k.pasien.alergi_lain %}; {{ k.pasien.alergi_lain }}{% endif %}</span>
</div>
{% endif %}
<button type="button" class="btn btn-outline-secondary btn-sm"
        onclick="location.href='{% url 'pasien:igd_asesmen_copy_prev' k.pk %}'">
    <i class="bi bi-clipboard-check me-1"></i>Salin dari Asesmen Sebelumnya
</button>
```

**Step 4: Run — expect hijau.**
**Step 5: Commit** `feat(pasien): allergy banner & copy-from-previous assessment`

---

### Task 4: Menu sidebar Jadwal Dinas & Logbook

**Files:**
- Modify: `templates/includes/sidebar.html`
- Modify: `pasien/views.py` (`pendaftaran_dashboard` — aktivasi tab via `?tab=shift`)
- Modify: `templates/pasien/pendaftaran_dashboard.html` (conditional `active` pada `#tab-shift`/`#pane-shift`)
- Test: `pasien/tests_asesmen_awal_ux.py`

**Step 1: Test.**

```python
class SidebarMenuTest(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('sidebaruser'))

    def test_sidebar_has_jadwal_logbook_menus(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard'))
        self.assertContains(res, "{% url 'pasien:pendaftaran_dashboard' %}?tab=shift")
        self.assertContains(res, 'Jadwal Dinas')
        self.assertContains(res, 'Logbook Harian')

    def test_tab_shift_activated_by_query_param(self):
        res = self.client.get(reverse('pasien:pendaftaran_dashboard') + '?tab=shift')
        content = res.content.decode()
        self.assertIn('tab-shift active', content)   # nav button
        self.assertIn('pane-shift active', content)  # pane
```

**Step 2: Run — expect gagal.**

**Step 3: Implementasi.**

`sidebar.html` — di grup Pendaftaran, setelah link `pendaftaran_dashboard` (~baris 234):

```html
<a href="{% url 'pasien:pendaftaran_dashboard' %}?tab=shift" class="nav-link{% if u == 'pendaftaran_dashboard' and request.GET.tab == 'shift' %} active{% endif %}">
    <i class="bi bi-person-badge me-2"></i>Jadwal Dinas &amp; Logbook
</a>
```

`pendaftaran_dashboard.html` — nav button:

```html
<button class="nav-link text-nowrap{% if request.GET.tab == 'shift' %} active{% endif %}" id="tab-shift" ...>
```

pane:

```html
<div class="tab-pane fade{% if request.GET.tab == 'shift' %} show active{% endif %} p-4" id="pane-shift" role="tabpanel">
```

View: tanpa perubahan (query param ditangani template).
`ponytail:` entri mengarah ke Tab 8 existing, bukan halaman baru. Tambah halaman dedicated hanya bila butuh riwayat lintas-tanggal/filter petugas.

**Step 4: Run — expect hijau.**
**Step 5: Commit** `feat(ui): surface Jadwal Dinas & Logbook in left sidebar menu`

---

### Task 5: Full regression

**Step 1:** `python manage.py test pasien`
**Step 2:** Expect OK (baseline 123 + test baru).
**Step 3:** Commit fix bila ada (pesan plan `fix(pasien): regression fixes from asesmen awal UX`).

---

## CATATAN EKSEKUSI

- TDD per task: test dulu → gagal → implementasi → hijau → commit.
- Windows/PowerShell: redirect output test ke file log (`> $env:TEMP\opencode\tX.log 2>&1`) lalu cek `$LASTEXITCODE`; pipe langsung ke `Select-Object` bisa melaporkan exit code 1 palsu.
- `kunjungan_detail.html` memakai form paralel dengan nama field identik — mirror perubahan Task 1–2 secara mekanis (id tanpa `{{ k.pk }}` di template itu; pakai id statis).

---

## EXECUTION STATUS (2026-11-04)

### Done
- **Task 1:** MST auto-calc (2 pertanyaan q1 + q2 → auto total & alert status) di `pasien/views.py`, `templates/pasien/igd_dashboard.html`, dan `templates/pasien/kunjungan_detail.html`. ✅ 4 tests OK.
- **Task 2:** Smart default button "⚡ Set Normal / Baik" + slider nyeri 0-10 dinamis dengan badge warna responsif di `templates/pasien/igd_dashboard.html` & `templates/pasien/kunjungan_detail.html`. ✅ 1 test OK.
- **Task 3:** Banner riwayat alergi obat/lain & tombol "Salin dari Asesmen Sebelumnya" (endpoint `pasien:igd_asesmen_copy_prev` menyalin parameter non-klinis) di `pasien/views.py`, `pasien/urls.py`, `templates/pasien/igd_dashboard.html`, dan `templates/pasien/kunjungan_detail.html`. ✅ 3 tests OK.
- **Task 4:** Menu sidebar "Jadwal Dinas & Logbook" di grup Pasien (`templates/includes/sidebar.html`) yang langsung membuka Tab 8 pada `pendaftaran_dashboard.html` via query param `?tab=shift`. ✅ 2 tests OK.
- **Task 5:** Full regression suite pasien app. ✅ **133 tests OK** (0 failure, 0 error).

### Git Commits
1. `850e041` docs(plan): UX asesmen awal IGD & sidebar menu jadwal/logbook
2. `f52e5d5` feat(pasien): auto-calculate MST nutrition score from screening questions
3. `a982181` feat(ui): smart default & color pain slider on IGD initial assessment
4. `9622d1d` feat(pasien): allergy banner & copy-from-previous assessment
5. `ff4da73` feat(ui): surface Jadwal Dinas & Logbook in left sidebar menu
