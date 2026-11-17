"""Real Chromium + separate project-venv DB verification for synthetic IGD visits.

smoke != acceptance. implemented exercises stable existing journeys only.
integrated requires --integration-ready and reviewed --contracts JSON for new
controls; missing bindings remain PENDING rather than fabricated acceptance.
No response bodies are substituted and no browser storage/trace is persisted.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa.igd_revision_fixture import load_state, validate_private_path
from playwright.async_api import async_playwright, expect


class Pending(Exception):
    pass


SCENARIOS = {
    'smoke': 'HTTP GET authenticated Step7/8/9/11; not feature acceptance',
    'diagnoses': 'Primary/secondary save, switch and DB/reload verification',
    'cito': 'CITO before full Step8; basket retained on parent reset; no charge',
    'professional': 'Step9 execution, CPPT sequential typing, signing and DPJP verification',
    'layout': '375/768/1366 diagnosis -> treatment -> nursing DOM order; no legacy editors/forms/IDs/overflow/errors',
    'nursing': 'Independent SDKI MASTER / SLKI MANUAL / SIKI MASTER, two saves/reopens and role boundaries',
    'suggestions': 'Exact diagnosis-linked ICD9 suggestions, planning creates no charge',
    'drafts': 'Action/medication tab switching retains unsaved notes and whitespace',
    'medication': 'Four-level selection, risk/TallMan, FIXED/INTERVAL instructions/real quantity preview, PRN manual quantity',
    'ancillary_metadata': 'Specimen/referral basket metadata survives parent reset and persists',
    'step7_single_path': 'Step 7 carries only the cascade: no legacy menu, no draft save, link advances to Step 8',
    'ancillary_race': 'Delayed real upstream response and page2 response cannot resurrect stale children',
    'pharmacy': 'Prescription submit, scoped dispense/complete same-key replay produces one owned charge',
    'snapshot': 'Retained legacy fields and signed snapshot/print frozen after real synthetic master mutation',
}
SUITES = {'smoke': ['smoke'], 'implemented': ['smoke', 'diagnoses', 'cito', 'professional'], 'integrated': list(SCENARIOS)}


class Harness:
    def __init__(self, args):
        self.args = args
        self.state_path = validate_private_path(args.state)
        self.state = load_state(self.state_path)
        self.evidence = validate_private_path(args.evidence)
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.contracts = json.loads(validate_private_path(args.contracts).read_text(encoding='utf-8')) if args.contracts else {}
        self.report = {'synthetic': True, 'suite': args.suite, 'integration_ready': args.integration_ready,
            'acceptance_complete': False, 'cases': [], 'page_errors': [], 'http': [], 'database': self.state['database'],
            'concurrency_proven': False, 'browser_storage_written_by_harness': False}
        self.base = self.state['base_url']
        self.contexts = []

    def contract(self, key):
        value = self.contracts.get(key)
        def missing(item):
            return item is None or item == '' or (isinstance(item, dict) and any(missing(child) for child in item.values()))
        if missing(value):
            raise Pending('Final implementation binding not reviewed: ' + key)
        return value

    @staticmethod
    def response_value(data, path):
        for key in path.split('.'):
            data = data[key]
        return data

    async def project(self, command, label=None):
        argv = [self.state['python'], str(Path(self.state['repo']) / 'qa/igd_revision_fixture.py'), command,
            '--settings', self.state['settings'], '--state', str(self.state_path)]
        if self.state['database']['vendor'] == 'postgresql':
            argv += ['--pg-name', self.state['database']['name']]
        if label:
            argv += ['--visit', label]
        child = await asyncio.create_subprocess_exec(*argv, cwd=self.state['repo'], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=60)
        except asyncio.TimeoutError:
            child.kill(); await child.wait(); raise AssertionError('Bounded project DB invocation timed out')
        if child.returncode:
            raise AssertionError('Project DB invocation failed: ' + stderr.decode('utf-8', errors='replace')[-3000:])
        return json.loads(stdout.decode('utf-8'))

    async def db(self, label):
        result = await self.project('readback', label)
        assert result['database'] == self.state['database']
        return result['visits'][label]

    async def context(self, role='doctor', width=1366):
        context = await self.browser.new_context(viewport={'width': width, 'height': 900})
        context.set_default_timeout(12000)
        await context.add_cookies([{'name': 'sessionid', 'value': self.state['users'][role]['session'], 'url': self.base}])
        # Permit only the observed public Bootstrap assets; clinical requests stay loopback.
        async def loopback_only(route):
            parsed = urlsplit(route.request.url)
            public_asset = (parsed.scheme == 'https' and parsed.hostname == 'cdn.jsdelivr.net' and
                not parsed.query and parsed.path.startswith(('/npm/bootstrap@5.3.3/', '/npm/bootstrap-icons@1.11.3/')) and
                route.request.method == 'GET' and route.request.resource_type in ('stylesheet', 'script', 'font'))
            if parsed.hostname not in ('127.0.0.1', None) and not public_asset:
                await route.abort()
            else:
                await route.continue_()
        await context.route('**/*', loopback_only)
        self.contexts.append(context)
        return context

    async def page(self, label, step=8, role='doctor', width=1366):
        context = await self.context(role, width)
        page = await context.new_page()
        page.on('pageerror', lambda error: self.report['page_errors'].append(str(error)))
        page.on('dialog', lambda dialog: asyncio.create_task(dialog.accept()))
        # Fetch the real upstream response, record it, and deliver it byte-for-byte unchanged.
        page.qa_actions = asyncio.Queue()
        async def capture(route):
            upstream = await route.fetch()
            data = await upstream.json()
            recorded = {'operation': route.request.post_data_json.get('operation'), 'status': upstream.status, 'result': data}
            self.report['http'].append(recorded)
            page.qa_actions.put_nowait(recorded)
            await route.fulfill(response=upstream)
        await page.route('**/asesmen-igd/aksi/', capture)
        await self.goto(page, label, step)
        return page

    async def goto(self, page, label, step):
        response = await page.goto(f'{self.base}/pasien/kunjungan/{self.state["visits"][label]}/asesmen-igd/?step={step}', wait_until='domcontentloaded')
        assert response and response.status == 200, f'GET step {step}: {response.status if response else None}'
        await expect(page.locator('#igd-workflow')).to_be_visible()
        return response

    async def version(self, page):
        value = await page.locator('#igd-step-form').get_attribute('data-version') if await page.locator('#igd-step-form').count() else None
        if value is None:
            value = await page.locator('#igd-workflow').get_attribute('data-version')
        return int(value)

    async def click_action(self, page, button, label):
        before = await self.version(page)
        async with page.expect_response(lambda response: '/asesmen-igd/aksi/' in response.url and response.request.method == 'POST') as found:
            await button.click()
        response = await found.value
        recorded = await asyncio.wait_for(page.qa_actions.get(), 15)
        data = recorded['result']
        assert response.status == recorded['status'] == 200 and data.get('success') is True, recorded
        assert type(data.get('version')) is int and data['version'] >= before + (0 if data.get('replayed') else 1), data
        actual = await self.db(label)
        assert actual['workflow']['version'] == data['version'], actual['workflow']
        return data

    async def raw_action(self, page, label, operation, fields, expected=200):
        before = await self.version(page)
        token = await page.locator('[name=csrfmiddlewaretoken]').first.input_value()
        response = await page.context.request.post(f'{self.base}/pasien/kunjungan/{self.state["visits"][label]}/asesmen-igd/aksi/',
            data={'operation': operation, 'fields': fields, 'version': before, 'request_id': str(uuid4())}, headers={'X-CSRFToken': token})
        assert response.status == expected, {'operation': operation, 'status': response.status, 'body': await response.text()}
        if expected != 200:
            return None
        data = await response.json()
        assert data.get('success') is True and data.get('version') == before + 1, data
        assert (await self.db(label))['workflow']['version'] == data['version']
        self.report['http'].append({'operation': operation, 'status': response.status, 'result': data})
        await page.reload(wait_until='domcontentloaded')
        assert await self.version(page) == data['version']
        return data

    async def storage(self, page):
        stored = await page.evaluate('({local:Object.fromEntries(Object.entries(localStorage)),session:Object.fromEntries(Object.entries(sessionStorage))})')
        serialized = json.dumps(stored)
        tokens = list(self.state['patient_rm'].values()) + ['SYNTHETIC IGD', 'Keluhan sintetis', 'Product Synthetic', 'SYNTHETIC historical']
        assert not any(token in serialized for token in tokens), 'Clinical content found in persistent browser storage'
        return {key: list(values) for key, values in stored.items()}

    async def smoke(self):
        checks = []
        for label, width in [('mobile', 375), ('tablet', 768), ('desktop', 1366)]:
            page = await self.page(label, width=width)
            for step in (7, 8, 9, 11):
                await self.goto(page, label, step)
                checks.append({'width': width, 'step': step, 'status': 200})
            await self.storage(page)
        return {'get_checks': checks, 'feature_acceptance': False}

    async def diagnoses(self):
        for label, width in [('mobile', 375), ('tablet', 768), ('desktop', 1366)]:
            page = await self.page(label, width=width)
            panel = page.locator('#igd-diagnoses')
            for suffix in ('utama', 'sekunder'):
                await panel.get_by_label('Diagnosis manual / istilah pencarian master').fill(f'SYNTHETIC Diagnosis {suffix} {label}')
                if suffix == 'utama':
                    await panel.get_by_role('checkbox', name='Diagnosis Utama', exact=True).check()
                await self.click_action(page, panel.get_by_role('button', name='Simpan Diagnosis', exact=True), label)
                await expect(page.locator('#igd-step-form')).to_have_attribute('data-version', str((await self.db(label))['workflow']['version']))
            row = panel.locator('article').filter(has_text=f'SYNTHETIC Diagnosis sekunder {label}')
            await row.get_by_role('button', name='Edit / Jadikan Utama').click()
            await panel.get_by_role('checkbox', name='Diagnosis Utama', exact=True).check()
            await self.click_action(page, panel.get_by_role('button', name='Simpan Diagnosis', exact=True), label)
            await page.reload(wait_until='domcontentloaded')
            actual = await self.db(label)
            rows = [row for row in actual['diagnoses'] if row['active']]
            assert len(rows) == 2 and sum(row['is_primary'] for row in rows) == 1, rows
            assert next(row for row in rows if row['is_primary'])['nama'] == f'SYNTHETIC Diagnosis sekunder {label}'
            assert not actual['charges']
            await expect(panel.locator('article')).to_have_count(2)
            await self.storage(page)
        return {'widths': [375, 768, 1366], 'primary_switch_persisted': True, 'charge_count': 0}

    async def select_ancillary(self, page, key):
        panel = page.locator('#igd-ancillary')
        for name, item in zip(['Kategori Utama', 'Instalasi', 'Kelompok', 'Item Pemeriksaan'], self.state['catalogue'][key]):
            select = panel.get_by_label(name, exact=True)
            await expect(select.locator(f'option[value="{item}"]')).to_have_count(1)
            await select.select_option(str(item))
        return panel

    async def cito(self):
        label = 'ancillary'; page = await self.page(label, 7)
        assert not (await self.db(label))['diagnoses']
        panel = await self.select_ancillary(page, 'ancillary')
        await panel.get_by_label('Indikasi klinis / diagnosis kerja').fill('SYNTHETIC CITO before full Step8')
        await panel.get_by_label('Prioritas', exact=True).select_option('CITO')
        await panel.get_by_role('button', name='Tambah ke Daftar Order').click()
        await panel.get_by_label('Kategori Utama', exact=True).select_option('')
        await expect(page.locator('#anc-basket').get_by_role('listitem')).to_have_count(1)
        await self.click_action(page, panel.get_by_role('button', name='Kirim Semua Order Terpilih'), label)
        await page.reload(wait_until='domcontentloaded')
        actual = await self.db(label)
        assert len(actual['orders']) == 1 and actual['orders'][0]['prioritas'] == 'CITO' and not actual['charges'], actual
        assert not actual['nursing']['diagnosa_keperawatan_sdki']
        return {'cito_before_step8': True, 'basket_retained': True, 'no_charge': True}

    async def professional(self, label='professional'):
        page = await self.page(label, 9)
        await expect(page.locator('#professional-care-panel')).to_be_visible()
        await page.select_option('#professional-service', str(self.state['professional']['service']))
        await page.wait_for_function("document.querySelector('#professional-performer').value!==''")
        await page.select_option('#professional-source', 'PLANNED' if label == 'professional' else 'DIRECT')
        if label == 'professional':
            await page.select_option('#professional-plan', str(self.state['professional']['plans'][label]))
        await page.locator('#professional-preview').click()
        await expect(page.locator('#professional-price')).to_contain_text('200000')
        before = await self.db(label)
        assert not before['charges'] and not before['notes']
        await self.click_action(page, page.locator('#professional-execution-form button[type=submit]'), label)
        await page.reload(wait_until='domcontentloaded')
        actual = await self.db(label)
        assert len(actual['charges']) == len(actual['notes']) == 1 and actual['actions'][0]['execution_status'] == 'PERFORMED'
        await page.locator('[data-professional-edit]').first.click()
        payload = {'subjektif': 'Keluhan sintetis dengan spasi berurutan', 'objektif': 'Temuan sintetis', 'asesmen': 'Asesmen sintetis', 'plan': 'Rencana sintetis'}
        for field, value in payload.items():
            control = page.locator('#professional-SOAP-' + field)
            await control.fill(''); await control.press_sequentially(value, delay=3)
            await expect(control).to_have_value(value)
        await self.click_action(page, page.locator('#professional-cppt-form button[type=submit]'), label)
        await page.reload(wait_until='domcontentloaded')
        await self.click_action(page, page.locator('[data-professional-sign]').first, label)
        await page.reload(wait_until='domcontentloaded')
        await self.click_action(page, page.locator('[data-professional-verify]').first, label)
        await page.reload(wait_until='domcontentloaded')
        actual = await self.db(label)
        assert actual['notes'][0]['status'] == 'SIGNED' and actual['notes'][0]['verifikasi_dpjp'] and actual['verification_count'] == 1, actual
        assert actual['notes'][0]['subjektif'] == payload['subjektif']
        await self.storage(page)
        await page.screenshot(path=str(self.evidence / f'{label}-signed.png'), full_page=True)
        return {'execution': True, 'cppt_signed': True, 'dpjp_verified': True, 'charges': 1, 'sequential_whitespace_preserved': True}

    async def layout(self):
        results = []
        for label, width in [('mobile', 375), ('tablet', 768), ('desktop', 1366)]:
            page = await self.page(label, width=width)
            await expect(page.locator('#igd-diagnoses')).to_be_visible()
            await expect(page.locator('#igd-action-panel')).to_have_count(1)
            await expect(page.locator('#igd-step-form')).to_have_count(1)
            geometry = await page.evaluate('''() => {
                const roots=['#igd-diagnoses','#igd-action-panel','#igd-step-form'].map(s=>document.querySelector(s));
                const ids=[...document.querySelectorAll('[id]')].map(n=>n.id);
                return {order:roots.slice(1).every((n,i)=>!!(roots[i].compareDocumentPosition(n)&Node.DOCUMENT_POSITION_FOLLOWING)),
                    nested:document.querySelectorAll('form form').length,duplicateIds:ids.filter((id,i)=>ids.indexOf(id)!==i),
                    width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
                    legacyEditors:document.querySelectorAll('input[name^="tatalaksana_"],textarea[name^="tatalaksana_"],select[name^="tatalaksana_"]').length};
            }''')
            assert geometry['order'] and geometry['nested'] == geometry['legacyEditors'] == 0 and not geometry['duplicateIds'] and geometry['scrollWidth'] <= width + 1, geometry
            await self.storage(page)
            await page.screenshot(path=str(self.evidence / f'integrated-layout-{width}.png'), full_page=True)
            results.append(geometry)
        # A browser parser repairs nested forms. Verify raw GET markup too.
        from html.parser import HTMLParser
        class FormNesting(HTMLParser):
            depth = 0; nested = False
            def handle_starttag(self, tag, attrs):
                if tag == 'form':
                    self.nested |= self.depth > 0; self.depth += 1
            def handle_endtag(self, tag):
                if tag == 'form': self.depth = max(0, self.depth - 1)
        response = await page.context.request.get(page.url)
        assert response.status == 200
        parser = FormNesting(); parser.feed(await response.text()); assert not parser.nested, 'Raw HTML contains nested forms'
        return {'viewports': results, 'raw_html_no_nested_forms': True}

    async def nursing(self):
        label = 'nursing'; page = await self.page(label, role='nurse')
        await expect(page.locator('#igd-diagnosis-form')).to_have_count(0)
        for save_number in (1, 2):
            for key, field, mode, value in [('sdki', 'diagnosa_keperawatan_sdki', 'MASTER', self.state['catalogue']['nursing']['sdki']),
                    ('slki', 'luaran_keperawatan_slki', 'MANUAL', f'SYNTHETIC manual outcome {save_number}'),
                    ('siki', 'intervensi_keperawatan_siki', 'MASTER', self.state['catalogue']['nursing']['siki'])]:
                await page.locator(f'[data-component-mode="{key}"]').select_option(mode)
                await page.locator(f'[name="{field}"]').fill(value)
            async with page.expect_response(lambda r: '/langkah/8/draft/' in r.url and r.request.method == 'POST') as found:
                await page.get_by_role('button', name='Simpan Draft', exact=True).click()
            response = await found.value; data = await response.json()
            assert response.status == 200 and data.get('success') is True and type(data.get('version')) is int, data
            actual = await self.db(label)
            assert actual['workflow']['version'] == data['version']
            for key, expected_mode in [('sdki', 'MASTER'), ('slki', 'MANUAL'), ('siki', 'MASTER')]:
                assert actual['nursing']['diagnosis_provenance']['components'][key]['mode'] == expected_mode
            assert actual['nursing']['luaran_keperawatan_slki'] == f'SYNTHETIC manual outcome {save_number}'
            await page.reload(wait_until='domcontentloaded')
            await expect(page.locator('[data-component-mode=siki]')).to_have_value('MASTER')
        await self.raw_action(page, label, 'diagnosis_set', {'changes': [{'op': 'upsert', 'temp_id': 'forged', 'mode': 'MANUAL', 'text': 'SYNTHETIC forbidden', 'is_primary': True}]}, expected=403)
        assert not (await self.db(label))['diagnoses']
        doctor = await self.page(label)
        for key in ('sdki', 'slki', 'siki'):
            await expect(doctor.locator(f'[data-component-mode={key}]')).to_be_disabled()
        return {'save_reopen_count': 2, 'medical_nursing_separation': True}

    async def suggestions(self):
        # Bind the final suggestion surface, not a guessed future endpoint/API.
        selector = self.contract('procedure_suggestions')
        label = 'roles'; page = await self.page(label)
        diagnosis = self.state['catalogue']['icd10']
        await self.raw_action(page, label, 'diagnosis_set', {'changes': [{'op': 'upsert', 'temp_id': 'linked', 'mode': 'MASTER', 'code': diagnosis['code'], 'text': '', 'is_primary': True}]})
        await expect(page.locator(selector)).to_contain_text(self.state['catalogue']['icd9']['code'])
        assert self.state['catalogue']['unrelated_icd9'] not in await page.locator(selector).inner_text()
        items = self.contract('procedure_suggestion_items')
        attribute = self.contract('procedure_suggestion_code_attribute')
        codes = await page.locator(items).evaluate_all('(nodes, attr)=>nodes.map(node=>node.getAttribute(attr))', attribute)
        assert codes == [self.state['catalogue']['icd9']['code']], codes
        await self.raw_action(page, label, 'plan_action', {'jenis': 'ICD9', 'mode': 'MASTER', 'kode': self.state['catalogue']['icd9']['code'], 'nama': '', 'quantity': '1', 'catatan_klinis': 'SYNTHETIC plan without execution'})
        actual = await self.db(label)
        assert len(actual['actions']) == 1 and actual['actions'][0]['execution_status'] == 'PLANNED' and not actual['charges'] and not actual['notes']
        return {'linked_code': self.state['catalogue']['icd9']['code'], 'unrelated_excluded': True, 'planning_no_charge': True}

    async def drafts(self):
        action_note = self.contract('action_clinical_note')
        page = await self.page('roles')
        await page.locator(action_note).press_sequentially('SYNTHETIC draft action with spaces', delay=5)
        await page.locator('[data-care-tab]').filter(has_text='Terapi').click()
        await page.locator('#rx-instructions').press_sequentially('SYNTHETIC draft medication with spaces', delay=5)
        await page.locator('[data-care-tab]').filter(has_text='Tindakan').click()
        await expect(page.locator(action_note)).to_have_value('SYNTHETIC draft action with spaces')
        await page.locator('[data-care-tab]').filter(has_text='Terapi').click()
        await expect(page.locator('#rx-instructions')).to_have_value('SYNTHETIC draft medication with spaces')
        await self.storage(page)
        return {'unsaved_action_and_medication_drafts_retained': True}

    async def medication(self):
        controls = self.contract('medication')
        output = []
        for label, frequency in [('rx', 'FIXED'), ('interval', 'INTERVAL'), ('prn', 'PRN')]:
            page = await self.page(label)
            previews = []
            async def capture_preview(route):
                upstream = await route.fetch()
                body = await upstream.json()
                recorded = {'status': upstream.status, 'result': body}
                previews.append(recorded)
                self.report['http'].append({'operation': 'quantity_preview', **recorded})
                await route.fulfill(response=upstream)
            await page.route(controls['quantity_preview_route'], capture_preview)
            await page.locator('[data-care-tab]').filter(has_text='Terapi').click()
            rx = page.locator('#igd-medications')
            await rx.locator(controls['kind']).select_option('OBAT')
            for level, item in zip(('class', 'generic', 'product'), self.state['catalogue']['normal']):
                select = rx.locator('#rx-' + level)
                await expect(select.locator(f'option[value="{item}"]')).to_have_count(1)
                await select.select_option(str(item))
            await rx.locator(controls['frequency']).select_option(frequency)
            await rx.get_by_label('Kali per hari / interval jam').fill('8' if frequency == 'INTERVAL' else '2')
            await rx.get_by_label('Dosis per pemberian', exact=True).fill('1')
            await rx.get_by_label('Durasi (hari)').fill('3')
            await rx.get_by_label('Rute pemberian', exact=True).select_option('PO')
            instructions = 'SYNTHETIC instructions ' + frequency
            await rx.locator('#rx-instructions').fill(instructions)
            preview = rx.locator(controls['quantity_preview'])
            if frequency == 'PRN':
                await expect(preview).to_contain_text(re.compile('manual', re.I))
                await rx.locator(controls['prn_indication']).fill('SYNTHETIC PRN indication')
                await rx.locator(controls['manual_quantity']).fill('4')
                await rx.locator(controls['quantity_reason']).fill('SYNTHETIC explicit manual quantity')
                quantity = '4.0000'
            else:
                await expect(preview).to_contain_text('9' if frequency == 'INTERVAL' else '6')
                quantity = '9.0000' if frequency == 'INTERVAL' else '6.0000'
            assert previews, 'Quantity preview must have a real upstream HTTP response'
            latest = previews[-1]
            assert latest['status'] == 200 and latest['result'].get('success') is True, latest
            manual = self.response_value(latest['result'], controls['preview_manual_path'])
            assert manual is (frequency == 'PRN'), latest
            if frequency != 'PRN':
                from decimal import Decimal
                assert Decimal(str(self.response_value(latest['result'], controls['preview_quantity_path']))) == Decimal(quantity), latest
            await rx.get_by_role('button', name='Tambah ke Draft Resep', exact=True).click()
            await rx.get_by_label('Depo farmasi tujuan').select_option(str(self.state['pharmacy_unit']))
            await self.click_action(page, rx.get_by_role('button', name='Simpan Draft Resep — Belum Dikirim', exact=True), label)
            await page.reload(wait_until='domcontentloaded')
            actual = await self.db(label); line = actual['prescriptions'][0]['items'][0]
            assert line['regimen'][controls['instructions_regimen_key']] == instructions and line['regimen']['frequency'] == frequency and line['quantity_decimal'] == quantity, line
            assert not actual['charges']
            output.append({'frequency': frequency, 'quantity': quantity, 'instructions_persisted': True})
        risk_page = await self.page('rx')
        await risk_page.locator('[data-care-tab]').filter(has_text='Terapi').click()
        for level, item in zip(('class', 'generic', 'product'), self.state['catalogue']['risk']):
            select = risk_page.locator('#rx-' + level)
            await expect(select.locator(f'option[value="{item}"]')).to_have_count(1)
            await select.select_option(str(item))
        await expect(risk_page.locator(controls['risk_display'])).to_contain_text('SYNthetic RISK')
        await expect(risk_page.locator(controls['risk_display'])).to_contain_text('HIGH_ALERT')
        return {'regimens': output, 'selected_risk_and_tallman_visible': True, 'preview_source': 'real upstream HTTP, no substitutions'}

    async def ancillary_metadata(self):
        label = 'race'; page = await self.page(label, 7)
        panel = await self.select_ancillary(page, 'ancillary_metadata')
        specimen = panel.locator('#anc-specimen')
        if await specimen.evaluate('el=>el.tagName') == 'SELECT':
            await specimen.select_option('SYNTHETIC EDTA')
        else:
            await specimen.fill('SYNTHETIC EDTA')
        await panel.locator('#anc-external-destination').fill('SYNTHETIC Referral Laboratory')
        await panel.get_by_label('Indikasi klinis / diagnosis kerja').fill('SYNTHETIC metadata persistence')
        await panel.get_by_label('Prioritas', exact=True).select_option('CITO')
        await panel.get_by_role('button', name='Tambah ke Daftar Order').click()
        await panel.get_by_label('Kategori Utama', exact=True).select_option('')
        await expect(page.locator('#anc-basket').get_by_role('listitem')).to_have_count(1)
        await self.click_action(page, panel.get_by_role('button', name='Kirim Semua Order Terpilih'), label)
        actual = await self.db(label)
        preparation = actual['orders'][0]['preparation']
        assert preparation['specimen'] == 'SYNTHETIC EDTA' and preparation['external_destination'] == 'SYNTHETIC Referral Laboratory'
        assert not actual['charges']
        return {'metadata_retained_and_persisted': True}

    async def step7_single_path(self):
        page = await self.page('race', 7)
        await expect(page.locator('#igd-workflow')).to_be_visible()
        await expect(page.locator('#igd-ancillary')).to_be_visible()
        for legacy in ('Order & Hasil Tercatat', 'Lampiran Hasil / Dokumen', 'Unggah Lampiran', 'Catat hasil / pembaruan operasional'):
            await expect(page.get_by_text(legacy)).to_have_count(0)
        await expect(page.locator('#igd-step-form button[type="submit"]')).to_have_count(0)
        await expect(page.locator('#igd-step-form [name^="penunjang_"]')).to_have_count(0)
        for number in (1, 2, 3, 4):
            await expect(page.locator(f'#anc-level-{number}')).to_have_count(1)
        for key in ('fasting', 'pregnancy', 'contrast_allergy', 'specimen', 'site', 'region',
                    'side', 'contrast', 'external_destination'):
            await expect(page.locator(f'#anc-{key}')).to_have_count(1)
        actions = len(self.report['http'])
        await page.get_by_role('link', name='Lanjut ke Penetapan Diagnosis').click()
        await page.wait_for_load_state('domcontentloaded')
        assert 'step=8' in page.url, page.url
        assert len(self.report['http']) == actions, 'Step 7 navigation must not submit a draft or action'
        await expect(page.locator('#igd-workflow')).to_be_visible()
        return {'single_surface': True, 'no_legacy_menu': True, 'advanced_without_draft_save': True}

    async def ancillary_race(self):
        page = await self.page('race', 7, width=375)
        panel = page.locator('#igd-ancillary')
        received = asyncio.Event(); release = asyncio.Event(); finished = asyncio.Event()
        installation = self.state['catalogue']['ancillary'][1]
        async def delayed(route):
            upstream = await route.fetch()
            query = parse_qs(urlsplit(route.request.url).query)
            if query.get('parent') == [str(installation)]:
                received.set(); await asyncio.wait_for(release.wait(), 15)
                await route.fulfill(response=upstream); finished.set()
            else:
                await route.fulfill(response=upstream)
        await page.route('**/katalog-penunjang/**', delayed)
        root = panel.get_by_label('Kategori Utama', exact=True)
        await root.select_option(str(self.state['catalogue']['ancillary'][0]))
        install = panel.get_by_label('Instalasi', exact=True)
        await expect(install.locator(f'option[value="{installation}"]')).to_have_count(1)
        await install.select_option(str(installation))
        await asyncio.wait_for(received.wait(), 10)
        await root.select_option(''); release.set(); await asyncio.wait_for(finished.wait(), 10)
        await expect(panel.get_by_label('Kelompok', exact=True)).to_be_disabled()
        await page.unroute('**/katalog-penunjang/**', delayed)
        # Pagination binding is supplied only after the final control is inspected.
        load_more = self.contract('ancillary_load_more')
        await self.select_ancillary(page, 'ancillary')
        paged = asyncio.Event(); release_page = asyncio.Event(); done_page = asyncio.Event()
        async def delayed_page(route):
            upstream = await route.fetch()
            query = parse_qs(urlsplit(route.request.url).query)
            if query.get('page') == ['2']:
                paged.set(); await asyncio.wait_for(release_page.wait(), 15)
                await route.fulfill(response=upstream); done_page.set()
            else: await route.fulfill(response=upstream)
        await page.route('**/katalog-penunjang/**', delayed_page)
        await page.locator(load_more).click(); await asyncio.wait_for(paged.wait(), 10)
        await root.select_option(''); release_page.set(); await asyncio.wait_for(done_page.wait(), 10)
        items = panel.get_by_label('Item Pemeriksaan', exact=True)
        await expect(items).to_be_disabled()
        assert await items.locator('option').count() <= 1
        await self.storage(page)
        return {'real_delayed_parent_discarded': True, 'real_delayed_page2_discarded': True}

    async def pharmacy(self):
        label = 'rx'; page = await self.page(label)
        actual = await self.db(label)
        if not actual['prescriptions']:
            raise Pending('Run medication scenario first to create a browser-authored prescription')
        prescription = actual['prescriptions'][0]; rxid = prescription['id']
        await page.locator('[data-care-tab]').filter(has_text='Terapi').click()
        await self.click_action(page, page.locator('#igd-medications').get_by_role('button', name='Tinjau Risiko & Kirim ke Farmasi', exact=True), label)
        actual = await self.db(label); assert actual['prescriptions'][0]['status'] == 'DIKIRIM'
        unrelated = await self.context('unrelated_pharmacist')
        response = await unrelated.request.get(self.base + '/pasien/farmasi/')
        assert response.status == 200
        assert f'/pasien/resep/{rxid}/proses/' not in await response.text(), 'Unrelated depo exposes prescription mutation form'
        pharmacist = await self.context('pharmacist'); ph = await pharmacist.new_page()
        response = await ph.goto(self.base + '/pasien/farmasi/'); assert response.status == 200
        row = ph.locator('tr').filter(has=ph.locator(f'form[action*="/resep/{rxid}/proses/"]'))
        async with ph.expect_response(lambda r: f'/resep/{rxid}/proses/' in r.url and r.request.method == 'POST') as found:
            await row.get_by_role('button', name='Proses', exact=True).click()
        response = await found.value; assert response.status in (200, 302)
        assert (await self.db(label))['prescriptions'][0]['status'] == 'DISPENSING'
        await ph.reload(wait_until='domcontentloaded')
        row = ph.locator('tr').filter(has=ph.locator(f'form[action*="/resep/{rxid}/proses/"]'))
        finish = row.locator('form').filter(has=ph.locator('input[value=selesai]'))
        version = int(await finish.locator('[name=version]').input_value())
        key = await finish.locator('[name=request_id]').input_value()
        token = await finish.locator('[name=csrfmiddlewaretoken]').input_value()
        async with ph.expect_response(lambda r: f'/resep/{rxid}/proses/' in r.url and r.request.method == 'POST') as found:
            await row.get_by_role('button', name='Selesaikan', exact=True).click()
        response = await found.value; assert response.status in (200, 302)
        actual = await self.db(label); assert actual['prescriptions'][0]['status'] == 'SELESAI'
        replay = await pharmacist.request.post(f'{self.base}/pasien/resep/{rxid}/proses/', data={'action': 'selesai', 'version': version, 'request_id': key, 'reason': ''}, headers={'X-CSRFToken': token})
        assert replay.status == 200 and (await replay.json())['success']
        actual = await self.db(label)
        charges = [charge for charge in actual['charges'] if charge['sumber'] == 'FARMASI']
        assert len(charges) == 1 and actual['prescriptions'][0]['operations'] == 2
        assert actual['prescriptions'][0]['items'][0]['billing_item_id'] == charges[0]['id']
        return {'scoped_pharmacist': True, 'completion_replay': True, 'owned_charge_count': 1, 'concurrency_proven': False}

    async def snapshot(self):
        label = 'snapshot'
        before = await self.db(label)
        assert before['legacy'] == self.state['legacy']
        await self.professional(label)
        page = await self.page(label, 11)
        saved = await self.raw_action(page, label, 'prescription_save', {
            'serving_unit_id': self.state['pharmacy_unit'],
            'lines': [{'product_id': self.state['catalogue']['normal'][-1], 'kind': 'OBAT',
                'regimen': {'schema_version': 1, 'frequency': 'FIXED', 'times_per_day': '2',
                    'dose': '1', 'dose_unit': 'tablet', 'duration_days': '3', 'route': 'PO', 'timing': 'PC'}}]})
        rxid = saved['prescription_id']
        await self.raw_action(page, label, 'prescription_submit', {'prescription_id': rxid, 'acknowledgements': []})
        pharmacist = await self.context('pharmacist')
        ph = await pharmacist.new_page()
        response = await ph.goto(self.base + '/pasien/farmasi/')
        assert response.status == 200
        token = await ph.locator('[name=csrfmiddlewaretoken]').first.input_value()
        for operation, expected_status in [('dispensing', 'DISPENSING'), ('selesai', 'SELESAI')]:
            current = (await self.db(label))['prescriptions'][0]
            result = await pharmacist.request.post(f'{self.base}/pasien/resep/{rxid}/proses/',
                data={'action': operation, 'version': current['version'], 'request_id': str(uuid4()), 'reason': ''},
                headers={'X-CSRFToken': token})
            data = await result.json()
            assert result.status == 200 and data.get('success') is True and data['version'] == current['version'] + 1, data
            actual = await self.db(label)
            assert actual['prescriptions'][0]['status'] == expected_status and actual['prescriptions'][0]['version'] == data['version']
        # Pharmacy changes invalidate workflow signatures; sign only after actual completion.
        await page.reload(wait_until='domcontentloaded')
        exemptions = {key: 'Explicit synthetic fixture exemption; not actual patient care' for key in ['triage', 'anamnesis', 'primary_survey', 'initial_vitals', 'screening', 'physical_exam', 'diagnosis', 'nursing', 'investigations', 'evaluation']}
        await self.raw_action(page, label, 'sign', {'section': 'MEDIS', 'exemptions': exemptions})
        await self.raw_action(page, label, 'finalize', {'outcome': 'NONE', 'resume': 'SYNTHETIC revision snapshot verification'})
        original = await self.db(label)
        assert original['revisions'][0]['legacy'] == self.state['legacy'], original['revisions']
        assert original['notes'][0]['status'] == 'SIGNED' and original['verification_count'] == 1
        assert original['prescriptions'][0]['status'] == 'SELESAI'
        url = f'{self.base}/pasien/kunjungan/{self.state["visits"][label]}/asesmen-igd/resume/'
        response = await page.goto(url); assert response.status == 200
        first = await page.locator('body').inner_text()
        for expected in [self.state['legacy']['tatalaksana_resusitasi'], self.state['legacy']['tatalaksana_terapi'],
                'Product Synthetic normal', 'PPA Sintetis', 'Keluhan sintetis dengan spasi berurutan']:
            assert expected in first, 'Signed resume missing ' + expected
        await page.emulate_media(media='print')
        await page.pdf(path=str(self.evidence / 'snapshot-before.pdf'))
        mutation = await self.project('mutate-master')
        assert mutation['synthetic_master_mutated'] is True and mutation['readback']['product']['nama'] == 'SYNTHETIC changed master'
        # Read back the exact signed target through another process after live master changes.
        after = await self.db(label)
        assert after['revisions'] == original['revisions']
        response = await page.goto(url); assert response.status == 200
        assert await page.locator('body').inner_text() == first
        assert 'SYNTHETIC changed master' not in first and 'SYNTHETIC changed performer' not in first
        await page.pdf(path=str(self.evidence / 'snapshot-after.pdf'))
        return {'legacy_values_preserved': True, 'revision_digest_unchanged': True, 'print_text_unchanged': True,
            'completed_prescription_and_signed_verified_note_in_snapshot': True,
            'master_change_readback': mutation['readback']}

    async def run(self):
        chosen = self.args.scenario or SUITES[self.args.suite]
        if self.args.suite == 'integrated' and not self.args.integration_ready:
            raise ValueError('Integrated UI acceptance requires --integration-ready after final application integration/restart.')
        async with async_playwright() as playwright:
            self.browser = await playwright.chromium.launch(headless=True)
            try:
                for name in chosen:
                    try:
                        detail = await getattr(self, name)()
                        # Snapshot without embedded changed entities is explicitly incomplete.
                        status = 'pending' if name == 'snapshot' and detail.get('pending_snapshot_depth') else 'passed'
                        self.report['cases'].append({'scenario': name, 'status': status, 'detail': detail})
                    except Pending as exc:
                        self.report['cases'].append({'scenario': name, 'status': 'pending', 'reason': str(exc)})
                    except Exception as exc:
                        self.report['cases'].append({'scenario': name, 'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)})
                    finally:
                        for context in self.contexts:
                            await context.close()
                        self.contexts.clear()
                for name, purpose in SCENARIOS.items():
                    if name not in chosen:
                        self.report['cases'].append({'scenario': name, 'status': 'pending', 'reason': 'Not selected / final integration pending', 'purpose': purpose})
            finally:
                await self.browser.close()
        self.report['acceptance_complete'] = self.args.suite == 'integrated' and all(row['status'] == 'passed' for row in self.report['cases']) and not self.report['page_errors']
        (self.evidence / 'browser-report.json').write_text(json.dumps(self.report, indent=2), encoding='utf-8')
        counts = {status: sum(row['status'] == status for row in self.report['cases']) for status in ('passed', 'failed', 'pending')}
        print(json.dumps({'report': str(self.evidence / 'browser-report.json'), 'counts': counts, 'page_errors': len(self.report['page_errors']), 'acceptance_complete': self.report['acceptance_complete']}))
        return 1 if counts['failed'] or self.report['page_errors'] or (self.args.suite == 'integrated' and counts['pending']) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--suite', choices=SUITES, default='smoke')
    parser.add_argument('--scenario', action='append', choices=SCENARIOS)
    parser.add_argument('--integration-ready', action='store_true')
    parser.add_argument('--contracts', help='Private reviewed final selector bindings; never guessed')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(Harness(args).run()))


if __name__ == '__main__':
    main()
