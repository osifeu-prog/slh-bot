# SLH OS — Canonical FAQ

> Source: canonical SLH OS bot repository.  
> Purpose: one factual knowledge source for user-facing FAQ/AI answers.  
> This document must not be treated as a substitute for live runtime verification.

## 1. What is SLH OS?
SLH OS is a Telegram-based system with an AI assistant, Academy, internal Credits, wallet-related flows, agents, and a Mini App.

## 2. What are Credits?
Credits are an internal SLH OS balance. They are separate from on-chain tokens and are used by internal product/economy flows.

## 3. What is SLH?
SLH is a digital asset that can exist on-chain. An on-chain balance is not automatically the same thing as an internal Credits balance.

## 4. Credits vs. on-chain SLH
An on-chain transfer does not by itself create an internal Credits balance. Internal crediting must follow the platform's verified settlement rules.

## 5. Why is wallet binding required?
A blockchain transaction identifies an on-chain address, not automatically the Telegram user who should receive an internal balance. Wallet binding links a wallet address to a user identity after cryptographic verification.

## 6. What is TON wallet verification?
The canonical TON ownership flow uses a server-issued one-time challenge and TON Connect wallet proof/signature data. The server verifies the cryptographic response before creating a wallet binding.

## 7. What does TON wallet verification prove?
It is intended to prove control of the connected wallet address without asking the user for a seed phrase or private key.

## 8. What does TON verification NOT do?
Connecting a wallet does not by itself create Credits, perform a deposit settlement, or authorize a manual balance change.

## 9. What happens before a TON deposit is credited?
The expected order is:
wallet ownership verification → deposit detection/validation → settlement → internal balance update.

A historical on-chain transaction may exist without being credited to a user when the required binding/settlement conditions are not satisfied.

## 10. Is a TX hash enough to prove wallet ownership?
No. A TX hash identifies a blockchain transaction; it does not by itself prove that a specific Telegram user controls the sending wallet.

## 11. Should a user ever send a seed phrase?
No. SLH OS should never ask for a seed phrase or private key in the Mini App or bot.

## 12. What is BNB/BSC wallet verification?
BNB/BSC wallet verification is a separate wallet-ownership flow from TON. BNB and TON bindings must not be conflated.

## 13. What is KYC in SLH?
KYC means identity/customer verification performed by an appropriate identity-verification service or process. It is different from cryptographic wallet ownership verification.

## 14. Is KYC currently connected to the SLH OS bot?
No dedicated KYC service/handler was found in the current `slh-bot` source. Public website content may mention KYC, but those references are not proof of a live KYC verification integration in the bot.

## 15. How should the LLM answer KYC questions?
The LLM should distinguish:
- wallet ownership verification (cryptographic control of an address),
- KYC/identity verification (customer identity/process),
- and any public website text that is not a live runtime capability.

It must not claim that a user is KYC-verified unless a connected KYC service/runtime provides that status.

## 16. What if the user asks for current balances or runtime status?
Use authoritative runtime/read-only paths when available. The FAQ is background knowledge, not a replacement for live account or system state.

## 17. What if information conflicts with live runtime state?
Live, verified runtime state takes precedence over this FAQ. The FAQ should be updated afterward when the product behavior changes.

## 18. Money and safety
Do not promise returns, invent balances, or represent an on-chain transaction as an internal credit without verified settlement. Never request private keys or seed phrases.

## 19. Support principle
When a feature is not confirmed as live, say that it is not currently verified rather than presenting planned or documented behavior as a completed capability.
