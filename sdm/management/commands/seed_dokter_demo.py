"""Buat akun demo untuk dokter spesialis jantung yang sudah ada (P4).

Masalah yang diselesaikan: ``seed_staf_medis`` sudah membuat baris ``Pegawai``
untuk enam dokter jantung, tetapi tidak satu pun punya ``User``. Karena
``eligible_dpjp_accounts()`` memfilter ``is_active`` + ``profile.profesi``,
pemilih DPJP kosong dan modul POLI-JANTUNG tidak dapat dipakai sama sekali —
setiap langkah klinis ditolak ADR-11 butir 4.

Perintah ini **tidak membuat baris Pegawai baru**. Ia hanya membuat akun untuk
Pegawai yang belum punya akun, lalu menautkannya lewat ``Pegawai.akun``
(OneToOne yang sudah ada). Nama, NIP, dan proveniensi pegawai tidak diubah;
``data_origin`` tetap ``DEMO`` karena barisnya memang berasal dari seeder.

Akunnya ditandai demo di tiga tempat yang terlihat operator: prefiks username
``demo.dokter.``, domain surel ``@demo.arima.local``, dan sufiks ``(DEMO)``
pada ``UserProfile.full_name`` — nama itu yang muncul di pemilih DPJP.

Idempoten: menjalankan ulang tidak membuat akun kedua.

Jalankan: python manage.py seed_dokter_demo [--password ...] [--dry-run]
"""
import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import Pegawai

#: Unit tempat akun demo ditempatkan. Harus sama dengan unit episode
#: POLI-JANTUNG supaya penugasan DPJP tidak ditolak ``_require_assignable_visit``.
POLI_JANTUNG_UNIT_CODE = 'POLI-JANTUNG'

#: Profesi profil yang lolos ``eligible_dpjp_accounts()``.
PROFESI_PROFIL = 'DOKTER_SPESIALIS'

#: Kata sandi demo yang sengaja mudah dikenali. Tidak dipakai di produksi:
#: akun ini hanya ada di basis data lokal/dev.
DEMO_PASSWORD = 'DemoDokter#2026'

#: Domain surel yang tidak dapat dikirimi surat, supaya tautan reset/pemberitahuan
#: tidak pernah keluar ke alamat nyata dari akun demo.
DEMO_EMAIL_DOMAIN = 'demo.arima.local'
DEMO_USERNAME_PREFIX = 'demo.dokter.'
DEMO_NAME_SUFFIX = ' (DEMO)'

#: Kode master profesi untuk dokter spesialis jantung.
KODE_SPESIALIS_JANTUNG = 'SP_JP'
#: ``SUB_SP`` dipakai bersama subspesialis lain, sehingga gelar pada nama adalah
#: satu-satunya penanda subspesialis jantung pada seed ini
#: ("dr. Wahyu Setiawan, Sp.JP(K)FIHA").
KODE_SUB_SPESIALIS = 'SUB_SP'
GELAR_JANTUNG = 'Sp.JP'

_TITLES = re.compile(r'^(?:prof\.|dr\.|drg\.)\s*', re.IGNORECASE)
_SLUG = re.compile(r'[^a-z0-9]+')

def dokter_jantung_queryset():
    """Pegawai yang benar-benar dokter jantung pada data seed.

    ``SP_JP`` sudah pasti jantung. ``SUB_SP`` dipakai bersama subspesialis lain
    (bedah onkologi, penyakit dalam), jadi gelar ``Sp.JP`` pada nama yang
    memisahkannya. Keduanya adalah pembacaan data yang ada, bukan daftar nama
    yang ditulis ulang di sini.
    """
    return Pegawai.objects.filter(
        profesi_master__code__in=(KODE_SPESIALIS_JANTUNG, KODE_SUB_SPESIALIS),
        nama_lengkap__contains=GELAR_JANTUNG,
    ).order_by('nama_lengkap', 'pk')

def username_for(pegawai):
    """``dr. Bima Sakti Perdana, Sp.JP`` → ``demo.dokter.bima-sakti-perdana``."""
    nama = pegawai.nama_lengkap.split(',')[0]
    nama = _TITLES.sub('', nama.strip())
    slug = _SLUG.sub('-', nama.lower()).strip('-')
    return f'{DEMO_USERNAME_PREFIX}{slug}'

