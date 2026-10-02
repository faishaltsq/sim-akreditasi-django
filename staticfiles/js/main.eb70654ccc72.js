function getCookie(name) {
    let c = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return c ? c.pop() : '';
}

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
