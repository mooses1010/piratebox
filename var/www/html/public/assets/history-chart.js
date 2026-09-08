/*
 * PirateBox sensor-history chart renderer (2026-09-08).
 *
 * A small, dependency-free canvas line-chart drawer - NOT a vendored
 * third-party library. Chosen deliberately over adding a chart library
 * (even a small one) because the actual requirement here (a handful of
 * line series, honest gaps, a hover/tap tooltip, readable on mobile) is
 * well within what ~150 lines of plain canvas code can do cleanly,
 * matching this project's existing zero-new-dependency conventions
 * (hand-drawn OLED icons, no icon fonts, etc.) and its "no CDN, fully
 * offline" requirement without any vendoring/licensing overhead at all.
 *
 * GAPS ARE HONEST: a line segment is only drawn between two consecutive
 * points if the time between them is no more than GAP_FACTOR times the
 * larger of (a) the series' own median sample spacing or (b) a floor
 * (MIN_GAP_SECONDS) - so a real sensor outage reads as a visible break
 * in the line, never a misleading straight line across missing data.
 *
 * Reads its color palette from the page's own CSS custom properties
 * (--accent, --text-primary, --text-muted, --border-subtle) via
 * getComputedStyle, so a chart matches the current theme (including
 * the light/dark/emergency variants already defined in styles.css)
 * automatically, with zero color logic duplicated here.
 */
