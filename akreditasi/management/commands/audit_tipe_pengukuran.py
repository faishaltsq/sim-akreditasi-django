"""Audit tipe_pengukuran + faktor_pengali (read-only unless --apply).

Menampilkan baris yang akan berubah beserta jumlah CatatanIndikator 2026-nya,
sehingga operator tahu berapa banyak nilai tersimpan yang akan berubah bacaan
setelah --apply. Tanpa --apply: dry run saja.
"""
from django.core.management.base import BaseCommand

from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu

PERSEN = {'%', 'persen', 'percent', ''}
PERMIL = {'‰', 'permil', 'per mil', 'o/oo'}


def proposal(satuan):
    s = (satuan or '').strip()
    if s in PERSEN:
        return 'persen', 100
    if s in PERMIL:
        return 'rate_absolut', 1000
    return 'rate_absolut', 1


class Command(BaseCommand):
    help = 'Audit tipe_pengukuran / faktor_pengali indikator mutu (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Terapkan perubahan (dry run tanpa flag ini).')

    def handle(self, *args, **opts):
        qs = (IndikatorMutu.objects.filter(aktif=True)
              .order_by('jenis', 'kode_indikator'))

        changed, same = [], 0
        for ind in qs:
            tipe, faktor = proposal(ind.satuan)
            if (ind.tipe_pengukuran, ind.faktor_pengali) != (tipe, faktor):
                changed.append((ind, tipe, faktor))
            else:
                same += 1

        total_catatan = (CatatanIndikator.objects.filter(tahun=2026).count())

        self.stdout.write(
            f'Total aktif: {qs.count()} | sudah benar: {same} | '
            f'perlu diperbaiki: {len(changed)}')
        self.stdout.write(f'CatatanIndikator tahun 2026: {total_catatan} baris '
                          f'(nilai tersimpan yang nilainya bisa berubah bacaan)')

        for ind, tipe, faktor in changed:
            n = (CatatanIndikator.objects
                 .filter(indikator=ind, tahun=2026).count())
            self.stdout.write(
                f'  FIX  [{ind.kode_indikator}] {ind.nama_indikator[:60]} '
                f'| satuan={ind.satuan!r} -> {tipe} ×{faktor} | catatan 2026={n}')

        if opts['apply'] and changed:
            for ind, tipe, faktor in changed:
                ind.tipe_pengukuran = tipe
                ind.faktor_pengali = faktor
                ind.save(update_fields=['tipe_pengukuran', 'faktor_pengali'])
            self.stdout.write(self.style.SUCCESS(
                f'Diterapkan ke {len(changed)} baris.'))
        elif changed:
            self.stdout.write(self.style.WARNING(
                'Dry run. Jalankan dengan --apply untuk menerapkan.'))
