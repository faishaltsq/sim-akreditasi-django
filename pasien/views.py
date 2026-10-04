"""Views Manajemen Pasien — Dashboard, Daftar, Detail, Form."""
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Sum, Q
from django.http import HttpResponse, JsonResponse
from .decorators import require_patient_module
from django.utils import timezone
from datetime import timedelta

from .models import Pasien, KunjunganPasien, Bed, Ruangan, CPPT, AsesmenRisikoKlinis, BillingItem, DischargeRecord, ResepElektronik, ResepDetail, OrderPenunjang, POLIKLINIK_CHOICES, BookingKamar, GeneralConsentRawatInap
from .pdf_utils import generate_resume_pdf
from .satusehat import sync_encounter_satusehat, parse_qr_medis


# ── ICD-10 Quick Reference (80+ common inpatient codes) ──────────────────────
ICD10_CODES = [
    ('A01.0', 'Demam Tifoid'),
    ('A09', 'Gastroenteritis Akut (GEA)'),
    ('A15.0', 'Tuberkulosis Paru (TB Paru)'),
    ('A90', 'Demam Dengue (DD)'),
    ('A91', 'Demam Berdarah Dengue (DHF)'),
    ('B15.9', 'Hepatitis A Akut'),
    ('B16.9', 'Hepatitis B Akut'),
    ('B20', 'HIV / AIDS'),
    ('B34.9', 'Infeksi Virus Akut, Tidak Spesifik'),
    ('C18.9', 'Kanker Kolon'),
    ('C50.9', 'Kanker Payudara'),
    ('D50.9', 'Anemia Defisiensi Besi'),
    ('D64.9', 'Anemia, Tidak Spesifik'),
    ('E10.9', 'Diabetes Melitus Tipe 1'),
    ('E11.2', 'DM Tipe 2 dengan Nefropati'),
    ('E11.5', 'DM Tipe 2 dengan Ulkus Diabetikum'),
    ('E11.9', 'Diabetes Melitus Tipe 2'),
    ('E14.9', 'Diabetes Melitus Tidak Spesifik'),
    ('E86', 'Dehidrasi'),
    ('E87.1', 'Hiponatremia'),
    ('G40.9', 'Epilepsi'),
    ('G43.9', 'Migrain'),
    ('G44.2', 'Tension-type Headache'),
    ('H10.9', 'Konjungtivitis'),
    ('H66.9', 'Otitis Media'),
    ('I10', 'Hipertensi Esensial'),
    ('I11.9', 'Penyakit Jantung Hipertensi'),
    ('I20.9', 'Angina Pectoris'),
    ('I21.9', 'Infark Miokard Akut (IMA / STEMI)'),
    ('I50.9', 'Gagal Jantung Kongestif (CHF)'),
    ('I61.9', 'Stroke Hemoragik'),
    ('I63.9', 'Stroke Iskemik'),
    ('I64', 'Stroke, Tidak Spesifik'),
    ('J06.9', 'ISPA (Infeksi Saluran Napas Atas)'),
    ('J18.9', 'Pneumonia'),
    ('J44.9', 'PPOK (Penyakit Paru Obstruktif Kronik)'),
    ('J45.9', 'Asma Bronkial'),
    ('K21.9', 'GERD (Refluks Gastroesofageal)'),
    ('K25.9', 'Ulkus Peptikum / Tukak Lambung'),
    ('K29.7', 'Gastritis'),
    ('K35.8', 'Apendisitis Akut'),
    ('K80.2', 'Kolelitiasis (Batu Empedu)'),
    ('K81.0', 'Kolesistitis Akut'),
    ('K92.2', 'Perdarahan Saluran Cerna'),
    ('L02.9', 'Abses Kulit'),
    ('L03.9', 'Selulitis'),
    ('M54.5', 'Nyeri Punggung Bawah (LBP)'),
    ('N17.9', 'Gagal Ginjal Akut (AKI)'),
    ('N18.9', 'Gagal Ginjal Kronik (CKD)'),
    ('N20.1', 'Ureterolitiasis (Batu Ureter)'),
    ('N39.0', 'Infeksi Saluran Kemih (ISK)'),
    ('N40', 'Benign Prostatic Hyperplasia (BPH)'),
    ('O03', 'Abortus Spontan'),
    ('O14.9', 'Preeklampsia'),
    ('O60', 'Persalinan Prematur'),
    ('O80', 'Persalinan Normal Spontan'),
    ('R00.0', 'Takikardia'),
    ('R04.0', 'Epistaksis (Mimisan)'),
    ('R05', 'Batuk'),
    ('R06.0', 'Sesak Napas (Dyspnoea)'),
    ('R07.4', 'Nyeri Dada'),
    ('R10.4', 'Nyeri Perut / Kolik Abdomen'),
    ('R11', 'Mual dan Muntah'),
    ('R50.9', 'Demam, Tidak Spesifik'),
    ('R51', 'Sefalgia (Nyeri Kepala)'),
    ('R53', 'Malaise / Kelelahan'),
    ('R55', 'Sinkop (Pingsan)'),
    ('R56.0', 'Kejang Demam'),
    ('S00.9', 'Cedera Kepala Ringan (CKR)'),
    ('S02.9', 'Fraktur Tulang Tengkorak'),
    ('S06.0', 'Cedera Kepala Sedang (CKS / Commotio)'),
    ('S22.3', 'Fraktur Kosta (Tulang Rusuk)'),
    ('S42.0', 'Fraktur Klavikula'),
    ('S42.3', 'Fraktur Humerus'),
    ('S52.5', 'Fraktur Radius Distal (Colles)'),
    ('S72.0', 'Fraktur Collum Femur'),
    ('S82.2', 'Fraktur Tibia'),
    ('S82.4', 'Fraktur Fibula'),
    ('S92.9', 'Fraktur Tulang Kaki'),
    ('Z00.0', 'Pemeriksaan Kesehatan Umum (MCU)'),
    ('Z38.0', 'Bayi Baru Lahir Normal di RS'),
    ('Z48.0', 'Perawatan Luka Pasca Bedah'),
    ('Z51.1', 'Sesi Kemoterapi'),
]


def _kpi():
    now = timezone.now()
    aktif_qs = KunjunganPasien.objects.filter(status__in=['DAFTAR','TRIAGE','ASESMEN','RANAP'])

    total_pasien  = Pasien.objects.count()
    pasien_aktif  = aktif_qs.count()
    pasien_ranap  = aktif_qs.filter(jenis_kunjungan='RANAP').count()
    pasien_igd    = aktif_qs.filter(jenis_kunjungan='IGD').count()
    pasien_rajal  = aktif_qs.filter(jenis_kunjungan='RAJAL').count()

    total_bed  = Bed.objects.exclude(status='TIDAK_AKTIF').count()
    bed_terisi = Bed.objects.filter(status='TERISI').count()
    bor        = round((bed_terisi / total_bed) * 100, 1) if total_bed > 0 else 0

    pulang_qs = KunjunganPasien.objects.filter(
        status='PULANG', tanggal_keluar__gte=now - timedelta(days=30)
    )
    los_avg = 0
    if pulang_qs.exists():
        total_los = sum(k.lama_rawat for k in pulang_qs)
        los_avg = round(total_los / pulang_qs.count(), 1)

    kunjungan_week = KunjunganPasien.objects.filter(
        tanggal_masuk__gte=now - timedelta(days=7)
    ).count()

    try:
        risiko_tinggi = AsesmenRisikoKlinis.objects.filter(
            grade__in=['TINGGI', 'SANGAT_TINGGI'],
            kunjungan__status__in=['DAFTAR','TRIAGE','ASESMEN','RANAP']
        ).count()
    except Exception:
        risiko_tinggi = 0

    return {
        'total_pasien': total_pasien, 'pasien_aktif': pasien_aktif,
        'pasien_ranap': pasien_ranap, 'pasien_igd': pasien_igd,
        'pasien_rajal': pasien_rajal, 'total_bed': total_bed,
        'bed_terisi': bed_terisi, 'bor': bor,
        'los_avg': los_avg, 'kunjungan_week': kunjungan_week,
        'risiko_tinggi': risiko_tinggi,
    }


