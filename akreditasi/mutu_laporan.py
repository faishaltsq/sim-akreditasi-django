"""Laporan Capaian Indikator Mutu — bulanan, semesteran, tahunan.

Modul terpisah dari ``akreditasi/views.py`` (sudah >2800 baris), mengikuti pola
``indikator_views`` / ``risiko_views``: seluruh logika laporan mutu berada di sini
— kalender pelaporan, snapshot angka, alur verifikasi/persetujuan, dan renderer
cetak/PDF.

Kalender pelaporan (dokumen model BAB I):
  - Laporan bulanan   : maksimum tanggal 10 bulan berikutnya.
  - Laporan semester  : Semester I maksimum 20 Juli, Semester II maksimum
                        20 Januari tahun berikutnya.
  - Laporan tahunan   : maksimum 31 Januari tahun berikutnya.
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .akses_indikator import HOSPITAL_WIDE_ROLES, unit_scope_ids
from .models import AuditLog, RumahSakitProfile, UnitKerja
from .risiko_models import (
    CatatanIndikator, IndikatorMutu, InsidenKeselamatan, LaporanMutu,
    LaporanMutuBaris, LaporanMutuSeksi,
)

__all__ = [
    'batas_waktu_laporan',
    'terlambat_laporan',
    'sisa_hari_laporan',
    'agregat_capaian_rentang',
    'status_tercapai',
    'build_baris',
    'laporan_mutu_daftar',
    'laporan_mutu_create',
    'laporan_mutu_detail',
    'laporan_mutu_simpan_analisis',
    'laporan_mutu_tarik_monev',
    'laporan_mutu_simpan_seksi',
    'monev_per_indikator',
    'isi_analisis_dari_monev',
    'teks_monev_untuk_baris',
    'periode_monev_relevan',
    'rekap_ikp',
    'benchmarking_laporan',
    'tren_indikator',
    'seksi_laporan',
]

BULAN_NAMA = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
              'Agustus', 'September', 'Oktober', 'November', 'Desember']

# Role yang boleh membuat laporan. Isinya identik dengan
# ``akreditasi.views._is_manager_role``; sengaja tidak diimpor dari sana agar
# modul ini tidak menciptakan siklus impor dengan views.py.
ROLE_BOLEH_BUAT = ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA', 'KEPALA_UNIT')

# Role yang selalu memandang seluruh rumah sakit tanpa perlu cek lingkup unit.
ROLE_LINGKUP_RS = ('SUPER_ADMIN', 'ADMIN_RS') + HOSPITAL_WIDE_ROLES

JENIS_LABEL = [
    ('INM', 'Indikator Nasional Mutu (INM)'),
    ('IMRS', 'Indikator Mutu Rumah Sakit (IMRS)'),
    ('IMU', 'Indikator Mutu Unit (IMU)'),
]


def batas_waktu_laporan(jenis, tahun, bulan=None, semester=None):
    """Tanggal batas pelaporan untuk satu periode laporan.

    ``jenis`` mengikuti ``LaporanMutu.JENIS_CHOICES``. Fungsi murni (tanpa
    ketergantungan model) sehingga bisa diuji dan dipakai dari view maupun
    template context.
    """
    if jenis == 'BULANAN':
        if bulan == 12:
            return date(tahun + 1, 1, 10)
        return date(tahun, bulan + 1, 10)
    if jenis == 'SEMESTER':
        # Semester I (Jan–Jun) → 20 Juli tahun sama; Semester II (Jul–Des)
        # → 20 Januari tahun berikutnya.
        return date(tahun, 7, 20) if semester == 1 else date(tahun + 1, 1, 20)
    return date(tahun + 1, 1, 31)  # TAHUNAN


def terlambat_laporan(jenis, tahun, bulan=None, semester=None, hari_ini=None):
    """True bila ``hari_ini`` sudah melewati batas pelaporan."""
    hari_ini = hari_ini or date.today()
    return hari_ini > batas_waktu_laporan(jenis, tahun, bulan, semester)


def sisa_hari_laporan(jenis, tahun, bulan=None, semester=None, hari_ini=None):
    """Selisih hari sampai batas pelaporan; negatif berarti sudah lewat."""
    hari_ini = hari_ini or date.today()
    return (batas_waktu_laporan(jenis, tahun, bulan, semester) - hari_ini).days


# ---------------------------------------------------------------------------
# 2. Perhitungan capaian per periode
# ---------------------------------------------------------------------------

def rentang_bulan(jenis, bulan=None, semester=None):
    """(bulan_awal, bulan_akhir) untuk satu laporan."""
    if jenis == 'BULANAN':
        return (bulan, bulan)
    if jenis == 'SEMESTER':
        return (1, 6) if semester == 1 else (7, 12)
    return (1, 12)


def agregat_capaian_rentang(ind, tahun, bulan_awal, bulan_akhir):
    """Agregat capaian indikator pada rentang bulan tertentu.

    Rumus identik dengan ``IndikatorMutu.agregat_capaian`` (Σ numerator /
    Σ denominator × faktor, bukan rerata persentase bulanan) — hanya rentangnya
    yang dibatasi, sehingga laporan Semester I memakai Jan–Jun dan tidak
    menyertakan bulan yang belum terisi.
    """
    agg = ind.catatan.filter(
        tahun=tahun,
        bulan__gte=bulan_awal,
        bulan__lte=bulan_akhir,
        nilai_denominator__gt=0,
    ).aggregate(num=Sum('nilai_numerator'), den=Sum('nilai_denominator'),
                bulan_terisi=Count('id'))
    num, den = agg['num'], agg['den']
    capaian = None
    if den is not None and den > 0:
        if ind.tipe_pengukuran == 'persen':
            # persen selalu dari literal 100 — faktor_pengali kolom tidak
            # pernah mengubah aritmetika persentase.
            faktor = Decimal('100')
        else:
            faktor = Decimal(str(ind.faktor_pengali or 100))
        capaian = round(float((num / den) * faktor), 2)
    return {
        'num': num,
        'den': den,
        'capaian': capaian,
        'bulan_terisi': agg['bulan_terisi'] or 0,
    }


def status_tercapai(capaian, target, arah):
    """Perbandingan target mengikuti arah indikator.

    MIN → capaian ≥ target (semakin tinggi semakin baik).
    MAX → capaian ≤ target (semakin rendah semakin baik).
    Nilai tanpa data menghasilkan None, bukan False — laporan tidak boleh
    mengklaim "belum tercapai" untuk indikator yang belum diukur.
    """
    if capaian is None:
        return None
    if arah == 'MAX':
        return capaian <= target
    return capaian >= target


def _capaian_bulanan(ind, tahun, bulan):
    """Capaian satu bulan, memakai properti model yang sama dengan dashboard."""
    kosong = {'capaian': None, 'status': None, 'bulan_terisi': 0,
              'num': None, 'den': None}
    if bulan is None:
        return kosong
    try:
        catatan = ind.catatan.get(tahun=tahun, bulan=bulan)
    except CatatanIndikator.DoesNotExist:
        return kosong
    return {
        'capaian': catatan.nilai_capaian,
        # .tercapai sudah menerapkan arah MIN/MAX — jangan dihitung ulang.
        'status': catatan.tercapai,
        'bulan_terisi': 1 if (catatan.nilai_denominator or 0) > 0 else 0,
        'num': catatan.nilai_numerator,
        'den': catatan.nilai_denominator,
    }


# ---------------------------------------------------------------------------
# 2B. Jembatan Monitoring & Evaluasi (RisikoUnit) → analisis laporan
# ---------------------------------------------------------------------------

# RisikoUnit menyimpan periode triwulanan; laporan mutu bulanan harus menarik
# baris triwulan yang memuat bulannya, bukan triwulan lain di tahun yang sama.
TRIWULAN_DARI_BULAN = {
    1: 'TRIWULAN_1', 2: 'TRIWULAN_1', 3: 'TRIWULAN_1',
    4: 'TRIWULAN_2', 5: 'TRIWULAN_2', 6: 'TRIWULAN_2',
    7: 'TRIWULAN_3', 8: 'TRIWULAN_3', 9: 'TRIWULAN_3',
    10: 'TRIWULAN_4', 11: 'TRIWULAN_4', 12: 'TRIWULAN_4',
}


def periode_monev_relevan(jenis, bulan=None, semester=None):
    """Periode MONEV yang relevan untuk satu laporan, urut prioritas.

    Prioritas pertama yang punya baris dipakai; periode di luar rentang laporan
    tidak pernah ditarik supaya angka triwulan lain tidak bocor ke laporan
    bulan yang berbeda.
    """
    if jenis == 'BULANAN':
        return [TRIWULAN_DARI_BULAN.get(bulan, 'TAHUNAN'), 'TAHUNAN']
    if jenis == 'SEMESTER':
        awal = ['TRIWULAN_1', 'TRIWULAN_2'] if semester == 1 else ['TRIWULAN_3', 'TRIWULAN_4']
        return awal + ['TAHUNAN']
    return ['TRIWULAN_1', 'TRIWULAN_2', 'TRIWULAN_3', 'TRIWULAN_4', 'TAHUNAN']


def monev_per_indikator(laporan):
    """Peta ``kode_indikator`` → daftar RisikoUnit (MONEV) yang relevan.

    Dipakai untuk mengisi awal kolom Analisis PDSA & Tindak Lanjut dan untuk
    tombol "Tarik dari MONEV" pada laporan draf. Hanya baris yang indikatornya
    tertaut ke master yang bisa dipetakan — risiko tanpa tautan tidak punya
    kode pembanding.
    """
    from .risiko_models import RisikoUnit

    qs = (RisikoUnit.objects
          .filter(tahun=laporan.tahun, indikator_mutu_terkait__isnull=False)
          .select_related('unit', 'indikator_mutu_terkait')
          .prefetch_related('tindak_lanjut')
          .order_by('-dampak', '-probabilitas', 'id'))
    if laporan.scope == 'UNIT' and laporan.unit_id:
        qs = qs.filter(unit_id__in=unit_scope_ids(laporan.unit))

    per_kode = {}
    for risiko in qs:
        kode = risiko.indikator_mutu_terkait.kode_indikator
        per_kode.setdefault(kode, {}).setdefault(risiko.periode, []).append(risiko)

    prioritas = periode_monev_relevan(laporan.jenis, laporan.bulan, laporan.semester)
    hasil = {}
    for kode, per_periode in per_kode.items():
        for periode in prioritas:
            if per_periode.get(periode):
                hasil[kode] = per_periode[periode]
                break
    return hasil


def _teks_analisis_monev(risiko):
    """Rangkai analisis PDSA dari kolom evaluasi/RCA satu RisikoUnit."""
    bagian = []
    if (risiko.evaluasi_capaian or '').strip():
        bagian.append(f'Evaluasi capaian: {risiko.evaluasi_capaian.strip()}')
    if (risiko.akar_masalah_rca or '').strip():
        bagian.append(f'Akar masalah: {risiko.akar_masalah_rca.strip()}')
    if (risiko.failure_mode_fmea or '').strip():
        bagian.append(f'Mode kegagalan (FMEA): {risiko.failure_mode_fmea.strip()}')
    if (risiko.rca_ulang or '').strip():
        bagian.append(f'RCA lanjutan: {risiko.rca_ulang.strip()}')
    for item in risiko.rca_fishbone_items:
        bagian.append(f'Fishbone — {item["label"]}: {item["text"]}')
    return '\n'.join(bagian)


def _teks_tindak_lanjut_monev(risiko):
    """Rangkai tindak lanjut dari RTL + daftar aksi TindakLanjutRisiko.

    Baris MONEV yang belum punya RTL maupun aksi mengembalikan string kosong —
    tanpa ini, semua indikator yang sekadar punya RisikoUnit akan terisi teks
    "status Belum Dimulai" yang tidak bermakna di laporan.
    """
    aksi = [f'{tl.urutan}) {tl.aksi} [{tl.get_status_aksi_display()}]'
            for tl in risiko.tindak_lanjut.all()]
    rencana = (risiko.rencana_tindak_lanjut or '').strip()
    if not rencana and not aksi:
        return ''

    bagian = []
    if rencana:
        bagian.append(f'RTL: {rencana}')
        jejak = []
        if (risiko.pj_rtl or '').strip():
            jejak.append(f'PJ {risiko.pj_rtl.strip()}')
        if risiko.deadline_rtl:
            jejak.append(f'tenggat {risiko.deadline_rtl:%d/%m/%Y}')
        jejak.append(f'status {risiko.get_status_rtl_display()}')
        bagian.append(' · '.join(jejak))
    if aksi:
        bagian.append('Aksi: ' + '; '.join(aksi))
    return '\n'.join(bagian)


def teks_monev_untuk_baris(risiko_list):
    """(analisis, tindak_lanjut) gabungan untuk satu indikator.

    Beberapa RisikoUnit bisa menunjuk indikator yang sama (mis. risiko klinis
    dan operasional); semuanya digabung agar tidak ada analisis yang hilang.
    """
    analisis = [t for t in (_teks_analisis_monev(r) for r in risiko_list) if t]
    tindak = [t for t in (_teks_tindak_lanjut_monev(r) for r in risiko_list) if t]
    return '\n\n'.join(analisis), '\n\n'.join(tindak)


def isi_analisis_dari_monev(laporan, timpa=False):
    """Isi kolom analisis/tindak lanjut laporan dari MONEV.

    ``timpa=False`` hanya mengisi kolom yang masih kosong, sehingga tulisan
    manual pada draf tidak pernah hilang saat tombol tarik ditekan. Kembalikan
    (jumlah_baris_terisi, jumlah_baris_dilewati).
    """
    peta = monev_per_indikator(laporan)
    terisi = dilewati = 0
    for baris in laporan.baris.all():
        risiko_list = peta.get(baris.kode)
        if not risiko_list:
            continue
        analisis, tindak = teks_monev_untuk_baris(risiko_list)
        if not analisis and not tindak:
            continue
        ubah = []
        if analisis and (timpa or not baris.analisis.strip()):
            baris.analisis = analisis
            ubah.append('analisis')
        if tindak and (timpa or not baris.tindak_lanjut.strip()):
            baris.tindak_lanjut = tindak
            ubah.append('tindak_lanjut')
        if ubah:
            baris.save(update_fields=ubah)
            terisi += 1
        else:
            dilewati += 1
    return terisi, dilewati


def _ringkas_monev(laporan):
    """Ringkasan MONEV untuk halaman detail (tanpa menulis apa pun).

    Template memakainya untuk menandai baris yang punya sumber MONEV, sehingga
    pengguna tahu baris mana yang bisa ditarik sebelum menekan tombol.
    """
    peta = monev_per_indikator(laporan)
    per_kode = {}
    for kode, risiko_list in peta.items():
        analisis, tindak = teks_monev_untuk_baris(risiko_list)
        # RisikoUnit yang belum diisi evaluasi/RTL tidak dianggap sumber:
        # menandainya di laporan hanya menjanjikan data yang tidak ada.
        if not analisis and not tindak:
            continue
        per_kode[kode] = {
            'jumlah_risiko': len(risiko_list),
            'periode': ', '.join(sorted({r.get_periode_display() for r in risiko_list})),
            'ada_analisis': bool(analisis),
            'ada_tindak_lanjut': bool(tindak),
            'pratinjau_analisis': analisis,
            'pratinjau_tindak_lanjut': tindak,
        }
    return {
        'per_kode': per_kode,
        'jumlah_kode': len(per_kode),
        'ada': bool(per_kode),
    }


def tempel_monev_ke_baris(baris_list, ringkasan):
    """Tempel ringkasan MONEV ke tiap baris agar template tak butuh filter dict.

    Template Django tidak bisa mengindeks dict dengan kunci dinamis tanpa
    custom filter; menempelkan atribut di view jauh lebih sederhana dan
    tidak menambah tag library baru.
    """
    per_kode = ringkasan['per_kode']
    for baris in baris_list:
        baris.monev = per_kode.get(baris.kode)
    return baris_list


# ---------------------------------------------------------------------------
# 3. Snapshot angka ke baris laporan
# ---------------------------------------------------------------------------

def indikator_untuk_laporan(laporan):
    """Queryset indikator yang menjadi isi laporan.

    Cakupan rumah sakit memakai seluruh indikator aktif; cakupan unit memakai
    lingkup unit yang sama dengan dashboard (naik 2 level, turun 2 level) supaya
    angka di laporan tidak pernah berbeda dari yang dilihat unit tersebut.
    """
    base = IndikatorMutu.objects.filter(aktif=True)
    if laporan.scope == 'RS':
        return base.select_related('unit', 'ep_terkait')
    return base.filter(
        unit_id__in=unit_scope_ids(laporan.unit)
    ).select_related('unit', 'ep_terkait')


@transaction.atomic
def build_baris(laporan):
    """Bekukan angka periode ke ``LaporanMutuBaris``. Mengembalikan jumlah baris.

    Hanya laporan draf yang boleh dibangun ulang; laporan terverifikasi tidak
    boleh berubah angkanya lagi.
    """
    if not laporan.boleh_ubah:
        return 0

    bulan_awal, bulan_akhir = rentang_bulan(laporan.jenis, laporan.bulan,
                                            laporan.semester)

    # Baris lama dipakai ulang agar analisis + tindak lanjut yang sudah diisi
    # tidak hilang saat dibangun ulang; indikator yang hilang baru dihapus.
    ada = {b.kode: b for b in laporan.baris.all()}
    dipakai = set()
    jumlah = 0

    for urutan, ind in enumerate(indikator_untuk_laporan(laporan), start=1):
        if laporan.jenis == 'BULANAN':
            hitung = _capaian_bulanan(ind, laporan.tahun, bulan_awal)
        else:
            agg = agregat_capaian_rentang(ind, laporan.tahun, bulan_awal, bulan_akhir)
            hitung = {
                'capaian': agg['capaian'],
                'status': status_tercapai(agg['capaian'], ind.target_nilai,
                                          ind.arah_target),
                'bulan_terisi': agg['bulan_terisi'],
                'num': agg['num'],
                'den': agg['den'],
            }
        nilai = {
            'urutan': urutan,
            'indikator': ind,
            'nama': ind.nama_indikator,
            'jenis': ind.jenis_standar,
            'unit_nama': (ind.unit.name if ind.unit else ''),
            'numerator': ind.numerator,
            'denominator': ind.denominator,
            'satuan': ind.satuan or '%',
            'arah': ind.arah_target,
            'target': ind.target_nilai,
            'nilai_capaian': hitung['capaian'],
            'status_tercapai': hitung['status'],
            'bulan_terisi': hitung['bulan_terisi'],
            'nilai_numerator': hitung.get('num'),
            'nilai_denominator': hitung.get('den'),
        }
        baris = ada.get(ind.kode_indikator)
        if baris is None:
            LaporanMutuBaris.objects.create(laporan=laporan,
                                            kode=ind.kode_indikator, **nilai)
        else:
            for nama_field, nilai_field in nilai.items():
                setattr(baris, nama_field, nilai_field)
            baris.save()
        dipakai.add(ind.kode_indikator)
        jumlah += 1

    laporan.baris.exclude(kode__in=list(dipakai)).delete()
    return jumlah


# ---------------------------------------------------------------------------
# 4. Izin
# ---------------------------------------------------------------------------

def _boleh_lapor_unit(user, unit):
    """True bila ``user`` boleh membuat/melihat laporan untuk ``unit``.

    ``unit=None`` berarti cakupan rumah sakit — hanya role lingkup RS yang lolos.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    if p is None:
        return False
    if p.role in ROLE_LINGKUP_RS:
        return True
    if unit is None:
        return False
    if getattr(p, 'is_unit_scoped', False) and p.unit_kerja:
        return unit.pk in unit_scope_ids(p.unit_kerja)
    return p.role in ROLE_BOLEH_BUAT


