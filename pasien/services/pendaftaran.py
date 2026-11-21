"""Logika pendaftaran mandiri bersama kiosk & portal mobile (single writer).

Dipisahkan dari ``apm_views`` agar kiosk dan portal mobile tidak punya dua
implementasi resolusi pasien/gerbang rujukan (plan 2026-11-19 Phase 6).
"""
import uuid

from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from pasien.models import (
    JadwalDokterPoli, KunjunganPasien, LogRisikoApm, POLIKLINIK_CHOICES, Pasien, RujukanBpjs,
)
from pasien.services.antrean import allocate_queue_number
from pasien.services.bpjs_antrean import update_task_id
from pasien.services.ktp_validator import parse_flexible_date
from pasien.services.rujukan import (
    BridgingError, KODE_RISIKO_PER_STATUS, RujukanFormatError,
    evaluate_rujukan, validasi_rujukan_lengkap,
)
from pasien.services.whatsapp import format_notifikasi_igd, kirim_pesan_wa, kirim_templat

TEXT_FIELDS = (
    'tipe_pasien', 'jenis_layanan', 'no_wa', 'penjamin', 'nama_lengkap',
    'nik', 'tanggal_lahir', 'jenis_kelamin', 'alamat', 'no_bpjs', 'no_rm', 'poliklinik',
    'no_rujukan',
)


def _galat(pesan, http_status=400, **tambahan):
    payload = {'success': False, 'message': pesan}
    payload.update(tambahan)
    return {'payload': payload, 'status': http_status}


def _matches_identity(pasien, data):
    nama = data.get('nama_lengkap', '')
    tanggal = data.get('tanggal_lahir', '')
    if not isinstance(nama, str) or not isinstance(tanggal, str):
        return False
    return (
        bool(nama.strip())
        and ' '.join(nama.split()).casefold() == ' '.join(pasien.nama_lengkap.split()).casefold()
        and parse_flexible_date(tanggal, prefer='DMY') == pasien.tanggal_lahir
    )


