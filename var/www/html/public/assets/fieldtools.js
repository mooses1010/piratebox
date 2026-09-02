// Field Tools (Post-Stage-32) - client-side conversion/time logic.
//
// Mirrors includes/fieldtools_convert.php's formulas exactly (same
// constants, same units) so the two never quietly disagree - PHP is the
// tested, canonical copy (see tools/test_fieldtools.php); this file is
// the UI-layer duplicate for instant, no-page-reload feedback, since
// this project has no build step to generate one from the other. If you
// change a conversion factor here, change it there too, and vice versa.
//
// Zero external dependencies, zero network calls (no fetch anywhere in
// this file) - every conversion is plain local arithmetic. Runs entirely
// offline, same as the rest of this app.
//
// Only attaches to elements that actually exist on the current page, so
// this one file can be safely included on all three Field Tools pages
// without erroring on the ones that don't have a given tool.

(function () {
    'use strict';

    function on(id, evt, fn) {
        var el = document.getElementById(id);
        if (el) el.addEventListener(evt, fn);
        return el;
    }

    function num(id) {
        var el = document.getElementById(id);
        if (!el || el.value === '') return null;
        var v = parseFloat(el.value);
        return isNaN(v) ? null : v;
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function fmt(n, decimals) {
        if (decimals === undefined) decimals = 4;
        // Trim trailing zeros for a cleaner read-out, but never show
        // false precision beyond `decimals` places.
        return parseFloat(n.toFixed(decimals)).toString();
    }

    // --- Conversion tables (mirrors fieldtools_convert.php) ----------------

    var DISTANCE_TO_M = { mm: 0.001, cm: 0.01, m: 1.0, km: 1000.0, in: 0.0254, ft: 0.3048, yd: 0.9144, mi: 1609.344 };
    var MASS_TO_G = { g: 1.0, kg: 1000.0, oz: 28.349523125, lb: 453.59237 };
    var VOLUME_TO_ML = { ml: 1.0, l: 1000.0, us_floz: 29.5735295625, us_cup: 236.5882365, us_pint: 473.176473, us_qt: 946.352946, us_gal: 3785.411784 };
    var SPEED_TO_MS = { mph: 0.44704, kmh: 1000.0 / 3600.0, ms: 1.0 };
    var PRESSURE_TO_KPA = { psi: 6.894757293168, kpa: 1.0, bar: 100.0 };
    var STORAGE_TO_BYTES = { b: 1.0, kib: 1024.0, mib: Math.pow(1024, 2), gib: Math.pow(1024, 3), tib: Math.pow(1024, 4) };
    var DISTANCE_LABELS = { mm: 'mm', cm: 'cm', m: 'm', km: 'km', in: 'in', ft: 'ft', yd: 'yd', mi: 'mi' };
    var MASS_LABELS = { g: 'g', kg: 'kg', oz: 'oz', lb: 'lb' };
    var VOLUME_LABELS = { ml: 'mL', l: 'L', us_floz: 'US fl oz', us_cup: 'US cups', us_pint: 'US pints', us_qt: 'US quarts', us_gal: 'US gallons' };
    var SPEED_LABELS = { mph: 'mph', kmh: 'km/h', ms: 'm/s' };
    var PRESSURE_LABELS = { psi: 'PSI', kpa: 'kPa', bar: 'bar' };
    var STORAGE_LABELS = { b: 'bytes', kib: 'KiB', mib: 'MiB', gib: 'GiB', tib: 'TiB' };

    function convertTemperature(value, from) {
        var c = from === 'f' ? (value - 32) * 5 / 9 : value;
        var f = (c * 9 / 5) + 32;
        return { c: c, f: f };
    }

    function convertAllUnits(value, fromUnit, table) {
        var base = value * table[fromUnit];
        var out = {};
        for (var unit in table) {
            if (Object.prototype.hasOwnProperty.call(table, unit)) {
                out[unit] = base / table[unit];
            }
        }
        return out;
    }

    // --- Temperature ---------------------------------------------------------

    (function () {
        var valueEl = document.getElementById('ft-temp-value');
        var fromEl = document.getElementById('ft-temp-from');
        if (!valueEl || !fromEl) return;
        function update() {
            var v = num('ft-temp-value');
            if (v === null) { setText('ft-temp-result', 'Enter a value above.'); return; }
            var r = convertTemperature(v, fromEl.value);
            setText('ft-temp-result', fmt(r.c, 2) + ' °C = ' + fmt(r.f, 2) + ' °F');
        }
        valueEl.addEventListener('input', update);
        fromEl.addEventListener('change', update);
    })();

    // --- Generic multi-unit converters (distance/mass/volume/speed/pressure/storage) ---

    function wireMultiUnit(prefix, table, labels, defaultDecimals) {
        var valueEl = document.getElementById('ft-' + prefix + '-value');
        var fromEl = document.getElementById('ft-' + prefix + '-from');
        if (!valueEl || !fromEl) return;
        function update() {
            var v = num('ft-' + prefix + '-value');
            if (v === null) { setText('ft-' + prefix + '-result', 'Enter a value above.'); return; }
            var results = convertAllUnits(v, fromEl.value, table);
            var parts = [];
            for (var unit in table) {
                if (unit === fromEl.value) continue;
                if (Object.prototype.hasOwnProperty.call(table, unit)) {
                    parts.push(fmt(results[unit], defaultDecimals) + ' ' + labels[unit]);
                }
            }
            setText('ft-' + prefix + '-result', parts.join(' · '));
        }
        valueEl.addEventListener('input', update);
        fromEl.addEventListener('change', update);
    }

    wireMultiUnit('distance', DISTANCE_TO_M, DISTANCE_LABELS, 4);
    wireMultiUnit('mass', MASS_TO_G, MASS_LABELS, 4);
    wireMultiUnit('volume', VOLUME_TO_ML, VOLUME_LABELS, 4);
    wireMultiUnit('speed', SPEED_TO_MS, SPEED_LABELS, 3);
    wireMultiUnit('pressure', PRESSURE_TO_KPA, PRESSURE_LABELS, 3);
    wireMultiUnit('storage', STORAGE_TO_BYTES, STORAGE_LABELS, 3);

    // --- Percentage / ratio ----------------------------------------------------

    (function () {
        function updateOf() {
            var part = num('ft-pct-part');
            var whole = num('ft-pct-whole');
            if (part === null || whole === null) { setText('ft-pct-of-result', ''); return; }
            if (whole === 0) { setText('ft-pct-of-result', 'Undefined (dividing by zero).'); return; }
            setText('ft-pct-of-result', fmt(part, 6) + ' is ' + fmt((part / whole) * 100, 4) + '% of ' + fmt(whole, 6));
        }
        function updateChange() {
            var oldV = num('ft-pct-old');
            var newV = num('ft-pct-new');
            if (oldV === null || newV === null) { setText('ft-pct-change-result', ''); return; }
            if (oldV === 0) { setText('ft-pct-change-result', 'Undefined (starting value is zero).'); return; }
            var change = ((newV - oldV) / oldV) * 100;
            setText('ft-pct-change-result', (change >= 0 ? '+' : '') + fmt(change, 4) + '% change');
        }
        on('ft-pct-part', 'input', updateOf);
        on('ft-pct-whole', 'input', updateOf);
        on('ft-pct-old', 'input', updateChange);
        on('ft-pct-new', 'input', updateChange);
    })();

    // --- Electrical / battery ---------------------------------------------------

    (function () {
        function updateWatts() {
            var v = num('ft-elec-volts');
            var a = num('ft-elec-amps');
            if (v === null || a === null) { setText('ft-elec-watts-result', ''); return; }
            setText('ft-elec-watts-result', fmt(v, 4) + 'V × ' + fmt(a, 4) + 'A = ' + fmt(v * a, 4) + 'W');
        }
        function updateBattery() {
            var capacity = num('ft-batt-capacity');
            var load = num('ft-batt-load');
            var eff = num('ft-batt-efficiency');
            if (eff === null) eff = 0.8;
            if (capacity === null || load === null || load <= 0 || eff <= 0) {
                setText('ft-batt-result', 'Enter a capacity and a load above zero.');
                return;
            }
            var hours = (capacity * eff) / load;
            setText('ft-batt-result', 'Estimated runtime: ' + fmt(hours, 2) + ' hours (theoretical - see caveats above).');
        }
        on('ft-elec-volts', 'input', updateWatts);
        on('ft-elec-amps', 'input', updateWatts);
        on('ft-batt-capacity', 'input', updateBattery);
        on('ft-batt-load', 'input', updateBattery);
        on('ft-batt-efficiency', 'input', updateBattery);
    })();

    // --- Coordinates -------------------------------------------------------

    function ddToDms(dd, isLat) {
        var hemi = isLat ? (dd < 0 ? 'S' : 'N') : (dd < 0 ? 'W' : 'E');
        var abs = Math.abs(dd);
        var deg = Math.floor(abs);
        var minFloat = (abs - deg) * 60;
        var min = Math.floor(minFloat);
        var sec = (minFloat - min) * 60;
        if (Math.round(sec * 1e6) / 1e6 >= 60) { sec = 0; min++; }
        if (min >= 60) { min = 0; deg++; }
        return { deg: deg, min: min, sec: sec, hemi: hemi };
    }

    function dmsToDd(deg, min, sec, hemi) {
        hemi = (hemi || '').toUpperCase();
        if (['N', 'S', 'E', 'W'].indexOf(hemi) === -1) return null;
        if (min < 0 || min >= 60 || sec < 0 || sec >= 60 || deg < 0) return null;
        var dd = deg + (min / 60) + (sec / 3600);
        return (hemi === 'S' || hemi === 'W') ? -dd : dd;
    }

    (function () {
        var latEl = document.getElementById('ft-dd-lat');
        var lonEl = document.getElementById('ft-dd-lon');
        if (!latEl || !lonEl) return;
        function update() {
            var lat = num('ft-dd-lat');
            var lon = num('ft-dd-lon');
            if (lat === null || lon === null) { setText('ft-dd-result', 'Enter both values above.'); return; }
            if (lat < -90 || lat > 90) { setText('ft-dd-result', 'Latitude must be between -90 and 90.'); return; }
            if (lon < -180 || lon > 180) { setText('ft-dd-result', 'Longitude must be between -180 and 180.'); return; }
            var la = ddToDms(lat, true);
            var lo = ddToDms(lon, false);
            setText('ft-dd-result',
                la.deg + '°' + la.min + '′' + fmt(la.sec, 2) + '″ ' + la.hemi + ', ' +
                lo.deg + '°' + lo.min + '′' + fmt(lo.sec, 2) + '″ ' + lo.hemi);
        }
        latEl.addEventListener('input', update);
        lonEl.addEventListener('input', update);
    })();

    (function () {
        var ids = ['ft-dms-lat-deg', 'ft-dms-lat-min', 'ft-dms-lat-sec', 'ft-dms-lat-hemi', 'ft-dms-lon-deg', 'ft-dms-lon-min', 'ft-dms-lon-sec', 'ft-dms-lon-hemi'];
        var els = ids.map(function (id) { return document.getElementById(id); });
        if (els.indexOf(null) !== -1) return;
        function update() {
            var latDeg = num('ft-dms-lat-deg'), latMin = num('ft-dms-lat-min'), latSec = num('ft-dms-lat-sec');
            var lonDeg = num('ft-dms-lon-deg'), lonMin = num('ft-dms-lon-min'), lonSec = num('ft-dms-lon-sec');
            if (latDeg === null || latMin === null || latSec === null || lonDeg === null || lonMin === null || lonSec === null) {
                setText('ft-dms-result', 'Enter both latitude and longitude above.');
                return;
            }
            var lat = dmsToDd(latDeg, latMin, latSec, document.getElementById('ft-dms-lat-hemi').value);
            var lon = dmsToDd(lonDeg, lonMin, lonSec, document.getElementById('ft-dms-lon-hemi').value);
            if (lat === null || lon === null) { setText('ft-dms-result', 'Check minutes/seconds are 0-59.'); return; }
            setText('ft-dms-result', fmt(lat, 6) + ', ' + fmt(lon, 6));
        }
        els.forEach(function (el) { el.addEventListener('input', update); el.addEventListener('change', update); });
    })();

    // --- Time & date (public/utility/fieldtools/time/) -----------------------

    var WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

    function dayOfYearUTC(y, m, d) {
        var start = Date.UTC(y, 0, 1);
        var target = Date.UTC(y, m - 1, d);
        return Math.round((target - start) / 86400000) + 1;
    }

    function isLeapYear(y) {
        return (y % 4 === 0 && y % 100 !== 0) || (y % 400 === 0);
    }

    // Live-ticking "right now" display: seeded from the server-rendered
    // snapshot's Unix epoch, advanced by this browser's own 1-second timer -
    // deliberately never reads this device's own Date/clock as the source
    // of truth, only as a tick generator, so a wrong visitor-device clock
    // can't make the displayed PirateBox time silently wrong. See
    // includes/fieldtools_time.php for why this distinction matters here.
    (function () {
        var grid = document.getElementById('ft-now-grid');
        if (!grid) return;
        var baseUnix = parseInt(grid.getAttribute('data-base-unix'), 10);
        if (isNaN(baseUnix)) return;
        var ticks = 0;

        function pad(n) { return n < 10 ? '0' + n : '' + n; }

        function render() {
            var t = baseUnix + ticks;
            var d = new Date(t * 1000);
            // Local fields (browser's own timezone - matches what the
            // server rendered, since both mean "this device's configured
            // local time" as long as browser and Pi agree on offset,
            // which is expected on a directly-connected client).
            var h24 = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
            var h12hour = d.getHours() % 12; if (h12hour === 0) h12hour = 12;
            var ampm = d.getHours() < 12 ? 'AM' : 'PM';
            var h12 = h12hour + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) + ' ' + ampm;

            var utcH = pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds());

            setText('ft-local24', d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + h24);
            setText('ft-local12', d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + h12);
            setText('ft-utc', d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()) + ' ' + utcH + ' UTC');
            setText('ft-unix', String(t));
            setText('ft-weekday', WEEKDAYS[d.getDay()]);
        }

        render();
        setInterval(function () { ticks++; render(); }, 1000);
    })();

    // Elapsed-time / duration calculator
    (function () {
        var startEl = document.getElementById('ft-elapsed-start');
        var endEl = document.getElementById('ft-elapsed-end');
        if (!startEl || !endEl) return;
        function update() {
            if (!startEl.value || !endEl.value) { setText('ft-elapsed-result', 'Enter both a start and end time.'); return; }
            var start = new Date(startEl.value);
            var end = new Date(endEl.value);
            if (isNaN(start.getTime()) || isNaN(end.getTime())) { setText('ft-elapsed-result', 'Check both dates are valid.'); return; }
            var diffMs = end.getTime() - start.getTime();
            var direction = diffMs > 0 ? 'after start' : (diffMs < 0 ? 'before start' : '');
            var absSec = Math.round(Math.abs(diffMs) / 1000);
            var days = Math.floor(absSec / 86400);
            var hours = Math.floor((absSec % 86400) / 3600);
            var mins = Math.floor((absSec % 3600) / 60);
            var secs = absSec % 60;
            var parts = [];
            if (days > 0) parts.push(days + 'd');
            if (days > 0 || hours > 0) parts.push(hours + 'h');
            parts.push(mins + 'm');
            parts.push(secs + 's');
            setText('ft-elapsed-result', parts.join(' ') + (direction ? ' (end is ' + direction + ')' : ' (same instant)'));
        }
        startEl.addEventListener('input', update);
        endEl.addEventListener('input', update);
    })();

    // Unix timestamp converter (both directions)
    (function () {
        var tsEl = document.getElementById('ft-unix-input');
        var dtEl = document.getElementById('ft-unix-datetime');
        if (tsEl) {
            tsEl.addEventListener('input', function () {
                var v = num('ft-unix-input');
                if (v === null) { setText('ft-unix-result', 'Enter a timestamp above.'); return; }
                var d = new Date(v * 1000);
                if (isNaN(d.getTime())) { setText('ft-unix-result', 'Out of range.'); return; }
                setText('ft-unix-result', 'Local: ' + d.toString().replace(/ \(.*\)$/, '') + '  ·  UTC: ' + d.toISOString());
            });
        }
        if (dtEl) {
            dtEl.addEventListener('input', function () {
                if (!dtEl.value) { setText('ft-unix-datetime-result', ''); return; }
                var d = new Date(dtEl.value);
                if (isNaN(d.getTime())) { setText('ft-unix-datetime-result', 'Check the date is valid.'); return; }
                setText('ft-unix-datetime-result', 'Unix timestamp: ' + Math.round(d.getTime() / 1000) + ' (interpreted in this device’s local time zone)');
            });
        }
    })();

    // Date lookup - weekday & day of year (pure calendar math, UTC-anchored
    // internally so it never depends on this browser's own timezone)
    (function () {
        var el = document.getElementById('ft-dateinfo-input');
        if (!el) return;
        el.addEventListener('input', function () {
            if (!el.value) { setText('ft-dateinfo-result', 'Pick a date above.'); return; }
            var parts = el.value.split('-');
            var y = parseInt(parts[0], 10), m = parseInt(parts[1], 10), d = parseInt(parts[2], 10);
            var weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
            var doy = dayOfYearUTC(y, m, d);
            var totalDays = isLeapYear(y) ? 366 : 365;
            setText('ft-dateinfo-result', weekday + ' · day ' + doy + ' of ' + totalDays + ' in ' + y);
        });
    })();

    // 12-hour <-> 24-hour
    (function () {
        var el = document.getElementById('ft-time-input');
        if (!el) return;
        el.addEventListener('input', function () {
            if (!el.value) { setText('ft-time-result', 'Enter a time above.'); return; }
            var parts = el.value.split(':');
            var h = parseInt(parts[0], 10), m = parts[1];
            var h12 = h % 12; if (h12 === 0) h12 = 12;
            var ampm = h < 12 ? 'AM' : 'PM';
            setText('ft-time-result', '24-hour: ' + el.value + '  ·  12-hour: ' + h12 + ':' + m + ' ' + ampm);
        });
    })();
})();