def _boleh_buat(user, scope):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    if p is None or p.role not in ROLE_BOLEH_BUAT:
        return False
    if scope == 'RS':
        return p.role in ROLE_LINGKUP_RS
    # Cakupan unit: pengelola lingkup RS boleh memilih unit mana pun,
    # unit lain hanya untuk unit miliknya sendiri.
    if p.role in ROLE_LINGKUP_RS:
        return True
    return bool(p.unit_kerja)


def _boleh_lihat(user, laporan):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = getattr(user, 'profile', None)
    if p is None:
        return False
    # ASESOR (L1) hanya menerima laporan yang sudah terbit.
    if p.role == 'ASESOR':
        return laporan.status == 'TERBIT'
    if laporan.scope == 'RS':
        return p.role in ROLE_LINGKUP_RS
    return _boleh_lapor_unit(user, laporan.unit)


def _cek_laporan(user, laporan):
    if not _boleh_lihat(user, laporan):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')


# ---------------------------------------------------------------------------
# 5. View: daftar laporan
# ---------------------------------------------------------------------------

@login_required
def laporan_mutu_daftar(request):
    """Daftar laporan mutu yang boleh dilihat user + sisa hari batas waktu."""
    p = getattr(request.user, 'profile', None)
    boleh_rs = bool(request.user.is_superuser or
                    (p and p.role in ROLE_LINGKUP_RS))

    laporan_list = []
    for laporan in LaporanMutu.objects.select_related(
            'unit', 'pembuat', 'diverifikasi_oleh', 'disetujui_oleh'):
        if not _boleh_lihat(request.user, laporan):
            continue
        laporan_list.append(laporan)  # sisa_hari sudah property model

    return render(request, 'akreditasi/mutu_laporan_daftar.html', {
        'laporan_list': laporan_list,
        'boleh_buat': boleh_rs or _boleh_buat(request.user, 'UNIT'),
        'tahun_sekarang': date.today().year,
    })


