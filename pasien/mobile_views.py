"""Portal pendaftaran mandiri dari HP Android tanpa login (BL-04).

Keamanan:
- Tidak ada akun/password; akses memakai capability token bertanda tangan
  (``django.core.signing``) yang terikat ke satu pasien dan kedaluwarsa.
- Verifikasi identitas dua-faktor (identitas + tanggal lahir) dengan pesan gagal
  yang seragam agar tidak bisa dipakai untuk enumerasi.
- Semua mutasi POST + CSRF; data klinis dari rujukan tidak dapat ditimpa klien.
"""
import datetime
import json

from django.core import signing
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.db.models import Q

from akreditasi.models import RumahSakitProfile
from pasien.models import JadwalDokterPoli, KunjunganPasien, Pasien
from pasien.services.estimasi import EstimasiError, estimasi_kunjungan
from pasien.services.ktp_validator import parse_flexible_date
from pasien.services.pendaftaran import daftarkan
from pasien.services.throttle import kunci_ip_identitas, throttle
from pasien.services.whatsapp import (
    _label_poli, blok_peringatan_biometrik, format_konfirmasi_booking, normalisasi_nomor,
)

SALT_SESI = 'apm-mobile'
SALT_TIKET = 'apm-mobile-tiket'
SALT_QR = 'apm-qr'
UMUR_SESI_DETIK = 12 * 3600
PESAN_GAGAL_IDENTITAS = 'Data identitas tidak cocok atau tidak ditemukan.'


def _buat_token(pasien):
    payload = {
        'pasien_id': pasien.pk,
        'exp': (timezone.now() + datetime.timedelta(seconds=UMUR_SESI_DETIK)).isoformat(),
    }
    return signing.dumps(payload, salt=SALT_SESI)


def _pasien_dari_token(token):
    try:
        data = signing.loads(token or '', salt=SALT_SESI, max_age=UMUR_SESI_DETIK)
    except signing.BadSignature:
        return None
    except Exception:
        return None
    try:
        kedaluwarsa = datetime.datetime.fromisoformat(data.get('exp', ''))
    except ValueError:
        return None
    if timezone.is_naive(kedaluwarsa):
        kedaluwarsa = timezone.make_aware(kedaluwarsa)
    if timezone.now() > kedaluwarsa:
        return None
    return Pasien.objects.filter(pk=data.get('pasien_id')).first()


def _buat_akses_tiket(kunjungan):
    return signing.dumps(
        {'kunjungan': kunjungan.pk, 'pasien': kunjungan.pasien_id}, salt=SALT_TIKET,
    )


def _kunjungan_dari_akses(akses, pasien):
    try:
        data = signing.loads(akses or '', salt=SALT_TIKET, max_age=UMUR_SESI_DETIK)
    except Exception:
        return None
    if data.get('pasien') != pasien.pk:
        return None
    return KunjunganPasien.objects.filter(pk=data.get('kunjungan'), pasien=pasien).first()


def _qr_payload(kunjungan):
    return signing.dumps(
        {'kode': kunjungan.kode_booking or kunjungan.no_kunjungan, 'pasien': kunjungan.pasien_id},
        salt=SALT_QR,
    )


def baca_qr_checkin(nilai):
    """Kembalikan kode booking dari payload QR bertanda tangan, atau None."""
    try:
        data = signing.loads(nilai, salt=SALT_QR, max_age=UMUR_SESI_DETIK)
    except Exception:
        return None
    return data.get('kode')


@never_cache
def mandiri_beranda(request):
    token = request.GET.get('token', '')
    if token and _pasien_dari_token(token):
        return HttpResponseRedirect(
            reverse('pasien:mandiri_jadwal') + '?token=' + token
        )
    rs = RumahSakitProfile.objects.first()
    return render(request, 'pasien/mobile/beranda.html', {'rs': rs, 'error': ''})


@never_cache
@require_http_methods(["POST"])
@throttle('mandiri-verifikasi', limit=5, window_detik=600, key_func=kunci_ip_identitas)
def mandiri_verifikasi(request):
    identitas = (request.POST.get('identitas') or '').strip()
    nama = (request.POST.get('nama_lengkap') or '').strip()
    tanggal_lahir = (request.POST.get('tanggal_lahir') or '').strip()
    no_wa = (request.POST.get('no_wa') or '').strip()
    rs = RumahSakitProfile.objects.first()

    if not identitas or not tanggal_lahir or not normalisasi_nomor(no_wa):
        return render(request, 'pasien/mobile/beranda.html', {
            'rs': rs,
            'error': 'Isi NIK/No. BPJS/No. RM, tanggal lahir, dan nomor WhatsApp yang valid.',
        }, status=400)

    bersih = identitas.replace('-', '').replace(' ', '').replace('.', '')
    pasien = Pasien.objects.filter(
        Q(nik=bersih) | Q(no_bpjs=bersih) | Q(no_rm__iexact=identitas)
    ).first()
    lahir = parse_flexible_date(tanggal_lahir, prefer='DMY')
    cocok = (
        pasien is not None
        and lahir is not None
        and pasien.tanggal_lahir == lahir
        and (not nama or ' '.join(nama.split()).casefold() == ' '.join(pasien.nama_lengkap.split()).casefold())
    )
    if not cocok:
        return render(request, 'pasien/mobile/beranda.html', {
            'rs': rs, 'error': PESAN_GAGAL_IDENTITAS,
        }, status=403)

    if not pasien.no_hp:
        pasien.no_hp = no_wa
        pasien.save(update_fields=['no_hp'])

    token = _buat_token(pasien)
    return HttpResponseRedirect(reverse('pasien:mandiri_jadwal') + '?token=' + token)


