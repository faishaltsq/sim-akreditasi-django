import json
import uuid
import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli, POLIKLINIK_CHOICES
from pasien.services.whatsapp import format_tiket_wa, format_notifikasi_igd, kirim_pesan_wa
from pasien.services.bpjs_antrean import update_task_id
from akreditasi.models import RumahSakitProfile

PREFIX_POLI = {
    'POLI_JANTUNG': 'JTG',
    'POLI_PARU': 'PRU',
    'POLI_PENYAKIT_DALAM': 'PDL',
    'POLI_BEDAH': 'BDH',
    'POLI_ANAK': 'ANK',
    'POLI_OBGYN': 'OBG',
    'POLI_MATA': 'MTA',
    'POLI_SARAF': 'SRF',
    'POLI_THT': 'THT',
    'POLI_GIGI': 'GGI',
    'POLI_ORTHO': 'ORT',
    'POLI_KULIT': 'KLT',
    'POLI_JIWA': 'JWA',
    'REHAB_MEDIK': 'RHB',
    'POLI_ENDOKRIN': 'END',
    'POLI_BSARAF': 'BSF',
    'POLI_UMUM': 'UMM',
}


def apm_kiosk_view(request):
    """Layar Utama Kiosk Touchscreen Anjungan Pendaftaran Mandiri (APM)"""
    rs = RumahSakitProfile.objects.first()
    daftar_poli = [
        {
            'kode': code,
            'nama': name,
            'prefix': PREFIX_POLI.get(code, 'POL')
        }
        for code, name in POLIKLINIK_CHOICES
    ]
    context = {
        'rs': rs,
        'daftar_poli': daftar_poli,
    }
    return render(request, 'pasien/apm/kiosk.html', context)


@require_http_methods(["GET"])
def apm_api_cari_pasien(request):
    """
    API Pencarian data pasien lama via NIK, No. BPJS, atau No. Rekam Medis.
    Mencegah duplikasi data pasien.
    """
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'found': False, 'message': 'Parameter pencarian q wajib diisi.'}, status=400)

    clean_q = q.replace('-', '').replace(' ', '').replace('.', '')
    
    pasien = Pasien.objects.filter(
        Q(nik=clean_q) |
        Q(no_bpjs=clean_q) |
        Q(no_rm__iexact=q) |
        Q(no_rm__iexact=clean_q)
    ).first()

    if not pasien:
        return JsonResponse({
            'found': False,
            'message': 'Pasien tidak ditemukan. Silakan lakukan pendaftaran sebagai Pasien Baru.'
        })

    return JsonResponse({
        'found': True,
        'pasien': {
            'id': pasien.id,
            'no_rm': pasien.no_rm,
            'nama_lengkap': pasien.nama_lengkap,
            'tanggal_lahir': pasien.tanggal_lahir.strftime('%Y-%m-%d') if pasien.tanggal_lahir else '',
            'jenis_kelamin': pasien.jenis_kelamin,
            'nik': pasien.nik or '',
            'no_bpjs': pasien.no_bpjs or '',
            'no_hp': pasien.no_hp or '',
            'alamat': pasien.alamat or '',
        }
    })


@require_http_methods(["GET"])
def apm_api_jadwal_dokter(request):
    """
    API Ketersediaan Dokter dan Sisa Kuota Real-Time untuk Poliklinik Tertentu.
    """
    poli = request.GET.get('poli')
    qs = JadwalDokterPoli.objects.filter(status_ketersediaan='BUKA')
    if poli:
        qs = qs.filter(poliklinik=poli)

    hasil = []
    for j in qs:
        hasil.append({
            'id': j.id,
            'nama_dokter': j.nama_dokter,
            'gelar': j.gelar,
            'poliklinik': j.poliklinik,
            'poliklinik_display': j.get_poliklinik_display(),
            'hari_praktik': j.hari_praktik,
            'jam_mulai': j.jam_mulai.strftime('%H:%M'),
            'jam_selesai': j.jam_selesai.strftime('%H:%M'),
            'kuota_maksimal': j.kuota_maksimal,
            'sisa_kuota': j.get_sisa_kuota(),
            'durasi_per_pasien_menit': j.durasi_per_pasien_menit,
            'status_ketersediaan': j.status_ketersediaan,
            'is_tersedia': j.is_tersedia(),
            'foto_url': j.foto_url or (j.foto_dokter.url if j.foto_dokter else ''),
            'keterangan': j.keterangan,
        })

    return JsonResponse({'success': True, 'jadwal': hasil})


