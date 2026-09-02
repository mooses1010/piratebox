<?php
declare(strict_types=1);
session_start();

// IPv4 Subnet Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to Computing &
// Networking Reference's CIDR/subnet-mask reference and private-IP-
// ranges entries - this is the calculator, that page is the
// explanation.
//
// Core calculation works via a plain POST + server-render round trip
// with NO JavaScript required (includes/subnet_calc.php does the real
// work, tested directly by tools/test_fieldtools.php). JavaScript,
// where available, enhances the same page for instant results as you
// type - mirroring the same bitwise arithmetic in JS, the same
// accepted duplication pattern public/assets/fieldtools.js already
// uses for simple formulas (a lookup table, like Morse's, gets the
// JSON-embedding treatment instead; arithmetic this simple doesn't
// need it).
//
// Nothing entered here is logged, stored in $_SESSION, or written to
// any PirateBox data file.

require_once __DIR__ . '/../../../../includes/subnet_calc.php';

$ipInput = trim((string) ($_POST['ip'] ?? ''));
$prefixInput = trim((string) ($_POST['prefix'] ?? ''));

// Convenience: accept combined "192.168.1.10/24" typed into the IP
// field alone, in addition to the two separate fields.
if ($prefixInput === '' && str_contains($ipInput, '/')) {
    [$ipInput, $prefixInput] = array_map('trim', explode('/', $ipInput, 2));
}

