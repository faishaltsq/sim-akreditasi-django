/* Langkah 9 — CPPT multiprofesi, TTE kanvas, tindakan poli, unggahan panel (F6).
 *
 * Semua keputusan klinis tetap di server: berkas ini hanya merakit payload dan
 * menampilkan balasan. Tidak ada dosis, kode, atau status yang ditentukan di
 * sini — chip, status kepatuhan, dan pilihan tindakan dirender server dari
 * matriks/katalog.
 */
(function () {
  'use strict';

  var root = document.querySelector('[data-poli-root]');
  if (!root) return;

  var actionUrl = root.getAttribute('data-action-url');
  var version = Number(root.getAttribute('data-version') || 0);

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function newRequestId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function setStatus(node, message, isError) {
    if (!node) return;
    node.textContent = message;
    node.style.color = isError ? '#b91c1c' : '#166534';
  }

  function postJson(url, body) {
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

  function postForm(url, formData) {
    formData.append('csrfmiddlewaretoken', csrfToken());
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() },
      body: formData
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      });
    });
  }

  /* ── CPPT: chip S, kepatuhan, TTE kanvas ─────────────────────────────── */
  var cpptForm = root.querySelector('[data-poli-cppt-form]');
  var canvas = root.querySelector('[data-cppt-canvas]');
  var drawing = false;
  var dirty = false;

  function payloadFromForm() {
    var payload = {
      subjektif: '', objektif: '', asesmen: '', plan: '',
      keluhan_chips: [], kepatuhan_terapi: '', kepatuhan_obat: {}
    };
    root.querySelectorAll('[data-cppt-field]').forEach(function (node) {
      payload[node.getAttribute('data-cppt-field')] = node.value;
    });
    root.querySelectorAll('[data-cppt-chip]').forEach(function (node) {
      if (node.checked) payload.keluhan_chips.push(node.value);
    });
    var compliance = root.querySelector('[data-cppt-compliance]');
    if (compliance) payload.kepatuhan_terapi = compliance.value;
    root.querySelectorAll('[data-cppt-drugs] [data-drug-id]').forEach(function (row) {
      var status = row.querySelector('[data-drug-status]');
      var note = row.querySelector('[data-drug-note]');
      if (!status || !status.value) return;
      payload.kepatuhan_obat[row.getAttribute('data-drug-id')] = {
        status: status.value,
        catatan: note ? note.value : ''
      };
    });
    return payload;
  }

  function tteImage() {
    if (!canvas || !dirty) return '';
    return canvas.toDataURL('image/png');
  }

  function selectedService() {
    var select = root.querySelector('[data-cppt-service]');
    if (!select || !select.value) return null;
    var option = select.options[select.selectedIndex];
    return { id: select.value, format: option.getAttribute('data-format') || 'SOAP' };
  }

  function createNote(statusNode, done) {
    var service = selectedService();
    if (!service) {
      setStatus(statusNode, 'Pilih layanan/profesi lebih dulu.', true);
      return;
    }
    postJson(actionUrl, {
      operation: 'cppt_create',
      fields: { service_id: service.id, format_code: service.format, payload: payloadFromForm() },
      version: version,
      request_id: newRequestId()
    }).then(function (result) {
      if (!result.ok) {
        setStatus(statusNode, result.data.error || 'CPPT gagal dibuat.', true);
        return;
      }
      version = result.data.version;
      root.setAttribute('data-version', String(version));
      done(result.data);
    });
  }

  function saveNote(statusNode) {
    createNote(statusNode, function (data) {
      postJson(actionUrl, {
        operation: 'cppt_save',
        fields: { note_id: data.cppt_id, note_version: data.note_version, payload: payloadFromForm() },
        version: version,
        request_id: newRequestId()
      }).then(function (result) {
        if (!result.ok) {
          setStatus(statusNode, result.data.error || 'Draft CPPT gagal disimpan.', true);
          return;
        }
        setStatus(statusNode, 'Draft CPPT tersimpan. Muat ulang untuk melihat catatan.', false);
      });
    });
  }

  function signNote(statusNode) {
    var credential = root.querySelector('[data-cppt-credential]');
    var image = tteImage();
    if (!image) {
      setStatus(statusNode, 'Tanda tangan pada kanvas wajib diisi sebelum menandatangani.', true);
      return;
    }
    if (!credential || !credential.checked) {
      setStatus(statusNode, 'Konfirmasi kredensial penanda tangan wajib dicentang.', true);
      return;
    }
    createNote(statusNode, function (data) {
      postJson(actionUrl, {
        operation: 'cppt_sign',
        fields: {
          note_id: data.cppt_id,
          note_version: data.note_version,
          ttd_image: image,
          credential_confirmed: true
        },
        version: version,
        request_id: newRequestId()
      }).then(function (result) {
        if (!result.ok) {
          setStatus(statusNode, result.data.error || 'Tanda tangan gagal.', true);
          return;
        }
        setStatus(statusNode, 'Catatan ditandatangani; batas verifikasi DPJP 24 jam tercatat.', false);
      });
    });
  }

  if (cpptForm) {
    var cpptStatus = cpptForm.querySelector('[data-poli-status]');

    cpptForm.querySelector('[data-cppt-save]').addEventListener('click', function () {
      saveNote(cpptStatus);
    });
    cpptForm.querySelector('[data-cppt-sign]').addEventListener('click', function () {
      signNote(cpptStatus);
    });

    // Chip keluhan menambah teks S supaya penulis tidak mengetik ulang.
    root.querySelectorAll('[data-cppt-chip]').forEach(function (chip) {
      chip.addEventListener('change', function () {
        var subjektif = root.querySelector('[data-cppt-field="subjektif"]');
        if (!subjektif) return;
        var label = chip.parentNode.textContent.trim();
        var lines = subjektif.value.split('\n').map(function (line) { return line.trim(); });
        if (chip.checked) {
          if (lines.indexOf(label) === -1) lines.push(label);
        } else {
          lines = lines.filter(function (line) { return line !== label; });
        }
        subjektif.value = lines.filter(Boolean).join('\n');
      });
    });

    if (canvas) {
      var context = canvas.getContext('2d');
      context.lineWidth = 2;
      context.lineCap = 'round';
      context.strokeStyle = '#111827';

      function position(event) {
        var rect = canvas.getBoundingClientRect();
        var point = event.touches ? event.touches[0] : event;
        return {
          x: (point.clientX - rect.left) * (canvas.width / rect.width),
          y: (point.clientY - rect.top) * (canvas.height / rect.height)
        };
      }

      function start(event) {
        event.preventDefault();
        drawing = true;
        dirty = true;
        var p = position(event);
        context.beginPath();
        context.moveTo(p.x, p.y);
      }

      function move(event) {
        if (!drawing) return;
        event.preventDefault();
        var p = position(event);
        context.lineTo(p.x, p.y);
        context.stroke();
      }

      function stop() { drawing = false; }

      canvas.addEventListener('mousedown', start);
      canvas.addEventListener('mousemove', move);
      canvas.addEventListener('mouseup', stop);
      canvas.addEventListener('mouseleave', stop);
      canvas.addEventListener('touchstart', start);
      canvas.addEventListener('touchmove', move);
      canvas.addEventListener('touchend', stop);

      var clear = root.querySelector('[data-cppt-clear]');
      if (clear) {
        clear.addEventListener('click', function () {
          context.clearRect(0, 0, canvas.width, canvas.height);
          dirty = false;
        });
      }
    }
  }

  root.querySelectorAll('[data-poli-verify]').forEach(function (button) {
    button.addEventListener('click', function () {
      var noteId = button.getAttribute('data-poli-verify');
      var noteVersion = button.getAttribute('data-note-version');
      var statusNode = root.querySelector('[data-poli-status]');
      postJson(actionUrl, {
        operation: 'cppt_verify',
        fields: { note_id: Number(noteId), note_version: Number(noteVersion) },
        version: version,
        request_id: newRequestId()
      }).then(function (result) {
        if (!result.ok) {
          setStatus(statusNode, result.data.error || 'Verifikasi ditolak.', true);
          return;
        }
        setStatus(statusNode, 'Catatan terverifikasi DPJP.', false);
      });
    });
  });

  /* ── Tindakan poli: tambah + void beralasan ──────────────────────────── */
  var tindakan = root.querySelector('[data-poli-tindakan]');
  if (tindakan) {
    var addUrl = tindakan.getAttribute('data-add-url');
    var voidUrl = tindakan.getAttribute('data-void-url');
    var tindakanForm = tindakan.querySelector('[data-tindakan-form]');
    var tindakanStatus = tindakan.querySelector('[data-poli-status]');

    if (tindakanForm) {
      tindakanForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var formData = new FormData();
        formData.append('kode', tindakanForm.querySelector('[data-tindakan-code]').value);
        formData.append('pelaksana', tindakanForm.querySelector('[data-tindakan-pelaksana]').value);
        formData.append('quantity', tindakanForm.querySelector('[data-tindakan-qty]').value);
        postForm(addUrl, formData).then(function (result) {
          if (!result.ok) {
            setStatus(tindakanStatus, result.data.error || 'Tindakan gagal ditambahkan.', true);
            return;
          }
          setStatus(tindakanStatus,
            'Tindakan ' + result.data.kode + ' tercatat; tagihan Rp ' + (result.data.billing_amount || '—') +
            (result.data.ep_code ? '; EP ' + result.data.ep_code : '') + '.', false);
        });
      });
    }

    tindakan.querySelectorAll('[data-tindakan-void]').forEach(function (button) {
      button.addEventListener('click', function () {
        var reason = window.prompt('Alasan pembatalan tagihan (5–2000 karakter):');
        if (!reason) return;
        var formData = new FormData();
        formData.append('line_id', button.getAttribute('data-tindakan-void'));
        formData.append('reason', reason);
        formData.append('request_id', newRequestId());
        postForm(voidUrl, formData).then(function (result) {
          if (!result.ok) {
            setStatus(tindakanStatus, result.data.error || 'Pembatalan ditolak.', true);
            return;
          }
          setStatus(tindakanStatus, 'Tagihan dibatalkan dengan alasan tercatat; baris asli dipertahankan.', false);
        });
      });
    });
  }

  /* ── Panel kanan: unggahan pendukung dengan SHA-256 ──────────────────── */
  var support = root.querySelector('[data-poli-support]');
  if (support) {
    var uploadUrl = support.getAttribute('data-upload-url');
    var uploadForm = support.querySelector('[data-poli-upload-form]');
    var uploadStatus = support.querySelector('[data-poli-upload-status]');

    function sha256Hex(buffer) {
      if (!window.crypto || !window.crypto.subtle) return Promise.resolve('');
      return window.crypto.subtle.digest('SHA-256', buffer).then(function (digest) {
        return Array.prototype.map.call(new Uint8Array(digest), function (byte) {
          return byte.toString(16).padStart(2, '0');
        }).join('');
      });
    }

    if (uploadForm) {
      uploadForm.addEventListener('submit', function (event) {
        event.preventDefault();
        var input = uploadForm.querySelector('input[type="file"]');
        if (!input || !input.files.length) {
          setStatus(uploadStatus, 'Pilih berkas lebih dulu.', true);
          return;
        }
        var file = input.files[0];
        file.arrayBuffer().then(function (buffer) {
          return sha256Hex(buffer).then(function (hash) {
            if (!hash) {
              setStatus(uploadStatus, 'Peramban ini tidak menyediakan SHA-256; unggahan ditolak.', true);
              return;
            }
            var formData = new FormData();
            formData.append('jenis', uploadForm.querySelector('select[name="jenis"]').value);
            formData.append('filename', file.name);
            formData.append('size', String(file.size));
            formData.append('sha256', hash);
            formData.append('file', file);
            postForm(uploadUrl, formData).then(function (result) {
              if (!result.ok) {
                setStatus(uploadStatus, result.data.error || 'Unggahan ditolak.', true);
                return;
              }
              setStatus(uploadStatus, 'Dokumen tersimpan (id ' + result.data.attachment_id + ').', false);
            });
          });
        });
      });
    }

    support.querySelectorAll('[data-poli-preview]').forEach(function (link) {
      link.addEventListener('mouseenter', function () {
        var output = support.querySelector('[data-poli-preview-output]');
        if (!output) return;
        output.textContent = link.getAttribute('data-preview-title') + ' — ' +
          link.getAttribute('data-preview-file') + ' (' + link.getAttribute('data-preview-version') + ')';
      });
    });
  }
})();
