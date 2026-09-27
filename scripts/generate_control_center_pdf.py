#!/usr/bin/env python3
"""
Generator PDF Panduan Lengkap Pusat Kontrol Sistem & Hak Akses
SIM Akreditasi RS (SIK AP) — Standar STARKES KARS 2026
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# Palette Warna
TEAL = colors.HexColor('#0d9488')
TEAL_DARK = colors.HexColor('#0f766e')
TEAL_LIGHT = colors.HexColor('#f0fdfa')
SLATE_DARK = colors.HexColor('#0f172a')
SLATE_TEXT = colors.HexColor('#334155')
SLATE_MUTED = colors.HexColor('#64748b')
BORDER_COLOR = colors.HexColor('#cbd5e1')
BG_LIGHT = colors.HexColor('#f8fafc')
WARNING_COLOR = colors.HexColor('#d97706')
DANGER_COLOR = colors.HexColor('#dc2626')

class NumberedCanvas(canvas.Canvas):
    """Canvas yang mencatat total halaman dinamis (Page X of Y) + Header/Footer resmi."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        page_w, page_h = A4

        # Header (mulai halaman 2 ke atas)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(TEAL_DARK)
            self.drawString(1.5 * cm, page_h - 1.2 * cm, "RS MONSISKAMI TIPE B — PANDUAN PUSAT KONTROL SISTEM")
            self.setFont("Helvetica", 8)
            self.setFillColor(SLATE_MUTED)
            self.drawRightString(page_w - 1.5 * cm, page_h - 1.2 * cm, "SIM Akreditasi RS (STARKES 2026)")
            self.setStrokeColor(BORDER_COLOR)
            self.setLineWidth(0.5)
            self.line(1.5 * cm, page_h - 1.35 * cm, page_w - 1.5 * cm, page_h - 1.35 * cm)

        # Footer (semua halaman)
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(1.5 * cm, 1.4 * cm, page_w - 1.5 * cm, 1.4 * cm)

        self.setFont("Helvetica", 8)
        self.setFillColor(SLATE_MUTED)
        self.drawString(1.5 * cm, 1.0 * cm, "Dokumen Resmi Manajemen Sistem &bull; Rahasia Internal RS")

        page_str = f"Halaman {self._pageNumber} dari {page_count}"
        self.drawRightString(page_w - 1.5 * cm, 1.0 * cm, page_str)
        self.restoreState()


