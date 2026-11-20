"""Validasi & kepatuhan rujukan BPJS (BL-02 / BL-03 / RSK-APM-02).

Aturan baku (plan 2026-11-19, Phase 4):
- Nomor rujukan = 19 digit; format lain ditolak sebelum menyentuh jaringan.
- Status mengikuti presedensi ``RujukanBpjs.status_dari_aturan``:
  TIDAK_DITEMUKAN → TIDAK_AKTIF → BEDA_PPK → KEDALUWARSA → VALID.
- Mode simulasi tidak pernah menghasilkan status VALID.
"""
import json
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from pasien.models import RujukanBpjs
from pasien.services import bpjs_vclaim
from pasien.services.bpjs_vclaim import BridgingError

PANJANG_NOMOR_RUJUKAN = 19

ALASAN = {
    'VALID': 'Rujukan valid dan dapat digunakan.',
    'KEDALUWARSA': 'Rujukan sudah melewati masa berlaku 90 hari sejak tanggal terbit.',
    'BEDA_PPK': 'Kode PPK tujuan pada rujukan berbeda dengan rumah sakit ini.',
    'TIDAK_DITEMUKAN': 'Nomor rujukan tidak ditemukan pada data BPJS.',
    'TIDAK_AKTIF': 'Status kepesertaan BPJS tidak aktif.',
    'BELUM_DIVALIDASI': 'Rujukan belum divalidasi.',
}

JALUR_ALTERNATIF = {
    'VALID': 'LANJUT',
    'KEDALUWARSA': 'PERBARUI_FKTP',
    'BEDA_PPK': 'LOKET_INFORMASI',
    'TIDAK_DITEMUKAN': 'LOKET_INFORMASI',
    'TIDAK_AKTIF': 'LOKET_ADMISI',
    'BELUM_DIVALIDASI': 'LOKET_ADMISI',
}

KODE_RISIKO_PER_STATUS = {
    'KEDALUWARSA': 'RUJUKAN_KEDALUWARSA',
    'BEDA_PPK': 'RUJUKAN_BEDA_PPK',
    'TIDAK_DITEMUKAN': 'RUJUKAN_TIDAK_DITEMUKAN',
    'TIDAK_AKTIF': 'PESERTA_TIDAK_AKTIF',
}


class RujukanFormatError(ValueError):
    """Nomor rujukan tidak sesuai format 19 digit."""


@dataclass(frozen=True)
class HasilValidasi:
    status: str
    alasan: str
    boleh_lanjut: bool
    jalur_alternatif: str

    def as_dict(self):
        return {
            'status': self.status,
            'alasan': self.alasan,
            'boleh_lanjut': self.boleh_lanjut,
            'jalur_alternatif': self.jalur_alternatif,
        }


def parse_nomor_rujukan(raw):
    """Terima 19 digit dengan/tanpa spasi atau tanda hubung."""
    bersih = ''.join(character for character in str(raw or '') if character.isdigit())
    if len(bersih) != PANJANG_NOMOR_RUJUKAN:
        raise RujukanFormatError(
            f'Nomor rujukan harus {PANJANG_NOMOR_RUJUKAN} digit (diterima {len(bersih)} digit).'
        )
    return bersih


def parse_qr_rujukan(raw):
    """QR rujukan bisa berisi JSON ``{noRujukan: ...}`` atau 19 digit polos."""
    teks = str(raw or '').strip()
    if not teks:
        raise RujukanFormatError('Isi QR rujukan kosong.')
    if teks.startswith('{'):
        try:
            data = json.loads(teks)
        except ValueError as exc:
            raise RujukanFormatError('Isi QR rujukan bukan JSON yang valid.') from exc
        if not isinstance(data, dict):
            raise RujukanFormatError('Isi QR rujukan tidak dikenali.')
        nomor = data.get('noRujukan') or data.get('no_rujukan') or data.get('nomor') or data.get('no')
        if not nomor:
            raise RujukanFormatError('QR rujukan tidak memuat nomor rujukan.')
        return parse_nomor_rujukan(nomor)
    return parse_nomor_rujukan(teks)


def kode_ppk_rs():
    return getattr(settings, 'BPJS_KODE_PPK', '0000000')


