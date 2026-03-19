# Brand

This directory is the living brand reference for Auris Vive. It is maintained by the design team and is the single source of truth for visual identity, voice, and experience principles.

If you are an engineer looking for the pipeline architecture, you want [`../engineering/`](../engineering/).

---

## Contents

| File | What it is |
|------|-----------|
| [`identity.html`](./identity.html) | Full brand sketch — open in a browser. Colours, type, logo variants, taglines, animated waveform, product moment. |
| [`palette.md`](./palette.md) | Colour system with hex values, usage rules, and accessibility notes |
| [`typography.md`](./typography.md) | Type system — fonts, weights, scale, usage contexts |
| [`voice.md`](./voice.md) | Brand voice guide — what Auris Vive sounds like in copy |
| [`assets/`](./assets/) | Exportable assets — logos, swatches, motion references *(in progress)* |

---

## The visual identity in brief

**Logo mark** — an orbital system. Concentric rings rotating around a golden core. Represents AI listening inward, collapsing complexity into a single point of light.

**Colour** — near-black backgrounds (Void, Dusk), living violet and iris for the generative visuals, warm gold as the accent. Pearl for typography on dark.

**Type** — Cormorant Garamond (display, brand voice — ancient, refined, felt) paired with Jost (UI, functional — geometric, airy, never competing with the visuals).

**Motion** — slow. Long wavelengths. The visuals breathe, they don't pulse. Even at high tempo music the visual language stays unhurried. This is intentional — it is what makes Auris Vive feel like an environment rather than a reaction.

---

## Open design questions

These are decisions the design team needs to resolve. Engineers are blocked on some of these.

| ID | Question |
|----|----------|
| D-01 | What does each stem *look like* individually? Bass vs trumpet vs piano — do they have distinct visual languages, or does the whole mix determine the aesthetic? |
| D-02 | How do the visuals transition when a user taps a stem pill? Cut, dissolve, or morph? |
| D-03 | Is there a "calm mode" visual preset distinct from the default? Or does the music's own character determine the energy? |
| D-04 | Logo mark — static SVG only, or should there be a motion version for app loading / splash? |
| D-05 | Light mode — does Auris Vive have one, or is it always dark? (Current instinct: always dark.) |

---

## Contributing

When adding or updating brand files, follow these conventions:

- All colour values in hex, not RGB or HSL
- Type specimens should use real Auris Vive copy, not lorem ipsum
- Motion descriptions should be in plain language (e.g. "eases in over 800ms, settles with a slight overshoot") not just easing function names
- Keep `identity.html` as a standalone file — all assets inlined, no external dependencies except Google Fonts

---

*Brand maintained by the design team. Questions → open an issue tagged `brand`.*