def create_guide_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Panduan Lengkap Pusat Kontrol Sistem — RS MonsisKami",
        author="Tim Pengembang SIM Akreditasi RS",
    )

    styles = getSampleStyleSheet()

    # Style Kustom
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=SLATE_DARK,
        alignment=0,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=TEAL_DARK,
        spaceAfter=15,
    )
    h1_style = ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=TEAL_DARK,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )
    h2_style = ParagraphStyle(
        'DocH2',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=SLATE_DARK,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        'DocBody',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=SLATE_TEXT,
        spaceAfter=6,
    )
    body_bold = ParagraphStyle(
        'DocBodyBold',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=SLATE_DARK,
    )
    bullet_style = ParagraphStyle(
        'DocBullet',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=SLATE_TEXT,
        leftIndent=12,
        spaceAfter=3,
    )
    table_cell = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=SLATE_TEXT,
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=SLATE_DARK,
    )
    table_cell_header = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
    )
    callout_style = ParagraphStyle(
        'CalloutText',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=SLATE_DARK,
    )

    story = []

    # ========================================================
    # HEADER COVER / BANNER DOKUMEN
    # ========================================================
    banner_data = [
        [
            Paragraph("<b>RUMAH SAKIT MONSISKAMI TIPE B</b><br/><font size=7 color='#64748b'>Jl. Kesehatan No. 10, Jakarta Pusat &bull; Akreditasi STARKES KARS 2026</font>", table_cell),
            Paragraph("<b>DOKUMEN KONTROL TEKNIS</b><br/><font size=7 color='#0f766e'>Kode: SOP-TI-KARS-07 / Rev. 2.0</font>", ParagraphStyle('HRight', parent=table_cell, alignment=2))
        ]
    ]
    t_banner = Table(banner_data, colWidths=[10*cm, 8*cm])
    t_banner.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_banner)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceBefore=4, spaceAfter=14))

    story.append(Paragraph("Panduan Lengkap Pusat Kontrol Sistem", title_style))
    story.append(Paragraph("Tata Cara Penggunaan, Arsitektur N-Level, Matriks Hak Akses Dinamis, dan Mode Kunci Survei", subtitle_style))

    # Meta Info Card
    meta_data = [
        [
            Paragraph("<b>Modul Sistem:</b> Pusat Kontrol Admin (<code>/accounts/kontrol/</code>)", table_cell),
            Paragraph("<b>Otoritas Pengguna:</b> Super Admin & Admin RS", table_cell),
        ],
        [
            Paragraph("<b>Versi Sistem:</b> SIK AP v2.4 (Railway PostgreSQL Production)", table_cell),
            Paragraph("<b>Standar Acuan:</b> KARS STARKES 2026 & Matriks PDCA", table_cell),
        ]
    ]
    t_meta = Table(meta_data, colWidths=[9*cm, 9*cm])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), TEAL_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.8, TEAL),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # ========================================================
    # 1. TENTANG PUSAT KONTROL
    # ========================================================
    story.append(Paragraph("1. Gambaran Umum & Tujuan", h1_style))
    story.append(Paragraph(
        "<b>Pusat Kontrol Sistem</b> adalah konsol administrasi terpusat yang dirancang untuk memberikan "
        "kustomisasi menyeluruh atas seluruh parameter tata kelola akreditasi dan organisasi rumah sakit. "
        "Sebelum fitur ini ada, perubahan struktur organisasi, penugasan hak akses, ambang batas kelulusan, "
        "dan kebijakan berkas membutuhkan perubahan kode teknis (*hardcoded*). Kini, seluruh konfigurasi "
        "dapat disesuaikan secara mandiri oleh manajemen tanpa sentuhan teknis pengembang.",
        body_style
    ))

    # ========================================================
    # 2. HAK AKSES & TINGKATAN WEWENANG
    # ========================================================
    story.append(Paragraph("2. Hak Akses & Pembagian Wewenang (Tab-Level Permission)", h1_style))
    story.append(Paragraph(
        "Untuk menjamin integritas data, Pusat Kontrol menerapkan sistem proteksi berlapis. Menu ini hanya dapat "
        "diakses oleh pengguna dengan peran Administrator, dengan pembatasan hak antar-tab:",
        body_style
    ))

    role_table_data = [
        [Paragraph("Peran Akun", table_cell_header), Paragraph("Akses Menu", table_cell_header), Paragraph("Wewenang Tab yang Terbuka", table_cell_header)],
        [
            Paragraph("<b>SUPER_ADMIN</b><br/><font size=7 color='#64748b'>Username: admin</font>", table_cell),
            Paragraph("<font color='#0f766e'><b>Akses Penuh</b></font>", table_cell),
            Paragraph("Semua 5 Tab: Hierarki N-Level, Matriks Hak Akses Peran, Override User, Ambang Batas Akreditasi, Tema & Mode Kunci Survei.", table_cell),
        ],
        [
            Paragraph("<b>ADMIN_RS</b><br/><font size=7 color='#64748b'>Username: admin.rs</font>", table_cell),
            Paragraph("<font color='#0f766e'><b>Operasional</b></font>", table_cell),
            Paragraph("Tab 1 (Hierarki), Tab 2 (Matriks Izin), Tab 3 (User Override). Tab 4 & 5 terkunci (read-only) demi keamanan tata kelola sistem.", table_cell),
        ],
        [
            Paragraph("<b>Role Lain</b><br/><font size=7 color='#64748b'>Direktur, Asesor, Nakes</font>", table_cell),
            Paragraph("<font color='#dc2626'><b>Terblokir</b></font>", table_cell),
            Paragraph("Menu disembunyikan dari sidebar. Percobaan akses langsung via URL otomatis diarahkan ke Dashboard dengan pesan peringatan.", table_cell),
        ],
    ]
    t_roles = Table(role_table_data, colWidths=[4*cm, 3.2*cm, 10.8*cm])
    t_roles.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_roles)
    story.append(Spacer(1, 10))

    # ========================================================
    # 3. PANDUAN PENGGUNAAN 5 TAB
    # ========================================================
    story.append(Paragraph("3. Panduan Operasional Tiap Tab", h1_style))

    # TAB 1
    story.append(Paragraph("Tab 1: Hierarki & Unit Organisasi (N-Level & Reparenting)", h2_style))
    story.append(Paragraph(
        "Tab ini digunakan untuk mengelola seluruh struktur unit kerja (65+ unit di RS MonsisKami). Fitur utama meliputi:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Dukungan N-Level Tanpa Batas:</b> Menghapus batasan lama 3 level. Unit kini dapat bersarang hingga tingkat 4, 5, atau lebih dalam (misal: RS &rarr; Direktorat &rarr; Bidang &rarr; Instalasi &rarr; Depo Pelayanan).", bullet_style))
    story.append(Paragraph("&bull; <b>Reparenting Interaktif:</b> Memindahkan induk unit semudah memilih unit induk baru di dropdown *Induk Unit (Parent)*.", bullet_style))
    story.append(Paragraph("&bull; <b>Proteksi Anti-Circular:</b> Sistem secara matematis menolak jika suatu unit dipilih menjadi anak dari sub-unitnya sendiri, mencegah loop sirkular.", bullet_style))
    story.append(Paragraph("&bull; <b>Klasifikasi Tipe Unit:</b> Pilihan label resmi (Pimpinan, Direktorat, Komite RS, SPI, Bagian, Instalasi, KSM, Ruangan, Depo).", bullet_style))
    story.append(Paragraph("&bull; <b>Toggle Aktif / Nonaktif:</b> Menonaktifkan unit kerja yang sedang dimerger atau ditutup tanpa menghapus data riwayat akreditasinya.", bullet_style))
    story.append(Spacer(1, 4))

    # Callout Sort Order
    sort_data = [[Paragraph(
        "<b>Tentang Kolom \"Urutan\" (Sort Order):</b><br/>"
        "Angka ini menentukan posisi tampil unit di sidebar, dropdown formulir, dan halaman pohon hierarki. "
        "Unit dengan angka lebih kecil tampil lebih atas. "
        "<b>Jika semua unit bernilai sama</b> (misal semua <code>0</code>), sistem fallback ke urutan ID database "
        "(urutan kapan unit pertama kali dibuat) — tidak ada pengaruh yang terasa bagi pengguna. "
        "<b>Tips praktis:</b> Gunakan kelipatan 10 (10, 20, 30 ...) agar mudah menyisipkan unit baru "
        "di antara unit yang sudah ada tanpa mengubah angka urutan seluruh unit.",
        callout_style
    )]]
    t_sort = Table(sort_data, colWidths=[18*cm])
    t_sort.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fefce8')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d97706')),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_sort)
    story.append(Spacer(1, 6))

    # Kamus Kolom Tab 1
    story.append(Paragraph("<b>Kamus Kolom pada Tabel Hierarki Unit (Tab 1):</b>", body_bold))
    kamus_tab1 = [
        [Paragraph("Kolom", table_cell_header), Paragraph("Jenis", table_cell_header), Paragraph("Penjelasan Penggunaan", table_cell_header)],
        [Paragraph("Kode", table_cell_bold), Paragraph("Badge (read-only)", table_cell), Paragraph("Kode identitas unik unit (misal: IGD, RANAP). Tidak dapat diubah di halaman ini.", table_cell)],
        [Paragraph("Nama Unit", table_cell_bold), Paragraph("Teks (read-only)", table_cell), Paragraph("Nama lengkap unit beserta PIC (Penanggung Jawab). Ubah di halaman manajemen Unit Kerja.", table_cell)],
        [Paragraph("Level", table_cell_bold), Paragraph("Badge (otomatis)", table_cell), Paragraph("Tingkat hierarki, dihitung otomatis: Level = Level Induk + 1. Jika induk dihapus → menjadi Level 1.", table_cell)],
        [Paragraph("Tipe / Klasifikasi", table_cell_bold), Paragraph("Dropdown pilihan", table_cell), Paragraph("Klasifikasi resmi unit: Pimpinan, Direktorat, Komite RS, SPI, Bagian, Instalasi, KSM, Ruangan, Depo, Lainnya.", table_cell)],
        [Paragraph("Induk Unit (Parent)", table_cell_bold), Paragraph("Dropdown pilihan", table_cell), Paragraph("Pilih unit induk atasan. Pilih \"— Tanpa Induk —\" untuk menjadikan unit sebagai puncak (Level 1).", table_cell)],
        [Paragraph("Urutan", table_cell_bold), Paragraph("Input angka", table_cell), Paragraph("Angka urutan tampil (0 = default). Angka kecil tampil lebih atas. Jika semua sama → urut berdasarkan ID database.", table_cell)],
        [Paragraph("Status", table_cell_bold), Paragraph("Toggle switch", table_cell), Paragraph("Nyala = Aktif (tampil di dropdown). Mati = Nonaktif/arsip (tidak muncul di formulir baru, data lama tetap aman).", table_cell)],
        [Paragraph("Aksi: Simpan", table_cell_bold), Paragraph("Tombol per baris", table_cell), Paragraph("Menyimpan perubahan pada satu baris unit ini saja. Tekan setiap kali selesai mengubah kolom pada baris tersebut.", table_cell)],
        [Paragraph("Cari nama/kode", table_cell_bold), Paragraph("Input teks", table_cell), Paragraph("Filter real-time: mengetik langsung menyaring tabel berdasarkan kode atau nama unit.", table_cell)],
        [Paragraph("Buka Pohon Visual", table_cell_bold), Paragraph("Tombol link", table_cell), Paragraph("Membuka halaman Pohon Hierarki (/unit/hierarki/) di tab browser baru untuk visualisasi pohon organisasi.", table_cell)],
    ]
    t_kamus1 = Table(kamus_tab1, colWidths=[3.5*cm, 3.5*cm, 11*cm])
    t_kamus1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_kamus1)
    story.append(Spacer(1, 6))

    # TAB 2
    story.append(Paragraph("Tab 2: Matriks Hak Akses Peran Dinamis (Role Permission Matrix)", h2_style))
    story.append(Paragraph(
        "Menyediakan kisi-kisi interaktif antara <b>6 Peran Standar</b> dengan <b>18 Modul Izin Modular</b>. Administrator cukup "
        "menekan saklar switch untuk membuka atau mencabut wewenang operasional suatu peran.",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Perubahan Seketika:</b> Pengaturan izin langsung berlaku saat tombol simpan ditekan tanpa perlu me-restart server.", bullet_style))
    story.append(Paragraph("&bull; <b>Lockout Guard (Proteksi Keamanan):</b> Izin vital Super Admin (Akses Kontrol, Kelola Pengguna, dan Kelola Sistem) diproteksi secara permanen dari penonaktifan tidak sengaja.", bullet_style))
    story.append(Paragraph("&bull; <b>Tombol Reset KARS:</b> Fitur satu-klik untuk mengembalikan seluruh matriks izin ke formula standar bawaan akreditasi KARS.", bullet_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>Kamus Elemen pada Matriks Izin (Tab 2):</b>", body_bold))
    kamus_tab2 = [
        [Paragraph("Elemen", table_cell_header), Paragraph("Jenis", table_cell_header), Paragraph("Penjelasan Penggunaan", table_cell_header)],
        [Paragraph("Grid switch 18×6", table_cell_bold), Paragraph("Toggle switch", table_cell), Paragraph("Baris = modul izin, Kolom = peran. Nyala (biru) = izin diberikan. Mati (abu) = izin dicabut.", table_cell)],
        [Paragraph("Switch abu dikunci (disabled)", table_cell_bold), Paragraph("Checkbox terkunci", table_cell), Paragraph("Izin vital Super Admin tidak dapat dimatikan. Hover akan menampilkan pesan peringatan alasannya.", table_cell)],
        [Paragraph("Simpan Seluruh Matriks Izin", table_cell_bold), Paragraph("Tombol utama", table_cell), Paragraph("Mengirim semua status switch sekaligus ke server. WAJIB ditekan setelah mengubah switch, atau perubahan akan hilang.", table_cell)],
        [Paragraph("Reset ke Standar KARS", table_cell_bold), Paragraph("Tombol merah", table_cell), Paragraph("Mengembalikan SEMUA izin ke nilai default bawaan sistem. Konfirmasi dialog akan muncul sebelum eksekusi.", table_cell)],
    ]
    t_kamus2 = Table(kamus_tab2, colWidths=[4*cm, 3.5*cm, 10.5*cm])
    t_kamus2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_kamus2)
    story.append(Spacer(1, 6))

    # TAB 3
    story.append(Paragraph("Tab 3: Kustomisasi Akses Pengguna (User Overrides)", h2_style))
    story.append(Paragraph(
        "Digunakan saat staf memerlukan wewenang khusus tambahan di luar batasan perannya tanpa harus menaikkan pangkat globalnya di sistem. "
        "Misalnya, seorang <i>Staf Nakes</i> ditunjuk menjadi Sekretaris Pokja, sehingga membutuhkan izin unggah RDWOS dan verifikasi KPS. "
        "Cukup buka modal kustomisasi pada nama staf tersebut dan aktifkan izin terkait.",
        body_style
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>Kamus Elemen pada Halaman User Overrides (Tab 3):</b>", body_bold))
    kamus_tab3 = [
        [Paragraph("Elemen", table_cell_header), Paragraph("Jenis", table_cell_header), Paragraph("Penjelasan Penggunaan", table_cell_header)],
        [Paragraph("Tabel daftar pengguna", table_cell_bold), Paragraph("Tabel (read-only)", table_cell), Paragraph("Menampilkan semua akun: username, nama lengkap, email, peran dasar, unit kerja, dan status override.", table_cell)],
        [Paragraph("Izin Kustom Aktif", table_cell_bold), Paragraph("Badge info", table_cell), Paragraph("Badge kuning = pengguna ini memiliki N override aktif. Badge abu = ikuti peran standar (tidak ada override).", table_cell)],
        [Paragraph("Cari nama / username", table_cell_bold), Paragraph("Input teks", table_cell), Paragraph("Filter real-time tabel pengguna berdasarkan username, nama lengkap, atau label peran.", table_cell)],
        [Paragraph("Tambah Pengguna Baru", table_cell_bold), Paragraph("Tombol link", table_cell), Paragraph("Membuka halaman form pembuatan akun baru (/accounts/create/).", table_cell)],
        [Paragraph("Atur Akses Kustom", table_cell_bold), Paragraph("Tombol per baris", table_cell), Paragraph("Membuka modal popup berisi 18 checkbox izin yang dapat diaktifkan khusus untuk pengguna ini.", table_cell)],
        [Paragraph("Modal: 18 checkbox izin", table_cell_bold), Paragraph("Toggle switch", table_cell), Paragraph("Centang = izin override aktif untuk pengguna ini, menimpa setelan default perannya. Kosongkan semua = kembali ikuti peran.", table_cell)],
        [Paragraph("Simpan Akses Kustom", table_cell_bold), Paragraph("Tombol di modal", table_cell), Paragraph("Menyimpan override untuk pengguna ini saja. Berlaku langsung pada request berikutnya pengguna tersebut.", table_cell)],
    ]
    t_kamus3 = Table(kamus_tab3, colWidths=[4*cm, 3.5*cm, 10.5*cm])
    t_kamus3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_kamus3)
    story.append(Spacer(1, 6))

    # Page break agar Tab 4 dan Tabel Izin berada di halaman baru yang rapi
    story.append(PageBreak())

    # TAB 4
    story.append(Paragraph("Tab 4: Standar & Ambang Batas Akreditasi (Passing Grade & Kebijakan)", h2_style))
    story.append(Paragraph(
        "Khusus untuk Super Admin, tab ini menampung seluruh variabel perhitungan otomatis sistem:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Ambang Batas Nilai Kelulusan (Passing Grade %):</b> Ambang minimal capaian untuk predikat Paripurna (&ge;80%), Utama (&ge;60%), Madya (&ge;40%), dan Dasar (&ge;20%). Perubahan nilai ini langsung memengaruhi modul Auto-Scoring dan badge pada Matriks PDCA.", bullet_style))
    story.append(Paragraph("&bull; <b>Kebijakan Bukti RDWOS:</b> Batas ukuran unggah berkas (default: 25 MB) dan daftar ekstensi yang diperbolehkan (pdf, docx, xlsx, dll).", bullet_style))
    story.append(Paragraph("&bull; <b>Peringatan STR/SIP Nakes (KPS):</b> Mengatur jendela waktu (misal: 60 hari) sebelum masa berlaku habis untuk memunculkan indikator peringatan kuning pada portofolio staf.", bullet_style))
    story.append(Paragraph("&bull; <b>Matriks Risiko 5x5:</b> Ambang batas skor pembagian tingkat risiko (Sangat Tinggi &ge;20, Tinggi &ge;12, Sedang &ge;5, Rendah &ge;1).", bullet_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>Kamus Formulir Konfigurasi Sistem (Tab 4):</b>", body_bold))
    kamus_tab4 = [
        [Paragraph("Field Formulir", table_cell_header), Paragraph("Satuan / Format", table_cell_header), Paragraph("Efek pada Sistem", table_cell_header)],
        [Paragraph("Threshold Paripurna / Utama / Madya / Dasar", table_cell_bold), Paragraph("Persen (10–100%)", table_cell), Paragraph("Mengubah batas kelulusan KARS di modul Auto-Scoring dan badge kelulusan per Pokja secara dinamis.", table_cell)],
        [Paragraph("Batas Maksimal Ukuran Unggah", table_cell_bold), Paragraph("Angka (MB)", table_cell), Paragraph("Membatasi ukuran satu berkas yang boleh diunggah di modul RDWOS bukti akreditasi dan portofolio staf.", table_cell)],
        [Paragraph("Ekstensi File yang Diizinkan", table_cell_bold), Paragraph("Teks pisah koma", table_cell), Paragraph("Format: pdf,docx,xlsx,jpg,png (tanpa titik). Berkas dengan ekstensi selain ini otomatis ditolak sistem.", table_cell)],
        [Paragraph("Peringatan Kedaluwarsa STR/SIP", table_cell_bold), Paragraph("Angka (Hari)", table_cell), Paragraph("Jumlah hari sebelum tanggal expired. Jika sisa hari <= angka ini, badge kuning peringatan akan menyala di portal nakes.", table_cell)],
        [Paragraph("Ambang Batas Matriks Risiko 5x5", table_cell_bold), Paragraph("Skor (1–25)", table_cell), Paragraph("Batas klasifikasi tingkat risiko: Sangat Tinggi (merah), Tinggi (oranye), Sedang (kuning), Rendah (hijau).", table_cell)],
        [Paragraph("Simpan Konfigurasi Standar", table_cell_bold), Paragraph("Tombol form submit", table_cell), Paragraph("Menyimpan semua setelan di Tab 4 sekaligus. Refresh halaman otomatis.", table_cell)],
    ]
    t_kamus4 = Table(kamus_tab4, colWidths=[4.5*cm, 3.2*cm, 10.3*cm])
    t_kamus4.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_kamus4)
    story.append(Spacer(1, 6))

    # TAB 5
    story.append(Paragraph("Tab 5: Branding, Tema & Mode Kunci Survei (Freeze Mode)", h2_style))
    story.append(Paragraph(
        "Menampung pengaturan visual dan protokol tanggap darurat akreditasi:",
        body_style
    ))
    story.append(Paragraph(
        "&bull; <b>Mode Kunci Survei (Read-Only Freeze):</b> Saat surveior akreditasi KARS datang ke rumah sakit, "
        "Super Admin dapat menekan tombol kunci ini. Seluruh akun staf non-superadmin seketika berubah menjadi "
        "<b>Hanya Baca (Read-Only)</b>. Hal ini melindungi data dari risiko terhapus, salah edit skor, atau tertukar berkas secara tidak sengaja saat telusur berlangsung.",
        bullet_style
    ))
    story.append(Paragraph("&bull; <b>Pilihan Tema:</b> Menyesuaikan skema warna aksen aplikasi (Teal Medis, Hospital Royal Blue, Emerald Green, atau Dark Navy).", bullet_style))
    story.append(Paragraph("&bull; <b>Kop Surat Dokumen Cetak:</b> Menetapkan teks kop surat resmi rumah sakit yang otomatis tercetak di header lembar cetak dokumen dan matriks PDCA.", bullet_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>Kamus Elemen pada Tab 5 (Branding & Mode Survei):</b>", body_bold))
    kamus_tab5 = [
        [Paragraph("Elemen", table_cell_header), Paragraph("Jenis", table_cell_header), Paragraph("Penjelasan Penggunaan", table_cell_header)],
        [Paragraph("Kunci Sistem Sekarang (Mode Survei)", table_cell_bold), Paragraph("Tombol merah konfirmasi", table_cell), Paragraph("Mengunci seluruh hak tulis non-Super Admin. Banner peringatan kuning akan muncul di semua layar pengguna.", table_cell)],
        [Paragraph("Buka Kunci Sistem", table_cell_bold), Paragraph("Tombol hijau/outline", table_cell), Paragraph("Mengembalikan sistem ke status normal terbuka. Hanya muncul saat Mode Survei sedang aktif.", table_cell)],
        [Paragraph("Warna Aksen Antarmuka Sistem", table_cell_bold), Paragraph("Dropdown 4 pilihan", table_cell), Paragraph("Pilihan tema: Teal Medis (default), Hospital Royal Blue, Emerald Green, atau Dark Navy Slate.", table_cell)],
        [Paragraph("Teks Kop Surat Resmi Dokumen Cetak", table_cell_bold), Paragraph("Textarea (multiline)", table_cell), Paragraph("Teks kop surat (nama yayasan, nama RS, alamat, izin operasional) yang muncul otomatis saat cetak (Ctrl+P).", table_cell)],
        [Paragraph("Simpan Tampilan & Kop Surat", table_cell_bold), Paragraph("Tombol simpan form", table_cell), Paragraph("Menyimpan pilihan tema dan kop surat sekaligus.", table_cell)],
    ]
    t_kamus5 = Table(kamus_tab5, colWidths=[4.5*cm, 3.2*cm, 10.3*cm])
    t_kamus5.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_kamus5)
    story.append(Spacer(1, 10))

    # ========================================================
    # 4. TABEL 18 MODUL IZIN SISTEM
    # ========================================================
    story.append(Paragraph("4. Tabel Referensi 18 Modul Izin Sistem", h1_style))
    story.append(Paragraph(
        "Berikut adalah rincian lengkap 18 izin modular yang dapat diatur pada Matriks Peran maupun User Overrides:",
        body_style
    ))

    perm_data = [
        [Paragraph("No", table_cell_header), Paragraph("Kode Teknis Izin", table_cell_header), Paragraph("Nama Modul", table_cell_header), Paragraph("Fungsi & Cakupan Wewenang", table_cell_header)],
        [Paragraph("1", table_cell), Paragraph("<code>can_view_pdca</code>", table_cell), Paragraph("Lihat Matriks PDCA", table_cell_bold), Paragraph("Membuka dan membaca halaman Matriks PDCA serta daftar EP Pokja.", table_cell)],
        [Paragraph("2", table_cell), Paragraph("<code>can_edit_pdca</code>", table_cell), Paragraph("Ubah Rencana PDCA", table_cell_bold), Paragraph("Mengisi formulir baseline, target mutu, PIC, jadwal, dan estimasi biaya.", table_cell)],
        [Paragraph("3", table_cell), Paragraph("<code>can_score_ep</code>", table_cell), Paragraph("Beri Skor EP (0/5/10)", table_cell_bold), Paragraph("Memberikan nilai self-assessment pada elemen penilaian standar.", table_cell)],
        [Paragraph("4", table_cell), Paragraph("<code>can_view_rdwos</code>", table_cell), Paragraph("Akses Bukti RDWOS", table_cell_bold), Paragraph("Melihat repositori dan mengunduh berkas bukti regulasi & dokumen.", table_cell)],
        [Paragraph("5", table_cell), Paragraph("<code>can_upload_rdwos</code>", table_cell), Paragraph("Unggah Berkas Bukti", table_cell_bold), Paragraph("Mengunggah dokumen bukti baru ke penyimpanan server/Supabase.", table_cell)],
        [Paragraph("6", table_cell), Paragraph("<code>can_delete_rdwos</code>", table_cell), Paragraph("Hapus Berkas Bukti", table_cell_bold), Paragraph("Menghapus berkas bukti yang telah terunggah pada elemen penilaian.", table_cell)],
        [Paragraph("7", table_cell), Paragraph("<code>can_view_risiko</code>", table_cell), Paragraph("Lihat Register Risiko", table_cell_bold), Paragraph("Membaca profil risiko unit, peta matriks 5x5, dan riwayat mitigasi.", table_cell)],
        [Paragraph("8", table_cell), Paragraph("<code>can_manage_risiko</code>", table_cell), Paragraph("Kelola Profil Risiko", table_cell_bold), Paragraph("Menginput risiko baru, asesmen dampak/probabilitas, dan evaluasi.", table_cell)],
        [Paragraph("9", table_cell), Paragraph("<code>can_lapor_insiden</code>", table_cell), Paragraph("Lapor Insiden RS", table_cell_bold), Paragraph("Mengisi formulir pelaporan insiden keselamatan (KNC/KTC/KTD/Sentinel).", table_cell)],
        [Paragraph("10", table_cell), Paragraph("<code>can_investigate_insiden</code>", table_cell), Paragraph("Investigasi Insiden", table_cell_bold), Paragraph("Melakukan grading risiko insiden, investigasi sederhana, atau RCA.", table_cell)],
        [Paragraph("11", table_cell), Paragraph("<code>can_view_scoring</code>", table_cell), Paragraph("Akses Auto-Scoring", table_cell_bold), Paragraph("Melihat prediksi persentase kelulusan KARS dan radar capaian bab.", table_cell)],
        [Paragraph("12", table_cell), Paragraph("<code>can_export_reports</code>", table_cell), Paragraph("Ekspor Data Excel", table_cell_bold), Paragraph("Mengunduh laporan rekapitulasi data akreditasi ke format spreadsheet.", table_cell)],
        [Paragraph("13", table_cell), Paragraph("<code>can_manage_units</code>", table_cell), Paragraph("Kelola Unit Kerja", table_cell_bold), Paragraph("Menambah unit baru, mengubah hierarki induk, dan klasifikasi unit.", table_cell)],
        [Paragraph("14", table_cell), Paragraph("<code>can_manage_users</code>", table_cell), Paragraph("Kelola Akun Staf", table_cell_bold), Paragraph("Membuat akun baru, mengubah peran staf, dan mereset kata sandi.", table_cell)],
        [Paragraph("15", table_cell), Paragraph("<code>can_verify_kps</code>", table_cell), Paragraph("Verifikasi KPS Nakes", table_cell_bold), Paragraph("Memvalidasi dan menyetujui dokumen STR, SIP, SPK, dan RKK nakes.", table_cell)],
        [Paragraph("16", table_cell), Paragraph("<code>can_view_audit_log</code>", table_cell), Paragraph("Akses Log Sistem", table_cell_bold), Paragraph("Melihat jejak rekam audit aktivitas dan histori perubahan seluruh data.", table_cell)],
        [Paragraph("17", table_cell), Paragraph("<code>can_access_control_center</code>", table_cell), Paragraph("Akses Pusat Kontrol", table_cell_bold), Paragraph("Hak mengakses antarmuka konsol Pusat Kontrol Sistem.", table_cell)],
        [Paragraph("18", table_cell), Paragraph("<code>can_manage_system_settings</code>", table_cell), Paragraph("Kelola Setelan Sistem", table_cell_bold), Paragraph("Mengubah ambang batas kelulusan, tema, dan Mode Kunci Survei.", table_cell)],
    ]
    t_perm = Table(perm_data, colWidths=[0.8*cm, 4.2*cm, 4*cm, 9*cm])
    t_perm.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), TEAL_DARK),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    story.append(t_perm)
    story.append(Spacer(1, 10))

    # ========================================================
    # 5. PROTOKOL KEAMANAN & AUDIT TRAIL
    # ========================================================
    story.append(Paragraph("5. Protokol Keamanan, Lockout Safety & Jejak Audit", h1_style))
    story.append(Paragraph(
        "Sistem dilengkapi pengaman ganda untuk mencegah kesalahan fatal operasional:",
        body_style
    ))
    story.append(Paragraph("1. <b>Proteksi Lockout Super Admin:</b> Izin akses pusat kontrol dan kelola sistem pada peran Super Admin diproteksi permanen. Sistem backend akan otomatis menolak jika ada request yang mencoba mematikan izin ini.", bullet_style))
    story.append(Paragraph("2. <b>Audit Trail Otomatis:</b> Setiap perubahan konfigurasi (reparenting unit, perubahan izin, override akun, ambang batas, maupun toggle mode survei) dicatat secara mendalam di tabel <code>AuditLog</code> mencakup timestamp, user pelaku, alamat IP, nilai sebelum, dan nilai sesudah.", bullet_style))
    story.append(Spacer(1, 12))

    # Callout Box Kesimpulan
    callout_data = [
        [
            Paragraph(
                "<b>RINGKASAN TATA KELOLA ADMINISTRATOR:</b><br/>"
                "&bull; Lakukan reparenting unit kerja di <b>Tab 1</b> dengan cermat memperhatikan silsilah organisasi.<br/>"
                "&bull; Hindari menaikkan peran staf ke Admin RS jika hanya butuh wewenang kecil; gunakan <b>Tab 3 (User Overrides)</b>.<br/>"
                "&bull; Aktifkan <b>Mode Kunci Survei (Tab 5)</b> H-1 sebelum surveior tiba di rumah sakit untuk menjamin ketenangan data.",
                callout_style
            )
        ]
    ]
    t_callout = Table(callout_data, colWidths=[18*cm])
    t_callout.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), TEAL_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, TEAL),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_callout)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path

if __name__ == '__main__':
    out_file = "C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django/docs/07_PANDUAN_PUSAT_KONTROL_AKSES_DAN_HIERARKI.pdf"
    res = create_guide_pdf(out_file)
    print(f"PDF berhasil dibuat: {res} ({os.path.getsize(out_file)} bytes)")
