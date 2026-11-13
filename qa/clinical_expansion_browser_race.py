"""Exercise a real delayed catalogue response without inventing API data."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from playwright.async_api import async_playwright,expect


async def run(state_path,evidence):
    state=json.loads(Path(state_path).read_text(encoding='utf-8'))
    received=asyncio.Event();release=asyncio.Event();finished=asyncio.Event()
    root_id,installation_id,_,_=state['catalogue']['ancillary']
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        context=await browser.new_context(ignore_https_errors=True,viewport={'width':375,'height':900})
        await context.add_cookies([{'name':'sessionid','value':state['users']['doctor']['session'],'url':state['base_url']}])
        page=await context.new_page();errors=[]
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        async def delayed(route):
            response=await route.fetch()
            parent=parse_qs(urlparse(route.request.url).query).get('parent',[''])[0]
            if parent==str(installation_id):
                received.set();await release.wait()
                await route.fulfill(response=response);finished.set()
            else:
                await route.fulfill(response=response)
        await page.route('**/katalog-penunjang/**',delayed)
        await page.goto(f'{state["base_url"]}/pasien/kunjungan/{state["visits"]["mobile"]}/asesmen-igd/?step=7')
        panel=page.locator('#igd-ancillary')
        root=panel.get_by_label('Kategori Utama',exact=True)
        await expect(root.get_by_role('option',name='Laboratorium Synthetic',exact=True)).to_have_count(1)
        await root.focus();await root.press('ArrowDown');await root.press('Enter')
        await expect(root).to_have_value(str(root_id))
        await panel.get_by_label('Instalasi',exact=True).select_option(str(installation_id))
        await asyncio.wait_for(received.wait(),10)
        await root.select_option('')
        release.set();await asyncio.wait_for(finished.wait(),10)
        group=panel.get_by_label('Kelompok',exact=True)
        await expect(group).to_be_disabled()
        await expect(group.get_by_role('option',name='Hematologi Synthetic',exact=True)).to_have_count(0)
        storage=await page.evaluate('({local:Object.fromEntries(Object.entries(localStorage)),session:Object.fromEntries(Object.entries(sessionStorage))})')
        stored=json.dumps(storage)
        assert not any(value in stored for value in list(state['patient_rm'].values())+['Diagnosis utama synthetic','Product Synthetic']),storage.keys()
        report={'delayed_real_response_discarded':True,'keyboard_parent_selection':True,'patient_data_in_persistent_storage':False,'storage_keys':{key:list(value) for key,value in storage.items()},'page_errors':errors}
        assert not errors,errors
        Path(evidence).write_text(json.dumps(report,indent=2),encoding='utf-8')
        await context.close();await browser.close()
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--state',required=True);parser.add_argument('--evidence',required=True)
    args=parser.parse_args();asyncio.run(run(args.state,args.evidence))
