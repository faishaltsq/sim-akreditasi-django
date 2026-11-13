"""Synthetic local-only browser gate. Auth state is generated outside the repository."""
import argparse
import json
import re
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect


def run(state_path, evidence):
    state=json.loads(Path(state_path).read_text(encoding='utf-8'))
    evidence=Path(evidence);evidence.mkdir(parents=True,exist_ok=True)
    base=state['base_url'];report={'synthetic':True,'viewports':[],'journeys':[],'page_errors':[]}
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        def context(role,width=1366):
            ctx=browser.new_context(viewport={'width':width,'height':900},ignore_https_errors=True)
            ctx.add_cookies([{'name':'sessionid','value':state['users'][role]['session'],'url':base}])
            return ctx
        def open_page(ctx,visit,step):
            page=ctx.new_page();page.on('pageerror',lambda exc:report['page_errors'].append(str(exc)))
            page.action_results=[]
            def capture_action(route):
                upstream=route.fetch()
                page.action_results.append({'status':upstream.status,'body':upstream.json(),'request':route.request.post_data_json})
                route.fulfill(response=upstream)
            page.route('**/asesmen-igd/aksi/',capture_action)
            page.on('dialog',lambda dialog:dialog.accept())
            response=page.goto(f'{base}/pasien/kunjungan/{visit}/asesmen-igd/?step={step}')
            assert response.status==200,response.status
            return page
        def click_action(page,button):
            with page.expect_response(lambda response:'/asesmen-igd/aksi/' in response.url and response.request.method=='POST') as got:
                button.click()
            response=page.action_results[-1]
            assert response['status']==200,response
            assert response['body']['success'],response
            expect(page.locator('#igd-step-form')).to_have_attribute('data-version',str(response['body']['version']))
            if page.locator('#igd-diagnosis-form').count():
                expect(page.locator('#igd-diagnosis-form')).to_have_attribute('data-temp-id',re.compile('.+'))
            return response['body']
        def post_action(ctx,page,visit,operation,fields):
            version=int(page.locator('#igd-step-form').get_attribute('data-version'))
            token=page.locator('#igd-step-form input[name=csrfmiddlewaretoken]').input_value()
            response=ctx.request.post(f'{base}/pasien/kunjungan/{visit}/asesmen-igd/aksi/',data={'operation':operation,'fields':fields,'version':version,'request_id':str(uuid4())},headers={'X-CSRFToken':token})
            assert response.status==200,response.text()
            return response.json()
        for label,width in [('desktop',1366),('tablet',768),('mobile',375)]:
            ctx=context('doctor',width);visit=state['visits'][label];page=open_page(ctx,visit,8)
            # Component roots and canonical Django field names disambiguate repeated labels.
            panel=page.locator('#igd-diagnoses')
            panel.get_by_label('Diagnosis manual / istilah pencarian master').press_sequentially('Diagnosis utama synthetic '+label,delay=5)
            panel.get_by_role('checkbox',name='Diagnosis Utama',exact=True).check()
            click_action(page,panel.get_by_role('button',name='Simpan Diagnosis',exact=True))
            expect(panel.get_by_text('Diagnosis utama synthetic '+label,exact=True)).to_be_visible()
            panel.get_by_label('Diagnosis manual / istilah pencarian master').fill('Diagnosis sekunder synthetic '+label)
            click_action(page,panel.get_by_role('button',name='Simpan Diagnosis',exact=True))
            secondary=panel.locator('article').filter(has_text='Diagnosis sekunder synthetic '+label)
            secondary.get_by_role('button',name='Edit / Jadikan Utama').click()
            panel.get_by_role('checkbox',name='Diagnosis Utama',exact=True).check()
            click_action(page,panel.get_by_role('button',name='Simpan Diagnosis',exact=True))
            expect(panel.locator('article').filter(has_text='Diagnosis sekunder synthetic '+label).get_by_text('Diagnosis Utama',exact=True)).to_be_visible()
            expect(panel.locator('article')).to_have_count(2)
            layout=page.evaluate('({width:innerWidth,documentWidth:document.documentElement.scrollWidth})')
            assert layout['documentWidth']<=width+1,layout
            panel.scroll_into_view_if_needed();page.screenshot(path=str(evidence/f'diagnosis-{width}.png'))
            report['viewports'].append({'width':width,'diagnosis_primary_switch':True,'layout':layout})
            page.goto(f'{base}/pasien/kunjungan/{visit}/asesmen-igd/?step=7')
            ancillary=page.locator('#igd-ancillary')
            for selector,item_id in zip(['Kategori Utama','Instalasi','Kelompok','Item Pemeriksaan'],state['catalogue']['ancillary']):
                ancillary.get_by_label(selector,exact=True).select_option(str(item_id))
            ancillary.get_by_label('Indikasi klinis / diagnosis kerja').fill('Indikasi synthetic CITO')
            ancillary.get_by_label('Prioritas',exact=True).select_option('CITO')
            ancillary.get_by_role('button',name='Tambah ke Daftar Order').click()
            ancillary.get_by_label('Kategori Utama',exact=True).select_option('')
            expect(page.locator('#anc-basket').get_by_role('listitem')).to_have_count(1)
            click_action(page,ancillary.get_by_role('button',name='Kirim Semua Order Terpilih'))
            expect(page.get_by_text('CBC Synthetic · Laboratorium',exact=True)).to_be_visible()
            report['journeys'].append({'kind':'ancillary','viewport':width,'basket_retained_on_parent_change':True})
            ctx.close()
        lab=context('lab');labpage=lab.new_page();labpage.goto(base+'/pasien/penunjang/?jenis=LAB')
        labrow=labpage.get_by_role('row').filter(has_text=state['patient_rm']['desktop'])
        labrow.get_by_role('button',name='Ubah hasil CBC Synthetic',exact=True).click()
        modal=labpage.get_by_role('dialog')
        modal.get_by_label('Status Order',exact=True).select_option('PROSES')
        modal.get_by_role('button',name='Simpan',exact=True).click()
        labrow.get_by_role('button',name='Ubah hasil CBC Synthetic',exact=True).click()
        modal.get_by_label('Status Order',exact=True).select_option('SELESAI')
        modal.get_by_label('Hasil Pemeriksaan',exact=True).fill('Hasil fixture sintetis terverifikasi')
        modal.get_by_role('button',name='Simpan',exact=True).click()
        expect(labrow.get_by_text('Selesai',exact=True)).to_be_visible()
        labpage.screenshot(path=str(evidence/'ancillary-result.png'))
        report['journeys'].append({'kind':'assigned_lab_result','ordered_process_complete':True})
        lab.close()
        nurse=context('nurse',768);page=open_page(nurse,state['visits']['nursing'],8)
        expect(page.locator('#igd-diagnosis-form')).to_have_count(0)
        for key,field,value,mode in [('sdki','diagnosa_keperawatan_sdki','D.QA','MASTER'),('slki','luaran_keperawatan_slki','Target manual synthetic','MANUAL'),('siki','intervensi_keperawatan_siki','I.QA','MASTER')]:
            page.locator(f'[name="{field}"]').fill(value)
            page.locator(f'[data-component-mode="{key}"]').select_option(mode)
        with page.expect_response(lambda response:'/langkah/8/draft/' in response.url and response.request.method=='POST') as got:
            page.get_by_role('button',name='Simpan Draft',exact=True).click()
        assert got.value.status==200,got.value.text()
        expect(page.locator('#igd-save-status')).to_contain_text('Draft tersimpan')
        page.reload();expect(page.locator('[name=luaran_keperawatan_slki]')).to_have_value('Target manual synthetic')
        expect(page.locator('[data-component-mode=siki]')).to_have_value('MASTER')
        report['journeys'].append({'kind':'nursing','independent_modes_persisted':True});nurse.close()
        doctor=context('doctor');page=open_page(doctor,state['visits']['rx'],8)
        page.get_by_role('button',name='Terapi / Obat',exact=True).click()
        rx=page.locator('#igd-medications')
        for level,item in zip(['class','generic','product'],state['catalogue']['normal']):
            rx.locator('#rx-'+level).select_option(str(item))
        rx.get_by_label('Kali per hari / interval jam').fill('2')
        rx.get_by_label('Dosis per pemberian',exact=True).fill('1')
        rx.get_by_label('Durasi (hari)').fill('3')
        rx.get_by_label('Rute pemberian',exact=True).select_option('PO')
        rx.get_by_label('Waktu pemberian',exact=True).select_option('PC')
        rx.get_by_role('button',name='Tambah ke Draft Resep',exact=True).click()
        rx.get_by_label('Depo farmasi tujuan').select_option(str(state['pharmacy_unit']))
        saved=click_action(page,rx.get_by_role('button',name='Simpan Draft Resep — Belum Dikirim',exact=True))
        page.get_by_role('button',name='Terapi / Obat',exact=True).click()
        expect(rx.get_by_text('Draft Dokter',exact=False)).to_be_visible()
        prescription_id=saved['prescription_id']
        rx_number=re.search(r'RSP-[a-f0-9]{24}',rx.inner_text()).group(0)
        click_action(page,rx.get_by_role('button',name='Tinjau Risiko & Kirim ke Farmasi',exact=True))
        page.get_by_role('button',name='Terapi / Obat',exact=True).click()
        expect(rx.get_by_text('Terkirim ke Farmasi',exact=False)).to_be_visible()
        rx.scroll_into_view_if_needed();page.screenshot(path=str(evidence/'prescription-submitted.png'))
        pharmacist=context('pharmacist');ph=pharmacist.new_page();ph.on('pageerror',lambda exc:report['page_errors'].append(str(exc)))
        ph.goto(base+'/pasien/farmasi/')
        row=ph.get_by_role('row').filter(has_text=rx_number)
        row.get_by_role('button',name='Proses',exact=True).click()
        row=ph.get_by_role('row').filter(has_text=rx_number)
        finish=row.locator('form').filter(has=ph.locator('input[value=selesai]'))
        version=int(finish.locator('[name=version]').input_value());key=finish.locator('[name=request_id]').input_value()
        csrf=finish.locator('[name=csrfmiddlewaretoken]').input_value()
        row.get_by_role('button',name='Selesaikan',exact=True).click()
        repeated=pharmacist.request.post(f'{base}/pasien/resep/{prescription_id}/proses/',data={'action':'selesai','version':version,'request_id':key,'reason':''},headers={'X-CSRFToken':csrf})
        assert repeated.status==200,repeated.text()
        assert repeated.json()['success']
        ph.goto(base+'/pasien/farmasi/?status=SELESAI')
        expect(ph.get_by_role('row').filter(has_text=rx_number)).to_be_visible()
        ph.screenshot(path=str(evidence/'pharmacy-completed.png'))
        report['journeys'].append({'kind':'prescription','id':prescription_id,'draft_submit_dispense_complete':True,'completion_replay':True})
        restricted_page=open_page(doctor,state['visits']['ppra'],8)
        restricted=post_action(doctor,restricted_page,state['visits']['ppra'],'prescription_save',{'serving_unit_id':state['pharmacy_unit'],'lines':[{'product_id':state['catalogue']['restricted'][-1],'kind':'OBAT','regimen':{'schema_version':1,'frequency':'FIXED','times_per_day':'1','dose':'1','dose_unit':'tablet','duration_days':'1','route':'PO'}}]})
        restricted_page.reload()
        held=post_action(doctor,restricted_page,state['visits']['ppra'],'prescription_submit',{'prescription_id':restricted['prescription_id'],'acknowledgements':[]})
        assert held['held'],held
        reviewer=context('reviewer');review_page=reviewer.new_page();review_page.goto(base+'/pasien/farmasi/')
        review_panel=review_page.get_by_role('heading',name='Tinjauan PPRA Menunggu Keputusan').locator('..')
        review_panel.get_by_label('Keputusan PPRA',exact=True).select_option('APPROVED')
        review_panel.get_by_label('Alasan keputusan PPRA',exact=True).fill('Persetujuan fixture sintetis oleh reviewer independen')
        review_panel.get_by_role('button',name='Simpan Keputusan PPRA',exact=True).click()
        restricted_page.reload()
        released=post_action(doctor,restricted_page,state['visits']['ppra'],'prescription_submit',{'prescription_id':restricted['prescription_id'],'acknowledgements':[]})
        assert not released['held'],released
        report['journeys'].append({'kind':'ppra','held_then_independent_review':True,'prescription_id':restricted['prescription_id']})
        reviewer.close();restricted_page.close()
        # Deliberate synthetic exemptions exercise final snapshot/print without fabricating normal findings.
        page.goto(f'{base}/pasien/kunjungan/{state["visits"]["rx"]}/asesmen-igd/?step=11')
        exemptions={k:'Batas fixture sintetis untuk pengujian integrasi' for k in ['triage','anamnesis','primary_survey','initial_vitals','screening','physical_exam','diagnosis','nursing','investigations','care','evaluation']}
        signed=post_action(doctor,page,state['visits']['rx'],'sign',{'section':'MEDIS','exemptions':exemptions})
        page.reload()
        finalized=post_action(doctor,page,state['visits']['rx'],'finalize',{'outcome':'NONE','resume':'Resume synthetic clinical expansion'})
        page.goto(f'{base}/pasien/kunjungan/{state["visits"]["rx"]}/asesmen-igd/resume/')
        expect(page.get_by_role('heading',name='Resep & Terapi Saat Ditandatangani')).to_be_visible()
        expect(page.get_by_text('Product Synthetic normal',exact=False)).to_be_visible()
        page.screenshot(path=str(evidence/'final-resume.png'))
        report['journeys'].append({'kind':'final_snapshot','revision_id':finalized['revision_id'],'prescription_printed':True})
        pharmacist.close();doctor.close();browser.close()
    assert not report['page_errors'],report['page_errors']
    (evidence/'browser.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--state',required=True)
    parser.add_argument('--evidence',required=True)
    args=parser.parse_args()
    run(args.state,args.evidence)