@login_required
def dashboard(request):
    try:
        kpi = _kpi()
    except Exception:
        kpi = {'total_pasien': 0, 'pasien_aktif': 0, 'pasien_ranap': 0,
               'pasien_igd': 0, 'pasien_rajal': 0, 'total_bed': 0,
               'bed_terisi': 0, 'bor': 0, 'los_avg': 0, 'kunjungan_week': 0,
               'risiko_tinggi': 0}
    try:
        ruangan_list = Ruangan.objects.prefetch_related('beds').order_by('jenis', 'kelas')
        kunjungan_terbaru = KunjunganPasien.objects.select_related('pasien', 'bed__ruangan').order_by('-created_at')[:10]
        penjamin_dist = KunjunganPasien.objects.values('penjamin').annotate(n=Count('id')).order_by('-n')
    except Exception:
        ruangan_list = []
        kunjungan_terbaru = []
        penjamin_dist = []

    now = timezone.now()
    tren = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        c = KunjunganPasien.objects.filter(tanggal_masuk__date=d.date()).count()
        tren.append({'label': d.strftime('%d/%m'), 'count': c})

    ctx = {**kpi, 'ruangan_list': ruangan_list, 'kunjungan_terbaru': kunjungan_terbaru,
           'penjamin_dist': penjamin_dist, 'tren': tren}
    return render(request, 'pasien/dashboard.html', ctx)


@login_required
def pasien_daftar(request):
    q = request.GET.get('q', '')
    qs = Pasien.objects.all()
    if q:
        qs = qs.filter(Q(nama_lengkap__icontains=q) | Q(no_rm__icontains=q) | Q(nik__icontains=q) | Q(no_bpjs__icontains=q))
    return render(request, 'pasien/pasien_daftar.html', {'pasien_list': qs[:100], 'q': q})


@login_required
def pasien_detail(request, pk):
    p = get_object_or_404(Pasien, pk=pk)
    kunjungan_list = p.kunjungan.select_related('bed__ruangan').order_by('-tanggal_masuk')
    return render(request, 'pasien/pasien_detail.html', {'pasien': p, 'kunjungan_list': kunjungan_list})


@login_required
def pasien_daftar_baru(request):
    if request.method == 'POST':
        try:
            p = Pasien(
                no_rm=request.POST['no_rm'],
                nik=request.POST.get('nik', ''),
                nama_lengkap=request.POST['nama_lengkap'],
                tanggal_lahir=request.POST['tanggal_lahir'],
                jenis_kelamin=request.POST['jenis_kelamin'],
                golongan_darah=request.POST.get('golongan_darah', '-'),
                alamat=request.POST.get('alamat', ''),
                no_hp=request.POST.get('no_hp', ''),
                no_bpjs=request.POST.get('no_bpjs', ''),
                alergi_obat=request.POST.get('alergi_obat', ''),
                alergi_lain=request.POST.get('alergi_lain', ''),
            )
            p.full_clean()
            p.save()
            messages.success(request, f'Pasien {p.nama_lengkap} berhasil didaftarkan. No. RM: {p.no_rm}')
            return redirect('pasien:pasien_detail', pk=p.pk)
        except Exception as e:
            messages.error(request, f'Gagal: {e}')
    return render(request, 'pasien/pasien_form.html', {
        'goldar_choices': Pasien.GOLDAR, 'jk_choices': Pasien.JENIS_KELAMIN,
    })


@login_required
def kunjungan_daftar(request):
    status_filter = request.GET.get('status', '')
    jenis_filter  = request.GET.get('jenis', '')
    qs = KunjunganPasien.objects.select_related('pasien', 'bed__ruangan').order_by('-tanggal_masuk')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if jenis_filter:
        qs = qs.filter(jenis_kunjungan=jenis_filter)
    ctx = {
        'kunjungan_list': qs[:100],
        'status_choices': KunjunganPasien.STATUS_KUNJUNGAN,
        'jenis_choices': KunjunganPasien.JENIS_KUNJUNGAN,
        'filter_status': status_filter, 'filter_jenis': jenis_filter,
    }
    return render(request, 'pasien/kunjungan_daftar.html', ctx)


@login_required
def kunjungan_detail(request, pk):
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien', 'bed__ruangan', 'created_by'), pk=pk)
    billing_list  = k.billing.all()
    total_billing = sum(b.subtotal for b in billing_list)
    ctx = {
        'k': k, 'cppt_list': k.cppt.all(), 'asesmen_list': k.asesmen_risiko.all(),
        'billing_list': billing_list, 'total_billing': total_billing,
        'resep_list': k.resep_list.prefetch_related('items').all(),
        'discharge': getattr(k, 'discharge', None),
        'profesi_choices': CPPT.PROFESI,
        'asesmen_choices': AsesmenRisikoKlinis.JENIS_ASESMEN,
        'grade_choices': AsesmenRisikoKlinis.GRADE,
        'billing_choices': BillingItem.KATEGORI,
        'status_choices': KunjunganPasien.STATUS_KUNJUNGAN,
        'kondisi_pulang_choices': DischargeRecord.KONDISI_PULANG,
    }
    return render(request, 'pasien/kunjungan_detail.html', ctx)


@login_required
def kunjungan_baru(request):
    if request.method == 'POST':
        try:
            pasien_obj = get_object_or_404(Pasien, pk=request.POST['pasien_id'])
            k = KunjunganPasien(
                pasien=pasien_obj,
                no_kunjungan=request.POST['no_kunjungan'],
                jenis_kunjungan=request.POST['jenis_kunjungan'],
                tanggal_masuk=request.POST['tanggal_masuk'],
                dpjp=request.POST.get('dpjp', ''),
                poliklinik=request.POST.get('poliklinik', ''),
                penjamin=request.POST.get('penjamin', 'UMUM'),
                triage=request.POST.get('triage', ''),
                catatan_admisi=request.POST.get('catatan_admisi', ''),
                general_consent=bool(request.POST.get('general_consent')),
                status='TRIAGE' if request.POST['jenis_kunjungan'] == 'IGD' else 'DAFTAR',
                created_by=request.user,
            )
            k.full_clean()
            k.save()
            messages.success(request, f'Kunjungan {k.no_kunjungan} berhasil dibuat.')
            return redirect('pasien:kunjungan_detail', pk=k.pk)
        except Exception as e:
            messages.error(request, f'Gagal: {e}')
    pasien_id = request.GET.get('pasien')
    ctx = {
        'pasien_list': Pasien.objects.order_by('nama_lengkap'),
        'selected_pasien': Pasien.objects.filter(pk=pasien_id).first() if pasien_id else None,
        'jenis_choices': KunjunganPasien.JENIS_KUNJUNGAN,
        'penjamin_choices': KunjunganPasien.TIPE_PENJAMIN,
        'triage_choices': KunjunganPasien.TRIAGE_CHOICES,
    }
    return render(request, 'pasien/kunjungan_form.html', ctx)