@transaction.atomic
def daftarkan(data, *, kanal='KIOSK', base_url=''):
    """Buat kunjungan APM. Return ``(kunjungan, error)``; salah satu selalu None."""
    if not isinstance(data, dict) or not data:
        return None, _galat('Format data pendaftaran tidak valid.')
    if any(not isinstance(data.get(key, ''), str) for key in TEXT_FIELDS):
        return None, _galat('Format data pendaftaran tidak valid.')

    jadwal_id = data.get('jadwal_id')
    if jadwal_id is not None and (
        isinstance(jadwal_id, bool) or not str(jadwal_id).isdigit() or len(str(jadwal_id)) > 18
    ):
        return None, _galat('Jadwal dokter tidak valid.')

    tipe_pasien = data.get('tipe_pasien', 'LAMA').upper()
    jenis_layanan = data.get('jenis_layanan', 'RAJAL').upper()
    no_wa = (data.get('no_wa') or '').strip()
    penjamin = (data.get('penjamin') or 'UMUM').upper()
    if tipe_pasien not in ('BARU', 'LAMA') or jenis_layanan not in ('IGD', 'RAJAL') or penjamin not in ('UMUM', 'BPJS', 'ASURANSI'):
        return None, _galat('Pilihan layanan tidak valid.')

    jadwal = None
    estimasi_jam = None
    if jenis_layanan == 'RAJAL':
        schedules = JadwalDokterPoli.objects.select_for_update()
        if jadwal_id:
            jadwal = schedules.filter(pk=jadwal_id).first()
        elif data.get('poliklinik'):
            jadwal = schedules.filter(poliklinik=data['poliklinik'], status_ketersediaan='BUKA').first()
        if not jadwal:
            return None, _galat('Jadwal dokter tidak ditemukan.')
        estimasi_jam = jadwal.get_next_estimasi_jam()
        hari_ini = timezone.localdate()
        if not jadwal.praktik_pada(hari_ini):
            return None, _galat(
                f'Mohon maaf, {jadwal.nama_dokter} tidak praktik hari ini '
                f'(jadwal praktik: {jadwal.hari_praktik}). Silakan pilih dokter atau poliklinik lain.'
            )
        if jadwal.status_ketersediaan == 'LIBUR':
            return None, _galat(f'Mohon maaf, jadwal {jadwal.nama_dokter} sedang libur / tutup.')
        if not jadwal.is_tersedia(hari_ini) or estimasi_jam is None:
            return None, _galat('Mohon maaf, kuota dokter untuk hari ini sudah penuh.')

    if tipe_pasien == 'BARU':
        nama = data.get('nama_lengkap', '').strip()
        nik = (data.get('nik') or '').strip()
        tgl_lahir_str = data.get('tanggal_lahir')
        jenis_kelamin = data.get('jenis_kelamin', 'L')
        alamat = data.get('alamat', '')
        no_bpjs = data.get('no_bpjs', '')

        if not nama or not tgl_lahir_str:
            return None, _galat('Nama lengkap dan tanggal lahir wajib diisi.')

        if nik and (not nik.isdigit() or len(nik) != 16):
            return None, _galat(
                f'NIK harus 16 digit angka (yang dikirim {len(nik)} digit). '
                'Periksa kembali NIK pada KTP, atau kosongkan bila pasien belum membawa KTP.'
            )

        pasien = Pasien.objects.filter(nik=nik).first() if nik else None
        if pasien and not _matches_identity(pasien, data):
            return None, _galat(
                'NIK ini sudah terdaftar dengan nama atau tanggal lahir yang berbeda. '
                'Periksa kembali ejaan nama dan tanggal lahir, atau gunakan pilihan "Pasien Lama" '
                'lalu cari dengan nomor rekam medis.',
                http_status=403,
            )

        tgl_lahir = parse_flexible_date(tgl_lahir_str, prefer='DMY')
        if not tgl_lahir or tgl_lahir > timezone.localdate():
            return None, _galat('Tanggal lahir tidak valid.')

        if not pasien:
            today_str = timezone.localdate().strftime('%Y%m%d')
            urutan = Pasien.objects.filter(no_rm__startswith=f'RM-{today_str}').count() + 1
            pasien = Pasien.objects.create(
                no_rm=f'RM-{today_str}-{urutan:04d}',
                nama_lengkap=nama, nik=nik, tanggal_lahir=tgl_lahir,
                jenis_kelamin=jenis_kelamin, alamat=alamat, no_hp=no_wa, no_bpjs=no_bpjs,
            )
    else:
        no_rm = data.get('no_rm', '').strip()
        nik = data.get('nik', '').strip()
        no_bpjs = data.get('no_bpjs', '').strip()
        pasien = Pasien.objects.filter(
            Q(no_rm__iexact=no_rm) |
            (Q(nik=nik) if nik else Q(pk__isnull=True)) |
            (Q(no_bpjs=no_bpjs) if no_bpjs else Q(pk__isnull=True))
        ).first()
        if not pasien:
            return None, _galat('Data pasien lama tidak ditemukan.', http_status=404)
        if not _matches_identity(pasien, data):
            return None, _galat('Verifikasi identitas pasien gagal.', http_status=403)
        if no_wa and pasien.no_hp != no_wa:
            pasien.no_hp = no_wa
            pasien.save(update_fields=['no_hp'])

    rujukan = None
    if jenis_layanan == 'RAJAL' and penjamin == 'BPJS':
        rujukan, error = _gerbang_rujukan(data, pasien, kanal)
        if error:
            return None, error

    now = timezone.now()
    today_date = timezone.localdate()
    suffix = uuid.uuid4().hex[:4].upper()
    token_batal = uuid.uuid4().hex[:12].upper()
    kode_booking = f'APM-{today_date:%Y%m%d}-{suffix}'

    if jenis_layanan == 'IGD':
        nomor_antrean = allocate_queue_number('IGD', tanggal=today_date)
        kunjungan = KunjunganPasien.objects.create(
            pasien=pasien,
            no_kunjungan=f'REG-APM-{now:%Y%m%d%H%M%S}-{suffix}',
            jenis_kunjungan='IGD',
            tanggal_masuk=now,
            poliklinik='IGD',
            dpjp='Dokter Jaga IGD',
            nomor_antrean=nomor_antrean,
            penjamin=penjamin,
            flag_khusus='KRITIS',
            status_antrean='MENUNGGU',
            kode_booking=kode_booking,
            token_batal=token_batal,
            estimasi_pelayanan=timezone.localtime().time(),
            is_apm=True,
        )
        target = no_wa or pasien.no_hp
        if target:
            kirim_pesan_wa(
                target, format_notifikasi_igd(kunjungan),
                jenis_pesan='NOTIFIKASI_IGD', kunjungan=kunjungan,
            )
        return kunjungan, None

    nomor_antrean = allocate_queue_number('RAJAL', jadwal.poliklinik, tanggal=today_date)
    kunjungan = KunjunganPasien.objects.create(
        pasien=pasien,
        no_kunjungan=f'REG-APM-{now:%Y%m%d%H%M%S}-{suffix}',
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
        is_apm=True,
        rujukan=rujukan,
        diagnosa_masuk=(rujukan.diagnosa_awal if rujukan else ''),
    )
    if penjamin == 'BPJS':
        update_task_id(kunjungan, 1)
    if pasien.no_hp:
        kirim_templat(kunjungan, 'KONFIRMASI_BOOKING', base_url=base_url)
    return kunjungan, None


