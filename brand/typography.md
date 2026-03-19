# Typography

Auris Vive uses two typefaces. They should never compete — Cormorant Garamond carries the brand's soul, Jost handles everything functional.

---

## Typefaces

### Cormorant Garamond — display and brand voice

A refined serif with deep historical roots and an unusual lightness at small weights. It reads as both ancient and contemporary — which maps exactly to what Auris Vive is doing: ancient human experience (music, feeling, the body's response to sound) expressed through new intelligence.

**Source** — Google Fonts: `Cormorant Garamond`
**Weights used** — Light (300), Light Italic (300 italic)
**Never use** — Bold or Regular weights in product UI. The lightness is the point.

Usage contexts:
- Wordmark: `AURIS` in Light, `Vive` in Light Italic
- Display headings in marketing and onboarding
- Taglines and editorial copy
- Track name in the now-playing view

### Jost — UI and functional copy

A geometric sans-serif with unusual airy proportions at light weights. It disappears into the UI — which is exactly right. Auris Vive's chrome should be as invisible as possible so the visuals dominate.

**Source** — Google Fonts: `Jost`
**Weights used** — ExtraLight (200), Light (300), Regular (400)
**Never use** — Medium (500) or heavier. Too loud.

Usage contexts:
- Navigation, labels, metadata
- Stem pill labels
- Settings and utility UI
- All-caps section labels (tracked wide, weight 300–400)

---

## Type scale

| Role | Font | Weight | Size | Tracking | Case |
|------|------|--------|------|----------|------|
| Wordmark — Auris | Cormorant Garamond | 300 | 72px | +0.18em | Upper |
| Wordmark — Vive | Cormorant Garamond | 300 italic | 72px | +0.18em | Sentence |
| Display heading | Cormorant Garamond | 300 | 56px | +0.04em | Sentence |
| Display italic | Cormorant Garamond | 300 italic | 56px | +0.04em | Sentence |
| Tagline | Cormorant Garamond | 300 italic | 26px | 0 | Sentence |
| Track title | Cormorant Garamond | 300 | 36px | 0 | Sentence |
| Section label | Jost | 400 | 11px | +0.24em | Upper |
| UI body | Jost | 200 | 15px | +0.12em | Sentence |
| Caption / metadata | Jost | 300 | 13px | +0.08em | Sentence |
| Stem pill label | Jost | 300 | 11px | +0.12em | Upper |
| Eyebrow / tag | Jost | 400 | 10px | +0.24em | Upper |

---

## Hierarchy in practice

The wordmark is always the only instance of large Cormorant Garamond on a screen. Do not use display-size serif headings in the same view as the wordmark — they compete.

In product UI (now-playing, stem view, settings), Cormorant Garamond appears only for the track title and artist name. Everything else is Jost.

In marketing and brand contexts (landing page, App Store screenshots, onboarding), Cormorant Garamond may be used more broadly for headlines and taglines.

---

## Loading fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
```

```css
--av-font-display: 'Cormorant Garamond', Georgia, serif;
--av-font-ui:      'Jost', system-ui, sans-serif;
```

---

## What not to do

- Do not use Inter, SF Pro, Roboto, or any system sans-serif as a substitute for Jost
- Do not use Cormorant Garamond at weights above 300 in product UI
- Do not use all-caps for Cormorant Garamond text — it destroys the letterform rhythm
- Do not mix a third typeface into the system