def evaluate_rujukan(rujukan, *, kode_ppk='', tanggal_kunjungan=None, peserta_aktif=True):
    """Terapkan aturan kepatuhan pada satu ``RujukanBpjs``."""
    status = rujukan.status_dari_aturan(
        ppk_rs=kode_ppk or kode_ppk_rs(),
        peserta_aktif=peserta_aktif,
        tanggal_acuan=tanggal_kunjungan,
    )
    alasan = ALASAN.get(status, 'Rujukan tidak dapat digunakan.')
    if status == 'BEDA_PPK' and rujukan.ppk_tujuan:
        alasan = (
            f'Rujukan ditujukan ke PPK {rujukan.ppk_tujuan}, bukan ke rumah sakit ini '
            f'({kode_ppk or kode_ppk_rs()}).'
        )
    return HasilValidasi(
        status=status,
        alasan=alasan,
        boleh_lanjut=status == 'VALID',
        jalur_alternatif=JALUR_ALTERNATIF.get(status, 'LOKET_ADMISI'),
    )


def simpan_rujukan(pasien, data, *, kanal='SISTEM', kode_ppk='', tanggal_kunjungan=None):
    """Simpan/segarkan hasil validasi VClaim untuk pasien ini."""
    nomor = data.get('no_rujukan') or ''
    simulasi = data.get('mode') == 'SIMULASI'
    ditemukan = bool(data.get('ditemukan')) and not simulasi
    defaults = {
        'pasien': pasien,
        'jenis_rujukan': data.get('jenis_rujukan') or 'FKTP',
        'tgl_rujukan': _parse_tanggal(data.get('tgl_rujukan')),
        'tgl_kunjungan_rencana': _parse_tanggal(
            data.get('tgl_kunjungan_rencana') or tanggal_kunjungan
        ),
        'ppk_rujukan': data.get('ppk_rujukan') or '',
        'nama_ppk_rujukan': data.get('nama_ppk_rujukan') or '',
        'ppk_tujuan': data.get('ppk_tujuan') or '',
        'poli_tujuan_bpjs': data.get('poli_tujuan_bpjs') or '',
        'diagnosa_awal': data.get('diagnosa_awal') or '',
        'nama_diagnosa_awal': data.get('nama_diagnosa_awal') or '',
        'ditemukan_di_vclaim': ditemukan,
        'raw_response': data.get('raw') or {},
        'divalidasi_pada': timezone.now(),
        'divalidasi_oleh_kanal': kanal,
    }
    rujukan, _ = RujukanBpjs.objects.update_or_create(no_rujukan=nomor, defaults=defaults)

    hasil = evaluate_rujukan(
        rujukan,
        kode_ppk=kode_ppk or kode_ppk_rs(),
        tanggal_kunjungan=tanggal_kunjungan,
        peserta_aktif=not simulasi,
    )
    if simulasi:
        hasil = HasilValidasi(
            status='TIDAK_DITEMUKAN',
            alasan='Validasi rujukan berjalan dalam mode simulasi; status tidak dapat dinyatakan valid.',
            boleh_lanjut=False,
            jalur_alternatif='LOKET_ADMISI',
        )
    rujukan.status_validasi = hasil.status
    rujukan.alasan_tolak = '' if hasil.boleh_lanjut else hasil.alasan
    rujukan.save(update_fields=['status_validasi', 'alasan_tolak'])
    return rujukan, hasil


def validasi_rujukan_lengkap(no_rujukan, pasien, *, kanal='SISTEM', kode_ppk='', tanggal_kunjungan=None):
    """Format-check → VClaim → simpan → evaluasi.

    Raises:
        RujukanFormatError: nomor bukan 19 digit.
        BridgingError: bridging gagal (timeout/HTTP/meta error/kredensial kosong).
    """
    nomor = parse_nomor_rujukan(no_rujukan)
    data = bpjs_vclaim.validasi_rujukan(nomor, kode_ppk or kode_ppk_rs(), tanggal_kunjungan)
    return simpan_rujukan(
        pasien, data, kanal=kanal, kode_ppk=kode_ppk, tanggal_kunjungan=tanggal_kunjungan,
    )


def _parse_tanggal(nilai):
    if not nilai:
        return None
    if hasattr(nilai, 'year'):
        return nilai
    teks = str(nilai).strip()[:10]
    try:
        return timezone.datetime.strptime(teks, '%Y-%m-%d').date()
    except ValueError:
        return None


__all__ = [
    'BridgingError', 'HasilValidasi', 'KODE_RISIKO_PER_STATUS', 'RujukanFormatError',
    'evaluate_rujukan', 'kode_ppk_rs', 'parse_nomor_rujukan', 'parse_qr_rujukan',
    'simpan_rujukan', 'validasi_rujukan_lengkap',
]