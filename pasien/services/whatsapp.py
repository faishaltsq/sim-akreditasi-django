"""Notifikasi WhatsApp APM-BPJS.

Isi (plan 2026-11-19, Phase 7):
- Tiga templat PRD §2B-3 (booking, check-in+SEP, pergeseran jadwal), multi-RS.
- Provider abstraction: Fonnte / WhatsApp Business Cloud API / simulasi.
- Retry maksimal ``KonfigurasiApm.wa_retry_maks`` dengan backoff.
- Idempotensi per ``(kunjungan, jenis_pesan, versi estimasi)``.
- Throttle per nomor agar gateway tidak memblokir nomor RS.
- Semua identitas disamarkan (masking) sesuai PRD §3A.

Catatan: baris tautan pembatalan T-60 pada templat 1 adalah tambahan ARima
(fitur yang sudah berjalan); badan pesan mengikuti PRD secara verbatim.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from pasien.models import (
    KonfigurasiApm,
    KonfigurasiBiometrikPoli,
    KunjunganPasien,
    WhatsAppLog,
)

logger = logging.getLogger(__name__)

THROTTLE_JENDELA_DETIK = 5
THROTTLE_MAKS_PER_JAM = 20
RETRY_BACKOFF_DETIK = (1, 3, 7)


# ── Util ─────────────────────────────────────────────────────────────────


def _konfigurasi():
    return KonfigurasiApm.get_solo()


def _nama_rs():
    from akreditasi.models import RumahSakitProfile

    profil = RumahSakitProfile.objects.first()
    return (profil.name if profil and profil.name else 'RS Monsiskami Arima')


def normalisasi_nomor(nomor):
    bersih = str(nomor or '').strip().replace('-', '').replace(' ', '').replace('+', '')
    if bersih.startswith('0'):
        bersih = '62' + bersih[1:]
    if not bersih.isdigit() or not (10 <= len(bersih) <= 15):
        return ''
    return bersih


def mask_nama(nama):
    teks = str(nama or '').strip()
    if not teks:
        return '-'
    if len(teks) <= 3:
        return teks[0] + '**'
    return teks[:3] + '***'


def mask_nomor(nomor):
    bersih = str(nomor or '').strip()
    if len(bersih) <= 4:
        return '****'
    return '****' + bersih[-4:]


def mask_sep(no_sep):
    bersih = str(no_sep or '').strip()
    if len(bersih) <= 4:
        return '****'
    return '*' * (len(bersih) - 4) + bersih[-4:]


def hitung_waktu_relatif(base_time, offset_menit):
    """Kurangi ``offset_menit`` dari ``datetime.time`` → 'HH:MM'."""
    import datetime

    if not base_time:
        return '--:--'
    dummy_date = datetime.date(2026, 1, 1)
    dt = datetime.datetime.combine(dummy_date, base_time)
    return (dt - datetime.timedelta(minutes=offset_menit)).strftime('%H:%M')


def _label_poli(kunjungan):
    """Label poli: pakai master POLIKLINIK_CHOICES bila kodenya dikenal, jika tidak apa adanya."""
    from pasien.models import POLIKLINIK_CHOICES

    kode = kunjungan.poliklinik or ''
    label = dict(POLIKLINIK_CHOICES).get(kode)
    if label:
        return label
    getter = getattr(kunjungan, 'get_poliklinik_display', None)
    return getter() if callable(getter) else (kode or '-')


def _estimasi(kunjungan):
    from pasien.services.estimasi import EstimasiError, estimasi_kunjungan

    try:
        return estimasi_kunjungan(kunjungan)
    except EstimasiError:
        return None


def _jam_estimasi(kunjungan):
    """(jam_periksa, jam_anjuran_tiba) sebagai 'HH:MM'."""
    konf = _konfigurasi()
    estimasi = _estimasi(kunjungan)
    if estimasi is not None:
        return estimasi.t_periksa.strftime('%H:%M'), estimasi.t_tiba.strftime('%H:%M')
    if kunjungan.estimasi_pelayanan:
        return (
            kunjungan.estimasi_pelayanan.strftime('%H:%M'),
            hitung_waktu_relatif(kunjungan.estimasi_pelayanan, konf.buffer_tiba_menit),
        )
    return '--:--', '--:--'


def blok_peringatan_biometrik(kunjungan):
    """Teks peringatan biometrik hanya untuk poli wajib biometrik yang tidak dikecualikan."""
    konf = KonfigurasiBiometrikPoli.objects.filter(poliklinik=kunjungan.poliklinik).first()
    if not konf or not konf.mewajibkan(usia=_usia_pasien(kunjungan)):
        return ''
    return (
        'Catatan Penting: Poli tujuan mewajibkan verifikasi sidik jari / face recognition '
        'di Kiosk APM sebelum pencetakan SEP.'
    )


def _usia_pasien(kunjungan):
    lahir = getattr(kunjungan.pasien, 'tanggal_lahir', None)
    if not lahir:
        return None
    hari_ini = timezone.localdate()
    return hari_ini.year - lahir.year - ((hari_ini.month, hari_ini.day) < (lahir.month, lahir.day))


# ── Templat PRD §2B-3 ────────────────────────────────────────────────────


def format_konfirmasi_booking(kunjungan, base_url=None):
    """TEMPLAT 1 — Konfirmasi booking mobile dari HP Android (belum check-in)."""
    if not base_url:
        base_url = os.environ.get('SITE_URL', 'https://sim-akreditasi-django.vercel.app')
    jam_periksa, jam_tiba = _jam_estimasi(kunjungan)
    tanggal = kunjungan.tanggal_kunjungan or timezone.localtime(kunjungan.tanggal_masuk).date()
    peringatan = blok_peringatan_biometrik(kunjungan)
    token_batal = kunjungan.token_batal or f'TRX-{kunjungan.pk}'
    link_batal = f"{base_url.rstrip('/')}/pasien/apm/batal/?token={token_batal}"

    pesan = (
        f"*{_nama_rs()}*\n"
        f"Bukti Pendaftaran Rawat Jalan Mandiri\n\n"
        f"Yth. *{mask_nama(kunjungan.pasien.nama_lengkap)}*\n"
        f"Kode Booking: *{kunjungan.kode_booking or '-'}*  |  "
        f"No. Antrean Poli: *{kunjungan.nomor_antrean or '-'}*\n"
        f"Tanggal Kunjungan: {tanggal.strftime('%d/%m/%Y')}\n\n"
        f"Layanan poli spesialis: *{_label_poli(kunjungan)}*\n"
        f"Oleh dokter: *{kunjungan.dpjp or '-'}*\n"
        f"Waktu pelayanan: sesuai nomor antrean dan jam buka poli, "
        f"estimasi pemeriksaan pukul *{jam_periksa} WIB*\n\n"
        f"*Harap datang 30 menit lebih awal di lokasi pelayanan* "
        f"(dianjurkan tiba pukul *{jam_tiba} WIB*) untuk melakukan "
        f"*Scan QR Check-In* pada Kiosk Anjungan Pendaftaran Mandiri (APM).\n\n"
        f"{peringatan + chr(10) + chr(10) if peringatan else ''}"
        f"Simpan pesan ini dan tunjukkan QR Code booking Anda saat tiba di rumah sakit.\n\n"
        f"Pembatalan mandiri (paling lambat 60 menit sebelum jadwal): {link_batal}"
    )
    return pesan


def format_konfirmasi_checkin_sep(kunjungan):
    """TEMPLAT 2 — Konfirmasi check-in & penerbitan SEP di Kiosk APM."""
    jam_periksa, _ = _jam_estimasi(kunjungan)
    return (
        f"*{_nama_rs()}*\n"
        f"Konfirmasi Check-In & Penerbitan SEP\n\n"
        f"Yth. *{mask_nama(kunjungan.pasien.nama_lengkap)}*\n"
        f"No. SEP: *{mask_sep(kunjungan.no_sep) if kunjungan.no_sep else '-'}*  |  "
        f"No. Antrean Poli: *{kunjungan.nomor_antrean or '-'}*\n\n"
        f"Layanan poli spesialis: *{_label_poli(kunjungan)}*\n"
        f"Oleh dokter: *{kunjungan.dpjp or '-'}*\n"
        f"Waktu pelayanan: sesuai nomor antrean dan jam buka poli, "
        f"estimasi pemeriksaan pukul *{jam_periksa} WIB*\n\n"
        f"Silakan menuju ruang tunggu *{_label_poli(kunjungan)}* dan bersiap "
        f"*30 menit lebih awal* sebelum estimasi waktu pemeriksaan."
    )


def format_pergeseran_jadwal(kunjungan, estimasi_lama=None, estimasi_baru=None):
    """TEMPLAT 3 — Pemberitahuan pembaruan jadwal / pergeseran estimasi waktu."""
    konf = _konfigurasi()
    if estimasi_baru is None:
        estimasi_baru = kunjungan.estimasi_pelayanan
    jam_baru = estimasi_baru.strftime('%H:%M') if estimasi_baru else '--:--'
    jam_tiba = hitung_waktu_relatif(estimasi_baru, konf.buffer_tiba_menit) if estimasi_baru else '--:--'
    return (
        f"*{_nama_rs()}*\n"
        f"Pemberitahuan Pembaruan Estimasi Waktu Pemeriksaan\n\n"
        f"Yth. *{mask_nama(kunjungan.pasien.nama_lengkap)}* "
        f"(Kode Booking: *{kunjungan.kode_booking or '-'}* / "
        f"Antrean: *{kunjungan.nomor_antrean or '-'}*)\n"
        f"Terdapat penyesuaian jadwal pelayanan pada:\n"
        f"Layanan poli spesialis: *{_label_poli(kunjungan)}*  |  "
        f"Oleh dokter: *{kunjungan.dpjp or '-'}*\n\n"
        f"Estimasi pemeriksaan terbaru: pukul *{jam_baru} WIB*\n"
        f"*Harap datang 30 menit lebih awal di lokasi pelayanan* "
        f"(sekitar pukul *{jam_tiba} WIB*).\n\n"
        f"Terima kasih atas pengertian Anda."
    )


def format_notifikasi_igd(kunjungan):
    """Pesan darurat Fast-Track IGD (bukan bagian templat PRD, tetap dipertahankan)."""
    return (
        f"🚨 [EMERGENCY FAST-TRACK IGD] {_nama_rs()}\n"
        f"No. Antrean: {kunjungan.nomor_antrean}\n"
        f"Pasien: {mask_nama(kunjungan.pasien.nama_lengkap)} (RM: {kunjungan.pasien.no_rm})\n"
        f"Waktu Registrasi: {timezone.localtime(kunjungan.tanggal_masuk).strftime('%H:%M:%S WIB')}\n"
        f"Status: Triase Prioritas Merah (Kritis/Gawat Darurat).\n"
        f"Harap segera menuju Ruang Triase / Resusitasi IGD."
    )


def format_tiket_wa(kunjungan, base_url=None):
    """Alias kompatibilitas → Templat 1."""
    return format_konfirmasi_booking(kunjungan, base_url=base_url)


# ── Provider & pengiriman ────────────────────────────────────────────────


def _sleep(detik):
    time.sleep(detik)


def _kirim_fonnte(nomor, pesan, token):
    payload = json.dumps({'target': nomor, 'message': pesan, 'countryCode': '62'}).encode('utf-8')
    request = urllib.request.Request(
        'https://api.fonnte.com/send', data=payload,
        headers={'Authorization': token, 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return True, json.loads(response.read().decode('utf-8'))


def _kirim_waba(nomor, pesan, token, phone_id):
    payload = json.dumps({
        'messaging_product': 'whatsapp',
        'to': nomor,
        'type': 'text',
        'text': {'body': pesan},
    }).encode('utf-8')
    request = urllib.request.Request(
        f'https://graph.facebook.com/v20.0/{phone_id}/messages', data=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return True, json.loads(response.read().decode('utf-8'))


def _throttled(nomor, jenis_pesan=''):
    """Batasi pengiriman: 1 per 5 detik per (nomor, jenis pesan), maksimal 20/jam per nomor."""
    sekarang = timezone.now()
    jendela = sekarang - timezone.timedelta(seconds=THROTTLE_JENDELA_DETIK)
    filter_jendela = {'nomor_tujuan': nomor, 'created_at__gte': jendela}
    if jenis_pesan:
        filter_jendela['jenis_pesan'] = jenis_pesan
    if WhatsAppLog.objects.filter(**filter_jendela).exists():
        return True
    sejam = sekarang - timezone.timedelta(hours=1)
    return WhatsAppLog.objects.filter(nomor_tujuan=nomor, created_at__gte=sejam).count() >= THROTTLE_MAKS_PER_JAM


def kirim_pesan_wa(nomor, pesan, jenis_pesan='TIKET_APM', kunjungan=None, idempotency_key=None):
    """Kirim satu pesan WhatsApp dengan idempotensi, throttle, dan retry.

    Returns:
        dict: ``{success, mode, log_id, percobaan}``. ``mode`` salah satu dari
        ``fonnte``, ``waba``, ``simulated``, ``throttled``, ``duplicate``.
    """
    clean_nomor = normalisasi_nomor(nomor)
    if not clean_nomor:
        return {'success': False, 'mode': 'invalid_number', 'message': 'Nomor WhatsApp tidak valid.'}

    if idempotency_key:
        existing = WhatsAppLog.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return {'success': True, 'mode': 'duplicate', 'log_id': existing.id, 'percobaan': existing.percobaan}

    if _throttled(clean_nomor, jenis_pesan):
        log = WhatsAppLog.objects.create(
            nomor_tujuan=clean_nomor, jenis_pesan=jenis_pesan, pesan=pesan,
            status='THROTTLED', kunjungan=kunjungan, provider='throttle',
            idempotency_key=idempotency_key,
            response_api={'reason': 'rate_limited', 'window_detik': THROTTLE_JENDELA_DETIK},
        )
        return {'success': False, 'mode': 'throttled', 'log_id': log.id, 'percobaan': 0}

    konf = _konfigurasi()
    provider = (konf.wa_provider or 'FONNTE').upper()
    fonnte_token = os.environ.get('FONNTE_TOKEN', '')
    waba_token = os.environ.get('WABA_TOKEN', '')
    waba_phone_id = os.environ.get('WABA_PHONE_ID', '')

    if provider == 'SIMULASI' or (provider == 'FONNTE' and not fonnte_token) or (
        provider == 'WABA' and not (waba_token and waba_phone_id)
    ):
        log = WhatsAppLog.objects.create(
            nomor_tujuan=clean_nomor, jenis_pesan=jenis_pesan, pesan=pesan,
            status='SIMULASI', kunjungan=kunjungan, provider='simulasi',
            idempotency_key=idempotency_key,
            response_api={'simulated': True, 'timestamp': timezone.now().isoformat()},
        )
        if kunjungan:
            kunjungan.wa_notifikasi_sent = True
            kunjungan.save(update_fields=['wa_notifikasi_sent'])
        return {'success': True, 'mode': 'simulated', 'log_id': log.id, 'percobaan': 1}

    percobaan_maks = max(1, konf.wa_retry_maks or 1)
    terakhir = {}
    for percobaan in range(1, percobaan_maks + 1):
        try:
            if provider == 'WABA':
                ok, respons = _kirim_waba(clean_nomor, pesan, waba_token, waba_phone_id)
            else:
                ok, respons = _kirim_fonnte(clean_nomor, pesan, fonnte_token)
            log = WhatsAppLog.objects.create(
                nomor_tujuan=clean_nomor, jenis_pesan=jenis_pesan, pesan=pesan,
                status='SENT' if ok else 'FAILED', kunjungan=kunjungan,
                provider=provider.lower(), percobaan=percobaan,
                idempotency_key=idempotency_key, response_api=respons or {},
            )
            if kunjungan and ok:
                kunjungan.wa_notifikasi_sent = True
                kunjungan.save(update_fields=['wa_notifikasi_sent'])
            return {
                'success': bool(ok), 'mode': provider.lower(), 'log_id': log.id,
                'percobaan': percobaan, 'response': respons,
            }
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            terakhir = {'error': str(exc), 'percobaan': percobaan}
            logger.warning('WA gagal (percobaan %s/%s): %s', percobaan, percobaan_maks, exc)
            if percobaan < percobaan_maks:
                _sleep(RETRY_BACKOFF_DETIK[min(percobaan - 1, len(RETRY_BACKOFF_DETIK) - 1)])

    log = WhatsAppLog.objects.create(
        nomor_tujuan=clean_nomor, jenis_pesan=jenis_pesan, pesan=pesan,
        status='FAILED', kunjungan=kunjungan, provider=provider.lower(),
        percobaan=percobaan_maks, idempotency_key=idempotency_key,
        response_api=terakhir,
    )
    return {'success': False, 'mode': provider.lower(), 'log_id': log.id, 'percobaan': percobaan_maks}


def kirim_templat(kunjungan, jenis_pesan, base_url=None):
    """Kirim salah satu templat PRD dengan idempotensi berbasis versi estimasi."""
    target = normalisasi_nomor(kunjungan.pasien.no_hp)
    if not target:
        return {'success': False, 'mode': 'no_number'}

    if jenis_pesan == 'KONFIRMASI_BOOKING':
        pesan = format_konfirmasi_booking(kunjungan, base_url=base_url)
    elif jenis_pesan == 'CHECKIN_SEP':
        pesan = format_konfirmasi_checkin_sep(kunjungan)
    elif jenis_pesan == 'PERGESERAN_JADWAL':
        pesan = format_pergeseran_jadwal(kunjungan)
    elif jenis_pesan == 'NOTIFIKASI_IGD':
        pesan = format_notifikasi_igd(kunjungan)
    else:
        raise ValueError(f'Jenis templat tidak dikenal: {jenis_pesan}')

    kunci = f'{kunjungan.pk}:{jenis_pesan}:{kunjungan.estimasi_versi}'
    return kirim_pesan_wa(
        target, pesan, jenis_pesan=jenis_pesan, kunjungan=kunjungan, idempotency_key=kunci,
    )


def notifier_pergeseran(kunjungan, estimasi_lama, estimasi_baru, alasan=''):
    """Callback untuk ``estimasi.recompute_for_schedule``."""
    hasil = kirim_pesan_wa(
        kunjungan.pasien.no_hp,
        format_pergeseran_jadwal(kunjungan, estimasi_lama, estimasi_baru),
        jenis_pesan='PERGESERAN_JADWAL',
        kunjungan=kunjungan,
        idempotency_key=f'{kunjungan.pk}:PERGESERAN_JADWAL:{kunjungan.estimasi_versi}',
    )
    return hasil.get('success', False)