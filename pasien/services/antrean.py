from django.db import transaction
from django.utils import timezone

from pasien.models import AntreanHarianCounter, KunjunganPasien, POLIKLINIK_CHOICES


PREFIX_POLI = {
    'POLI_JANTUNG': 'JTG', 'POLI_PARU': 'PRU', 'POLI_PENYAKIT_DALAM': 'PDL',
    'POLI_BEDAH': 'BDH', 'POLI_ANAK': 'ANK', 'POLI_OBGYN': 'OBG',
    'POLI_MATA': 'MTA', 'POLI_SARAF': 'SRF', 'POLI_THT': 'THT',
    'POLI_GIGI': 'GGI', 'POLI_ORTHO': 'ORT', 'POLI_KULIT': 'KLT',
    'POLI_JIWA': 'JWA', 'REHAB_MEDIK': 'RHB', 'POLI_ENDOKRIN': 'END',
    'POLI_BSARAF': 'BSF', 'POLI_UMUM': 'UMM',
}


def queue_prefix(jenis, poliklinik=''):
    if jenis == 'IGD':
        return 'IGD'
    if poliklinik in PREFIX_POLI:
        return PREFIX_POLI[poliklinik]
    for code, label in POLIKLINIK_CHOICES:
        if poliklinik.casefold() == label.casefold():
            return PREFIX_POLI.get(code, 'POL')
    aliases = {
        'jantung':'JTG', 'paru':'PRU', 'penyakit dalam':'PDL', 'anak':'ANK',
        'bedah':'BDH', 'kandungan':'OBG', 'mata':'MTA', 'saraf':'SRF',
        'gigi':'GGI', 'tht':'THT', 'umum':'UMM',
    }
    for label, prefix in aliases.items():
        if label in poliklinik.casefold():
            return prefix
    return 'POL'


@transaction.atomic
def allocate_queue_number(jenis, poliklinik='', tanggal=None):
    """Reserve a daily ticket independently of the active doctor quota."""
    today = tanggal or timezone.localdate()
    prefix = queue_prefix(jenis, poliklinik)

    def previous_maximum():
        issued = KunjunganPasien.objects.filter(
            tanggal_masuk__date=today, nomor_antrean__startswith=prefix + '-',
        ).values_list('nomor_antrean', flat=True)
        return max((int(number[len(prefix) + 1:]) for number in issued
                    if number[len(prefix) + 1:].isascii() and number[len(prefix) + 1:].isdigit()), default=0)

    counter, _ = AntreanHarianCounter.objects.get_or_create(
        tanggal=today, prefix=prefix, defaults={'nomor_terakhir': previous_maximum},
    )
    counter = AntreanHarianCounter.objects.select_for_update().get(pk=counter.pk)
    counter.nomor_terakhir += 1
    counter.save(update_fields=['nomor_terakhir'])
    return f'{prefix}-{counter.nomor_terakhir:03d}'
