from django.core.management.base import BaseCommand

from akreditasi.risiko_models import IndikatorMutu

# ponytail: dua sinyal independen untuk arah indikator, bukan satu daftar kata.
#  1) TANDA EKSPRESI — dibaca dari teks target yang sudah tertulis di nama
#     indikator itu sendiri ("(< 1%)", "(>= 95%)", "(0%)") — bukti paling langsung.
#  2) KATA KUNCI — daftar kata lower/higher-is-better berbahasa Indonesia.
# Baris hanya masuk bucket FIX bila KEDUA sinyal sepakat. Bila bertentangan
# (mis. "Angka Keselamatan ... (>= 98%)": kata "angka" mengarah MAX, tanda
# ">=" mengarah MIN) baris masuk bucket KONFLIK dan tidak pernah di-apply
# otomatis — arah ditentukan oleh definisi indikator, bukan oleh heuristik.
LOWER_IS_BETTER = (
    'kejadian', 'angka ', 'insiden', 'infeksi', 'ido', 'isk', 'phlebitis',
    'jatuh', 'dekubitus', 're-admisi', 'readmisi', 'kematian', 'mortalitas',
    'waktu tunggu', 'keterlambatan', 'komplain', 'keluhan', 'kesalahan',
    'error', 'drop out', 'putus obat', 'lost to follow',
)
HIGHER_IS_BETTER = (
    'kepatuhan', 'ketaatan', 'kelengkapan', 'cakupan', 'kepuasan', 'keberhasilan',
)


def arah_dari_tanda(nama):
    """Kembalikan 'MIN' (higher-is-better), 'MAX' (lower-is-better), atau None.

    Urutan urutan penting: '<=' harus diuji sebelum '<'.
    """
    if '\u2265' in nama or '>=' in nama:
        return 'MIN'
    if '\u2264' in nama or '<=' in nama:
        return 'MAX'
    if '<' in nama:
        return 'MAX'
    if '>' in nama:
        return 'MIN'
    # Target eksplisit nol: "Angka Kejadian ... (0%)" = wajib ditekan ke nol.
    if '0%)' in nama:
        return 'MAX'
    return None


def arah_dari_kata(nama):
    """Kembalikan arah dari kata kunci, atau None bila tidak ada/melawan."""
    low = any(k in nama for k in LOWER_IS_BETTER)
    high = any(k in nama for k in HIGHER_IS_BETTER)
    if low and not high:
        return 'MAX'
    if high and not low:
        return 'MIN'
    return None


class Command(BaseCommand):
    help = 'Audit arah_target indikator mutu (read-only). Tidak mengubah data.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Terapkan hanya baris bucket SETUJU (kedua sinyal sepakat).')
        parser.add_argument('--jenis', default='',
                            help='Batasi audit ke satu jenis indikator (mis. NASIONAL).')

    def handle(self, *args, **opts):
        rows = IndikatorMutu.objects.filter(aktif=True).order_by('jenis', 'kode_indikator')
        if opts['jenis']:
            rows = rows.filter(jenis=opts['jenis'])

        setuju, konflik, ragu = [], [], []
        benar = 0
        for ind in rows:
            nama = (ind.nama_indikator or '').lower()
            tanda = arah_dari_tanda(nama)
            kata = arah_dari_kata(nama)

            if tanda is not None and kata is not None and tanda != kata:
                konflik.append((ind, tanda, kata))
            elif tanda is not None or kata is not None:
                desired = tanda if tanda is not None else kata
                if ind.arah_target != desired:
                    setuju.append((ind, desired))
                else:
                    benar += 1
            else:
                ragu.append(ind)

        self.stdout.write(
            f'Total aktif: {rows.count()} | sudah benar: {benar} | '
            f'SETUJU (perlu diubah): {len(setuju)} | KONFLIK (manual): {len(konflik)} | '
            f'RAGU (tanpa sinyal): {len(ragu)}')

        for ind, desired in setuju:
            self.stdout.write(f'  FIX     [{ind.kode_indikator}] {ind.nama_indikator[:70]} '
                              f'arah={ind.arah_target} -> {desired} target={ind.target_nilai}')
        for ind, tanda, kata in konflik:
            self.stdout.write(f'  KONFLIK [{ind.kode_indikator}] {ind.nama_indikator[:70]} '
                              f'tanda={tanda} kata={kata} sekarang={ind.arah_target}')
        for ind in ragu:
            self.stdout.write(f'  RAGU    [{ind.kode_indikator}] {ind.nama_indikator[:70]}')

        if opts['apply'] and setuju:
            targets = []
            for ind, desired in setuju:
                ind.arah_target = desired
                targets.append(ind)
            IndikatorMutu.objects.bulk_update(targets, ['arah_target'])
            self.stdout.write(self.style.SUCCESS(
                f'Diterapkan ke {len(targets)} baris (hanya bucket SETUJU).'))
        elif setuju:
            self.stdout.write(self.style.WARNING(
                'Dry run. Jalankan dengan --apply untuk bucket SETUJU saja.'))
