#!/bin/bash
# Payment safety checklist - run BEFORE every git push that touches payment files
echo "🔒 Payment Safety Check"
FAIL=0

if ! grep -q "existing_charge_ids" payment_handler.py 2>/dev/null; then
    echo "❌ MISSING: idempotency guard (existing_charge_ids) in payment_handler.py"
    FAIL=1
else
    echo "✅ Stars idempotency guard present"
fi

if ! grep -q "CRITICAL: save_db failed" payment_handler.py 2>/dev/null; then
    echo "❌ MISSING: save_db error handling in payment_handler.py"
    FAIL=1
else
    echo "✅ Stars save_db error handling present"
fi

TON_ACTIVE=0
if grep -qE "^[^#]*register_ton_handlers\(bot\)" bot_stable.py 2>/dev/null; then
    TON_ACTIVE=1
fi

if [ $TON_ACTIVE -eq 1 ]; then
    if ! grep -q "^from datetime import\|^import datetime" ton_handler.py 2>/dev/null; then
        echo "❌ DANGER: ton_handler is ACTIVE but missing datetime import"
        FAIL=1
    else
        echo "✅ ton_handler datetime import present"
    fi

    if grep -q 'DEFAULT_WALLET = "YOUR_WALLET_ADDRESS"' ton_handler.py 2>/dev/null; then
        echo "❌ DANGER: ton_handler is ACTIVE but wallet is still placeholder"
        FAIL=1
    else
        echo "✅ ton_handler wallet configured"
    fi

    if ! grep -q "used_ton_txs" ton_handler.py 2>/dev/null; then
        echo "❌ DANGER: ton_handler is ACTIVE but missing idempotency guard (used_ton_txs)"
        FAIL=1
    else
        echo "✅ ton_handler idempotency guard present"
    fi

    if ! grep -q 'wallet == "YOUR_WALLET_ADDRESS"' ton_handler.py 2>/dev/null; then
        echo "⚠️  WARNING: ton_handler has no runtime placeholder guard in /ton command"
    else
        echo "✅ ton_handler runtime placeholder guard present"
    fi
else
    echo "✅ ton_handler is disabled"
fi

if [ $FAIL -eq 1 ]; then
    echo ""
    echo "🚨 SAFETY CHECK FAILED - do not push until fixed"
    exit 1
else
    echo ""
    echo "✅ All payment safety checks passed"
    exit 0
fi