# ---------------------------------------------------------------------------
# 6. View: buat laporan
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def laporan_mutu_create(request):
    p = getattr(request.user, 'profile', None)
    unit_awal = p.unit_kerja if p else None
    daftar_unit = UnitKerja.objects.filter(is_active=True).order_by('level', 'name')

    if request.method == 'POST':
        jenis = request.POST.get('jenis', 'BULANAN')
        try:
            tahun = int(request.POST.get('tahun') or date.today().year)
        except (TypeError, ValueError):
            tahun = date.today().year
        bulan = request.POST.get('bulan') or None
        semester = request.POST.get('semester') or None
        try:
            bulan = int(bulan) if bulan else None
            semester = int(semester) if semester else None
        except (TypeError, ValueError):
            bulan = semester = None
        scope = request.POST.get('scope', 'UNIT')

        # Bulan hanya berlaku untuk laporan bulanan, semester hanya untuk
        # laporan semester — dibersihkan agar aturan unik periode bermakna.
        if jenis != 'BULANAN':
            bulan = None
        if jenis != 'SEMESTER':
            semester = None
        if jenis == 'BULANAN' and not bulan:
            messages.warning(request, 'Laporan bulanan wajib memilih bulan.')
            return redirect('akreditasi:laporan_mutu_create')
        if jenis == 'SEMESTER' and not semester:
            messages.warning(request, 'Laporan semester wajib memilih semester.')
            return redirect('akreditasi:laporan_mutu_create')

        if scope == 'UNIT':
            unit_id = request.POST.get('unit') or (unit_awal.pk if unit_awal else None)
            unit = UnitKerja.objects.filter(pk=unit_id).first() if unit_id else None
        else:
            unit = None

        if not _boleh_buat(request.user, scope):
            raise PermissionDenied('Pembuatan laporan untuk cakupan ini tidak diizinkan.')
        if scope == 'UNIT' and not _boleh_lapor_unit(request.user, unit):
            raise PermissionDenied('Unit tersebut di luar lingkup Anda.')

        try:
            laporan = LaporanMutu.objects.create(
                jenis=jenis, tahun=tahun, bulan=bulan, semester=semester,
                scope=scope, unit=unit, pembuat=request.user,
            )
        except ValidationError as exc:
            pesan = '; '.join(
                str(v) for vs in exc.message_dict.values() for v in vs
            ) if hasattr(exc, 'message_dict') else str(exc)
            messages.warning(request, pesan)
        else:
            build_baris(laporan)
            messages.success(request, f'Laporan {laporan.periode_label} dibuat.')
            return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)

    return render(request, 'akreditasi/mutu_laporan_form.html', {
        'daftar_unit': daftar_unit,
        'unit_awal': unit_awal,
        'tahun_sekarang': date.today().year,
        # Pilihan tahun: tahun berjalan + empat tahun ke belakang, cukup untuk
        # laporan susulan tanpa membuka tahun yang datanya tidak ada.
        'tahun_choices': list(range(date.today().year, date.today().year - 5, -1)),
        'bulan_choices': list(enumerate(BULAN_NAMA, start=1)),
        'boleh_rs': bool(request.user.is_superuser or
                         (p and p.role in ROLE_LINGKUP_RS)),
    })


