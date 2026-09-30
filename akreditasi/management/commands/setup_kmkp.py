"""
Setup standar_terkait unit KMKP (Komite/Tim Manajemen Mutu & Keselamatan Pasien)
dan sub-tim-nya sesuai pemetaan 5 kelompok standar STARKES.
"""
from django.core.management.base import BaseCommand

# KMKP = engine mutu RS: penuh PMKP + seluruh SKP + TKRS pengawasan mutu
# + integrasi PPI & MFK
STANDAR_KMKP = {
    'PMKP': ['PMKP 1', 'PMKP 2', 'PMKP 3', 'PMKP 4', 'PMKP 5',
             'PMKP 6', 'PMKP 7', 'PMKP 8', 'PMKP 9', 'PMKP 10'],
    'SKP':  ['SKP 1', 'SKP 2', 'SKP 3', 'SKP 4', 'SKP 5', 'SKP 6'],
    'TKRS': ['TKRS 4', 'TKRS 5', 'TKRS 11'],
    'PPI':  ['PPI 1'],          # integrasi HAIs → laporan mutu (PPI 11 = PPI 1 di DB)
    'MFK':  ['MFK 3'],          # integrasi risk register fasilitas
}

# Sub-Tim Mutu: fokus PMKP + TKRS
STANDAR_MUTU_PEL = {
    'PMKP': ['PMKP 1', 'PMKP 2', 'PMKP 3', 'PMKP 4', 'PMKP 5'],
    'TKRS': ['TKRS 4', 'TKRS 5', 'TKRS 11'],
}

# Sub-Tim Keselamatan Pasien & Risiko: SKP + PMKP insiden + MFK risiko
STANDAR_KP_RISIKO = {
    'SKP':  ['SKP 1', 'SKP 2', 'SKP 3', 'SKP 4', 'SKP 5', 'SKP 6'],
    'PMKP': ['PMKP 6', 'PMKP 7', 'PMKP 8', 'PMKP 9', 'PMKP 10'],
    'MFK':  ['MFK 3'],
}

# Sub-Tim PPI: PPI full + integrasi ke PMKP
STANDAR_PPI_TIM = {
    'PPI':  ['PPI 1', 'PPI 2', 'PPI 3', 'PPI 4', 'PPI 5',
             'PPI 6', 'PPI 7', 'PPI 7.1', 'PPI 8'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}


class Command(BaseCommand):
    help = 'Setup standar_terkait KMKP dan sub-tim mutu (5 kelompok standar)'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        max_order = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 500
        counter = [max_order]

        def next_order():
            counter[0] += 1
            return counter[0]

        def set_standar(code, standar, label=''):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ [{code}] {label or u.name[:45]} → {len(standar)} kelompok")
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

        self.stdout.write(self.style.SUCCESS('\n=== KMKP (Komite/Tim Mutu & Keselamatan Pasien) ==='))

        # ── 1. KMKP L2 (unit utama) ──
        kmkp = set_standar('KMKP', STANDAR_KMKP, 'Tim Manajemen Mutu & Keselamatan Pasien')

        # ── 2. KOM-MUTU (Komite Mutu, duplikat hirearki lain) ──
        set_standar('KOM-MUTU', STANDAR_KMKP, 'Komite Mutu PMKP & Keselamatan Pasien')

        # ── 3. Sub-Tim yang sudah ada ──
        set_standar('MUTU-PEL',  STANDAR_MUTU_PEL, 'Sub-Tim Mutu Pelayanan & Akreditasi')
        set_standar('KP-RISIKO', STANDAR_KP_RISIKO, 'Sub-Tim Keselamatan Pasien & Risiko')
        set_standar('PPI-TIM',   STANDAR_PPI_TIM,  'Sub-Tim PPI')

        # ── 4. Tambah unit L3 khusus akreditasi ──
        if kmkp:
            upsert('TIM-AKREDITASI',   'Tim Akreditasi & Survei STARKES',            3, kmkp, STANDAR_KMKP)
            upsert('TIM-AUDIT-KLINIS', 'Tim Audit Klinis & Manajemen Risiko Klinis', 3, kmkp, STANDAR_KP_RISIKO)

        # ── 5. Reassign akun koordinator.mutu ke KMKP ──
        from django.contrib.auth.models import User
        u = User.objects.filter(username='koordinator.mutu').first()
        if u and kmkp:
            p = getattr(u, 'profile', None)
            if p and p.unit_kerja != kmkp:
                p.unit_kerja = kmkp
                p.save(update_fields=['unit_kerja'])
                self.stdout.write(f"  ✔ koordinator.mutu → unit [{kmkp.code}]")
            else:
                self.stdout.write(f"  ✔ koordinator.mutu sudah di [{kmkp.code}]")

        self.stdout.write(self.style.SUCCESS('\n✅ Setup KMKP selesai!'))
        self.stdout.write('  Kelompok: PMKP (1-10) + SKP (1-6) + TKRS (4,5,11) + PPI (1) + MFK (3)')
