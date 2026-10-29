// Auto-fill for the HC credential submission form.
//
// Selecting an employee fetches their current placement, profession and
// licence state from the JSON endpoint and pre-fills Unit Kerja. The native
// <select> stays authoritative: every auto-filled value is still editable, and
// the badge switches to "Diubah manual" the moment the operator overrides it,
// so the form never claims a value came from Kepegawaian when it did not.
(function () {
    'use strict';

    var form = document.querySelector('[data-kredensial-autofill]');
    if (!form) return;

    var endpointTemplate = form.getAttribute('data-profile-url');
    var employeeField = form.querySelector('[data-kredensial-employee]');
    var unitField = form.querySelector('[data-kredensial-unit]');
    if (!endpointTemplate || !employeeField || !unitField) return;

    var badge = form.querySelector('[data-kredensial-badge]');
    var panel = form.querySelector('[data-kredensial-panel]');
    var autoFilledUnit = null;

    function setBadge(text, variant) {
        if (!badge) return;
        badge.textContent = text;
        badge.className = 'badge ' + variant;
        badge.hidden = !text;
    }

    function renderPanel(data) {
        if (!panel) return;
        var rows = [
            ['Profesi', data.profesi || '—'],
            ['Jabatan', data.jabatan || '—'],
            ['Jenjang', data.jenjang || '—'],
            ['Masa Kerja', data.masa_kerja || '—'],
        ];
        var html = '<dl class="row g-1 small mb-2">';
        rows.forEach(function (row) {
            html += '<dt class="col-5 text-muted fw-normal">' + row[0] + '</dt>';
            html += '<dd class="col-7 mb-0 fw-semibold">' + row[1] + '</dd>';
        });
        html += '</dl><div class="d-flex gap-2 flex-wrap">';
        (data.licenses || []).forEach(function (lic) {
            var variant = lic.label === 'Berlaku'
                ? 'bg-success'
                : (lic.label === 'Belum ada' ? 'bg-secondary' : 'bg-warning text-dark');
            var detail = lic.nomor ? ' (' + lic.nomor + ')' : '';
            html += '<span class="badge ' + variant + '">' +
                lic.subtype + ': ' + lic.label + detail + '</span>';
        });
        html += '</div>';
        panel.innerHTML = html;
        panel.hidden = false;
    }

    function clearPanel() {
        if (panel) {
            panel.innerHTML = '';
            panel.hidden = true;
        }
        setBadge('', 'bg-secondary');
    }

    function fillUnit(unit) {
        if (!unit) return;
        var option = unitField.querySelector('option[value="' + unit.id + '"]');
        if (!option) {
            // The employee's current unit is outside the operator's grant; the
            // form must not silently invent an option for it.
            setBadge('Unit di luar wewenang Anda', 'bg-warning text-dark');
            return;
        }
        unitField.value = unit.id;
        autoFilledUnit = unit.id;
        setBadge('Auto-filled dari Data Kepegawaian', 'bg-success');
    }

    employeeField.addEventListener('change', function () {
        var id = employeeField.value;
        if (!id) {
            clearPanel();
            return;
        }
        var url = endpointTemplate.replace('00000000-0000-0000-0000-000000000000', id);
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(function (response) {
                if (!response.ok) throw new Error('profil tidak tersedia');
                return response.json();
            })
            .then(function (data) {
                renderPanel(data);
                fillUnit(data.unit_kerja);
            })
            .catch(function () {
                clearPanel();
                setBadge('Gagal memuat profil pegawai', 'bg-danger');
            });
    });

    unitField.addEventListener('change', function () {
        if (autoFilledUnit !== null && unitField.value !== autoFilledUnit) {
            setBadge('Diubah manual', 'bg-info text-dark');
        }
    });

    // Re-run on load so a bound form (validation error) keeps the panel in sync
    // with the employee that is already selected.
    if (employeeField.value) {
        employeeField.dispatchEvent(new Event('change'));
    }
})();
