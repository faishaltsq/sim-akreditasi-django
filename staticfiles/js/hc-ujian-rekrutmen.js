// Countdown and focus tracking for the CBT exam page.
//
// The timer only displays the remaining seconds the server already sent; it
// never extends the window. When it reaches zero the form is submitted so the
// paper is scored server-side rather than silently abandoned.
(function () {
    'use strict';

    var el = document.getElementById('ujian-sisa');
    var form = document.getElementById('form-ujian');
    if (!el || !form) return;

    var sisa = parseInt(el.getAttribute('data-batas'), 10);
    if (isNaN(sisa)) return;

    var timer = window.setInterval(function () {
        sisa -= 1;
        if (sisa <= 0) {
            window.clearInterval(timer);
            el.textContent = '0';
            // Auto-submit so the attempt is scored instead of left dangling.
            var hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'submit';
            hidden.value = '1';
            form.appendChild(hidden);
            form.submit();
            return;
        }
        el.textContent = String(sisa);
    }, 1000);

    // Anti-cheating: report leaving the exam page. Fire-and-forget; a failed
    // report must not interrupt the candidate.
    var focusUrl = form.getAttribute('data-fokus-url');
    document.addEventListener('visibilitychange', function () {
        if (document.hidden && focusUrl) {
            navigator.sendBeacon && navigator.sendBeacon(focusUrl);
        }
    });
})();
