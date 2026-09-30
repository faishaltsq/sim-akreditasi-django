"""
Setup CSSD: tambah sub-standar PPI sterilisasi (PPI 7.2 dst),
set standar_terkait CSSD dan sub-unitnya (5 kelompok standar).
"""
from django.core.management.base import BaseCommand

# Sub-standar PPI sterilisasi yang perlu ditambahkan ke DB
PPI_STERILISASI_ITEMS = [
    {
        'sub_standard': 'PPI 7.2',
        'sub_title': 'Alur Sterilisasi Instrumen Medis (CSSD)',
        'eps': [
            ('PPI 7.2 EP 1', 'Regulasi alur sterilisasi lengkap: penerimaan, dekontaminasi, pencucian, pengeringan, pengemasan, pelabelan, sterilisasi, penyimpanan.'),
            ('PPI 7.2 EP 2', 'Implementasi dan monitoring kepatuhan terhadap alur sterilisasi instrumen medis di seluruh proses CSSD.'),
        ]
    },
    {
        'sub_standard': 'PPI 7.2.1',
        'sub_title': 'Zonasi Fisik CSSD (Kotor/Bersih/Steril)',
        'eps': [
            ('PPI 7.2.1 EP 1', 'Penerapan zonasi fisik CSSD: Zona Kotor (Red), Zona Bersih (Yellow), Zona Steril (Green) dengan batas alur pass-through.'),
            ('PPI 7.2.1 EP 2', 'Pengawasan kepatuhan pemisahan zonasi dan alur satu arah instrumen medis di CSSD.'),
        ]
    },
    {
        'sub_standard': 'PPI 7.2.2',
        'sub_title': 'Pemantauan Indikator & Uji Sterilisasi',
        'eps': [
            ('PPI 7.2.2 EP 1', 'Pemantauan indikator sterilisasi berkala: indikator fisika, kimia internal/eksternal, dan uji biologi/spora.'),
            ('PPI 7.2.2 EP 2', 'Mekanisme penarikan barang steril (recall system) jika terjadi kegagalan sterilisasi beserta dokumentasinya.'),
        ]
    },
    {
        'sub_standard': 'PPI 7.3',
        'sub_title': 'Distribusi & Transportasi Instrumen Steril',
        'eps': [
            ('PPI 7.3 EP 1', 'Regulasi pengelolaan distribusi instrumen steril ke unit pengguna (OK, ICU, Poliklinik, Bangsal) menggunakan wadah tertutup.'),
            ('PPI 7.3 EP 2', 'Monitoring kepatuhan alur transportasi steril dan dokumentasi serah terima instrumen steril.'),
        ]
    },
    {
        'sub_standard': 'PPI 7.3.1',
        'sub_title': 'Regulasi Re-use Peralatan Single-Use',
        'eps': [
            ('PPI 7.3.1 EP 1', 'Regulasi re-use peralatan sekali pakai: proses pembersihan, sterilisasi, batas frekuensi, dan pencatatan pasien.'),
            ('PPI 7.3.1 EP 2', 'Pengawasan kepatuhan dan audit berkala terhadap pelaksanaan re-use peralatan single-use di RS.'),
        ]
    },
]

