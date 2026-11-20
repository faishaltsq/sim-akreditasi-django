import json
import uuid
import datetime
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.views.decorators.cache import never_cache
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from pasien.models import (
    Pasien, KunjunganPasien, JadwalDokterPoli, POLIKLINIK_CHOICES, LogBiometrik, LogRisikoApm,
    KonfigurasiApm, RujukanBpjs,
)
from pasien.services.rujukan import (
    BridgingError, KODE_RISIKO_PER_STATUS, RujukanFormatError,
    evaluate_rujukan, validasi_rujukan_lengkap,
)
from pasien.services.pendaftaran import daftarkan, payload_sukses
from pasien.mobile_views import baca_qr_checkin
from pasien.services.masking import mask_nama
from pasien.services.throttle import kunci_ip, kunci_ip_identitas, throttle
from pasien.services.whatsapp import (
    format_tiket_wa, format_notifikasi_igd, kirim_pesan_wa, kirim_templat,
)
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
        'idle_timeout': KonfigurasiApm.get_solo().idle_timeout_detik,
    }
    return render(request, 'pasien/apm/kiosk.html', context)


@never_cache
@require_http_methods(["GET", "POST"])
@throttle('cari-pasien', limit=30, window_detik=60)
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
        'pasien': {'no_rm': pasien.no_rm, 'nama_lengkap': mask_nama(pasien.nama_lengkap)},
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
    """Endpoint registrasi kunjungan mandiri (kiosk).

    Logika lengkap ada di :func:`pasien.services.pendaftaran.daftarkan` supaya
    portal mobile memakai jalur yang sama (satu penulis data).
    """
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = {}
    else:
        data = request.POST.dict()

    kunjungan, error = daftarkan(
        data, kanal='KIOSK', base_url=request.build_absolute_uri('/')[:-1],
    )
    if error:
        return JsonResponse(error['payload'], status=error['status'])
    struk_url = reverse('pasien:apm_cetak_struk', kwargs={'pk': kunjungan.pk}) + '?' + urlencode({
        'access': signing.dumps(kunjungan.pk, salt='apm-receipt'),
    })
    return JsonResponse(payload_sukses(kunjungan, struk_url=struk_url))


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
    kode_qr = baca_qr_checkin(kode)
    if kode_qr:
        kode = kode_qr
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
    estimasi_baru = None
    sep_info = None
    if not kunjungan.is_checkin:
        if kunjungan.status_antrean != 'MENUNGGU' or kunjungan.is_noshow:
            return JsonResponse({'success': False, 'message': 'Status kunjungan tidak mengizinkan check-in.'}, status=409)
        from pasien.services.biometrik import wajib_biometrik

        if wajib_biometrik(kunjungan) and kunjungan.biometrik_status != 'VALID':
            if kunjungan.biometrik_status == 'TIDAK_WAJIB':
                kunjungan.biometrik_status = 'MENUNGGU'
                kunjungan.save(update_fields=['biometrik_status'])
            return JsonResponse({
                'success': False,
                'status': 'BIOMETRIK_BELUM_VALID',
                'message': (
                    'Poli tujuan mewajibkan verifikasi sidik jari / face recognition. '
                    'Selesaikan verifikasi biometrik di kiosk sebelum SEP dicetak.'
                ),
            }, status=409)
        kunjungan.is_checkin = True
        kunjungan.waktu_checkin = timezone.now()
        kunjungan.save(update_fields=['is_checkin', 'waktu_checkin'])
        if kunjungan.penjamin == 'BPJS':
            sep_info = _proses_bpjs_checkin(kunjungan)
        estimasi_baru = _reestimasi_jika_terlambat(kunjungan)
    return JsonResponse({
        'success': True,
        'message': f"Check-In Berhasil! Selamat datang, {kunjungan.pasien.nama_lengkap}. Silakan menuju ruang tunggu {dict(POLIKLINIK_CHOICES).get(kunjungan.poliklinik, kunjungan.poliklinik)}.",
        'terlambat': estimasi_baru is not None,
        'estimasi_baru': estimasi_baru,
        'sep': sep_info,
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


@never_cache
@require_http_methods(["POST"])
@throttle('rujukan-validasi', limit=10, window_detik=600)
def apm_api_rujukan_validasi(request):
    """Validasi rujukan sebelum booking (BL-02). Identitas dua-faktor tetap wajib."""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            data = {}
    else:
        data = request.POST

    if not isinstance(data, dict) or not all(
        isinstance(data.get(key, ''), str)
        for key in ('identitas', 'nama_lengkap', 'tanggal_lahir', 'no_rujukan')
    ):
        return JsonResponse({'success': False, 'message': 'Format data tidak valid.'}, status=400)

    identitas = data.get('identitas', '').strip()
    nomor_rujukan = data.get('no_rujukan', '').strip()
    if not identitas or not data.get('nama_lengkap', '').strip() or not data.get('tanggal_lahir', '').strip() or not nomor_rujukan:
        return JsonResponse({
            'success': False,
            'message': 'Isi identitas, nama lengkap, tanggal lahir, dan nomor rujukan.',
        }, status=400)

    bersih = identitas.replace('-', '').replace(' ', '').replace('.', '')
    pasien = Pasien.objects.filter(
        Q(nik=bersih) | Q(no_bpjs=bersih) | Q(no_rm__iexact=identitas)
    ).first()
    if not pasien or not _matches_identity(pasien, data):
        return JsonResponse({
            'success': False, 'message': 'Data identitas tidak cocok atau tidak ditemukan.',
        }, status=403)

    try:
        rujukan, hasil = validasi_rujukan_lengkap(
            nomor_rujukan, pasien, kanal='KIOSK', tanggal_kunjungan=timezone.localdate(),
        )
    except RujukanFormatError as exc:
        return JsonResponse({'success': False, 'status': 'FORMAT_RUJUKAN', 'message': str(exc)}, status=400)
    except BridgingError as exc:
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-04', kanal='KIOSK', pemicu='BRIDGING_TIMEOUT',
            severity='TINGGI', detail={'status': exc.status, 'pesan': str(exc)},
        )
        return JsonResponse({
            'success': False,
            'status': 'BRIDGING_DOWN',
            'message': 'Layanan validasi rujukan BPJS sedang terganggu. Silakan menuju loket admisi.',
            'jalur_alternatif': 'LOKET_ADMISI',
        }, status=503)

    return JsonResponse({
        'success': True,
        'pasien': {'no_rm': pasien.no_rm, 'nama_lengkap': mask_nama(pasien.nama_lengkap)},
        'rujukan': {
            'no_rujukan': rujukan.no_rujukan,
            'tgl_rujukan': rujukan.tgl_rujukan.isoformat() if rujukan.tgl_rujukan else None,
            'masa_berlaku_hari': rujukan.masa_berlaku_hari(),
            'ppk_rujukan': rujukan.ppk_rujukan,
            'nama_ppk_rujukan': rujukan.nama_ppk_rujukan,
            'ppk_tujuan': rujukan.ppk_tujuan,
            'poli_tujuan_bpjs': rujukan.poli_tujuan_bpjs,
            'diagnosa_awal': rujukan.diagnosa_awal,
            'nama_diagnosa_awal': rujukan.nama_diagnosa_awal,
        },
        **hasil.as_dict(),
    })


@never_cache
@require_http_methods(["POST"])
def apm_api_igd_fasttrack(request):
    """IGD Fast-Track (BL-01): identitas minimal, tanpa rujukan/biometrik/jadwal.

    PRD mensyaratkan pendaftaran darurat tidak tertahan administrasi. Karena itu
    endpoint ini hanya mewajibkan nama, melewati seluruh validasi rawat jalan,
    mencatat RSK-APM-01, dan mengembalikan durasi registrasi untuk target <= 2 menit.
    """
    mulai = timezone.now()
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            data = {}
    else:
        data = request.POST.dict()

    if not isinstance(data, dict):
        return JsonResponse({'success': False, 'message': 'Format data tidak valid.'}, status=400)
    for key in ('nama_lengkap', 'nik', 'no_bpjs', 'no_wa', 'alamat'):
        if not isinstance(data.get(key, ''), str):
            return JsonResponse({'success': False, 'message': 'Format data tidak valid.'}, status=400)

    nama = ' '.join((data.get('nama_lengkap') or '').split())
    if not nama:
        return JsonResponse({
            'success': False,
            'message': 'Nama pasien wajib diisi untuk memulai penanganan darurat.',
        }, status=400)

    nik = (data.get('nik') or '').strip()
    no_bpjs = (data.get('no_bpjs') or '').strip()
    no_wa = (data.get('no_wa') or '').strip()
    alamat = (data.get('alamat') or '').strip()

    with transaction.atomic():
        pasien = None
        identitas_terverifikasi = False
        if nik:
            pasien = Pasien.objects.filter(nik=nik).first()
        if not pasien and no_bpjs:
            pasien = Pasien.objects.filter(no_bpjs=no_bpjs).first()
        if pasien:
            identitas_terverifikasi = (
                ' '.join(pasien.nama_lengkap.split()).casefold() == nama.casefold()
            )

        if not pasien:
            today_str = timezone.localdate().strftime('%Y%m%d')
            urutan = Pasien.objects.filter(no_rm__startswith=f'RM-IGD-{today_str}').count() + 1
            pasien = Pasien.objects.create(
                no_rm=f'RM-IGD-{today_str}-{urutan:04d}',
                nama_lengkap=nama,
                nik=nik,
                no_bpjs=no_bpjs,
                no_hp=no_wa,
                alamat=alamat,
                jenis_kelamin='',
            )

        now = timezone.now()
        suffix = uuid.uuid4().hex[:4].upper()
        nomor_antrean = allocate_queue_number('IGD', tanggal=timezone.localdate())
        kunjungan = KunjunganPasien.objects.create(
            pasien=pasien,
            no_kunjungan=f'REG-IGD-{now.strftime("%Y%m%d%H%M%S")}-{suffix}',
            jenis_kunjungan='IGD',
            tanggal_masuk=now,
            poliklinik='IGD',
            dpjp='Dokter Jaga IGD',
            nomor_antrean=nomor_antrean,
            penjamin='BPJS' if (no_bpjs or pasien.no_bpjs) else 'UMUM',
            flag_khusus='KRITIS',
            triage='MERAH',
            status_antrean='MENUNGGU',
            kode_booking=f'IGD-{timezone.localdate():%Y%m%d}-{suffix}',
            token_batal=uuid.uuid4().hex[:12].upper(),
            estimasi_pelayanan=timezone.localtime().time(),
            is_apm=True,
            catatan_admisi=(
                'REGISTRASI_DARURAT_IDENTITAS_MINIMAL'
                if not identitas_terverifikasi else 'REGISTRASI_DARURAT'
            ),
            registrasi_mulai_at=mulai,
        )

        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-01',
            kanal='KIOSK',
            pemicu='IGD_FASTTRACK',
            severity='KRITIS',
            kunjungan=kunjungan,
            detail={
                'identitas_terverifikasi': identitas_terverifikasi,
                'waktu_mulai': mulai.isoformat(),
            },
        )

        target_wa = no_wa or pasien.no_hp
        if target_wa:
            kirim_pesan_wa(
                target_wa, format_notifikasi_igd(kunjungan),
                jenis_pesan='NOTIFIKASI_IGD', kunjungan=kunjungan,
            )

        selesai = timezone.now()
        durasi = (selesai - mulai).total_seconds()
        KunjunganPasien.objects.filter(pk=kunjungan.pk).update(registrasi_selesai_at=selesai)

    return JsonResponse({
        'success': True,
        'jenis_kunjungan': 'IGD',
        'triage': 'MERAH',
        'nomor_antrean': kunjungan.nomor_antrean,
        'kode_booking': kunjungan.kode_booking,
        'nama_pasien': kunjungan.pasien.nama_lengkap,
        'no_rm': kunjungan.pasien.no_rm,
        'durasi_registrasi_detik': round(durasi, 2),
        'target_terpenuhi': durasi <= 120,
        'message': (
            f'Registrasi darurat selesai dalam {durasi:.1f} detik. '
            f'Nomor antrean IGD {kunjungan.nomor_antrean} — segera menuju triase IGD.'
        ),
        'struk_url': reverse('pasien:apm_cetak_struk', kwargs={'pk': kunjungan.pk}) + '?' + urlencode({
            'access': signing.dumps(kunjungan.pk, salt='apm-receipt'),
        }),
    })