@csrf_exempt
@require_http_methods(["POST"])
def apm_api_daftar(request):
    """
    Endpoint Registrasi Kunjungan Mandiri (APM) - Rajal atau Fast-Track IGD.
    Menjamin kuota tidak race condition via transaction.atomic().
    """
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = {}
    else:
        data = request.POST.dict()

    tipe_pasien = data.get('tipe_pasien', 'LAMA').upper()
    jenis_layanan = data.get('jenis_layanan', 'RAJAL').upper()
    no_wa = (data.get('no_wa') or '').strip()
    penjamin = (data.get('penjamin') or 'UMUM').upper()

    with transaction.atomic():
        # 1. Resolusi Pasien
        if tipe_pasien == 'BARU':
            nama = data.get('nama_lengkap', '').strip()
            nik = (data.get('nik') or '').strip()
            tgl_lahir_str = data.get('tanggal_lahir')
            jk = data.get('jenis_kelamin', 'L')
            alamat = data.get('alamat', '')
            no_bpjs = data.get('no_bpjs', '')

            if not nama or not tgl_lahir_str:
                return JsonResponse({'success': False, 'message': 'Nama lengkap dan tanggal lahir wajib diisi.'}, status=400)

            # Jika NIK sudah ada, reuse pasien
            if nik:
                pasien = Pasien.objects.filter(nik=nik).first()
            else:
                pasien = None

            if not pasien:
                # Generate No RM Baru: RM-YYYYMMDD-XXXX
                today_str = timezone.localdate().strftime('%Y%m%d')
                count_today = Pasien.objects.filter(no_rm__startswith=f"RM-{today_str}").count() + 1
                new_no_rm = f"RM-{today_str}-{count_today:04d}"

                try:
                    tgl_lahir = datetime.date.fromisoformat(tgl_lahir_str)
                except Exception:
                    tgl_lahir = timezone.localdate()

                pasien = Pasien.objects.create(
                    no_rm=new_no_rm,
                    nama_lengkap=nama,
                    nik=nik,
                    tanggal_lahir=tgl_lahir,
                    jenis_kelamin=jk,
                    alamat=alamat,
                    no_hp=no_wa,
                    no_bpjs=no_bpjs
                )
        else: # Pasien LAMA
            no_rm = data.get('no_rm', '').strip()
            nik = data.get('nik', '').strip()
            no_bpjs = data.get('no_bpjs', '').strip()

            pasien = Pasien.objects.filter(
                Q(no_rm__iexact=no_rm) |
                (Q(nik=nik) if nik else Q(pk__isnull=True)) |
                (Q(no_bpjs=no_bpjs) if no_bpjs else Q(pk__isnull=True))
            ).first()

            if not pasien:
                return JsonResponse({'success': False, 'message': 'Data pasien lama tidak ditemukan.'}, status=404)

            if no_wa and pasien.no_hp != no_wa:
                pasien.no_hp = no_wa
                pasien.save(update_fields=['no_hp'])

        # 2. Generate Booking & Token Batal
        now = timezone.now()
        today_date = timezone.localdate()
        random_suffix = uuid.uuid4().hex[:4].upper()
        no_kunjungan = f"REG-APM-{now.strftime('%Y%m%d%H%M%S')}-{random_suffix}"
        token_batal = uuid.uuid4().hex[:12].upper()
        kode_booking = f"APM-{today_date.strftime('%Y%m%d')}-{random_suffix}"

        # 3. Alur Pelayanan: IGD vs RAJAL
        if jenis_layanan == 'IGD':
            count_igd = KunjunganPasien.objects.filter(
                tanggal_masuk__date=today_date,
                jenis_kunjungan='IGD'
            ).count() + 1
            nomor_antrean = f"IGD-{count_igd:03d}"
            estimasi_jam = timezone.localtime().time()

            kunjungan = KunjunganPasien.objects.create(
                pasien=pasien,
                no_kunjungan=no_kunjungan,
                jenis_kunjungan='IGD',
                tanggal_masuk=now,
                poliklinik='IGD',
                dpjp='Dokter Jaga IGD',
                nomor_antrean=nomor_antrean,
                penjamin=penjamin,
                flag_khusus='MERAH', # Fast-Track Emergency Priority
                status_antrean='MENUNGGU',
                kode_booking=kode_booking,
                token_batal=token_batal,
                estimasi_pelayanan=estimasi_jam,
                is_apm=True
            )

            # Notifikasi WhatsApp IGD Emergency
            if no_wa or pasien.no_hp:
                msg_igd = format_notifikasi_igd(kunjungan)
                kirim_pesan_wa(no_wa or pasien.no_hp, msg_igd, jenis_pesan='NOTIFIKASI_IGD', kunjungan=kunjungan)

        else: # RAJAL
            jadwal_id = data.get('jadwal_id')
            poliklinik = data.get('poliklinik')

            if jadwal_id:
                jadwal = JadwalDokterPoli.objects.select_for_update().filter(pk=jadwal_id).first()
            elif poliklinik:
                jadwal = JadwalDokterPoli.objects.select_for_update().filter(poliklinik=poliklinik, status_ketersediaan='BUKA').first()
            else:
                jadwal = None

            if not jadwal:
                return JsonResponse({'success': False, 'message': 'Jadwal dokter tidak ditemukan.'}, status=400)

            if not jadwal.is_tersedia(today_date):
                return JsonResponse({'success': False, 'message': 'Mohon maaf, kuota dokter untuk hari ini sudah penuh.'}, status=400)

            urutan = jadwal.get_terdaftar_hari_ini(today_date) + 1
            prefix = PREFIX_POLI.get(jadwal.poliklinik, 'POL')
            nomor_antrean = f"{prefix}-{urutan:03d}"
            estimasi_jam = jadwal.hitung_estimasi_jam(urutan)

            kunjungan = KunjunganPasien.objects.create(
                pasien=pasien,
                no_kunjungan=no_kunjungan,
                jenis_kunjungan='RAJAL',
                tanggal_masuk=now,
                poliklinik=jadwal.poliklinik,
                dpjp=jadwal.nama_dokter,
                nomor_antrean=nomor_antrean,
                penjamin=penjamin,
                status_antrean='MENUNGGU',
                kode_booking=kode_booking,
                token_batal=token_batal,
                estimasi_pelayanan=estimasi_jam,
                is_apm=True
            )

            # Catat Task ID 1 (Mulai Waktu Tunggu Admisi) jika BPJS
            if penjamin == 'BPJS':
                update_task_id(kunjungan, 1)

            # Kirim Tiket Digital WhatsApp
            target_wa = no_wa or pasien.no_hp
            if target_wa:
                wa_body = format_tiket_wa(kunjungan, base_url=request.build_absolute_uri('/')[:-1])
                kirim_pesan_wa(target_wa, wa_body, jenis_pesan='TIKET_APM', kunjungan=kunjungan)

    return JsonResponse({
        'success': True,
        'kunjungan_id': kunjungan.id,
        'no_kunjungan': kunjungan.no_kunjungan,
        'nomor_antrean': kunjungan.nomor_antrean,
        'jenis_kunjungan': kunjungan.jenis_kunjungan,
        'kode_booking': kunjungan.kode_booking,
        'token_batal': kunjungan.token_batal,
        'estimasi_pelayanan': kunjungan.estimasi_pelayanan.strftime('%H:%M') if kunjungan.estimasi_pelayanan else '',
        'dpjp': kunjungan.dpjp,
        'poliklinik': kunjungan.get_poliklinik_display() if hasattr(kunjungan, 'get_poliklinik_display') else kunjungan.poliklinik,
        'struk_url': reverse('pasien:apm_cetak_struk', kwargs={'pk': kunjungan.pk})
    })