# ---------------------------------------------------------------------------
# 7. View: detail laporan
# ---------------------------------------------------------------------------

def _pj_baris(baris):
    """PJ indikator; kosong bila master belum mengisinya (ditampilkan '—')."""
    if baris.indikator_id:
        return (baris.indikator.pj or '').strip()
    return ''


@login_required
def laporan_mutu_detail(request, pk):
    laporan = get_object_or_404(
        LaporanMutu.objects.select_related('unit', 'pembuat',
                                           'diverifikasi_oleh', 'disetujui_oleh'),
        pk=pk)
    _cek_laporan(request.user, laporan)

    baris = list(laporan.baris.select_related('indikator'))
    baris_per_jenis = [
        (kode, judul, [b for b in baris if b.jenis == kode])
        for kode, judul in JENIS_LABEL
    ]
    # Keterbacaan data master: PJ & EP yang belum diisi ditampilkan sebagai
    # angka di kepala laporan, bukan disembunyikan sebagai sel kosong.
    tanpa_pj = sum(1 for b in baris if not _pj_baris(b))
    tanpa_ep = sum(1 for b in baris
                   if b.indikator_id and b.indikator.ep_terkait_id is None)

    # Tombol aksi hanya muncul bila role & status benar — tombol yang tampil
    # namun selalu 403 justru menipu pengguna.
    role = _role_user(request.user)
    dalam_lingkup = _boleh_lapor_unit(request.user, laporan.unit)
    boleh_verifikasi = (laporan.status == 'DRAF'
                        and role in VERIFIKATOR_L4 and dalam_lingkup)
    boleh_setujui = (
        (laporan.status == 'DIVERIFIKASI' and role in APPROVER_L3) or
        (laporan.status == 'DISETUJUI' and role in APPROVER_L2))

    # Sumber MONEV ditempel ke tiap baris supaya template bisa menandai baris
    # yang punya analisis/tindak lanjut siap tarik.
    monev = _ringkas_monev(laporan)
    tempel_monev_ke_baris(baris, monev)

    return render(request, 'akreditasi/mutu_laporan_detail.html', {
        'laporan': laporan,
        'baris': baris,
        'baris_per_jenis': baris_per_jenis,
        'jumlah_baris': len(baris),
        'jumlah_tercapai': sum(1 for b in baris if b.status_tercapai is True),
        'jumlah_tidak_tercapai': sum(1 for b in baris if b.status_tercapai is False),
        'jumlah_tanpa_data': sum(1 for b in baris if b.status_tercapai is None),
        'tanpa_pj': tanpa_pj,
        'tanpa_ep': tanpa_ep,
        'boleh_ubah': laporan.boleh_ubah and dalam_lingkup,
        'boleh_verifikasi': boleh_verifikasi,
        'boleh_setujui': boleh_setujui,
        'seksi_list': seksi_laporan(laporan),
        'monev': monev,
        'ikp': rekap_ikp(
            laporan.tahun, *rentang_bulan(laporan.jenis, laporan.bulan,
                                          laporan.semester),
            unit=laporan.unit if laporan.scope == 'UNIT' else None),
        'benchmark': tempel_benchmark(baris, benchmarking_laporan(laporan)),
        'tren': tren_indikator(laporan),
    })


