"""
Setup hierarki unit Rawat Inap (L3-L5), Rawat Jalan (L3-L4), IGD (L3-L4)
beserta pemetaan standar_terkait 11 kelompok standar STARKES.
"""
from django.core.management.base import BaseCommand


# ── Pemetaan standar terkait ───────────────────────────────────────────────

# Bangsal Rawat Inap (VIP, Dewasa, Bedah, Anak, Obgyn, Isolasi, ICU, ICCU)
STANDAR_BANGSAL = {
    'IPKP': ['IPKP 1', 'IPKP 2', 'IPKP 3'],          # PPK: MOU diklit, CI, supervisi peserta didik
    'HPK':  ['HPK 1', 'HPK 2'],                        # Privasi, informed consent
    'SKP':  ['SKP 1', 'SKP 2', 'SKP 3', 'SKP 5', 'SKP 6'],  # 5 SKP bangsal
    'PP':   ['PP 1', 'PP 2', 'PP 3', 'PP 4', 'PP 8'], # Asesmen awal, nyeri, gizi, jatuh, CPPT
    'PAP':  ['PAP 1', 'PAP 2', 'PAP 3'],               # Asuhan terintegrasi, EWS
    'PKPO': ['PKPO 4', 'PKPO 6', 'PKPO 7'],            # Verifikasi resep, 7 benar, ESO
    'KE':   ['KE 1', 'KE 4'],                           # Edukasi pasien, discharge planning
    'TKRS': ['TKRS 9', 'TKRS 11'],                      # Kepala ruang, indikator mutu & risk register
    'PPI':  ['PPI 5', 'PPI 7'],                         # Kewaspadaan standar, HAIs
    'MFK':  ['MFK 4', 'MFK 8'],                         # Nurse call/APAR/code blue, kalibrasi alkes
    'KPS':  ['KPS 12'],                                 # STR/SIP/RKK perawat & bidan
}

# IGD — tambahan ARK (skrining, rujukan, transfer pasien)
STANDAR_IGD = {
    **STANDAR_BANGSAL,
    'ARK':  ['ARK 1', 'ARK 2', 'ARK 3'],               # Skrining, triase, transfer/rujukan pasien
}
# IGD tidak pakai IPKP (diklit) karena fokus pelayanan emergensi
STANDAR_IGD.pop('IPKP', None)

# Rawat Jalan — lebih ringkas, tidak ada EWS, tidak ada IPKP bangsal
STANDAR_RAJAL = {
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'HPK':  ['HPK 1', 'HPK 2'],
    'SKP':  ['SKP 1', 'SKP 2', 'SKP 5', 'SKP 6'],
    'PP':   ['PP 1', 'PP 2', 'PP 4'],
    'PAP':  ['PAP 1'],
    'PKPO': ['PKPO 4', 'PKPO 6'],
    'KE':   ['KE 1', 'KE 4'],
    'PPI':  ['PPI 5', 'PPI 7'],
    'MFK':  ['MFK 4', 'MFK 8'],
    'KPS':  ['KPS 12'],
    'ARK':  ['ARK 1', 'ARK 2'],
}


