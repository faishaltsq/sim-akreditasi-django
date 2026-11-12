(() => {
  'use strict';
  const form = document.getElementById('igd-step-form');
  if (!form) return;
  let dirty = false;
  let saving = false;
  const status = document.getElementById('igd-save-status');
  const errors = document.getElementById('igd-errors');
  document.getElementById('igd-step-select')?.addEventListener('change', event => {
    window.location.assign(`?step=${encodeURIComponent(event.target.value)}`);
  });
  form.addEventListener('input', () => { dirty = true; form.dataset.dirty = 'true'; });
  form.addEventListener('change', () => { dirty = true; form.dataset.dirty = 'true'; });
  window.addEventListener('beforeunload', event => {
    if (dirty || saving) { event.preventDefault(); event.returnValue = ''; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving) return;
    const intent = event.submitter?.value || 'save';
    const data = new FormData(form);
    const fields = {};
    for (const [name, value] of data.entries()) {
      if (name !== 'csrfmiddlewaretoken' && name !== 'intent') fields[name] = value;
    }
    const observed = form.querySelector('[data-observed-at]')?.value;
    if (observed) fields.observed_at = observed;
    const ticket = document.getElementById('igd-ai-ticket');
    if (ticket?.value && fields.diagnosis_mode === 'AI') fields.ai_ticket = ticket.value;
    const buttons = Array.from(form.querySelectorAll('button[type="submit"]'));
    saving = true;
    buttons.forEach(button => { button.disabled = true; });
    errors.hidden = true;
    status.textContent = 'Menyimpan draft…';
    try {
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': data.get('csrfmiddlewaretoken') },
        body: JSON.stringify({ version: Number(form.dataset.version), fields }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok || !result || result.success !== true) {
        const detail = result?.fields ? Object.entries(result.fields).map(([name, entries]) => {
          const messages = Array.isArray(entries) ? entries.map(e => e.message || String(e)).join('; ') : String(entries);
          return `${name}: ${messages}`;
        }).join(' · ') : '';
        throw new Error([result?.error || `Penyimpanan gagal (${response.status}).`, detail].filter(Boolean).join(' '));
      }
      form.dataset.version = String(result.version);
      dirty = false;
      form.dataset.dirty = 'false';
      if (ticket) ticket.value = '';
      document.dispatchEvent(new CustomEvent('igd:draft-saved', {detail:result}));
      status.textContent = `Draft tersimpan · versi ${result.version}`;
      if (intent === 'next') {
        window.location.assign(`?step=${Math.min(11, Number(form.dataset.step) + 1)}`);
      }
    } catch (error) {
      status.textContent = 'Draft belum tersimpan. Isian tetap tersedia untuk dicoba kembali.';
      errors.textContent = error.message;
      errors.hidden = false;
      errors.focus();
    } finally {
      saving = false;
      buttons.forEach(button => { button.disabled = false; });
    }
  });
})();