@login_required
def cppt_tambah(request, kunjungan_pk):
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    if request.method == 'POST':
        try:
            CPPT.objects.create(
                kunjungan=k, profesi=request.POST['profesi'],
                nama_ppa=request.POST['nama_ppa'], tanggal=request.POST['tanggal'],
                subjektif=request.POST['subjektif'], objektif=request.POST['objektif'],
                asesmen=request.POST['asesmen'], plan=request.POST['plan'],
                verifikasi_dpjp=bool(request.POST.get('verifikasi_dpjp')),
            )
            messages.success(request, 'CPPT berhasil ditambahkan.')
        except Exception as e:
            messages.error(request, f'Gagal: {e}')
    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
def billing_tambah(request, kunjungan_pk):
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    if request.method == 'POST':
        try:
            BillingItem.objects.create(
                kunjungan=k, kategori=request.POST['kategori'],
                nama_item=request.POST['nama_item'],
                kuantitas=request.POST.get('kuantitas', 1),
                harga_satuan=request.POST.get('harga_satuan', 0),
                kode_icd=request.POST.get('kode_icd', ''),
                dicatat_oleh=request.user,
            )
            messages.success(request, 'Item billing ditambahkan.')
        except Exception as e:
            messages.error(request, f'Gagal: {e}')
    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
def discharge_proses(request, kunjungan_pk):
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    if request.method == 'POST':
        try:
            total = sum(b.subtotal for b in k.billing.all())
            DischargeRecord.objects.update_or_create(
                kunjungan=k,
                defaults=dict(
                    tanggal_discharge=request.POST['tanggal_discharge'],
                    kondisi_pulang=request.POST['kondisi_pulang'],
                    resume_medis=request.POST['resume_medis'],
                    edukasi_pulang=request.POST.get('edukasi_pulang', ''),
                    obat_pulang=request.POST.get('obat_pulang', ''),
                    jadwal_kontrol=request.POST.get('jadwal_kontrol') or None,
                    total_tagihan=total,
                    status_clearance='CLEARANCE' if request.POST.get('clearance') else 'PROSES',
                    dibuat_oleh=request.user,
                )
            )
            k.status = request.POST.get('status_keluar', 'PULANG')
            k.tanggal_keluar = request.POST['tanggal_discharge']
            k.diagnosa_keluar = request.POST.get('diagnosa_keluar', '')
            k.save()
            if k.bed:
                k.bed.status = 'STERILISASI'
                k.bed.save()
            messages.success(request, 'Discharge berhasil diproses.')
        except Exception as e:
            messages.error(request, f'Gagal: {e}')
    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
@require_patient_module('ranap')
def bed_management(request):
    ruangan_list = Ruangan.objects.prefetch_related('beds').order_by('jenis', 'kelas', 'kode')
    total_bed    = Bed.objects.exclude(status='TIDAK_AKTIF').count()
    bed_terisi   = Bed.objects.filter(status='TERISI').count()
    bor = round((bed_terisi / total_bed) * 100, 1) if total_bed else 0
    return render(request, 'pasien/bed_management.html', {
        'ruangan_list': ruangan_list, 'total_bed': total_bed,
        'bed_terisi': bed_terisi, 'bor': bor,
    })


@login_required
def discharge_planning_set(request, kunjungan_pk):
    """GAP 2: Set/update discharge planning H-1 on a KunjunganPasien."""
    if request.method != 'POST':
        return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    try:
        k.discharge_planning_aktif = bool(request.POST.get('discharge_planning_aktif'))
        k.discharge_planning_catatan = request.POST.get('discharge_planning_catatan', '').strip()
        tgl = request.POST.get('discharge_planning_tgl', '').strip()
        k.discharge_planning_tgl = tgl if tgl else None
        k.save(update_fields=['discharge_planning_aktif', 'discharge_planning_catatan', 'discharge_planning_tgl'])
        messages.success(request, 'Discharge Planning berhasil diperbarui.')
    except Exception as e:
        messages.error(request, f'Gagal: {e}')
    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
def api_icd10(request):
    """GAP 3: AJAX ICD-10 quick picker — returns max 10 matches as JSON."""
    q = request.GET.get('q', '').strip().lower()
    if len(q) < 2:
        return JsonResponse([], safe=False)
    results = [
        {'kode': kode, 'nama': nama}
        for kode, nama in ICD10_CODES
        if q in kode.lower() or q in nama.lower()
    ][:10]
    return JsonResponse(results, safe=False)


@login_required
def resume_pdf(request, kunjungan_pk):
    k = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    if not hasattr(k, 'discharge'):
        messages.error(request, 'Pasien belum memiliki data discharge / resume medis.')
        return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)

    pdf_bytes = generate_resume_pdf(kunjungan_pk)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=Resume_Medis_download.pdf'
    return response


# ── GAP 4: E-Prescribing & Farmasi Views ──────────────────────────────────────

@login_required
def resep_buat(request, kunjungan_pk):
    """Dokter membuat resep elektronik dari kunjungan detail."""
    kunjungan = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    if request.method == 'POST':
        jenis_resep = request.POST.get('jenis_resep', 'RAWAT_INAP')
        catatan_dokter = request.POST.get('catatan_dokter', '').strip()

        # Nomor resep unik
        today_str = timezone.now().strftime('%Y%m%d')
        count = ResepElektronik.objects.filter(no_resep__startswith=f'RSP-{today_str}').count() + 1
        no_resep = f'RSP-{today_str}-{count:04d}'

        resep = ResepElektronik.objects.create(
            no_resep=no_resep,
            kunjungan=kunjungan,
            dokter_peresep=request.user,
            jenis_resep=jenis_resep,
            status='DIKIRIM',
            catatan_dokter=catatan_dokter,
        )

        # Simpan list obat
        nama_obat_list = request.POST.getlist('nama_obat[]')
        sediaan_list = request.POST.getlist('bentuk_sediaan[]')
        dosis_list = request.POST.getlist('dosis[]')
        aturan_list = request.POST.getlist('aturan_pakai[]')
        jumlah_list = request.POST.getlist('jumlah[]')
        harga_list = request.POST.getlist('harga_satuan[]')

        items_created = 0
        for i in range(len(nama_obat_list)):
            nama = nama_obat_list[i].strip()
            if not nama:
                continue
            sediaan = sediaan_list[i] if i < len(sediaan_list) else 'TABLET'
            dosis = dosis_list[i] if i < len(dosis_list) else '-'
            aturan = aturan_list[i] if i < len(aturan_list) else 'Sesuai Petunjuk'
            try:
                jml = max(int(jumlah_list[i]), 1)
            except (IndexError, ValueError):
                jml = 1
            try:
                hrg = max(float(harga_list[i]), 0)
            except (IndexError, ValueError):
                hrg = 0

            ResepDetail.objects.create(
                resep=resep,
                nama_obat=nama,
                bentuk_sediaan=sediaan,
                dosis=dosis,
                aturan_pakai=aturan,
                jumlah=jml,
                harga_satuan=hrg,
            )
            items_created += 1

        if items_created == 0:
            resep.delete()
            messages.error(request, 'Resep gagal dibuat: minimal harus ada 1 obat yang dimasukkan.')
        else:
            messages.success(request, f'Resep {no_resep} berhasil dikirim ke Farmasi ({items_created} obat).')

    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
