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

function showToast(msg, type) {
    const t = document.getElementById('appToast');
    const m = document.getElementById('toastMessage');
    if (!t || !m) return;
    const icon = type === 'success' ? 'check-circle'
        : type === 'danger' ? 'exclamation-triangle'
        : type === 'warning' ? 'exclamation-circle'
        : 'info-circle';
    m.replaceChildren();
    const i = document.createElement('i');
    i.className = 'bi bi-' + icon;
    i.setAttribute('aria-hidden', 'true');
    const span = document.createElement('span');
    span.textContent = msg;
    m.append(i, span);
    t.classList.toggle('toast-success', type === 'success');
    t.classList.toggle('toast-danger', type === 'danger');
    const toast = bootstrap.Toast.getOrCreateInstance(t, { delay: 3200 });
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
                const labels = { 10: '10 Lengkap', 5: '5 Sebagian', 0: '0 Belum' };
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
