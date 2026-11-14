(() => {
  'use strict';
  const api = window.IgdProfessionalCare;
  const form = document.getElementById('professional-cppt-form');
  if (!api) return;
  const el = (name) => document.getElementById(`professional-${name}`);
  const find = (id) => api.data.notes.find((note) => String(note.id) === String(id));
  const notes = document.querySelectorAll('[data-professional-note]');
  function payload() {
    const active = form.querySelector(`[data-professional-format="${el('note-format').value}"]`);
    const content = {unavailable_reasons: {}};
    active.querySelectorAll('[data-note-field]').forEach((input) => { content[input.dataset.noteField] = input.value; });
    active.querySelectorAll('[data-note-reason]').forEach((input) => { if (input.value.trim()) content.unavailable_reasons[input.dataset.noteReason] = input.value; });
    return content;
  }
  let dirty = false;
  if (form) {
    form.addEventListener('input', () => { dirty = true; });
    el('note-format').addEventListener('change', () => {
      form.querySelectorAll('[data-professional-format]').forEach((fieldset) => {
        fieldset.hidden = fieldset.dataset.professionalFormat !== el('note-format').value;
      });
    });
    el('note-new').addEventListener('click', () => {
      if (dirty && !window.confirm('Buang perubahan catatan yang belum disimpan?')) return;
      form.reset(); el('note-id').value = ''; el('note-version').value = ''; dirty = false;
      el('note-format').dispatchEvent(new Event('change'));
    });
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const id = el('note-id').value;
      if (!id) {
        if (!el('service')?.value) { api.report('Pilih layanan yang ditinjau sebelum membuat CPPT.'); return; }
        api.send('cppt_create', {service_id: Number(el('service').value), format_code: el('note-format').value, payload: payload()});
      } else {
        const note = find(id);
        if (el('note-format').value !== note.format_code) { api.report('Format catatan tersimpan tidak boleh diganti; buat catatan baru.'); return; }
        const fields = {note_id: Number(id), note_version: Number(el('note-version').value), payload: payload()};
        if (note.status === 'SIGNED') { fields.reason = el('note-reason').value; api.send('cppt_correct', fields); }
        else api.send('cppt_save', fields);
      }
    });
  }
  notes.forEach((article) => {
    const note = find(article.dataset.professionalNote);
    article.querySelector('[data-professional-edit]')?.addEventListener('click', () => {
      if (!form || dirty && !window.confirm('Ganti perubahan yang belum disimpan dengan catatan ini?')) return;
      el('note-id').value = String(note.id); el('note-version').value = String(note.version);
      el('note-format').value = note.format_code; el('note-format').dispatchEvent(new Event('change'));
      const active = form.querySelector(`[data-professional-format="${note.format_code}"]`);
      active.querySelectorAll('[data-note-field]').forEach((input) => { input.value = note.content[input.dataset.noteField] || ''; });
      active.querySelectorAll('[data-note-reason]').forEach((input) => { input.value = note.content.unavailable_reasons?.[input.dataset.noteReason] || ''; });
      el('note-reason').value = ''; dirty = false; form.scrollIntoView({block: 'start'}); active.querySelector('textarea').focus();
    });
    article.querySelector('[data-professional-sign]')?.addEventListener('click', () => {
      if (window.confirm('Tandatangani isi catatan ini sebagai penulis?')) api.send('cppt_sign', {note_id: note.id, note_version: note.version});
    });
    article.querySelector('[data-professional-verify]')?.addEventListener('click', () => {
      if (window.confirm('Verifikasi revisi catatan ini sebagai DPJP yang ditugaskan?')) api.send('cppt_verify', {note_id: note.id, note_version: note.version});
    });
  });
})();
