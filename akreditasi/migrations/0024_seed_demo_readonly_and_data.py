"""Seed data demo — dipindah ke 0041.

Alasan sama dengan ``0023``: seed ini memanggil management command yang memakai
model hidup, sementara kolom yang dibutuhkannya baru ada setelah ``0027``.
Seed-nya kini dijalankan ``0041_seed_indikator_mutu_renstra`` setelah skema
lengkap.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0023_seed_indikator_mutu_renstra'),
    ]

    operations = []