@require_patient_module('farmasi')
def farmasi_antrean(request):
    """Halaman operasional Farmasi/Depo: Antrean Resep, Telaah, Dispensing & Penyerahan."""
    status_filter = request.GET.get('status', 'AKTIF')
    q = request.GET.get('q', '').strip()

    resep_qs = ResepElektronik.objects.select_related('kunjungan__pasien', 'dokter_peresep', 'apoteker').prefetch_related('items')

    if status_filter == 'AKTIF':
        resep_qs = resep_qs.filter(status__in=['DIKIRIM', 'DISPENSING'])
    elif status_filter in ['DIKIRIM', 'DISPENSING', 'SELESAI', 'BATAL']:
        resep_qs = resep_qs.filter(status=status_filter)

    if q:
        resep_qs = resep_qs.filter(
            Q(no_resep__icontains=q) |
            Q(kunjungan__pasien__nama_lengkap__icontains=q) |
            Q(kunjungan__pasien__no_rm__icontains=q)
        )

    counts = {
        'total': ResepElektronik.objects.count(),
        'dikirim': ResepElektronik.objects.filter(status='DIKIRIM').count(),
        'dispensing': ResepElektronik.objects.filter(status='DISPENSING').count(),
        'selesai': ResepElektronik.objects.filter(status='SELESAI').count(),
    }

    context = {
        'resep_list': resep_qs[:50],
        'status_filter': status_filter,
        'q': q,
        'counts': counts,
    }
    return render(request, 'pasien/farmasi_antrean.html', context)


@login_required
def resep_update_status(request, resep_pk):
    """Apoteker memproses status resep: DISPENSING, SELESAI, BATAL.
    Saat SELESAI, otomatis membuat BillingItem 'FARMASI' ke tagihan kunjungan!
    """
    resep = get_object_or_404(ResepElektronik, pk=resep_pk)
    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        catatan_apoteker = request.POST.get('catatan_apoteker', '').strip()
        if catatan_apoteker:
            resep.catatan_apoteker = catatan_apoteker

        if aksi == 'dispensing':
            resep.status = 'DISPENSING'
            resep.apoteker = request.user
            resep.save(update_fields=['status', 'apoteker', 'catatan_apoteker'])
            messages.info(request, f'Resep {resep.no_resep} sedang dalam proses dispensing/peracikan.')

        elif aksi == 'selesai':
            resep.status = 'SELESAI'
            resep.apoteker = request.user
            resep.waktu_selesai = timezone.now()
            resep.save(update_fields=['status', 'apoteker', 'waktu_selesai', 'catatan_apoteker'])

            # Otomatis catat ke BillingItem kunjungan pasien
            total_nominal = 0
            for item in resep.items.all():
                if item.harga_satuan > 0:
                    BillingItem.objects.create(
                        kunjungan=resep.kunjungan,
                        kategori='OBAT',
                        nama_item=f'Obat: {item.nama_obat} ({item.dosis})',
                        kuantitas=item.jumlah,
                        harga_satuan=item.harga_satuan,
                        dicatat_oleh=request.user,
                    )
                    total_nominal += item.subtotal

            messages.success(request, f'Resep {resep.no_resep} selesai diserahkan. Otomatis masuk tagihan billing: Rp {total_nominal:,.0f}')

        elif aksi == 'batal':
            resep.status = 'BATAL'
            resep.save(update_fields=['status', 'catatan_apoteker'])
            messages.warning(request, f'Resep {resep.no_resep} telah dibatalkan.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'pasien:farmasi_antrean'
    return redirect(next_url)


# ── GAP 5: SatuSehat Kemenkes & QR Scanner Views ──────────────────────────────

@login_required
def satusehat_sync_view(request, kunjungan_pk):
    """Kirim encounter FHIR R4 ke SatuSehat Kemenkes."""
    kunjungan = get_object_or_404(KunjunganPasien, pk=kunjungan_pk)
    result = sync_encounter_satusehat(kunjungan)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, f"Gagal SatuSehat: {result['message']}")
    return redirect('pasien:kunjungan_detail', pk=kunjungan_pk)


@login_required
def api_parse_qr(request):
    """Parse text hasil scan QR KTP/BPJS/SatuSehat."""
    if request.method == 'POST':
        import json
        try:
            body = json.loads(request.body)
            raw = body.get('qr_text', '')
        except Exception:
            raw = request.POST.get('qr_text', '')

        parsed = parse_qr_medis(raw)
        return JsonResponse(parsed)
    return JsonResponse({'error': 'POST method required'}, status=405)


# ── HELPER ANTREAN ────────────────────────────────────────────────────────────

def generate_nomor_antrean(jenis, poliklinik=''):
    """Generate daily queue number: IGD-001 or JTG-001, etc."""
    today = timezone.localdate()
    if jenis == 'IGD':
        cnt = KunjunganPasien.objects.filter(tanggal_masuk__date=today, jenis_kunjungan='IGD').count() + 1
        return f"IGD-{cnt:03d}"
    
    # Prefix mapping for clinics
    prefix_map = {
        'Jantung': 'JTG', 'Paru': 'PAR', 'Penyakit Dalam': 'INT',
        'Anak': 'PED', 'Bedah': 'BDH', 'Kandungan': 'OBG',
        'Mata': 'MTA', 'Saraf': 'SRF', 'Gigi': 'GGI',
        'THT': 'THT', 'Umum': 'UMM',
    }
    pfx = 'POL'
    for k, v in prefix_map.items():
        if k.lower() in poliklinik.lower():
            pfx = v
            break
    cnt = KunjunganPasien.objects.filter(tanggal_masuk__date=today, poliklinik__icontains=k if 'k' in locals() else '').count() + 1
    return f"{pfx}-{cnt:03d}"


# ── DASBOR KHUSUS PENDAFTARAN ─────────────────────────────────────────────────

@login_required
@require_patient_module('pendaftaran')
def pendaftaran_dashboard(request):
    """Dedicated Front-Office Registration & Routing Desk."""
    today = timezone.localdate()
    qs_today = KunjunganPasien.objects.filter(tanggal_masuk__date=today).select_related('pasien', 'created_by')

    # Bed availability summary matrix
    ruangan_list = Ruangan.objects.filter(jenis='RANAP').prefetch_related('beds')
    bed_matrix = []
    for r in ruangan_list:
        total = r.beds.exclude(status='TIDAK_AKTIF').count()
        tersedia = r.beds.filter(status='TERSEDIA').count()
        terisi = r.beds.filter(status='TERISI').count()
        bed_matrix.append({
            'ruangan': r,
            'total': total,
            'tersedia': tersedia,
            'terisi': terisi,
            'persen': round((terisi / total) * 100) if total else 0
        })

    ctx = {
        'kunjungan_hari_ini':  qs_today.order_by('-tanggal_masuk')[:100],
        'total_hari_ini':      qs_today.count(),
        'ke_igd':              qs_today.filter(jenis_kunjungan='IGD').count(),
        'ke_rajal':            qs_today.filter(jenis_kunjungan='RAJAL').count(),
        'ke_ranap':            qs_today.filter(jenis_kunjungan='RANAP').count(),
        'poliklinik_choices':  POLIKLINIK_CHOICES,
        'triage_choices':      KunjunganPasien.TRIAGE_CHOICES,
        'penjamin_choices':    KunjunganPasien.TIPE_PENJAMIN,
        'pasien_recent':       Pasien.objects.order_by('-created_at')[:10],
        'pasien_list':         Pasien.objects.order_by('nama_lengkap'),
        'bed_matrix':          bed_matrix,
    }
    return render(request, 'pasien/pendaftaran_dashboard.html', ctx)