@never_cache
def mandiri_jadwal(request):
    pasien = _pasien_dari_token(request.GET.get('token', ''))
    if not pasien:
        return HttpResponseRedirect(reverse('pasien:mandiri_beranda'))

    jadwal_qs = JadwalDokterPoli.objects.filter(status_ketersediaan='BUKA').order_by('poliklinik', 'nama_dokter')
    daftar = []
    for jadwal in jadwal_qs:
        sisa = jadwal.get_sisa_kuota()
        if sisa <= 0:
            continue
        daftar.append({
            'jadwal': jadwal,
            'label_poli': jadwal.get_poliklinik_display(),
            'sisa': sisa,
        })
    return render(request, 'pasien/mobile/jadwal.html', {
        'rs': RumahSakitProfile.objects.first(),
        'pasien': pasien,
        'token': request.GET.get('token', ''),
        'daftar': daftar,
        'error': '',
    })


@never_cache
@require_http_methods(["POST"])
def mandiri_booking(request):
    pasien = _pasien_dari_token(request.POST.get('token', ''))
    if not pasien:
        return HttpResponseRedirect(reverse('pasien:mandiri_beranda'))

    payload = {
        'tipe_pasien': 'LAMA',
        'jenis_layanan': 'RAJAL',
        'nama_lengkap': pasien.nama_lengkap,
        'tanggal_lahir': pasien.tanggal_lahir.isoformat() if pasien.tanggal_lahir else '',
        'no_rm': pasien.no_rm,
        'nik': pasien.nik or '',
        'no_bpjs': pasien.no_bpjs or '',
        'no_wa': pasien.no_hp or '',
        'penjamin': (request.POST.get('penjamin') or 'UMUM').upper(),
        'jadwal_id': request.POST.get('jadwal_id', ''),
        'poliklinik': request.POST.get('poliklinik', ''),
        'no_rujukan': (request.POST.get('no_rujukan') or '').strip(),
    }
    kunjungan, error = daftarkan(
        payload, kanal='MOBILE', base_url=request.build_absolute_uri('/')[:-1],
    )
    if error:
        jadwal_qs = JadwalDokterPoli.objects.filter(status_ketersediaan='BUKA').order_by('poliklinik', 'nama_dokter')
        daftar = [
            {'jadwal': jadwal, 'label_poli': jadwal.get_poliklinik_display(), 'sisa': jadwal.get_sisa_kuota()}
            for jadwal in jadwal_qs if jadwal.get_sisa_kuota() > 0
        ]
        return render(request, 'pasien/mobile/jadwal.html', {
            'rs': RumahSakitProfile.objects.first(),
            'pasien': pasien,
            'token': request.POST.get('token', ''),
            'daftar': daftar,
            'error': error['payload'].get('message', 'Pendaftaran gagal.'),
            'jalur_alternatif': error['payload'].get('jalur_alternatif', ''),
        }, status=error['status'])

    return HttpResponseRedirect(
        reverse('pasien:mandiri_tiket') + '?token=' + request.POST.get('token', '')
        + '&akses=' + _buat_akses_tiket(kunjungan)
    )


@never_cache
def mandiri_tiket(request):
    pasien = _pasien_dari_token(request.GET.get('token', ''))
    if not pasien:
        return HttpResponseRedirect(reverse('pasien:mandiri_beranda'))
    kunjungan = _kunjungan_dari_akses(request.GET.get('akses', ''), pasien)
    if not kunjungan:
        return HttpResponse('Data tiket tidak valid atau kedaluwarsa.', status=403)

    try:
        estimasi = estimasi_kunjungan(kunjungan)
        jam_periksa = estimasi.t_periksa.strftime('%H:%M')
        jam_tiba = estimasi.t_tiba.strftime('%H:%M')
    except EstimasiError:
        jam_periksa = kunjungan.estimasi_pelayanan.strftime('%H:%M') if kunjungan.estimasi_pelayanan else '--:--'
        jam_tiba = '--:--'

    response = render(request, 'pasien/mobile/tiket.html', {
        'rs': RumahSakitProfile.objects.first(),
        'pasien': pasien,
        'kunjungan': kunjungan,
        'label_poli': _label_poli(kunjungan),
        'jam_periksa': jam_periksa,
        'jam_tiba': jam_tiba,
        'peringatan_biometrik': blok_peringatan_biometrik(kunjungan),
        'qr_url': reverse('pasien:mandiri_qr') + '?token=' + request.GET.get('token', '')
        + '&akses=' + request.GET.get('akses', ''),
        'wa_text': format_konfirmasi_booking(kunjungan, base_url=request.build_absolute_uri('/')[:-1]),
    })
    response['Cache-Control'] = 'no-store'
    return response


@never_cache
def mandiri_qr(request):
    pasien = _pasien_dari_token(request.GET.get('token', ''))
    if not pasien:
        return HttpResponse('Sesi tidak valid.', status=403)
    kunjungan = _kunjungan_dari_akses(request.GET.get('akses', ''), pasien)
    if not kunjungan:
        return HttpResponse('Data tiket tidak valid.', status=403)

    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing

    qr = QrCodeWidget(_qr_payload(kunjungan))
    drawing = Drawing(160, 160)
    x1, y1, x2, y2 = qr.getBounds()
    drawing.transform = (160 / (x2 - x1), 0, 0, 160 / (y2 - y1), 0, 0)
    drawing.add(qr)
    svg = renderSVG.drawToString(drawing)
    svg = svg[svg.index('<svg'):]
    response = HttpResponse(svg, content_type='image/svg+xml')
    response['Cache-Control'] = 'no-store'
    return response