"""
Management command: Setup Instalasi Laboratorium L3 + 2 unit L4 (PK & PA)
dengan pemetaan standar_terkait lengkap 7 kelompok standar.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Setup unit LAB: tambah L4 PK & PA, pemetakan standar_terkait 7 kelompok'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        # ── 1. Rename unit LAB L3 jika perlu ──
        lab = UnitKerja.objects.filter(code='LAB').first()
        if not lab:
            self.stdout.write(self.style.ERROR('Unit LAB tidak ditemukan!'))
            return

        # Rename jadi "Instalasi Laboratorium" (lebih ringkas sebagai L3 payung)
        lab.name = 'Instalasi Laboratorium'
        lab.save()
        self.stdout.write(f'  ✔ L3 [{lab.code}] → {lab.name}')

        # ── 2. Tambah 2 unit L4 ──
        l4_units = [
            {
                'code': 'LAB-PK',
                'name': 'Unit Laboratorium Patologi Klinik',
            },
            {
                'code': 'LAB-PA',
                'name': 'Unit Laboratorium Patologi Anatomi',
            },
        ]

        max_order = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 200
        for i, u_data in enumerate(l4_units):
            u, created = UnitKerja.objects.update_or_create(
                code=u_data['code'],
                defaults={
                    'name': u_data['name'],
                    'level': 4,
                    'parent': lab,
                    'order': max_order + i + 1,
                }
            )
            status = 'dibuat' if created else 'diupdate'
            self.stdout.write(f'  ✔ L4 [{u.code}] {u.name} — {status}')

        # ── 3. Pemetaan standar_terkait (7 kelompok standar) ──
        # Format: {category_code: [list sub_standard yang relevan]}
        standar_lab = {
            # 1. TKRS: Tata Kelola RS (unit lab)
            'TKRS': ['TKRS 9', 'TKRS 10', 'TKRS 11'],
            # 2. PP: Pengasesan Pasien (AP.5 = PP 5, Critical Value = PP 6)
            'PP': ['PP 5', 'PP 6'],
            # 3. SKP: Sasaran Keselamatan Pasien
            'SKP': ['SKP 1', 'SKP 2'],
            # 4. MFK: Manajemen Fasilitas & Keselamatan
            'MFK': ['MFK 4', 'MFK 5', 'MFK 8'],
            # 5. PMKP: Peningkatan Mutu & Keselamatan Pasien
            'PMKP': ['PMKP 4', 'PMKP 7'],
            # 6. KPS: Kualifikasi & Pendidikan Staf
            'KPS': ['KPS 10', 'KPS 12'],
            # 7. PPI: Pencegahan & Pengendalian Infeksi
            'PPI': ['PPI 5', 'PPI 7'],
        }

        # Set standar_terkait di L3 LAB
        lab.standar_terkait = standar_lab
        lab.save()
        self.stdout.write(f'  ✔ L3 [{lab.code}] standar_terkait → {len(standar_lab)} kelompok standar')

        # Set standar_terkait yang sama di kedua L4
        for code in ['LAB-PK', 'LAB-PA']:
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar_lab
                u.save()
                self.stdout.write(f'  ✔ L4 [{u.code}] standar_terkait → {len(standar_lab)} kelompok standar')

        # ── 4. Reassign akun ka.laboratorium ke unit LAB (bukan LAB-BDRS) ──
        from django.contrib.auth.models import User
        from accounts.models import UserProfile

        user_ka = User.objects.filter(username='ka.laboratorium').first()
        if user_ka:
            profile = getattr(user_ka, 'profile', None)
            if profile:
                profile.unit_kerja = lab
                profile.save()
                self.stdout.write(f'  ✔ Akun ka.laboratorium → unit [{lab.code}] {lab.name}')

        self.stdout.write(self.style.SUCCESS('\n✅ Setup Instalasi Laboratorium selesai!'))
