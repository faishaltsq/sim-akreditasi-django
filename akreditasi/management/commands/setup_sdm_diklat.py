"""
Setup standar_terkait unit SDM & Diklat: BAG-SDM, SDM, BAG-DIKLIT
dan sub-unitnya (L3, L4), sesuai pemetaan 4 kelompok standar STARKES.
"""
from django.core.management.base import BaseCommand

# Pemetaan standar SDM & Diklat (4 kelompok)
STANDAR_SDM = {
    'KPS':  ['KPS 1', 'KPS 2', 'KPS 3', 'KPS 4', 'KPS 5', 'KPS 6',
             'KPS 7', 'KPS 8', 'KPS 9', 'KPS 10', 'KPS 11', 'KPS 12'],
    'IPKP': ['IPKP 1', 'IPKP 2', 'IPKP 3'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}

# Pemetaan khusus sub-unit kredensial (semua KPS + PMKP)
STANDAR_KREDENSIAL = {
    'KPS':  ['KPS 1', 'KPS 2', 'KPS 3', 'KPS 4', 'KPS 5', 'KPS 6',
             'KPS 7', 'KPS 8', 'KPS 9', 'KPS 10', 'KPS 11', 'KPS 12'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}

# Pemetaan sub-unit diklit (IPKP + KPS pelatihan)
STANDAR_DIKLIT = {
    'IPKP': ['IPKP 1', 'IPKP 2', 'IPKP 3'],
    'KPS':  ['KPS 3', 'KPS 5', 'KPS 6'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'PMKP': ['PMKP 4'],
}


class Command(BaseCommand):
    help = 'Setup standar_terkait unit SDM & Diklat (4 kelompok standar STARKES)'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        max_order = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 400
        counter = [max_order]

        def next_order():
            counter[0] += 1
            return counter[0]

        def set_standar(code, standar, label=None):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ [{code}] {label or u.name[:40]} → {len(standar)} kelompok")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ [{code}] tidak ditemukan"))
            return u

        def upsert(code, name, level, parent, standar):
            u, created = UnitKerja.objects.update_or_create(
                code=code,
                defaults={
                    'name': name, 'level': level, 'parent': parent,
                    'order': next_order(), 'standar_terkait': standar,
                }
            )
            self.stdout.write(f"  {'dibuat' if created else 'diupdate'}: L{level} [{code}] {name}")
            return u

        self.stdout.write(self.style.SUCCESS('\n=== SDM & DIKLAT ==='))

        # ── 1. BAG-SDM (L2) dan sub-unitnya ──
        bag_sdm = set_standar('BAG-SDM', STANDAR_SDM, 'Bagian SDM & Kredensial')
        set_standar('SUB-REKRUTMEN',  STANDAR_KREDENSIAL, 'Subbag Rekrutmen & Administrasi')
        set_standar('SUB-KREDENSIAL', STANDAR_KREDENSIAL, 'Subbag Kredensial & Etika')

        # Tambah L4 di bawah BAG-SDM jika belum ada
        if bag_sdm:
            upsert('UNIT-REKRUTMEN-ADM', 'Unit Rekrutmen, Kontrak & Administrasi Kepegawaian', 3, bag_sdm, STANDAR_KREDENSIAL)
            upsert('UNIT-KREDENSIAL',    'Unit Kredensial & Rekredensial Staf',                3, bag_sdm, STANDAR_KREDENSIAL)
            upsert('UNIT-DIKLAT-SDM',   'Unit Pelatihan & Pengembangan SDM',                  3, bag_sdm, STANDAR_DIKLIT)

        # ── 2. SDM (L2 lama / duplikat) — samakan standar_terkait ──
        set_standar('SDM', STANDAR_SDM, 'Bagian SDM & Diklat (lama)')

        # ── 3. BAG-DIKLIT (L2) dan sub-unitnya ──
        set_standar('BAG-DIKLIT',    STANDAR_SDM,    'Bagian Pendidikan & Penelitian')
        set_standar('SUB-PELATIHAN', STANDAR_DIKLIT, 'Subbag Pelatihan Staf & Pasien')
        set_standar('SUB-LITBANG',   STANDAR_DIKLIT, 'Subbag Penelitian & Pengembangan')

        # ── 4. Reassign akun staf.sdm ke BAG-SDM dan update role ──
        from django.contrib.auth.models import User
        u = User.objects.filter(username='staf.sdm').first()
        if u and bag_sdm:
            p = getattr(u, 'profile', None)
            if p and p.unit_kerja != bag_sdm:
                p.unit_kerja = bag_sdm
                p.save(update_fields=['unit_kerja'])
                self.stdout.write(f"  ✔ staf.sdm → unit [{bag_sdm.code}]")

        self.stdout.write(self.style.SUCCESS('\n✅ Setup SDM & Diklat selesai!'))
        self.stdout.write('  Kelompok: KPS (1-12) + IPKP (1-3) + TKRS (9,11) + PMKP (4,7)')
