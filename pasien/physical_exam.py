"""Versioned examination choices and non-mutating legacy adapters."""
import copy
import json
from django.core.exceptions import ValidationError


def section(key, label, normal, options, hint='Lokasi, sisi dan rincian temuan'):
    return {'key':key,'label':label,'kind':'anatomical','normal':normal,
            'options':[{'code':'normal','label':'Normal — '+normal}]+[{'code':code,'label':text} for code,text in options]+[{'code':'lainnya','label':'Lainnya'}], 'hint':hint}


GENERAL_CHOICES = {
    'keadaan_umum':['Baik / sakit ringan','Tampak sakit sedang','Tampak sakit berat'],
    'kesadaran':['Kompos Mentis','Apatis','Somnolen','Sopor','Koma'],
}
EXAM_SECTIONS = [
    {'key':'keadaan_umum_kesadaran','label':'Keadaan Umum & Kesadaran','kind':'general','options':[]},
    section('kepala_wajah','Kepala & Wajah','Normocephal, simetris, tidak ada jejas',[
        ('hematoma_vulnus','Hematoma / Vulnus'),('deformitas_fraktur_impresi','Deformitas / Fraktur impresi'),('nyeri_tekan','Nyeri tekan')],'Lokasi dan ukuran jejas/luka'),
    section('mata','Mata','Konjungtiva tidak anemis, sklera tidak ikterik, pupil isokor, refleks cahaya +/+',[
        ('anemis','Konjungtiva anemis'),('ikterik','Sklera ikterik'),('anisokor','Pupil anisokor'),('midriasis_miosis','Pupil midriasis / miosis'),('edema_palpebra_hematoma','Edema palpebra / Hematoma periorbita')],'Ukuran pupil kanan/kiri dan temuan spesifik; ukuran tidak diasumsikan'),
    section('tht','Telinga, Hidung, Tenggorokan','Tidak ada sekret/perdarahan, faring tidak hiperemis',[
        ('otorrhea_rhinorrhea','Otorrhea / Rhinorrhea'),('epistaksis','Epistaksis'),('deviasi_septum','Deviasi septum'),('faring_tonsil','Faring hiperemis / Tonsil membesar')],'Sisi dan karakteristik cairan'),
    section('leher','Leher','Trakea di tengah, JVP tidak meningkat, tidak ada pembesaran KGB',[
        ('jvp_meningkat','Peningkatan JVP'),('deviasi_trakea','Deviasi trakea'),('kgb_tiroid','Pembesaran KGB / Tiroid'),('kaku_kuduk_jejas','Kaku kuduk / Jejas leher')],'Lokasi dan ukuran massa/jejas'),
    section('paru','Thorax — Paru','Gerak simetris, vesikuler +/+, rhonki dan wheezing negatif',[
        ('asimetris_retraksi','Gerak dada asimetris / Retraksi'),('vesikuler_menurun_hilang','Vesikuler menurun / hilang'),('rhonki','Rhonki'),('wheezing','Wheezing'),('perkusi_redup_hipersonor','Perkusi redup / hipersonor')],'Lapang paru, sisi dan lokasi'),
    section('jantung','Thorax — Jantung','BJ I–II reguler, murmur dan gallop negatif',[
        ('ireguler','Bunyi jantung ireguler'),('murmur','Murmur'),('gallop','Gallop'),('bunyi_menjauh','Bunyi jantung menjauh (muffled)')],'Jenis dan lokasi auskultasi'),
    section('abdomen','Abdomen','Datar, supel, bising usus normal, nyeri tekan negatif',[
        ('distensi','Distensi abdomen'),('nyeri_tekan','Nyeri tekan epigastrium / kuadran'),('defans','Defans muskular'),('bising_usus_abnormal','Bising usus meningkat / menurun / menghilang'),('hepatosplenomegali','Hepatomegali / Splenomegali')],'Kuadran RUQ/LUQ/RLQ/LLQ dan rincian'),
    section('genitalia_anus','Genitalia & Anus','Tidak ada kelainan pada pemeriksaan sesuai indikasi',[
        ('perdarahan','Perdarahan pervaginam / uretra'),('retensi_distensi_vesika','Retensi urin / Distensi vesika'),('hemoroid_melena_hematochezia','Hemoroid / Melena / Hematochezia')],'Temuan sesuai indikasi dan status kateter bila diperiksa'),
    section('ekstremitas','Ekstremitas Atas & Bawah','Akral hangat, CRT <2 detik, edema negatif, kekuatan otot normal',[
        ('akral_dingin_pucat_sianosis','Akral dingin / pucat / sianosis'),('crt_memanjang','CRT >2 detik'),('edema','Edema'),('deformitas_krepitasi_fraktur','Deformitas / Krepitasi / Fraktur'),('paresis_plegia','Paresis / Plegia')],'Sisi, lokasi dan derajat kekuatan otot; angka tidak diasumsikan'),
    section('kulit','Kulit & Integumen','Turgor baik, warna normal, tidak ada jejas',[
        ('turgor_menurun','Turgor menurun'),('sianosis_pucat_ikterik','Sianosis / Pucat / Ikterik'),('ruam_petekie_ekimosis','Ruam / Petekie / Ekimosis'),('luka_bakar_ulkus','Luka bakar / Ulkus dekubitus')],'Luas dan derajat luka bila relevan'),
]
CATALOGUE = {item['key']:item for item in EXAM_SECTIONS if item['kind']=='anatomical'}
PROJECTIONS = {'kepala_leher':('kepala_wajah','leher'),'mata':('mata',),'tht':('tht',),
    'thorax':('paru','jantung'),'toraks_dada':('paru','jantung'),'abdomen':('abdomen',),
    'genitalia_anus':('genitalia_anus',),'ekstremitas':('ekstremitas',),'kulit':('kulit',),'integumen_kulit':('kulit',)}
