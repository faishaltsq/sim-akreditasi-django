"""F7.5/F7.7 — seed aturan EP Poli Jantung + indikator PDCA unit.

ADR-7: pemetaan EP adalah **data**. Berkas ini hanya menulis baris
``AturanEpAsesmen``/``AturanEpTindakan`` dan satu ``IndikatorMutu``; tidak ada
kode sub-standar yang dibaca dari Python saat asesmen berjalan.

Dua penjagaan sebelum menulis:

1. Katalog aktif harus STARKES 2024 (800 EP). Bila tidak, perintah berhenti —
   aturan yang menunjuk sub-standar edisi lain akan dibuang senyap oleh
   resolver dan menjadi bukti palsu.
2. Setiap sub-standar yang akan ditulis diperiksa ada di katalog aktif. Bila
   satu saja tidak ada, perintah berhenti dan menyebutkannya; tidak ada baris
   yang ditulis sebagian.

Perintah idempoten: baris dicocokkan lewat kunci alaminya (sub_standar atau
jenis+kode+layanan) lalu diperbarui, bukan digandakan.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akreditasi.models import Framework, StandardItem
from akreditasi.risiko_models import IndikatorMutu
from klinis.models import AturanEpAsesmen, AturanEpTindakan

LAYANAN = 'RAJAL_JANTUNG'
#: ``Framework.version`` memuat tahun instrumen (2024); ``edition`` masih
#: menyimpan label edisi lama sehingga tidak dipakai sebagai penjaga.
EXPECTED_EDITION = '2024'
EXPECTED_EP_COUNT = 800

#: Matriks §6 — setiap baris menunjuk satu sub-standar katalog aktif.
#: Label ditulis ulang dari teks matriks, bukan dari nama sub-standar.
ATURAN_ASESMEN = (
    ('AKP 3', 'CPPT multiprofesi terintegrasi (matriks §6 ARK)'),
    ('AKP 3.1', 'DPJP ditetapkan dan bertanggung jawab atas asuhan'),
    ('AKP 5', 'Kriteria pemulangan + edukasi pasien (matriks §6 ARK)'),
    ('AKP 5.1', 'Ringkasan pasien pulang terdokumentasi di rekam medis'),
    ('AKP 5.4', 'Rujukan sesuai kebutuhan kesinambungan asuhan'),
    ('PP 1.1', 'Pengkajian awal medis & keperawatan <= 24 jam (matriks §6 PP)'),
    ('PP 2', 'Pengkajian ulang oleh DPJP/PPA untuk rencana lanjutan'),
    ('HPK 4.1', 'Informed consent tindakan diagnostik/invasif (matriks §6 HPK)'),
    ('KE 4', 'Edukasi diberikan dengan cara dan bahasa yang mudah dipahami'),
    ('KPS 4', 'Kompetensi PPA disesuaikan dengan kebutuhan pasien'),
    ('PMKP 8', 'Pelaporan & pembelajaran insiden keselamatan (matriks §6 PMKP)'),
    ('SKP 2', 'Komunikasi nilai kritis: tulis–baca–konfirmasi (read-back)'),
    ('SKP 3', 'Obat kewaspadaan tinggi / LASA pada terapi pulang'),
    ('SKP 6', 'Skrining risiko jatuh pasien rawat jalan'),
)

#: Aturan tindakan berlaku untuk **semua** kode di jalur ini (wildcard
#: ``jenis='ANY', kode=''``). Klasifikasi invasif per kode tidak dikarang:
#: master ICD-9 hari ini tidak menandai satu pun kode POLI_JANTUNG sebagai
#: invasif/wajib consent, sehingga aturan per kode akan berarti mengarang.
ATURAN_TINDAKAN = (
    ('ANY', '', 'HPK 4.1', 'Informed consent tindakan diagnostik/invasif', 1),
    ('ANY', '', 'SKP 1', 'Identifikasi pasien sebelum tindakan', 2),
)

#: F7.7 — indikator PDCA unit. Target mewarisi target INM-06 yang sudah
#: terkonfigurasi (matriks tidak memberi angka target persentase).
INDIKATOR_WAKTU_TUNGGU = {
    'kode_indikator': 'IMU-POLJAN-01',
    'nama_indikator': 'Waktu tunggu pelayanan rawat jalan <= 60 menit',
    'jenis': 'IMU',
    'dimensi_mutu': 'TEPAT_WAKTU',
    'numerator': 'Kunjungan POLI-JANTUNG selesai dengan waktu tunggu <= 60 menit',
    'denominator': 'Kunjungan POLI-JANTUNG selesai dengan waktu tunggu terukur',
    'satuan': '%',
    'tipe_pengukuran': 'persen',
    'faktor_pengali': 100,
    'arah_target': 'MIN',
    'pj': 'Kepala Unit Poli Jantung',
}
INM_TARGET_SOURCE = 'INM-06'

#: F7.7 — lapor nilai kritis (matriks §7: <= 30 menit). Target tidak diberikan
#: matriks untuk indikator unit; dipinjam dari target INM-06 yang sudah
#: terkonfigurasi, dengan arah MIN (semakin tinggi kepatuhan semakin baik).
INDIKATOR_NILAI_KRITIS = {
    'kode_indikator': 'IMU-POLJAN-02',
    'nama_indikator': 'Kepatuhan lapor hasil nilai kritis <= 30 menit',
    'jenis': 'IMU',
    'dimensi_mutu': 'TEPAT_WAKTU',
    'numerator': 'Nilai kritis POLI-JANTUNG dilaporkan <= 30 menit sejak ditemukan',
    'denominator': 'Nilai kritis POLI-JANTUNG dengan waktu temuan & pelaporan tercatat',
    'satuan': '%',
    'tipe_pengukuran': 'persen',
    'faktor_pengali': 100,
    'arah_target': 'MIN',
    'pj': 'Kepala Unit Poli Jantung',
}


class Command(BaseCommand):
    help = ('Seed aturan EP STARKES 2024 untuk POLI-JANTUNG dan indikator PDCA '
            'unit (F7.5/F7.7). Idempoten; menolak berjalan bila katalog aktif '
            'bukan edisi 2024 atau ada sub-standar yang tidak dikenal.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Periksa prasyarat dan laporkan rencana tanpa menulis apa pun.',
        )

    def handle(self, *args, **options):
        framework = Framework.objects.filter(is_active=True).first()
        if framework is None:
            raise CommandError('Tidak ada katalog akreditasi aktif.')
        if framework.version != EXPECTED_EDITION:
            raise CommandError(
                f'Katalog aktif versi {framework.version}, bukan {EXPECTED_EDITION}. '
                'Jalankan cutover STARKES 2024 lebih dulu (ADR-7).'
            )
        items = StandardItem.objects.filter(category__framework=framework)
        total = items.count()
        if total != EXPECTED_EP_COUNT:
            raise CommandError(
                f'Katalog aktif memuat {total} EP, bukan {EXPECTED_EP_COUNT}. '
                'Instrumen 2024 belum lengkap; aturan tidak boleh ditulis.'
            )

        needed = {sub for sub, _label in ATURAN_ASESMEN}
        needed |= {sub for _jenis, _kode, sub, _label, _urut in ATURAN_TINDAKAN}
        known = set(items.values_list('sub_standard', flat=True).distinct())
        missing = sorted(needed - known)
        if missing:
            raise CommandError(
                'Sub-standar berikut tidak ada di katalog aktif: ' + ', '.join(missing)
            )

        plan = {
            'framework': f'{framework.name} (versi {framework.version})',
            'ep_count': total,
            'aturan_asesmen': len(ATURAN_ASESMEN),
            'aturan_tindakan': len(ATURAN_TINDAKAN),
            'indikator': [INDIKATOR_WAKTU_TUNGGU['kode_indikator'],
                          INDIKATOR_NILAI_KRITIS['kode_indikator']],
        }
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN — tidak ada yang ditulis.'))
            self.stdout.write(str(plan))
            return

        with transaction.atomic():
            for urutan, (sub, label) in enumerate(ATURAN_ASESMEN, start=1):
                AturanEpAsesmen.objects.update_or_create(
                    sub_standard=sub,
                    defaults={
                        'label': label, 'layanan': LAYANAN,
                        'wajib': True, 'urutan': urutan,
                    },
                )
            for urutan, (jenis, kode, sub, label, order) in enumerate(ATURAN_TINDAKAN, start=1):
                AturanEpTindakan.objects.update_or_create(
                    jenis=jenis, kode=kode, sub_standard=sub, layanan=LAYANAN,
                    defaults={'label': label, 'wajib': True, 'urutan': order},
                )
            unit = self._unit()
            if unit is None:
                raise CommandError(
                    'Unit kerja POLI-JANTUNG belum ada; jalankan seed_poli_jantung_tarif.'
                )
            target = IndikatorMutu.objects.filter(
                kode_indikator=INM_TARGET_SOURCE
            ).values_list('target_nilai', flat=True).first()
            if target is None:
                raise CommandError(
                    f'{INM_TARGET_SOURCE} tidak ada; target indikator unit tidak dapat '
                    'diwarisi dan tidak boleh dikarang.'
                )
            for spec in (INDIKATOR_WAKTU_TUNGGU, INDIKATOR_NILAI_KRITIS):
                IndikatorMutu.objects.update_or_create(
                    kode_indikator=spec['kode_indikator'],
                    defaults={
                        **{k: v for k, v in spec.items() if k != 'kode_indikator'},
                        'unit': unit,
                        'target_nilai': Decimal(target),
                        'aktif': True,
                    },
                )

        plan['aturan_asesmen_total'] = AturanEpAsesmen.objects.filter(layanan=LAYANAN).count()
        plan['aturan_tindakan_total'] = AturanEpTindakan.objects.filter(layanan=LAYANAN).count()
        self.stdout.write(self.style.SUCCESS(str(plan)))

    @staticmethod
    def _unit():
        from akreditasi.models import UnitKerja
        from akreditasi.layanan_unit import POLI_UNIT_CODE

        return UnitKerja.objects.filter(code=POLI_UNIT_CODE['POLI_JANTUNG']).first()
