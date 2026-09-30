"""
Setup standar_terkait Instalasi Rekam Medis & Pendaftaran
(7 kelompok standar STARKES).
"""
from django.core.management.base import BaseCommand

STANDAR_RM = {
    'MRMIK': ['MRMIK 1', 'MRMIK 2', 'MRMIK 3', 'MRMIK 4', 'MRMIK 5', 'MRMIK 6', 'MRMIK 7'],
    'ARK':   ['ARK 1', 'ARK 2'],        # Pendaftaran, skrining/triase, admisi
    'HPK':   ['HPK 1', 'HPK 2'],         # Privasi data, general consent
    'SKP':   ['SKP 1'],                  # Identifikasi 2 identitas
    'TKRS':  ['TKRS 9', 'TKRS 11'],      # Pengorganisasian, indikator mutu & risk register
    'KPS':   ['KPS 12'],                 # Kualifikasi PMIK
    'PMKP':  ['PMKP 4', 'PMKP 7'],       # Pelaporan mutu, risiko RM ganda/downtime
}

# Sub-unit khusus pendaftaran/admisi
STANDAR_ADMISI = {
    'ARK':   ['ARK 1', 'ARK 2'],
    'HPK':   ['HPK 1', 'HPK 2'],
    'SKP':   ['SKP 1'],
    'TKRS':  ['TKRS 9'],
    'MRMIK': ['MRMIK 1', 'MRMIK 5'],    # MPI & privasi
}

# Sub-unit coding/RME
STANDAR_CODING = {
    'MRMIK': ['MRMIK 1', 'MRMIK 2', 'MRMIK 3', 'MRMIK 4', 'MRMIK 5', 'MRMIK 6', 'MRMIK 7'],
    'TKRS':  ['TKRS 9', 'TKRS 11'],
}


class Command(BaseCommand):
    help = 'Setup standar_terkait Instalasi Rekam Medis (7 kelompok standar)'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        def set_standar(code, standar, label=''):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ [{code}] {label or u.name[:45]} → {len(standar)} kelompok")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ [{code}] tidak ditemukan"))
            return u

        self.stdout.write(self.style.SUCCESS('\n=== REKAM MEDIS & PENDAFTARAN ==='))

        # ── 1. Unit utama Rekam Medis ──
        set_standar('REKAM-MEDIS', STANDAR_RM, 'Instalasi Rekam Medis & Pendaftaran')
        set_standar('RM',          STANDAR_RM, 'Instalasi RM (duplikat BID-PENJ)')

        # ── 2. Sub-unit L4 ──
        set_standar('ADMISI',                STANDAR_ADMISI, 'Unit Pendaftaran & Admisi')
        set_standar('PENDAFTARAN-ADMISSION',  STANDAR_ADMISI, 'Unit Pendaftaran & Admission')
        set_standar('CODING-RME',            STANDAR_CODING, 'Unit Coding, Indexing & RME')

        # ── 3. Cek akun ka.rekam.medis ──
        from django.contrib.auth.models import User
        rm_unit = UnitKerja.objects.filter(code='REKAM-MEDIS').first()
        u = User.objects.filter(username='ka.rekam.medis').first()
        if u and rm_unit:
            p = getattr(u, 'profile', None)
            if p:
                if p.unit_kerja != rm_unit:
                    p.unit_kerja = rm_unit
                    p.save(update_fields=['unit_kerja'])
                    self.stdout.write(f"  ✔ ka.rekam.medis → [{rm_unit.code}]")
                else:
                    self.stdout.write(f"  ✔ ka.rekam.medis sudah di [{rm_unit.code}]")

        self.stdout.write(self.style.SUCCESS('\n✅ Setup Rekam Medis selesai!'))
        self.stdout.write('  Kelompok: MRMIK (1-7) + ARK (1,2) + HPK (1,2) + SKP (1) + TKRS (9,11) + KPS (12) + PMKP (4,7)')