LEGACY_LABELS = {'kepala_leher':'Kepala & Leher (gabungan historis)','thorax':'Thorax (gabungan historis)',
    'toraks_dada':'Thorax (gabungan historis)','integumen_kulit':'Kulit & Integumen','genitalia':'Genitalia & Anus'}


def invalid(message):
    raise ValidationError(message)


def validate_exam(document):
    if not isinstance(document,dict) or set(document)-{'schema_version','sections'}:
        invalid('Struktur pemeriksaan tidak valid.')
    if type(document.get('schema_version')) is not int or document['schema_version'] != 1:
        invalid('Versi pemeriksaan tidak didukung.')
    try:
        if len(json.dumps(document,ensure_ascii=False).encode('utf-8'))>65536:
            invalid('Pemeriksaan maksimal 64 KiB.')
    except (TypeError,ValueError):
        invalid('Pemeriksaan harus berupa JSON.')
    values=document.get('sections')
    if not isinstance(values,dict) or set(values)-set(CATALOGUE):
        invalid('Bagian tubuh tidak dikenal.')
    result={}
    for key,value in values.items():
        if not isinstance(value,dict) or set(value)-{'status','findings','note','reason'}:
            invalid('Atribut temuan tidak valid.')
        status=value.get('status','UNASSESSED')
        findings=value.get('findings',[])
        if status not in ('UNASSESSED','EXAMINED','NOT_EXAMINED') or not isinstance(findings,list):
            invalid('Status atau pilihan temuan tidak valid.')
        codes=[option['code'] for option in CATALOGUE[key]['options']]
        if any(not isinstance(code,str) or code not in codes for code in findings) or len(findings)!=len(set(findings)):
            invalid('Kode temuan tidak dikenal atau berulang.')
        if 'normal' in findings and len(findings)>1:
            invalid('Normal tidak dapat dipilih bersama temuan abnormal.')
        note,reason=value.get('note',''),value.get('reason','')
        if any(not isinstance(text,str) or len(text)>2000 for text in (note,reason)):
            invalid('Keterangan dan alasan maksimal 2000 karakter.')
        note,reason=note.strip(),reason.strip()
        if status!='EXAMINED' and findings or status=='EXAMINED' and not findings:
            invalid('Pilihan temuan harus sesuai status pemeriksaan.')
        if status=='NOT_EXAMINED' and not reason:
            invalid('Alasan tidak diperiksa wajib diisi.')
        if 'lainnya' in findings and not note:
            invalid('Keterangan Lainnya wajib diisi.')
        result[key]={'status':status,'findings':[code for code in codes if code in findings],'note':note,'reason':reason}
    return {'schema_version':1,'sections':result}


def finding_text(key,value):
    status=value.get('status','UNASSESSED')
    if status=='NOT_EXAMINED':
        return 'Tidak diperiksa — '+value.get('reason','')
    if status!='EXAMINED':
        return 'Belum dikaji'
    labels={o['code']:o['label'] for o in CATALOGUE[key]['options']}
    text='; '.join(labels.get(code,code) for code in value.get('findings',[]))
    return text+(' — '+value['note'] if value.get('note') else '')


def summary_for(exam):
    values=exam.get('sections',{})
    return '\n'.join(CATALOGUE[key]['label']+': '+finding_text(key,values[key]) for key in CATALOGUE if key in values and values[key].get('status')!='UNASSESSED')


