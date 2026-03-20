# Pitch Curve — Designer Notes

## What the pitch_curve value means

Each stem's `pitch_curve` is a time-series of values in `[0.0, 1.0]` where:

- `0.0` = unvoiced / unpitched (silence, noise, drum hit)
- `> 0.0` = pitched content, normalised against C7 (~2093 Hz)

## Per-stem ranges from real data

The normalisation is global (against C7), so each stem naturally occupies
a different slice of the `[0, 1]` range. When mapping pitch to a visual
parameter, remap against the stem's actual range — not the full `[0, 1]`.

| Stem   | Typical voiced % | Typical range | Notes |
|--------|-----------------|---------------|-------|
| vocals | 85–99%  | 0.010–0.930 | Wide range — rap to soprano. Map full range for color/flutter. |
| bass   | 46–96%  | 0.010–0.070 | Narrow low range. Remap 0–0.07 → 0–1 for visual use. |
| piano  | varies  | 0.010–0.800 | Depends heavily on register of material. |
| guitar | varies  | 0.010–0.600 | Similar to piano. |
| other  | varies  | 0.010–0.500 | Catch-all stem — treat as melodic. |
| drums  | 0%      | always 0    | Intentionally zero — use onset/energy instead. |

## Recommended remapping pattern (JavaScript)

```javascript
// Instead of using raw pitch value:
//   butterfly_hue = pitch_curve * 360  // wrong — bass never reaches high hues

// Remap to stem's actual range first:
function remapPitch(value, stemMin = 0.01, stemMax = 0.25) {
  if (value === 0) return 0;  // unvoiced
  return (value - stemMin) / (stemMax - stemMin);
}

// Vocals — full range
const vocalHue = remapPitch(frame.pitch_curve, 0.01, 0.93) * 360;

// Bass — narrow low range
const bassGravity = remapPitch(frame.pitch_curve, 0.01, 0.07);
```

## Which stems to use pitch for

| Stem   | Suggested visual use |
|--------|---------------------|
| vocals | Color shift, iridescence, flutter frequency |
| bass   | Gravity weight, slow oscillation frequency |
| piano  | Petal position, bloom radius |
| guitar | Branch angle, leaf flutter |
| drums  | Don't use pitch — use `onset` and `energy` instead |

## Voiced vs unvoiced detection

`pitch_curve === 0` means unvoiced. Use this to trigger state changes:

```javascript
const isVoiced = frame.pitch_curve > 0;
// e.g. butterfly wings spread when vocals are voiced
// wings fold when unvoiced
```
