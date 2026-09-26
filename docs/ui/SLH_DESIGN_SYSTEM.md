# SLH Mini App — Design System v1

Scope: Telegram Mini App (`mini_app.html`), RTL Hebrew, dark financial UI.
Does **not** change deposit/binding APIs — presentation and IA only.

## Principles

1. **One primary action per screen**
2. **Status before action** (wallet state machine visible)
3. **Credits ≠ on-chain ≠ TON deposit** — never mix in one number
4. **4-tab bottom nav** — secondary screens under «עוד»
5. **User language** for errors; keep `TON_*` codes in logs only

## Color tokens

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#070A12` | Page background |
| `--surface` | `#111827` | Cards |
| `--surface-2` | `#0D1422` | Nested panels |
| `--elevated` | `#1A2234` | Modals / elevated |
| `--border` | `#2A3548` | Hairline borders |
| `--text` | `#F8FAFC` | Primary text |
| `--text-2` | `#CBD5E1` | Secondary |
| `--muted` | `#94A3B8` | Labels |
| `--accent` | `#7C5CFF` | Primary CTA |
| `--accent-2` | `#20D3A7` | Success / staked |
| `--ok` | `#34D399` | Verified |
| `--pending` | `#FBBF24` | Waiting proof |
| `--danger` | `#FB7185` | Error / rejected |
| `--info` | `#38BDF8` | Neutral info |

## Typography

| Role | Size | Weight |
|------|------|--------|
| Hero balance | 32–36px | 800–900 |
| Screen title | 16–18px | 800 |
| Body | 13–14px | 400–500 |
| Label | 11–12px | 500 |
| Address (LTR mono) | 11px | 500 |

Line-height body (Hebrew): **1.5**.

## Spacing

Base unit **4px**. Common: 8 / 12 / 16 / 24.
Card padding: **16px**. Button min height: **44px**.

## Radius

| Element | Radius |
|---------|--------|
| Card | 16–20px |
| Button | 12–14px |
| Pill | 999px |
| Logo | 14px |

## Components

### Status pill

- `ok` — verified wallet
- `pending` — connected, waiting signature
- `danger` — rejected / expired
- `muted` — not connected

### Primary button

Gradient `accent` → deeper purple. One per viewport section.

### Toast

Fixed above bottom nav, 3.5s, no secrets in text.

### Bottom navigation

```
בית | ארנק | שוק | עוד
```

«עוד» opens: Academy, Staking, Exchange, Transfer, Buy, Alpha, Control, AI, System.

## Wallet state machine (copy)

| State | Pill | User text |
|-------|------|-----------|
| `none` | muted | לא מחובר · לחץ לאימות |
| `awaiting_proof` | pending | אשר חתימה בארנק · אל תסגור את המסך |
| `verified` | ok | מאומת · {short address} |
| `error` | danger | נדחה · נסה שוב |
| `gate_closed` | info | הפקדות סגורות כרגע |

Never ask for seed / mnemonic in UI.

## TON Connect notes

- Pin `@tonconnect/ui@3.0.2` (current stable as of 2026-08).
- Manifest: `https://slh-nft.com/tonconnect-manifest.json`
- Proof domain must stay in server allowlist (`slh-nft.com`, …).
- Surface `Script error` as: «תקלה בחיבור הארנק · נסה שוב מתוך Telegram».

## Implementation order

1. Apply CSS tokens (see `docs/ui/slh-tokens.css`)
2. Bottom nav IA
3. Wallet status machine UI
4. Home «next step» single CTA
5. Polish remaining screens under same tokens

## Out of scope

- Changing `/api/wallet/*` contracts
- Manual credit / bypass binding
- Light theme (unless product asks later)
