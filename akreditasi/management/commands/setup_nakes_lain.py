"""
Setup Tenaga Kesehatan Lainnya:
1. Tambah 9 EP baru di KPS (KPS 14, 16, 17 masing-masing 3 EP: a, b, c)
2. Buat Unit [KOM-NAKES-LAIN] Komite Tenaga Kesehatan Lainnya (L2) di bawah [KOMITE-RS]
3. Set standar_terkait untuk Komite Nakes Lain (TKRS 10, KPS 14, 16, 17, PMKP 4, 7)
4. Buat / update akun demo ka.komite.nakeslain
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.utils import timezone

KPS_NAKES_LAIN_ITEMS = [
    {
        'sub_standard': 'KPS 14',
        'sub_title': 'Kredensial dan Verifikasi Tenaga Kesehatan Lainnya (PSV)',
        'eps': [
            ('KPS 14 EP 1', 'KPS 14 (EP a): Rumah sakit menetapkan dan menerapkan proses kredensial yang efektif bagi Tenaga Kesehatan Lainnya meliputi pengumpulan, verifikasi, dan evaluasi terhadap kualifikasi staf.'),
            ('KPS 14 EP 2', 'KPS 14 (EP b): Bukti verifikasi keabsahan dokumen kualifikasi (ijazah, STR, SIP, sertifikat pelatihan) dilakukan dari sumber aslinya (Primary Source Verification / PSV) sebelum staf mulai memberikan pelayanan.'),
            ('KPS 14 EP 3', 'KPS 14 (EP c): Rumah sakit melakukan rekredensial secara berkala (sekurang-kurangnya 3 tahun sekali) untuk memperbarui izin dan kewenangan klinis.'),
        ]
    },
    {
        'sub_standard': 'KPS 16',
        'sub_title': 'Surat Penugasan Klinis (SPK) & RKK Tenaga Kesehatan Lainnya',
        'eps': [
            ('KPS 16 EP 1', 'KPS 16 (EP a): Rumah sakit menetapkan Rincian Kewenangan Klinis (RKK) Tenaga Kesehatan Lainnya berdasarkan hasil rekomendasi kredensial dari Komite Tenaga Kesehatan Lainnya.'),
            ('KPS 16 EP 2', 'KPS 16 (EP b): Berdasarkan rekomendasi tersebut, Direktur menetapkan Surat Penugasan Klinis (SPK) dan RKK bagi setiap Tenaga Kesehatan Lainnya.'),
            ('KPS 16 EP 3', 'KPS 16 (EP c): Ada bukti pelaksanaan pelayanan klinis oleh Tenaga Kesehatan Lainnya yang sesuai dengan kewenangan klinis yang diberikan (SPK & RKK tersedia di unit kerja).'),
        ]
    },
    {
        'sub_standard': 'KPS 17',
        'sub_title': 'Evaluasi Kinerja Profesional Berkelanjutan Tenaga Kesehatan Lainnya',
        'eps': [
            ('KPS 17 EP 1', 'KPS 17 (EP a): Rumah sakit melakukan evaluasi kinerja profesional secara berkelanjutan bagi Tenaga Kesehatan Lainnya untuk mempertahankan dan meningkatkan mutu layanan.'),
            ('KPS 17 EP 2', 'KPS 17 (EP b): Penilaian kinerja mencakup partisipasi aktif Tenaga Kesehatan Lainnya dalam program Peningkatan Mutu dan Keselamatan Pasien (PMKP) serta manajemen risiko.'),
            ('KPS 17 EP 3', 'KPS 17 (EP c): Dokumentasi hasil evaluasi kinerja disimpan dalam file kepegawaian/kredensial dan ditindaklanjuti secara berkala.'),
        ]
    },
]

STANDAR_KOM_NAKES_LAIN = {
    'TKRS': ['TKRS 10'],
    'KPS':  ['KPS 14', 'KPS 16', 'KPS 17'],
    'PMKP': ['PMKP 4', 'PMKP 7'],
}


class Command(BaseCommand):
    help = 'Setup Komite Tenaga Kesehatan Lainnya: tambah EP KPS 14/16/17 + Unit L2 + pemetaan standar'

    def handle(self, *args, **options):
        from akreditasi.models import UnitKerja, Category, StandardItem, QualityRecord, Framework
        from django.contrib.auth.models import User
        from accounts.models import UserProfile

        self.stdout.write(self.style.SUCCESS('\n=== TENAGA KESEHATAN LAINNYA (STARKES KMK 1128/2022) ==='))
        # Column-awareness: this command runs before Track C columns
        # (source_ep_code on StandardItem, assessment_state on QualityRecord)
        # exist on fresh databases (migration 0022 before 0052). Detect and
        # fall back to raw SQL so the command still completes.
        from django.db import connection

        def _table_columns(table: str) -> set:
            with connection.cursor() as _cur:
                return {
                    column.name
                    for column in connection.introspection.get_table_description(_cur, table)
                }

        _si_columns = _table_columns(StandardItem._meta.db_table)
        _si_modern = 'source_ep_code' in _si_columns
        _qr_columns = _table_columns(QualityRecord._meta.db_table)
        _qr_modern = 'assessment_state' in _qr_columns

        # ── 1. Tambah StandardItem KPS 14, 16, 17 ──
        cat_kps = Category.objects.filter(code='KPS').first()
        if not cat_kps:
            self.stdout.write(self.style.ERROR('Category KPS tidak ditemukan!'))
            return

        unit_default = UnitKerja.objects.filter(code='BAG-SDM').first() or UnitKerja.objects.first()
        if _si_modern:
            max_order = StandardItem.objects.filter(category=cat_kps).order_by('-order').values_list('order', flat=True).first() or 200
        else:
            with connection.cursor() as _cur:
                _cur.execute(
                    'SELECT "order" FROM akreditasi_standarditem '
                    'WHERE category_id = %s ORDER BY "order" DESC LIMIT 1',
                    [cat_kps.pk],
                )
                _row = _cur.fetchone()
                max_order = _row[0] if _row else 200

        added_eps = 0
        for block in KPS_NAKES_LAIN_ITEMS:
            for ep_code, ep_desc in block['eps']:
                if _si_modern:
                    si, created = StandardItem.objects.update_or_create(
                        code=ep_code,
                        defaults={
                            'category': cat_kps,
                            'sub_standard': block['sub_standard'],
                            'sub_title': block['sub_title'],
                            'description': ep_desc,
                            'order': max_order + added_eps + 1,
                        }
                    )
                else:
                    with connection.cursor() as _cur:
                        _cur.execute(
                            'SELECT id FROM akreditasi_standarditem WHERE code = %s LIMIT 1',
                            [ep_code],
                        )
                        _row = _cur.fetchone()
                        if _row is None:
                            _cur.execute(
                                'INSERT INTO akreditasi_standarditem '
                                '(category_id, sub_standard, sub_title, code, description, "order") '
                                'VALUES (%s, %s, %s, %s, %s, %s)',
                                [cat_kps.pk, block['sub_standard'], block['sub_title'], ep_code, ep_desc, max_order + added_eps + 1],
                            )
                            _cur.execute(
                                'SELECT id FROM akreditasi_standarditem WHERE code = %s LIMIT 1',
                                [ep_code],
                            )
                            _row = _cur.fetchone()
                            created = True
                        else:
                            created = False
                    si = StandardItem(
                        id=_row[0], category=cat_kps,
                        sub_standard=block['sub_standard'], sub_title=block['sub_title'],
                        code=ep_code, description=ep_desc,
                        order=max_order + added_eps + 1,
                    )
                if created:
                    added_eps += 1
                    if _qr_modern:
                        QualityRecord.objects.get_or_create(
                            standard_item=si,
                            defaults={
                                'unit': unit_default,
                                'score': 0,
                            }
                        )
                    else:
                        with connection.cursor() as _cur:
                            _cur.execute(
                                'SELECT id FROM akreditasi_qualityrecord '
                                'WHERE standard_item_id = %s LIMIT 1',
                                [si.id],
                            )
                            if _cur.fetchone() is None:
                                _cur.execute(
                                    'INSERT INTO akreditasi_qualityrecord '
                                    '(standard_item_id, unit_id, score, budget_status, baseline_data, '
                                    'quality_target, risk_mitigation, action_plan, pic, target_date, '
                                    'budget_source, est_cost, eval_notes, updated_at) '
                                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)',
                                    [si.id, unit_default.id, 0, 'DRAFT', '', '', '', '', '', '', '', 0, ''],
                                )
                status = 'dibuat' if created else 'diupdate'
                self.stdout.write(f"  {status}: {ep_code} | {block['sub_standard']}")

        # Update target_ep_count KPS
        if _si_modern:
            actual_kps_count = StandardItem.objects.filter(category=cat_kps).count()
        else:
            with connection.cursor() as _cur:
                _cur.execute(
                    'SELECT COUNT(*) FROM akreditasi_standarditem WHERE category_id = %s',
                    [cat_kps.pk],
                )
                actual_kps_count = _cur.fetchone()[0]
        cat_kps.target_ep_count = actual_kps_count
        cat_kps.save(update_fields=['target_ep_count'])
        self.stdout.write(f"  ✔ KPS target_ep_count diupdate → {actual_kps_count}")

        # ── 2. Buat Unit [KOM-NAKES-LAIN] (L2) di bawah [KOMITE-RS] ──
        komite_parent = UnitKerja.objects.filter(code='KOMITE-RS').first()
        max_order_u = UnitKerja.objects.all().order_by('-order').values_list('order', flat=True).first() or 600

        kom_nakes, created = UnitKerja.objects.update_or_create(
            code='KOM-NAKES-LAIN',
            defaults={
                'name': 'Komite Tenaga Kesehatan Lainnya',
                'level': 2,
                'parent': komite_parent,
                'order': max_order_u + 1,
                'standar_terkait': STANDAR_KOM_NAKES_LAIN,
            }
        )
        self.stdout.write(f"  {'dibuat' if created else 'diupdate'}: Unit [KOM-NAKES-LAIN] level={kom_nakes.level}")

        # ── 3. Buat Sub-Komite L3 (Kredensial, Mutu Profesi, Disiplin & Etik) ──
        sub_komites = [
            ('SUBKOM-KRED-NAKES', 'Subkomite Kredensial Tenaga Kesehatan Lainnya'),
            ('SUBKOM-MUTU-NAKES', 'Subkomite Mutu Profesi Tenaga Kesehatan Lainnya'),
            ('SUBKOM-ETIK-NAKES', 'Subkomite Etika & Disiplin Profesi Nakes Lain'),
        ]
        for i, (sk_code, sk_name) in enumerate(sub_komites):
            sk_unit, sk_created = UnitKerja.objects.update_or_create(
                code=sk_code,
                defaults={
                    'name': sk_name,
                    'level': 3,
                    'parent': kom_nakes,
                    'order': max_order_u + 2 + i,
                    'standar_terkait': STANDAR_KOM_NAKES_LAIN,
                }
            )
            self.stdout.write(f"    {'dibuat' if sk_created else 'diupdate'}: L3 [{sk_code}] {sk_name}")

        # ── 4. Juga update BAG-SDM agar KPS 14, 16, 17 masuk standar_terkait SDM ──
        bag_sdm = UnitKerja.objects.filter(code='BAG-SDM').first()
        if bag_sdm and bag_sdm.standar_terkait:
            st = dict(bag_sdm.standar_terkait)
            kps_list = st.get('KPS', [])
            for s in ['KPS 14', 'KPS 16', 'KPS 17']:
                if s not in kps_list:
                    kps_list.append(s)
            st['KPS'] = kps_list
            bag_sdm.standar_terkait = st
            bag_sdm.save(update_fields=['standar_terkait'])
            self.stdout.write(f"  ✔ BAG-SDM standar_terkait diupdate → KPS 14, 16, 17 dimasukkan")

        # ── 5. Buat Akun Demo ka.komite.nakeslain ──
        user_kn, u_created = User.objects.update_or_create(
            username='ka.komite.nakeslain',
            defaults={
                'first_name': 'Ketua',
                'last_name': 'Komite Nakes Lain',
                'email': 'komite.nakeslain@monsiskami.com',
                'password': make_password('Unit@1234'),
                'is_active': True,
                'is_staff': False,
                'last_login': timezone.now(),
            }
        )
        UserProfile.objects.update_or_create(
            user=user_kn,
            defaults={
                'role': 'KEPALA_UNIT',
                'full_name': 'Ketua Komite Tenaga Kesehatan Lainnya',
                'jabatan': 'Ketua Komite Nakes Lain',
                'unit_kerja': kom_nakes,
                'profesi': 'LAINNYA',
                'is_active_member': True,
            }
        )
        self.stdout.write(f"  {'dibuat' if u_created else 'diupdate'}: Akun ka.komite.nakeslain / Unit@1234")

        self.stdout.write(self.style.SUCCESS('\n✅ Setup Tenaga Kesehatan Lainnya selesai!'))
        self.stdout.write('  9 EP Baru di KPS: KPS 14 (EP a,b,c), KPS 16 (EP a,b,c), KPS 17 (EP a,b,c)')
        self.stdout.write('  Unit: [KOM-NAKES-LAIN] + 3 Subkomite L3')
        self.stdout.write('  Standar: TKRS (10) + KPS (14, 16, 17) + PMKP (4, 7)')
        self.stdout.write('  Akun demo: ka.komite.nakeslain / Unit@1234')
