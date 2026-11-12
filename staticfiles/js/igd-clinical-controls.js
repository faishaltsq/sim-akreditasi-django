(() => {
  'use strict';
  const root = document.getElementById('igd-workflow');
  const main = document.getElementById('igd-step-form');
  if (!root || !main) return;
  const errors = document.getElementById('igd-errors');
  const status = document.getElementById('igd-save-status');
  const dirtyForms = new Set();
  let busy = false;
  let navigating = false;
  const csrf = () => main.querySelector('[name=csrfmiddlewaretoken]').value;
  const version = () => Number(main.dataset.version);
  function message(text) { errors.textContent = text; errors.hidden = false; errors.focus(); }
  function changed(element = main) { element.dispatchEvent(new Event('input', { bubbles: true })); }
  function jsonField(name) { return main.elements.namedItem(name); }
  function readJson(name, fallback) {
    try { return JSON.parse(jsonField(name)?.value || JSON.stringify(fallback)) ?? fallback; }
    catch { return fallback; }
  }
  function writeJson(name, value) { const input = jsonField(name); if (input) { input.value = JSON.stringify(value); changed(input); } }
  function updateVersion(result) {
    if (Number.isInteger(result.version)) { main.dataset.version = String(result.version); root.dataset.version = String(result.version); }
  }
  document.addEventListener('igd:draft-saved', event => {
    updateVersion(event.detail);
    const signatures = document.getElementById('igd-signature-status');
    if (signatures) signatures.textContent = 'Draft berubah; persetujuan sebelumnya dibatalkan. Setujui ulang data terkini.';
  });
  async function request(url, body, multipart = false) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(url, {method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        headers: {'X-CSRFToken': csrf(), ...(multipart ? {} : {'Content-Type': 'application/json'})},
        body: multipart ? body : JSON.stringify(body)});
      const result = await response.json().catch(() => null);
      if (!response.ok || !result || result.success !== true) {
        const details = result?.fields ? JSON.stringify(result.fields) : '';
        throw new Error([result?.error || `Aksi gagal (${response.status}).`, details].filter(Boolean).join(' '));
      }
      return result;
    } finally { window.clearTimeout(timer); }
  }
  const operationForms = [...document.querySelectorAll('form.igd-operation, #igd-upload-form')];
  operationForms.forEach(form => {
    form.addEventListener('input', () => { dirtyForms.add(form); delete form.dataset.requestId; });
    form.addEventListener('change', () => { dirtyForms.add(form); delete form.dataset.requestId; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      if (main.dataset.dirty === 'true') { message('Simpan perubahan draft terlebih dahulu sebelum menjalankan aksi.'); return; }
      if (form.dataset.operation !== 'sign' && [...dirtyForms].some(other => other !== form)) {
        message('Ada formulir aksi lain yang belum disimpan. Selesaikan formulir itu terlebih dahulu.'); return;
      }
      const data = new FormData(form);
      const fields = {};
      for (const [name, value] of data) if (name !== 'csrfmiddlewaretoken') fields[name] = value;
      if (form.dataset.operation === 'sign') {
        const reasons = [...document.querySelectorAll('[data-exemption-section]')];
        if (reasons.length) fields.exemptions = Object.fromEntries(reasons.filter(e => e.value.trim()).map(e => [e.dataset.exemptionSection, e.value.trim()]));
      }
      form.dataset.requestId ||= crypto.randomUUID();
      const upload = form.id === 'igd-upload-form';
      if (upload) { data.set('version', String(version())); data.set('request_id', form.dataset.requestId); }
      busy = true;
      const buttons = [...form.querySelectorAll('button[type=submit]')];
      buttons.forEach(button => { button.disabled = true; });
      errors.hidden = true;
      try {
        const result = await request(form.action, upload ? data : {operation:form.dataset.operation, fields, version:version(), request_id:form.dataset.requestId}, upload);
        updateVersion(result);
        dirtyForms.delete(form);
        delete form.dataset.requestId;
        status.textContent = `Aksi tercatat · versi ${result.version}`;
        if (form.dataset.operation === 'sign') {
          const signatures = document.getElementById('igd-signature-status');
          if (signatures) signatures.textContent = `Persetujuan bagian ${result.signed_section} tercatat untuk data terkini.`;
        } else { navigating = true; window.location.reload(); }
      } catch (error) { message(error.name === 'AbortError' ? 'Koneksi terputus. Coba ulang tanpa mengubah isian agar ID permintaan yang sama dipakai.' : error.message); }
      finally { busy = false; buttons.forEach(button => { button.disabled = false; }); }
    });
  });
  document.querySelectorAll('[data-exemption-section]').forEach(input => input.addEventListener('input', () => {
    const form = document.getElementById('sign-form');
    if (form) { dirtyForms.add(form); delete form.dataset.requestId; }
  }));
  window.addEventListener('beforeunload', event => {
    if (!navigating && (busy || dirtyForms.size)) { event.preventDefault(); event.returnValue = ''; }
  });
  function questionnaire(selector, field, scoreName, gradeName) {
    const answers = [...document.querySelectorAll(selector)];
    answers.forEach(input => input.addEventListener('change', () => {
      const selected = answers.filter(e => e.value !== '');
      writeJson(field, Object.fromEntries(selected.map(e => [e.dataset.key, Number(e.value)])));
      const score = selected.length === answers.length ? selected.reduce((total,e) => total + Number(e.value), 0) : null;
      const target = jsonField(scoreName);
      if (target) target.value = score === null ? '' : String(score);
      if (gradeName) {
        const grade = jsonField(gradeName);
        if (grade) grade.value = score === null ? '' : score >= 45 ? 'TINGGI' : score >= 25 ? 'SEDANG' : 'RENDAH';
        const method = jsonField('metode_risiko_jatuh');
        if (method && selected.length) method.value = 'Morse Fall Scale';
      }
    }));
  }
  questionnaire('.morse-answer', 'skrining_jatuh_detail', 'skrining_jatuh_skor', 'skrining_jatuh_grade');
  questionnaire('.mst-answer', 'skrining_gizi_detail', 'skrining_gizi_mst');
  document.querySelectorAll('.organ-finding').forEach(input => input.addEventListener('input', () => {
    const findings = readJson('fisik_head_to_toe', {});
    findings[input.dataset.key] = input.value;
    writeJson('fisik_head_to_toe', findings);
  }));
  const editor = document.getElementById('igd-body-editor');
  if (editor) {
    let markers = readJson('penanda_anatomi', []);
    let selected = -1;
    const side = document.getElementById('marker-side');
    const svg = document.getElementById('igd-body-map');
    const list = document.getElementById('igd-marker-list');
    const pointLayer = document.getElementById('igd-marker-points');
    const label = document.getElementById('marker-label');
    const kind = document.getElementById('marker-kind');
    const x = document.getElementById('marker-x');
    const y = document.getElementById('marker-y');
    function choose(index) { selected = index; const m = markers[index]; side.value=m.side; label.value=m.label; kind.value=m.kind; x.value=m.x; y.value=m.y; render(); }
    function render() {
      list.replaceChildren(); pointLayer.replaceChildren();
      markers.forEach((marker,index) => {
        const row = document.createElement('li'); row.className='list-group-item igd-marker-row';
        const text = document.createElement('span'); text.textContent=`${marker.side} · ${marker.kind} · ${marker.label}`; row.append(text);
        const pick = document.createElement('button'); pick.type='button'; pick.className='btn btn-sm btn-outline-primary'; pick.textContent='Pilih'; pick.addEventListener('click',()=>choose(index)); row.append(pick);
        const remove = document.createElement('button'); remove.type='button'; remove.className='btn btn-sm btn-outline-secondary'; remove.textContent='Hapus'; remove.addEventListener('click',()=>{ if (editor.dataset.readonly==='true') return; markers.splice(index,1); selected=-1; writeJson('penanda_anatomi',markers); render(); }); row.append(remove); list.append(row);
        if (marker.side === side.value) { const point=document.createElementNS('http://www.w3.org/2000/svg','circle'); point.setAttribute('cx',String(marker.x*200)); point.setAttribute('cy',String(marker.y*360)); point.setAttribute('r',selected===index?'7':'5'); point.setAttribute('fill','#b91c1c'); pointLayer.append(point); }
      });
    }
    function addOrUpdate(update) {
      if (editor.dataset.readonly==='true') return;
      const px=Number(x.value), py=Number(y.value);
      if (!label.value.trim() || x.value==='' || y.value==='' || !Number.isFinite(px) || !Number.isFinite(py) || px<0 || px>1 || py<0 || py>1) { message('Isi label serta koordinat X/Y antara 0 dan 1.'); return; }
      const marker={side:side.value,x:px,y:py,label:label.value.trim(),kind:kind.value};
      if (update && selected>=0) markers[selected]=marker;
      else if (!update) { markers.push(marker); selected=markers.length-1; }
      else { message('Pilih penanda yang ingin diperbarui.'); return; }
      writeJson('penanda_anatomi',markers); render();
    }
    svg.addEventListener('click',event=>{ if (editor.dataset.readonly==='true') return; const r=svg.getBoundingClientRect(); x.value=((event.clientX-r.left)/r.width).toFixed(3); y.value=((event.clientY-r.top)/r.height).toFixed(3); addOrUpdate(selected>=0); });
    document.getElementById('marker-add').addEventListener('click',()=>addOrUpdate(false));
    document.getElementById('marker-update').addEventListener('click',()=>addOrUpdate(true));
    side.addEventListener('change',render); render();
  }
  document.querySelectorAll('[data-edit-plan]').forEach(button=>button.addEventListener('click',()=>{
    const form=document.getElementById('plan_action-form'); if (!form) return;
    form.elements.namedItem('action_id').value=button.dataset.editPlan;
    for (const name of ['jenis','kode','nama','quantity','tarif','catatan_tarif','standard_item','ep_status','ep_catatan']) {
      const input=form.elements.namedItem(name); if(input) input.value=button.dataset[name] || '';
    }
    form.scrollIntoView({behavior:'smooth',block:'start'}); changed(form);
  }));
  document.querySelectorAll('[data-correction]').forEach(button=>button.addEventListener('click',()=>{
    if(main.dataset.dirty==='true'){message('Simpan perubahan draft sebelum memilih pengukuran yang akan dikoreksi.');return;}
    const values=JSON.parse(button.closest('article').querySelector('script[type="application/json"]').textContent);
    for(const [name,value] of Object.entries(values)){const input=main.elements.namedItem(name);if(input) input.value=value ?? '';}
    document.getElementById('igd-corrects').value=button.dataset.correction;
    document.getElementById('observed-at').value='';
    changed(main);main.scrollIntoView({behavior:'smooth',block:'start'});
    status.textContent=`Koreksi observasi #${button.dataset.correction}; tinjau lalu simpan sebagai catatan baru.`;
  }));
  async function catalogue(kind,q) {
    const url=new URL(root.dataset.catalogue,window.location.origin); url.searchParams.set('type',kind); url.searchParams.set('q',q);
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store'});
    if (!response.ok) throw new Error('Katalog tidak tersedia.');
    return (await response.json()).results;
  }
  function bindCatalogue(input,kind) {
    if (!input) return;
    const options=document.createElement('datalist'); options.id=`${input.id}-catalogue`; input.setAttribute('list',options.id); input.after(options);
    let timer;
    input.addEventListener('input',()=>{ window.clearTimeout(timer); timer=window.setTimeout(async()=>{
      if(!input.value.trim()) return;
      try { const rows=await catalogue(kind,input.value); options.replaceChildren(); rows.forEach(row=>{ const option=document.createElement('option'); option.value=`${row.kode} — ${row.nama}`; options.append(option); }); }
      catch { options.replaceChildren(); }
    },250); });
  }
  bindCatalogue(main.elements.namedItem('diagnosa_masuk'),'ICD10');
  const sdki=main.elements.namedItem('diagnosa_keperawatan_sdki'); bindCatalogue(sdki,'SDKI');
  if (sdki && !sdki.disabled) {
    const button=document.createElement('button'); button.type='button'; button.className='btn btn-outline-primary mt-2'; button.id='igd-apply-3s'; button.textContent='Gunakan Pemetaan SDKI → SLKI → SIKI'; sdki.after(button);
    button.addEventListener('click',async()=>{ try { const code=sdki.value.split(' — ')[0].trim(); const row=(await catalogue('SDKI',code)).find(r=>r.kode===code); if(!row) throw new Error('Pilih kode SDKI dari master terlebih dahulu.'); main.elements.namedItem('luaran_keperawatan_slki').value=row.slki.join('\n'); main.elements.namedItem('intervensi_keperawatan_siki').value=row.siki.join('\n'); changed(sdki); } catch(error){message(error.message);} });
  }
  const planForm=document.getElementById('plan_action-form');
  if (planForm) {
    let timer; const code=planForm.elements.namedItem('kode'); const kind=planForm.elements.namedItem('jenis');
    const options=document.createElement('datalist'); options.id='igd-action-code-list'; code.setAttribute('list',options.id); code.after(options);
    code.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(async()=>{try{const type=kind.value==='SIKI'?'SIKI':'ICD9';const rows=await catalogue(type,code.value);options.replaceChildren();rows.forEach(row=>{const option=document.createElement('option');option.value=row.kode;option.label=row.nama;options.append(option);});}catch{options.replaceChildren();}},250);});
  }
  const aiButton=document.getElementById('igd-ai-request');
  aiButton?.addEventListener('click',async()=>{
    const target=document.getElementById('igd-ai-results'); aiButton.disabled=true; target.textContent='Meminta kandidat…';
    try {
      const result=await request(root.dataset.ai,{query:document.getElementById('igd-ai-query').value});
      target.replaceChildren(); const picks={};
      for(const [key,rows] of Object.entries(result.suggestions)) {
        const label=document.createElement('label'); label.textContent=key==='medical'?'Kandidat medis':'Kandidat keperawatan';
        const select=document.createElement('select'); select.className='form-select'; select.setAttribute('aria-label',label.textContent);
        const blank=document.createElement('option');blank.value='';blank.textContent='— Tidak mengubah bagian ini —';select.append(blank);
        rows.forEach((row,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=key==='medical'?`${row.kode} — ${row.nama}`:`${row.sdki_kode} — ${row.sdki_nama}`;select.append(option);});target.append(label,select);picks[key]=select;
      }
      const accept=document.createElement('button'); accept.type='button'; accept.id='igd-ai-accept'; accept.className='btn btn-outline-primary mt-2'; accept.textContent='Terapkan Pilihan ke Draft (Belum Disimpan)';
      accept.addEventListener('click',()=>{
        if(picks.medical.value==='' && picks.nursing.value===''){message('Pilih minimal satu kandidat.');return;}
        if(picks.medical.value!==''){const row=result.suggestions.medical[Number(picks.medical.value)]; main.elements.namedItem('diagnosa_masuk').value=`${row.kode} — ${row.nama}`;}
        if(picks.nursing.value!==''){const row=result.suggestions.nursing[Number(picks.nursing.value)];sdki.value=`${row.sdki_kode} — ${row.sdki_nama}`;main.elements.namedItem('luaran_keperawatan_slki').value=row.slki.map(r=>`${r.kode} — ${r.nama}`).join('\n');main.elements.namedItem('intervensi_keperawatan_siki').value=row.siki.map(r=>`${r.kode} — ${r.nama}`).join('\n');}
        main.elements.namedItem('diagnosis_mode').value='AI';document.getElementById('igd-ai-ticket').value=result.ticket;changed(main);status.textContent='Kandidat diterapkan ke isian; tinjau dan simpan draft.';
      }); target.append(accept);
    } catch(error){target.textContent=error.message;} finally{aiButton.disabled=false;}
  });
})();