@login_required
def api_cek_nik(request):
    """API endpoint to check duplicate NIK / No RM."""
    nik = request.GET.get('nik', '').strip()
    no_rm = request.GET.get('no_rm', '').strip()
    p = None
    if nik:
        p = Pasien.objects.filter(nik=nik).first()
    elif no_rm:
        p = Pasien.objects.filter(no_rm=no_rm).first()
    
    if p:
        return JsonResponse({
            'exists': True,
            'pasien': {
                'id': p.pk,
                'no_rm': p.no_rm,
                'nama': p.nama_lengkap,
                'nik': p.nik,
                'tanggal_lahir': p.tanggal_lahir.strftime('%Y-%m-%d'),
                'jenis_kelamin': p.get_jenis_kelamin_display(),
                'no_bpjs': p.no_bpjs,
                'alamat': p.alamat,
            }
        })
    return JsonResponse({'exists': False})


@login_required
def pendaftaran_route(request, pk):
    """Route a registered visit to IGD or Poli Rawat Jalan."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        tujuan = request.POST.get('tujuan')
        dpjp = request.POST.get('dpjp', '')
        flag = request.POST.get('flag_khusus', 'NORMAL')
        try:
            if tujuan == 'IGD':
                k.jenis_kunjungan = 'IGD'
                k.triage = request.POST.get('triage', 'HIJAU')
                k.flag_khusus = flag
                k.status = 'TRIAGE'
                k.status_antrean = 'MENUNGGU'
                if not k.nomor_antrean:
                    k.nomor_antrean = generate_nomor_antrean('IGD')
                if dpjp:
                    k.dpjp = dpjp
                k.save()
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} diarahkan ke IGD ({k.get_triage_display()}) — Antrean: {k.nomor_antrean}.')
                return redirect('pasien:igd_dashboard')
            elif tujuan == 'RAJAL':
                poli_dict = dict(POLIKLINIK_CHOICES)
                poli_key = request.POST.get('poliklinik', '')
                k.jenis_kunjungan = 'RAJAL'
                k.poliklinik = poli_dict.get(poli_key, poli_key)
                k.flag_khusus = flag
                k.status = 'DAFTAR'
                k.status_antrean = 'MENUNGGU'
                if not k.nomor_antrean:
                    k.nomor_antrean = generate_nomor_antrean('RAJAL', k.poliklinik)
                if dpjp:
                    k.dpjp = dpjp
                k.save()
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} diarahkan ke {k.poliklinik} — Antrean: {k.nomor_antrean}.')
                return redirect('pasien:rajal_dashboard')
            else:
                messages.error(request, 'Pilih tujuan: IGD atau Poli Rawat Jalan.')
        except Exception as e:
            messages.error(request, f'Gagal routing: {e}')
    return redirect('pasien:pendaftaran_dashboard')


# ── DASBOR IGD ───────────────────────────────────────────────────────────────

@login_required
@require_patient_module('igd')
def igd_dashboard(request):
    """Dedicated Emergency Department (IGD) Clinical Dashboard with Dwell-Time."""
    triage_filter = request.GET.get('triage', '')
    qs = KunjunganPasien.objects.filter(
        jenis_kunjungan='IGD',
        status__in=['TRIAGE', 'ASESMEN', 'DAFTAR']
    ).select_related('pasien', 'bed')

    if triage_filter:
        qs = qs.filter(triage=triage_filter)
    qs = qs.order_by('triage', 'tanggal_masuk')

    def _cnt(t):
        return KunjunganPasien.objects.filter(jenis_kunjungan='IGD', status__in=['TRIAGE', 'ASESMEN', 'DAFTAR'], triage=t).count()

    available_beds = (
        Bed.objects.filter(status='TERSEDIA')
        .select_related('ruangan')
        .order_by('ruangan__kelas', 'ruangan__kode', 'kode_bed')
    )
    try:
        critical_orders = (
            OrderPenunjang.objects.filter(
                kunjungan__jenis_kunjungan='IGD',
                is_critical_value=True
            )
            .select_related('kunjungan__pasien')
            .order_by('-created_at')[:5]
        )
        critical_orders = list(critical_orders)  # force eval now
    except Exception:
        critical_orders = []
    try:
        active_bookings = list(
            BookingKamar.objects.filter(
                status='BOOKED',
                batas_waktu__gte=timezone.now()
            )
            .select_related('pasien', 'bed__ruangan')
            .order_by('-waktu_booking')[:10]
        )
    except Exception:
        active_bookings = []
    ctx = {
        'pasien_igd_list':    qs,
        'triage_filter':      triage_filter,
        'count_merah':        _cnt('MERAH'),
        'count_kuning':       _cnt('KUNING'),
        'count_hijau':        _cnt('HIJAU'),
        'count_hitam':        _cnt('HITAM'),
        'available_beds':     available_beds,
        'critical_orders':    critical_orders,
        'active_bookings':    active_bookings,
        'triage_choices':     KunjunganPasien.TRIAGE_CHOICES,
        'kondisi_choices':    DischargeRecord.KONDISI_PULANG,
    }
    return render(request, 'pasien/igd_dashboard.html', ctx)


@login_required
def igd_ttv_update(request, pk):
    """Quick TTV & Tindakan ICD-9-CM entry from IGD dashboard."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        try:
            k.ttv_sistole = int(request.POST['ttv_sistole']) if request.POST.get('ttv_sistole') else None
            k.ttv_diastole = int(request.POST['ttv_diastole']) if request.POST.get('ttv_diastole') else None
            k.ttv_nadi = int(request.POST['ttv_nadi']) if request.POST.get('ttv_nadi') else None
            k.ttv_rr = int(request.POST['ttv_rr']) if request.POST.get('ttv_rr') else None
            k.ttv_suhu = float(request.POST['ttv_suhu']) if request.POST.get('ttv_suhu') else None
            k.ttv_spo2 = int(request.POST['ttv_spo2']) if request.POST.get('ttv_spo2') else None
            k.ttv_gcs = request.POST.get('ttv_gcs', '').strip()
            k.ttv_skala_nyeri = int(request.POST['ttv_skala_nyeri']) if request.POST.get('ttv_skala_nyeri') else None
            k.icd9_tindakan = request.POST.get('icd9_tindakan', '').strip()
            k.status = 'ASESMEN'
            k.save()
            messages.success(request, f'TTV Pasien {k.pasien.nama_lengkap} berhasil diperbarui.')
        except Exception as e:
            messages.error(request, f'Gagal update TTV: {e}')
    return redirect('pasien:igd_dashboard')


# ── DASBOR POLI RAWAT JALAN ───────────────────────────────────────────────────