def _gerbang_rujukan(data, pasien, kanal):
    nomor_rujukan = (data.get('no_rujukan') or '').strip()
    if not nomor_rujukan:
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-02', kanal=kanal, pemicu='RUJUKAN_WAJIB',
            severity='TINGGI', detail={'pasien': pasien.no_rm},
        )
        return None, _galat(
            'Pendaftaran BPJS rawat jalan wajib menyertakan nomor rujukan 19 digit. '
            'Perbarui rujukan di FKTP bila belum ada.',
            http_status=409, status='RUJUKAN_WAJIB', jalur_alternatif='PERBARUI_FKTP',
        )
    rujukan = RujukanBpjs.objects.filter(no_rujukan=nomor_rujukan, pasien=pasien).first()
    if rujukan is None:
        try:
            rujukan, _ = validasi_rujukan_lengkap(
                nomor_rujukan, pasien, kanal=kanal, tanggal_kunjungan=timezone.localdate(),
            )
        except RujukanFormatError as exc:
            return None, _galat(str(exc), http_status=400, status='FORMAT_RUJUKAN')
        except BridgingError as exc:
            LogRisikoApm.objects.create(
                kode_risiko='RSK-APM-04', kanal=kanal, pemicu='BRIDGING_TIMEOUT',
                severity='TINGGI', detail={'status': exc.status, 'pesan': str(exc)},
            )
            return None, _galat(
                'Layanan validasi rujukan BPJS sedang terganggu. Silakan menuju loket admisi '
                'untuk pendaftaran manual.',
                http_status=503, status='BRIDGING_DOWN', jalur_alternatif='LOKET_ADMISI',
            )

    hasil = evaluate_rujukan(rujukan, tanggal_kunjungan=timezone.localdate())
    if not hasil.boleh_lanjut:
        LogRisikoApm.objects.create(
            kode_risiko='RSK-APM-02', kanal=kanal,
            pemicu=KODE_RISIKO_PER_STATUS.get(hasil.status, 'RUJUKAN_TIDAK_LAYAK'),
            severity='TINGGI',
            detail={'no_rujukan': rujukan.no_rujukan, 'status': hasil.status},
        )
        return None, _galat(hasil.alasan, http_status=409, **hasil.as_dict())
    return rujukan, None


def payload_sukses(kunjungan, *, struk_url=''):
    return {
        'success': True,
        'kunjungan_id': kunjungan.id,
        'no_kunjungan': kunjungan.no_kunjungan,
        'nomor_antrean': kunjungan.nomor_antrean,
        'jenis_kunjungan': kunjungan.jenis_kunjungan,
        'kode_booking': kunjungan.kode_booking,
        'token_batal': kunjungan.token_batal,
        'estimasi_pelayanan': (
            kunjungan.estimasi_pelayanan.strftime('%H:%M') if kunjungan.estimasi_pelayanan else ''
        ),
        'dpjp': kunjungan.dpjp,
        'poliklinik': dict(POLIKLINIK_CHOICES).get(kunjungan.poliklinik, kunjungan.poliklinik),
        'struk_url': struk_url,
    }