def _reestimasi_jika_terlambat(kunjungan):
    """Pasien yang check-in melewati estimasi dijadwalkan ulang ke antrean aktif terakhir."""
    import datetime as _datetime

    from pasien.services.estimasi import EstimasiError, estimasi_kunjungan
    from pasien.models import KonfigurasiApm

    if not kunjungan.estimasi_pelayanan:
        return None
    sekarang = timezone.localtime()
    target = _datetime.datetime.combine(sekarang.date(), kunjungan.estimasi_pelayanan)
    if sekarang.replace(tzinfo=None) <= target:
        return None

    jadwal = JadwalDokterPoli.objects.filter(
        nama_dokter=kunjungan.dpjp, poliklinik=kunjungan.poliklinik,
    ).first()
    if not jadwal:
        return None

    tanggal = kunjungan.tanggal_kunjungan or sekarang.date()
    antrean_aktif = KunjunganPasien.objects.filter(
        tanggal_kunjungan=tanggal, jenis_kunjungan='RAJAL',
        dpjp=kunjungan.dpjp, poliklinik=kunjungan.poliklinik,
        status_antrean__in=('MENUNGGU', 'DIPANGGIL', 'SEDANG_DILAYANI'),
    ).exclude(status='BATAL').count()

    konf = KonfigurasiApm.get_solo()
    try:
        estimasi = estimasi_kunjungan(
            kunjungan, konfigurasi=konf, urutan=max(1, antrean_aktif),
        )
    except EstimasiError:
        return None

    kunjungan.estimasi_pelayanan = estimasi.t_periksa
    kunjungan.estimasi_versi = kunjungan.estimasi_versi + 1
    kunjungan.save(update_fields=['estimasi_pelayanan', 'estimasi_versi'])
    kirim_templat(kunjungan, 'PERGESERAN_JADWAL')
    return {
        't_periksa': estimasi.t_periksa.strftime('%H:%M'),
        't_tiba': estimasi.t_tiba.strftime('%H:%M'),
        'versi': kunjungan.estimasi_versi,
    }


