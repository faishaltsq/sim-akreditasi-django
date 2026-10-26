document.addEventListener('DOMContentLoaded', function() {
    // Sidebar di-include dua kali (offcanvas mobile + rail desktop), jadi id
    // diberi sufiks per instance. Pasang handler di semua salinan.
    const searchInputs = document.querySelectorAll('[id^="sidebarPokjaSearch"]');
    searchInputs.forEach(function (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase().trim();
            // Batasi pencarian ke sidebar tempat input ini berada.
            const root = this.closest('.sidebar-nav') || document;
            const kelompokContainers = root.querySelectorAll('.sidebar-kelompok');
            
            kelompokContainers.forEach(container => {
                const pokjaLinks = container.querySelectorAll('.nav-pokja');
                let hasVisible = false;
                
                pokjaLinks.forEach(link => {
                    const text = link.textContent.toLowerCase();
                    if (text.includes(query)) {
                        link.style.display = '';
                        hasVisible = true;
                    } else {
                        link.style.display = 'none';
                    }
                });
                
                const collapseEl = container.querySelector('.collapse');
                if (query.length > 0) {
                    container.style.display = hasVisible ? '' : 'none';
                    if (collapseEl && hasVisible) {
                        collapseEl.classList.add('show');
                    }
                } else {
                    container.style.display = '';
                }
            });
        });
    });
});

function getCookie(name) {
    let c = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return c ? c.pop() : '';
}

/* ============================================================
   SIDEBAR COLLAPSE / EXPAND (DESKTOP)
   ============================================================ */
(function () {
    const STORAGE_KEY = 'arima.sidebar.collapsed';
    const root = document.documentElement;

    function syncControls(collapsed) {
        document.querySelectorAll('.sidebar-desktop [data-sidebar-toggle]').forEach(function (el) {
            el.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            const label = collapsed ? 'Perbesar sidebar' : 'Perkecil sidebar';
            el.setAttribute('title', label);
            if (el.classList.contains('sidebar-toggle-btn')) {
                el.setAttribute('aria-label', label);
                const icon = el.querySelector('i');
                if (icon) {
                    icon.classList.toggle('bi-chevron-double-left', !collapsed);
                    icon.classList.toggle('bi-chevron-double-right', collapsed);
                }
            }
        });

        // Saat rail mode, teks hilang — pasang tooltip dari judul menu.
        document.querySelectorAll('.sidebar-desktop .nav-link').forEach(function (link) {
            const titleEl = link.querySelector('.nav-title');
            if (!titleEl) return;
            if (collapsed) {
                if (!link.dataset.fullTitle) link.dataset.fullTitle = titleEl.textContent.trim();
                link.setAttribute('title', link.dataset.fullTitle);
            } else if (link.dataset.fullTitle) {
                link.removeAttribute('title');
            }
        });
    }

    function setCollapsed(collapsed, persist) {
        root.classList.toggle('sidebar-collapsed', collapsed);
        syncControls(collapsed);
        if (persist) {
            try { localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0'); } catch (e) {}
        }
    }

    // Sinkronkan ikon/aria dengan state yang sudah dipasang inline di <head>.
    syncControls(root.classList.contains('sidebar-collapsed'));

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.sidebar-desktop [data-sidebar-toggle]');
        if (!btn) return;
        e.preventDefault();
        setCollapsed(!root.classList.contains('sidebar-collapsed'), true);
    });

    // Ctrl/Cmd + B sebagai shortcut, sama seperti editor.
    // Jangan bajak saat fokus di field teks / editor (Ctrl+B = bold di sana).
    document.addEventListener('keydown', function (e) {
        if (!(e.ctrlKey || e.metaKey) || (e.key !== 'b' && e.key !== 'B')) return;
        const t = e.target;
        if (t && (t.isContentEditable ||
                  /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
        e.preventDefault();
        setCollapsed(!root.classList.contains('sidebar-collapsed'), true);
    });
})();

function showToast(msg, type) {
    const t = document.getElementById('appToast');
    const m = document.getElementById('toastMessage');
    if (!t || !m) return;
    t.className = 'toast align-items-center text-white border-0 shadow bg-' + (type || 'dark');
    m.innerHTML = '<i class="bi bi-' + (type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-triangle' : 'info-circle') + '"></i> ' + msg;
    const toast = bootstrap.Toast.getOrCreateInstance(t, { delay: 3000 });
    toast.show();
}

document.addEventListener('click', function(e) {
    const btn = e.target.closest('.quick-score-btn');
    if (!btn) return;
    const recordId = btn.dataset.recordId;
    const score = parseInt(btn.dataset.score, 10);
    const group = btn.closest('.quick-score-group');

    fetch('/ep/record/' + recordId + '/quick-score/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ score: score }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            group.querySelectorAll('.quick-score-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const badge = group.closest('td').querySelector('.score-badge');
            if (badge) {
                badge.className = 'score-badge score-' + score;
                const labels = { 10: '10 — Lengkap', 5: '5 — Sebagian', 0: '0 — Belum' };
                badge.textContent = labels[score] || score;
            }

            showToast('Skor diperbarui ke ' + score, 'success');
        } else {
            showToast('Gagal memperbarui skor: ' + (data.error || 'Error'), 'danger');
        }
    })
    .catch(err => {
        showToast('Koneksi gagal: ' + err.message, 'danger');
    });
});
