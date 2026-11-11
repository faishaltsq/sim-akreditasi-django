import json
import uuid
import datetime
from urllib.parse import urlencode
from django.core import signing
from django.views.decorators.cache import never_cache
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from pasien.models import Pasien, KunjunganPasien, JadwalDokterPoli, POLIKLINIK_CHOICES
from pasien.services.whatsapp import format_tiket_wa, format_notifikasi_igd, kirim_pesan_wa
from pasien.services.bpjs_antrean import update_task_id
from akreditasi.models import RumahSakitProfile
from pasien.services.ktp_validator import parse_flexible_date
from pasien.services.antrean import PREFIX_POLI, allocate_queue_number


def _matches_identity(pasien, data):
    name = data.get('nama_lengkap', '')
    birthdate = data.get('tanggal_lahir', '')
    if not isinstance(name, str) or not isinstance(birthdate, str):
        return False
    return (
        bool(name.strip())
        and ' '.join(name.split()).casefold() == ' '.join(pasien.nama_lengkap.split()).casefold()
        and parse_flexible_date(birthdate, prefer='DMY') == pasien.tanggal_lahir
    )




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


@never_cache
@require_http_methods(["GET", "POST"])
def apm_api_cari_pasien(request):
    """Resolve a patient only after matching name and date of birth."""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            data = {}
    else:
        data = request.POST if request.method == 'POST' else request.GET
    if not isinstance(data, dict) or not all(isinstance(data.get(key, ''), str) for key in ('q', 'nama_lengkap', 'tanggal_lahir')):
        return JsonResponse({'found': False, 'message': 'Format data tidak valid.'}, status=400)
    q = data.get('q', '').strip()
    clean_q = q.replace('-', '').replace(' ', '').replace('.', '')
    if not clean_q or not data.get('nama_lengkap', '').strip() or not parse_flexible_date(data.get('tanggal_lahir', ''), prefer='DMY'):
        return JsonResponse({'found': False, 'message': 'Isi identitas, nama lengkap, dan tanggal lahir.'}, status=400)
    pasien = Pasien.objects.filter(
        Q(nik=clean_q) | Q(no_bpjs=clean_q) | Q(no_rm__iexact=q) | Q(no_rm__iexact=clean_q)
    ).first()
    if not pasien or not _matches_identity(pasien, data):
        return JsonResponse({'found': False, 'message': 'Data identitas tidak cocok atau tidak ditemukan.'})
    return JsonResponse({
        'found': True,
        'pasien': {'no_rm': pasien.no_rm, 'nama_lengkap': pasien.nama_lengkap},
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


@never_cache
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

    text_fields = (
        'tipe_pasien', 'jenis_layanan', 'no_wa', 'penjamin', 'nama_lengkap',
        'nik', 'tanggal_lahir', 'jenis_kelamin', 'alamat', 'no_bpjs', 'no_rm', 'poliklinik',
    )
    if not isinstance(data, dict) or not data or any(not isinstance(data.get(key, ''), str) for key in text_fields):
        return JsonResponse({'success': False, 'message': 'Format data pendaftaran tidak valid.'}, status=400)
    jadwal_id = data.get('jadwal_id')
    if jadwal_id is not None and (isinstance(jadwal_id, bool) or not str(jadwal_id).isdigit() or len(str(jadwal_id)) > 18):
        return JsonResponse({'success': False, 'message': 'Jadwal dokter tidak valid.'}, status=400)
    tipe_pasien = data.get('tipe_pasien', 'LAMA').upper()
    jenis_layanan = data.get('jenis_layanan', 'RAJAL').upper()
    no_wa = (data.get('no_wa') or '').strip()
    penjamin = (data.get('penjamin') or 'UMUM').upper()
    if tipe_pasien not in ('BARU', 'LAMA') or jenis_layanan not in ('IGD', 'RAJAL') or penjamin not in ('UMUM', 'BPJS', 'ASURANSI'):
        return JsonResponse({'success': False, 'message': 'Pilihan layanan tidak valid.'}, status=400)

    with transaction.atomic():
        jadwal = None
        if jenis_layanan == 'RAJAL':
            schedules = JadwalDokterPoli.objects.select_for_update()
            if jadwal_id:
                jadwal = schedules.filter(pk=jadwal_id).first()
            elif data.get('poliklinik'):
                jadwal = schedules.filter(poliklinik=data['poliklinik'], status_ketersediaan='BUKA').first()
            if not jadwal:
                return JsonResponse({'success': False, 'message': 'Jadwal dokter tidak ditemukan.'}, status=400)
            estimasi_jam = jadwal.get_next_estimasi_jam()
            if not jadwal.is_tersedia(timezone.localdate()) or estimasi_jam is None:
                return JsonResponse({'success': False, 'message': 'Mohon maaf, kuota dokter untuk hari ini sudah penuh.'}, status=400)
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

            if pasien and not _matches_identity(pasien, data):
                return JsonResponse({'success': False, 'message': 'Verifikasi identitas pasien gagal.'}, status=403)

            tgl_lahir = parse_flexible_date(tgl_lahir_str, prefer='DMY')
            if not tgl_lahir or tgl_lahir > timezone.localdate():
                return JsonResponse({'success': False, 'message': 'Tanggal lahir tidak valid.'}, status=400)

            if not pasien:
                # Generate No RM Baru: RM-YYYYMMDD-XXXX
                today_str = timezone.localdate().strftime('%Y%m%d')
                count_today = Pasien.objects.filter(no_rm__startswith=f"RM-{today_str}").count() + 1
                new_no_rm = f"RM-{today_str}-{count_today:04d}"

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

            if not _matches_identity(pasien, data):
                return JsonResponse({'success': False, 'message': 'Verifikasi identitas pasien gagal.'}, status=403)

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
            nomor_antrean = allocate_queue_number('IGD', tanggal=today_date)
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
            nomor_antrean = allocate_queue_number('RAJAL', jadwal.poliklinik, tanggal=today_date)

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
        'poliklinik': dict(POLIKLINIK_CHOICES).get(kunjungan.poliklinik, kunjungan.poliklinik) if hasattr(kunjungan, 'get_poliklinik_display') else kunjungan.poliklinik,
        'struk_url': reverse('pasien:apm_cetak_struk', kwargs={'pk': kunjungan.pk}) + '?' + urlencode({
            'access': signing.dumps(kunjungan.pk, salt='apm-receipt'),
        })
    })