class Command(BaseCommand):
    help = (
        'Buat akun demo untuk dokter jantung yang sudah ada di data Pegawai '
        '(tidak membuat Pegawai baru).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--password', default=DEMO_PASSWORD,
            help=f'Kata sandi akun demo (default: {DEMO_PASSWORD}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Laporkan akun yang akan dibuat tanpa menulis apa pun.',
        )

    def handle(self, *args, **options):
        unit = UnitKerja.objects.filter(code=POLI_JANTUNG_UNIT_CODE).first()
        if unit is None:
            self.stderr.write(self.style.ERROR(
                f'Unit {POLI_JANTUNG_UNIT_CODE} belum ada; jalankan seeder unit '
                'terlebih dahulu. Tidak ada akun yang dibuat.'
            ))
            return

        kandidat = list(dokter_jantung_queryset())
        if not kandidat:
            self.stdout.write(self.style.WARNING(
                'Tidak ada Pegawai dokter jantung. Jalankan '
                '`manage.py seed_staf_medis` lebih dulu.'
            ))
            return

        dibuat, ditautkan, dilewati = [], [], []
        if not options['dry_run']:
            with transaction.atomic():
                for pegawai in kandidat:
                    if pegawai.akun_id is not None:
                        # Sudah punya akun: jangan sentuh. Idempotensi berarti
                        # run kedua tidak membuat akun kedua.
                        if not UserProfile.objects.filter(user_id=pegawai.akun_id).exists():
                            self._ensure_profile(pegawai.akun, pegawai, unit)
                            ditautkan.append(pegawai.akun.username)
                        else:
                            dilewati.append(pegawai.nama_lengkap)
                        continue
                    akun = self._create_account(pegawai, unit, options['password'])
                    pegawai.akun = akun
                    pegawai.save(update_fields=['akun'])
                    dibuat.append((akun.username, pegawai.nama_lengkap))
        else:
            for pegawai in kandidat:
                if pegawai.akun_id is None:
                    dibuat.append((username_for(pegawai), pegawai.nama_lengkap))
                else:
                    dilewati.append(pegawai.nama_lengkap)

        for username, nama in dibuat:
            self.stdout.write(f'  + akun {username} → {nama}')
        for username in ditautkan:
            self.stdout.write(f'  ~ profil dilengkapi untuk akun {username}')
        for nama in dilewati:
            self.stdout.write(f'  = sudah punya akun: {nama}')

        ringkas = (
            f'Selesai. {len(dibuat)} akun demo dibuat, '
            f'{len(ditautkan)} profil dilengkapi, {len(dilewati)} dilewati.'
        )
        if options['dry_run']:
            ringkas = 'Dry-run. ' + ringkas
        self.stdout.write(self.style.SUCCESS(ringkas))
        if dibuat:
            self.stdout.write(
                f'Kata sandi akun demo: {options["password"]} — akun demo, '
                'jangan dipakai di produksi.'
            )

    def _create_account(self, pegawai, unit, password):
        User = get_user_model()
        username = username_for(pegawai)
        akun = User.objects.create_user(
            username=username,
            email=f'{username.removeprefix(DEMO_USERNAME_PREFIX)}@{DEMO_EMAIL_DOMAIN}',
            password=password,
            first_name='',
            last_name='',
            is_active=True,
        )
        self._ensure_profile(akun, pegawai, unit)
        return akun

    def _ensure_profile(self, akun, pegawai, unit):
        """Profil yang memenuhi ``eligible_dpjp_accounts()`` apa adanya.

        Filter itu menuntut ``is_active`` + ``profile.profesi`` dokter; tidak ada
        jalan pintas yang lebih longgar yang dipakai di sini.
        """
        UserProfile.objects.update_or_create(
            user=akun,
            defaults={
                'role': 'STAF_NAKES',
                'profesi': PROFESI_PROFIL,
                'unit_kerja': unit,
                'full_name': f'{pegawai.nama_lengkap}{DEMO_NAME_SUFFIX}',
                'nip_nrp': pegawai.nomor_pegawai or '',
                'jabatan': pegawai.jabatan or pegawai.profesi,
                'is_active_member': True,
            },
        )
        # Proveniensi baris tetap DEMO; ditulis ulang supaya akun yang dibuat
        # untuk baris UNCLASSIFIED pun tidak menyamar sebagai data terverifikasi.
        if pegawai.data_origin != 'DEMO':
            pegawai.data_origin = 'DEMO'
            pegawai.save(update_fields=['data_origin'])
