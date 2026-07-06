#!/bin/bash
# Payment safety checklist - run BEFORE every git push that touches payment files
echo "🔒 Payment Safety Check"
FAIL=0

if ! grep -q "existing_charge_ids" payment_handler.py 2>/dev/null; then
    echo "❌ MISSING: idempotency guard (existing_charge_ids) in payment_handler.py"
    FAIL=1
else
    echo "✅ idempotency guard present"
fi

if ! grep -q "CRITICAL: save_db failed" payment_handler.py 2>/dev/null; then
    echo "❌ MISSING: save_db error handling in payment_handler.py"
    FAIL=1
else
    echo "✅ save_db error handling present"
fi

if grep -qE "^[^#]*register_ton_handlers\(bot\)" bot_stable.py 2>/dev/null; then
    if ! grep -q "^import datetime" ton_handler.py 2>/dev/null && ! grep -q "^from datetime" ton_handler.py 2>/dev/null; then
        echo "❌ DANGER: ton_handler is ACTIVE but missing datetime import - will crash on real deposit"
        FAIL=1
    fi
else
    echo "✅ ton_handler is disabled (or has datetime import)"
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
