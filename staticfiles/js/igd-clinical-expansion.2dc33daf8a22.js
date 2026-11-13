(() => {
  'use strict';
  const root=document.getElementById('igd-workflow');
  const main=document.getElementById('igd-step-form');
  if (!root || !main) return;
  const errors=document.getElementById('igd-errors');
  let busy=false, leaving=false;
  const dirty=new Set();
  const csrf=()=>main.querySelector('[name=csrfmiddlewaretoken]').value;
  const codeOf=value=>String(value || '').split(' — ')[0].trim();
  function error(message) { errors.textContent=message; errors.hidden=false; errors.focus(); }
  function changed() { main.dispatchEvent(new Event('input',{bubbles:true})); }
  function option(value,label) { const node=document.createElement('option'); node.value=String(value); node.textContent=label; return node; }
  async function json(url,body) {
    const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),30000);
    try {
      const response=await fetch(url,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:body?{'Content-Type':'application/json','X-CSRFToken':csrf()}:{},body:body?JSON.stringify(body):undefined});
      const result=await response.json();
      if (!response.ok || result.success===false) throw new Error([result.error || `Permintaan gagal (${response.status}).`,result.fields?JSON.stringify(result.fields):''].filter(Boolean).join(' '));
      return result;
    } finally { clearTimeout(timer); }
  }
  async function action(form,operation,fields) {
    if (busy) return;
    if (main.dataset.dirty==='true') { error('Simpan draft utama sebelum menjalankan aksi lain.'); return; }
    const serialized=JSON.stringify({operation,fields});
    if (form.dataset.payload!==serialized) { form.dataset.payload=serialized; form.dataset.requestId=crypto.randomUUID(); }
    busy=true; const buttons=[...root.querySelectorAll('button[type=submit]')]; buttons.forEach(b=>{b.disabled=true;});
    try {
      const result=await json(form.dataset.action,{operation,fields,version:Number(main.dataset.version),request_id:form.dataset.requestId});
      main.dataset.version=String(result.version); dirty.delete(form); leaving=true; location.reload();
    } catch(e) { error(e.name==='AbortError'?'Koneksi terputus. Ulangi tanpa mengubah isian untuk menggunakan ID yang sama.':e.message); }
    finally { busy=false; buttons.forEach(b=>{b.disabled=false;}); }
  }
  window.addEventListener('beforeunload',event=>{if (!leaving && (busy || dirty.size)) {event.preventDefault();event.returnValue='';}});
  function watch(form) { form.addEventListener('input',()=>dirty.add(form));form.addEventListener('change',()=>dirty.add(form)); }

  document.querySelectorAll('[data-planning-component]').forEach(card=>{
    const key=card.dataset.planningComponent, mode=card.querySelector('[data-component-mode]');
    if (!mode || mode.disabled) return;
    const field=main.elements.namedItem(mode.dataset.field);
    const search=card.querySelector('[data-component-query]'), choices=card.querySelector('[data-component-options]');
    let generation=0,timer;
    field.addEventListener('input',()=>{if(mode.value==='AI'){mode.value='MANUAL';delete mode.dataset.ticket;}});
    search.addEventListener('input',()=>{
      const token=++generation;clearTimeout(timer);
      timer=setTimeout(async()=>{try{const url=new URL(root.dataset.catalogue,location.origin);url.searchParams.set('type',search.dataset.type);url.searchParams.set('q',search.value);
        const result=await json(url);if(token!==generation)return;choices.replaceChildren(option('','— Pilih hasil master —'));result.results.forEach(r=>choices.append(option(`${r.kode} — ${r.nama}`,`${r.kode} — ${r.nama}`)));
      }catch(e){error(e.message);}},250);
    });
    choices.addEventListener('change',()=>{if(!choices.value)return;field.value=choices.value;mode.value='MASTER';delete mode.dataset.ticket;changed();});
    card.querySelector('[data-component-ai]').addEventListener('click',async event=>{
      const button=event.currentTarget,target=card.querySelector('[data-component-results]');button.disabled=true;target.textContent='Meminta kandidat…';
      try {
        const response=await json(root.dataset.ai,{target:key,query:search.value,
          sdki_code:codeOf(main.elements.namedItem('diagnosa_keperawatan_sdki')?.value),
          slki_codes:String(main.elements.namedItem('luaran_keperawatan_slki')?.value || '').split('\n').filter(Boolean).map(codeOf)});
        target.replaceChildren();response.candidates.forEach(row=>{const pick=document.createElement('button');pick.type='button';pick.className='btn btn-outline-primary d-block my-1';pick.textContent=`Gunakan ${row.kode} — ${row.nama}`;pick.addEventListener('click',()=>{field.value=`${row.kode} — ${row.nama}`;mode.value='AI';mode.dataset.ticket=response.ticket;changed();});target.append(pick);});
      }catch(e){target.textContent=e.message;}finally{button.disabled=false;}
    });
  });

  const careButtons=[...document.querySelectorAll('[data-care-tab]')];
  function careTab(key){const actions=document.getElementById('igd-action-panel'),medications=document.getElementById('igd-medications');if(actions)actions.hidden=key!=='actions';if(medications)medications.hidden=key!=='medications';careButtons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.careTab===key)));}
  careButtons.forEach(button=>button.addEventListener('click',()=>careTab(button.dataset.careTab)));
  if(careButtons.length)careTab('actions');
  const ancillary=document.getElementById('igd-ancillary');
  if (ancillary) {
    const form=document.getElementById('ancillary-form'),selects=[...ancillary.querySelectorAll('[data-anc-level]')],basket=[];
    const status=document.getElementById('anc-status'),more=document.getElementById('anc-next-page');
    const rows=new Map();let generation=0,last={level:0,page:1,parent:null};watch(form);
    async function load(level,parent=null,page=1,append=false) {
      const token=++generation;last={level,parent,page};
      const url=new URL(ancillary.dataset.catalogue,location.origin);if(parent)url.searchParams.set('parent',parent);url.searchParams.set('page',page);
      status.textContent='Memuat pilihan…';
      try {
        const result=await json(url);if(token!==generation)return;
        const select=selects[level];if(!append)select.replaceChildren(option('','— Pilih —'));select.disabled=false;
        result.results.forEach(row=>{select.append(option(row.id,row.nama));if(level===3)rows.set(String(row.id),row);});
        more.hidden=!result.has_more;status.textContent=result.results.length?'Pilih pemeriksaan lalu tambahkan ke daftar.':'Belum ada item aktif/review pada cabang ini.';
      }catch(e){status.textContent=e.message;}
    }
    selects.forEach((select,index)=>select.addEventListener('change',()=>{
      ++generation;selects.slice(index+1).forEach(child=>{child.replaceChildren(option('','— Pilih induk dahulu —'));child.disabled=true;});
      if(index<3 && select.value)load(index+1,select.value);
      if(index===3){const box=document.getElementById('anc-variants');box.replaceChildren();const row=rows.get(select.value);if(row)Object.entries(row.variants || {}).forEach(([key,values])=>{const label=document.createElement('label');label.textContent=key;const choice=document.createElement('select');choice.className='form-select';choice.dataset.ancVariant=key;choice.append(option('','— Pilih varian —'));values.forEach(v=>choice.append(option(v,v)));box.append(label,choice);});}
    }));
    more.addEventListener('click',()=>load(last.level,last.parent,last.page+1,true));
    function render() {
      const list=document.getElementById('anc-basket');list.replaceChildren();basket.forEach((row,index)=>{const li=document.createElement('li');li.className='list-group-item';const label=document.createElement('span');label.textContent=`${row.label} · ${row.payload.prioritas} · ${row.payload.indication}`;const remove=document.createElement('button');remove.type='button';remove.className='btn btn-sm btn-outline-secondary ms-2';remove.textContent='Hapus dari daftar';remove.addEventListener('click',()=>{basket.splice(index,1);dirty.add(form);render();});li.append(label,remove);list.append(li);});
    }
    document.getElementById('anc-add').addEventListener('click',()=>{
      const item=rows.get(selects[3].value),indication=document.getElementById('anc-indication').value.trim();
      if(!item || !indication){error('Pilih item dan isi indikasi klinis.');return;}
      if(basket.some(row=>row.payload.item_id===item.id)){error('Item sudah ada pada daftar ini.');return;}
      const preparation=Object.fromEntries([...ancillary.querySelectorAll('[data-anc-prep]')].map(e=>[e.dataset.ancPrep,e.value]));
      if(document.getElementById('anc-site').value)preparation.site=document.getElementById('anc-site').value;
      ancillary.querySelectorAll('[data-anc-variant]').forEach(e=>{preparation[e.dataset.ancVariant]=e.value;});
      const payload={item_id:item.id,prioritas:document.getElementById('anc-priority').value,indication,preparation};
      const diagnosis=document.getElementById('anc-diagnosis').value;if(diagnosis)payload.diagnosis_id=Number(diagnosis);
      basket.push({label:[...item.path.map(n=>n.nama),item.nama].join(' / '),payload});dirty.add(form);render();
    });
    form.addEventListener('submit',event=>{event.preventDefault();if(!basket.length){error('Daftar order masih kosong.');return;}action(form,'order_batch',{items:basket.map(r=>r.payload)});});
    load(0);
  }

  const meds=document.getElementById('igd-medications'),rxForm=document.getElementById('medication-form');
  if (meds && rxForm) {
    watch(rxForm);const kinds=document.getElementById('rx-kind'),formulary=document.getElementById('rx-formulary');
    const levels=['class','generic','product'],selects=levels.map(key=>document.getElementById('rx-'+key));
    const products=new Map(),lines=[],parts=[];let generation=0,last={level:'class',parent:null,page:1};
    const status=document.getElementById('rx-status'),more=document.getElementById('rx-next-page');
    const value=id=>document.getElementById('rx-'+id).value;
    async function load(level,parent=null,page=1,append=false) {
      const token=++generation;last={level,parent,page};const url=new URL(meds.dataset.catalogue,location.origin);
      Object.entries({level,kind:kinds.value,formulary:formulary.value,page}).forEach(([k,v])=>url.searchParams.set(k,v));if(parent)url.searchParams.set('parent',parent);
      try {
        const result=await json(url);if(token!==generation)return;const select=selects[levels.indexOf(level)];if(!append)select.replaceChildren(option('','— Pilih —'));select.disabled=false;
        result.results.forEach(row=>{select.append(option(row.id,row.nama));if(level==='product')products.set(String(row.id),row);});more.hidden=!result.has_more;
        status.textContent=result.results.length?'Pilih produk yang telah direview.':'Belum ada master aktif untuk pilihan ini; katalog contoh memerlukan review sebelum aktivasi.';
      }catch(e){status.textContent=e.message;}
    }
    function clearAfter(index) {++generation;selects.slice(index+1).forEach(s=>{s.replaceChildren(option('','— Pilih induk dahulu —'));s.disabled=true;});}
    kinds.addEventListener('change',()=>{clearAfter(-1);document.getElementById('rx-regimen').hidden=kinds.value==='BMHP';document.getElementById('rx-compound').hidden=kinds.value!=='RACIKAN';load('class');});
    formulary.addEventListener('change',()=>{clearAfter(-1);load('class');});
    selects.forEach((select,index)=>select.addEventListener('change',()=>{
      clearAfter(index);if(index<2 && select.value)load(levels[index+1],select.value);
      if(index===2){const product=products.get(select.value),routes=document.getElementById('rx-route');routes.replaceChildren(option('','— Pilih rute —'));
        if(product){document.getElementById('rx-product-info').textContent=`${product.tall_man_label || product.nama} · ${product.flags.join(', ') || 'Tidak ada flag terdaftar'} · Harga ${product.price ?? 'belum ditetapkan'} · Satuan ${product.unit}`;product.allowed_routes.forEach(route=>routes.append(option(route,route)));document.getElementById('rx-dose-unit').value=product.unit;}
      }
    }));
    more.addEventListener('click',()=>load(last.level,last.parent,last.page+1,true));
    function renderParts() {const list=document.getElementById('rx-components');list.replaceChildren();parts.forEach((part,index)=>{const li=document.createElement('li');li.textContent=`${part.label}: ${part.payload.amount} ${part.payload.unit} `;const remove=document.createElement('button');remove.type='button';remove.textContent='Hapus komponen';remove.className='btn btn-sm btn-outline-secondary';remove.addEventListener('click',()=>{parts.splice(index,1);dirty.add(rxForm);renderParts();});li.append(remove);list.append(li);});}
    document.getElementById('rx-add-component').addEventListener('click',()=>{const product=products.get(selects[2].value);if(!product || !value('component-amount') || !value('component-unit')){error('Pilih produk, jumlah dan satuan komponen.');return;}parts.push({label:product.nama,payload:{product_id:product.id,amount:value('component-amount'),unit:value('component-unit')}});dirty.add(rxForm);renderParts();});
    function renderLines() {const list=document.getElementById('rx-lines');list.replaceChildren();lines.forEach((line,index)=>{const li=document.createElement('li');li.className='list-group-item';li.textContent=`${line.label} · ${line.payload.kind} · Jumlah ${line.payload.quantity || 'dihitung server'} `;const remove=document.createElement('button');remove.type='button';remove.className='btn btn-sm btn-outline-secondary';remove.textContent='Hapus baris';remove.addEventListener('click',()=>{lines.splice(index,1);dirty.add(rxForm);renderLines();});li.append(remove);list.append(li);});}
    document.getElementById('rx-add-line').addEventListener('click',()=>{
      const product=products.get(selects[2].value);if(!product){error('Pilih produk aktif dari master.');return;}
      const kind=kinds.value,frequency=kind==='BMHP'?'BMHP':value('frequency');
      const regimen={schema_version:1,frequency};
      if(kind!=='BMHP'){Object.assign(regimen,{dose:value('dose'),dose_unit:value('dose-unit'),duration_days:value('duration'),route:value('route'),timing:value('timing')});
        if(frequency==='INTERVAL')regimen.interval_hours=value('rate');else if(frequency==='FIXED')regimen.times_per_day=value('rate');
        if(frequency==='PRN'){regimen.prn_indication=value('prn');regimen.max_per_day=value('max');}
      }
      const payload={product_id:product.id,kind,regimen,quantity_reason:value('quantity-reason'),formulary:formulary.value};
      if(value('quantity'))payload.quantity=value('quantity');
      if(kind==='RACIKAN'){payload.components=parts.map(p=>p.payload);payload.compound_instructions=value('compound-instructions');payload.compound_form=value('compound-form');}
      lines.push({label:kind==='RACIKAN'?'Racikan '+value('compound-form'):product.nama,payload});dirty.add(rxForm);renderLines();
    });
    rxForm.addEventListener('submit',event=>{event.preventDefault();if(!lines.length){error('Tambahkan minimal satu baris resep.');return;}const fields={lines:lines.map(r=>r.payload),serving_unit_id:Number(value('serving-unit'))};if(value('edit-id'))fields.prescription_id=Number(value('edit-id'));action(rxForm,'prescription_save',fields);});
    rxForm.addEventListener('reset',()=>{lines.splice(0);parts.splice(0);dirty.delete(rxForm);delete rxForm.dataset.payload;document.getElementById('rx-edit-id').value='';renderLines();renderParts();setTimeout(()=>load('class'),0);});
    meds.querySelectorAll('[data-rx-edit]').forEach(button=>button.addEventListener('click',()=>{if(dirty.has(rxForm)){error('Kosongkan isian resep baru sebelum membuka draft lain.');return;}const payload=JSON.parse(document.getElementById(button.dataset.payload).textContent);lines.splice(0);payload.lines.forEach(line=>{const {label,...fields}=line;lines.push({label,payload:fields});});document.getElementById('rx-edit-id').value=button.dataset.rxEdit;document.getElementById('rx-serving-unit').value=payload.serving_unit_id || '';renderLines();rxForm.scrollIntoView({block:'start'});}));
    document.getElementById('rx-compound').hidden=true;load('class');
  }
  document.querySelectorAll('[data-rx-submit]').forEach(form=>form.addEventListener('submit',event=>{event.preventDefault();const acknowledgements=[...form.querySelectorAll('[data-risk-code]')].map(input=>({code:input.dataset.riskCode,reason:input.value}));action(form,'prescription_submit',{prescription_id:Number(form.dataset.rxSubmit),acknowledgements});}));

  document.querySelector('[data-procedure-ai]')?.addEventListener('click',async event=>{
    const button=event.currentTarget,form=document.getElementById('plan_action-form'),target=document.getElementById('procedure-ai-results');if(!form)return;button.disabled=true;target.textContent='Meminta kandidat tindakan…';
    try {const result=await json(root.dataset.ai,{target:button.dataset.procedureAi,query:main.elements.namedItem('diagnosa_masuk')?.value || '',sdki_code:codeOf(main.elements.namedItem('diagnosa_keperawatan_sdki')?.value),slki_codes:String(main.elements.namedItem('luaran_keperawatan_slki')?.value || '').split('\n').filter(Boolean).map(codeOf)});target.replaceChildren();result.candidates.forEach(row=>{const pick=document.createElement('button');pick.type='button';pick.className='btn btn-outline-primary my-1';pick.textContent=`Gunakan ${row.kode} — ${row.nama}`;pick.addEventListener('click',()=>{form.elements.namedItem('jenis').value=button.dataset.procedureAi==='siki'?'SIKI':'ICD9';form.elements.namedItem('kode').value=row.kode;form.elements.namedItem('nama').value=row.nama;form.elements.namedItem('mode').value='AI';form.elements.namedItem('ai_ticket').value=result.ticket;form.dispatchEvent(new Event('input',{bubbles:true}));});target.append(pick);});}catch(e){target.textContent=e.message;}finally{button.disabled=false;}
  });
})();