@csrf_exempt
@require_http_methods(["POST", "GET"])
def apm_api_checkin(request):
    """
    Check-In Mandiri Kiosk via Pemindaian Barcode/QR Code Tiket WA / KTP / No. RM.
    Mencatat kehadiran pasien dan memicu Task ID 3 BPJS Antrean.
    """
    kode = (request.POST.get('kode') or request.GET.get('kode') or '').strip()
    if not kode and request.content_type == 'application/json':
        try:
            body = json.loads(request.body.decode('utf-8'))
            kode = body.get('kode', '').strip()
        except Exception:
            pass

    if not kode:
        return JsonResponse({'success': False, 'message': 'Kode barcode/booking tidak boleh kosong.'}, status=400)

    clean_kode = kode.replace('-', '').replace(' ', '')
    today = timezone.localdate()

    kunjungan = KunjunganPasien.objects.filter(
        Q(kode_booking__iexact=kode) |
        Q(token_batal__iexact=kode) |
        Q(no_kunjungan__iexact=kode) |
        Q(nomor_antrean__iexact=kode) |
        Q(pasien__no_rm__iexact=kode) |
        Q(pasien__nik=clean_kode) |
        Q(pasien__no_bpjs=clean_kode)
    ).filter(
        tanggal_masuk__date=today
    ).exclude(status='BATAL').first()

    if not kunjungan:
        return JsonResponse({
            'success': False,
            'message': 'Data booking antrean tidak ditemukan untuk hari ini atau sudah dibatalkan.'
        }, status=404)

    # Tandai Check-In
    kunjungan.is_checkin = True
    kunjungan.waktu_checkin = timezone.now()
    kunjungan.status_antrean = 'MENUNGGU'
    kunjungan.save(update_fields=['is_checkin', 'waktu_checkin', 'status_antrean'])

    # Bridging BPJS Task 3: Akhir pelayanan admisi / check-in APM / mulai tunggu poli
    if kunjungan.penjamin == 'BPJS':
        update_task_id(kunjungan, 3)

    return JsonResponse({
        'success': True,
        'message': f"Check-In Berhasil! Selamat datang, {kunjungan.pasien.nama_lengkap}. Silakan menuju ruang tunggu {kunjungan.get_poliklinik_display() if hasattr(kunjungan, 'get_poliklinik_display') else kunjungan.poliklinik}.",
        'kunjungan': {
            'id': kunjungan.id,
            'nama_pasien': kunjungan.pasien.nama_lengkap,
            'no_rm': kunjungan.pasien.no_rm,
            'nomor_antrean': kunjungan.nomor_antrean,
            'poliklinik': kunjungan.get_poliklinik_display() if hasattr(kunjungan, 'get_poliklinik_display') else kunjungan.poliklinik,
            'dpjp': kunjungan.dpjp,
            'waktu_checkin': kunjungan.waktu_checkin.strftime('%H:%M:%S WIB')
        }
    })