@login_required
@require_patient_module('rajal')
def rajal_dashboard(request):
    """Dedicated Outpatient Clinics (Poli Rawat Jalan) Dashboard."""
    poli_filter = request.GET.get('poli', '')
    qs = KunjunganPasien.objects.filter(
        jenis_kunjungan='RAJAL',
        status__in=['DAFTAR', 'ASESMEN']
    ).select_related('pasien')

    if poli_filter:
        qs = qs.filter(poliklinik__icontains=poli_filter)
    qs = qs.order_by('status_antrean', 'tanggal_masuk')

    available_beds = (
        Bed.objects.filter(status='TERSEDIA')
        .select_related('ruangan')
        .order_by('ruangan__kelas', 'ruangan__kode', 'kode_bed')
    )

    poli_counts = {}
    for code, label in POLIKLINIK_CHOICES:
        poli_counts[code] = {
            'label': label,
            'count': KunjunganPasien.objects.filter(
                jenis_kunjungan='RAJAL',
                status__in=['DAFTAR', 'ASESMEN'],
                poliklinik__icontains=label[:15]
            ).count()
        }

    try:
        active_bookings = list(
            BookingKamar.objects.filter(
                status='BOOKED',
                batas_waktu__gte=timezone.now()
            )
            .select_related('pasien', 'bed__ruangan')
            .order_by('-waktu_booking')[:10]
        )
    except Exception:
        active_bookings = []
    try:
        critical_orders = list(
            OrderPenunjang.objects.filter(
                kunjungan__jenis_kunjungan='RAJAL',
                is_critical_value=True
            )
            .select_related('kunjungan__pasien')
            .order_by('-created_at')[:5]
        )
    except Exception:
        critical_orders = []

    ctx = {
        'pasien_rajal_list':   qs,
        'poli_filter':         poli_filter,
        'poliklinik_choices':  POLIKLINIK_CHOICES,
        'poli_counts':         poli_counts,
        'available_beds':      available_beds,
        'active_bookings':     active_bookings,
        'critical_orders':     critical_orders,
        'kondisi_choices':     DischargeRecord.KONDISI_PULANG,
    }
    return render(request, 'pasien/rajal_dashboard.html', ctx)


@login_required
def rajal_antrean_status(request, pk):
    """Update Outpatient queue caller status (MENUNGGU/DIPANGGIL/SEDANG_DILAYANI/SELESAI)."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        st = request.POST.get('status_antrean')
        if st in ['MENUNGGU', 'DIPANGGIL', 'SEDANG_DILAYANI', 'SELESAI']:
            k.status_antrean = st
            if st == 'SEDANG_DILAYANI':
                k.status = 'ASESMEN'
            k.save()
            messages.info(request, f'Status Antrean {k.nomor_antrean} ({k.pasien.nama_lengkap}) diubah ke {k.get_status_antrean_display()}.')
    return redirect('pasien:rajal_dashboard')


@login_required
def order_penunjang_buat(request, pk):
    """Direct-entry diagnostic order (Lab / Radiologi) from doctor's desk."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        jenis = request.POST.get('jenis', 'LAB')
        nama = request.POST.get('nama_pemeriksaan', '').strip()
        catatan = request.POST.get('catatan_klinis', '').strip()
        prioritas = request.POST.get('prioritas', 'RUTIN')
        is_critical = request.POST.get('is_critical_value') in ('1', 'true', 'True', 'on')
        critical_catatan = request.POST.get('critical_value_catatan', '').strip()
        if nama:
            OrderPenunjang.objects.create(
                kunjungan=k,
                jenis=jenis,
                nama_pemeriksaan=nama,
                catatan_klinis=catatan,
                prioritas=prioritas,
                dokter_pengirim=request.user.get_full_name() or request.user.username,
                is_critical_value=is_critical,
                critical_value_catatan=critical_catatan,
            )
            # Automatic billing item
            base_price = 150000 if jenis == 'LAB' else 250000
            BillingItem.objects.create(
                kunjungan=k,
                kategori='LAB' if jenis == 'LAB' else 'RADIOLOGI',
                nama_item=f'Pemeriksaan {jenis}: {nama}',
                kuantitas=1,
                harga_satuan=base_price,
                dicatat_oleh=request.user,
            )
            messages.success(request, f'Order {jenis} "{nama}" berhasil dikirim & ditambahkan ke billing.')
        else:
            messages.error(request, 'Nama pemeriksaan tidak boleh kosong.')
    back = 'pasien:igd_dashboard' if k.jenis_kunjungan == 'IGD' else 'pasien:rajal_dashboard'
    return redirect(back)