@login_required
@require_http_methods(['POST'])
def laporan_mutu_simpan_analisis(request, pk):
    """Simpan analisis PDSA + tindak lanjut, hanya untuk laporan draf.

    Menerima dua bentuk: satu baris (``baris_id``, dipakai tautan lama) atau
    seluruh baris sekaligus (``analisis_<id>`` / ``tindak_lanjut_<id>``) supaya
    satu laporan 210 indikator tidak perlu 210 kali submit.
    """
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)

    if not laporan.boleh_ubah:
        messages.warning(
            request,
            'Laporan sudah diverifikasi — perubahan hanya melalui proses revisi.')
        return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)
    if not _boleh_lapor_unit(request.user, laporan.unit):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')

    if request.POST.get('baris_id'):
        baris_list = [get_object_or_404(LaporanMutuBaris,
                                        pk=request.POST['baris_id'],
                                        laporan=laporan)]
    else:
        # Kunci formulir massal: analisis_<pk> / tindak_lanjut_<pk>.
        id_list = [int(k.rsplit('_', 1)[1]) for k in request.POST
                   if k.startswith('analisis_') and k.rsplit('_', 1)[1].isdigit()]
        baris_list = list(laporan.baris.filter(pk__in=id_list))

    tersimpan = 0
    for baris in baris_list:
        suffix = f'_{baris.pk}'
        analisis = (request.POST.get('analisis' + suffix)
                    if not request.POST.get('baris_id')
                    else request.POST.get('analisis', ''))
        tindak = (request.POST.get('tindak_lanjut' + suffix)
                  if not request.POST.get('baris_id')
                  else request.POST.get('tindak_lanjut', ''))
        baris.analisis = (analisis or '').strip()
        baris.tindak_lanjut = (tindak or '').strip()
        baris.save(update_fields=['analisis', 'tindak_lanjut'])
        tersimpan += 1

    if tersimpan == 1:
        messages.success(request, f'Analisis [{baris_list[0].kode}] tersimpan.')
    else:
        messages.success(request, f'Analisis {tersimpan} indikator tersimpan.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


@login_required
@require_http_methods(['POST'])
def laporan_mutu_tarik_monev(request, pk):
    """Tarik analisis & tindak lanjut dari Monitoring-Evaluasi risiko.

    Hanya laporan draf yang boleh diisi; tombol "timpa" eksplisit diperlukan
    untuk menimpa tulisan manual yang sudah ada di baris.
    """
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)

    if not laporan.boleh_ubah:
        messages.warning(
            request,
            'Laporan sudah diverifikasi — analisis hanya dapat diubah melalui revisi.')
        return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)
    if not _boleh_lapor_unit(request.user, laporan.unit):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')

    timpa = request.POST.get('timpa') == '1'
    terisi, dilewati = isi_analisis_dari_monev(laporan, timpa=timpa)

    if terisi:
        pesan = f'{terisi} baris terisi dari MONEV.'
        if dilewati:
            pesan += f' {dilewati} baris dilewati karena sudah berisi analisis.'
        messages.success(request, pesan)
    elif dilewati:
        messages.info(
            request,
            f'{dilewati} baris sudah berisi analisis. Centang "timpa" untuk '
            'menggantinya dengan data MONEV.')
    else:
        messages.warning(
            request,
            'Tidak ada data Monitoring & Evaluasi yang tertaut ke indikator '
            'pada laporan ini.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


# ---------------------------------------------------------------------------
# 8. Alur verifikasi L4 → L3 → L2 (dokumen BAB I)
# ---------------------------------------------------------------------------

# Pemetaan tingkat pelaporan dokumen (bab: hierarki pelaporan). Database hanya
# menyimpan sampai KEPALA_UNIT — dua tingkat teratas dipetakan ke role
# administrasi yang ada agar rantai tanda tangan tetap utuh di cetakan.
LEVEL_LAPORAN_MUTU = {
    'L5': ('STAF_NAKES',           'Pelaksana / PJ data'),
    'L4': ('KEPALA_UNIT',          'Kepala Unit — verifikator'),
    'L3': ('KOORDINATOR_POKJA',    'Komite Mutu — persetujuan I'),
    'L2': ('ADMIN_RS',             'Direksi — persetujuan II / penerbitan'),
    'L1': ('ASESOR',               'Dewan Pengawas — penerima laporan'),
}

VERIFIKATOR_L4 = ('KEPALA_UNIT', 'KOORDINATOR_POKJA', 'ADMIN_RS', 'SUPER_ADMIN')
APPROVER_L3 = ('KOORDINATOR_POKJA', 'ADMIN_RS', 'SUPER_ADMIN')
APPROVER_L2 = ('ADMIN_RS', 'SUPER_ADMIN')


def _catat(user, aksi, laporan, detail=''):
    """Jejak audit satu transisi status laporan."""
    AuditLog.objects.create(
        user=user, aksi=aksi,
        model_name=laporan.__class__.__name__,
        object_repr=str(laporan)[:250],
        detail=detail,
    )


def _role_user(user):
    p = getattr(user, 'profile', None)
    return p.role if p else ''


@login_required
@require_http_methods(['POST'])
def laporan_mutu_verifikasi(request, pk):
    """L4 — Kepala Unit memverifikasi laporan: DRAF → DIVERIFIKASI."""
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)

    if laporan.status != 'DRAF':
        return HttpResponseBadRequest(
            'Verifikasi hanya untuk laporan berstatus Draf; '
            f'status saat ini {laporan.get_status_display()}.')
    if not _boleh_lapor_unit(request.user, laporan.unit):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')
    if _role_user(request.user) not in VERIFIKATOR_L4:
        raise PermissionDenied('Hanya Kepala Unit / pengelola yang boleh memverifikasi.')

    laporan.status = 'DIVERIFIKASI'
    laporan.diverifikasi_oleh = request.user
    laporan.diverifikasi_pada = timezone.now()
    laporan.catatan_verifikasi = request.POST.get('catatan', '').strip()
    laporan.save(update_fields=['status', 'diverifikasi_oleh', 'diverifikasi_pada',
                                'catatan_verifikasi'])
    _catat(request.user, 'verifikasi', laporan,
           f'DRAF → DIVERIFIKASI ({laporan.periode_label})')
    messages.success(request, f'Laporan {laporan.periode_label} diverifikasi.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


@login_required
@require_http_methods(['POST'])
def laporan_mutu_setujui(request, pk):
    """L3/L2 — persetujuan: DIVERIFIKASI → DISETUJUI → TERBIT.

    Lompatan status (mis. DRAF → TERBIT) ditolak dengan pesan langkah yang
    hilang, bukan exception 500.
    """
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)
    role = _role_user(request.user)

    peta = {
        'DIVERIFIKASI': ('DISETUJUI', APPROVER_L3,
                         'Laporan harus diverifikasi Kepala Unit terlebih dahulu.'),
        'DISETUJUI':    ('TERBIT',    APPROVER_L2,
                         'Laporan harus disetujui Komite Mutu terlebih dahulu.'),
    }
    if laporan.status not in peta:
        return HttpResponseBadRequest(
            f'Tidak ada langkah persetujuan dari status {laporan.get_status_display()}.')
    if role not in peta[laporan.status][1]:
        raise PermissionDenied('Role Anda tidak berwenang menyetujui tahap ini.')

    status_baru, _, langkah_hilang = peta[laporan.status]
    asal = laporan.status
    laporan.status = status_baru
    if status_baru == 'DISETUJUI':
        laporan.disetujui_oleh = request.user
        laporan.disetujui_pada = timezone.now()
        laporan.save(update_fields=['status', 'disetujui_oleh', 'disetujui_pada'])
    else:
        laporan.terbit_pada = timezone.now()
        laporan.save(update_fields=['status', 'terbit_pada'])
    _catat(request.user, 'setujui', laporan,
           f'{asal} → {status_baru} ({laporan.periode_label})')
    messages.success(
        request, f'Laporan {laporan.periode_label} → {laporan.get_status_display()}.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


@login_required
@require_http_methods(['POST'])
def laporan_mutu_regenerasi(request, pk):
    """Bangun ulang snapshot — hanya DRAF; laporan terkunci dianggap basi."""
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)
    if not laporan.boleh_ubah:
        messages.warning(
            request, 'Laporan sudah diverifikasi — snapshot tidak dapat dibangun ulang.')
        return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)
    if not _boleh_lapor_unit(request.user, laporan.unit):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')

    jumlah = build_baris(laporan)
    _catat(request.user, 'regenerasi', laporan, f'{jumlah} baris snapshot diperbarui')
    messages.success(request, f'Snapshot diperbarui: {jumlah} indikator.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


# ---------------------------------------------------------------------------
# 10. Rekap IKP + benchmarking (dokumen BAB V dan BAB VI)
# ---------------------------------------------------------------------------

# Lima jenis insiden yang diminta dokumen. Urutannya tetap agar tabel rekap
# tidak berubah bentuk antar periode; jenis tanpa kejadian dicetak 0, bukan
# dihilangkan.
IKP_JENIS = [
    ('KTD',      'KTD — Kejadian Tidak Diharapkan'),
    ('KNC',      'KNC — Kejadian Nyaris Cedera'),
    ('KTC',      'KTC — Kejadian Tidak Cedera'),
    ('KPC',      'KPC — Kejadian Pasien Cedera'),
    ('SENTINEL', 'Kejadian Sentinel'),
]


def rekap_ikp(tahun, bulan_awal=1, bulan_akhir=12, unit=None):
    """Rekap kejadian IKP per jenis + matriks bulanan untuk BAB V.

    ``unit`` membatasi hitungan ke satu unit kerja; ``None`` berarti seluruh
    rumah sakit. Semua lima jenis selalu muncul di hasil, berisi 0 bila tidak
    ada kejadian — pembaca tidak boleh menyimpulkan "tidak diukur" dari sel
    yang hilang.
    """
    qs = InsidenKeselamatan.objects.filter(
        tanggal_kejadian__year=tahun,
        tanggal_kejadian__month__gte=bulan_awal,
        tanggal_kejadian__month__lte=bulan_akhir,
    )
    if unit is not None:
        qs = qs.filter(unit=unit)

    per_jenis = dict(
        qs.values_list('jenis_insiden').annotate(jumlah=Count('id'))
        .values_list('jenis_insiden', 'jumlah')
    )
    per_bulan_raw = {
        (jenis, bulan): jumlah
        for jenis, bulan, jumlah in qs.values_list(
            'jenis_insiden', 'tanggal_kejadian__month').annotate(jumlah=Count('id'))
    }

    baris = []
    for kode, label in IKP_JENIS:
        baris.append({
            'kode': kode,
            'label': label,
            'jumlah': per_jenis.get(kode, 0),
            'per_bulan': [per_bulan_raw.get((kode, b), 0)
                          for b in range(bulan_awal, bulan_akhir + 1)],
        })

    return {
        'tahun': tahun,
        'bulan_awal': bulan_awal,
        'bulan_akhir': bulan_akhir,
        'bulan_header': BULAN_NAMA[bulan_awal - 1:bulan_akhir],
        'baris': baris,
        'total': sum(b['jumlah'] for b in baris),
        'jenis_lain': sum(j for k, j in per_jenis.items()
                          if k not in {kode for kode, _ in IKP_JENIS}),
    }


def _faktor_indikator(ind):
    """Faktor pengali capaian: 100 untuk persen, selain itu faktor_pengali."""
    if ind is None:
        return Decimal('100')
    if getattr(ind, 'tipe_pengukuran', 'persen') == 'persen':
        return Decimal('100')
    return Decimal(str(getattr(ind, 'faktor_pengali', 100) or 100))


def benchmarking_laporan(laporan):
    """Capaian seluruh rumah sakit untuk indikator yang sama, periode yang sama.

    ``kode_indikator`` unik per unit, jadi "indikator yang sama" diidentifikasi
    lewat ``nama_indikator`` — INM yang diukur di banyak unit memakai nama yang
    identik (mis. "Kepatuhan Kebersihan Tangan" ada di 9 unit). Pembanding
    dihitung dengan rumus ΣN/ΣD yang sama seperti snapshot, bukan rerata persen,
    supaya kolom pembanding tidak pernah memakai definisi berbeda.

    Laporan bercakupan RS tidak punya pembanding (dirinya sendiri), jadi
    hasilnya kosong dan kolomnya tidak dirender.
    """
    if laporan.scope == 'RS':
        return {}

    bulan_awal, bulan_akhir = rentang_bulan(laporan.jenis, laporan.bulan,
                                            laporan.semester)
    nama_list = list(laporan.baris.values_list('nama', flat=True))
    if not nama_list:
        return {}

    agregat = {
        nama: (n, d) for nama, n, d in CatatanIndikator.objects.filter(
            indikator__nama_indikator__in=nama_list,
            tahun=laporan.tahun,
            bulan__gte=bulan_awal,
            bulan__lte=bulan_akhir,
            nilai_denominator__gt=0,
        ).values('indikator__nama_indikator').annotate(
            n=Sum('nilai_numerator'), d=Sum('nilai_denominator')
        ).values_list('indikator__nama_indikator', 'n', 'd')
    }

    hasil = {}
    for baris in laporan.baris.select_related('indikator'):
        n, d = agregat.get(baris.nama, (None, None))
        if not n or not d:
            hasil[baris.kode] = {'capaian_rs': None, 'selisih': None}
            continue
        capaian_rs = (Decimal(n) / Decimal(d)) * _faktor_indikator(baris.indikator)
        capaian_rs = capaian_rs.quantize(Decimal('0.01'))
        selisih = (None if baris.nilai_capaian is None
                   else (baris.nilai_capaian - capaian_rs).quantize(Decimal('0.01')))
        hasil[baris.kode] = {'capaian_rs': capaian_rs, 'selisih': selisih}
    return hasil


def tren_indikator(laporan):
    """Deret capaian bulanan per indikator untuk laporan semester/tahunan.

    Angka per bulan adalah ``CatatanIndikator.nilai_capaian`` apa adanya (bukan
    agregat), supaya pembaca bisa melihat bulan mana yang menjatuhkan capaian
    periode. Laporan bulanan tidak punya deret — satu titik bukan tren.
    """
    if laporan.jenis == 'BULANAN':
        return None

    bulan_awal, bulan_akhir = rentang_bulan(laporan.jenis, laporan.bulan,
                                            laporan.semester)
    bulan_list = list(range(bulan_awal, bulan_akhir + 1))
    kode_list = list(laporan.baris.values_list('kode', flat=True))
    if not kode_list:
        return None

    # nilai_capaian adalah property model (butuh faktor pengali indikator),
    # jadi dihitung di Python dari baris catatan — tidak bisa di-Sum di SQL.
    seri = {}
    for catatan in CatatanIndikator.objects.filter(
            indikator__kode_indikator__in=kode_list,
            tahun=laporan.tahun,
            bulan__gte=bulan_awal,
            bulan__lte=bulan_akhir,
            nilai_denominator__gt=0).select_related('indikator'):
        seri[(catatan.indikator.kode_indikator, catatan.bulan)] = catatan.nilai_capaian

    hasil = []
    for baris in laporan.baris.all():
        nilai_bulan = [seri.get((baris.kode, b)) for b in bulan_list]
        terisi = [v for v in nilai_bulan if v is not None]
        hasil.append({
            'kode': baris.kode,
            'nama': baris.nama,
            'satuan': baris.satuan,
            'target': baris.target,
            'arah': baris.arah,
            'nilai_bulan': nilai_bulan,
            'terendah': min(terisi) if terisi else None,
            'tertinggi': max(terisi) if terisi else None,
            'jumlah_bulan_terisi': len(terisi),
        })

    return {
        'bulan_header': [BULAN_NAMA[b - 1][:3] for b in bulan_list],
        'baris': hasil,
    }


def _grafik_tren(tren, maks=6):
    """Grafik batang tren bulanan + garis target, satu gambar per indikator.

    Yang digambar hanya indikator yang tidak mencapai target pada periode itu
    (maksimal ``maks``) — dokumen tidak perlu 210 grafik, dan pembaca hanya
    butuh melihat di mana capaian jatuh. Angka lengkapnya tetap ada di tabel.
    """
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, Line, String
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    if not tren or not tren.get('baris'):
        return []

    kandidat = [t for t in tren['baris']
                if t['terendah'] is not None and t['target'] is not None
                and ((t['arah'] == 'MAX' and t['tertinggi'] > t['target'])
                     or (t['arah'] != 'MAX' and t['terendah'] < t['target']))]
    kandidat.sort(key=lambda t: t['jumlah_bulan_terisi'], reverse=True)

    grafik = []
    for t in kandidat[:maks]:
        nilai = [float(v) if v is not None else 0.0 for v in t['nilai_bulan']]
        target = float(t['target'])
        puncak = max(nilai + [target]) or 1.0
        skala = max(puncak * 1.15, 1.0)

        d = Drawing(170 * mm, 42 * mm)
        chart = VerticalBarChart()
        chart.x = 12 * mm
        chart.y = 8 * mm
        chart.width = 150 * mm
        chart.height = 28 * mm
        chart.data = [nilai]
        chart.categoryAxis.categoryNames = tren['bulan_header']
        chart.categoryAxis.labels.fontSize = 6
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = skala
        chart.valueAxis.labels.fontSize = 6
        chart.bars[0].fillColor = colors.HexColor('#3b82f6')
        chart.barWidth = 6
        d.add(chart)

        # Garis target: y dipetakan dari skala ke tinggi chart.
        y_target = chart.y + (target / skala) * chart.height
        d.add(Line(chart.x, y_target, chart.x + chart.width, y_target,
                   strokeColor=colors.HexColor('#dc2626'), strokeWidth=0.8,
                   strokeDashArray=[3, 2]))
        d.add(String(chart.x + chart.width + 1 * mm, y_target - 1.5,
                     f'Target {t["arah"]} {target:g}{t["satuan"]}',
                     fontSize=5.5, fillColor=colors.HexColor('#dc2626')))

        grafik.append((f'[{t["kode"]}] {t["nama"]}', d))
    return grafik


def tempel_benchmark(baris, benchmark):
    """Tempel angka pembanding ke objek baris agar template tidak butuh filter."""
    for b in baris:
        bm = benchmark.get(b.kode) or {}
        b.bench_capaian_rs = bm.get('capaian_rs')
        b.bench_selisih = bm.get('selisih')
    return baris


# ---------------------------------------------------------------------------
# 11. Bagian naratif (seksi) — BAB I–VI, ringkasan eksekutif, kendala
# ---------------------------------------------------------------------------

# Bagian naratif yang relevan per jenis laporan; urutan ini yang dirender.
SEKSI_PER_JENIS = {
    'BULANAN': ['RINGKASAN_EKSEKUTIF', 'KENDALA', 'REKOMENDASI'],
    'SEMESTER': ['RINGKASAN_EKSEKUTIF', 'KENDALA', 'REKOMENDASI'],
    'TAHUNAN': ['BAB_I', 'BAB_II', 'BAB_III', 'BAB_IV', 'BAB_V', 'BAB_VI',
                'KESIMPULAN', 'PENUTUP'],
}

SEKSI_JUDUL = dict(LaporanMutuSeksi.KUNCI_CHOICES)


def seksi_laporan(laporan):
    """Daftar bagian naratif laporan + isinya, urut sesuai jenis laporan."""
    tersimpan = {s.kunci: s.isi for s in laporan.seksi.all()}
    return [
        {'kunci': kunci,
         'judul': SEKSI_JUDUL.get(kunci, kunci),
         'isi': tersimpan.get(kunci, '')}
        for kunci in SEKSI_PER_JENIS.get(laporan.jenis, [])
    ]


@login_required
@require_http_methods(['POST'])
def laporan_mutu_simpan_seksi(request, pk):
    """Simpan bagian naratif laporan; hanya untuk laporan draf."""
    laporan = get_object_or_404(LaporanMutu, pk=pk)
    _cek_laporan(request.user, laporan)

    if not laporan.boleh_ubah:
        messages.warning(
            request, 'Laporan sudah diverifikasi — narasi tidak dapat diubah.')
        return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)
    if not _boleh_lapor_unit(request.user, laporan.unit):
        raise PermissionDenied('Laporan ini berada di luar lingkup Anda.')

    jumlah = 0
    for kunci in SEKSI_PER_JENIS.get(laporan.jenis, []):
        if f'seksi_{kunci}' not in request.POST:
            continue
        isi = request.POST.get(f'seksi_{kunci}', '').strip()
        LaporanMutuSeksi.objects.update_or_create(
            laporan=laporan, kunci=kunci,
            defaults={'judul': SEKSI_JUDUL.get(kunci, kunci), 'isi': isi},
        )
        jumlah += 1

    messages.success(request, f'{jumlah} bagian narasi tersimpan.')
    return redirect('akreditasi:laporan_mutu_detail', pk=laporan.pk)


