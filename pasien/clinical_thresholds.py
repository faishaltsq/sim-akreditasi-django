"""Ambang klinis yang dapat dikonfigurasi — satu tempat, bukan konstanta tersembunyi.

Hanya **satu** ambang di sini: batas normal → hipertensi derajat 1–2. Matriks
spesifikasi tidak menuliskan angka untuk batas itu (AMBIGU-01, §9b), sehingga
nilainya bukan aturan yang bersumber dari dokumen melainkan **default
operasional** yang dipilih produk: 140/90, batas lazim JNC/PERHI.

Keputusan itu dicatat sebagai ADR-14 dengan tiga konsekuensi yang dijaga modul
ini:

1. angka tinggal di satu tempat dan dapat diganti lewat konfigurasi
   (``CLINICAL_HT_SISTOLE`` / ``CLINICAL_HT_DIASTOLE`` di settings atau
   environment) tanpa menyentuh logika kategori;
2. statusnya **belum diratifikasi Komite Medis**, jadi setiap tampilan yang
   memakai ambang ini wajib menyebutkan sumber konfigurasinya
   (``hipertensi_threshold_source()``);
3. ambang yang **berangka pada sumber** — krisis >= 180/120 dan hipotensi
   sistolik < 90 — sengaja **tidak** ada di sini. Angka itu berasal dari
   matriks §9a/§9b, bukan keputusan operasional, sehingga membuatnya
   konfigurabel berarti membuka pintu penyimpangan dari sumber.

Modul ini tidak boleh mengimpor model atau layanan: ia dipanggil dari
``pasien.models`` saat kategori tekanan darah dihitung.
"""
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

#: Kunci konfigurasi. Dibaca dari Django settings lebih dulu (sehingga
#: ``override_settings`` bekerja di tes), lalu environment, lalu default.
SETTING_HT_SISTOLE = 'CLINICAL_HT_SISTOLE'
SETTING_HT_DIASTOLE = 'CLINICAL_HT_DIASTOLE'

#: Default operasional (ADR-14). Bukan angka yang bersumber dari matriks.
DEFAULT_HT_SISTOLE = 140
DEFAULT_HT_DIASTOLE = 90

#: Teks provenance yang wajib ikut tampil di setiap tempat yang memakai ambang
#: ini. Menyebut ADR dan status ratifikasinya, bukan hanya angkanya.
HT_THRESHOLD_ADR = 'ADR-14'
HT_THRESHOLD_STATUS = (
    'default operasional JNC/PERHI, belum diratifikasi Komite Medis'
)

def _read(name, default):
    """Nilai integer dari settings/env; nilai rusak ditolak dengan jelas."""
    raw = getattr(settings, name, None)
    if raw is None:
        raw = os.environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f'{name} harus berupa bilangan bulat positif, bukan {raw!r}.'
        ) from exc
    if value <= 0:
        raise ImproperlyConfigured(
            f'{name} harus bilangan bulat positif, bukan {value}.'
        )
    return value

def hipertensi_thresholds():
    """``(sistole, diastole)`` efektif untuk batas hipertensi derajat 1–2."""
    return _read(SETTING_HT_SISTOLE, DEFAULT_HT_SISTOLE), _read(
        SETTING_HT_DIASTOLE, DEFAULT_HT_DIASTOLE)

def hipertensi_threshold_source():
    """Kalimat provenance untuk ditampilkan bersama kategori hipertensi.

    Menyebut kunci konfigurasi, angka efektif, ADR, dan status ratifikasi —
    supaya pembaca layar/auditor tahu dari mana ambang itu datang dan bahwa
    angka itu masih dapat berubah.
    """
    sistole, diastole = hipertensi_thresholds()
    return (
        f'Ambang hipertensi {sistole}/{diastole} dari '
        f'{SETTING_HT_SISTOLE}/{SETTING_HT_DIASTOLE} '
        f'({HT_THRESHOLD_ADR}: {HT_THRESHOLD_STATUS}).'
    )
