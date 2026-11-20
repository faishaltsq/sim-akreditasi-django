"""Klien bridging BPJS Kesehatan: VClaim 2.0 + Antrean Online RS v2.

Prinsip modul ini (plan 2026-11-19, keputusan D6):
- Setiap kegagalan MELEMPAR ``BridgingError``. Tidak ada jalur yang mengembalikan
  "seolah berhasil" ketika kredensial belum dikonfigurasi atau bridging timeout.
- Satu-satunya sumber nomor SEP adalah respons ``/SEP/2.0/insert``.
- Mode simulasi hanya aktif bila ``settings.BPJS_ALLOW_SIMULATION`` menyala, dan
  hasilnya selalu ditandai ``mode='SIMULASI'`` agar tidak diklaim sebagai SEP nyata.

Catatan kontrak: bentuk payload mengikuti dokumentasi VClaim 2.0 / Antrean RS v2.
Bila RS memakai varian berbeda (v1.1), sesuaikan di ``_payload_sep`` /
``_payload_antrean`` saja; pemanggil tidak perlu berubah.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import date, datetime

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

BPJS_VCLAIM_BASE = getattr(
    settings, 'BPJS_VCLAIM_BASE_URL',
    'https://apijkn-dev.bpjs-kesehatan.go.id/vclaim-rest-dev',
)
BPJS_ANTREAN_BASE = getattr(
    settings, 'BPJS_ANTREAN_BASE_URL',
    'https://apijkn-dev.bpjs-kesehatan.go.id/antreanrs-dev',
)

# Status kegagalan yang boleh ditangani pemanggil secara berbeda.
STATUS_TIMEOUT = 'TIMEOUT'
STATUS_HTTP_ERROR = 'HTTP_ERROR'
STATUS_META_ERROR = 'META_ERROR'
STATUS_NOT_CONFIGURED = 'NOT_CONFIGURED'
STATUS_MAPPING_MISSING = 'MAPPING_MISSING'
STATUS_DATA_INVALID = 'DATA_INVALID'


class BridgingError(Exception):
    """Kegagalan bridging yang harus terlihat oleh operator, bukan ditelan."""

    def __init__(self, status, message='', *, meta_code=None, meta_message='', raw=None, path=''):
        self.status = status
        self.meta_code = str(meta_code) if meta_code is not None else None
        self.meta_message = meta_message or ''
        self.raw = raw or {}
        self.path = path
        detail = self.meta_message or message or status
        super().__init__(f'[{status}] {path or "-"}: {detail}')


# ── Kredensial & tanda tangan ────────────────────────────────────────────


def _credentials():
    cons_id = getattr(settings, 'BPJS_CONS_ID', None) or os.environ.get('BPJS_CONS_ID')
    secret_key = getattr(settings, 'BPJS_SECRET_KEY', None) or os.environ.get('BPJS_SECRET_KEY')
    user_key = getattr(settings, 'BPJS_USER_KEY', None) or os.environ.get('BPJS_USER_KEY')
    return cons_id, secret_key, user_key


def _is_live_mode():
    return all(_credentials())


def simulation_allowed():
    """Mode simulasi hanya untuk pengembangan; produksi wajib fail-closed."""
    flag = getattr(settings, 'BPJS_ALLOW_SIMULATION', None)
    if flag is None:
        return bool(getattr(settings, 'DEBUG', False))
    return bool(flag)


def _bpjs_auth_headers(path=''):
    """Header HMAC-SHA256: signature = HMAC(cons_id&timestamp, secret_key)."""
    cons_id, secret_key, user_key = _credentials()
    if not all([cons_id, secret_key, user_key]):
        return {}
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret_key.encode('utf-8'),
        f'{cons_id}&{timestamp}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return {
        'X-cons-id': cons_id,
        'X-timestamp': timestamp,
        'X-signature': signature,
        'user_key': user_key,
        'Content-Type': 'application/json',
    }


def _decrypt_response(payload):
    """Buka envelope VClaim: base64 → XOR dengan (cons_id + secret_key + user_key)."""
    if not isinstance(payload, str):
        return payload
    cons_id, secret_key, user_key = _credentials()
    key = f'{cons_id}{secret_key}{user_key}'.encode('utf-8')
    if not key:
        return payload
    try:
        raw = base64.b64decode(payload)
    except Exception:
        return payload
    plain = bytes(byte ^ key[index % len(key)] for index, byte in enumerate(raw))
    try:
        return json.loads(plain.decode('utf-8'))
    except Exception:
        return payload


def call(path, method='GET', payload=None, timeout=10, base=None):
    """Panggil endpoint BPJS dan kembalikan ``{meta_code, meta_message, response}``.

    Raises:
        BridgingError: kredensial kosong, timeout, HTTP non-200, atau metaData.code != 200.
    """
    if not _is_live_mode():
        raise BridgingError(
            STATUS_NOT_CONFIGURED,
            'Kredensial BPJS belum dikonfigurasi (BPJS_CONS_ID/SECRET_KEY/USER_KEY).',
            path=path,
        )

    url = f'{(base or BPJS_VCLAIM_BASE).rstrip("/")}{path}'
    headers = _bpjs_auth_headers(path)
    try:
        if method.upper() == 'POST':
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        raise BridgingError(STATUS_TIMEOUT, f'Timeout {timeout}s ke BPJS', path=path) from exc
    except requests.RequestException as exc:
        raise BridgingError(STATUS_HTTP_ERROR, f'Gagal koneksi ke BPJS: {exc}', path=path) from exc

    if response.status_code != 200:
        raise BridgingError(
            STATUS_HTTP_ERROR,
            f'HTTP {response.status_code} dari BPJS',
            meta_code=response.status_code,
            path=path,
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise BridgingError(STATUS_HTTP_ERROR, 'Respons BPJS bukan JSON', path=path) from exc

    meta = body.get('metaData') or body.get('metadata') or {}
    meta_code = str(meta.get('code', '')).strip()
    meta_message = str(meta.get('message', '')).strip()
    data = _decrypt_response(body.get('response'))

    if meta_code != '200':
        raise BridgingError(
            STATUS_META_ERROR,
            meta_message or 'BPJS menolak permintaan',
            meta_code=meta_code,
            meta_message=meta_message,
            raw=body,
            path=path,
        )

    return {'meta_code': meta_code, 'meta_message': meta_message, 'response': data or {}, 'raw': body}


# ── Pemetaan jadwal lokal → kode BPJS ────────────────────────────────────


def mapping_jadwal(kunjungan):
    """Jadwal dokter lokal yang menyimpan kode poli/dokter BPJS untuk kunjungan ini."""
    from pasien.models import JadwalDokterPoli

    jadwal = JadwalDokterPoli.objects.filter(
        nama_dokter=kunjungan.dpjp, poliklinik=kunjungan.poliklinik,
    ).first()
    if not jadwal:
        raise BridgingError(
            STATUS_MAPPING_MISSING,
            f'Jadwal dokter "{kunjungan.dpjp}" untuk poli {kunjungan.poliklinik} tidak ditemukan.',
        )
    if not jadwal.kode_poli_bpjs or not jadwal.kode_dokter_bpjs:
        raise BridgingError(
            STATUS_MAPPING_MISSING,
            f'Jadwal {jadwal.nama_dokter} belum memiliki kode poli/dokter BPJS.',
        )
    return jadwal


def _normalisasi_nomor_wa(nomor):
    bersih = str(nomor or '').strip().replace('-', '').replace(' ', '').replace('+', '')
    if bersih.startswith('0'):
        bersih = '62' + bersih[1:]
    return bersih


# ── Peserta ──────────────────────────────────────────────────────────────


def validasi_peserta(no_kartu, tanggal=None):
    """GET /Peserta/nokartu/{noKartu}/tgl/{tgl} → data kepesertaan ternormalisasi."""
    if not no_kartu:
        raise BridgingError(STATUS_DATA_INVALID, 'Nomor kartu BPJS kosong')
    tgl = tanggal or date.today().strftime('%Y-%m-%d')
    hasil = call(f'/Peserta/nokartu/{no_kartu}/tgl/{tgl}')
    peserta = (hasil['response'] or {}).get('peserta') or {}
    if not peserta:
        raise BridgingError(
            STATUS_META_ERROR, 'Data peserta kosong',
            meta_code=hasil['meta_code'], path='/Peserta/nokartu',
        )
    status = ((peserta.get('statusPeserta') or {}).get('keterangan') or '').strip()
    return {
        'mode': 'LIVE',
        'no_kartu': peserta.get('noKartu', no_kartu),
        'nik': peserta.get('nik', ''),
        'nama': peserta.get('nama', ''),
        'tgl_lahir': peserta.get('tglLahir', ''),
        'jenis_peserta': ((peserta.get('jnsPeserta') or {}).get('nama') or ''),
        'status_peserta': status,
        'aktif': status.upper() == 'AKTIF',
        'faskes_tingkat1': ((peserta.get('kdProviderPst') or {}).get('nmProvider') or ''),
        'kelas': ((peserta.get('hakKelas') or {}).get('keterangan') or ''),
        'raw': peserta,
    }


def cek_eligibilitas(no_bpjs, tanggal=None):
    """Kompatibilitas view lama: bentuk respons lama, tanpa melempar exception."""
    if not no_bpjs:
        return {'success': False, 'message': 'Nomor BPJS tidak diisi', 'eligible': False}
    try:
        data = validasi_peserta(no_bpjs, tanggal)
    except BridgingError as exc:
        if exc.status == STATUS_NOT_CONFIGURED and simulation_allowed():
            return {
                'success': True, 'eligible': True, 'mode': 'simulated',
                'nama': 'PESERTA DEMO', 'no_kartu': no_bpjs,
                'faskes_tingkat1': 'Puskesmas Demo (Simulasi)',
                'jenis_peserta': 'PPU', 'status_peserta': 'AKTIF',
                'message': '[SIMULASI] Kredensial BPJS belum dikonfigurasi',
            }
        return {
            'success': False, 'eligible': False, 'mode': 'gagal',
            'status_bridging': exc.status, 'message': str(exc),
        }
    return {
        'success': True,
        'eligible': data['aktif'],
        'mode': 'live',
        'nama': data['nama'],
        'no_kartu': data['no_kartu'],
        'faskes_tingkat1': data['faskes_tingkat1'],
        'jenis_peserta': data['jenis_peserta'],
        'status_peserta': data['status_peserta'],
        'raw': data['raw'],
    }


# ── Rujukan ──────────────────────────────────────────────────────────────


def _normalisasi_rujukan(rujukan, jenis_default):
    diagnosa = rujukan.get('diagnosa') or {}
    poli = rujukan.get('poliRujukan') or {}
    tgl = rujukan.get('tglRujukan') or None
    return {
        'mode': 'LIVE',
        'ditemukan': True,
        'no_rujukan': rujukan.get('noRujukan', ''),
        'no_kartu': rujukan.get('noKartu', ''),
        'jenis_rujukan': jenis_default,
        'tgl_rujukan': tgl,
        'tgl_kunjungan_rencana': rujukan.get('tglRencanaKunjungan') or None,
        'ppk_rujukan': rujukan.get('ppkRujukan', ''),
        'nama_ppk_rujukan': rujukan.get('nmPpkRujukan', ''),
        'ppk_tujuan': rujukan.get('ppkDirujuk', ''),
        'nama_ppk_tujuan': rujukan.get('nmPpkDirujuk', ''),
        'poli_tujuan_bpjs': poli.get('kode', ''),
        'nama_poli_tujuan': poli.get('nama', ''),
        'diagnosa_awal': diagnosa.get('kode', ''),
        'nama_diagnosa_awal': diagnosa.get('nama', ''),
        'catatan': rujukan.get('catatan', ''),
        'raw': rujukan,
    }


def validasi_rujukan(no_rujukan, kode_ppk_rs='', tanggal_kunjungan=None):
    """Validasi rujukan via ``/Rujukan/Peserta`` lalu ``/Rujukan/RS/Peserta``.

    Raises:
        BridgingError: timeout/HTTP/meta error selain "tidak ditemukan".
    """
    nomor = str(no_rujukan or '').strip()
    if not nomor:
        raise BridgingError(STATUS_DATA_INVALID, 'Nomor rujukan kosong')

    if not _is_live_mode():
        if not simulation_allowed():
            raise BridgingError(
                STATUS_NOT_CONFIGURED,
                'Validasi rujukan memerlukan kredensial VClaim produksi.',
                path='/Rujukan/Peserta',
            )
        return {
            'mode': 'SIMULASI', 'ditemukan': False, 'no_rujukan': nomor,
            'alasan': 'Simulasi: rujukan tidak dapat divalidasi tanpa kredensial.',
        }

    percobaan = (
        (f'/Rujukan/Peserta/{nomor}', 'FKTP'),
        (f'/Rujukan/RS/Peserta/{nomor}', 'ANTAR_FKRTL'),
    )
    terakhir = None
    for path, jenis in percobaan:
        try:
            hasil = call(path)
        except BridgingError as exc:
            if exc.meta_code == '201':
                terakhir = exc
                continue
            raise
        rujukan = (hasil['response'] or {}).get('rujukan') or {}
        if not rujukan:
            terakhir = BridgingError(
                STATUS_META_ERROR, 'Rujukan kosong', meta_code=hasil['meta_code'], path=path,
            )
            continue
        data = _normalisasi_rujukan(rujukan, jenis)
        if kode_ppk_rs:
            data['kode_ppk_rs'] = kode_ppk_rs
        if tanggal_kunjungan:
            data['tgl_kunjungan_rencana'] = data['tgl_kunjungan_rencana'] or str(tanggal_kunjungan)
        return data

    return {
        'mode': 'LIVE', 'ditemukan': False, 'no_rujukan': nomor,
        'alasan': (terakhir.meta_message if terakhir else 'Rujukan tidak ditemukan di VClaim.'),
        'raw': (terakhir.raw if terakhir else {}),
    }


def jadwal_dokter_bpjs(kode_poli, tanggal=None):
    """GET /jadwaldokter/kodepoli/{kode}/tanggal/{yyyy-MM-dd}."""
    tgl = tanggal or date.today()
    tgl_str = tgl.strftime('%Y-%m-%d') if hasattr(tgl, 'strftime') else str(tgl)
    hasil = call(f'/jadwaldokter/kodepoli/{kode_poli}/tanggal/{tgl_str}')
    return (hasil['response'] or {}).get('list') or []


# ── SEP ──────────────────────────────────────────────────────────────────


def _payload_sep(kunjungan, jadwal):
    pasien = kunjungan.pasien
    rujukan = kunjungan.rujukan
    asal_rujukan = '2' if rujukan.jenis_rujukan == 'ANTAR_FKRTL' else '1'
    return {
        'request': {
            't_sep': {
                'noKartu': pasien.no_bpjs,
                'tglSep': timezone.localdate().strftime('%Y-%m-%d'),
                'ppkPelayanan': getattr(settings, 'BPJS_KODE_PPK', '0000000'),
                'jnsPelayanan': '1' if kunjungan.jenis_kunjungan in ('RANAP', 'IGD') else '2',
                'klsRawat': {
                    'klsRawatHak': '3',
                    'klsRawatNaik': '',
                    'pembiayaan': '',
                    'penanggungJawab': '',
                },
                'noMR': pasien.no_rm,
                'rujukan': {
                    'asalRujukan': asal_rujukan,
                    'tglRujukan': rujukan.tgl_rujukan.strftime('%Y-%m-%d') if rujukan.tgl_rujukan else '',
                    'noRujukan': rujukan.no_rujukan,
                    'ppkRujukan': rujukan.ppk_rujukan,
                },
                'catatan': 'SEP terbit via APM ARima',
                'diagAwal': rujukan.diagnosa_awal or kunjungan.diagnosa_masuk or '',
                'poli': {'tujuan': jadwal.kode_poli_bpjs, 'eksekutif': '0'},
                'cob': {'cob': '0'},
                'katarak': {'katarak': '0'},
                'jaminan': {
                    'lakaLantas': '0',
                    'penjamin': {
                        'penjamin': '', 'tglKejadian': '', 'keterangan': '',
                        'suplesi': {'suplesi': '0', 'noSepSuplesi': ''},
                    },
                },
                'skdp': {'noSurat': '', 'kodeDPJP': str(jadwal.kode_dokter_bpjs)},
                'dpjpLayan': str(jadwal.kode_dokter_bpjs),
                'noTelp': _normalisasi_nomor_wa(pasien.no_hp),
                'user': 'ARIMA-APM',
            },
        },
    }


def terbitkan_sep(kunjungan):
    """Terbitkan SEP sekali saja (idempoten), lalu simpan nomor aslinya.

    Returns:
        dict: ``{success, mode, no_sep, message}``

    Raises:
        BridgingError: data tidak lengkap, mapping BPJS belum ada, atau BPJS menolak.
    """
    if kunjungan.no_sep:
        return {
            'success': True, 'mode': kunjungan.sep_mode or 'LIVE',
            'no_sep': kunjungan.no_sep, 'message': f'SEP {kunjungan.no_sep} sudah terbit sebelumnya.',
            'idempotent': True,
        }

    pasien = kunjungan.pasien
    if not pasien.no_bpjs:
        raise BridgingError(STATUS_DATA_INVALID, 'Pasien tidak memiliki No. BPJS')
    rujukan = kunjungan.rujukan
    if not rujukan or not rujukan.no_rujukan:
        raise BridgingError(STATUS_DATA_INVALID, 'Rujukan belum tervalidasi untuk kunjungan ini')

    jadwal = mapping_jadwal(kunjungan)

    if not _is_live_mode():
        if not simulation_allowed():
            _tandai_sep_gagal(kunjungan)
            raise BridgingError(
                STATUS_NOT_CONFIGURED,
                'Penerbitan SEP memerlukan kredensial VClaim; SEP tidak diterbitkan.',
                path='/SEP/2.0/insert',
            )
        no_sep = f"SIM-{timezone.localdate():%Y%m%d}-{kunjungan.pk:06d}"
        kunjungan.no_sep = no_sep
        kunjungan.sep_mode = 'SIMULASI'
        kunjungan.sep_terbit_pada = timezone.now()
        kunjungan.save(update_fields=['no_sep', 'sep_mode', 'sep_terbit_pada'])
        return {
            'success': True, 'mode': 'SIMULASI', 'no_sep': no_sep,
            'message': f'[SIMULASI] SEP {no_sep} — bukan SEP BPJS sesungguhnya.',
        }

    try:
        hasil = call('/SEP/2.0/insert', method='POST', payload=_payload_sep(kunjungan, jadwal))
    except BridgingError:
        _tandai_sep_gagal(kunjungan)
        raise

    sep = (hasil['response'] or {}).get('sep') or {}
    no_sep = sep.get('noSep') or ''
    if not no_sep:
        _tandai_sep_gagal(kunjungan)
        raise BridgingError(
            STATUS_META_ERROR, 'Respons SEP tanpa noSep',
            meta_code=hasil['meta_code'], raw=hasil['raw'], path='/SEP/2.0/insert',
        )

    kunjungan.no_sep = no_sep
    kunjungan.sep_mode = 'LIVE'
    kunjungan.sep_terbit_pada = timezone.now()
    kunjungan.save(update_fields=['no_sep', 'sep_mode', 'sep_terbit_pada'])
    return {'success': True, 'mode': 'LIVE', 'no_sep': no_sep, 'message': f'SEP {no_sep} berhasil diterbitkan.'}


def _tandai_sep_gagal(kunjungan):
    kunjungan.sep_mode = 'GAGAL'
    kunjungan.save(update_fields=['sep_mode'])


# ── Antrean Online RS v2 ─────────────────────────────────────────────────


def _payload_antrean(kunjungan, jadwal):
    pasien = kunjungan.pasien
    rujukan = kunjungan.rujukan
    tanggal_periksa = kunjungan.tanggal_kunjungan or timezone.localdate()
    epoch_ms = int(datetime.combine(tanggal_periksa, jadwal.jam_mulai).timestamp() * 1000)
    jenis_kunjungan = {'FKTP': 1, 'ANTAR_FKRTL': 4, 'KONTROL': 3, 'RS': 2}.get(
        getattr(rujukan, 'jenis_rujukan', 'FKTP'), 1,
    )
    return {
        'kodebooking': kunjungan.kode_booking or kunjungan.no_kunjungan,
        'jenispasien': 'JKN' if kunjungan.penjamin == 'BPJS' else 'NON JKN',
        'nomorkartu': pasien.no_bpjs or '',
        'nik': pasien.nik or '',
        'nohp': _normalisasi_nomor_wa(pasien.no_hp),
        'kodepoli': jadwal.kode_poli_bpjs,
        'namapoli': jadwal.get_poliklinik_display(),
        'pasienbaru': 0,
        'norm': pasien.no_rm,
        'tanggalperiksa': epoch_ms,
        'kodedokter': int(jadwal.kode_dokter_bpjs),
        'jampraktek': jadwal.jam_praktek_bpjs,
        'jeniskunjungan': jenis_kunjungan,
        'nomorreferensi': getattr(rujukan, 'no_rujukan', '') or '',
    }


def daftar_antrean_bpjs(kunjungan):
    """Daftarkan kunjungan ke Antrean Online BPJS sekali saja (idempoten)."""
    if kunjungan.no_referensi_antrean:
        return {
            'success': True, 'mode': 'LIVE', 'idempotent': True,
            'kodebooking': kunjungan.no_referensi_antrean, 'nomor_antrean': kunjungan.nomor_antrean,
        }

    if kunjungan.penjamin != 'BPJS':
        raise BridgingError(STATUS_DATA_INVALID, 'Antrean Online BPJS hanya untuk penjamin BPJS')

    jadwal = mapping_jadwal(kunjungan)

    if not _is_live_mode():
        if not simulation_allowed():
            raise BridgingError(
                STATUS_NOT_CONFIGURED,
                'Antrean Online memerlukan kredensial BPJS.',
                path='/antrean/add',
            )
        kodebooking = kunjungan.kode_booking or kunjungan.no_kunjungan
        kunjungan.no_referensi_antrean = kodebooking
        kunjungan.save(update_fields=['no_referensi_antrean'])
        return {
            'success': True, 'mode': 'SIMULASI', 'kodebooking': kodebooking,
            'nomor_antrean': kunjungan.nomor_antrean,
            'message': '[SIMULASI] Antrean BPJS belum dikonfigurasi.',
        }

    hasil = call('/antrean/add', method='POST', payload=_payload_antrean(kunjungan, jadwal), base=BPJS_ANTREAN_BASE)
    data = hasil['response'] or {}
    kodebooking = data.get('kodebooking') or (kunjungan.kode_booking or kunjungan.no_kunjungan)
    kunjungan.no_referensi_antrean = kodebooking
    kunjungan.save(update_fields=['no_referensi_antrean'])
    return {
        'success': True, 'mode': 'LIVE',
        'kodebooking': kodebooking,
        'nomor_antrean': data.get('nomorantrean') or kunjungan.nomor_antrean,
        'estimasi_dilayani': data.get('estimasidilayani'),
        'raw': data,
    }


# ── Kompatibilitas pemanggil lama (pasien/bpjs.py) ───────────────────────


def buat_sep(kunjungan):
    try:
        hasil = terbitkan_sep(kunjungan)
    except BridgingError as exc:
        return {
            'success': False, 'no_sep': None, 'mode': 'GAGAL',
            'status_bridging': exc.status, 'message': str(exc),
        }
    return {
        'success': True, 'no_sep': hasil['no_sep'], 'mode': hasil['mode'],
        'message': hasil['message'],
    }


def ambil_antrean(kunjungan, poli_kode=None):
    try:
        hasil = daftar_antrean_bpjs(kunjungan)
    except BridgingError as exc:
        return {
            'success': False, 'nomor_antrean': None, 'status_bridging': exc.status,
            'message': str(exc),
        }
    return {
        'success': True, 'mode': hasil['mode'],
        'nomor_antrean': hasil.get('nomor_antrean'),
        'task_id': None,
        'kodebooking': hasil.get('kodebooking'),
        'estimasi_waktu': hasil.get('estimasi_dilayani'),
    }


def bpjs_connection_status():
    if not _is_live_mode():
        return {
            'connected': False, 'mode': 'simulated',
            'message': 'Kredensial BPJS belum dikonfigurasi (BPJS_CONS_ID/SECRET_KEY/USER_KEY)',
            'vclaim_url': BPJS_VCLAIM_BASE,
            'antrean_url': BPJS_ANTREAN_BASE,
            'simulation_allowed': simulation_allowed(),
        }
    try:
        call('/Peserta/nokartu/0000000000000/tgl/' + date.today().strftime('%Y-%m-%d'), timeout=8)
        return {'connected': True, 'mode': 'live', 'message': 'Terhubung ke VClaim', 'vclaim_url': BPJS_VCLAIM_BASE}
    except BridgingError as exc:
        if exc.status == STATUS_META_ERROR:
            return {
                'connected': True, 'mode': 'live',
                'message': f'Terhubung ke VClaim (meta {exc.meta_code})', 'vclaim_url': BPJS_VCLAIM_BASE,
            }
        return {
            'connected': False, 'mode': 'live_failed', 'status_bridging': exc.status,
            'message': str(exc), 'vclaim_url': BPJS_VCLAIM_BASE,
        }