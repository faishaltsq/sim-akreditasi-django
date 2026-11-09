from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from akreditasi.models import UnitKerja
from klinis.data.master_tarif import (
    KELOMPOK,
    KASUS,
    SDKI,
    SLKI,
    SIKI,
    PEMETAAN_3S,
    ATURAN_EP,
    ATURAN_EP_TINDAKAN,
)
from klinis.models import (
    KelompokLayanan,
    MasterIcd10,
    MasterIcd9,
    KasusTersering,
    KasusTindakan,
    SdkiDiagnosis,
    SlkiLuaran,
    SikiIntervensi,
    Pemetaan3S,
    AturanEpAsesmen,
    AturanEpTindakan,
)


class Command(BaseCommand):
    help = 'Seed master katalog klinis (ICD-10, ICD-9, Tarif Umum/BPJS, 3S, dan Aturan EP)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Memulai seeding katalog klinis...'))

        with transaction.atomic():
            # 1. Kelompok Layanan
            kelompok_map = {}
            for kode, nama, unit_code, urutan in KELOMPOK:
                unit = UnitKerja.objects.filter(code=unit_code).first()
                obj, _ = KelompokLayanan.objects.update_or_create(
                    kode=kode,
                    defaults={
                        'nama': nama,
                        'unit_kerja': unit,
                        'urutan': urutan,
                    },
                )
                kelompok_map[kode] = obj
            self.stdout.write(self.style.SUCCESS(f'[OK] KelompokLayanan: {len(kelompok_map)} entri'))

            # 2. Master ICD-10
            icd10_map = {}
            for k in KASUS:
                if k['icd10']:
                    kode_10, nama_10 = k['icd10']
                    if kode_10 not in icd10_map:
                        obj, _ = MasterIcd10.objects.update_or_create(
                            kode=kode_10,
                            defaults={
                                'nama': nama_10,
                                'spesialisasi': k['kelompok'],
                            },
                        )
                        icd10_map[kode_10] = obj
            self.stdout.write(self.style.SUCCESS(f'[OK] MasterIcd10: {len(icd10_map)} entri'))

            # 3. Master ICD-9-CM
            icd9_map = {}
            for k in KASUS:
                for act in k['tindakan']:
                    kode_9, nama_9, _, _, _ = act
                    if kode_9 not in icd9_map:
                        obj, _ = MasterIcd9.objects.update_or_create(
                            kode=kode_9,
                            defaults={
                                'nama': nama_9,
                            },
                        )
                        icd9_map[kode_9] = obj
            self.stdout.write(self.style.SUCCESS(f'[OK] MasterIcd9: {len(icd9_map)} entri'))

            # 4. Kasus Tersering & Kasus Tindakan
            total_kasus = 0
            total_tindakan = 0
            for k in KASUS:
                klp = kelompok_map[k['kelompok']]
                icd10_obj = icd10_map.get(k['icd10'][0]) if k['icd10'] else None

                kasus_obj, _ = KasusTersering.objects.update_or_create(
                    kelompok=klp,
                    urutan=k['urutan'],
                    defaults={
                        'icd10': icd10_obj,
                        'sdki_kode': k['sdki_kode'],
                        'sdki_nama': k['sdki_nama'],
                        'tatalaksana': k['tatalaksana'],
                        'kewenangan': k['kewenangan'],
                        'perlu_verifikasi': k['perlu_verifikasi'],
                        'catatan_sumber': k['catatan_sumber'],
                    },
                )
                total_kasus += 1

                for idx, act in enumerate(k['tindakan']):
                    c9, n9, val_u, val_b, sat = act
                    icd9_obj = icd9_map[c9]
                    t_u = Decimal(val_u) if val_u is not None else None
                    t_b = Decimal(val_b) if val_b is not None else None

                    KasusTindakan.objects.update_or_create(
                        kasus=kasus_obj,
                        icd9=icd9_obj,
                        urutan=idx + 1,
                        defaults={
                            'tarif_umum': t_u,
                            'tarif_bpjs': t_b,
                            'satuan': sat,
                        },
                    )
                    total_tindakan += 1

            self.stdout.write(self.style.SUCCESS(f'[OK] KasusTersering: {total_kasus} entri'))
            self.stdout.write(self.style.SUCCESS(f'[OK] KasusTindakan: {total_tindakan} entri'))

            # 5. Standar 3S (SDKI, SLKI, SIKI, Pemetaan)
            sdki_map = {}
            for kode, nama in SDKI:
                obj, _ = SdkiDiagnosis.objects.update_or_create(kode=kode, defaults={'nama': nama})
                sdki_map[kode] = obj

            slki_map = {}
            for kode, nama in SLKI:
                obj, _ = SlkiLuaran.objects.update_or_create(kode=kode, defaults={'nama': nama})
                slki_map[kode] = obj

            siki_map = {}
            for kode, nama in SIKI:
                obj, _ = SikiIntervensi.objects.update_or_create(kode=kode, defaults={'nama': nama})
                siki_map[kode] = obj

            total_3s = 0
            for d_kode, l_kode, i_kode, prio in PEMETAAN_3S:
                if d_kode in sdki_map and l_kode in slki_map and i_kode in siki_map:
                    Pemetaan3S.objects.update_or_create(
                        sdki=sdki_map[d_kode],
                        slki=slki_map[l_kode],
                        siki=siki_map[i_kode],
                        defaults={'prioritas': prio},
                    )
                    total_3s += 1

            self.stdout.write(self.style.SUCCESS(f'[OK] 3S: SDKI={len(sdki_map)}, SLKI={len(slki_map)}, SIKI={len(siki_map)}, Pemetaan={total_3s}'))

            # 6. Aturan EP Asesmen
            total_ep = 0
            for sub_std, label, wajib, urutan in ATURAN_EP:
                AturanEpAsesmen.objects.update_or_create(
                    sub_standard=sub_std,
                    defaults={
                        'label': label,
                        'wajib': wajib,
                        'urutan': urutan,
                    },
                )
                total_ep += 1

            self.stdout.write(self.style.SUCCESS(f'[OK] AturanEpAsesmen: {total_ep} entri'))

            # 7. Aturan EP per Tindakan
            total_ep_tindakan = 0
            for jenis, kode, sub_std, label, wajib, urutan in ATURAN_EP_TINDAKAN:
                AturanEpTindakan.objects.update_or_create(
                    jenis=jenis, kode=kode, sub_standard=sub_std,
                    defaults={'label': label, 'wajib': wajib, 'urutan': urutan},
                )
                total_ep_tindakan += 1

            self.stdout.write(self.style.SUCCESS(f'[OK] AturanEpTindakan: {total_ep_tindakan} entri'))

        self.stdout.write(self.style.SUCCESS('Selesai! Seluruh master katalog klinis berhasil di-seed.'))
