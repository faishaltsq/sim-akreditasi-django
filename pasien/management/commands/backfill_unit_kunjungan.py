from django.core.management.base import BaseCommand
from akreditasi.models import UnitKerja
from pasien.models import Bed, KunjunganPasien, Ruangan
from pasien.unit_scope import DEFAULT_UNIT_BY_JENIS


class Command(BaseCommand):
    help = 'Backfill unit_kerja pada Ruangan dan KunjunganPasien'

    def handle(self, *args, **options):
        self.stdout.write("Memulai backfill unit_kerja...")

        # 1. Backfill Ruangan.unit_kerja dari Ruangan.jenis
        ruangan_updated = 0
        for r in Ruangan.objects.filter(unit_kerja__isnull=True):
            u = UnitKerja.objects.filter(code=r.jenis).first()
            if u:
                Ruangan.objects.filter(pk=r.pk).update(unit_kerja=u)
                ruangan_updated += 1
        self.stdout.write(f"- Ruangan diperbarui dari jenis: {ruangan_updated}")

        # 2. Backfill KunjunganPasien.unit_kerja dari bed.ruangan.unit_kerja (Presedensi 1)
        kunjungan_bed_updated = 0
        for k in KunjunganPasien.objects.filter(bed__isnull=False, unit_kerja__isnull=True).select_related('bed__ruangan'):
            if k.bed and k.bed.ruangan and k.bed.ruangan.unit_kerja_id:
                KunjunganPasien.objects.filter(pk=k.pk).update(unit_kerja_id=k.bed.ruangan.unit_kerja_id)
                kunjungan_bed_updated += 1
        self.stdout.write(f"- Kunjungan diperbarui dari bed/ruangan: {kunjungan_bed_updated}")

        # 3. Backfill sisa KunjunganPasien dari DEFAULT_UNIT_BY_JENIS (Presedensi 2)
        kunjungan_jenis_updated = 0
        unit_cache = {}
        for k in KunjunganPasien.objects.filter(unit_kerja__isnull=True):
            target_code = DEFAULT_UNIT_BY_JENIS.get(k.jenis_kunjungan)
            if target_code:
                if target_code not in unit_cache:
                    unit_cache[target_code] = UnitKerja.objects.filter(code=target_code).first()
                u = unit_cache[target_code]
                if u:
                    KunjunganPasien.objects.filter(pk=k.pk).update(unit_kerja=u)
                    kunjungan_jenis_updated += 1
        self.stdout.write(f"- Kunjungan diperbarui dari jenis_kunjungan: {kunjungan_jenis_updated}")

        # 4. Laporkan sisa NULL
        sisa_null = KunjunganPasien.objects.filter(unit_kerja__isnull=True).count()
        self.stdout.write(f"- Sisa kunjungan dengan unit_kerja NULL: {sisa_null}")
        self.stdout.write(self.style.SUCCESS("Backfill unit_kerja selesai!"))
