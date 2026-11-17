"""Real browser journey against the owned synthetic loopback fixture."""
import asyncio,json,os,re,urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:18769'
private=Path(os.environ['TMPDIR'])/'professional-browser'/'final'/'fixture.json'
out=Path(__file__).resolve().parents[1]/'docs/superpowers/evidence/igd-professional-care/final-browser'
out.mkdir(parents=True,exist_ok=True)

async def main():
    fixture=json.loads(private.read_text())
    result={'fixture_only':True,'layouts':[],'actions':[],'page_errors':[],'fault_injection':'first execution persists then browser response is aborted; retry is real server replay'}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1366,'height':900})
        await context.add_cookies([{'name':key,'value':value,'url':BASE} for key,value in fixture['cookies'].items()])
        page=await context.new_page()
        page.on('pageerror',lambda error:result['page_errors'].append(str(error)))
        page.on('dialog',lambda dialog:asyncio.create_task(dialog.accept('Koreksi tagihan sintetis')))
        aborted=False
        async def transport(route):
            nonlocal aborted
            response=await route.fetch()
            body=route.request.post_data_json
            data=await response.json()
            result['actions'].append({'operation':body.get('operation'),'status':response.status,'result':data})
            if body.get('operation')=='professional_execute' and not aborted and response.ok:
                aborted=True
                await route.abort('failed')
            else:await route.fulfill(response=response)
        await page.route(re.compile('/asesmen-igd/aksi/'),transport)
        url=f'{BASE}/pasien/kunjungan/{fixture["visit"]}/asesmen-igd/?step=9'
        await page.goto(url.replace('step=9','step=8'),wait_until='domcontentloaded')
        assert 'Layanan QA' in await page.locator(f'#clinical-action-{fixture["planned"]}').inner_text()
        await page.goto(url,wait_until='domcontentloaded')
        await page.wait_for_function("document.querySelector('#professional-service').options.length>1")
        async def sweep(label):
            for width in (375,768,1366):
                await page.set_viewport_size({'width':width,'height':900})
                await page.wait_for_timeout(150)
                geometry=await page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow:document.documentElement.scrollWidth>innerWidth+1,forms:[...document.querySelectorAll('#professional-care-panel input,#professional-care-panel textarea,#professional-care-panel select')].filter(e=>e.offsetParent!==null).map(e=>({id:e.id,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right}))})''')
                geometry['phase']=label;result['layouts'].append(geometry)
                assert not geometry['overflow'],geometry
                await page.screenshot(path=str(out/f'{label}-{width}.png'),full_page=True)
        await sweep('initial')
        await page.select_option('#professional-note-format','SOAP')
        await page.locator('#professional-SOAP-subjektif').press_sequentially('Keluhan sintetis dengan spasi')
        await page.select_option('#professional-note-format','ADIME')
        await page.locator('#professional-ADIME-asesmen_gizi').fill('Asesmen gizi belum disimpan')
        await page.select_option('#professional-note-format','SOAP')
        assert await page.locator('#professional-SOAP-subjektif').input_value()=='Keluhan sintetis dengan spasi'
        await page.select_option('#professional-note-format','ADIME')
        assert await page.locator('#professional-ADIME-asesmen_gizi').input_value()=='Asesmen gizi belum disimpan'
        await page.locator('#professional-note-new').click()
        for code,expected in [('QA.FREE','gratis disetujui'),('QA.PENDING','Tarif belum ditetapkan')]:
            await page.select_option('#professional-service',str(fixture['extra'][code]))
            await page.wait_for_function("document.querySelector('#professional-performer').value!==''")
            await page.locator('#professional-preview').click()
            await page.wait_for_function('(text)=>document.querySelector("#professional-price").textContent.includes(text)',arg=expected)
        preview_state=await (await page.request.get(BASE+'/__qa/state')).json()
        assert preview_state['action_statuses']==['PLANNED'] and not preview_state['notes'] and not preview_state['charges'],preview_state
        # A delayed real response must not resurrect cleared child choices.
        async def delay_catalogue(route):
            response=await route.fetch()
            if 'service=' in route.request.url:await asyncio.sleep(.35)
            await route.fulfill(response=response)
        await page.route(re.compile('/profesional/katalog/'),delay_catalogue)
        await page.select_option('#professional-service',str(fixture['service']))
        await page.select_option('#professional-service','')
        await page.wait_for_timeout(600)
        assert await page.locator('#professional-performer').input_value()==''
        assert await page.locator('#professional-performer option').count()==1
        await page.unroute(re.compile('/profesional/katalog/'),delay_catalogue)
        await page.select_option('#professional-service',str(fixture['service']))
        await page.wait_for_function("document.querySelector('#professional-performer').value!==''")
        await page.select_option('#professional-source','PLANNED')
        await page.select_option('#professional-plan',str(fixture['planned']))
        await page.locator('#professional-preview').click()
        await page.wait_for_function("document.querySelector('#professional-price').textContent.includes('200000')")
        # First POST is really persisted, but its response is deliberately lost.
        await page.locator('#professional-execution-form button[type=submit]').click()
        await page.wait_for_function("!document.querySelector('#professional-error').hidden")
        state=await (await page.request.get(BASE+'/__qa/state')).json()
        assert state['actions']==1 and len(state['charges'])==1 and len(state['notes'])==1,state
        async with page.expect_navigation(wait_until='domcontentloaded'):
            await page.locator('#professional-execution-form button[type=submit]').click(click_count=2,force=True)
        state=await (await page.request.get(BASE+'/__qa/state')).json()
        assert state['actions']==1 and len(state['charges'])==1 and len(state['notes'])==1,state
        assert any(row['result'].get('replayed') for row in result['actions'] if row['operation']=='professional_execute')
        await page.locator('[data-professional-edit]').first.click()
        for field,text in {'subjektif':'Keluhan sintetis dengan spasi','objektif':'Temuan sintetis','asesmen':'Asesmen sintetis','plan':'Rencana sintetis'}.items():
            await page.locator(f'#professional-SOAP-{field}').fill('')
            await page.locator(f'#professional-SOAP-{field}').press_sequentially(text)
        async with page.expect_navigation(wait_until='domcontentloaded'):
            await page.locator('#professional-cppt-form button[type=submit]').click()
        await page.locator('[data-professional-edit]').first.click()
        assert await page.locator('#professional-SOAP-subjektif').input_value()=='Keluhan sintetis dengan spasi'
        await sweep('authored')
        async with page.expect_navigation(wait_until='domcontentloaded'):
            await page.locator('[data-professional-sign]').first.click()
        async with page.expect_navigation(wait_until='domcontentloaded'):
            await page.locator('[data-professional-verify]').first.click()
        state=await (await page.request.get(BASE+'/__qa/state')).json()
        assert state['notes'][0]['status']=='SIGNED' and state['notes'][0]['verifikasi_dpjp'] and state['verifications']==1,state
        # Verify real keyboard tab progression reaches the dedicated controls.
        await page.locator('#professional-note-format').focus()
        await page.keyboard.press('Tab')
        assert await page.evaluate("document.activeElement.id")=='professional-SOAP-subjektif'
        # Full unpaid void has confirmation and leaves performed care intact.
        async with page.expect_navigation(wait_until='domcontentloaded'):
            await page.locator('[data-professional-void]').first.click()
        state=await (await page.request.get(BASE+'/__qa/state')).json()
        assert state['actions']==1 and state['charges'][0]['is_void'],state
        # Complete a synthetic documentation-only finalization, not a patient disposition.
        async def raw_action(operation,fields):
            version=await page.locator('#igd-workflow').get_attribute('data-version')
            body=await page.evaluate('''async ({operation,fields,version})=>{
                const root=document.querySelector('#professional-care-panel');
                const r=await fetch(root.dataset.action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({operation,fields,version:Number(version),request_id:crypto.randomUUID()})});
                return {status:r.status,body:await r.json()};
            }''',{'operation':operation,'fields':fields,'version':version})
            assert body['status']==200,body
            await page.reload(wait_until='domcontentloaded')
        exemptions={key:'Pengecualian fixture sintetis; bukan pelayanan pasien nyata.' for key in ('triage','anamnesis','primary_survey','initial_vitals','screening','physical_exam','diagnosis','nursing','investigations','evaluation')}
        await raw_action('sign',{'section':'MEDIS','exemptions':exemptions})
        await raw_action('finalize',{'outcome':'NONE','resume':'Resume fixture sintetis untuk pengujian aplikasi.'})
        await page.goto(f'{BASE}/pasien/kunjungan/{fixture["visit"]}/asesmen-igd/resume/',wait_until='domcontentloaded')
        assert 'Keluhan sintetis dengan spasi' in await page.locator('body').inner_text()
        assert 'Verifikasi aplikasi' in await page.locator('body').inner_text()
        await sweep('final')
        result['final_state']=await (await page.request.get(BASE+'/__qa/state')).json()
        assert result['final_state']['workflow'][0]['status']=='FINAL'
        assert not result['page_errors'],result['page_errors']
        await browser.close()
    (out/'browser.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'layouts':len(result['layouts']),'page_errors':len(result['page_errors']),'actions':len(result['actions']),'final':result['final_state']['workflow'][0]['status']}))

asyncio.run(main())
