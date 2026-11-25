"""Nomor e-SKDP dan jadwal kontrol (F5.6, matriks S8-L2-03).

**Satu skema penomoran.** Format ``SKDP-YYYYMMDD-NNNN`` sudah dipakai
``pasien/views.py`` saat pasien dipulangkan dari dasbor rawat jalan. Berkas ini
memindahkan format itu ke satu fungsi supaya jalur baru (Langkah 8) tidak
menciptakan format kedua. ``NNNN`` adalah nomor kunjungan, bukan urutan harian
— sama dengan perilaku lama, sehingga nomor tidak pernah bertabrakan antar
pasien dan tidak bergantung pada jam penyimpanan.

**Jadwal kontrol.** Matriks S8-L2-03 memberi empat pilihan; hanya tiga yang
menyebut jarak hari (7/14/30). Opsi "sesuai jadwal tindakan / hasil lab" tidak
memberi jarak apa pun, jadi **tidak ada tanggal yang dihitung** untuknya —
nomor SKDP tetap terbit, tanggal kontrol tetap kosong sampai diisi manusia.
"""
from django.utils import timezone

from pasien.models import DischargeRecord
from pasien.workflow_schemas import JADWAL_KONTROL_CHOICES, JADWAL_KONTROL_HARI

SKDP_NOMOR_TEMPLATE = 'SKDP-{tanggal}-{urut:04d}'


def skdp_nomor(visit, tanggal=None):
    """Nomor SKDP episode ini untuk tanggal terbit ``tanggal``."""
    hari = tanggal or timezone.localdate()
    return SKDP_NOMOR_TEMPLATE.format(tanggal=hari.strftime('%Y%m%d'), urut=visit.pk)


def jadwal_kontrol_tanggal(kode, hari_ini=None):
    """Tanggal kontrol dari satu kode matriks, atau ``None`` bila tak berjarak."""
    if kode not in JADWAL_KONTROL_CHOICES:
        raise ValueError('Jadwal kontrol tidak dikenal.')
    jarak = JADWAL_KONTROL_HARI.get(kode)
    if jarak is None:
        return None
    return (hari_ini or timezone.localdate()) + timezone.timedelta(days=jarak)


def apply_jadwal_kontrol(visit, kode, *, diagnosa='', terapi='', tanggal=None):
    """Terbitkan/mutakhirkan SKDP untuk satu jadwal kontrol Langkah 8.

    ``DischargeRecord`` adalah satu-satunya pemilik kolom ``skdp_*`` (tidak ada
    model kedua). Baris dibuat lebih awal bila belum ada — episode rawat jalan
    memang menerbitkan surat kontrol sebelum penutupan — dan penutupan episode
    kelak memakai ``update_or_create`` sehingga kolom SKDP tidak hilang.

    Kembalian: ``(record, tanggal_kontrol)``; ``tanggal_kontrol`` adalah
    ``None`` untuk opsi tanpa jarak hari.
    """
    tanggal_kontrol = jadwal_kontrol_tanggal(kode, tanggal)
    record, _created = DischargeRecord.objects.get_or_create(
        kunjungan=visit,
        defaults={
            'tanggal_discharge': timezone.now(),
            'kondisi_pulang': '',
            'resume_medis': '',
        },
    )
    record.skdp_nomor = skdp_nomor(visit, tanggal)
    record.skdp_diagnosa = (diagnosa or '')[:250]
    record.skdp_terapi = terapi or ''
    if tanggal_kontrol is not None:
        record.jadwal_kontrol = tanggal_kontrol
    record.save(update_fields=['skdp_nomor', 'skdp_diagnosa', 'skdp_terapi', 'jadwal_kontrol'])
    return record, tanggal_kontrol
