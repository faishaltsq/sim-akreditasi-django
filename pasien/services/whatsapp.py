import os
import json
import logging
import datetime
from django.utils import timezone
from pasien.models import WhatsAppLog

logger = logging.getLogger(__name__)

def hitung_waktu_relatif(base_time, offset_menit):
    """
    Mengurangi menit dari datetime.time.
    Return string 'HH:MM'.
    """
    if not base_time:
        return "--:--"
    dummy_date = datetime.date(2026, 1, 1)
    dt = datetime.datetime.combine(dummy_date, base_time)
    res_dt = dt - datetime.timedelta(minutes=offset_menit)
    return res_dt.strftime('%H:%M')

def format_tiket_wa(kunjungan, base_url=None):
    """
    Format bukti pendaftaran APM via WhatsApp sesuai spesifikasi verbatim RS ARima.
    """
    if not base_url:
        base_url = os.environ.get('SITE_URL', 'https://sim-akreditasi-django.vercel.app')
    
    pasien = kunjungan.pasien
    no_rm = pasien.no_rm or '-'
    nama = pasien.nama_lengkap or '-'
    
    # Ambil label poli yang rapi
    poli = getattr(kunjungan, 'get_poliklinik_display', None)
    if callable(poli):
        poli = kunjungan.get_poliklinik_display()
    else:
        poli = kunjungan.poliklinik or '-'
        
    dpjp = kunjungan.dpjp or 'Dokter Jaga Poli'
    no_antrean = kunjungan.nomor_antrean or '-'
    
    if kunjungan.estimasi_pelayanan:
        jam_estimasi = kunjungan.estimasi_pelayanan.strftime('%H:%M')
        jam_hadir = hitung_waktu_relatif(kunjungan.estimasi_pelayanan, 30)
        jam_batas_batal = hitung_waktu_relatif(kunjungan.estimasi_pelayanan, 60)
    else:
        jam_estimasi = "09:00"
        jam_hadir = "08:30"
        jam_batas_batal = "08:00"
        
    token_batal = kunjungan.token_batal or f"TRX-{kunjungan.pk}"
    link_batal = f"{base_url.rstrip('/')}/pasien/apm/batal/?token={token_batal}"

    pesan = (
        f"[ RSU PKU MUHAMMADIYAH GOMBONG / RS ARima ] BUKTI PENDAFTARAN MANDIRI (APM)\n"
        f"No. Rekam Medis: {no_rm}\n"
        f"Nama Pasien: {nama}\n"
        f"Tujuan Poli: {poli}\n"
        f"Dokter DPJP: {dpjp}\n"
        f"No. Antrean Poli: {no_antrean}\n"
        f"Estimasi Waktu Pemeriksaan: {jam_estimasi} WIB\n\n"
        f"⚠️ HIMBAUAN PENTING:\n"
        f"Mohon hadir 30 menit sebelum waktu pemeriksaan (pukul {jam_hadir} WIB) di Ruang Tunggu {poli}. "
        f"Lakukan check-in ulang dengan scan barcode pesan ini pada scanner APM di lokasi.\n\n"
        f"❌ PEMBATALAN JANJI:\n"
        f"Pembatalan pendaftaran dapat dilakukan paling lambat 60 menit sebelum waktu pemeriksaan "
        f"(sebelum pukul {jam_batas_batal} WIB) dengan mengklik link berikut:\n"
        f"{link_batal}"
    )
    return pesan

def format_notifikasi_igd(kunjungan):
    """Format pesan darurat Fast-Track IGD"""
    pasien = kunjungan.pasien
    return (
        f"🚨 [EMERGENCY FAST-TRACK IGD] RS ARima\n"
        f"No. Antrean: {kunjungan.nomor_antrean}\n"
        f"Pasien: {pasien.nama_lengkap} (RM: {pasien.no_rm})\n"
        f"Waktu Registrasi: {kunjungan.tanggal_masuk.strftime('%H:%M:%S WIB')}\n"
        f"Status: Triase Prioritas Merah (Kritis/Gawat Darurat).\n"
        f"Harap segera menuju Ruang Triase / Resusitasi IGD."
    )

def kirim_pesan_wa(nomor, pesan, jenis_pesan='TIKET_APM', kunjungan=None):
    """
    Mengirim pesan WhatsApp menggunakan gateway (Fonnte/Wablas) jika tersedia token,
    atau mencatat dalam mode SIMULASI di database WhatsAppLog.
    """
    fonnte_token = os.environ.get('FONNTE_TOKEN')
    wablas_token = os.environ.get('WABLAS_TOKEN')
    
    # Normalisasi format nomor WA (62...)
    clean_nomor = str(nomor).strip().replace('-', '').replace(' ', '').replace('+', '')
    if clean_nomor.startswith('0'):
        clean_nomor = '62' + clean_nomor[1:]

    # Jika ada token Fonnte aktif
    if fonnte_token:
        try:
            import urllib.request
            url = "https://api.fonnte.com/send"
            data = json.dumps({
                "target": clean_nomor,
                "message": pesan,
                "countryCode": "62"
            }).encode('utf-8')
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Authorization": fonnte_token,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                log = WhatsAppLog.objects.create(
                    nomor_tujuan=clean_nomor,
                    jenis_pesan=jenis_pesan,
                    pesan=pesan,
                    status='SENT' if resp_data.get('status') else 'FAILED',
                    kunjungan=kunjungan,
                    response_api=resp_data
                )
                return {'success': True, 'mode': 'fonnte', 'log_id': log.id, 'response': resp_data}
        except Exception as e:
            logger.warning("Gagal mengirim WA via Fonnte: %s. Melanjutkan simulasi.", e)

    # Fallback / Simulasi Default
    log = WhatsAppLog.objects.create(
        nomor_tujuan=clean_nomor,
        jenis_pesan=jenis_pesan,
        pesan=pesan,
        status='SIMULASI',
        kunjungan=kunjungan,
        response_api={'simulated': True, 'timestamp': timezone.now().isoformat()}
    )
    if kunjungan:
        kunjungan.wa_notifikasi_sent = True
        kunjungan.save(update_fields=['wa_notifikasi_sent'])

    return {'success': True, 'mode': 'simulated', 'log_id': log.id}
