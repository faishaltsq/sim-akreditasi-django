"""Seed Fase 4 — Extended RS Tipe B units (Dewas, SPI, Komite, Diklit + KSM)."""

from django.core.management.base import BaseCommand
from akreditasi.models import UnitKerja


class Command(BaseCommand):
    help = 'Tambah unit kerja extended RS Tipe B: Dewas, SPI, Komite-komite, Diklit, dan KSM'

    def handle(self, *args, **options):
        created_count = 0

        def goc(code, defaults):
            nonlocal created_count
            obj, created = UnitKerja.objects.get_or_create(code=code, defaults=defaults)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  + {code}: {obj.name}'))
            else:
                self.stdout.write(f'  = {code}: sudah ada')
            return obj

        # ── Level 1 ─────────────────────────────────────────────
        self.stdout.write('\n── Level 1 ──')

        dewas = goc('DEWAS', dict(
            level=1, name='Dewan Pengawas RS',
            pic_name='Prof. Dr. H. Sumarno',
            description='Ketua Dewan Pengawas',
        ))
        spi = goc('SPI', dict(
            level=1, name='Satuan Pengawas Internal',
            pic_name='CPA Arifin, SE, Ak',
            description='Satuan Pengawas Internal RS',
        ))
        komite_rs = goc('KOMITE-RS', dict(
            level=1, name='Komite-komite RS Medis & Non-Medis',
            pic_name='dr. Wahyu Sp.PD',
            description='Induk komite-komite rumah sakit',
        ))
        diklit = goc('DIKLIT', dict(
            level=1, name='Direktorat Pendidikan & Penelitian',
            pic_name='Prof. dr. Eka, Sp.B(K)Onk',
            description='Direktorat Pendidikan dan Penelitian RS',
        ))

        # ── Level 2 ─────────────────────────────────────────────
        self.stdout.write('\n── Level 2 ──')

        # Anak DEWAS
        goc('SEKDEWAS', dict(
            level=2, parent=dewas,
            name='Sekretariat Dewan Pengawas',
            pic_name='', description='Sekretariat Dewan Pengawas RS',
        ))

        # Anak SPI
        goc('AUDIT-OPS', dict(
            level=2, parent=spi,
            name='Audit Operasional & Keuangan',
            pic_name='', description='Sub-unit audit operasional dan keuangan',
        ))
        goc('AUDIT-MED', dict(
            level=2, parent=spi,
            name='Audit Medis & Keselamatan',
            pic_name='', description='Sub-unit audit medis dan keselamatan pasien',
        ))

        # Anak KOMITE-RS
        kom_med = goc('KOM-MED', dict(
            level=2, parent=komite_rs,
            name='Komite Medis',
            pic_name='dr. Drs. Sp.PD-KGH',
            description='Komite Medis RS',
        ))
        goc('KOM-KEP', dict(
            level=2, parent=komite_rs,
            name='Komite Keperawatan',
            pic_name='Ns. Sri Handayani M.Kep',
            description='Komite Keperawatan RS',
        ))
        goc('KOM-MUTU', dict(
            level=2, parent=komite_rs,
            name='Komite Mutu PMKP & Keselamatan Pasien',
            pic_name='drg. Sartika M.Kes',
            description='Komite Peningkatan Mutu dan Keselamatan Pasien',
        ))
        goc('KOM-PPI', dict(
            level=2, parent=komite_rs,
            name='Komite Pencegahan & Pengendalian Infeksi',
            pic_name='dr. Linda Sp.MK',
            description='Komite PPI RS',
        ))
        goc('KOM-ETIK', dict(
            level=2, parent=komite_rs,
            name='Komite Etik & Disiplin Profesi',
            pic_name='dr. H. Mukhlis Sp.OG',
            description='Komite Etik dan Disiplin Profesi RS',
        ))
        goc('KOM-FARMASI', dict(
            level=2, parent=komite_rs,
            name='Komite Farmasi & Terapi',
            pic_name='apt. Dr. Budi M.Farm',
            description='Komite Farmasi dan Terapi (KFT) RS',
        ))

        # Anak DIKLIT
        goc('DIKLAT-STAF', dict(
            level=2, parent=diklit,
            name='Sub-Bag Pelatihan & Pengembangan Staf',
            pic_name='', description='Pelatihan dan pengembangan SDM RS',
        ))
        goc('PENELITIAN', dict(
            level=2, parent=diklit,
            name='Sub-Bag Penelitian & Pengabmas',
            pic_name='', description='Penelitian dan pengabdian masyarakat RS',
        ))

        # ── Level 3 — KSM ───────────────────────────────────────
        self.stdout.write('\n── Level 3 (KSM) ──')

        ksm_list = [
            ('KSM-BEDAH',     'KSM Bedah'),
            ('KSM-PD',        'KSM Penyakit Dalam'),
            ('KSM-ANAK',      'KSM Anak'),
            ('KSM-OBGYN',     'KSM Obstetri & Ginekologi'),
            ('KSM-ANESTESI',  'KSM Anestesi & Terapi Intensif'),
            ('KSM-RADIOLOGI', 'KSM Radiologi'),
            ('KSM-PATKLIN',   'KSM Patologi Klinik'),
            ('KSM-REHAB',     'KSM Rehabilitasi Medik'),
            ('KSM-MATA',      'KSM Mata'),
            ('KSM-THT',       'KSM THT-KL'),
            ('KSM-KULIT',     'KSM Kulit & Kelamin'),
            ('KSM-SARAF',     'KSM Saraf'),
            ('KSM-JIWA',      'KSM Jiwa'),
            ('KSM-GIGI',      'KSM Gigi & Mulut'),
        ]
        for code, name in ksm_list:
            goc(code, dict(
                level=3, parent=kom_med,
                name=name, pic_name='',
                description=f'Kelompok Staf Medis — {name}',
            ))

        # ── Ringkasan ───────────────────────────────────────────
        total = UnitKerja.objects.count()
        self.stdout.write(self.style.WARNING(
            f'\nSelesai: {created_count} unit baru ditambahkan, total {total} unit kerja.'
        ))