class Command(BaseCommand):
    help = 'Setup unit Rawat Inap L3-L5, Rawat Jalan L3-L4, IGD L3-L4 + standar_terkait'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja

        max_order = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 300
        counter = [max_order]

        def next_order():
            counter[0] += 1
            return counter[0]

        def upsert(code, name, level, parent, standar=None):
            u, created = UnitKerja.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'level': level,
                    'parent': parent,
                    'order': next_order(),
                    'standar_terkait': standar or {},
                }
            )
            action = 'dibuat' if created else 'diupdate'
            self.stdout.write(f"  {'  ' * (level-1)}L{level} [{u.code}] {u.name} — {action}")
            return u

        def set_standar(code, standar):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ standar_terkait [{code}] → {len(standar)} kelompok")
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Unit [{code}] tidak ditemukan"))

        # ══════════════════════════════════════════════════════════════════
        # 1. RAWAT INAP (IRIN L2 → Bangsal L3 → Ruang L4 → Bangsal/Kelas L5)
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS('\n=== RAWAT INAP ==='))

        irin = UnitKerja.objects.filter(code='IRIN').first()
        if irin:
            irin.standar_terkait = STANDAR_BANGSAL
            irin.save(update_fields=['standar_terkait'])
            self.stdout.write(f"  ✔ IRIN (L2) standar_terkait set")

        # L3 bangsal yang sudah ada — set standar_terkait
        for code in ['BANGSAL-VIP', 'BANGSAL-DEWASA', 'BANGSAL-BEDAH',
                     'BANGSAL-ANAK', 'BANGSAL-OBGYN', 'ISOLASI-INFEKSIUS']:
            set_standar(code, STANDAR_BANGSAL)

        # L4 ruang yang sudah ada — set standar_terkait
        for code in ['RUANG-PRIA', 'RUANG-WANITA', 'RUANG-BEDAH-PRIA-WANITA',
                     'RUANG-ANAK-UMUM', 'ISOLASI-ANAK',
                     'RUANG-BERSALIN-VK', 'RUANG-NIFAS', 'RUANG-PERINATOLOGI']:
            set_standar(code, STANDAR_BANGSAL)

        # ── L5: Bangsal VIP ──
        bangsal_vip = UnitKerja.objects.filter(code='BANGSAL-VIP').first()
        if bangsal_vip:
            upsert('RUANG-VIP-SUITE',    'Ruang VIP Suite / Presiden',       5, bangsal_vip, STANDAR_BANGSAL)
            upsert('RUANG-VIP-UTAMA',    'Ruang VIP Utama',                  5, bangsal_vip, STANDAR_BANGSAL)
            upsert('RUANG-VIP-KELAS1',   'Ruang Perawatan Kelas I VIP',      5, bangsal_vip, STANDAR_BANGSAL)

        # ── L5: Ruang Perawatan Pria (di bawah L4) ──
        ruang_pria = UnitKerja.objects.filter(code='RUANG-PRIA').first()
        if ruang_pria:
            upsert('RUANG-PRIA-KELAS2',  'Ruang Perawatan Pria Kelas II',    5, ruang_pria,  STANDAR_BANGSAL)
            upsert('RUANG-PRIA-KELAS3',  'Ruang Perawatan Pria Kelas III',   5, ruang_pria,  STANDAR_BANGSAL)

        # ── L5: Ruang Perawatan Wanita ──
        ruang_wanita = UnitKerja.objects.filter(code='RUANG-WANITA').first()
        if ruang_wanita:
            upsert('RUANG-WANITA-KELAS2', 'Ruang Perawatan Wanita Kelas II',  5, ruang_wanita, STANDAR_BANGSAL)
            upsert('RUANG-WANITA-KELAS3', 'Ruang Perawatan Wanita Kelas III', 5, ruang_wanita, STANDAR_BANGSAL)

        # ── L5: Bangsal Bedah ──
        bedah_rw = UnitKerja.objects.filter(code='RUANG-BEDAH-PRIA-WANITA').first()
        if bedah_rw:
            upsert('RUANG-BEDAH-KELAS1',  'Ruang Bedah Kelas I',              5, bedah_rw, STANDAR_BANGSAL)
            upsert('RUANG-BEDAH-KELAS2',  'Ruang Bedah Kelas II & III',       5, bedah_rw, STANDAR_BANGSAL)

        # ── L5: ICU (dari L3 [ICU] di bawah [INTENSIF]) ──
        icu = UnitKerja.objects.filter(code='ICU').first()
        if icu:
            icu.standar_terkait = STANDAR_BANGSAL
            icu.save(update_fields=['standar_terkait'])
            upsert('BED-ICU-UMUM',        'Area Perawatan ICU Umum',          5, icu, STANDAR_BANGSAL)
            upsert('BED-ICU-ISOLASI',     'Ruang ICU Isolasi (Airborne)',      5, icu, STANDAR_BANGSAL)

        # ── L5: ICCU ──
        iccu = UnitKerja.objects.filter(code='ICCU').first()
        if iccu:
            iccu.standar_terkait = STANDAR_BANGSAL
            iccu.save(update_fields=['standar_terkait'])
            upsert('BED-ICCU-MONITOR',    'Area Pemantauan ICCU (Cardiac Monitor)', 5, iccu, STANDAR_BANGSAL)
            upsert('BED-ICCU-ISOLASI',    'Ruang ICCU Isolasi',                5, iccu, STANDAR_BANGSAL)

        # ── L5: HCU ──
        hcu = UnitKerja.objects.filter(code='HCU').first()
        if hcu:
            hcu.standar_terkait = STANDAR_BANGSAL
            hcu.save(update_fields=['standar_terkait'])
            upsert('BED-HCU-UMUM',        'Area HCU Umum',                    5, hcu, STANDAR_BANGSAL)

        # ── L5: NICU / PICU ──
        nicu = UnitKerja.objects.filter(code='NICU-PICU').first()
        if nicu:
            nicu.standar_terkait = STANDAR_BANGSAL
            nicu.save(update_fields=['standar_terkait'])
            upsert('BED-NICU',            'Area Perawatan NICU (Neonatus)',    5, nicu, STANDAR_BANGSAL)
            upsert('BED-PICU',            'Area Perawatan PICU (Pediatrik)',   5, nicu, STANDAR_BANGSAL)

        # ══════════════════════════════════════════════════════════════════
        # 2. IGD (L2 → Triase/Resusitasi/Observasi L3 → Area kerja L4)
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS('\n=== IGD ==='))

        igd = UnitKerja.objects.filter(code='IGD').first()
        if igd:
            igd.standar_terkait = STANDAR_IGD
            igd.save(update_fields=['standar_terkait'])
            self.stdout.write(f"  ✔ IGD (L2) standar_terkait set")

        for code in ['TRIASE-RESUS', 'TINDAKAN-EMERGENCY', 'OBSERVASI-EMERGENCY']:
            set_standar(code, STANDAR_IGD)

        # L4 di bawah IGD L3
        triase = UnitKerja.objects.filter(code='TRIASE-RESUS').first()
        if triase:
            upsert('AREA-P1',  'Area Merah (P1 – Gawat Darurat)',        4, triase, STANDAR_IGD)
            upsert('AREA-P2',  'Area Kuning (P2 – Urgen)',               4, triase, STANDAR_IGD)
            upsert('AREA-P3',  'Area Hijau (P3 – Non-Urgen)',            4, triase, STANDAR_IGD)

        obs = UnitKerja.objects.filter(code='OBSERVASI-EMERGENCY').first()
        if obs:
            upsert('RUANG-OBS-IGD', 'Ruang Observasi 6-8 Jam IGD',      4, obs, STANDAR_IGD)

        # ══════════════════════════════════════════════════════════════════
        # 3. RAWAT JALAN (L2 IRJ → Poliklinik L3 → Sub-poliklinik L4)
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write(self.style.SUCCESS('\n=== RAWAT JALAN (IRJ) ==='))

        irj = UnitKerja.objects.filter(code='IRJ').first()
        if irj:
            irj.standar_terkait = STANDAR_RAJAL
            irj.save(update_fields=['standar_terkait'])
            self.stdout.write(f"  ✔ IRJ (L2) standar_terkait set")

        # L3 poliklinik yang sudah ada
        for code in ['POLI-PD', 'POLI-BEDAH', 'POLI-ANAK', 'POLI-OBGYN',
                     'POLI-SPESIALIS', 'POLI-GIGI', 'REHAB-MEDIK']:
            set_standar(code, STANDAR_RAJAL)

        # L4 sub-poliklinik
        poli_pd = UnitKerja.objects.filter(code='POLI-PD').first()
        if poli_pd:
            upsert('POLI-JANTUNG',  'Poliklinik Jantung & Pembuluh Darah', 4, poli_pd, STANDAR_RAJAL)
            upsert('POLI-PARU',     'Poliklinik Paru & Respirologi',        4, poli_pd, STANDAR_RAJAL)
            upsert('POLI-ENDOKRIN', 'Poliklinik Endokrin & Metabolik',      4, poli_pd, STANDAR_RAJAL)

        poli_bedah = UnitKerja.objects.filter(code='POLI-BEDAH').first()
        if poli_bedah:
            upsert('POLI-ORTHO',    'Poliklinik Orthopedi & Traumatologi',  4, poli_bedah, STANDAR_RAJAL)
            upsert('POLI-BSARAF',   'Poliklinik Bedah Saraf',               4, poli_bedah, STANDAR_RAJAL)

        poli_spesialis = UnitKerja.objects.filter(code='POLI-SPESIALIS').first()
        if poli_spesialis:
            upsert('POLI-SARAF',    'Poliklinik Neurologi (Saraf)',          4, poli_spesialis, STANDAR_RAJAL)
            upsert('POLI-MATA',     'Poliklinik Mata',                       4, poli_spesialis, STANDAR_RAJAL)
            upsert('POLI-THT',      'Poliklinik THT-KL',                     4, poli_spesialis, STANDAR_RAJAL)
            upsert('POLI-JIWA',     'Poliklinik Jiwa & Psikiatri',           4, poli_spesialis, STANDAR_RAJAL)
            upsert('POLI-KULIT',    'Poliklinik Kulit & Kelamin',            4, poli_spesialis, STANDAR_RAJAL)

        # Set standar_terkait juga untuk RANAP (L3 lama di BID-YAN)
        for code in ['RANAP', 'RAJAL']:
            set_standar(code, STANDAR_BANGSAL if code == 'RANAP' else STANDAR_RAJAL)

        self.stdout.write(self.style.SUCCESS('\n✅ Setup Rawat Inap, IGD, dan Rawat Jalan selesai!'))
        self.stdout.write(f"  Unit L5 dibuat: bangsal VIP, ICU, ICCU, HCU, NICU/PICU")
        self.stdout.write(f"  Unit L4 dibuat: triase IGD (P1/P2/P3), sub-poliklinik")
        self.stdout.write(f"  Standar terkait set di: IRIN, IGD, IRJ + seluruh sub-unit")
