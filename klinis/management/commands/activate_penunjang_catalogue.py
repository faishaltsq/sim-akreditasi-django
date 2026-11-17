"""Aktivasi katalog penunjang impor agar benar-benar dapat di-order dari IGD."""
import json
from collections import Counter
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akreditasi.models import UnitKerja
from klinis.models import ItemPenunjang

DEFAULT_SIDECAR = Path(__file__).resolve().parents[2] / 'data' / 'penunjang_activation.json'
ALLOWED_PREPARATION = {'fasting', 'pregnancy', 'contrast_allergy', 'specimen', 'site',
                       'region', 'side', 'contrast', 'external_destination'}


class Command(BaseCommand):
    help = 'Aktifkan item katalog penunjang impor: unit tujuan, reviewer dan persiapan wajib.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewer', help='Username peninjau klinis yang dicatat pada setiap item.')
        parser.add_argument('--sidecar', default=str(DEFAULT_SIDECAR), help='Berkas aturan aktivasi (JSON).')
        parser.add_argument('--map', action='append', default=[], metavar='KEY=KODE',
                            help='Ganti kode unit tujuan untuk satu kunci, misal RAD=RAD-01. Dapat diulang.')
        parser.add_argument('--dry-run', action='store_true', help='Tampilkan rencana tanpa menulis.')
        parser.add_argument('--allow-missing', action='store_true',
                            help='Lewati item tanpa aturan dan unit yang tidak ditemukan, bukan berhenti.')

    def handle(self, *args, **options):
        sidecar = self.load_sidecar(options['sidecar'])
        rules = sorted(sidecar['rules'], key=lambda rule: len(rule['prefix']), reverse=True)
        units = self.resolve_units(sidecar, options['map'], options['dry_run'], options['allow_missing'])
        reviewer = self.resolve_reviewer(options['reviewer'], options['dry_run'])

        items = list(ItemPenunjang.objects.select_related('group').order_by('kode'))
        unmatched, skipped, planned = [], [], []
        for item in items:
            rule = next((r for r in rules if item.group.kode.startswith(r['prefix'])), None)
            if rule is None:
                unmatched.append(item.kode)
                continue
            unit = units.get(rule['unit'])
            if unit is None:
                skipped.append(item.kode)
                continue
            unknown = set(rule['required']) - ALLOWED_PREPARATION
            if unknown:
                raise CommandError(f"Aturan {rule['prefix']} memuat kunci persiapan tak dikenal: {sorted(unknown)}")
            planned.append((item, unit, {'required': list(rule['required'])}))
        if unmatched and not options['allow_missing']:
            raise CommandError('Item tanpa aturan aktivasi: ' + ', '.join(unmatched[:20]))
        if skipped and not options['allow_missing']:
            raise CommandError('Unit tujuan tidak ditemukan untuk item: ' + ', '.join(skipped[:20]))

        if options['dry_run']:
            for item, unit, schema in planned:
                self.stdout.write(f"DRY  {item.kode} -> {unit.code} {schema['required']}")
            self.stdout.write(self.style.WARNING(
                f"Dry run: {len(planned)} item akan diaktifkan, {len(unmatched)} tanpa aturan, {len(skipped)} dilewati."))
            return

        activated, failed = 0, []
        with transaction.atomic():
            for item, unit, schema in planned:
                item.destination = unit
                item.reviewed_by = reviewer
                item.active = True
                item.preparation_schema = schema
                if not item.source_version:
                    failed.append((item.kode, 'sumber katalog tidak tercatat'))
                    continue
                try:
                    item.full_clean()
                except ValidationError as exc:
                    failed.append((item.kode, '; '.join(f'{k}: {v[0]}' for k, v in exc.message_dict.items())))
                    continue
                item.save(update_fields=['destination', 'reviewed_by', 'active', 'preparation_schema'])
                activated += 1
            if failed:
                raise CommandError('Aktivasi dibatalkan, item gagal validasi: '
                                   + '; '.join(f'{kode} ({why})' for kode, why in failed[:20]))
        counts = Counter(unit.code for _, unit, _ in planned)
        self.stdout.write(self.style.SUCCESS(f'{activated} item katalog penunjang aktif.'))
        for code, total in sorted(counts.items()):
            self.stdout.write(f'  {code}: {total}')
        if unmatched:
            self.stdout.write(self.style.WARNING(f'{len(unmatched)} item tanpa aturan dilewati: ' + ', '.join(unmatched[:20])))
        if skipped:
            self.stdout.write(self.style.WARNING(f'{len(skipped)} item dilewati karena unit tujuan tidak ada: ' + ', '.join(skipped[:20])))

    def load_sidecar(self, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Berkas aturan aktivasi tidak dapat dibaca: {exc}') from exc
        if not isinstance(data.get('rules'), list) or not data['rules']:
            raise CommandError('Berkas aturan aktivasi tidak memuat daftar rules.')
        if not isinstance(data.get('destination_units'), dict) or not data['destination_units']:
            raise CommandError('Berkas aturan aktivasi tidak memuat destination_units.')
        return data

    def resolve_units(self, sidecar, overrides, dry_run, allow_missing):
        mapping = dict(sidecar['destination_units'])
        for override in overrides:
            if '=' not in override:
                raise CommandError(f'Format --map tidak valid: {override}')
            key, code = override.split('=', 1)
            mapping[key.strip()] = code.strip()
        units, missing = {}, []
        for key, code in mapping.items():
            unit = UnitKerja.objects.filter(code=code).first()
            if unit is None:
                missing.append(f'{key}={code}')
            else:
                units[key] = unit
        if missing and not allow_missing:
            raise CommandError('Unit kerja tujuan tidak ditemukan: ' + ', '.join(missing)
                               + '. Buat unit tersebut atau lewati dengan --map KEY=KODE.')
        if missing:
            self.stdout.write(self.style.WARNING('Unit tidak ditemukan: ' + ', '.join(missing)))
        return units

    def resolve_reviewer(self, username, dry_run):
        if not username:
            if dry_run:
                return None
            raise CommandError('--reviewer wajib diisi: aktivasi mencatat peninjau klinis per item.')
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'Pengguna reviewer tidak ditemukan: {username}')
        return user
