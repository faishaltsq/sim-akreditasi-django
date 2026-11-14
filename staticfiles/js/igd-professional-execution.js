(() => {
  'use strict';
  const panel = document.getElementById('professional-care-panel');
  if (!panel) return;
  const root = document.getElementById('igd-workflow');
  const error = document.getElementById('professional-error');
  const status = document.getElementById('professional-status');
  const data = JSON.parse(document.getElementById('professional-care-data').textContent);
  const el = (name) => document.getElementById(`professional-${name}`);
  const keys = new Map();
  let busy = false;
  const report = (message) => { error.textContent = message; error.hidden = false; error.focus(); };
  async function read(url) {
    const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error(`Akses ditolak atau sesi berakhir (${response.status}).`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Permintaan ditolak (${response.status}).`);
    return result;
  }
  async function send(operation, fields) {
    if (busy) return;
    const intent = JSON.stringify({operation, fields});
    if (!keys.has(intent)) keys.set(intent, crypto.randomUUID());
    busy = true; error.hidden = true; status.textContent = 'Menyimpan…';
    panel.querySelectorAll('button').forEach((button) => { button.disabled = true; });
    try {
      const response = await fetch(panel.dataset.action, {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value},
        body: JSON.stringify({operation, fields, version: Number(root.dataset.version), request_id: keys.get(intent)}),
      });
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error(`Akses ditolak atau sesi berakhir (${response.status}).`);
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Aksi ditolak.');
      root.dataset.version = String(result.version); status.textContent = 'Tersimpan; membaca ulang catatan server.';
      window.location.reload();
    } catch (exception) { status.textContent = ''; report(exception.message); }
    finally { busy = false; panel.querySelectorAll('button').forEach((button) => { button.disabled = false; }); }
  }
  window.IgdProfessionalCare = {send, report, data};
  panel.querySelectorAll('[data-professional-cancel]').forEach((button) => button.addEventListener('click', () => {
    if (window.confirm('Batalkan hanya rencana yang belum dilaksanakan ini?')) send('cancel_action', {action_id: Number(button.dataset.professionalCancel)});
  }));
  panel.querySelectorAll('[data-professional-void]').forEach((button) => button.addEventListener('click', () => {
    const reason = window.prompt('Alasan pembatalan penuh tagihan belum dibayar (minimal 5 karakter):');
    if (!reason || !window.confirm('Batalkan tagihan ini? Nilai asli dan riwayat pelayanan tetap disimpan.')) return;
    send('professional_void', {billing_id: Number(button.dataset.professionalVoid), reason});
  }));
  const form = el('execution-form');
  if (!form) return;
  const profession = el('profession'), grade = el('grade'), service = el('service');
  const performer = el('performer'), supervisor = el('supervisor');
  let catalogueSeq = 0, performerSeq = 0, quoteSeq = 0, quote = null;
  const invalidate = () => { quote = null; quoteSeq += 1; el('price').textContent = 'Preview perlu diperbarui.'; };
  function options(select, rows, valueKey, labelKey, placeholder) {
    const previous = select.value;
    select.replaceChildren(new Option(placeholder, ''));
    rows.forEach((row) => select.add(new Option(row[labelKey], String(row[valueKey]))));
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }
  function atValue() { const value = el('time').value; return value ? `${value.length === 16 ? `${value}:00` : value}+07:00` : ''; }
  async function loadCatalogue(initial = false) {
    const sequence = ++catalogueSeq; ++performerSeq; invalidate();
    options(service, [], 'id', 'name', 'Pilih layanan'); options(performer, [], 'performer_id', 'performer_name', 'Pilih pelaksana');
    const url = new URL(panel.dataset.catalogue, window.location.origin);
    if (!initial && profession.value) url.searchParams.set('profession', profession.value);
    if (!initial && grade.value) url.searchParams.set('grade', grade.value);
    try {
      const result = await read(url);
      if (sequence !== catalogueSeq) return;
      options(profession, result.professions, 'id', 'name', 'Pilih profesi');
      options(grade, result.grades, 'id', 'name', 'Pilih jenjang');
      if (result.professions.length === 1) profession.value = String(result.professions[0].id);
      if (result.grades.length === 1) grade.value = String(result.grades[0].id);
      options(service, result.services, 'id', 'name', 'Pilih layanan');
      service._rows = result.services; status.textContent = result.unavailable || 'Pilih layanan; kuantitas/tarif harus ditinjau sebelum pelaksanaan.';
    } catch (exception) { if (sequence === catalogueSeq) report(exception.message); }
  }
  async function loadPerformers() {
    const sequence = ++performerSeq; invalidate();
    options(performer, [], 'performer_id', 'performer_name', 'Pilih pelaksana');
    options(supervisor, [], 'performer_id', 'performer_name', 'Tidak dipilih');
    if (!service.value) return;
    const url = new URL(panel.dataset.catalogue, window.location.origin);
    url.searchParams.set('service', service.value);
    if (profession.value) url.searchParams.set('profession', profession.value);
    if (grade.value) url.searchParams.set('grade', grade.value);
    if (atValue()) url.searchParams.set('at', atValue());
    try {
      const result = await read(url); if (sequence !== performerSeq) return;
      options(performer, result.performers, 'performer_id', 'performer_name', 'Pilih pelaksana');
      options(supervisor, result.supervisors || [], 'performer_id', 'performer_name', 'Tidak dipilih');
      if (result.performers.some((row) => row.performer_id === result.actor_performer_id)) performer.value = result.actor_performer_id;
      status.textContent = result.unavailable || 'Pelaksana harus sesuai kewenangan layanan.';
      const selected = service._rows?.find((row) => String(row.id) === service.value);
      if (selected && el('note-format')) { el('note-format').value = selected.note_format; el('note-format').dispatchEvent(new Event('change')); }
    } catch (exception) { if (sequence === performerSeq) report(exception.message); }
  }
  profession.addEventListener('change', () => { grade.value = ''; loadCatalogue(); });
  grade.addEventListener('change', () => { service.value = ''; loadCatalogue(); });
  service.addEventListener('change', loadPerformers);
  ['performer', 'supervisor', 'quantity', 'retrospective'].forEach((name) => el(name).addEventListener('input', invalidate));
  el('time').addEventListener('change', loadPerformers);
  el('source').addEventListener('change', () => { el('plan').required = el('source').value === 'PLANNED'; });
  el('plan').addEventListener('change', () => { const option = el('plan').selectedOptions[0]; if (option.dataset.quantity) el('quantity').value = option.dataset.quantity; invalidate(); });
  el('preview').addEventListener('click', async () => {
    const sequence = ++quoteSeq;
    const url = new URL(panel.dataset.quote, window.location.origin);
    url.searchParams.set('service', service.value); url.searchParams.set('quantity', el('quantity').value);
    if (profession.value) url.searchParams.set('profession', profession.value);
    if (grade.value) url.searchParams.set('grade', grade.value);
    if (performer.value) url.searchParams.set('performer', performer.value);
    if (supervisor.value) url.searchParams.set('supervisor', supervisor.value);
    if (atValue()) url.searchParams.set('at', atValue());
    try {
      const result = await read(url); if (sequence !== quoteSeq) return; quote = result.quote;
      el('price').textContent = quote.status === 'UNPRICED' ? 'Tarif belum ditetapkan; bukan layanan gratis. Pencatatan pending mengikuti kebijakan layanan.' : `Sarana Rp ${quote.jasa_sarana} + pelayanan Rp ${quote.jasa_pelayanan}; unit Rp ${quote.unit_total}; subtotal Rp ${quote.subtotal}${quote.status === 'FREE' ? ' — gratis disetujui' : ''}`;
      error.hidden = true;
    } catch (exception) { if (sequence === quoteSeq) { quote = null; report(exception.message); } }
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!quote) { report('Tinjau preview tarif dan kewenangan terlebih dahulu.'); return; }
    const fields = {source: el('source').value, service_id: Number(service.value), quantity: el('quantity').value, quote_fingerprint: quote.fingerprint};
    if (fields.source === 'PLANNED') fields.action_id = Number(el('plan').value);
    if (performer.value) fields.performer = performer.value;
    if (supervisor.value) fields.supervisor = supervisor.value;
    if (atValue()) fields.occurred_at = atValue();
    if (el('retrospective').value) fields.retrospective_reason = el('retrospective').value;
    send('professional_execute', fields);
  });
  loadCatalogue(true);
})();
