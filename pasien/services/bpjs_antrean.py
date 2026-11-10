import logging
import json
import urllib.request
from django.utils import timezone
from pasien.models import AntreanBpjsTaskLog
from pasien.bpjs import _is_live_mode, _bpjs_auth_headers, BPJS_ANTREAN_BASE

logger = logging.getLogger(__name__)

TASK_ID_NAMES = {
    1: 'Mulai waktu tunggu admisi',
    2: 'Akhir waktu tunggu admisi / mulai pelayanan admisi',
    3: 'Akhir pelayanan admisi / check-in APM / mulai waktu tunggu poli',
    4: 'Mulai pemeriksaan dokter',
    5: 'Selesai pemeriksaan dokter / mulai waktu tunggu farmasi',
    6: 'Mulai pelayanan farmasi',
    7: 'Selesai pelayanan farmasi / serah terima obat',
}


def update_task_id(kunjungan, task_id, waktu=None):
    """
    Mencatat dan mengirim Task ID 1-7 Antrean Online BPJS Kesehatan.
    Mendukung Live Mode (BPJS Antrean RS API) atau Simulated Mode.
    """
    if task_id not in TASK_ID_NAMES:
        raise ValueError(f"Task ID {task_id} tidak valid. Harus antara 1 hingga 7.")

    waktu_event = waktu or timezone.now()
    nama_task = TASK_ID_NAMES[task_id]
    kode_booking = kunjungan.kode_booking or kunjungan.no_kunjungan
    waktu_ms = int(waktu_event.timestamp() * 1000)

    status_kirim = 'SIMULATED'
    resp_data = {
        'metadata': {'code': 200, 'message': 'Ok (Simulated)'},
        'kodebooking': kode_booking,
        'taskid': task_id,
        'waktu': waktu_ms
    }

    if _is_live_mode() and kunjungan.penjamin == 'BPJS':
        try:
            url = f"{BPJS_ANTREAN_BASE}/antrean/updatewaktu"
            headers = _bpjs_auth_headers("/antrean/updatewaktu")
            headers['Content-Type'] = 'application/json'
            payload = json.dumps({
                'kodebooking': kode_booking,
                'taskid': task_id,
                'waktu': waktu_ms
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                code = resp_data.get('metadata', {}).get('code')
                status_kirim = 'SENT' if str(code) == '200' else 'FAILED'
        except Exception as e:
            logger.warning("BPJS Antrean Task %s gagal dikirim: %s. Fallback SIMULATED.", task_id, e)
            status_kirim = 'FAILED'
            resp_data = {'error': str(e)}

    log, _ = AntreanBpjsTaskLog.objects.update_or_create(
        kunjungan=kunjungan,
        task_id=task_id,
        defaults={
            'nama_task': nama_task,
            'waktu': waktu_event,
            'status_kirim': status_kirim,
            'response_bpjs': resp_data
        }
    )

    return {
        'success': True,
        'task_id': task_id,
        'nama_task': nama_task,
        'status_kirim': status_kirim,
        'log_id': log.id
    }


def get_task_timeline(kunjungan):
    """Mengembalikan ringkasan progress 7 Task ID untuk suatu kunjungan"""
    existing = {log.task_id: log for log in AntreanBpjsTaskLog.objects.filter(kunjungan=kunjungan)}
    timeline = []
    for tid in range(1, 8):
        log = existing.get(tid)
        timeline.append({
            'task_id': tid,
            'nama_task': TASK_ID_NAMES[tid],
            'selesai': log is not None,
            'waktu': log.waktu.isoformat() if log else None,
            'status_kirim': log.status_kirim if log else 'PENDING'
        })
    return timeline