(function (global) {
    'use strict';

    var GAP_FACTOR = 2.5;
    var MIN_GAP_SECONDS = 60;
    var SERIES_COLORS = ['--accent', '--color-success', '--color-warning', '--color-danger', '--text-muted'];

    function cssVar(name, fallback) {
        var v = getComputedStyle(document.documentElement).getPropertyValue(name);
        return v && v.trim() ? v.trim() : fallback;
    }

    function medianGap(points) {
        if (points.length < 2) return MIN_GAP_SECONDS;
        var gaps = [];
        for (var i = 1; i < points.length; i++) gaps.push(points[i].t - points[i - 1].t);
        gaps.sort(function (a, b) { return a - b; });
        return Math.max(gaps[Math.floor(gaps.length / 2)], MIN_GAP_SECONDS);
    }

    /**
     * Renders one chart into `canvas` from `series` = [{label, points:
     * [{t, v}, ...]}], all sharing one time axis and one value axis.
     * `opts.unit` (string, e.g. "lux", "°C") is appended to the
     * hover tooltip only - never assumed to be the same scale as
     * another chart (see the page's own grouping: ambient light and
     * temperature are always separate charts for exactly this reason).
     */
    function render(canvas, series, opts) {
        opts = opts || {};
        var dpr = window.devicePixelRatio || 1;
        var cssWidth = canvas.clientWidth || canvas.parentElement.clientWidth || 300;
        var cssHeight = canvas.clientHeight || 180;
        canvas.width = cssWidth * dpr;
        canvas.height = cssHeight * dpr;
        var ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssWidth, cssHeight);

        var textColor = cssVar('--text-muted', '#888');
        var borderColor = cssVar('--border-subtle', '#444');
        var padding = { left: 42, right: 8, top: 10, bottom: 20 };
        var plotW = Math.max(1, cssWidth - padding.left - padding.right);
        var plotH = Math.max(1, cssHeight - padding.top - padding.bottom);

        var allPoints = [];
        series.forEach(function (s) { allPoints = allPoints.concat(s.points); });
        if (allPoints.length === 0) {
            ctx.fillStyle = textColor;
            ctx.font = '13px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No data for this range yet', cssWidth / 2, cssHeight / 2);
            canvas._pbHistory = null;
            return;
        }

        var minT = Math.min.apply(null, allPoints.map(function (p) { return p.t; }));
        var maxT = Math.max.apply(null, allPoints.map(function (p) { return p.t; }));
        var minV = Math.min.apply(null, allPoints.map(function (p) { return p.v; }));
        var maxV = Math.max.apply(null, allPoints.map(function (p) { return p.v; }));
        if (minV === maxV) { minV -= 1; maxV += 1; }  // flat data still gets a visible range
        var vPad = (maxV - minV) * 0.08;
        minV -= vPad; maxV += vPad;
        if (maxT === minT) maxT = minT + 1;

        function x(t) { return padding.left + ((t - minT) / (maxT - minT)) * plotW; }
        function y(v) { return padding.top + plotH - ((v - minV) / (maxV - minV)) * plotH; }

        // Y-axis gridlines/labels (3 lines: min, mid, max)
        ctx.strokeStyle = borderColor;
        ctx.fillStyle = textColor;
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        [minV + vPad, (minV + maxV) / 2, maxV - vPad].forEach(function (v) {
            var yy = y(v);
            ctx.globalAlpha = 0.4;
            ctx.beginPath();
            ctx.moveTo(padding.left, yy);
            ctx.lineTo(cssWidth - padding.right, yy);
            ctx.stroke();
            ctx.globalAlpha = 1;
            ctx.fillText(v.toFixed(v >= 100 ? 0 : 1), padding.left - 6, yy);
        });

        // X-axis labels (start/end of the visible range)
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        [minT, maxT].forEach(function (t, i) {
            ctx.textAlign = i === 0 ? 'left' : 'right';
            ctx.fillText(formatAxisTime(t), i === 0 ? padding.left : cssWidth - padding.right, cssHeight - padding.bottom + 4);
        });

        // One line per series, broken across gaps.
        series.forEach(function (s, idx) {
            if (s.points.length === 0) return;
            var color = cssVar(SERIES_COLORS[idx % SERIES_COLORS.length], '#8c8dff');
            var gapThreshold = medianGap(s.points) * GAP_FACTOR;
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.75;
            ctx.beginPath();
            var started = false;
            for (var i = 0; i < s.points.length; i++) {
                var p = s.points[i];
                var prev = s.points[i - 1];
                if (prev && p.t - prev.t > gapThreshold) started = false;
                if (!started) { ctx.moveTo(x(p.t), y(p.v)); started = true; } else { ctx.lineTo(x(p.t), y(p.v)); }
            }
            ctx.stroke();
        });

        canvas._pbHistory = { series: series, x: x, y: y, minT: minT, maxT: maxT, padding: padding, unit: opts.unit || '' };
        if (!canvas._pbHistoryBound) {
            canvas._pbHistoryBound = true;
            bindTooltip(canvas);
        }
    }

    function formatAxisTime(t) {
        var d = new Date(t * 1000);
        var now = new Date();
        var sameDay = d.toDateString() === now.toDateString();
        return sameDay
            ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    function bindTooltip(canvas) {
        var tip = document.createElement('div');
        tip.className = 'history-chart-tooltip';
        tip.hidden = true;
        canvas.parentElement.style.position = canvas.parentElement.style.position || 'relative';
        canvas.parentElement.appendChild(tip);

        function nearestPoint(clientX, clientY) {
            var state = canvas._pbHistory;
            if (!state) return null;
            var rect = canvas.getBoundingClientRect();
            var px = clientX - rect.left;
            var best = null, bestDist = Infinity;
            state.series.forEach(function (s) {
                s.points.forEach(function (p) {
                    var d = Math.abs(state.x(p.t) - px);
                    if (d < bestDist) { bestDist = d; best = { p: p, label: s.label }; }
                });
            });
            return bestDist < 30 ? best : null;
        }

        function showAt(clientX, clientY) {
            var hit = nearestPoint(clientX, clientY);
            if (!hit) { tip.hidden = true; return; }
            var state = canvas._pbHistory;
            var rect = canvas.getBoundingClientRect();
            var d = new Date(hit.p.t * 1000);
            tip.textContent = hit.label + ': ' + hit.p.v.toFixed(1) + state.unit + ' (' + d.toLocaleString() + ')';
            tip.hidden = false;
            tip.style.left = Math.min(clientX - rect.left + 8, rect.width - tip.offsetWidth - 4) + 'px';
            tip.style.top = '4px';
        }

        canvas.addEventListener('mousemove', function (e) { showAt(e.clientX, e.clientY); });
        canvas.addEventListener('mouseleave', function () { tip.hidden = true; });
        canvas.addEventListener('touchstart', function (e) {
            if (e.touches[0]) showAt(e.touches[0].clientX, e.touches[0].clientY);
        }, { passive: true });
    }

    global.PirateboxHistoryChart = { render: render };
})(window);
