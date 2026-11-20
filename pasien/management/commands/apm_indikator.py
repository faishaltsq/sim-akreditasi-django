"""Cetak indikator mutu APM dalam JSON untuk dasbor mutu ARima.

Contoh:
    manage.py apm_indikator --bulan 2026-11
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pasien.services.indikator import hitung_indikator


class Command(BaseCommand):
    help = 'Hitung indikator mutu modul APM (registrasi, SEP, biometrik, blokir rujukan).'

    def add_arguments(self, parser):
        parser.add_argument('--bulan', help='Format YYYY-MM (default bulan berjalan)')

    def handle(self, *args, **options):
        hari_ini = timezone.localdate()
        tahun, bulan = hari_ini.year, hari_ini.month
        if options.get('bulan'):
            try:
                tahun_str, bulan_str = options['bulan'].split('-')
                tahun, bulan = int(tahun_str), int(bulan_str)
            except (ValueError, AttributeError) as exc:
                raise CommandError('Format --bulan harus YYYY-MM.') from exc
            if not 1 <= bulan <= 12:
                raise CommandError('Bulan harus antara 1 dan 12.')

        data = hitung_indikator(tahun, bulan)
        self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False))