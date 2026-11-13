(() => {
  'use strict';
  const root = document.getElementById('igd-physical-exam');
  const form = document.getElementById('igd-step-form');
  if (!root || !form) return;
  const input = form.elements.namedItem('secondary_survey_detail');
  const summary = document.getElementById('igd-exam-summary');
  const status = document.getElementById('igd-save-status');
  const catalogue = JSON.parse(document.getElementById('igd-exam-catalogue').textContent);
  const rows = [...root.querySelectorAll('[data-exam-status]')].map(select => select.closest('[data-exam-section]'));
  const readonly = root.dataset.readonly === 'true';
  const hasLegacy = root.dataset.hasLegacy === 'true';
  let secondary = {};
  let exam = {};
  const empty = () => ({status:'UNASSESSED', findings:[], note:'', reason:''});
  function load() {
    secondary = JSON.parse(input.value || '{}') || {};
    exam = secondary.head_to_toe || {schema_version:1, sections:{}};
    render();
  }
  function render() {
    const lines = [];
    rows.forEach(row => {
      const key = row.dataset.examSection;
      const value = exam.sections[key] || empty();
      const definition = catalogue.find(item => item.key === key);
      row.querySelector('[data-exam-status]').value = value.status;
      row.querySelectorAll('input[type=checkbox]').forEach(box => { box.checked = value.findings.includes(box.value); });
      row.querySelector('[data-exam-note]').value = value.note;
      row.querySelector('[data-exam-reason]').value = value.reason;
      row.querySelector('[data-exam-choices]').hidden = value.status !== 'EXAMINED';
      row.querySelector('[data-exam-note-wrap]').hidden = !value.note && !value.findings.some(code => code !== 'normal');
      row.querySelector('[data-exam-reason-wrap]').hidden = value.status !== 'NOT_EXAMINED';
      if (value.status === 'NOT_EXAMINED') lines.push(`${definition.label}: Tidak diperiksa — ${value.reason.trim()}`);
      if (value.status === 'EXAMINED') {
        const labels = definition.options.filter(option => value.findings.includes(option.code)).map(option => option.label).join('; ');
        lines.push(`${definition.label}: ${labels}${value.note.trim() ? ' — ' + value.note.trim() : ''}`);
      }
    });
    summary.value = lines.join('\n');
  }
  function changed() {
    secondary.head_to_toe = exam;
    input.value = JSON.stringify(secondary);
    input.dispatchEvent(new Event('input', {bubbles:true}));
    render();
  }
  if (!readonly) {
    rows.forEach(row => {
      const key = row.dataset.examSection;
      const select = row.querySelector('[data-exam-status]');
      select.addEventListener('change', () => {
        const old = exam.sections[key] || empty();
        if (select.value !== old.status && (old.findings.length || old.note) && !window.confirm('Status berubah. Temuan pilihan akan dilepas; catatan tetap dipertahankan. Lanjutkan?')) { render(); return; }
        exam.sections[key] = {...old, status:select.value, findings:select.value === 'EXAMINED' ? old.findings : []};
        changed();
      });
      row.querySelectorAll('input[type=checkbox]').forEach(box => box.addEventListener('change', () => {
        const old = exam.sections[key] || empty();
        if (box.checked && box.value === 'normal' && (old.findings.some(code => code !== 'normal') || old.note) && !window.confirm('Ganti temuan abnormal menjadi normal? Catatan tetap dipertahankan untuk ditinjau.')) { render(); return; }
        let findings = [...row.querySelectorAll('input[type=checkbox]:checked')].map(e => e.value);
        if (box.checked) findings = box.value === 'normal' ? ['normal'] : findings.filter(code => code !== 'normal');
        exam.sections[key] = {...old, status:'EXAMINED', findings};
        changed();
      }));
      for (const field of ['note','reason']) {
        row.querySelector(`[data-exam-${field}]`).addEventListener('input', event => {
          exam.sections[key] = {...(exam.sections[key] || empty()), [field]:event.target.value};
          secondary.head_to_toe = exam;
          input.value = JSON.stringify(secondary);
          input.dispatchEvent(new Event('input', {bubbles:true}));
          const pos = event.target.selectionStart;
          render();
          event.target.setSelectionRange(pos,pos);
        });
      }
    });
    document.getElementById('igd-exam-normal').addEventListener('click', () => {
      const filled = [], skipped = [];
      rows.forEach(row => {
        const key = row.dataset.examSection;
        const old = exam.sections[key] || empty();
        if (key === 'genitalia_anus' || hasLegacy || old.status !== 'UNASSESSED' || old.note || old.reason) { skipped.push(key); return; }
        exam.sections[key] = {status:'EXAMINED', findings:['normal'], note:'', reason:''};
        filled.push(key);
      });
      if (filled.length) changed();
      status.textContent = `Normal diterapkan ke ${filled.length} bagian draft; belum disimpan. Dilewati: keadaan umum/kesadaran, ${skipped.join(', ') || '—'}.`;
    });
  }
  document.addEventListener('igd:draft-saved', load);
  load();
})();
