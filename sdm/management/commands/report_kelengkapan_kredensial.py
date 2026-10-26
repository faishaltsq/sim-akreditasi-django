"""C-7: read-only coverage report for credential supporting documents."""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from sdm.models import (
    AturanDokumen,
    DokumenSyaratKredensial,
    Pegawai,
    PengajuanKredensial,
)
from sdm.services.kepatuhan import STATE_MISSING, _latest_version

DOMAIN_LABELS = dict(DokumenSyaratKredensial.DOMAIN_CHOICES)


class Command(BaseCommand):
    help = (
        'Read-only coverage report: per-employee supporting-document status for '
        'active credential requests, plus employees whose STR/MCU rules resolve '
        'no current document.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--unit', help='Filter by unit kerja code.')
        parser.add_argument(
            '--jenis', help='Filter by request jenis (AWAL, REKREDENSIAL, PENAMBAHAN).',
        )

    def handle(self, *args, **options):
        unit_code = (options.get('unit') or '').strip()
        jenis = (options.get('jenis') or '').strip()

        requests = PengajuanKredensial.objects.select_related('employee', 'unit_kerja')
        if unit_code:
            requests = requests.filter(unit_kerja__code=unit_code)
        if jenis:
            requests = requests.filter(jenis=jenis)
        requests = requests.filter(status__in=(
            'DIAJUKAN', 'DITINJAU', 'DIREKOMENDASI',
        )).order_by('employee__nama_lengkap')

        self.stdout.write('Kelengkapan Dokumen Pendukung Kredensial')
        self.stdout.write('-' * 96)
        self.stdout.write('Format kolom domain: <terpenuhi>/<total-baris-bukti>')
        header = f'{"Pegawai":32} {"Unit":10} {"Jenis":12} ' + ' '.join(
            f'{label[:10]:>10}' for label in DOMAIN_LABELS.values()
        )
        self.stdout.write(header)
        empty = True
        for app in requests:
            empty = False
            rows = (
                DokumenSyaratKredensial.objects.filter(pengajuan=app)
                .exclude(status='INFO')
                .values('domain')
                .annotate(
                    terpenuhi=Count('pk', filter=Q(status='TERPENUHI')),
                    kurang=Count('pk', filter=Q(status='KURANG')),
                )
            )
            counts = {row['domain']: (row['terpenuhi'], row['kurang']) for row in rows}
            cells = []
            for domain in DOMAIN_LABELS:
                pair = counts.get(domain)
                cells.append(
                    f'{(pair[0] if pair else 0)}/'
                    f'{((pair[0] if pair else 0) + (pair[1] if pair else 0)):>3}'
                )
            self.stdout.write(
                f'{app.employee.nama_lengkap[:32]:32} '
                f'{app.unit_kerja.code[:10]:10} {app.jenis[:12]:12} '
                + ' '.join(f'{cell:>10}' for cell in cells)
            )
        if empty:
            self.stdout.write('Belum ada pengajuan aktif.')

        self.stdout.write('')
        self.stdout.write('Persyaratan tanpa dokumen berlaku (STR/MCU)')
        self.stdout.write('-' * 96)
        rules = AturanDokumen.objects.filter(
            is_active=True, document_type__in=('CREDENTIAL', 'HEALTH'),
            jenis_berkas_wajib__in=('STR', 'MCU'),
        )
        unresolved = []
        for employee in Pegawai.objects.all().only('pk', 'nama_lengkap'):
            for rule in rules:
                if _latest_version(employee, rule) is None:
                    unresolved.append((employee.nama_lengkap, rule.name))
        for name, rule_name in unresolved:
            self.stdout.write(f'{name[:40]:40} — {rule_name}')
        if not unresolved:
            self.stdout.write('Tidak ada.')
