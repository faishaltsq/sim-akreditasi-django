/* ==========================================================================
   ARIMA V3 — application shell behaviour
   Expanded desktop navigation, active-item visibility and search shortcut.
   No framework, no dependencies beyond Bootstrap's own JS.
   ========================================================================== */
(function () {
    'use strict';

    function init() {
        document.body.classList.remove('sb-collapsed');
        document.documentElement.classList.remove('sb-collapsed');
        try { window.localStorage.removeItem('arima.v3.sidebar.collapsed'); } catch (e) { /* private mode */ }

        /* Keep the active route visible without jumping the page. */
        var active = document.querySelector('.sidebar-desktop .nav-link.active');
        if (active && active.scrollIntoView) {
            try {
                active.scrollIntoView({ block: 'nearest' });
            } catch (e) { /* older engines: no action needed */ }
        }

        /* "/" focuses the global search, the way a command palette would —
           never while the user is already typing somewhere else. */
        var search = document.getElementById('topbarSearch');
        if (search) {
            document.addEventListener('keydown', function (e) {
                if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
                var target = e.target;
                var typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
                if (typing) return;
                e.preventDefault();
                search.focus();
                search.select();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
