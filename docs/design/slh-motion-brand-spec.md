# SLH OS Motion & Brand Specification

## Canonical visual language

SLH OS uses a geometric hexagonal shield with three connected layers and a central node.

Palette:
- Electric Cyan: `#00F2FE`
- Ultra Violet: `#7F00FF`
- Mint Green: `#00FF87`
- Deep background: `#0D0F12` / `#07111C`

The canonical static assets are:
- `branding/slh-logo.svg`
- `branding/favicon.svg`

Both assets use the same shield/layer/core motif.

## 1. Video generation prompt — Sora / Runway / Pika

```text
A futuristic 3D logo reveal and motion graphics loop for a technology ecosystem named "SLH OS - Smart Layer Hub".

Dark mode background with deep charcoal blue tone (#0D0F12) and subtle cyan glowing grid lines.

Phase 1: Glowing cyan laser paths and futuristic terminal code converge rapidly from the edges into a bright central point of light.

Phase 2: The core light splits into three orbiting energy rings in Electric Cyan, Ultra Violet Purple, and Mint Green. They spin smoothly and merge into a glowing glassmorphism 3D hexagon with neon light refraction.

Phase 3: The hexagon separates into three floating transparent glass layers. Layer 1 displays an interconnected node network, Layer 2 displays neural AI streams, and Layer 3 shows a clean user interface. The camera subtly tilts to show 3D depth and glass refraction.

Phase 4: The three layers snap back together with a bright pulse wave, revealing a sleek geometric shield "S" mark with modern "SLH OS" typography and subtitle "SMART LAYER HUB".

Professional cinematic motion graphics, smooth 60fps motion, volumetric lighting, glowing ambient occlusion, glass reflections, seamless loop.
```

## 2. After Effects / Rive / Lottie animation spec

### Layer hierarchy

1. `BG_Grid` — subdued cyan grid with vignette.
2. `Terminal_Streams` — terminal/code particles converging toward center.
3. `Core_Nodes` — three orbiting nodes using Trim Paths and the canonical palette.
4. `Hexagon_3D_Layers`
   - `Layer_3_Top` — UI interface
   - `Layer_2_Mid` — AI logic
   - `Layer_1_Base` — network nodes
5. `Logo_Mark` — canonical shield/core mark plus `SLH OS` and `SMART LAYER HUB`.

### Timing

- **0.0–1.0s — Converge:** terminal streams and nodes move into the center with strong ease-out.
- **1.0–2.5s — Rotation & Merge:** three core nodes orbit and merge into the glass hexagon.
- **2.5–4.0s — Glass Split:** the three layers separate on Z with a subtle Y-axis camera orbit.
- **4.0–5.5s — Pulse & Reveal:** layers snap together, scale overshoots slightly, then settle to 100%; a pulse ring expands and fades.

Suggested easing: `cubic-bezier(0.16, 1, 0.3, 1)`.

## 3. Telegram / web asset pipeline

### Static
Use the canonical SVG for:
- Dashboard headers
- Mini App branding
- Website branding
- Invoice/document headers
- Favicon

### Animated
Create a short 512×512 loop derived from Phase 2 + Phase 4 for Telegram-compatible animated branding. Keep the animation visually identical to the canonical shield/core mark.

### Mini App splash

The Motion Concept can become a lightweight splash sequence, but production integration should remain separate from the financial/authentication path. The splash must:
- never block Telegram authentication;
- never fabricate wallet/economy state;
- fail open to the normal Mini App UI if animation assets fail;
- keep Haptic feedback optional and browser/Telegram capability-gated;
- avoid external asset dependencies where possible.

Recommended synchronization labels:
- `Connecting Anti-Fraud Synapses…`
- `Syncing Economy Grid…`
- `Neural Core Active`

Recommended target duration: about 2.7 seconds, with a user-skippable/fail-safe transition.

## Interactive Motion Concept

The supplied Canvas concept remains a design/prototype artifact. Its four phases are:

1. Matrix Grid / Node Convergence
2. Core Spheres Assembly
3. Multi-Layer 3D Tilt
4. Logo Snap / Shockwave Reveal

When the concept is embedded in production, the final Phase 4 SVG should reference the same canonical `branding/slh-logo.svg` geometry rather than maintaining a second independent logo definition.

## Production boundary

This document is design source-of-truth only. It does not open BNB/TON settlement, change wallet accounting, or alter Telegram authentication semantics.
