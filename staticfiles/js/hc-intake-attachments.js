// Accessible drag-and-drop enhancement for the step-5 intake file inputs.
// The native <input type="file"> stays the authoritative control: this script
// only prevents the browser from navigating to a dropped file and mirrors the
// chosen filename into an aria-live region.
(function () {
    'use strict';

    var zones = document.querySelectorAll('[data-hc-drop-zone]');
    if (!zones.length) return;

    function announce(zone, file) {
        var target = zone.querySelector('[data-hc-drop-name]');
        if (target) {
            target.textContent = file ? file.name : '';
        }
    }

    zones.forEach(function (zone) {
        var input = zone.querySelector('input[type="file"]');
        if (!input) return;

        ['dragenter', 'dragover'].forEach(function (name) {
            zone.addEventListener(name, function (event) {
                event.preventDefault();
                event.stopPropagation();
                zone.classList.add('border-primary');
            });
        });

        ['dragleave', 'dragend'].forEach(function (name) {
            zone.addEventListener(name, function (event) {
                event.preventDefault();
                event.stopPropagation();
                zone.classList.remove('border-primary');
            });
        });

        zone.addEventListener('drop', function (event) {
            event.preventDefault();
            event.stopPropagation();
            zone.classList.remove('border-primary');

            var files = event.dataTransfer && event.dataTransfer.files;
            if (!files || files.length !== 1) {
                announce(zone, null);
                return;
            }
            // Assigning a FileList is not permitted; DataTransfer is the only
            // portable way to put a dropped file on a native input.
            var carrier = new DataTransfer();
            carrier.items.add(files[0]);
            input.files = carrier.files;
            announce(zone, files[0]);
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });

        input.addEventListener('change', function () {
            announce(zone, input.files && input.files[0]);
        });
    });
})();