@login_required
def rajal_soap_simpan(request, pk):
    """Direct entry SOAP note -> saves into integrated CPPT."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    if request.method == 'POST':
        s = request.POST.get('subjektif', '').strip()
        o = request.POST.get('objektif', '').strip()
        a = request.POST.get('asesmen', '').strip()
        p = request.POST.get('plan', '').strip()
        if s or o or a or p:
            CPPT.objects.create(
                kunjungan=k,
                profesi='DOKTER',
                nama_ppa=request.user.get_full_name() or request.user.username,
                tanggal=timezone.now(),
                subjektif=s or '-',
                objektif=o or '-',
                asesmen=a or '-',
                plan=p or '-',
                verifikasi_dpjp=True,
            )
            messages.success(request, f'Catatan SOAP untuk {k.pasien.nama_lengkap} berhasil disimpan ke CPPT.')
        else:
            messages.error(request, 'Harap isi minimal salah satu elemen SOAP.')
    return redirect('pasien:rajal_dashboard')


# ── DISPOSISI KLINIS COMPREHENSIVE (IGD & RAJAL) ──────────────────────────────

@login_required
def kunjungan_disposisi(request, pk):
    """Comprehensive disposition handler — Sembuh, PAPS, Ranap (SPRI), SISRUTE, Meninggal, Konsul."""
    k = get_object_or_404(KunjunganPasien, pk=pk)
    back = 'pasien:igd_dashboard' if k.jenis_kunjungan == 'IGD' else 'pasien:rajal_dashboard'
    back = request.POST.get('next_url', back)

    if request.method == 'POST':
        aksi = request.POST.get('aksi')
        try:
            if aksi == 'PULANG':
                k.discharge_patient(
                    kondisi=request.POST.get('kondisi_pulang', 'MEMBAIK'),
                    resume=request.POST.get('resume_medis', 'Pelayanan rawat jalan / IGD selesai.'),
                    user=request.user,
                    edukasi=request.POST.get('edukasi_pulang', ''),
                    obat=request.POST.get('obat_pulang', ''),
                    kontrol=request.POST.get('jadwal_kontrol') or None,
                )
                k.status_antrean = 'SELESAI'
                # If SKDP requested
                if request.POST.get('jadwal_kontrol'):
                    today_str = timezone.localdate().strftime('%Y%m%d')
                    k.discharge.skdp_nomor = f"SKDP-{today_str}-{k.pk:04d}"
                    k.discharge.skdp_diagnosa = request.POST.get('resume_medis', '')[:200]
                    k.discharge.skdp_terapi = request.POST.get('obat_pulang', '')
                    k.discharge.save()
                k.save()
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} berhasil dipulangkan.')

            elif aksi == 'PAPS':
                k.discharge_patient(
                    kondisi='APS',
                    resume=request.POST.get('resume_medis', 'Pulang Atas Permintaan Sendiri (PAPS).'),
                    user=request.user,
                    edukasi='Telah diedukasi risiko perburukan dan penolakan rawat.',
                )
                k.status_antrean = 'SELESAI'
                k.discharge.paps_alasan = request.POST.get('paps_alasan', '')
                k.discharge.paps_nama_penolak = request.POST.get('paps_nama_penolak', '')
                k.discharge.save()
                k.save()
                messages.warning(request, f'Pasien {k.pasien.nama_lengkap} dipulangkan PAPS (Refusal recorded).')

            elif aksi == 'RANAP':
                bed_id = request.POST.get('bed_id')
                if not bed_id:
                    raise ValueError('Pilih Bed rawat inap terlebih dahulu.')
                bed_obj = get_object_or_404(Bed, pk=bed_id)
                k.admit_to_ranap(
                    bed=bed_obj,
                    dpjp=request.POST.get('dpjp', k.dpjp),
                    catatan=request.POST.get('catatan_admisi', ''),
                )
                k.status_antrean = 'SELESAI'
                k.save()
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} berhasil masuk Rawat Inap di {bed_obj}.')
                return redirect('pasien:cetak_spri', pk=k.pk)

            elif aksi == 'RUJUK_EKSTERNAL':
                k.status = 'RUJUK'
                k.status_antrean = 'SELESAI'
                k.sisrute_rs_tujuan = request.POST.get('sisrute_rs_tujuan', '')
                k.sisrute_alasan = request.POST.get('sisrute_alasan', '')
                if k.bed:
                    k.bed.status = 'STERILISASI'
                    k.bed.save()
                    k.bed = None
                k.save()
                messages.info(request, f'Pasien {k.pasien.nama_lengkap} dirujuk keluar ke {k.sisrute_rs_tujuan} (SISRUTE).')

            elif aksi == 'MENINGGAL':
                from django.utils.dateparse import parse_datetime
                k.status = 'MENINGGAL'
                k.status_antrean = 'SELESAI'
                waktu_str = request.POST.get('waktu_kematian')
                k.waktu_kematian = parse_datetime(waktu_str) if waktu_str else timezone.now()
                k.penyebab_kematian = request.POST.get('penyebab_kematian', '')
                if k.bed:
                    k.bed.status = 'STERILISASI'
                    k.bed.save()
                    k.bed = None
                k.save()
                # Create discharge record for mortuary
                DischargeRecord.objects.update_or_create(
                    kunjungan=k,
                    defaults={
                        'tanggal_discharge': k.waktu_kematian,
                        'kondisi_pulang': 'MENINGGAL',
                        'resume_medis': f"Penyebab kematian: {k.penyebab_kematian}",
                        'status_clearance': 'CLEARANCE',
                        'dibuat_oleh': request.user,
                    }
                )
                messages.error(request, f'Protokol Pasien Meninggal Dunia tercatat untuk {k.pasien.nama_lengkap}. Notifikasi kamar jenazah diteruskan.')

            elif aksi == 'KONSUL_INTERNAL':
                target_poli = request.POST.get('konsul_ke_poli')
                if not target_poli:
                    raise ValueError('Pilih Poliklinik tujuan konsul.')
                k.konsul_ke_poli = target_poli
                k.konsul_catatan = request.POST.get('konsul_catatan', '')
                k.poliklinik = target_poli
                k.status_antrean = 'MENUNGGU'
                k.nomor_antrean = generate_nomor_antrean('RAJAL', target_poli)
                k.status = 'DAFTAR'
                k.save()
                messages.success(request, f'Pasien {k.pasien.nama_lengkap} berhasil dialihkan antrean ke {target_poli} ({k.nomor_antrean}).')

            else:
                messages.error(request, 'Aksi disposisi tidak dikenali.')
        except Exception as e:
            messages.error(request, f'Gagal disposisi: {e}')
    return redirect(back)


# ── PRINTABLE VIEWS ───────────────────────────────────────────────────────────

@login_required
def cetak_gelang(request, pk):
    """Printable patient identity wristband (thermal standard 25x280mm)."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien'), pk=pk)
    return render(request, 'pasien/cetak_gelang.html', {'k': k, 'p': k.pasien})


@login_required
def cetak_sep(request, pk):
    """Printable BPJS Surat Eligibilitas Peserta (SEP)."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien'), pk=pk)
    today_str = timezone.localdate().strftime('%Y%m%d')
    no_sep = f"0123R001{today_str}000{k.pk}"
    return render(request, 'pasien/cetak_sep.html', {'k': k, 'p': k.pasien, 'no_sep': no_sep})


@login_required
def cetak_spri(request, pk):
    """Printable Surat Perintah Rawat Inap (SPRI)."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien', 'bed__ruangan'), pk=pk)
    today_str = timezone.localdate().strftime('%Y%m%d')
    no_spri = f"SPRI-{today_str}-{k.pk:04d}"
    return render(request, 'pasien/cetak_spri.html', {'k': k, 'p': k.pasien, 'no_spri': no_spri})


@login_required
def cetak_skdp(request, pk):
    """Printable Surat Keterangan Dalam Perawatan (SKDP / Surat Kontrol)."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien'), pk=pk)
    discharge = getattr(k, 'discharge', None)
    return render(request, 'pasien/cetak_skdp.html', {'k': k, 'p': k.pasien, 'discharge': discharge})


# ── PEMESANAN KAMAR (BOOKING BED) & GENERAL CONSENT RANAP ─────────────────────

@login_required
def booking_kamar_buat(request, kunjungan_id):
    """Pesan / booking tempat tidur rawat inap dari IGD atau Poliklinik."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien'), pk=kunjungan_id)
    back = request.META.get('HTTP_REFERER') or (
        'pasien:igd_dashboard' if k.jenis_kunjungan == 'IGD' else 'pasien:rajal_dashboard'
    )
    if request.method == 'POST':
        bed_id = request.POST.get('bed_id')
        durasi_jam = int(request.POST.get('durasi_jam', 2))
        catatan = request.POST.get('catatan', '').strip()

        if not bed_id:
            messages.error(request, 'Pilih bed / tempat tidur yang tersedia terlebih dahulu.')
            return redirect(back)

        bed = get_object_or_404(Bed, pk=bed_id)
        if bed.status != 'TERSEDIA':
            messages.error(request, f'Tempat tidur {bed.ruangan.nama} - {bed.kode_bed} tidak tersedia (status: {bed.get_status_display()}).')
            return redirect(back)

        now = timezone.now()
        nomor_booking = f"BK-{now.strftime('%Y%m%d')}-{k.pk:04d}-{bed.pk}"
        batas_waktu = now + timedelta(hours=durasi_jam)

        BookingKamar.objects.create(
            nomor_booking=nomor_booking,
            pasien=k.pasien,
            kunjungan=k,
            bed=bed,
            batas_waktu=batas_waktu,
            catatan=catatan,
            petugas=request.user
        )
        messages.success(
            request,
            f'Tempat tidur {bed.ruangan.nama} ({bed.kode_bed}) berhasil dipesan/dibooking '
            f'untuk {k.pasien.nama_lengkap}. No. Booking: {nomor_booking}. Berlaku hingga {batas_waktu.strftime("%H:%M WIB")}.'
        )
    return redirect(back)


