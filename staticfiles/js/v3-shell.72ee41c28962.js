/* ==========================================================================
   ARIMA V3 — application shell behaviour
   Sidebar collapse (persisted), active-item visibility, collapsed tooltips.
   No framework, no dependencies beyond Bootstrap's own JS.
   ========================================================================== */
(function () {
    'use strict';

    var STORE_KEY = 'arima.v3.sidebar.collapsed';

    function isCollapsed() {
        try { return window.localStorage.getItem(STORE_KEY) === '1'; } catch (e) { return false; }
    }

    function store(value) {
        try { window.localStorage.setItem(STORE_KEY, value ? '1' : '0'); } catch (e) { /* private mode */ }
    }

    function applyState(collapsed) {
        var btn = document.getElementById('sidebarCollapseBtn');
        document.body.classList.toggle('sb-collapsed', collapsed);
        document.documentElement.classList.toggle('sb-collapsed', collapsed);
        if (!btn) return;
        btn.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
        btn.setAttribute('aria-label', collapsed ? 'Perluas menu navigasi' : 'Ciutkan menu navigasi');
        btn.setAttribute('data-tooltip', collapsed ? 'Perluas menu' : 'Ciutkan menu');
        var icon = btn.querySelector('i');
        if (icon) icon.className = collapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
    }

    /* When collapsed, the text labels are hidden — mirror them onto the link
       so the CSS bubble ([data-tooltip]) and the native tooltip both name the
       destination. */
    function syncTooltips(collapsed) {
        var links = document.querySelectorAll('.sidebar-desktop .nav-link');
        for (var i = 0; i < links.length; i++) {
            var link = links[i];
            if (collapsed) {
                if (!link.getAttribute('data-v3-label')) {
                    var title = link.querySelector('.nav-title');
                    if (title) link.setAttribute('data-v3-label', title.textContent.trim());
                }
                if (link.getAttribute('data-v3-label')) {
                    var label = link.getAttribute('data-v3-label');
                    link.setAttribute('title', label);
                    link.setAttribute('data-tooltip', label);
                }
            } else {
                link.removeAttribute('title');
                link.removeAttribute('data-tooltip');
            }
        }
    }

    function init() {
        var collapsed = isCollapsed();
        applyState(collapsed);
        syncTooltips(collapsed);

        var btn = document.getElementById('sidebarCollapseBtn');
        if (btn) {
            btn.addEventListener('click', function () {
                var next = !document.body.classList.contains('sb-collapsed');
                store(next);
                applyState(next);
                syncTooltips(next);
            });
        }

        /* Keep the active route visible without jumping the page. */
        var active = document.querySelector('.sidebar-desktop .nav-link.active');
        if (active && active.scrollIntoView) {
            try {
                active.scrollIntoView({ block: 'nearest' });
            } catch (e) { /* older engines: no action needed */ }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
