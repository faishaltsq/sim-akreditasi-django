"""Views Manajemen Pasien — Dashboard, Daftar, Detail, Form."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Sum, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import Pasien, KunjunganPasien, Bed, Ruangan, CPPT, AsesmenRisikoKlinis, BillingItem, DischargeRecord, ResepElektronik, ResepDetail
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

    risiko_tinggi = AsesmenRisikoKlinis.objects.filter(
        grade__in=['TINGGI', 'SANGAT_TINGGI'],
        kunjungan__status__in=['DAFTAR','TRIAGE','ASESMEN','RANAP']
    ).count()

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
    kpi = _kpi()
    ruangan_list     = Ruangan.objects.prefetch_related('beds').order_by('jenis', 'kelas')
    kunjungan_terbaru = KunjunganPasien.objects.select_related('pasien', 'bed__ruangan').order_by('-created_at')[:10]
    penjamin_dist    = KunjunganPasien.objects.values('penjamin').annotate(n=Count('id')).order_by('-n')

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

