<?php

declare(strict_types=1);

// Ohm's Law / Power Solver (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to Field Tools
// Units' existing "Ohm's Law & power relationships" reference table -
// this is the calculator, that table is the at-a-glance reference.
//
// Pure, deterministic, dependency-free. Deliberately scoped to DC
// resistive-circuit arithmetic only (V = IR, P = VI, and their
// algebraic combinations) - not live-mains procedure, not AC
// impedance/reactance, no safety-critical guidance beyond what the
// existing Electrical Quick Reference help-note already states.

if (!function_exists('piratebox_ohms_law_solve')) {
    /**
     * Give exactly two of $v, $i, $r, $p (as numeric strings; leave the
     * other two as null or ''), get all four back.
     *
     * @return array{error: string}|array{voltage: float, current: float, resistance: float, power: float}
     */
    function piratebox_ohms_law_solve(?string $v, ?string $i, ?string $r, ?string $p): array
    {
        $fields = ['voltage' => $v, 'current' => $i, 'resistance' => $r, 'power' => $p];
        $known = [];
        foreach ($fields as $name => $raw) {
            $raw = trim((string) $raw);
            if ($raw === '') continue;
            if (!is_numeric($raw)) {
                return ['error' => "\"$raw\" for $name isn't a valid number."];
            }
            $known[$name] = (float) $raw;
        }

        if (count($known) !== 2) {
            return ['error' => 'Enter exactly two values (voltage, current, resistance, or power) and leave the other two blank.'];
        }
        foreach (['resistance', 'power'] as $mustBeNonNegative) {
            if (isset($known[$mustBeNonNegative]) && $known[$mustBeNonNegative] < 0) {
                return ['error' => ucfirst($mustBeNonNegative) . " can't be negative in this model."];
            }
        }

        $keys = array_keys($known);
        sort($keys);
        $pair = implode('+', $keys);

        switch ($pair) {
            case 'current+voltage':
                $v = $known['voltage']; $i = $known['current'];
                if ($i === 0.0) return ['error' => 'Current of 0 A with a nonzero voltage implies infinite resistance (an open circuit) - resistance and power cannot be computed from these two alone.'];
                $r = $v / $i; $p = $v * $i;
                break;
            case 'resistance+voltage':
                $v = $known['voltage']; $r = $known['resistance'];
                if ($r === 0.0) return ['error' => 'Resistance of 0 Ω with a nonzero voltage implies infinite current (a short circuit) - current and power cannot be computed from these two alone.'];
                $i = $v / $r; $p = ($v * $v) / $r;
                break;
            case 'power+voltage':
                $v = $known['voltage']; $p = $known['power'];
                if ($v === 0.0) return ['error' => 'Voltage of 0 V with nonzero power is not physically possible in this model - current and resistance cannot be computed from these two alone.'];
                $i = $p / $v; $r = ($v * $v) / $p;
                break;
            case 'current+resistance':
                $i = $known['current']; $r = $known['resistance'];
                $v = $i * $r; $p = ($i * $i) * $r;
                break;
            case 'current+power':
                $i = $known['current']; $p = $known['power'];
                if ($i === 0.0) return ['error' => 'Current of 0 A with nonzero power is not physically possible in this model - voltage and resistance cannot be computed from these two alone.'];
                $v = $p / $i; $r = $p / ($i * $i);
                break;
            case 'power+resistance':
                $r = $known['resistance']; $p = $known['power'];
                if ($r === 0.0 && $p !== 0.0) return ['error' => 'Resistance of 0 Ω with nonzero power is not physically possible in this model.'];
                $v = $r === 0.0 ? 0.0 : sqrt($p * $r);
                $i = $r === 0.0 ? 0.0 : sqrt($p / $r);
                break;
            default:
                return ['error' => 'Unexpected combination of values.'];
        }

        return ['voltage' => $v, 'current' => $i, 'resistance' => $r, 'power' => $p];
    }
}
