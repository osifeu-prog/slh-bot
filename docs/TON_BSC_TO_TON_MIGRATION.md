# SLH BSC → TON Migration Preflight

## Current source evidence

BscScan currently identifies the BSC SLH contract as:

- Contract: \`0xacb0a09414cea1c879c67bb7a877e4e19480f022\`
- Decimals: 15
- Reported holders in the indexed page: 247
- Reported max total supply: 111,186,328 SLH

The indexed holder page is a point-in-time external source; a production snapshot must be generated at the actual migration cutoff.

## Required order

1. Freeze the snapshot timestamp and source.
2. Export the complete holder set with balances.
3. Explicitly classify treasury, controller, liquidity pair, burn/null addresses, contracts and disputed addresses.
4. Produce a reviewable allocation table.
5. Approve the allocation policy.
6. Only then create the TON Jetton.
7. Mint/distribute exactly the approved amount.
8. Disable further mint authority according to the selected Jetton implementation.
9. Create the TON/SLH pool.
10. Seed liquidity from a separately approved amount of TON and SLH.
11. Verify the pool and Jetton metadata from independent readers.
12. Publish the Mini App swap entry only after the master address and pool are verified.

## No automatic parity claim

The migration tool does not assume that every BSC holder should receive TON SLH 1:1.
That policy has to be explicitly approved because the BSC supply may contain the
treasury, liquidity, disputed balances, contracts or other addresses that should
not be migrated.

## DEX integration

STON.fi documents a mainnet workflow where the API simulates the swap, returns
routing metadata, and the application builds transaction parameters from that
result before sending the signed transaction through TonConnect.

STON.fi also provides a direct swap-link format:

\`https://app.ston.fi/swap?ft=TON&tt=YOUR_JETTON_ADDRESS\`

DeDust supports creation of a Jetton vault and a volatile TON/Jetton pool, then
users swap through the Vault/Pool architecture.

The SLH Mini App should therefore keep a configuration-driven \`TON_SLH_JETTON_MASTER\`
and activate the "Buy SLH" button only after the master and pool have been
independently verified.

## Hard security gates

The launch package must not:

- store a mnemonic or private key in the repository;
- mint after the final supply is frozen;
- seed a pool before the allocation and liquidity policy are approved;
- present a target price as a live market price;
- treat an external DEX pool balance as internal Credits;
- accept USDT/Jettons as deposits until the exact Jetton master and settlement
  rules are verified.

## Regulatory gate

A public token distribution can engage Israeli securities rules depending on the
asset's characteristics and the structure of the offering. Israeli authorities
have noted that some digital-asset offerings can fall under existing securities
frameworks, while other digital assets may fall outside it. This must be reviewed
for the actual SLH offering, target jurisdictions and user access policy before
public sale.

Tax treatment in Israel also treats digital assets as a relevant taxable category,
so the accounting/export design should preserve transaction provenance.
