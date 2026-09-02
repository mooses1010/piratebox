<?php

declare(strict_types=1);

// IPv4 Subnet Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to Computing &
// Networking Reference's CIDR/subnet-mask table and private-IP-ranges
// entries - this is the calculator, that page is the explanation,
// same division of labor as every other reference/tool pair in this
// project (Maps/Coordinates, Radio/Morse).
//
// Pure, deterministic, dependency-free - same discipline as
// includes/fieldtools_convert.php and includes/morse.php. Assumes a
// 64-bit PHP int (true on this project's actual target - Raspberry Pi
// OS Bookworm on Pi 3/4/5 defaults to 64-bit) so a full unsigned 32-bit
// address fits safely in a native int without float-overflow risk;
// explicitly detected and refused otherwise rather than silently
// producing wrong arithmetic on a hypothetical 32-bit PHP build.

if (!function_exists('piratebox_parse_ipv4')) {
    /** Strict dotted-quad parse (4 octets, each 0-255, no other format accepted). Returns null, never guesses, on anything else. */
    function piratebox_parse_ipv4(string $ip): ?int
    {
        $ip = trim($ip);
        if (!preg_match('/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/', $ip, $m)) return null;
        $value = 0;
        for ($i = 1; $i <= 4; $i++) {
            $raw = $m[$i];
            // Reject leading-zero octets (e.g. "192.168.01.1") as
            // ambiguous rather than silently accepting them - some
            // older tools treat a leading zero as octal.
            if (strlen($raw) > 1 && $raw[0] === '0') return null;
            $octet = (int) $raw;
            if ($octet > 255) return null;
            $value = ($value << 8) | $octet;
        }
        return $value;
    }
}

if (!function_exists('piratebox_ipv4_to_string')) {
    function piratebox_ipv4_to_string(int $addr): string
    {
        $addr &= 0xFFFFFFFF;
        return implode('.', [
            ($addr >> 24) & 0xFF,
            ($addr >> 16) & 0xFF,
            ($addr >> 8) & 0xFF,
            $addr & 0xFF,
        ]);
    }
}

if (!function_exists('piratebox_parse_prefix_or_mask')) {
    /**
     * Accepts either a bare prefix length ("24") or a dotted subnet
     * mask ("255.255.255.0"). Returns the prefix length (0-32) on
     * success, or null if the input is out of range or - for a dotted
     * mask - not a valid contiguous mask (e.g. "255.0.255.0" is
     * rejected, not silently reinterpreted).
     */
    function piratebox_parse_prefix_or_mask(string $input): ?int
    {
        $input = trim($input);
        if (preg_match('/^\d{1,2}$/', $input)) {
            $prefix = (int) $input;
            return ($prefix >= 0 && $prefix <= 32) ? $prefix : null;
        }
        $mask = piratebox_parse_ipv4($input);
        if ($mask === null) return null;
        for ($prefix = 0; $prefix <= 32; $prefix++) {
            $expected = $prefix === 0 ? 0 : ((0xFFFFFFFF << (32 - $prefix)) & 0xFFFFFFFF);
            if ($expected === $mask) return $prefix;
        }
        return null; // valid IPv4 syntax, but not a contiguous mask
    }
}

if (!function_exists('piratebox_subnet_info')) {
    /**
     * @return array{error: string}|array{
     *   ip: string, prefix: int, netmask: string, wildcard: string,
     *   network: string, broadcast: ?string, first_host: string,
     *   last_host: string, usable_hosts: string, total_addresses: string
     * }
     */
    function piratebox_subnet_info(string $ipInput, string $prefixOrMaskInput): array
    {
        if (PHP_INT_SIZE < 8) {
            return ['error' => 'This calculator needs a 64-bit PHP build to compute IPv4 arithmetic safely - not available on this system.'];
        }
        $ip = piratebox_parse_ipv4($ipInput);
        if ($ip === null) {
            return ['error' => "\"$ipInput\" isn't a valid IPv4 address - expected 4 numbers 0-255 separated by dots, e.g. 192.168.1.10."];
        }
        $prefix = piratebox_parse_prefix_or_mask($prefixOrMaskInput);
        if ($prefix === null) {
            return ['error' => "\"$prefixOrMaskInput\" isn't a valid prefix length (0-32) or a valid contiguous subnet mask (e.g. 255.255.255.0)."];
        }

        $mask = $prefix === 0 ? 0 : ((0xFFFFFFFF << (32 - $prefix)) & 0xFFFFFFFF);
        $wildcard = (~$mask) & 0xFFFFFFFF;
        $network = $ip & $mask;
        $broadcast = $network | $wildcard;
        $totalAddresses = 2 ** (32 - $prefix);

        // /31 (RFC 3021, point-to-point) and /32 (single host) have no
        // separate network/broadcast address in the usual sense - stated
        // explicitly rather than printing a misleading 0-usable-hosts
        // answer for what are actually valid, common configurations.
        if ($prefix === 32) {
            return [
                'ip' => piratebox_ipv4_to_string($ip), 'prefix' => 32,
                'netmask' => piratebox_ipv4_to_string($mask), 'wildcard' => piratebox_ipv4_to_string($wildcard),
                'network' => piratebox_ipv4_to_string($network), 'broadcast' => null,
                'first_host' => piratebox_ipv4_to_string($network), 'last_host' => piratebox_ipv4_to_string($network),
                'usable_hosts' => '1 (a /32 identifies a single host, not a range)',
                'total_addresses' => '1',
            ];
        }
        if ($prefix === 31) {
            return [
                'ip' => piratebox_ipv4_to_string($ip), 'prefix' => 31,
                'netmask' => piratebox_ipv4_to_string($mask), 'wildcard' => piratebox_ipv4_to_string($wildcard),
                'network' => piratebox_ipv4_to_string($network), 'broadcast' => null,
                'first_host' => piratebox_ipv4_to_string($network), 'last_host' => piratebox_ipv4_to_string($broadcast),
                'usable_hosts' => '2 (RFC 3021 point-to-point link - both addresses usable, no network/broadcast address)',
                'total_addresses' => '2',
            ];
        }

        return [
            'ip' => piratebox_ipv4_to_string($ip),
            'prefix' => $prefix,
            'netmask' => piratebox_ipv4_to_string($mask),
            'wildcard' => piratebox_ipv4_to_string($wildcard),
            'network' => piratebox_ipv4_to_string($network),
            'broadcast' => piratebox_ipv4_to_string($broadcast),
            'first_host' => piratebox_ipv4_to_string($network + 1),
            'last_host' => piratebox_ipv4_to_string($broadcast - 1),
            'usable_hosts' => number_format($totalAddresses - 2),
            'total_addresses' => number_format($totalAddresses),
        ];
    }
}