# ---------------------------------------------------------------------------
# 12. Cetak (A4) & PDF
# ---------------------------------------------------------------------------

def _konteks_dokumen(request, laporan):
    """Konteks bersama untuk halaman cetak dan pembangkit PDF."""
    baris = list(laporan.baris.select_related('indikator'))

    # Analisis/tindak lanjut dokumen memakai isian baris; bila masih kosong,
    # jatuh ke data Monitoring & Evaluasi yang sudah ada. Nilainya hanya
    # ditempel di memori (tidak disimpan) supaya cetak tidak mengubah draf.
    monev = _ringkas_monev(laporan)
    tempel_monev_ke_baris(baris, monev)
    for b in baris:
        b.analisis_dokumen = b.analisis or (
            b.monev['pratinjau_analisis'] if b.monev else '')
        b.tindak_lanjut_dokumen = b.tindak_lanjut or (
            b.monev['pratinjau_tindak_lanjut'] if b.monev else '')

    return {
        'laporan': laporan,
        'baris': baris,
        'baris_per_jenis': [
            (kode, judul, [b for b in baris if b.jenis == kode])
            for kode, judul in JENIS_LABEL
        ],
        'jumlah_baris': len(baris),
        'jumlah_tercapai': sum(1 for b in baris if b.status_tercapai is True),
        'jumlah_tidak_tercapai': sum(1 for b in baris if b.status_tercapai is False),
        'jumlah_tanpa_data': sum(1 for b in baris if b.status_tercapai is None),
        # PDSA hanya dicetak untuk indikator yang tidak tercapai dan punya
        # analisis (dari baris atau dari MONEV) — dokumen tidak menampilkan
        # blok kosong.
        'pdsa_rows': [b for b in baris
                      if b.status_tercapai is False
                      and (b.analisis_dokumen or b.tindak_lanjut_dokumen)],
        'seksi': {s.kunci: s for s in laporan.seksi.all()},
        'seksi_list': [s for s in seksi_laporan(laporan) if s['isi']],
        # Rekap IKP hanya bermakna untuk periode agregat (BAB V laporan
        # semester/tahunan); laporan bulanan tetap menampilkannya bulan itu.
        'ikp': rekap_ikp(
            laporan.tahun, *rentang_bulan(laporan.jenis, laporan.bulan,
                                          laporan.semester),
            unit=laporan.unit if laporan.scope == 'UNIT' else None),
        'benchmark': tempel_benchmark(baris, benchmarking_laporan(laporan)),
        'tren': tren_indikator(laporan),
        'rs_profile': RumahSakitProfile.get_default(),
    }


