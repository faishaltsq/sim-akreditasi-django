"""
Revisi standar_terkait Kamar Operasi (IBS, RUANG-OK, KAMAR-OPERASI, PACU-RECOVERY)
8 kelompok standar sesuai pemetaan STARKES terbaru.
"""
from django.core.management.base import BaseCommand

STANDAR_IBS = {
    'PAB':  ['PAB 1', 'PAB 2', 'PAB 3', 'PAB 4', 'PAB 5', 'PAB 6', 'PAB 7', 'PAB 8', 'PAB 9', 'PAB 10'],
    'SKP':  ['SKP 1', 'SKP 2', 'SKP 4', 'SKP 5'],
    'PPI':  ['PPI 5', 'PPI 7', 'PPI 7.1', 'PPI 7.2', 'PPI 7.3'],
    'HPK':  ['HPK 1'],
    'MFK':  ['MFK 4', 'MFK 8'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'KPS':  ['KPS 9', 'KPS 11'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}

# PACU/Recovery: subset (PAB pemulihan + SKP + PPI + MFK)
STANDAR_PACU = {
    'PAB':  ['PAB 5', 'PAB 6'],
    'SKP':  ['SKP 1', 'SKP 5'],
    'PPI':  ['PPI 5', 'PPI 7'],
    'MFK':  ['MFK 4', 'MFK 8'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'KPS':  ['KPS 9', 'KPS 11'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}


class Command(BaseCommand):
    help = 'Revisi standar_terkait Kamar Operasi (IBS) — 8 kelompok standar'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        def set_standar(code, standar, label=''):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ [{code}] {label or u.name[:50]} → {len(standar)} kelompok")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ [{code}] tidak ditemukan"))
            return u

        self.stdout.write(self.style.SUCCESS('\n=== REVISI KAMAR OPERASI (IBS) ==='))

        # IBS (L2) — induk
        set_standar('IBS', STANDAR_IBS, 'Instalasi Bedah Sentral')
        # RUANG-OK (L3)
        set_standar('RUANG-OK', STANDAR_IBS, 'Unit Kamar Operasi (OK Sentral)')
        # KAMAR-OPERASI (L3) — duplikat
        set_standar('KAMAR-OPERASI', STANDAR_IBS, 'Unit Kamar Operasi (OK)')
        # PACU-RECOVERY (L3)
        set_standar('PACU-RECOVERY', STANDAR_PACU, 'Unit Recovery Room (PACU)')
        # SEK-IGD-BEDAH (L3) — seksi terkait
        set_standar('SEK-IGD-BEDAH', STANDAR_IBS, 'Seksi IGD, Bedah Sentral & Intensif')

        # Pastikan akun ka.kamar.operasi tetap di unit yang benar
        from django.contrib.auth.models import User
        u = User.objects.filter(username='ka.kamar.operasi').first()
        ibs = UnitKerja.objects.filter(code='IBS').first()
        if u and ibs:
            p = getattr(u, 'profile', None)
            if p:
                # Pindahkan dari RUANG-OK ke IBS (L2) agar bisa lihat semua child units
                if p.unit_kerja != ibs:
                    p.unit_kerja = ibs
                    p.save(update_fields=['unit_kerja'])
                    self.stdout.write(f"  ✔ ka.kamar.operasi → [{ibs.code}] L{ibs.level}")
                else:
                    self.stdout.write(f"  ✔ ka.kamar.operasi sudah di [{ibs.code}]")

        self.stdout.write(self.style.SUCCESS('\n✅ Revisi Kamar Operasi selesai!'))
        self.stdout.write('  8 kelompok: PAB(1-10) + SKP(1,2,4,5) + PPI(5,7,7.1-7.3) + HPK(1) + MFK(4,8) + TKRS(9,11) + KPS(9,11) + PMKP(4,7)')