def _proses_bpjs_checkin(kunjungan):
    """Antrean Online → SEP → Task ID 3 → Templat 2. Gagal bridging = fail-closed."""
    from pasien.services.bpjs_vclaim import BridgingError, daftar_antrean_bpjs, terbitkan_sep

    try:
        daftar_antrean_bpjs(kunjungan)
        terbitkan_sep(kunjungan)
    except BridgingError as exc:
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-04', kanal='KIOSK', pemicu='BRIDGING_TIMEOUT',
            severity='TINGGI', kunjungan=kunjungan,
            detail={'status': exc.status, 'pesan': str(exc)},
        )
        kunjungan.refresh_from_db()
        if not kunjungan.no_sep:
            kunjungan.sep_mode = 'GAGAL'
            kunjungan.save(update_fields=['sep_mode'])
        return {
            'success': False,
            'status': exc.status,
            'message': (
                'SEP belum dapat diterbitkan karena layanan BPJS terganggu. '
                'Silakan menuju loket admisi — jangan mencetak SEP dari kiosk.'
            ),
            'jalur_alternatif': 'LOKET_ADMISI',
        }

    update_task_id(kunjungan, 3)
    kirim_templat(kunjungan, 'CHECKIN_SEP')
    return {
        'success': True,
        'no_sep': kunjungan.no_sep,
        'sep_mode': kunjungan.sep_mode,
        'kodebooking': kunjungan.no_referensi_antrean,
    }