@login_required
def laporan_mutu_cetak(request, pk):
    """Halaman cetak A4 — lebar, tanpa navigasi, siap printer."""
    laporan = get_object_or_404(
        LaporanMutu.objects.select_related('unit', 'pembuat',
                                           'diverifikasi_oleh', 'disetujui_oleh'),
        pk=pk)
    _cek_laporan(request.user, laporan)
    return render(request, 'akreditasi/mutu_laporan_cetak.html',
                  _konteks_dokumen(request, laporan))


def _laporan_pdf(laporan, ctx):
    """Bangkitkan PDF laporan (landscape A4) memakai reportlab platypus."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    DARK = colors.HexColor('#0f172a')
    MUTED = colors.HexColor('#64748b')
    HEAD_BG = colors.HexColor('#e2e8f0')

    def st(nama, **kw):
        dasar = dict(fontName='Helvetica', fontSize=8, leading=10, textColor=DARK)
        dasar.update(kw)
        return ParagraphStyle(nama, **dasar)

    judul = st('judul', fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER)
    sub = st('sub', fontSize=9, alignment=TA_CENTER, textColor=MUTED)
    kepala = st('kepala', fontName='Helvetica-Bold', fontSize=9)
    kecil = st('kecil', fontSize=7.5, leading=9)
    kecil_kiri = st('kecil_kiri', fontSize=7.5, leading=9, alignment=TA_LEFT)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f'Laporan Mutu {laporan.periode_label}',
    )
    story = []
    rs = ctx['rs_profile']
    nama_rs = getattr(rs, 'name', None) or 'Rumah Sakit'

    story.append(Paragraph(nama_rs.upper(), judul))
    story.append(Paragraph(laporan.get_jenis_display().upper(), judul))
    story.append(Paragraph(
        f'{laporan.periode_label} &nbsp;·&nbsp; {laporan.scope_label}'
        + (f' &nbsp;·&nbsp; No. {laporan.nomor}' if laporan.nomor else ''),
        sub))
    story.append(HRFlowable(width='100%', thickness=1, color=MUTED, spaceAfter=6))

    # ── Kepala dokumen ──
    meta = [
        ('Jenis Laporan', laporan.get_jenis_display()),
        ('Periode', laporan.periode_label),
        ('Cakupan', laporan.scope_label),
        ('Status', laporan.get_status_display()),
        ('Batas Waktu', laporan.batas_waktu.strftime('%d %B %Y')),
        ('Dibuat Oleh', f'{laporan.pembuat.get_full_name() or laporan.pembuat.username}'
                        f' — {laporan.dibuat_pada:%d/%m/%Y}'),
        ('Tercapai / Tidak / Tanpa Data',
         f'{ctx["jumlah_tercapai"]} / {ctx["jumlah_tidak_tercapai"]} / {ctx["jumlah_tanpa_data"]}'
         f' dari {ctx["jumlah_baris"]} indikator'),
    ]
    mt = Table([[Paragraph(f'<b>{k}</b>', kecil), Paragraph(str(v), kecil)]
                for k, v in meta],
               colWidths=[55 * mm, 200 * mm])
    mt.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, MUTED),
        ('BACKGROUND', (0, 0), (0, -1), HEAD_BG),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(mt)
    story.append(Spacer(1, 5 * mm))

    # ── Tabel per tier ──
    kepala_tabel = ['No', 'Kode', 'Indikator', 'Unit', 'N', 'D', 'Capaian',
                    'Target', 'Status', 'PJ']
    for _, judul_tier, rows in ctx['baris_per_jenis']:
        if not rows:
            continue
        story.append(Paragraph(f'<b>{judul_tier}</b> ({len(rows)})', kepala))
        data = [[Paragraph(f'<b>{h}</b>', kecil) for h in kepala_tabel]]
        for i, b in enumerate(rows, start=1):
            capaian = (f'{b.nilai_capaian} {b.satuan}'
                       if b.nilai_capaian is not None else '—')
            status = ('Tercapai' if b.status_tercapai is True
                      else 'Tidak Tercapai' if b.status_tercapai is False
                      else 'Tanpa Data')
            data.append([
                Paragraph(str(i), kecil),
                Paragraph(b.kode, kecil),
                Paragraph(b.nama, kecil_kiri),
                Paragraph(b.unit_nama or '—', kecil),
                Paragraph('—' if b.nilai_numerator is None else f'{b.nilai_numerator:g}', kecil),
                Paragraph('—' if b.nilai_denominator is None else f'{b.nilai_denominator:g}', kecil),
                Paragraph(capaian, kecil),
                Paragraph(f'{b.arah} {b.target}', kecil),
                Paragraph(status, kecil),
                Paragraph((b.indikator.pj if b.indikator_id else '') or '—', kecil),
            ])
        tt = Table(data, repeatRows=1,
                   # Total 269 mm = lebar A4 landscape (297) dikurangi margin
                   # 14 mm kiri-kanan. Lebih dari itu membuat kolom terakhir
                   # terpotong di tepi halaman.
                   colWidths=[8 * mm, 22 * mm, 75 * mm, 30 * mm, 20 * mm, 20 * mm,
                              20 * mm, 17 * mm, 22 * mm, 35 * mm])
        tt.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, MUTED),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(tt)
        story.append(Spacer(1, 4 * mm))

    # ── Analisis PDSA baris yang tidak tercapai ──
    analisis = [b for b in ctx['baris']
                if b.status_tercapai is False
                and (b.analisis_dokumen or b.tindak_lanjut_dokumen)]
    if analisis:
        story.append(Paragraph('<b>ANALISIS PDSA &amp; TINDAK LANJUT</b>', kepala))
        story.append(Spacer(1, 2 * mm))
        rows_a = [[Paragraph('<b>Kode</b>', kecil),
                   Paragraph('<b>Analisis PDSA</b>', kecil),
                   Paragraph('<b>Tindak Lanjut</b>', kecil)]]
        for b in analisis:
            rows_a.append([
                Paragraph(b.kode, kecil),
                Paragraph((b.analisis_dokumen or '—').replace('\n', '<br/>'), kecil_kiri),
                Paragraph((b.tindak_lanjut_dokumen or '—').replace('\n', '<br/>'), kecil_kiri),
            ])
        at = Table(rows_a, repeatRows=1, colWidths=[25 * mm, 120 * mm, 120 * mm])
        at.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, MUTED),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(at)
        story.append(Spacer(1, 6 * mm))

    # ── Tren bulanan (semester/tahunan) ──
    tren = ctx.get('tren')
    if tren and tren['baris']:
        story.append(Paragraph(
            f'<b>TREN CAPAIAN BULANAN ({len(tren["bulan_header"])} BULAN)</b>', kepala))
        story.append(Spacer(1, 2 * mm))
        kepala_tren = ['Kode', 'Indikator'] + tren['bulan_header'] + ['Min', 'Maks']
        rows_t = [[Paragraph(f'<b>{h}</b>', kecil) for h in kepala_tren]]
        for t in tren['baris']:
            sel = [Paragraph(t['kode'], kecil),
                   Paragraph(t['nama'], kecil_kiri)]
            sel += [Paragraph('—' if v is None else f'{v:.1f}', kecil)
                    for v in t['nilai_bulan']]
            sel += [Paragraph('—' if t['terendah'] is None else f'{t["terendah"]:.1f}', kecil),
                    Paragraph('—' if t['tertinggi'] is None else f'{t["tertinggi"]:.1f}', kecil)]
            rows_t.append(sel)
        lebar_t = ([22 * mm, 72 * mm] + [12 * mm] * len(tren['bulan_header'])
                   + [15 * mm, 15 * mm])
        trt = Table(rows_t, repeatRows=1, colWidths=lebar_t)
        trt.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, MUTED),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(trt)
        story.append(Paragraph(
            'Capaian periode memakai ΣN/ΣD, bukan rerata kolom bulan di atas.',
            kecil_kiri))
        story.append(Spacer(1, 5 * mm))

        # Grafik hanya untuk indikator yang menyimpang dari target; tabel di
        # atas tetap menjadi pembawa angka yang lengkap.
        grafik = _grafik_tren(tren)
        if grafik:
            story.append(Paragraph(
                '<b>GRAFIK TREN — INDIKATOR DI BAWAH/DI ATAS TARGET</b>', kepala))
            story.append(Spacer(1, 2 * mm))
            for judul_grafik, gambar in grafik:
                story.append(Paragraph(judul_grafik, kecil_kiri))
                story.append(gambar)
                story.append(Spacer(1, 2 * mm))
            story.append(Spacer(1, 3 * mm))

    # ── Bagian naratif (ringkasan eksekutif / BAB) ──
    seksi_terisi = [s for s in ctx.get('seksi_list') or [] if s.get('isi')]
    if seksi_terisi:
        story.append(Paragraph('<b>NARASI LAPORAN</b>', kepala))
        story.append(Spacer(1, 2 * mm))
        for s in seksi_terisi:
            story.append(Paragraph(f'<b>{s["judul"]}</b>', kecil_kiri))
            story.append(Paragraph(s['isi'].replace('\n', '<br/>'), kecil_kiri))
            story.append(Spacer(1, 2 * mm))
        story.append(Spacer(1, 3 * mm))

    # ── Rekap IKP (BAB V) ──
    ikp = ctx.get('ikp')
    if ikp and ikp['baris']:
        story.append(Paragraph(f'<b>REKAP KEJADIAN IKP — {ikp["tahun"]}</b>', kepala))
        story.append(Spacer(1, 2 * mm))
        bulan_header = [b[:3] for b in ikp['bulan_header']]
        rows_i = [[Paragraph('<b>Jenis Insiden</b>', kecil),
                   Paragraph('<b>Jumlah</b>', kecil)]
                  + [Paragraph(f'<b>{h}</b>', kecil) for h in bulan_header]]
        for r in ikp['baris']:
            rows_i.append([Paragraph(r['label'], kecil_kiri),
                           Paragraph(str(r['jumlah']), kecil)]
                          + [Paragraph(str(j), kecil) for j in r['per_bulan']])
        rows_i.append([Paragraph('<b>Total</b>', kecil_kiri),
                       Paragraph(f'<b>{ikp["total"]}</b>', kecil)]
                      + [Paragraph('', kecil) for _ in bulan_header])
        lebar = [70 * mm, 18 * mm] + [9 * mm] * len(bulan_header)
        it = Table(rows_i, repeatRows=1, colWidths=lebar)
        it.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, MUTED),
            ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
            ('BACKGROUND', (0, -1), (-1, -1), HEAD_BG),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(it)
        if ikp.get('jenis_lain'):
            story.append(Paragraph(
                f'{ikp["jenis_lain"]} kejadian berkategori lain tidak termasuk '
                'lima jenis di atas.', kecil_kiri))
        story.append(Spacer(1, 6 * mm))

    # ── Lembar verifikasi & persetujuan (L4, L3, L2, L1) ──
    def nama_pengguna(user, fallback):
        if user is None:
            return '..........................'
        return user.get_full_name() or user.username or fallback

    ttd = [[
        Paragraph(f'<b>{LEVEL_LAPORAN_MUTU["L4"][1]}</b><br/><br/><br/>'
                  f'({nama_pengguna(laporan.diverifikasi_oleh, "")})<br/>'
                  f'{laporan.diverifikasi_pada:%d/%m/%Y}' if laporan.diverifikasi_pada
                  else f'<b>{LEVEL_LAPORAN_MUTU["L4"][1]}</b><br/><br/><br/>'
                       '(..................................)<br/>'
                       '..........................', kecil),
        Paragraph(f'<b>{LEVEL_LAPORAN_MUTU["L3"][1]}</b><br/><br/><br/>'
                  f'({nama_pengguna(laporan.disetujui_oleh, "")})<br/>'
                  f'{laporan.disetujui_pada:%d/%m/%Y}' if laporan.disetujui_pada
                  else f'<b>{LEVEL_LAPORAN_MUTU["L3"][1]}</b><br/><br/><br/>'
                       '(..................................)<br/>'
                       '..........................', kecil),
        Paragraph(f'<b>{LEVEL_LAPORAN_MUTU["L2"][1]}</b><br/><br/><br/>'
                  f'({nama_pengguna(request_pembuat_terbit(laporan), "")})<br/>'
                  f'{laporan.terbit_pada:%d/%m/%Y}' if laporan.terbit_pada
                  else f'<b>{LEVEL_LAPORAN_MUTU["L2"][1]}</b><br/><br/><br/>'
                       '(..................................)<br/>'
                       '..........................', kecil),
        Paragraph(f'<b>{LEVEL_LAPORAN_MUTU["L1"][1]}</b><br/><br/><br/>'
                  '(.................................)<br/>'
                  '..........................', kecil),
    ]]
    sgt = Table(ttd, colWidths=[66 * mm] * 4)
    sgt.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sgt)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'Dicetak {timezone.localtime():%d/%m/%Y %H:%M} — ARIMA.', sub))

    doc.build(story)
    return buf.getvalue()


def request_pembuat_terbit(laporan):
    """Penerbit (L2): pencatat tahap TERBIT; fallback ke pembuat laporan."""
    return laporan.diverifikasi_oleh or laporan.pembuat


@login_required
def laporan_mutu_pdf(request, pk):
    """Unduhan PDF laporan — satu-satunya endpoint yang balas application/pdf."""
    laporan = get_object_or_404(
        LaporanMutu.objects.select_related('unit', 'pembuat',
                                           'diverifikasi_oleh', 'disetujui_oleh'),
        pk=pk)
    _cek_laporan(request.user, laporan)
    ctx = _konteks_dokumen(request, laporan)
    data = _laporan_pdf(laporan, ctx)

    response = HttpResponse(data, content_type='application/pdf')
    nama = f'Laporan_Mutu_{laporan.jenis}_{laporan.tahun}'
    if laporan.bulan:
        nama += f'_{laporan.bulan:02d}'
    response['Content-Disposition'] = f'attachment; filename="{nama}.pdf"'
    return response
