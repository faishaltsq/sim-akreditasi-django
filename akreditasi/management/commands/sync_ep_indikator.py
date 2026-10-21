"""Sinkronisasi massal IndikatorMutu -> Elemen Penilaian (EP).

Menautkan indikator yang belum punya EP ke rekomendasi terbaik, memakai
kaskade: saran kata (Tier B) -> DeepSeek atas katalog penuh (Tier C).

Kaidah keselamatan:
- Link ``ep_sumber='MANUAL'`` TIDAK PERNAH ditimpa (keputusan manusia).
- Hanya tulisan ber-skor tinggi yang dipakai; di bawah itu dibiarkan kosong
  supaya operator memutuskan sendiri.
- Tanpa ``--apply``: dry run (default). Selalu tampilkan apa yang akan berubah.

Ambang batas diturunkan dari pengukuran pada 72 link manual: presisi@1 saran
kata hanya 10% dan tidak ada kombinasi skor/jarak yang memisahkan benar dari
salah (median jarak 0.000 — banyak EP bernilai seri). Karena itu saran kata
tidak boleh dipakai untuk menerapkan otomatis tanpa verifikasi AI.
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from akreditasi import ai_service, ep_sync
from akreditasi.risiko_models import IndikatorMutu
from akreditasi.system_models import SystemConfig


class Command(BaseCommand):
    help = 'Sinkronkan indikator mutu ke EP (dry run tanpa --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Terapkan tautan (dry run tanpa flag ini).')
        parser.add_argument('--limit', type=int, default=0,
                            help='Batasi jumlah indikator yang diproses (0 = semua).')
        parser.add_argument('--kode', type=str, default='',
                            help='Hanya indikator dengan kode ini (atau awalan kode).')
        parser.add_argument('--min-confidence', type=float, default=0.75,
                            help='Ambang confidence AI untuk diterapkan (default 0.75).')
        parser.add_argument('--ai', action='store_true',
                            help='Pakai DeepSeek (Tier C). Tanpa flag: hanya saran kata.')
        parser.add_argument('--throttle', type=float, default=2.0,
                            help='Jeda antar panggilan AI dalam detik (default 2).')
        parser.add_argument('--ulang', action='store_true',
                            help='Nilai ulang tautan yang dibuat otomatis '
                                 '(AI/RULE/LEXICAL). Link MANUAL tetap tidak disentuh.')

    def handle(self, *args, **opts):
        apply_ = opts['apply']
        use_ai = opts['ai']
        min_conf = opts['min_confidence']

        config = SystemConfig.get_solo()
        ai_ok = (use_ai and getattr(config, 'ai_enable_ep_sync', True)
                 and config.ai_enabled)

        # Link manual tidak pernah disentuh, dengan atau tanpa --ulang.
        seleksi = Q(ep_terkait__isnull=True)
        if opts['ulang']:
            seleksi |= Q(ep_terkait__isnull=False,
                         ep_sumber__in=('AI', 'RULE', 'LEXICAL'))
        qs = (IndikatorMutu.objects.filter(seleksi)
              .select_related('unit', 'ep_terkait')
              .order_by('kode_indikator'))
        if opts['kode']:
            qs = qs.filter(kode_indikator__istartswith=opts['kode'])
        if opts['limit']:
            qs = qs[:opts['limit']]

        total = qs.count()
        self.stdout.write(
            f'Indikator belum tertaut: {total} | mode: '
            f'{"APPLY" if apply_ else "DRY RUN"} | '
            f'AI: {"aktif" if ai_ok else "nonaktif (saran kata saja)"} | '
            f'min confidence: {min_conf}')
        if use_ai and not ai_ok:
            self.stdout.write(self.style.WARNING(
                '  --ai diminta tapi AI mati/flag off; jatuh ke saran kata.'))
        if not total:
            self.stdout.write('Tidak ada yang perlu disinkronkan.')
            return

        self.stdout.write('Membangun indeks EP…')
        t0 = time.perf_counter()
        n_ep = len(ep_sync.get_ep_index())
        self.stdout.write(f'  {n_ep} EP siap dalam {(time.perf_counter()-t0)*1000:.0f} ms')

        diterapkan = 0
        dilaporkan = 0
        dilewati = 0
        gagal_ai = 0

        for i, ind in enumerate(qs, 1):
            petunjuk = ''
            boost = ep_sync.rule_boost_map(ind.unit)
            if boost:
                petunjuk = '; '.join(
                    f'{k}: {", ".join(sorted(v))}' for k, v in sorted(boost.items()))

            res = ai_service.generate_ep_rekomendasi(
                user=None, ind=ind, petunjuk_unit=petunjuk) if ai_ok else {
                    'success': True, 'ai_terpakai': False,
                    'data': {'sumber': 'LEXICAL', 'rekomendasi': [{
                        'ep_code': k['code'], 'confidence': float(k['skor']),
                        'alasan': 'saran kata'} for k in ep_sync.lexical_top(ind, n=5)]}}

            if use_ai and not res.get('ai_terpakai'):
                gagal_ai += 1

            rekom = (res.get('data') or {}).get('rekomendasi') or []
            if not rekom:
                dilewati += 1
                continue

            pilih = None
            for r in rekom:
                # Saran kata tidak pernah cukup untuk menulis otomatis.
                if res.get('ai_terpakai') and float(r.get('confidence') or 0) >= min_conf:
                    pilih = r
                    break
            if pilih is None:
                dilaporkan += 1
                self.stdout.write(
                    f'  [{i}/{total}] {ind.kode_indikator} — perlu keputusan operator '
                    f'({len(rekom)} kandidat, confidence tertinggi '
                    f'{max(float(r.get("confidence") or 0) for r in rekom):.2f})')
                continue

            ep = ep_sync.resolve_ep_by_code(pilih['ep_code'])
            if ep is None:
                dilewati += 1
                continue

            self.stdout.write(
                f'  [{i}/{total}] {ind.kode_indikator} -> {ep.code} '
                f'(conf {pilih["confidence"]:.2f}, {pilih.get("alasan", "")[:60]})')
            if apply_:
                ind.ep_terkait = ep
                ind.ep_sumber = 'AI' if res.get('ai_terpakai') else 'LEXICAL'
                ind.ep_skor = round(float(pilih['confidence']), 4)
                ind.save(update_fields=['ep_terkait', 'ep_sumber', 'ep_skor'])
            diterapkan += 1

            if ai_ok and i < total:
                time.sleep(max(0.0, opts['throttle']))

        self.stdout.write('')
        self.stdout.write(
            f'Selesai: {diterapkan} {"ditautkan" if apply_ else "akan ditautkan"} | '
            f'{dilaporkan} perlu keputusan operator | {dilewati} tanpa kandidat | '
            f'{gagal_ai} AI gagal (jatuh ke saran kata)')
        if not apply_ and diterapkan:
            self.stdout.write(self.style.WARNING(
                'Dry run. Jalankan dengan --apply untuk menulis ke database.'))
        elif apply_ and diterapkan:
            self.stdout.write(self.style.SUCCESS(f'{diterapkan} indikator diperbarui.'))
