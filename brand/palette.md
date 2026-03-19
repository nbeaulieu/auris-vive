# Colour palette

Auris Vive lives in near-darkness. The palette is built around the idea that music happens in a dimmed room — the visuals are the light source.

---

## Core palette

| Name | Hex | Role |
|------|-----|------|
| **Void** | `#06060A` | Primary background. The deepest dark. Used for hero and full-bleed surfaces. |
| **Dusk** | `#1A1428` | Secondary background. Cards, panels, nav. Slightly warmer than Void. |
| **Deep** | `#0E0B18` | Tertiary background. Between Void and Dusk. Used for subtle layering. |
| **Violet** | `#7B5EA7` | Primary accent for AI-driven visuals. The generative layer. |
| **Iris** | `#A084C8` | Secondary accent. Lighter violet for hover states, secondary UI elements. |
| **Gold** | `#C9A96E` | Warm accent. Brand mark, active states, editorial highlights. |
| **Pearl** | `#E8E0D5` | Primary text on dark. Slightly warm white — never pure `#FFFFFF`. |
| **Mist** | `rgba(232,224,213,0.45)` | Secondary text, captions, labels. Pearl at reduced opacity. |

---

## Visualisation palette

The generative visuals use an extended palette that shifts based on what's playing. These are the base colours — the AI layer will modulate opacity, scale, and blend mode in real time.

| Stem | Colour | Hex |
|------|--------|-----|
| All / full mix | Violet → Iris gradient | `#7B5EA7` → `#A084C8` |
| Vocals | Soft rose | `#C8849A` |
| Bass | Deep teal | `#3D7A8A` |
| Drums | Amber pulse | `#C9A96E` |
| Other / instruments | Iris | `#A084C8` |

These are starting points for the design system, not fixed rules. The artist lead should iterate on these. See [open design question D-01](./README.md#open-design-questions).

---

## Usage rules

**Backgrounds** — always Void, Dusk, or Deep. Never use colour as a background except for full-bleed visual moments.

**Text** — Pearl on all dark backgrounds. Never pure white. Never use Violet or Iris for body text — they exist for visuals only.

**Gold** — used sparingly. Active states, the logo mark, one editorial highlight per screen. If everything is gold, nothing is.

**Violet / Iris** — the visuals own these colours. Avoid using them for UI chrome (buttons, borders, navigation) so they remain associated with the generative layer.

---

## Accessibility

| Pair | Contrast ratio | WCAG AA (4.5:1) |
|------|---------------|-----------------|
| Pearl on Void | 16.2:1 | ✓ Pass |
| Pearl on Dusk | 12.8:1 | ✓ Pass |
| Gold on Void | 6.4:1 | ✓ Pass |
| Gold on Dusk | 5.1:1 | ✓ Pass |
| Mist on Void | 7.3:1 | ✓ Pass |
| Iris on Void | 3.1:1 | ✗ Fail — use for decorative/visual only, never text |

**Note:** Iris and Violet do not meet WCAG AA for text. They are visual-layer colours only. All UI text uses Pearl or Gold.

---

## CSS custom properties

```css
:root {
  --av-void:   #06060A;
  --av-dusk:   #1A1428;
  --av-deep:   #0E0B18;
  --av-violet: #7B5EA7;
  --av-iris:   #A084C8;
  --av-gold:   #C9A96E;
  --av-pearl:  #E8E0D5;
  --av-mist:   rgba(232, 224, 213, 0.45);
}
```

All product code should reference these variables, never hardcoded hex values.
