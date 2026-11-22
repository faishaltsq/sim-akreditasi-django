"""View modul Jadwal Praktek Dokter (Human Capital).

Semua tampilan memakai resolver kapabilitas yang sama dengan menu navigasi,
sehingga penyembunyian menu bukan batas penegakan otorisasi.
"""
from datetime import date, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from sdm.akses import require_hc_capability, visible_employees, visible_units
from sdm.jadwal_forms import JadwalPraktekRutinForm, PengajuanIzinDokterForm
from sdm.models import (
    JadwalPraktekHarian,
    JadwalPraktekRutin,
    LogAuditJadwal,
    PengajuanIzinDokter,
)
from sdm.services.jadwal_praktek import (
    cek_bentrok_jadwal,
    cek_bentrok_ruangan,
    generate_jadwal_harian,
    proses_izin_dokter,
    sync_jadwal_ke_apm,
    validasi_kredensial_dokter,
)


@login_required
def jadwal_list(request):
    """Daftar pola jadwal rutin beserta peringatan legalitas per dokter."""
    require_hc_capability(request.user, 'can_view_hc')
    units = visible_units(request.user)
    unit_id = (request.GET.get('unit') or '').strip()

    qs = JadwalPraktekRutin.objects.select_related(
        'dokter', 'unit_kerja',
    ).filter(unit_kerja__in=units, is_active=True)
    if unit_id.isdigit():
        qs = qs.filter(unit_kerja_id=unit_id)

    peringatan = {}
    for jadwal in qs:
        if jadwal.dokter_id not in peringatan:
            _, warns = validasi_kredensial_dokter(jadwal.dokter_id)
            peringatan[jadwal.dokter_id] = warns

    baris = [
        {'jadwal': jadwal, 'peringatan': peringatan.get(jadwal.dokter_id, [])}
        for jadwal in qs
    ]

    return render(request, 'sdm/jadwal_praktek/daftar.html', {
        'baris': baris,
        'jumlah_baris': len(baris),
        'unit_options': units.order_by('code'),
        'selected_unit': unit_id,
        'can_manage': visible_units(
            request.user, capability='can_plan_hc_workforce'
        ).exists(),
    })


@login_required
def jadwal_create(request):
    """Buat pola jadwal rutin dengan pemeriksaan bentrok dokter dan ruangan."""
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    form = JadwalPraktekRutinForm(
        request.POST or None, units=units,
    )
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        if cek_bentrok_jadwal(
            data['dokter'].pk, data['hari'], data['jam_mulai'], data['jam_selesai'],
        ):
            form.add_error(
                None,
                'Bentrok jadwal: dokter sudah memiliki jadwal aktif pada jam tersebut.',
            )
        elif cek_bentrok_ruangan(
            data['unit_kerja'].pk, data['ruang_praktek'], data['hari'],
            data['jam_mulai'], data['jam_selesai'],
        ):
            form.add_error(
                None,
                'Bentrok ruangan: ruang tersebut sudah dipakai pada jam yang sama.',
            )
        else:
            jadwal = form.save(commit=False)
            jadwal.created_by = request.user
            jadwal.save()
            messages.success(request, f'Jadwal rutin {jadwal} berhasil dibuat.')
            return redirect('sdm:jadwal_praktek_list')

    return render(request, 'sdm/jadwal_praktek/form.html', {
        'form': form,
        'title': 'Jadwal Praktek Rutin Baru',
    })


@login_required
def jadwal_harian(request):
    """Jadwal efektif harian; pola rutin dibentuk otomatis bila belum ada."""
    require_hc_capability(request.user, 'can_view_hc')
    units = visible_units(request.user)

    tanggal = parse_date(request.GET.get('tanggal') or '') or timezone.localdate()
    dibuat = generate_jadwal_harian(tanggal)

    qs = JadwalPraktekHarian.objects.select_related(
        'dokter_rencana', 'dokter_aktual', 'dokter_pengganti', 'unit_kerja',
    ).filter(tanggal=tanggal, unit_kerja__in=units).order_by('jam_mulai_rencana')

    return render(request, 'sdm/jadwal_praktek/harian.html', {
        'tanggal': tanggal,
        'jadwal_harian': qs,
        'jumlah_dibentuk': dibuat,
        'can_manage': visible_units(
            request.user, capability='can_plan_hc_workforce'
        ).exists(),
    })


@login_required
def jadwal_catat_jam(request, jadwal_id):
    """Catat jam mulai pelayanan aktual untuk indikator ketepatan waktu."""
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    units = visible_units(request.user, capability='can_plan_hc_workforce')
    jadwal = get_object_or_404(
        JadwalPraktekHarian, pk=jadwal_id, unit_kerja__in=units,
    )

    if request.method == 'POST':
        jam_teks = (request.POST.get('jam_mulai_aktual') or '').strip()
        try:
            jam = time.fromisoformat(jam_teks)
        except ValueError:
            messages.error(request, 'Format jam tidak valid (gunakan HH:MM).')
        else:
            jadwal.jam_mulai_aktual = jam
            jadwal.save(update_fields=['jam_mulai_aktual', 'updated_at'])
            LogAuditJadwal.objects.create(
                jadwal_harian=jadwal,
                pengguna=request.user,
                jenis_aksi='CATAT_JAM',
                ringkasan=f'Jam mulai aktual dicatat: {jam:%H:%M}.',
            )
            messages.success(request, 'Jam mulai aktual tersimpan.')
            sync_jadwal_ke_apm(jadwal)

    return redirect(f"{request.POST.get('next') or '/human-capital/jadwal-praktek/harian/'}")