@csrf_exempt
def apm_batal_mandiri(request):
    """
    Pembatalan Janji Mandiri oleh Pasien via Token WhatsApp dengan Aturan T-60.
    - >= 60 menit sebelum estimasi: Batal diterima, kuota dilepas.
    - < 60 menit sebelum estimasi: Batal ditolak, tercatat sebagai No-Show.
    """
    token = (request.POST.get('token') or request.GET.get('token') or '').strip()
    if not token:
        return render(request, 'pasien/apm/batal.html', {
            'error': 'Token pembatalan tidak ditemukan dalam permintaan.'
        })

    kunjungan = KunjunganPasien.objects.filter(token_batal=token).first()
    if not kunjungan:
        return render(request, 'pasien/apm/batal.html', {
            'error': 'Data pendaftaran dengan token tersebut tidak ditemukan.'
        })

    # Hitung selisih waktu dalam menit
    now_dt = timezone.localtime()
    if kunjungan.estimasi_pelayanan:
        visit_local_dt = timezone.localtime(kunjungan.tanggal_masuk)
        est_datetime = datetime.datetime.combine(visit_local_dt.date(), kunjungan.estimasi_pelayanan)
        est_dt = timezone.make_aware(est_datetime, timezone.get_current_timezone())
        if est_dt < visit_local_dt - datetime.timedelta(hours=12):
            est_dt += datetime.timedelta(days=1)
        selisih_menit = (est_dt - now_dt).total_seconds() / 60
    else:
        selisih_menit = 120 # Default allow jika estimasi belum tercatat

    can_cancel = selisih_menit >= 60

    if request.method == 'POST':
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or request.content_type == 'application/json'
            or 'application/json' in request.headers.get('accept', '')
        )

        if not can_cancel:
            # Kebijakan No-Show dikunci
            kunjungan.is_noshow = True
            kunjungan.save(update_fields=['is_noshow'])

            msg_tolak = (
                f"Pembatalan Ditolak. Sesuai kebijakan rumah sakit, pembatalan mandiri hanya dapat "
                f"dilakukan paling lambat 60 menit sebelum jadwal estimasi pemeriksaan. "
                f"Pendaftaran Anda kini tercatat sebagai No-Show pada sistem evaluasi efisiensi antrean."
            )
            if is_ajax:
                return JsonResponse({'success': False, 'message': msg_tolak})
            return render(request, 'pasien/apm/batal.html', {
                'kunjungan': kunjungan,
                'rejected': True,
                'message': msg_tolak
            })

        # Pembatalan Berhasil
        kunjungan.status = 'BATAL'
        kunjungan.save(update_fields=['status'])

        msg_sukses = f"Pendaftaran nomor {kunjungan.nomor_antrean} ({kunjungan.pasien.nama_lengkap}) berhasil dibatalkan. Kuota dokter telah dilepaskan."
        
        # Kirim konfirmasi WA
        if kunjungan.pasien.no_hp:
            kirim_pesan_wa(
                kunjungan.pasien.no_hp,
                f"Halo {kunjungan.pasien.nama_lengkap}, pendaftaran antrean Anda ({kunjungan.nomor_antrean}) untuk Poli {kunjungan.poliklinik} telah BERHASIL DIBATALKAN. Terima kasih.",
                jenis_pesan='BATAL_APM',
                kunjungan=kunjungan
            )

        if is_ajax:
            return JsonResponse({'success': True, 'message': msg_sukses})
        return render(request, 'pasien/apm/batal.html', {
            'kunjungan': kunjungan,
            'success': True,
            'message': msg_sukses
        })

    return render(request, 'pasien/apm/batal.html', {
        'kunjungan': kunjungan,
        'selisih_menit': int(selisih_menit),
        'can_cancel': can_cancel,
        'token': token
    })


