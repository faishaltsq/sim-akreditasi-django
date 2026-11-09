import os
import re
import pprint
import docx

doc_path = r'C:\Users\cubeb\Downloads\Master icd 10 dan 9 dokter terbaru dengan tarif.docx'
doc = docx.Document(doc_path)


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def parse_price(p_str):
    if not p_str:
        return None, ''
    m = re.search(r'Rp\s*([\d\.]+)(?:\s*/\s*([a-zA-Z]+))?', p_str)
    if m:
        val = m.group(1).replace('.', '')
        satuan = f'/{m.group(2)}' if m.group(2) else ''
        return val, satuan
    return None, ''


def parse_icd10(text):
    text = clean(text)
    m = re.match(r'^([A-Z0-9\.\s/]+?)\s*[-–]\s*(.+)$', text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return '', text


def parse_icd9_item(s):
    s = clean(s)
    m = re.match(r'^([\d\.]{2,6})\s*[-–:\(]\s*(.+?)\)?$', s)
    if m:
        code = m.group(1).strip()
        name = m.group(2).strip()
        return code, name
    m2 = re.match(r'^([\d\.]{2,6})\s+(.+)$', s)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip()
    return '', s


table_info = [
    (1, 'JANTUNG', 'ICCU'),
    (2, 'PARU', 'BANGSAL-DEWASA'),
    (3, 'ENDOKRIN', 'BANGSAL-DEWASA'),
    (4, 'PD', 'BANGSAL-DEWASA'),
    (5, 'MATA', 'POLI-MATA'),
    (6, 'MATA_PASCA', 'POLI-MATA'),
    (7, 'ORTO_PASCA', 'POLI-ORTHO'),
    (8, 'ORTO', 'POLI-ORTHO'),
    (9, 'NIFAS', 'RUANG-NIFAS'),
    (10, 'VK', 'RUANG-BERSALIN-VK'),
    (11, 'IBS', 'IBS'),
    (12, 'BEDAH', 'BANGSAL-BEDAH'),
    (13, 'ANAK', 'BANGSAL-ANAK'),
    (14, 'IGD', 'IGD'),
]

all_kasus = []
for t_idx, kelompok, unit_code in table_info:
    t = doc.tables[t_idx]
    is_mata_pasca = (t_idx == 6)
    for r_idx, row in enumerate(t.rows[1:]):
        urutan = r_idx + 1
        cells = [c.text for c in row.cells]
        icd10_code, icd10_name = parse_icd10(cells[1])
        raw_actions = [clean(x) for x in re.split(r'\n+', cells[2]) if clean(x)]

        tindakan_list = []
        if is_mata_pasca:
            tatalaksana = clean(cells[3])
            kewenangan = clean(cells[4])
            for act in raw_actions:
                c9, n9 = parse_icd9_item(act)
                tindakan_list.append((c9, n9, None, None, ''))
        else:
            raw_umum = [clean(x) for x in re.split(r'\n+', cells[3]) if clean(x)]
            raw_bpjs = [clean(x) for x in re.split(r'\n+', cells[4]) if clean(x)]
            tatalaksana = clean(cells[5])
            kewenangan = clean(cells[6])
            for i, act in enumerate(raw_actions):
                c9, n9 = parse_icd9_item(act)
                p_u_str = raw_umum[i] if i < len(raw_umum) else ''
                p_b_str = raw_bpjs[i] if i < len(raw_bpjs) else ''
                val_u, sat_u = parse_price(p_u_str)
                val_b, sat_b = parse_price(p_b_str)
                sat = sat_u or sat_b
                tindakan_list.append((c9, n9, val_u, val_b, sat))

        is_trunc = tatalaksana.endswith(
            ('...', ',', 'dan', 'atau', 'serta', 'dengan', 'pada', 'untuk', 'secara', 'yang', 'di', 'ke', 'dari')
        ) or not tatalaksana.endswith(('.', ')', '!', ';'))
        all_kasus.append({
            'kelompok': kelompok,
            'urutan': urutan,
            'icd10': (icd10_code, icd10_name),
            'sdki_kode': '',
            'sdki_nama': '',
            'tindakan': tindakan_list,
            'tatalaksana': tatalaksana,
            'kewenangan': kewenangan,
            'perlu_verifikasi': is_trunc,
            'catatan_sumber': f'Tabel {t_idx} baris {urutan}',
        })

# 5 SDKI cases
t0 = doc.tables[0]
for idx, row in enumerate(t0.rows[1:]):
    cells = [c.text for c in row.cells]
    sdki_raw = clean(cells[1])
    m = re.search(r'\(D\.(\d{4})\)', sdki_raw)
    sdki_code = f'D.{m.group(1)}' if m else ''
    sdki_name = re.sub(r'\s*\(D\.\d{4}\)', '', sdki_raw).strip()
    tatalaksana = clean(cells[3])
    all_kasus.append({
        'kelompok': 'NIFAS',
        'urutan': 16 + idx,
        'icd10': None,
        'sdki_kode': sdki_code,
        'sdki_nama': sdki_name,
        'tindakan': [],
        'tatalaksana': tatalaksana,
        'kewenangan': 'Bidan / Perawat',
        'perlu_verifikasi': False,
        'catatan_sumber': f'Tabel 0 (SDKI Nifas) baris {idx+1}',
    })

kelompok_data = [
    ('IGD', 'Instalasi Gawat Darurat', 'IGD', 1),
    ('JANTUNG', 'Rawat Inap Jantung & Kardiovaskular', 'ICCU', 2),
    ('PARU', 'Rawat Inap Paru & Respirologi', 'BANGSAL-DEWASA', 3),
    ('ENDOKRIN', 'Rawat Inap Endokrin & Ginjal', 'BANGSAL-DEWASA', 4),
    ('PD', 'Rawat Inap Penyakit Dalam', 'BANGSAL-DEWASA', 5),
    ('MATA', 'Perawatan & Bedah Mata', 'POLI-MATA', 6),
    ('MATA_PASCA', 'Perawatan Pascabedah Mata', 'POLI-MATA', 7),
    ('ORTO', 'Rawat Inap Orthopedi & Traumatologi', 'POLI-ORTHO', 8),
    ('ORTO_PASCA', 'Perawatan Pascabedah Orthopedi', 'POLI-ORTHO', 9),
    ('NIFAS', 'Rawat Inap Nifas', 'RUANG-NIFAS', 10),
    ('VK', 'Kamar Bersalin (VK)', 'RUANG-BERSALIN-VK', 11),
    ('IBS', 'Kamar Operasi (IBS)', 'IBS', 12),
    ('BEDAH', 'Rawat Inap Bedah Umum', 'BANGSAL-BEDAH', 13),
    ('ANAK', 'Rawat Inap Anak', 'BANGSAL-ANAK', 14),
]

sdki_data = [
    ('D.0001', 'Bersihan Jalan Napas Tidak Efektif'),
    ('D.0003', 'Gangguan Pertukaran Gas'),
    ('D.0005', 'Pola Napas Tidak Efektif'),
    ('D.0007', 'Gangguan Sirkulasi Spontan'),
    ('D.0008', 'Penurunan Curah Jantung'),
    ('D.0009', 'Perfusi Perifer Tidak Efektif'),
    ('D.0012', 'Risiko Perdarahan (Nifas/Sisa Plasenta)'),
    ('D.0019', 'Defisit Nutrisi'),
    ('D.0020', 'Diare'),
    ('D.0022', 'Hipervolemia'),
    ('D.0023', 'Hipovolemia'),
    ('D.0036', 'Konstipasi'),
    ('D.0039', 'Risiko Syok Hipovolemik'),
    ('D.0049', 'Toleransi Aktivitas Menurun'),
    ('D.0056', 'Intoleransi Aktivitas / Keletihan'),
    ('D.0074', 'Gangguan Rasa Nyaman'),
    ('D.0077', 'Nyeri Akut'),
    ('D.0078', 'Nyeri Kronis'),
    ('D.0080', 'Ansietas'),
    ('D.0111', 'Defisit Pengetahuan'),
    ('D.0129', 'Gangguan Integritas Kulit/Jaringan'),
    ('D.0130', 'Hipertermia'),
    ('D.0131', 'Hipotermia'),
    ('D.0136', 'Risiko Cedera'),
    ('D.0142', 'Risiko Infeksi'),
    ('D.0143', 'Risiko Jatuh'),
    ('D.0149', 'Risiko Perdarahan'),
]

slki_data = [
    ('L.01001', 'Bersihan Jalan Napas'),
    ('L.01003', 'Pertukaran Gas'),
    ('L.01004', 'Pola Napas'),
    ('L.02008', 'Sirkulasi Spontan'),
    ('L.02011', 'Curah Jantung'),
    ('L.02014', 'Status Cairan'),
    ('L.02017', 'Tingkat Perdarahan'),
    ('L.03028', 'Status Cairan & Hidrasi'),
    ('L.03030', 'Fungsi Gastrointestinal'),
    ('L.05046', 'Tingkat Keletihan'),
    ('L.05047', 'Toleransi Aktivitas'),
    ('L.08064', 'Status Kenyamanan'),
    ('L.08066', 'Tingkat Nyeri'),
    ('L.09093', 'Tingkat Ansietas'),
    ('L.12111', 'Tingkat Pengetahuan'),
    ('L.14125', 'Integritas Kulit dan Jaringan'),
    ('L.14134', 'Termoregulasi'),
    ('L.14136', 'Kontrol Cedera'),
    ('L.14137', 'Tingkat Infeksi'),
    ('L.14138', 'Tingkat Jatuh'),
]

siki_data = [
    ('I.01011', 'Manajemen Jalan Napas'),
    ('I.01014', 'Pemantauan Respirasi'),
    ('I.01026', 'Terapi Oksigen'),
    ('I.02067', 'Manajemen Perdarahan Postpartum'),
    ('I.02068', 'Resusitasi Cairan'),
    ('I.02075', 'Perawatan Jantung'),
    ('I.03114', 'Manajemen Hipervolemia'),
    ('I.03116', 'Manajemen Hipovolemia'),
    ('I.04151', 'Manajemen Eliminasi Fekal'),
    ('I.05178', 'Manajemen Energi'),
    ('I.08238', 'Manajemen Nyeri'),
    ('I.09314', 'Reduksi Ansietas'),
    ('I.11353', 'Perawatan Luka'),
    ('I.12383', 'Edukasi Kesehatan'),
    ('I.14537', 'Manajemen Keselamatan Lingkungan'),
    ('I.14539', 'Pencegahan Infeksi'),
    ('I.14540', 'Pencegahan Jatuh'),
    ('I.15506', 'Regulasi Temperatur'),
]

pemetaan_3s = [
    ('D.0077', 'L.08066', 'I.08238', 1),
    ('D.0078', 'L.08066', 'I.08238', 1),
    ('D.0001', 'L.01001', 'I.01011', 1),
    ('D.0003', 'L.01003', 'I.01026', 1),
    ('D.0005', 'L.01004', 'I.01014', 1),
    ('D.0007', 'L.02008', 'I.02068', 1),
    ('D.0008', 'L.02011', 'I.02075', 1),
    ('D.0022', 'L.03028', 'I.03114', 1),
    ('D.0023', 'L.03028', 'I.03116', 1),
    ('D.0012', 'L.02017', 'I.02067', 1),
    ('D.0039', 'L.02014', 'I.02068', 1),
    ('D.0056', 'L.05046', 'I.05178', 1),
    ('D.0049', 'L.05047', 'I.05178', 1),
    ('D.0080', 'L.09093', 'I.09314', 1),
    ('D.0111', 'L.12111', 'I.12383', 1),
    ('D.0129', 'L.14125', 'I.11353', 1),
    ('D.0130', 'L.14134', 'I.15506', 1),
    ('D.0131', 'L.14134', 'I.15506', 1),
    ('D.0136', 'L.14136', 'I.14537', 1),
    ('D.0142', 'L.14137', 'I.14539', 1),
    ('D.0143', 'L.14138', 'I.14540', 1),
    ('D.0149', 'L.02017', 'I.02067', 1),
]

aturan_ep = [
    ('ARK 1', 'Skrining dan Triase Pasien di IGD', True, 1),
    ('PAP 3', 'Pelayanan Pasien Gawat Darurat', True, 2),
    ('PAP 8', 'Peringatan Dini Sistem Skoring (EWS)', True, 3),
    ('SKP 1', 'Identifikasi Pasien Secara Benar', True, 4),
]

out_path = os.path.join('klinis', 'data', 'master_tarif.py')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('# Auto-generated from Master icd 10 dan 9 dokter terbaru dengan tarif.docx\n')
    f.write('# DO NOT EDIT DIRECTLY - generated by tools/generate_master_tarif.py\n\n')
    f.write('KELOMPOK = ' + pprint.pformat(kelompok_data, indent=4) + '\n\n')
    f.write('SDKI = ' + pprint.pformat(sdki_data, indent=4) + '\n\n')
    f.write('SLKI = ' + pprint.pformat(slki_data, indent=4) + '\n\n')
    f.write('SIKI = ' + pprint.pformat(siki_data, indent=4) + '\n\n')
    f.write('PEMETAAN_3S = ' + pprint.pformat(pemetaan_3s, indent=4) + '\n\n')
    f.write('ATURAN_EP = ' + pprint.pformat(aturan_ep, indent=4) + '\n\n')
    f.write('KASUS = ' + pprint.pformat(all_kasus, indent=4) + '\n')

print(f'Successfully generated {out_path} with {len(all_kasus)} cases!')
