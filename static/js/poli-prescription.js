/* Langkah 8 POLI-JANTUNG: diagnosis, komposer resep, pintasan GDMT, toolbar (F5).
 *
 * Aturan yang dijaga di sini hanya tata kelola formulir; semua penegakan tetap
 * di server (unique diagnosis utama, validasi regimen, jumlah baris per produk).
 * Karena itu kegagalan server ditampilkan apa adanya, bukan ditelan.
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-poli-root]');
  if (!root) return;

  var actionUrl = root.getAttribute('data-action-url');
  var step = root.getAttribute('data-step');
  var version = Number(root.getAttribute('data-version') || 0);

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function newRequestId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function post(body) {
    return fetch(actionUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body)
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      });
    });
  }

  function setStatus(node, message, isError) {
    var target = node || root.querySelector('[data-poli-status]');
    if (!target) return;
    target.textContent = message;
    target.style.color = isError ? '#b91c1c' : '#166534';
  }

  function applyVersion(next) {
    version = Number(next);
    root.setAttribute('data-version', String(version));
    var badge = root.querySelector('[data-poli-version]');
    if (badge) badge.textContent = String(version);
  }

  /* ── Toolbar metode input (F5.7) ──────────────────────────────────────── */
  var toolbar = root.querySelector('[data-poli-toolbar]');
  var modeInput = root.querySelector('#poli-field-input_mode');
  var modeValue = root.querySelector('[data-poli-mode-value]');

  if (toolbar) {
    toolbar.addEventListener('click', function (event) {
      var button = event.target.closest('[data-poli-mode]');
      if (!button) return;
      var mode = button.getAttribute('data-poli-mode');
      if (modeInput) modeInput.value = mode;
      if (modeValue) modeValue.textContent = mode;
      toolbar.querySelectorAll('[data-poli-mode]').forEach(function (node) {
        var active = node === button;
        node.classList.toggle('is-active', active);
        node.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
    });
  }

  /* ── Diagnosis (F5.1) ─────────────────────────────────────────────────── */
  var dxSection = root.querySelector('[data-poli-diagnosis]');
  if (dxSection) {
    var dxAdd = dxSection.querySelector('[data-poli-dx-add]');
    if (dxAdd) {
      dxAdd.addEventListener('click', function () {
        var code = (dxSection.querySelector('[data-poli-dx-code]').value || '').trim();
        var text = (dxSection.querySelector('[data-poli-dx-text]').value || '').trim();
        var primaryBox = dxSection.querySelector('[data-poli-dx-primary]');
        var primary = Boolean(primaryBox && primaryBox.checked);
        var status = dxSection.querySelector('[data-poli-status]');
        if (!code && !text) {
          setStatus(status, 'Isi kode ICD-10 atau teks diagnosis.', true);
          return;
        }
        var change = {
          op: 'upsert',
          temp_id: 'dx-' + newRequestId(),
          mode: code ? 'MASTER' : 'MANUAL',
          code: code,
          text: text,
          is_primary: primary
        };
        var changes = [];
        // Satu diagnosis utama aktif: mempromosikan diagnosis baru sekaligus
        // menurunkan yang lama dalam satu permintaan, karena server menolak dua
        // diagnosis utama dalam satu keadaan.
        var currentPrimaryId = primaryBox && primaryBox.getAttribute('data-poli-primary-id');
        if (primary && currentPrimaryId) {
          changes.push({
            op: 'upsert',
            id: Number(currentPrimaryId),
            mode: primaryBox.getAttribute('data-poli-primary-mode'),
            code: primaryBox.getAttribute('data-poli-primary-code') || '',
            text: primaryBox.getAttribute('data-poli-primary-text') || '',
            is_primary: false
          });
        }
        changes.push(change);
        setStatus(status, 'Menyimpan diagnosis…', false);
        post({ operation: 'diagnosis_set', fields: { changes: changes }, version: version, request_id: newRequestId() })
          .then(function (result) {
            if (result.ok) {
              window.location.reload();
              return;
            }
            setStatus(status, result.data.error || 'Diagnosis ditolak.', true);
          })
          .catch(function () { setStatus(status, 'Gagal menghubungi server.', true); });
      });
    }
  }

  /* ── Komposer resep + pintasan GDMT (F5.3/F5.4) ───────────────────────── */
  var rxSection = root.querySelector('[data-poli-rx]');
  if (!rxSection) return;

  var rowsBody = rxSection.querySelector('[data-poli-rx-rows]');
  var depo = rxSection.querySelector('[data-poli-rx-depo]');
  var rxStatus = rxSection.querySelector('[data-poli-status]');
  // Draf yang sudah ada harus dikirim balik supaya penyimpanan berikutnya
  // memperbarui baris yang sama, bukan membuat resep kedua.
  var prescriptionId = Number(rxSection.getAttribute('data-prescription-id') || 0) || null;

  function rowFor(productId) {
    return rowsBody.querySelector('[data-poli-rx-row][data-product-id="' + productId + '"]');
  }

  function makeRow(product) {
    var tr = document.createElement('tr');
    tr.setAttribute('data-poli-rx-row', '');
    tr.setAttribute('data-product-id', product.id);
    tr.innerHTML =
      '<td><input type="radio" name="poli-rx-selected" aria-label="Pilih baris"></td>' +
      '<td data-poli-rx-name></td>' +
      '<td><input type="text" data-poli-rx-dose></td>' +
      '<td><input type="text" data-poli-rx-dose-unit></td>' +
      '<td><input type="text" data-poli-rx-times></td>' +
      '<td><input type="text" data-poli-rx-days></td>' +
      '<td><input type="text" data-poli-rx-route></td>' +
      '<td><button type="button" class="btn btn-sm btn-outline-danger" data-poli-rx-remove aria-label="Hapus baris">×</button></td>';
    tr.querySelector('[data-poli-rx-name]').textContent = product.name;
    tr.querySelector('[data-poli-rx-dose-unit]').value = product.unit || '';
    tr.querySelector('[data-poli-rx-route]').value = (product.routes && product.routes[0]) || '';
    return tr;
  }

  rowsBody.addEventListener('click', function (event) {
    var remove = event.target.closest('[data-poli-rx-remove]');
    if (remove) {
      var row = remove.closest('[data-poli-rx-row]');
      if (row) row.remove();
    }
  });

  rxSection.querySelectorAll('[data-poli-gdmt-add]').forEach(function (button) {
    button.addEventListener('click', function () {
      var product = {
        id: button.getAttribute('data-product-id'),
        name: button.getAttribute('data-product-name'),
        unit: button.getAttribute('data-product-unit'),
        routes: (button.getAttribute('data-product-routes') || '').split(',').filter(Boolean)
      };
      // Satu baris per produk: klik kedua memperbarui baris yang sama, bukan
      // menambah baris ganda (S9-L1-19 "satu sumber kebenaran").
      var existing = rowFor(product.id);
      if (!existing) {
        rowsBody.appendChild(makeRow(product));
      }
      var target = rowFor(product.id);
      if (target) {
        var radio = target.querySelector('input[type="radio"]');
        if (radio) radio.checked = true;
      }
      setStatus(rxStatus, existing ? 'Baris diperbarui.' : 'Baris ditambahkan.', false);
    });
  });

  var applyButton = rxSection.querySelector('[data-poli-gdmt-apply]');
  if (applyButton) {
    applyButton.addEventListener('click', function () {
      var selected = rowsBody.querySelector('input[name="poli-rx-selected"]:checked');
      if (!selected) {
        setStatus(rxStatus, 'Pilih satu baris terlebih dahulu.', true);
        return;
      }
      var adjust = rxSection.querySelector('[data-poli-gdmt-adjust]').value;
      var note = (rxSection.querySelector('[data-poli-gdmt-note]').value || '').trim();
      if (!adjust) {
        setStatus(rxStatus, 'Pilih penyesuaian dosis.', true);
        return;
      }
      var row = selected.closest('[data-poli-rx-row]');
      row.setAttribute('data-gdmt-adjust', adjust);
      row.setAttribute('data-gdmt-note', note);
      setStatus(rxStatus, 'Penyesuaian diterapkan pada baris terpilih; simpan draf untuk menyimpan.', false);
    });
  }

  function collectLines() {
    var lines = [];
    rowsBody.querySelectorAll('[data-poli-rx-row]').forEach(function (row) {
      var regimen = {
        schema_version: 1,
        frequency: 'FIXED',
        dose: (row.querySelector('[data-poli-rx-dose]').value || '').trim(),
        dose_unit: (row.querySelector('[data-poli-rx-dose-unit]').value || '').trim(),
        times_per_day: (row.querySelector('[data-poli-rx-times]').value || '').trim(),
        duration_days: (row.querySelector('[data-poli-rx-days]').value || '').trim(),
        route: (row.querySelector('[data-poli-rx-route]').value || '').trim()
      };
      var adjust = row.getAttribute('data-gdmt-adjust');
      if (adjust) {
        // Catatan klinis penyesuaian ikut ke ``regimen.instructions`` — kunci
        // yang sudah diterima ``calculate_quantity`` dan ikut tersimpan di
        // snapshot resep serta audit.
        var note = row.getAttribute('data-gdmt-note') || '';
        regimen.instructions = 'GDMT: ' + adjust + (note ? ' — ' + note : '');
      }
      lines.push({
        product_id: Number(row.getAttribute('data-product-id')),
        kind: 'OBAT',
        regimen: regimen
      });
    });
    return lines;
  }

  function saveDraft(status) {
    var lines = collectLines();
    if (!lines.length) {
      setStatus(status, 'Belum ada baris obat.', true);
      return Promise.resolve(null);
    }
    var serving = depo ? depo.value : '';
    var fields = { lines: lines, catatan_dokter: '' };
    if (prescriptionId) fields.prescription_id = prescriptionId;
    if (serving) fields.serving_unit_id = Number(serving);
    setStatus(status, 'Menyimpan draf resep…', false);
    return post({ operation: 'prescription_save', fields: fields, version: version, request_id: newRequestId() })
      .then(function (result) {
        if (result.ok) {
          applyVersion(result.data.version);
          prescriptionId = result.data.prescription_id || prescriptionId;
          rxSection.setAttribute('data-prescription-id', String(prescriptionId || ''));
          setStatus(status, 'Draf resep tersimpan (versi ' + result.data.version + ').', false);
          return result.data.prescription_id;
        }
        setStatus(status, result.data.error || 'Draf resep ditolak.', true);
        return null;
      });
  }

  var saveButton = rxSection.querySelector('[data-poli-rx-save]');
  if (saveButton) {
    saveButton.addEventListener('click', function () { saveDraft(rxStatus); });
  }

  var submitButton = rxSection.querySelector('[data-poli-rx-submit]');
  if (submitButton) {
    submitButton.addEventListener('click', function () {
      saveDraft(rxStatus).then(function (prescriptionId) {
        if (!prescriptionId) return;
        setStatus(rxStatus, 'Mengirim ke farmasi…', false);
        post({
          operation: 'prescription_submit',
          fields: { prescription_id: prescriptionId, acknowledgements: [] },
          version: version,
          request_id: newRequestId()
        }).then(function (result) {
          if (result.ok) {
            applyVersion(result.data.version);
            setStatus(rxStatus, 'Resep terkirim ke farmasi.', false);
            window.location.reload();
            return;
          }
          setStatus(rxStatus, result.data.error || 'Pengiriman ditolak.', true);
        });
      });
    });
  }
})();