@never_cache
@require_http_methods(["POST"])
@transaction.atomic
def apm_api_checkin(request):
    """Record arrival once, after two-identifier verification."""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            data = {}
    else:
        data = request.POST
    if not isinstance(data, dict) or not isinstance(data.get('kode', ''), str):
        return JsonResponse({'success': False, 'message': 'Format data tidak valid.'}, status=400)
    kode = data.get('kode', '').strip()
    if not kode:
        return JsonResponse({'success': False, 'message': 'Kode barcode/booking tidak boleh kosong.'}, status=400)
    clean_kode = kode.replace('-', '').replace(' ', '')
    candidates = KunjunganPasien.objects.select_for_update().select_related('pasien').filter(
        Q(kode_booking__iexact=kode) | Q(no_kunjungan__iexact=kode) |
        Q(pasien__no_rm__iexact=kode) | Q(pasien__nik=clean_kode) | Q(pasien__no_bpjs=clean_kode),
        tanggal_masuk__date=timezone.localdate(), is_apm=True,
    ).exclude(status='BATAL')
    # Ambiguous identifiers must not silently check in an arbitrary appointment.
    visits = list(candidates[:2])
    if len(visits) != 1 or not _matches_identity(visits[0].pasien, data):
        return JsonResponse({'success': False, 'message': 'Booking atau verifikasi identitas tidak valid.'}, status=403)
    kunjungan = visits[0]
    if not kunjungan.is_checkin:
        if kunjungan.status_antrean != 'MENUNGGU' or kunjungan.is_noshow:
            return JsonResponse({'success': False, 'message': 'Status kunjungan tidak mengizinkan check-in.'}, status=409)
        kunjungan.is_checkin = True
        kunjungan.waktu_checkin = timezone.now()
        kunjungan.save(update_fields=['is_checkin', 'waktu_checkin'])
        if kunjungan.penjamin == 'BPJS':
            update_task_id(kunjungan, 3)
    return JsonResponse({
        'success': True,
        'message': f"Check-In Berhasil! Selamat datang, {kunjungan.pasien.nama_lengkap}. Silakan menuju ruang tunggu {dict(POLIKLINIK_CHOICES).get(kunjungan.poliklinik, kunjungan.poliklinik)}.",
        'kunjungan': {
            'id': kunjungan.id,
            'nama_pasien': kunjungan.pasien.nama_lengkap,
            'no_rm': kunjungan.pasien.no_rm,
            'nomor_antrean': kunjungan.nomor_antrean,
            'poliklinik': dict(POLIKLINIK_CHOICES).get(kunjungan.poliklinik, kunjungan.poliklinik),
            'dpjp': kunjungan.dpjp,
            'waktu_checkin': timezone.localtime(kunjungan.waktu_checkin).strftime('%H:%M:%S WIB') if kunjungan.waktu_checkin else '',
        },
    })


@never_cache
@require_http_methods(["GET", "POST"])
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


@never_cache
@require_http_methods(["GET"])
def apm_cetak_struk(request, pk):
    """Cetak Struk Thermal POS (80mm/58mm) Bukti Antrean APM"""
    try:
        allowed_pk = signing.loads(request.GET.get('access', ''), salt='apm-receipt', max_age=900)
    except signing.BadSignature:
        allowed_pk = None
    if allowed_pk != pk:
        return HttpResponse('Akses struk tidak valid atau kedaluwarsa.', status=403)
    kunjungan = get_object_or_404(KunjunganPasien, pk=pk)
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderSVG

    rs = RumahSakitProfile.objects.first()
    paper_width = 58 if request.GET.get('width') == '58' else 80
    qr = QrCodeWidget(kunjungan.kode_booking or kunjungan.no_kunjungan)
    drawing = Drawing(110, 110)
    x1, y1, x2, y2 = qr.getBounds()
    drawing.transform = (110 / (x2 - x1), 0, 0, 110 / (y2 - y1), 0, 0)
    drawing.add(qr)
    qr_svg = renderSVG.drawToString(drawing)
    qr_svg = qr_svg[qr_svg.index('<svg'):]
    response = render(request, 'pasien/apm/struk_thermal.html', {
        'kunjungan': kunjungan,
        'rs': rs,
        'paper_width': paper_width,
        'content_width': paper_width - 2,
        'qr_svg': qr_svg,
    })
    response['Cache-Control'] = 'no-store'
    return response


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
