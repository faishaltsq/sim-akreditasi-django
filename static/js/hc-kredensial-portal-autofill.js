// Auto-fill for the portal credential submission form.
//
// When a portal user is logged in, the view always has an employee bound
// to the account (pegawai_hc). The form does not have a dropdown for
// selecting employees, but we still apply the same pattern: show a badge
// when the unit is taken from the employee profile, allow manual override,
// and render a panel with the most recent profile snapshot.
(function () {
    'use strict';

    var form = document.querySelector('[data-kredensial-portal-autofill]');
    if (!form) return;

    var employeeId = form.getAttribute('data-kredensial-employee-id');
    var unitField = form.querySelector('[data-kredensial-unit]');
    if (!employeeId || !unitField) return;

    var badge = form.querySelector('[data-kredensial-portal-badge]');
    var panel = form.querySelector('[data-kredensial-portal-panel]');
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
            setBadge('Unit di luar wewenang Anda', 'bg-warning text-dark');
            return;
        }
        unitField.value = unit.id;
        autoFilledUnit = unit.id;
        setBadge('Unit kerja diambil dari data Kepegawaian', 'bg-success');
    }

    function fetchProfile() {
        fetch(employeeId + '/profil.json', {headers: {'X-Requested-With': 'XMLHttpRequest'}})
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
    }

    unitField.addEventListener('change', function () {
        if (autoFilledUnit !== null && unitField.value !== autoFilledUnit) {
            setBadge('Diubah manual', 'bg-info text-dark');
        }
    });

    fetchProfile();
})();
