#!/usr/bin/env python3
"""Prepare a deterministic BSC -> TON migration snapshot.

This tool is PRE-FLIGHT ONLY. It never signs, mints, transfers, approves,
creates liquidity, or changes any on-chain or internal balance.

Input sources:
  1) Etherscan V2 tokenholderlist (requires an Etherscan API key if the
     account/plan permits this endpoint), or
  2) a local JSON/CSV export of holder rows.

The output is a reviewable snapshot. Allocation is intentionally not
invented: excluded addresses must be explicit and any allocation multiplier
must come from an approved policy file.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from decimal import Decimal, InvalidOperation, getcontext
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

getcontext().prec = 50

TOKEN_DECIMALS = 15
DEFAULT_CONTRACT = "0xacb0a09414cea1c879c67bb7a877e4e19480f022"
ZERO = "0x0000000000000000000000000000000000000000"


def norm_address(value: str) -> str:
    value = str(value or "").strip()
    return value.lower()


def parse_quantity(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid holder quantity: {value!r}") from exc


def load_local(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        rows = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                address = row.get("TokenHolderAddress") or row.get("address") or row.get("holder")
                quantity = row.get("TokenHolderQuantity") or row.get("quantity") or row.get("balance")
                if address and quantity is not None:
                    rows.append({"TokenHolderAddress": address, "TokenHolderQuantity": quantity})
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("result", "data", "holders", "rows"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("local source must contain a holder list")
    return [x for x in data if isinstance(x, dict)]


def fetch_etherscan(contract: str, api_key: str, offset: int = 1000) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        query = urlencode(
            {
                "chainid": "56",
                "module": "token",
                "action": "tokenholderlist",
                "contractaddress": contract,
                "page": page,
                "offset": min(offset, 1000),
                "apikey": api_key,
            }
        )
        req = Request(
            f"https://api.etherscan.io/v2/api?{query}",
            headers={"User-Agent": "SLH-ton-migration-preflight/1.0"},
        )
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("result")
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        if not isinstance(result, list):
            raise RuntimeError(f"Etherscan returned no holder rows: {payload.get('message', 'unknown')}")
        rows.extend(result)
        if len(result) < offset:
            break
        page += 1
    return rows


def parse_policy(path: Path | None) -> dict:
    if path is None:
        return {}
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("policy file must be an object")
    return policy


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, help="local JSON/CSV holder export")
    ap.add_argument("--api-key-env", default="ETHERSCAN_API_KEY")
    ap.add_argument("--contract", default=DEFAULT_CONTRACT)
    ap.add_argument("--exclude-file", type=Path, help="JSON array of addresses to exclude")
    ap.add_argument("--policy", type=Path, help="approved allocation policy JSON; optional")
    ap.add_argument("--output", type=Path, default=Path("state/ton_migration_snapshot.json"))
    args = ap.parse_args()

    if args.input is None and not os.getenv(args.api_key_env, "").strip():
        print("ERROR: supply --input or configure the Etherscan API key in the named environment variable.", file=sys.stderr)
        return 2

    rows = load_local(args.input) if args.input is not None else fetch_etherscan(
        args.contract, os.getenv(args.api_key_env, "").strip()
    )

    explicit_excluded = {ZERO}
    if args.exclude_file:
        data = json.loads(args.exclude_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("--exclude-file must contain a JSON array")
        explicit_excluded.update(norm_address(x) for x in data if str(x).strip())

    policy = parse_policy(args.policy)
    policy_exclusions = policy.get("excluded_addresses", [])
    if isinstance(policy_exclusions, list):
        explicit_excluded.update(norm_address(x) for x in policy_exclusions if str(x).strip())

    by_address: dict[str, Decimal] = {}
    for row in rows:
        address = norm_address(row.get("TokenHolderAddress") or row.get("address") or row.get("holder"))
        if not address:
            continue
        quantity = parse_quantity(row.get("TokenHolderQuantity", row.get("quantity", row.get("balance", 0))))
        if quantity < 0:
            raise ValueError(f"negative holder quantity for {address}")
        by_address[address] = by_address.get(address, Decimal("0")) + quantity

    holders = []
    excluded = []
    eligible_total = Decimal("0")
    raw_total = Decimal("0")

    for address, balance in sorted(by_address.items(), key=lambda item: (-item[1], item[0])):
        raw_total += balance
        item = {
            "address": address,
            "bsc_balance": str(balance),
            "decimals": TOKEN_DECIMALS,
        }
        if address in explicit_excluded:
            item["excluded"] = True
            excluded.append(item)
            continue
        item["excluded"] = False
        eligible_total += balance
        holders.append(item)

    allocation_mode = policy.get("allocation_mode", "REVIEW_REQUIRED")
    if allocation_mode != "REVIEW_REQUIRED":
        raise ValueError("Only allocation_mode=REVIEW_REQUIRED is supported until policy is explicitly approved.")

    result = {
        "schema": "slh-ton-migration-snapshot-v1",
        "source_chain": "BSC",
        "source_token_contract": args.contract,
        "source_decimals": TOKEN_DECIMALS,
        "snapshot_type": "current-holder-list-preflight",
        "allocation_status": "PENDING_POLICY_APPROVAL",
        "holder_count_seen": len(by_address),
        "eligible_holder_count": len(holders),
        "excluded_holder_count": len(excluded),
        "raw_token_total": str(raw_total),
        "eligible_token_total": str(eligible_total),
        "excluded_token_total": str(raw_total - eligible_total),
        "excluded_addresses": sorted(explicit_excluded),
        "holders": holders,
        "excluded": excluded,
        "policy": policy,
        "execution_allowed": False,
        "notes": [
            "No TON Jetton is created by this tool.",
            "No BSC holder receives TON allocation automatically.",
            "Do not map contracts, pools, treasury, controller, burn addresses or disputed addresses without explicit review.",
            "Final TON allocation must be approved before any mint/transfer.",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "holder_count_seen": len(by_address),
                "eligible_holder_count": len(holders),
                "excluded_holder_count": len(excluded),
                "raw_token_total": str(raw_total),
                "eligible_token_total": str(eligible_total),
                "allocation_status": result["allocation_status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