@login_required
def izin_create(request):
    """Ajukan cuti/izin dokter (status awal menunggu persetujuan)."""
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    form = PengajuanIzinDokterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        izin = form.save()
        messages.success(
            request,
            f'Pengajuan izin {izin} tercatat dan menunggu persetujuan.',
        )
        return redirect('sdm:jadwal_praktek_izin_list')

    return render(request, 'sdm/jadwal_praktek/izin_form.html', {
        'form': form,
        'title': 'Pengajuan Izin / Cuti Dokter',
    })


@login_required
def izin_list(request):
    """Daftar pengajuan izin dokter beserta status persetujuannya."""
    require_hc_capability(request.user, 'can_view_hc')
    izin_qs = PengajuanIzinDokter.objects.select_related(
        'dokter', 'dokter_pengganti', 'disetujui_oleh',
    ).order_by('-tanggal_mulai', '-pk')
    return render(request, 'sdm/jadwal_praktek/izin_daftar.html', {
        'izin_list': izin_qs,
        'can_manage': visible_units(
            request.user, capability='can_plan_hc_workforce'
        ).exists(),
    })


@login_required
def izin_approve(request, izin_id):
    """Setujui izin lalu kaskade ke jadwal harian dan jadwal APM."""
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    izin = get_object_or_404(PengajuanIzinDokter, pk=izin_id)

    if request.method == 'POST':
        izin.status = 'DISETUJUI'
        izin.disetujui_oleh = request.user
        izin.disetujui_pada = timezone.now()
        izin.save(update_fields=[
            'status', 'disetujui_oleh', 'disetujui_pada', 'updated_at',
        ])
        jumlah = proses_izin_dokter(izin, pengguna=request.user)
        for jadwal in JadwalPraktekHarian.objects.filter(
            dokter_rencana=izin.dokter,
            tanggal__gte=izin.tanggal_mulai,
            tanggal__lte=izin.tanggal_selesai,
        ):
            sync_jadwal_ke_apm(jadwal)
        messages.success(
            request,
            f'Izin {izin.dokter} disetujui. {jumlah} sesi jadwal diperbarui.',
        )

    return redirect('sdm:jadwal_praktek_izin_list')


@login_required
def izin_tolak(request, izin_id):
    """Tolak pengajuan izin tanpa mengubah jadwal."""
    require_hc_capability(request.user, 'can_plan_hc_workforce')
    izin = get_object_or_404(PengajuanIzinDokter, pk=izin_id)

    if request.method == 'POST':
        izin.status = 'DITOLAK'
        izin.disetujui_oleh = request.user
        izin.disetujui_pada = timezone.now()
        izin.save(update_fields=[
            'status', 'disetujui_oleh', 'disetujui_pada', 'updated_at',
        ])
        messages.info(request, f'Pengajuan izin {izin.dokter} ditolak.')

    return redirect('sdm:jadwal_praktek_izin_list')


@login_required
def pola_eskalasi(request, formasi_id):
    """Eskalasi satu baris defisit pola ketenagaan ke Risk Register."""
    from django.core.exceptions import ValidationError

    from sdm.services.eskalasi_risiko import eskalasi_gap_ke_risiko
    from sdm.services.pola_ketenagaan import hitung_gap_ketenagaan

    require_hc_capability(request.user, 'can_plan_hc_workforce')

    if request.method != 'POST':
        return redirect('sdm:dashboard')

    baris = next(
        (b for b in hitung_gap_ketenagaan(request.user) if b['formasi_id'] == formasi_id),
        None,
    )
    if baris is None:
        messages.error(request, 'Baris pola ketenagaan tidak ditemukan dalam lingkup Anda.')
        return redirect('sdm:dashboard')

    try:
        risiko, created = eskalasi_gap_ke_risiko(baris, user=request.user)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        if created:
            messages.success(
                request,
                f'Risiko "kekurangan tenaga {baris["profesi"]}" dibuat pada Risk Register '
                f'unit {baris["unit_kode"]}.',
            )
        else:
            messages.info(
                request,
                f'Risiko untuk {baris["profesi"]} di {baris["unit_kode"]} sudah ada '
                f'di Risk Register.',
            )
    return redirect('sdm:dashboard')


@login_required
def pola_sk_pdf(request):
    """Unduh dokumen SK Pola Ketenagaan (PDF) untuk lingkup pengguna."""
    from django.http import HttpResponse

    from sdm.services.pola_ketenagaan import render_sk_pola_pdf

    require_hc_capability(request.user, 'can_export_hc')
    unit_id = (request.GET.get('unit') or '').strip()
    unit = None
    if unit_id.isdigit():
        unit = visible_units(request.user, capability='can_export_hc').filter(
            pk=unit_id
        ).first()

    pdf = render_sk_pola_pdf(request.user, unit=unit)
    response = HttpResponse(pdf, content_type='application/pdf')
    nama = 'SK Pola Ketenagaan.pdf'
    response['Content-Disposition'] = f'attachment; filename="{nama}"'
    response['Cache-Control'] = 'private, no-store'
    return response