# Standar CSSD (5 kelompok)
STANDAR_CSSD = {
    'PPI':  ['PPI 7', 'PPI 7.1', 'PPI 7.2', 'PPI 7.2.1', 'PPI 7.2.2', 'PPI 7.3', 'PPI 7.3.1'],
    'TKRS': ['TKRS 9', 'TKRS 11'],
    'MFK':  ['MFK 4', 'MFK 8'],
    'KPS':  ['KPS 12'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}


class Command(BaseCommand):
    help = 'Setup CSSD: tambah EP sterilisasi + pemetaan 5 kelompok standar'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja, Category, StandardItem, QualityRecord, Framework

        self.stdout.write(self.style.SUCCESS('\n=== CSSD (Instalasi Pusat Sterilisasi) ==='))

        # ── 1. Tambah StandardItem PPI sterilisasi ──
        cat_ppi = Category.objects.filter(code='PPI').first()
        framework = Framework.objects.first()
        if not cat_ppi:
            self.stdout.write(self.style.ERROR('Category PPI tidak ditemukan!'))
            return

        max_order = StandardItem.objects.filter(category=cat_ppi).order_by('-order').values_list('order', flat=True).first() or 100

        ep_count = 0
        for item_data in PPI_STERILISASI_ITEMS:
            for ep_code, ep_desc in item_data['eps']:
                si, created = StandardItem.objects.update_or_create(
                    code=ep_code,
                    defaults={
                        'category': cat_ppi,
                        'sub_standard': item_data['sub_standard'],
                        'sub_title': item_data['sub_title'],
                        'description': ep_desc,
                        'order': max_order + ep_count + 1,
                    }
                )
                if created:
                    ep_count += 1
                    # Buat QualityRecord default
                    unit_default = UnitKerja.objects.filter(code='CSSD').first() or UnitKerja.objects.first()
                    QualityRecord.objects.get_or_create(
                        standard_item=si,
                        defaults={
                            'unit': unit_default,
                            'score': 0,
                        }
                    )
                status = 'dibuat' if created else 'sudah ada'
                self.stdout.write(f"  {status}: {ep_code} | {item_data['sub_standard']}")

        self.stdout.write(f"  ✔ {ep_count} EP baru ditambahkan ke PPI")

        # Update target_ep_count di Category PPI
        actual_count = StandardItem.objects.filter(category=cat_ppi).count()
        cat_ppi.target_ep_count = actual_count
        cat_ppi.save(update_fields=['target_ep_count'])
        self.stdout.write(f"  ✔ PPI target_ep_count diupdate → {actual_count}")

        # ── 2. Set standar_terkait unit CSSD ──
        def set_standar(code, standar, label=''):
            u = UnitKerja.objects.filter(code=code).first()
            if u:
                u.standar_terkait = standar
                u.save(update_fields=['standar_terkait'])
                self.stdout.write(f"  ✔ [{code}] {label or u.name[:45]} → {len(standar)} kelompok")
            return u

        set_standar('CSSD', STANDAR_CSSD, 'Instalasi CSSD')
        set_standar('CSSD-LAUNDRY', STANDAR_CSSD, 'CSSD & Laundry (duplikat)')

        # ── 3. Tambah L4 sub-unit CSSD ──
        cssd = UnitKerja.objects.filter(code='CSSD').first()
        max_order_u = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 500

        if cssd:
            l4_units = [
                ('CSSD-DEKONTAM',  'Unit Dekontaminasi & Pencucian (Zona Kotor)'),
                ('CSSD-PACKING',   'Unit Pengemasan & Pelabelan (Zona Bersih)'),
                ('CSSD-STERIL',    'Unit Sterilisasi & Penyimpanan (Zona Steril)'),
                ('CSSD-DISTRIBUSI', 'Unit Distribusi Instrumen Steril'),
            ]
            for i, (code, name) in enumerate(l4_units):
                u, created = UnitKerja.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name, 'level': 4, 'parent': cssd,
                        'order': max_order_u + i + 1,
                        'standar_terkait': STANDAR_CSSD,
                    }
                )
                self.stdout.write(f"  {'dibuat' if created else 'diupdate'}: L4 [{code}] {name}")

        # ── 4. Reassign akun ka.cssd ke unit CSSD jika perlu ──
        from django.contrib.auth.models import User
        u = User.objects.filter(username='ka.cssd').first()
        if u and cssd:
            p = getattr(u, 'profile', None)
            if p and p.unit_kerja != cssd:
                p.unit_kerja = cssd
                p.save(update_fields=['unit_kerja'])
                self.stdout.write(f"  ✔ ka.cssd → unit [{cssd.code}]")
            else:
                self.stdout.write(f"  ✔ ka.cssd sudah di [{cssd.code}]")

        self.stdout.write(self.style.SUCCESS('\n✅ Setup CSSD selesai!'))
        self.stdout.write(f"  PPI: 7 sub-standar (termasuk 5 baru: 7.2, 7.2.1, 7.2.2, 7.3, 7.3.1)")
        self.stdout.write(f"  Total kelompok: PPI + TKRS + MFK + KPS + PMKP")