@login_required
def booking_kamar_batal(request, booking_id):
    """Batalkan pemesanan tempat tidur dan lepaskan bed ke status TERSEDIA."""
    booking = get_object_or_404(BookingKamar.objects.select_related('bed', 'kunjungan'), pk=booking_id)
    alasan = request.POST.get('alasan_batal', request.GET.get('alasan', 'Dibatalkan oleh petugas/keluarga pasien'))
    booking.batalkan(alasan=alasan)
    messages.info(request, f'Pemesanan kamar {booking.nomor_booking} telah dibatalkan. Bed {booking.bed} kini TERSEDIA.')
    back = request.META.get('HTTP_REFERER') or 'pasien:bed_management'
    return redirect(back)


@login_required
def booking_kamar_checkin(request, booking_id):
    """Check-in pasien ke kamar ranap dari reservasi booking."""
    booking = get_object_or_404(BookingKamar.objects.select_related('bed', 'kunjungan', 'pasien'), pk=booking_id)
    booking.checkin()
    messages.success(request, f'Pasien {booking.pasien.nama_lengkap} resmi masuk (check-in) ke {booking.bed.ruangan.nama} - {booking.bed.kode_bed}.')
    if booking.kunjungan:
        return redirect('pasien:kunjungan_detail', pk=booking.kunjungan.pk)
    return redirect('pasien:bed_management')


@login_required
def api_bed_tersedia(request):
    """JSON API untuk memuat daftar tempat tidur TERSEDIA (bisa difilter kelas)."""
    kelas = request.GET.get('kelas')
    qs = Bed.objects.filter(status='TERSEDIA').select_related('ruangan')
    if kelas:
        qs = qs.filter(ruangan__kelas=kelas)
    qs = qs.order_by('ruangan__kelas', 'ruangan__nama', 'kode_bed')
    data = [
        {
            'id': b.id,
            'kode_bed': b.kode_bed,
            'ruangan_nama': b.ruangan.nama,
            'kelas': b.ruangan.kelas,
            'kelas_display': b.ruangan.get_kelas_display(),
            'label': f"{b.ruangan.nama} — Bed {b.kode_bed} ({b.ruangan.get_kelas_display()})"
        }
        for b in qs
    ]
    return JsonResponse({'status': 'ok', 'beds': data})


@login_required
def general_consent_simpan(request, kunjungan_id):
    """Simpan / perbarui Formulir Persetujuan Rawat Inap (General Consent Ranap STARKES HPK)."""
    k = get_object_or_404(KunjunganPasien.objects.select_related('pasien'), pk=kunjungan_id)
    back = request.META.get('HTTP_REFERER') or (
        'pasien:igd_dashboard' if k.jenis_kunjungan == 'IGD' else 'pasien:rajal_dashboard'
    )
    if request.method == 'POST':
        nama_pj = request.POST.get('nama_pj', '').strip()
        nik_pj = request.POST.get('nik_pj', '').strip()
        hubungan = request.POST.get('hubungan', 'DIRI_SENDIRI')
        telepon_pj = request.POST.get('telepon_pj', '').strip()
        alamat_pj = request.POST.get('alamat_pj', '').strip()

        setuju_perawatan = request.POST.get('setuju_perawatan_umum') in ('1', 'true', 'True', 'on')
        setuju_informasi = request.POST.get('setuju_pelepasan_informasi') in ('1', 'true', 'True', 'on')
        setuju_tatatertib = request.POST.get('setuju_tata_tertib') in ('1', 'true', 'True', 'on')
        nama_anggota = request.POST.get('nama_anggota_akses_info', '').strip()

        jaminan = request.POST.get('jaminan_biaya', 'BPJS')
        selisih = request.POST.get('pernyataan_selisih_biaya') in ('1', 'true', 'True', 'on')

        if not nama_pj or not nik_pj:
            messages.error(request, 'Nama dan NIK Penanggung Jawab wajib diisi.')
            return redirect(back)

        GeneralConsentRawatInap.objects.update_or_create(
            kunjungan=k,
            defaults={
                'nama_pj': nama_pj,
                'nik_pj': nik_pj,
                'hubungan': hubungan,
                'telepon_pj': telepon_pj,
                'alamat_pj': alamat_pj,
                'setuju_perawatan_umum': setuju_perawatan,
                'setuju_pelepasan_informasi': setuju_informasi,
                'setuju_tata_tertib': setuju_tatatertib,
                'nama_anggota_akses_info': nama_anggota,
                'jaminan_biaya': jaminan,
                'pernyataan_selisih_biaya': selisih,
                'petugas_saksi': request.user
            }
        )
        k.general_consent = True
        k.save(update_fields=['general_consent'])
        messages.success(request, f'General Consent Rawat Inap untuk {k.pasien.nama_lengkap} berhasil disimpan dan ditandatangani.')
    return redirect(back)


@login_required
def cetak_general_consent(request, pk):
    """Cetak Dokumen Akreditasi Standar STARKES HPK: Formulir General Consent Rawat Inap (A4)."""
    k = get_object_or_404(
        KunjunganPasien.objects.select_related('pasien', 'bed__ruangan', 'dpjp'),
        pk=pk
    )
    consent = getattr(k, 'general_consent_doc', None)
    return render(request, 'pasien/cetak_general_consent.html', {
        'k': k,
        'p': k.pasien,
        'consent': consent,
        'petugas': request.user,
        'now': timezone.now()
    })


# ── DASBOR LABORATORIUM & LIS ────────────────────────────────────────────────

@login_required
@require_patient_module('laboratorium')
def laboratorium_dashboard(request):
    """Dashboard Worklist Laboratorium: order penunjang, nilai kritis, verifikasi hasil."""
    status_filter = request.GET.get('status', '')
    orders_qs = OrderPenunjang.objects.filter(
        jenis='LAB'
    ).select_related('kunjungan__pasien').order_by('-created_at')

    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)

    try:
        critical_orders = list(OrderPenunjang.objects.filter(
            jenis='LAB', is_critical_value=True
        ).exclude(status='SELESAI').select_related('kunjungan__pasien'))
    except Exception:
        critical_orders = []

    return render(request, 'pasien/laboratorium_dashboard.html', {
        'orders': orders_qs[:100],
        'critical_orders': critical_orders,
        'total_pending': orders_qs.filter(status='ORDERED').count(),
        'total_proses': orders_qs.filter(status='PROSES').count(),
        'total_selesai': orders_qs.filter(status='SELESAI').count(),
        'status_filter': status_filter,
    })


@login_required
@require_patient_module('laboratorium')
def order_penunjang_update(request, pk):
    """Update status, hasil, dan flag critical value order penunjang Lab."""
    order = get_object_or_404(OrderPenunjang, pk=pk)
    if request.method == 'POST':
        order.status = request.POST.get('status', order.status)
        order.hasil_pemeriksaan = request.POST.get('hasil_pemeriksaan', order.hasil_pemeriksaan)
        order.is_critical_value = request.POST.get('is_critical_value') == '1'
        order.critical_value_catatan = request.POST.get('critical_value_catatan', '')
        order.save()
        messages.success(request, f'Order #{order.pk} ({order.nama_pemeriksaan}) berhasil diperbarui.')
    return redirect(request.META.get('HTTP_REFERER', reverse('pasien:laboratorium_dashboard')))



