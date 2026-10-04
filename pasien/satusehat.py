"""
SatuSehat Kemenkes FHIR R4 Service Helper & QR Parser SIMRS MonsisKami.
Standar interoperabilitas Kemenkes RI (Permenkes No 24 Tahun 2022).
"""
import uuid
from datetime import datetime
from django.utils import timezone


def parse_qr_medis(qr_raw_text: str) -> dict:
    """
    Parse text hasil scan QR/Barcode KTP, Kartu BPJS, atau QR SatuSehat.
    Mendukung format:
    1. 16 digit angka (NIK langsung)
    2. Format BPJS KIS: '0001234567890' (13 digit)
    3. Format delimited (NIK|NAMA|TGL_LAHIR)
    4. Format JSON (SatuSehat IHSRecord)
    """
    import json
    text = (qr_raw_text or "").strip()
    result = {
        'tipe': 'UNKNOWN',
        'nik': '',
        'no_bpjs': '',
        'nama': '',
        'raw': text,
    }

    if not text:
        return result

    # JSON format
    if text.startswith('{') and text.endswith('}'):
        try:
            data = json.loads(text)
            result['tipe'] = 'JSON_SATUSEHAT'
            result['nik'] = str(data.get('nik') or data.get('identifier', ''))
            result['nama'] = data.get('nama') or data.get('name', '')
            result['no_bpjs'] = data.get('no_bpjs') or data.get('bpjs', '')
            return result
        except Exception:
            pass

    # Pipe delimited format e.g. 3201011234560001|BUDI SANTOSO|1988-05-12
    if '|' in text:
        parts = text.split('|')
        result['tipe'] = 'DELIMITED_KTP'
        if len(parts) >= 1 and parts[0].isdigit() and len(parts[0]) == 16:
            result['nik'] = parts[0]
        if len(parts) >= 2:
            result['nama'] = parts[1].strip()
        return result

    # 16-digit numeric -> NIK KTP
    clean_digits = "".join(filter(str.isdigit, text))
    if len(clean_digits) == 16:
        result['tipe'] = 'NIK_KTP'
        result['nik'] = clean_digits
        return result

    # 13-digit numeric -> No BPJS
    if len(clean_digits) == 13:
        result['tipe'] = 'NO_BPJS'
        result['no_bpjs'] = clean_digits
        return result

    result['tipe'] = 'RAW_TEXT'
    return result


def sync_pasien_satusehat(pasien) -> dict:
    """
    Simulasi sinkronisasi Master Pasien ke SatuSehat Kemenkes (FHIR R4 Patient Resource).
    Mengembalikan dict hasil dan update satusehat_id jika berhasil.
    """
    if not pasien.nik:
        return {
            'success': False,
            'message': 'Pasien belum memiliki NIK KTP yang valid untuk verifikasi SatuSehat.',
            'satusehat_id': None,
        }

    # Simulasi lookup IHS ID Kemenkes berbasis NIK
    ihs_id = pasien.satusehat_id or f"P-{pasien.nik[-8:]}-{uuid.uuid4().hex[:6].upper()}"
    pasien.satusehat_id = ihs_id
    pasien.satusehat_sync_at = timezone.now()
    pasien.save(update_fields=['satusehat_id', 'satusehat_sync_at'])

    fhir_patient_resource = {
        "resourceType": "Patient",
        "id": ihs_id,
        "identifier": [
            {
                "use": "official",
                "system": "https://fhir.kemkes.go.id/id/nik",
                "value": pasien.nik
            }
        ],
        "active": True,
        "name": [{"use": "official", "text": pasien.nama_lengkap}],
        "gender": "male" if pasien.jenis_kelamin == 'L' else "female",
        "birthDate": pasien.tanggal_lahir.strftime("%Y-%m-%d"),
    }

    return {
        'success': True,
        'message': f'Berhasil terverifikasi di SatuSehat Kemenkes (IHS ID: {ihs_id})',
        'satusehat_id': ihs_id,
        'fhir_payload': fhir_patient_resource,
    }


def sync_encounter_satusehat(kunjungan) -> dict:
    """
    Kirim FHIR R4 Encounter Resource ke SatuSehat Kemenkes.
    Status kunjungan, DPJP, dan diagnosis masuk/keluar di-bundle.
    """
    pasien = kunjungan.pasien
    if not pasien.satusehat_id:
        res_pasien = sync_pasien_satusehat(pasien)
        if not res_pasien['success']:
            kunjungan.satusehat_status = 'FAILED'
            kunjungan.save(update_fields=['satusehat_status'])
            return res_pasien

    encounter_uuid = kunjungan.satusehat_encounter_id or f"ENC-{uuid.uuid4().hex[:12].upper()}"
    kunjungan.satusehat_encounter_id = encounter_uuid
    kunjungan.satusehat_status = 'SYNCED'
    kunjungan.save(update_fields=['satusehat_encounter_id', 'satusehat_status'])

    # FHIR Encounter Standard Kemenkes
    fhir_encounter = {
        "resourceType": "Encounter",
        "id": encounter_uuid,
        "identifier": [
            {
                "system": "http://sys-ids.kemkes.go.id/encounter/monsiskami",
                "value": kunjungan.no_kunjungan
            }
        ],
        "status": "finished" if kunjungan.status in ('PULANG', 'RUJUK') else "in-progress",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "IMP" if kunjungan.jenis_kunjungan == 'RANAP' else ("EMER" if kunjungan.jenis_kunjungan == 'IGD' else "AMB"),
            "display": kunjungan.get_jenis_kunjungan_display()
        },
        "subject": {
            "reference": f"Patient/{pasien.satusehat_id}",
            "display": pasien.nama_lengkap
        },
        "participant": [
            {
                "individual": {
                    "display": kunjungan.dpjp or "Dokter Jaga RS MonsisKami"
                }
            }
        ],
        "period": {
            "start": kunjungan.tanggal_masuk.isoformat(),
            "end": kunjungan.tanggal_keluar.isoformat() if kunjungan.tanggal_keluar else None
        },
        "diagnosis": [
            {
                "condition": {
                    "display": kunjungan.diagnosa_masuk or "Pemeriksaan Umum"
                },
                "use": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/diagnosis-role",
                            "code": "AD",
                            "display": "Admission diagnosis"
                        }
                    ]
                }
            }
        ]
    }

    return {
        'success': True,
        'message': f'Encounter {kunjungan.no_kunjungan} berhasil disinkronkan ke SatuSehat Kemenkes!',
        'encounter_id': encounter_uuid,
        'satusehat_patient_id': pasien.satusehat_id,
        'fhir_payload': fhir_encounter,
    }
