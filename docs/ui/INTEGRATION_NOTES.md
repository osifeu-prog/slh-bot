# Integrating Design System v1 into mini_app.html

## Goal

Apply IA + tokens without breaking TON/BNB API calls.

## Steps

1. Keep existing `function show`, `bindTonWallet`, `loadMe`, etc.
2. Add class `slh-ds` on `<body>`.
3. Paste or `@import` rules from `slh-tokens.css` into the main `<style>` (or extend `:root`).
4. Replace the dense top `.nav` grid with bottom nav markup:

```html
<nav class="slh-bottom-nav" id="slhBottomNav">
  <button type="button" data-screen="home" class="active">🏠 בית</button>
  <button type="button" data-screen="wallet">👛 ארנק</button>
  <button type="button" data-screen="market">🛍 שוק</button>
  <button type="button" data-screen="more">⋯ עוד</button>
</nav>
<div class="slh-more-sheet" id="slhMoreSheet">
  <button type="button" data-screen="transfer">💸 העברה</button>
  <button type="button" data-screen="buy">💳 קנייה</button>
  <button type="button" data-screen="stake">🔒 סטייקינג</button>
  <button type="button" data-screen="academy">🎓 Academy</button>
  <button type="button" data-screen="exchange">🪙 בורסה</button>
  <button type="button" data-screen="alpha">🚀 Alpha</button>
  <button type="button" data-screen="control">🧭 Control</button>
  <button type="button" data-screen="ai">✨ AI</button>
  <button type="button" data-screen="system">🖥 מערכת</button>
</div>
```

5. Wire clicks to existing `show(id)` and hide more-sheet except when `more`.
6. Map TON UI states to pills:
   - not bound → `muted`
   - connected waiting proof → `pending` + hint «אשר חתימה בארנק»
   - verified → `ok` + short address
   - error / expired → `danger` + retry button

## Do not

- Remove Telegram `initData` auth gate
- Change `/api/wallet/ton/challenge|verify` payloads
- Add mnemonic / seed inputs

## Verify after deploy

- [ ] Home loads credits
- [ ] Wallet shows binding pills
- [ ] TON Connect still opens modal
- [ ] Bottom nav reaches Academy / Control
- [ ] No seed UI