$result = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $ipInput !== '' && $prefixInput !== '') {
    $result = piratebox_subnet_info($ipInput, $prefixInput);
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Subnet Calculator</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>IPv4 Subnet Calculator</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Enter an IPv4 address and either a prefix length (e.g. <code>24</code>) or a dotted subnet mask (e.g. <code>255.255.255.0</code>) to get the network/broadcast address, usable host range, and host count. For what these terms mean, see <a href="/utility/computing/#cidr-subnet-mask-reference">Computing: CIDR Prefix &harr; Subnet Mask Reference</a>.</p>

        <form method="post" action="" id="subnet-form">
            <div class="fieldtools-tool" id="ft-subnet-tool">
                <div class="fieldtools-row">
                    <label for="subnet-ip">IP address</label>
                    <input type="text" id="subnet-ip" name="ip" placeholder="192.168.1.10" value="<?= htmlspecialchars($ipInput) ?>" inputmode="decimal">
                </div>
                <div class="fieldtools-row">
                    <label for="subnet-prefix">Prefix length or subnet mask</label>
                    <input type="text" id="subnet-prefix" name="prefix" placeholder="24 or 255.255.255.0" value="<?= htmlspecialchars($prefixInput) ?>">
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Calculate</button>
                </div>

                <?php if ($result !== null && isset($result['error'])): ?>
                    <p class="fieldtools-result help-note" id="subnet-error"><?= htmlspecialchars($result['error']) ?></p>
                <?php elseif ($result !== null): ?>
                    <div class="table-wrapper" id="subnet-result">
                        <table>
                            <tbody>
                                <tr><td>Network address</td><td><?= htmlspecialchars($result['network']) ?></td></tr>
                                <tr><td>Broadcast address</td><td><?= $result['broadcast'] !== null ? htmlspecialchars($result['broadcast']) : '<span class="muted">none (see note below)</span>' ?></td></tr>
                                <tr><td>Subnet mask</td><td><?= htmlspecialchars($result['netmask']) ?> <span class="muted">(/<?= (int) $result['prefix'] ?>)</span></td></tr>
                                <tr><td>Wildcard mask</td><td><?= htmlspecialchars($result['wildcard']) ?></td></tr>
                                <tr><td>Usable host range</td><td><?= htmlspecialchars($result['first_host']) ?> &ndash; <?= htmlspecialchars($result['last_host']) ?></td></tr>
                                <tr><td>Usable hosts</td><td><?= htmlspecialchars((string) $result['usable_hosts']) ?></td></tr>
                                <tr><td>Total addresses</td><td><?= htmlspecialchars((string) $result['total_addresses']) ?></td></tr>
                            </tbody>
                        </table>
                    </div>
                <?php else: ?>
                    <p class="fieldtools-result" id="ft-subnet-placeholder">Enter an IP address and prefix/mask above, then Calculate.</p>
                <?php endif; ?>
            </div>
        </form>

        <noscript>
            <p class="help-note">JavaScript is off - calculation still works: enter the fields above and press Calculate.</p>
        </noscript>

        <p class="muted">Unfamiliar term (CIDR, subnet, netmask)? See the <a href="/utility/glossary/">Glossary</a>.</p>
    </div>

    <script>
        // Enhancement only - the form above already works with JS off via
        // the server round trip. Mirrors includes/subnet_calc.php's exact
        // bitwise arithmetic for instant feedback (32-bit values are well
        // within JS's safe integer range, no precision concerns).
        (function () {
            function parseIPv4(ip) {
                var m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(ip.trim());
                if (!m) return null;
                var value = 0;
                for (var i = 1; i <= 4; i++) {
                    var raw = m[i];
                    if (raw.length > 1 && raw[0] === '0') return null;
                    var octet = parseInt(raw, 10);
                    if (octet > 255) return null;
                    value = (value * 256) + octet;
                }
                return value >>> 0;
            }
            function ipToString(addr) {
                addr = addr >>> 0;
                return [(addr >>> 24) & 255, (addr >>> 16) & 255, (addr >>> 8) & 255, addr & 255].join('.');
            }
            function parsePrefixOrMask(input) {
                input = input.trim();
                if (/^\d{1,2}$/.test(input)) {
                    var p = parseInt(input, 10);
                    return (p >= 0 && p <= 32) ? p : null;
                }
                var mask = parseIPv4(input);
                if (mask === null) return null;
                for (var prefix = 0; prefix <= 32; prefix++) {
                    var expected = prefix === 0 ? 0 : ((0xFFFFFFFF << (32 - prefix)) >>> 0);
                    if (expected === mask) return prefix;
                }
                return null;
            }
            function subnetInfo(ipInput, prefixInput) {
                var ip = parseIPv4(ipInput);
                if (ip === null) return { error: '"' + ipInput + '" isn\'t a valid IPv4 address - expected 4 numbers 0-255 separated by dots, e.g. 192.168.1.10.' };
                var prefix = parsePrefixOrMask(prefixInput);
                if (prefix === null) return { error: '"' + prefixInput + '" isn\'t a valid prefix length (0-32) or a valid contiguous subnet mask (e.g. 255.255.255.0).' };
                var mask = prefix === 0 ? 0 : ((0xFFFFFFFF << (32 - prefix)) >>> 0);
                var wildcard = (~mask) >>> 0;
                var network = (ip & mask) >>> 0;
                var broadcast = (network | wildcard) >>> 0;
                var total = Math.pow(2, 32 - prefix);
                if (prefix === 32) {
                    return { network: ipToString(network), broadcast: null, netmask: ipToString(mask), wildcard: ipToString(wildcard), prefix: 32, first_host: ipToString(network), last_host: ipToString(network), usable_hosts: '1 (a /32 identifies a single host, not a range)', total_addresses: '1' };
                }
                if (prefix === 31) {
                    return { network: ipToString(network), broadcast: null, netmask: ipToString(mask), wildcard: ipToString(wildcard), prefix: 31, first_host: ipToString(network), last_host: ipToString(broadcast), usable_hosts: '2 (RFC 3021 point-to-point link - both addresses usable, no network/broadcast address)', total_addresses: '2' };
                }
                return {
                    network: ipToString(network), broadcast: ipToString(broadcast),
                    netmask: ipToString(mask), wildcard: ipToString(wildcard), prefix: prefix,
                    first_host: ipToString(network + 1), last_host: ipToString(broadcast - 1),
                    usable_hosts: (total - 2).toLocaleString(), total_addresses: total.toLocaleString()
                };
            }

            var ipField = document.getElementById('subnet-ip');
            var prefixField = document.getElementById('subnet-prefix');
            var form = document.getElementById('subnet-form');
            if (!ipField || !prefixField || !form) return;
            var toolDiv = form.querySelector('.fieldtools-tool');
            var liveResult = null;

            function esc(s) {
                var d = document.createElement('div');
                d.textContent = s;
                return d.innerHTML;
            }

            function render() {
                if (ipField.value.trim() === '' || prefixField.value.trim() === '') return;
                var r = subnetInfo(ipField.value, prefixField.value);
                if (!liveResult) {
                    liveResult = document.createElement('div');
                    liveResult.id = 'subnet-result-live';
                    toolDiv.appendChild(liveResult);
                    ['subnet-error', 'subnet-result', 'ft-subnet-placeholder'].forEach(function (id) {
                        var el = document.getElementById(id);
                        if (el) el.hidden = true;
                    });
                }
                if (r.error) {
                    liveResult.innerHTML = '<p class="fieldtools-result help-note">' + esc(r.error) + '</p>';
                    return;
                }
                liveResult.innerHTML =
                    '<div class="table-wrapper"><table><tbody>' +
                    '<tr><td>Network address</td><td>' + esc(r.network) + '</td></tr>' +
                    '<tr><td>Broadcast address</td><td>' + (r.broadcast !== null ? esc(r.broadcast) : '<span class="muted">none (see note below)</span>') + '</td></tr>' +
                    '<tr><td>Subnet mask</td><td>' + esc(r.netmask) + ' <span class="muted">(/' + r.prefix + ')</span></td></tr>' +
                    '<tr><td>Wildcard mask</td><td>' + esc(r.wildcard) + '</td></tr>' +
                    '<tr><td>Usable host range</td><td>' + esc(r.first_host) + ' &ndash; ' + esc(r.last_host) + '</td></tr>' +
                    '<tr><td>Usable hosts</td><td>' + esc(String(r.usable_hosts)) + '</td></tr>' +
                    '<tr><td>Total addresses</td><td>' + esc(String(r.total_addresses)) + '</td></tr>' +
                    '</tbody></table></div>';
            }

            ipField.addEventListener('input', render);
            prefixField.addEventListener('input', render);
            render();
        })();
    </script>

    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
