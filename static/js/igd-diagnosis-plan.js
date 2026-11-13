(() => {
  'use strict';
  const panel = document.getElementById('igd-diagnoses');
  const form = document.getElementById('igd-diagnosis-form');
  const main = document.getElementById('igd-step-form');
  const root = document.getElementById('igd-workflow');
  if (!panel || !form || !main || !root) return;
  const errorBox = document.getElementById('igd-errors');
  const code = form.elements.namedItem('code');
  const text = form.elements.namedItem('text');
  let busy = false;
  let dirty = false;
  let leaving = false;
  let lookupGeneration = 0;
  let timer;
  const records=JSON.parse(document.getElementById('igd-diagnosis-data').textContent).filter(row=>row.active);
  form.dataset.tempId = crypto.randomUUID();
  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    errorBox.focus();
  }
  form.addEventListener('input', () => { dirty = true; delete form.dataset.requestId; });
  form.addEventListener('change', () => { dirty = true; delete form.dataset.requestId; });
  form.addEventListener('reset', () => { dirty = false; delete form.dataset.requestId; delete form.dataset.editId; delete form.dataset.aiTicket; form.dataset.tempId = crypto.randomUUID(); });
  window.addEventListener('beforeunload', event => {
    if (!leaving && (dirty || busy)) { event.preventDefault(); event.returnValue = ''; }
  });
  async function send(changes, owner) {
    if (busy) return;
    if (main.dataset.dirty === 'true') { showError('Simpan draft utama sebelum mengubah daftar diagnosis.'); return; }
    owner.dataset.requestId ||= crypto.randomUUID();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    busy = true;
    const buttons = [...panel.querySelectorAll('button')];
    buttons.forEach(button => { button.disabled = true; });
    try {
      const response = await fetch(panel.dataset.action, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value},
        body: JSON.stringify({operation: 'diagnosis_set', fields: {changes}, version: Number(main.dataset.version), request_id: owner.dataset.requestId})
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Diagnosis belum tersimpan.');
      dirty = false;
      leaving = true;
      window.location.reload();
    } catch (error) {
      showError(error.name === 'AbortError' ? 'Koneksi terputus. Ulangi tanpa mengubah isian untuk memakai ID permintaan yang sama.' : error.message);
    } finally {
      window.clearTimeout(timeout);
      busy = false;
      buttons.forEach(button => { button.disabled = false; });
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const mode = form.elements.namedItem('mode').value;
    const change = {op: 'upsert', temp_id: form.dataset.tempId, mode,
      text: text.value, is_primary: form.elements.namedItem('primary').checked};
    if (form.dataset.editId) { delete change.temp_id; change.id=Number(form.dataset.editId); }
    if (mode === 'MASTER' || mode==='AI') change.code = code.value.trim();
    if (mode==='AI' && form.dataset.aiTicket) change.ai_ticket=form.dataset.aiTicket;
    const changes=[];
    if(change.is_primary) records.filter(row=>row.is_primary && row.id!==change.id).forEach(row=>{const demote={op:'upsert',id:row.id,mode:row.mode,text:row.nama,is_primary:false};if(row.kode)demote.code=row.kode;changes.push(demote);});
    changes.push(change);send(changes, form);
  });
  panel.querySelectorAll('[data-diagnosis-cancel]').forEach(button => button.addEventListener('click', () => {
    if (dirty) { showError('Simpan atau kosongkan isian diagnosis baru sebelum membatalkan baris lain.'); return; }
    send([{op: 'cancel', id: Number(button.dataset.diagnosisCancel)}], button);
  }));
  panel.querySelectorAll('[data-diagnosis-edit]').forEach(button=>button.addEventListener('click',()=>{
    const row=records.find(item=>item.id===Number(button.dataset.diagnosisEdit));
    if(!row)return; form.dataset.editId=String(row.id); delete form.dataset.requestId; delete form.dataset.aiTicket;
    form.elements.namedItem('mode').value=row.mode;code.value=row.kode;text.value=row.nama;
    form.elements.namedItem('primary').checked=row.is_primary;dirty=true;form.scrollIntoView({block:'start'});
  }));
  document.getElementById('diagnosis-ai-request').addEventListener('click',async event=>{
    const button=event.currentTarget,target=document.getElementById('diagnosis-ai-results');button.disabled=true;target.textContent='Meminta kandidat…';
    try {
      const response=await fetch(root.dataset.ai,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({target:'medical',query:text.value})});
      const result=await response.json();if(!response.ok || !result.success)throw new Error(result.error || 'AI tidak tersedia.');target.replaceChildren();
      result.candidates.forEach(row=>{const pick=document.createElement('button');pick.type='button';pick.className='btn btn-outline-primary my-1';pick.textContent=`Gunakan ${row.kode} — ${row.nama}`;pick.addEventListener('click',()=>{form.elements.namedItem('mode').value='AI';code.value=row.kode;text.value=row.nama;form.dataset.aiTicket=result.ticket;delete form.dataset.requestId;dirty=true;});target.append(pick);});
    }catch(e){target.textContent=e.message;}finally{button.disabled=false;}
  });
  text.addEventListener('input', () => {
    const generation = ++lookupGeneration;
    window.clearTimeout(timer);
    timer = window.setTimeout(async () => {
      if (form.elements.namedItem('mode').value !== 'MASTER') return;
      const url = new URL(root.dataset.catalogue, window.location.origin);
      url.searchParams.set('type', 'ICD10');
      url.searchParams.set('q', text.value.trim());
      try {
        const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
        if (!response.ok) throw new Error('Katalog tidak tersedia.');
        const result = await response.json();
        if (generation !== lookupGeneration) return;
        const options = document.getElementById('diagnosis-codes');
        options.replaceChildren();
        result.results.forEach(row => {
          const option = document.createElement('option'); option.value = row.kode; option.label = row.nama; options.append(option);
        });
      } catch (error) { if (generation === lookupGeneration) showError(error.message); }
    }, 250);
  });
})();
