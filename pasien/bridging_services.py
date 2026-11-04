"""Bridging kepesertaan — V-Claim BPJS & SatuSehat (SIMULASI).

Belum terhubung server BPJS/Kemenkes produksi. Payload mengikuti format
V-Claim 2.x dan FHIR Patient agar kontrak konsumsi UI tidak berubah saat
integrasi nyata dipasang.
"""
from datetime import date


def _valid_nik(nik):
    nik = (nik or '').strip()
    if not (nik.isdigit() and len(nik) == 16):
        raise ValueError('NIK harus 16 digit numerik.')
    return nik


class BPJSVClaimService:
    """Simulasi layanan BPJS V-Claim: cek kepesertaan by NIK."""

    @staticmethod
    def cek_peserta_by_nik(nik):
        nik = _valid_nik(nik)
        # Derivasi deterministik dari digit NIK agar simulasi stabil per-NIK.
        tahun = 1950 + (int(nik[6:8]) % 60)
        bulan = 1 + (int(nik[8:10]) % 12)
        hari = 1 + (int(nik[10:12]) % 28)
        sex = 'P' if int(nik[6]) >= 5 else 'L'  # konvensi NIK: +40 pada digit ke-7 untuk perempuan
        return {
            'noKartu': '000' + nik[:10],
            'nik': nik,
            'nama': '',  # nama hanya tersedia dari data lokal atau response server asli
            'tglLahir': date(tahun, bulan, hari).isoformat(),
            'sex': sex,
            'hakKelas': '3',
            'statusPeserta': 'AKTIF',
        }


class SatuSehatService:
    """Simulasi SatuSehat Kemenkes: Patient resource by NIK."""

    @staticmethod
    def get_patient_by_nik(nik):
        nik = _valid_nik(nik)
        return {
            'resourceType': 'Patient',
            'id': nik,
            'identifier': [{
                'system': 'https://fhir.kemkes.go.id/id/nik',
                'value': nik,
            }],
            'gender': 'female' if int(nik[6]) >= 5 else 'male',
            'birthDate': BPJSVClaimService.cek_peserta_by_nik(nik)['tglLahir'],
            'name': [{'text': ''}],
        }
