"""Seed konfigurasi APM-BPJS: parameter operasional + aturan wajib biometrik per poli.

Idempoten. Nilai yang sudah diubah admin TIDAK ditimpa kecuali `--force`.
"""
from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction
from pasien.models import KonfigurasiApm, KonfigurasiBiometrikPoli

# PRD §2E: poli wajib biometrik (dapat diubah admin kapan saja).
POLI_WAJIB_BIOMETRIK = [
    ('POLI_THT', {}),
    ('POLI_MATA', {}),
    ('POLI_JANTUNG', {}),
    ('REHAB_MEDIK', {}),
]


class Command(BaseCommand):
    help = 'Seed Konfigurasi APM dan aturan wajib biometrik per poliklinik.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Timpa nilai konfigurasi yang sudah diubah admin.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options['force']

        konfigurasi = KonfigurasiApm.get_solo()
        if force:
            konfigurasi.t_buka_rs = time(7, 0)
            konfigurasi.buffer_tiba_menit = 30
            konfigurasi.ambang_geser_notif_menit = 15
            konfigurasi.idle_timeout_detik = 90
            konfigurasi.biometrik_maks_percobaan = 3
            konfigurasi.booking_hari_ke_depan = 0
            konfigurasi.wa_provider = 'FONNTE'
            konfigurasi.wa_retry_maks = 3
            konfigurasi.full_clean()
            konfigurasi.save()
            self.stdout.write(self.style.WARNING('Konfigurasi APM dikembalikan ke default PRD (--force).'))
        self.stdout.write(
            f'Konfigurasi APM: buka {konfigurasi.t_buka_rs.strftime("%H:%M")}, '
            f'buffer {konfigurasi.buffer_tiba_menit} mnt, '
            f'ambang geser {konfigurasi.ambang_geser_notif_menit} mnt, '
            f'idle {konfigurasi.idle_timeout_detik}s, '
            f'biometrik maks {konfigurasi.biometrik_maks_percobaan}x, '
            f'WA {konfigurasi.wa_provider}'
        )

        dibuat, diperbarui = 0, 0
        for poliklinik, default in POLI_WAJIB_BIOMETRIK:
            konf, created = KonfigurasiBiometrikPoli.objects.get_or_create(
                poliklinik=poliklinik,
                defaults={'wajib_biometrik': True, 'aktif': True, **default},
            )
            if created:
                dibuat += 1
            elif force:
                konf.wajib_biometrik = True
                konf.aktif = True
                konf.save(update_fields=['wajib_biometrik', 'aktif', 'updated_at'])
                diperbarui += 1

        self.stdout.write(self.style.SUCCESS(
            f'Aturan biometrik: {dibuat} dibuat, {diperbarui} diperbarui, '
            f'{KonfigurasiBiometrikPoli.objects.count()} total.'
        ))