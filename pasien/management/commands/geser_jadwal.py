"""Geser jadwal dokter dan hitung ulang estimasi pasien yang belum dipanggil.

Dipakai perawat poli / admin SIMRS saat dokter mulai lebih lambat atau lebih cepat.
Contoh:
    manage.py geser_jadwal --jadwal 12 --delta 20 --alasan "Dokter terlambat operasi"
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from pasien.models import JadwalDokterPoli
from pasien.services.estimasi import recompute_for_schedule
from pasien.services.whatsapp import notifier_pergeseran


class Command(BaseCommand):
    help = 'Hitung ulang estimasi waktu pemeriksaan setelah pergeseran jadwal dokter.'

    def add_arguments(self, parser):
        parser.add_argument('--jadwal', type=int, required=True, help='ID JadwalDokterPoli')
        parser.add_argument('--delta', type=int, required=True, help='Pergeseran menit (boleh negatif)')
        parser.add_argument('--tanggal', help='Tanggal kunjungan (YYYY-MM-DD), default hari ini')
        parser.add_argument('--alasan', default='', help='Alasan pergeseran untuk log')
        parser.add_argument('--tanpa-notifikasi', action='store_true', help='Jangan kirim WhatsApp')

    def handle(self, *args, **options):
        if not -240 <= options['delta'] <= 240:
            raise CommandError('Delta harus antara -240 dan 240 menit.')

        try:
            jadwal = JadwalDokterPoli.objects.get(pk=options['jadwal'])
        except JadwalDokterPoli.DoesNotExist as exc:
            raise CommandError(f'Jadwal {options["jadwal"]} tidak ditemukan.') from exc

        tanggal = timezone.localdate()
        if options.get('tanggal'):
            try:
                tanggal = datetime.date.fromisoformat(options['tanggal'])
            except ValueError as exc:
                raise CommandError('Format tanggal harus YYYY-MM-DD.') from exc

        notifier = None if options['tanpa_notifikasi'] else notifier_pergeseran
        perubahan = recompute_for_schedule(
            jadwal, tanggal, options['delta'], alasan=options.get('alasan', ''), notifier=notifier,
        )

        if not perubahan:
            self.stdout.write(self.style.WARNING(
                f'Tidak ada pasien MENUNGGU pada {jadwal.nama_dokter} / {jadwal.get_poliklinik_display()} '
                f'tanggal {tanggal}.'
            ))
            return

        for item in perubahan:
            lama = item['lama'].strftime('%H:%M') if item['lama'] else '--:--'
            baru = item['baru'].strftime('%H:%M') if item['baru'] else '--:--'
            self.stdout.write(
                f"[{item['kunjungan'].nomor_antrean}] {lama} → {baru} "
                f"(versi {item['versi']}, WA {'terkirim' if item['notifikasi'] else 'tidak'})"
            )
        self.stdout.write(self.style.SUCCESS(f'{len(perubahan)} kunjungan dihitung ulang.'))