@never_cache
@require_http_methods(["POST"])
def apm_api_biometrik(request):
    """Verifikasi biometrik kiosk + eskalasi 3x gagal (BL-08 / BL-09)."""
    from pasien.services.biometrik import (
        BiometricGateway, batas_percobaan, nomor_tiket_helpdesk, wajib_biometrik,
    )
    from pasien.services.bpjs_vclaim import simulation_allowed

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
        return JsonResponse({'success': False, 'message': 'Kode booking wajib diisi.'}, status=400)

    kunjungan = KunjunganPasien.objects.select_related('pasien').filter(
        Q(kode_booking__iexact=kode) | Q(no_kunjungan__iexact=kode),
        tanggal_masuk__date=timezone.localdate(), is_apm=True,
    ).exclude(status='BATAL').first()
    if not kunjungan or not _matches_identity(kunjungan.pasien, data):
        return JsonResponse({'success': False, 'message': 'Booking atau verifikasi identitas tidak valid.'}, status=403)

    if not wajib_biometrik(kunjungan):
        kunjungan.biometrik_status = 'TIDAK_WAJIB'
        kunjungan.save(update_fields=['biometrik_status'])
        return JsonResponse({'success': True, 'status': 'TIDAK_WAJIB', 'message': 'Poli ini tidak mewajibkan biometrik.'})

    batas = batas_percobaan()
    percobaan = LogBiometrik.objects.filter(kunjungan=kunjungan).count() + 1
    metode = (data.get('metode') or 'FINGERPRINT').upper()
    if metode not in ('FINGERPRINT', 'FACE'):
        metode = 'FINGERPRINT'
    simulasi_valid = True
    if simulation_allowed() and str(data.get('simulasi_valid', '1')) in ('0', 'false', 'False'):
        simulasi_valid = False

    gateway = BiometricGateway(mode='SIMULASI')
    hasil = gateway.verify(
        kunjungan=kunjungan, percobaan=percobaan, metode=metode,
        simulasi_valid=simulasi_valid, perangkat_id=(data.get('perangkat_id') or '')[:60],
    )

    if hasil['valid']:
        kunjungan.biometrik_status = 'VALID'
        kunjungan.save(update_fields=['biometrik_status'])
        return JsonResponse({
            'success': True, 'status': 'VALID', 'mode': hasil['mode'], 'percobaan': percobaan,
            'message': 'Verifikasi biometrik berhasil. Lanjutkan check-in untuk mencetak SEP.',
        })

    sisa = max(0, batas - percobaan)
    if percobaan >= batas:
        tiket = nomor_tiket_helpdesk()
        LogBiometrik.objects.create(
            kunjungan=kunjungan, percobaan_ke=percobaan, metode=metode, hasil='ESKALASI',
            mode='SIMULASI', detail={'tiket_helpdesk': tiket},
        )
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-03', kanal='KIOSK', pemicu='BIOMETRIK_GAGAL_3X',
            severity='TINGGI', kunjungan=kunjungan,
            detail={'percobaan': percobaan, 'tiket_helpdesk': tiket},
        )
        kunjungan.biometrik_status = 'ESKALASI'
        kunjungan.save(update_fields=['biometrik_status'])
        if kunjungan.pasien.no_hp:
            kirim_pesan_wa(
                kunjungan.pasien.no_hp,
                f'Tiket Antrean Prioritas Helpdesk BPJS: *{tiket}*. '
                f'Mohon menuju meja helpdesk BPJS untuk verifikasi manual.',
                jenis_pesan='ESKALASI_BIOMETRIK', kunjungan=kunjungan,
            )
        return JsonResponse({
            'success': False, 'status': 'ESKALASI', 'tiket_helpdesk': tiket,
            'message': (
                f'Verifikasi biometrik gagal {percobaan}x. Silakan menuju helpdesk BPJS '
                f'dengan tiket prioritas {tiket}.'
            ),
        }, status=409)

    kunjungan.biometrik_status = 'GAGAL'
    kunjungan.save(update_fields=['biometrik_status'])
    return JsonResponse({
        'success': False, 'status': 'GAGAL', 'percobaan': percobaan, 'sisa_percobaan': sisa,
        'mode': hasil['mode'],
        'message': f'Verifikasi biometrik gagal. Sisa percobaan: {sisa}.',
    }, status=200)


@never_cache
@require_http_methods(["POST"])
def apm_api_sesi_reset(request):
    """Bersihkan sesi layar publik (dipanggil idle timer kiosk)."""
    response = HttpResponse(status=204)
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def apm_indikator_view(request):
    """Indikator mutu APM untuk staf (JSON) — konsumen dasbor mutu ARima."""
    from pasien.services.indikator import hitung_indikator

    tahun = request.GET.get('tahun')
    bulan = request.GET.get('bulan')
    try:
        data = hitung_indikator(
            int(tahun) if tahun else None,
            int(bulan) if bulan else None,
        )
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Parameter tahun/bulan tidak valid.'}, status=400)
    response = JsonResponse({'success': True, 'indikator': data})
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
