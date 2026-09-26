# SLH BSC / SLH Send Runbook — 2026-09-26

## Purpose
Reusable procedure for connecting a user's BNB wallet and sending SLH directly on BNB Smart Chain without custody.

## Current production facts
- BSC chain ID: 56.
- SLH token contract: 0xACb0A09414CEA1C879c67bB7A877E4e19480f022.
- Token decimals: 15.
- SLH OS does not receive or store the user's seed phrase or private key.
- Wallet binding is a one-time signed challenge using the canonical BNB binding authority.
- A transfer is prepared client-side and is signed/broadcast by the user's own wallet.
- Settlement/deposit accounting is separate from outbound transfer and remains gated.

## User procedure
1. Open the Mini App from Telegram.
2. Connect the BNB wallet with WalletConnect or an injected EVM wallet.
3. Complete the one-time ownership signature.
4. Confirm the wallet is on BNB Smart Chain (56).
5. Enter the destination address and a small test SLH amount first.
6. Run **Check Gas**.
7. Confirm the screen shows:
   - real SLH balance;
   - real BNB balance;
   - estimated gas;
   - current gas price;
   - estimated BNB fee;
   - post-fee BNB balance;
   - safety reserve.
8. Press **Send SLH** and verify the recipient, amount, chain and fee in the wallet itself.
9. Copy the resulting TX hash and inspect it on BscScan.
10. Only after the test transfer is confirmed should a larger transfer be considered.

## Gas safety
The Mini App uses `eth_estimateGas` and current `eth_gasPrice`. It adds a 25% fee buffer and retains a 0.001 BNB reserve before allowing the transaction to be prepared. The wallet remains the final source for the exact fee shown at confirmation.

## Failure collection
Ask the user for:
- wallet provider name;
- Android/iPhone/desktop;
- public wallet address;
- public BNB balance;
- public SLH balance;
- current BSC chain;
- exact error text;
- TX hash if one was created.

Never request seed words, private keys, passwords or 2FA codes.
