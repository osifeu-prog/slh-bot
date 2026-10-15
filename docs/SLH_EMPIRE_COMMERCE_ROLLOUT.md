# SLH EMPIRE Commerce Rollout — Source of Truth

This document describes a proposed code change on this branch. It does not mean the offer is live in production.

## Canonical offers in this change

- VIP via Telegram Stars: the existing /vip recurring subscription remains 499 Stars/month. The pre-existing launch-benefit path remains governed by its existing qualification and deadline.
- VIP via Credits: /vipcredits is a manual one-month purchase for 150 Credits. It does not auto-renew. A second call while VIP is active reports the expiry and does not debit again.
- Investor digital bundle: /buystars slh_investor_bundle is one 899-Star purchase and grants the eight existing digital SKUs: Agent OS, Trade Pro permission, the three existing courses, and three emoji packs. The included item prices sum to 1,321 Stars (199 + 199 + 299 + 299 + 150 + 50 + 100 + 25), so the proposed bundle discount is 422 Stars (~31.95%), not 622 Stars/41%. The bundle also grants 50 Credits and one complimentary VIP month.
- ESP32 Pro: the existing 888-Credit SKU retains its canonical price and hardware grant, and adds Agent OS plus three complimentary VIP months through the same idempotent grant pathway. Inventory is canonical runtime state and must be checked before claiming a particular stock number.

## Replay and accounting safety

- Bundle item grants use a stable child purchase ID based on the immutable Telegram Stars charge/purchase ID.
- The 50-Credit bonus is written through the canonical economy ledger with an idempotency key.
- Complimentary VIP months are written to vip_bonus_awards in the same atomic DB update as the VIP entitlement extension; they do not create Stars revenue.
- The Credits-funded VIP debit, entitlement extension, and negative ledger event are one canonical atomic DB update.
- This change does not open BNB or TON, alter on-chain balances, or change external settlement configuration.

## Not enabled by this change

- Daily Trade Pro signals: the bundle grants the current trade_pro permission; this is not proof that a daily signal-delivery service is running. Do not promise daily signals until delivery and cadence are verified.
- 10% WhatsApp cashback: no reward is issued merely because a customer sends a WhatsApp message. Cashback must be tied to a verified WhatsApp-origin purchase intent and the corresponding canonical completed Telegram order.
- Referral-to-purchase commission and newcomer 25-Credit bonus: existing referral-start telemetry is not proof of paid conversion. Do not promise these rewards until first-touch attribution, paid VIP conversion, and idempotent reward settlement are connected and tested end-to-end.
- Annual VIP for 4,990 Stars: no annual SKU or 12-month payment authority is created here.
- Agent OS “preinstalled” on a physical ESP32: the app entitlement is granted, but physical staging/installation is not automated by this change.

## Release conditions

Do not advertise the proposed offer as purchasable until this PR is reviewed, merged, deployed and tested with a non-customer test account. Keep the WhatsApp bridge disabled by default. This is a code proposal only; no production state, user balance, inventory, or payment was modified by authoring it.