def apm_cetak_struk(request, pk):
    """Cetak Struk Thermal POS (80mm/58mm) Bukti Antrean APM"""
    kunjungan = get_object_or_404(KunjunganPasien, pk=pk)
    rs = RumahSakitProfile.objects.first()
    return render(request, 'pasien/apm/struk_thermal.html', {
        'kunjungan': kunjungan,
        'rs': rs
    })


def antrean_display_board(request):
    """Papan Display TV Ruang Tunggu Poliklinik & Pemanggilan Suara TTS"""
    rs = RumahSakitProfile.objects.first()
    return render(request, 'pasien/apm/display_antrean.html', {
        'rs': rs
    })


def antrean_display_api(request):
    """API Real-Time Status Antrean untuk Papan TV"""
    today = timezone.localdate()
    kunjungans = KunjunganPasien.objects.filter(
        tanggal_masuk__date=today,
        jenis_kunjungan='RAJAL'
    ).exclude(status='BATAL').order_by('id')

    antrean_per_poli = {}
    for code, name in POLIKLINIK_CHOICES:
        antrean_per_poli[code] = {
            'kode_poli': code,
            'nama_poli': name,
            'nomor_sekarang': '-',
            'nama_pasien': '-',
            'dpjp': '-',
            'total_antre': 0,
            'sisa_antre': 0
        }

    for k in kunjungans:
        p_code = k.poliklinik
        if p_code in antrean_per_poli:
            antrean_per_poli[p_code]['total_antre'] += 1
            if k.status_antrean == 'DIPANGGIL':
                antrean_per_poli[p_code]['nomor_sekarang'] = k.nomor_antrean
                antrean_per_poli[p_code]['nama_pasien'] = k.pasien.nama_lengkap
                antrean_per_poli[p_code]['dpjp'] = k.dpjp
            elif k.status_antrean == 'MENUNGGU':
                antrean_per_poli[p_code]['sisa_antre'] += 1

    return JsonResponse({
        'success': True,
        'timestamp': timezone.localtime().strftime('%H:%M:%S'),
        'data': list(antrean_per_poli.values())
    })
