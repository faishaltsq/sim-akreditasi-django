"""Logika bisnis modul Jadwal Praktek Dokter.

Berisi pemeriksaan bentrok jadwal/ruang, validasi legalitas kredensial,
pembentukan jadwal harian dari pola rutin, kaskade izin/cuti, serta
sinkronisasi status sesi ke jadwal APM (anjungan pendaftaran mandiri).
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone


def cek_bentrok_jadwal(dokter_id, hari, jam_mulai, jam_selesai, exclude_id=None):
    """True bila dokter sudah punya jadwal rutin aktif yang tumpang tindih."""
    from sdm.models import JadwalPraktekRutin

    qs = JadwalPraktekRutin.objects.filter(
        dokter_id=dokter_id, hari=hari, is_active=True,
    ).filter(Q(jam_mulai__lt=jam_selesai) & Q(jam_selesai__gt=jam_mulai))
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def cek_bentrok_ruangan(
    unit_kerja_id, ruang, hari, jam_mulai, jam_selesai, exclude_id=None
):
    """True bila ruang praktek yang sama sudah terpakai pada jam tumpang tindih."""
    from sdm.models import JadwalPraktekRutin

    ruang = (ruang or '').strip()
    if not ruang:
        return False
    qs = JadwalPraktekRutin.objects.filter(
        unit_kerja_id=unit_kerja_id, ruang_praktek__iexact=ruang,
        hari=hari, is_active=True,
    ).filter(Q(jam_mulai__lt=jam_selesai) & Q(jam_selesai__gt=jam_mulai))
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def validasi_kredensial_dokter(dokter_id, *, as_of=None):
    """Kembalikan (is_valid, warnings) atas SPK/RKK dan SIP dokter.

    Peringatan dikembalikan sebagai daftar teks siap tampil; jadwal tetap boleh
    disimpan (keputusan operasional), tetapi badge peringatan wajib terlihat.

    SIP dibaca dari dua sumber, berurutan: master izin profesi
    (:class:`sdm.IzinProfesiPegawai`, sumber kanonis untuk nomor & masa berlaku)
    lalu berkas dokumen terverifikasi. Tanpa fallback ini, izin yang sudah
    diinput pada master izin tetap tampil sebagai "belum terverifikasi".
    """
    from sdm.models import IzinProfesiPegawai, PenugasanKlinis, VersiDokumen

    today = as_of or timezone.localdate()
    warnings = []

    spk_aktif = PenugasanKlinis.objects.filter(
        employee_id=dokter_id, is_active=True, berlaku_mulai__lte=today,
    ).filter(
        Q(berlaku_sampai__isnull=True) | Q(berlaku_sampai__gte=today)
    ).exists()
    if not spk_aktif:
        warnings.append('SPK/RKK tidak aktif atau sudah berakhir.')

    izin = (
        IzinProfesiPegawai.objects.filter(
            pegawai_id=dokter_id, subtype='SIP', is_local_rs=True,
        )
        .order_by('-tanggal_berakhir')
        .first()
    )
    if izin is not None:
        if izin.validity_mode == 'LIFETIME':
            pass
        elif izin.tanggal_berakhir is None:
            warnings.append('SIP belum memiliki tanggal berlaku.')
        elif izin.tanggal_berakhir < today:
            warnings.append(
                f'SIP kedaluwarsa sejak {izin.tanggal_berakhir:%d-%m-%Y}.'
            )
        elif izin.tanggal_berakhir <= today + timedelta(days=30):
            warnings.append(
                f'SIP akan kedaluwarsa pada {izin.tanggal_berakhir:%d-%m-%Y}.'
            )
    else:
        sip = (
            VersiDokumen.objects.filter(
                document__employee_id=dokter_id,
                document__jenis_berkas='SIP',
                status='VERIFIED',
            )
            .order_by('-valid_until')
            .first()
        )
        if sip is None:
            warnings.append('SIP belum terverifikasi.')
        elif sip.valid_until is None:
            warnings.append('SIP belum memiliki tanggal berlaku.')
        elif sip.valid_until < today:
            warnings.append(f'SIP kedaluwarsa sejak {sip.valid_until:%d-%m-%Y}.')
        elif sip.valid_until <= today + timedelta(days=30):
            warnings.append(f'SIP akan kedaluwarsa pada {sip.valid_until:%d-%m-%Y}.')

    return (not warnings, warnings)


@transaction.atomic
def generate_jadwal_harian(tanggal, *, unit_kerja_id=None):
    """Bentuk baris jadwal harian dari pola rutin aktif pada tanggal tersebut.

    Idempoten: jadwal rutin yang sudah punya baris pada tanggal itu dilewati.
    Kembalikan jumlah baris yang baru dibuat.
    """
    from sdm.models import JadwalPraktekHarian, JadwalPraktekRutin

    hari = tanggal.weekday()
    rutin_qs = JadwalPraktekRutin.objects.filter(
        hari=hari, is_active=True,
    ).select_related('dokter', 'unit_kerja')
    if unit_kerja_id:
        rutin_qs = rutin_qs.filter(unit_kerja_id=unit_kerja_id)

    dibuat = 0
    for rutin in rutin_qs:
        _, created = JadwalPraktekHarian.objects.get_or_create(
            jadwal_rutin=rutin, tanggal=tanggal,
            defaults={
                'dokter_rencana': rutin.dokter,
                'unit_kerja': rutin.unit_kerja,
                'jam_mulai_rencana': rutin.jam_mulai,
                'jam_selesai_rencana': rutin.jam_selesai,
                'kuota_jkn': rutin.kuota_jkn,
                'kuota_non_jkn': rutin.kuota_non_jkn,
            },
        )
        if created:
            dibuat += 1
    return dibuat


@transaction.atomic
def proses_izin_dokter(izin, *, pengguna=None):
    """Terapkan izin yang disetujui ke seluruh jadwal harian terdampak.

    Bila ada dokter pengganti -> status DIGANTIKAN, selain itu BATAL.
    Setiap perubahan dicatat pada LogAuditJadwal.
    """
    from sdm.models import JadwalPraktekHarian, LogAuditJadwal

    terdampak = JadwalPraktekHarian.objects.filter(
        dokter_rencana=izin.dokter,
        tanggal__gte=izin.tanggal_mulai,
        tanggal__lte=izin.tanggal_selesai,
        status_sesi__in=['AKTIF', 'MUNDUR'],
    )
    diubah = 0
    for jadwal in terdampak:
        status_lama = jadwal.status_sesi
        if izin.dokter_pengganti_id:
            jadwal.status_sesi = 'DIGANTIKAN'
            jadwal.dokter_pengganti = izin.dokter_pengganti
            jadwal.dokter_aktual = izin.dokter_pengganti
        else:
            jadwal.status_sesi = 'BATAL'
        jadwal.alasan_perubahan = f'{izin.get_jenis_display()}: {izin.catatan}'.strip()
        jadwal.save(update_fields=[
            'status_sesi', 'dokter_pengganti', 'dokter_aktual',
            'alasan_perubahan', 'updated_at',
        ])
        LogAuditJadwal.objects.create(
            jadwal_harian=jadwal,
            pengguna=pengguna,
            jenis_aksi='GANTI_DOKTER' if izin.dokter_pengganti_id else 'BATAL',
            ringkasan=(
                f'Izin {izin.get_jenis_display()} {izin.tanggal_mulai} s/d '
                f'{izin.tanggal_selesai}. Status {status_lama} -> {jadwal.status_sesi}.'
            ),
        )
        diubah += 1
    return diubah


def sync_jadwal_ke_apm(jadwal_harian):
    """Selaraskan status sesi HC ke baris jadwal APM milik dokter yang sama."""
    from pasien.models import JadwalDokterPoli

    dokter = jadwal_harian.dokter_rencana
    if dokter is None:
        return 0

    target = 'BUKA'
    if jadwal_harian.status_sesi == 'BATAL':
        target = 'LIBUR'
    elif jadwal_harian.status_sesi in ('MUNDUR', 'DIGANTIKAN'):
        target = 'BUKA'

    baris = JadwalDokterPoli.objects.filter(pegawai=dokter)
    return baris.update(status_ketersediaan=target, updated_at=timezone.now())