def prepare_exam(current_secondary,current_head,incoming_secondary,incoming_head):
    if not all(isinstance(v,dict) for v in (current_secondary,current_head,incoming_secondary,incoming_head)):
        invalid('Pemeriksaan historis harus berupa objek JSON; tinjau koreksi secara eksplisit.')
    secondary=copy.deepcopy(current_secondary)
    head=copy.deepcopy(current_head)
    existing=copy.deepcopy(current_secondary.get('head_to_toe',{}))
    incoming=copy.deepcopy(incoming_secondary.get('head_to_toe'))
    if 'head_to_toe' not in incoming_secondary:
        if existing and incoming_head!=current_head:
            invalid('Gunakan formulir terstruktur untuk mengubah pemeriksaan yang sudah diadopsi.')
        secondary.update({k:copy.deepcopy(v) for k,v in incoming_secondary.items() if k not in ('head_to_toe','head_to_toe_summary')})
        head.update(copy.deepcopy(incoming_head))
        return secondary,head
    if not isinstance(incoming,dict):
        invalid('Pemeriksaan terstruktur harus berupa objek.')
    if existing and incoming==existing and incoming_head!=current_head:
        invalid('Gunakan formulir terstruktur untuk mengubah pemeriksaan yang sudah diadopsi.')
    prior=existing.get('legacy_before_adoption',{}) if isinstance(existing,dict) else {}
    if 'legacy_before_adoption' in incoming:
        if not prior or incoming.pop('legacy_before_adoption')!=prior:
            invalid('Provenance historis tidak boleh diubah.')
    incoming=validate_exam(incoming)
    old_sections=existing.get('sections',{}) if isinstance(existing,dict) else {}
    merged=validate_exam({'schema_version':1,'sections':{**old_sections,**incoming['sections']}})
    if not existing and any(current_head.values()):
        prior=copy.deepcopy(current_head)
    if prior:
        merged['legacy_before_adoption']=prior
    secondary['head_to_toe']=merged
    secondary['head_to_toe_summary']=summary_for(merged)
    for target,parts in PROJECTIONS.items():
        if any(part in merged['sections'] for part in parts):
            head[target]='\n'.join(CATALOGUE[part]['label']+': '+finding_text(part,merged['sections'][part])
                for part in parts if part in merged['sections'] and merged['sections'][part]['status']=='EXAMINED')
    return secondary,head


def legacy_text(value):
    if isinstance(value,dict):
        return '; '.join(str(k)+': '+legacy_text(v) for k,v in value.items() if legacy_text(v))
    if isinstance(value,list):
        return '; '.join(filter(None,(legacy_text(v) for v in value)))
    return '' if value is None else str(value).strip()


def exam_context(head,secondary,general):
    head=head if isinstance(head,dict) else {}
    secondary=secondary if isinstance(secondary,dict) else {}
    exam=secondary.get('head_to_toe',{})
    exam=exam if isinstance(exam,dict) else {}
    values=exam.get('sections',{})
    values=values if isinstance(values,dict) else {}
    legacy=[]
    sources=[('Secondary Survey historis',{k:v for k,v in secondary.items() if k not in ('head_to_toe','head_to_toe_summary')})]
    old_head=exam.get('legacy_before_adoption',head if not exam else {k:v for k,v in head.items() if k not in PROJECTIONS})
    sources.append(('Head-to-Toe historis',old_head))
    for source,data in sources:
        if isinstance(data,dict):
            for key,value in data.items():
                text=legacy_text(value)
                if text:
                    legacy.append({'source':source,'label':LEGACY_LABELS.get(key,CATALOGUE.get(key,{}).get('label',key)),'text':text})
    rows=[]
    for item in EXAM_SECTIONS:
        row=copy.deepcopy(item)
        if item['kind']=='general':
            appearance = (general.get('keadaan_umum') or 'Belum dikaji') if 'keadaan_umum' in general else 'Tidak dicatat pada snapshot'
            consciousness = (general.get('kesadaran') or 'Belum dikaji') if 'kesadaran' in general else 'Tidak dicatat pada snapshot'
            row['text']='Keadaan umum: '+appearance+'; Kesadaran: '+consciousness
            row['value']={}
        else:
            value=values.get(item['key'],{})
            row['value']=value if isinstance(value,dict) else {}
            row['text']=finding_text(item['key'],row['value'])
            for option in row['options']:
                option['selected']=option['code'] in row['value'].get('findings',[])
        rows.append(row)
    return {'sections':rows,'legacy':legacy,'summary':secondary.get('head_to_toe_summary','') if exam else '',
            'catalogue':EXAM_SECTIONS,'has_legacy':bool(legacy)}


def exam_present(head,secondary,localis):
    if localis and str(localis).strip():
        return True
    context=exam_context(head,secondary,{})
    if any(row['value'].get('status')=='EXAMINED' and row['value'].get('findings') for row in context['sections']):
        return True
    return bool(context['legacy'])
