"""Seed indikator mutu & renstra — dipindah ke 0041.

Migrasi ini dulu menjalankan ``seed_indikator_mutu_renstra`` lewat
``call_command``. Command itu memakai model ``IndikatorMutu`` yang hidup
(model terkini), padahal kolom ``pj`` dan ``rencana_aksi`` baru ditambahkan
oleh migrasi ``0027``. Akibatnya ``migrate`` pada database baru gagal dengan
``no such column: akreditasi_indikatormutu.rencana_aksi``.

Rantai 0022→0028 bersifat linear, jadi dependensi tidak bisa sekadar dipindah
ke 0027 tanpa membentuk siklus (0027 bergantung pada 0026, yang bergantung
pada 0025, yang bergantung pada 0024, yang bergantung pada 0023).

Perbaikannya: migrasi ini dikosongkan, dan seed-nya dijalankan oleh
``0041_seed_indikator_mutu_renstra`` setelah seluruh skema selesai. Nomor dan
dependensinya dipertahankan agar riwayat migrasi di environment lain tidak
berubah.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0022_setup_nakes_lain'),
    ]

    operations = []
