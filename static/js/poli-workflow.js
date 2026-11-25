/* Simpan draft & aksi asesmen POLI-JANTUNG (F1.7).
 * Versi optimistik: setiap POST membawa versi yang dirender server; balasan
 * 409 berarti draft sudah bergerak dan pengguna harus memuat ulang.
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-poli-root]');
  if (!root) return;

  var version = Number(root.getAttribute('data-version') || 0);
  var step = root.getAttribute('data-step');
  var draftUrl = root.getAttribute('data-draft-url');
  var actionUrl = root.getAttribute('data-action-url');

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function statusNode(node) {
    return node || root.querySelector('[data-poli-status]');
  }

  function setStatus(node, message, isError) {
    var target = statusNode(node);
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

  function post(url, body) {
    return fetch(url, {
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

  function newRequestId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function assign(payload, name, value) {
    // ``fisik_kardio.murmur_derajat`` → payload.fisik_kardio.murmur_derajat;
    // layanan menyatukan dict ini kembali sebelum validasi.
    var parts = name.split('.');
    var target = payload;
    for (var i = 0; i < parts.length - 1; i += 1) {
      if (!target[parts[i]] || typeof target[parts[i]] !== 'object') target[parts[i]] = {};
      target = target[parts[i]];
    }
    target[parts[parts.length - 1]] = value;
  }

  function collectFields(form) {
    var payload = {};
    var checked = {};
    Array.prototype.forEach.call(form.querySelectorAll('[name]'), function (field) {
      if (field.disabled) return;
      if (field.type === 'checkbox') {
        // Multi-select: satu kunci berisi daftar nilai yang dicentang.
        if (!field.checked) return;
        if (!checked[field.name]) { checked[field.name] = []; assign(payload, field.name, checked[field.name]); }
        checked[field.name].push(field.value);
        return;
      }
      if (field.hasAttribute('data-poli-json')) {
        var raw = field.value.trim();
        if (!raw) { assign(payload, field.name, []); return; }
        try {
          assign(payload, field.name, JSON.parse(raw));
        } catch (error) {
          assign(payload, field.name, raw);
        }
        return;
      }
      if (field.type === 'number') {
        assign(payload, field.name, field.value === '' ? null : Number(field.value));
      } else {
        assign(payload, field.name, field.value);
      }
    });
    return payload;
  }

  var stepForm = document.getElementById('poli-step-form');
  if (stepForm) {
    // AMBIGU-17(b): sub-field teks hanya tampil untuk satu nilai pemicu, dan
    // nilainya dikosongkan saat disembunyikan supaya teks basi tidak pernah
    // ikut terkirim bersama kode lokasi lain.
    Array.prototype.forEach.call(stepForm.querySelectorAll('[data-poli-show-when]'), function (node) {
      var trigger = stepForm.querySelector('[name="' + node.getAttribute('data-poli-show-when') + '"]');
      if (!trigger) return;
      var expected = node.getAttribute('data-poli-show-value');
      function sync() {
        var show = trigger.value === expected;
        node.hidden = !show;
        if (!show) {
          var input = node.querySelector('input, textarea');
          if (input) input.value = '';
        }
      }
      trigger.addEventListener('change', sync);
      sync();
    });
    stepForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var node = stepForm.querySelector('[data-poli-status]');
      setStatus(node, 'Menyimpan…', false);
      post(draftUrl, { fields: collectFields(stepForm), version: version }).then(function (result) {
        if (result.ok) {
          applyVersion(result.data.version);
          setStatus(node, 'Tersimpan. Versi ' + result.data.version + '.', false);
          return;
        }
        if (result.status === 409) {
          setStatus(node, 'Konflik versi — muat ulang halaman sebelum menyimpan lagi.', true);
          return;
        }
        var fields = result.data.fields || {};
        var first = Object.keys(fields)[0];
        setStatus(node, (first ? first + ': ' : '') + (result.data.error || 'Gagal menyimpan.'), true);
      }).catch(function () {
        setStatus(node, 'Gagal menghubungi server.', true);
      });
    });
  }

  Array.prototype.forEach.call(root.querySelectorAll('[data-poli-action]'), function (button) {
    button.addEventListener('click', function () {
      var operation = button.getAttribute('data-poli-action');
      var node = button.parentNode.querySelector('[data-poli-status]');
      var payload;
      if (operation === 'sign') {
        payload = { section: 'MEDIS' };
      } else if (operation === 'addendum') {
        var reasonNode = document.querySelector('[data-addendum-field="reason"]');
        var textNode = document.querySelector('[data-addendum-field="text"]');
        payload = {
          section: 'MEDIS',
          reason: reasonNode ? reasonNode.value : '',
          text: textNode ? textNode.value : ''
        };
      } else {
        var resume = document.getElementById('poli-resume');
        var bed = document.getElementById('poli-bed');
        payload = { resume: resume ? resume.value : '' };
        // S10-L1-05 cabang Admisi Rawat Inap: bed dipilih di panel penutupan.
        if (bed && bed.value !== '') payload.bed_id = Number(bed.value);
      }
      setStatus(node, 'Memproses…', false);
      post(actionUrl, {
        operation: operation,
        fields: payload,
        version: version,
        request_id: newRequestId()
      }).then(function (result) {
        if (result.ok) {
          applyVersion(result.data.version);
          setStatus(node, 'Selesai. Versi ' + result.data.version + '.', false);
          if (operation === 'finalize' || operation === 'addendum') window.location.reload();
          return;
        }
        setStatus(node, result.data.error || 'Aksi ditolak.', true);
      }).catch(function () {
        setStatus(node, 'Gagal menghubungi server.', true);
      });
    });
  });
})();
