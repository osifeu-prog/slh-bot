# SLH EMPIRE Commerce Rollout — Source of Truth

This document describes a proposed code change on this branch. It does not mean the offer is live in production.

## Offers proposed by this branch

- VIP via Telegram Stars: the existing `/vip` recurring subscription remains 499 Stars/month. The existing launch benefits remain governed by their current qualification and deadline.
- VIP via Credits: `/vipcredits` is a manual one-month purchase for 150 Credits. It does not auto-renew. A second call while VIP is active reports the expiry and does not debit again.
- Investor digital bundle: `/buystars slh_investor_bundle` is one 899-Star purchase and grants the eight existing digital entitlements: Agent OS, Trade Pro permission, the three existing courses, and three emoji packs. The included item prices sum to **1,321 Stars** (199 + 199 + 299 + 299 + 150 + 50 + 100 + 25), so the discount is **422 Stars (~31.95%)**, not 622 Stars/41%.
- The bundle includes a fixed 50-Credit bonus and one complimentary VIP month. A separate WhatsApp cashback policy is specified at 10% of Stars paid, rounded half-up to whole Credits (899 Stars would return 90 Credits), but **cashback is not currently issued** because the per-purchase WhatsApp-intent-to-payment attribution writer is not implemented. Do not advertise the extra 90 Credits or the 140-Credit total yet.
- ESP32 Pro retains its canonical price of 888 Credits and existing hardware grant, and adds Agent OS plus three complimentary VIP months. The proposed 10% WhatsApp cashback on a completed 888-Credit purchase would be 88.8 Credits, but it is **not active** until a verified per-purchase attribution record is written. Inventory comes from canonical runtime state; never advertise a fixed quantity without a live inventory check.
- Referral VIP rewards: after a referred user successfully pays for a VIP Stars subscription, the buyer receives 25 Credits once per buyer and the referrer receives 10% of each valid VIP Stars charge as Credits, rounded half-up to whole Credits (499 Stars returns 50 Credits to the referrer). Each award is keyed to the immutable identity of the buyer or payment charge to prevent replay duplication.

## WhatsApp attribution boundary

- Use the WhatsApp campaign deep link `https://t.me/Me_ad_main_bot?start=wa_8789977826`. It preserves the referrer ID and records the WhatsApp acquisition source without overwriting an existing referral relationship.
- The current `wa_<referrer_uid>` start payload records a campaign touch; it does not prove that a specific later payment came from a particular WhatsApp inquiry. The reward helper now requires a `whatsapp_purchase_attributions[purchase_id]` record with matching user, SKU, amount/currency, verified intent ID, hashed provider message ID and completed-order status. No code in this branch writes that record yet, so cashback calls fail closed and **no WhatsApp cashback is currently issued**.
- This is **not yet a full WhatsApp checkout integration**. The `slh-api` inbound Twilio adapter is not implemented/verified end-to-end; the current bot change cannot prove that every purchase happened inside a WhatsApp chat or associate a WhatsApp MessageSid with the final Telegram payment. The Control Plane WhatsApp catalog/intents PR is separately default-off and must be reviewed/deployed with the adapter before promoting automatic WhatsApp replies.
- Referral VIP rewards are implemented against persisted `users[buyer].referral.referred_by` plus a confirmed VIP Stars charge: 25 Credits for the buyer once per buyer UID and 10% of each paid monthly VIP Stars charge to the referrer in Credits. A click or WhatsApp message alone does not trigger these rewards. These rewards are direct ledger Credits issuance, not Treasury-funded commissions; the economics and recurring-commission policy must be explicitly approved before merge.

## Replay and accounting safety

- Bundle item grants use stable child purchase IDs derived from the immutable Telegram Stars charge/purchase ID.
- The fixed 50-Credit bundle bonus and 10% cashback are separate ledger events with distinct idempotency keys.
- Complimentary VIP months are recorded in `vip_bonus_awards` in the same atomic DB update as the VIP entitlement extension; they do not create Stars revenue.
- The Credits-funded VIP debit, entitlement extension, and negative ledger event are one canonical atomic DB update.
- Referral buyer bonus and referrer commission are written to the canonical Credits ledger, with a preflight of both awards and stable keys.
- Nothing in this branch opens BNB or TON, alters on-chain balances, or changes external settlement configuration.

## Not included / must not be promised yet

- Daily Trade Pro signal delivery: granting the `trade_pro` permission does not prove that a daily signal delivery service or fixed cadence is running.
- Annual VIP: `/vip annual` (also accepts `/vip yearly` and `/vip שנתי`) creates a one-time Telegram Stars invoice for 4,990 Stars and grants 365 days of VIP. It is not recurring; no auto-renewal is started. The price is equal to 10 monthly payments of 499 Stars, so it saves 2 monthly payments (998 Stars).
- Private WhatsApp group membership, automated invite after payment, early-access-course announcements, and direct Q&A scheduling are not automated by this PR.
- Agent OS entitlement is granted with ESP32 Pro, but physical device staging / pre-installation is not automated.

## Release conditions

Keep this PR in draft until CI passes and reviewers validate the fulfillment, referral and cashback paths. Do not advertise the proposal as live or as full WhatsApp checkout until the PR is reviewed, merged, deployed and tested using non-customer test accounts. Keep the WhatsApp bridge default-off. No production state, user balance, inventory, payment, or deployment was modified by authoring this branch.
