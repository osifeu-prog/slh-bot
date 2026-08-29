#!/bin/bash
set -e
python3 -m compileall -q core handlers services
python3 -m py_compile bot_gateway.py core/economy_service.py core/reward_engine.py core/stake_position.py core/binance_connector.py core/deposit_monitor.py core/ton_lab.py handlers/staking_handler.py handlers/brief_handler.py handlers/claim_handler.py handlers/task_handler.py
python3 -c "import json; json.load(open('state/db.json', encoding='utf-8')); print('DB_JSON_OK')"
python3 -c "import core.economy_service, core.reward_engine, core.stake_position, core.binance_connector, core.deposit_monitor, core.ton_lab; print('IMPORTS_OK')"
echo PRE_PUSH_PASS