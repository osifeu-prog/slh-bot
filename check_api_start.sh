#!/bin/bash

echo "=== APP END ==="
tail -40 web/api/app.py

echo
echo "=== PORT REFERENCES ==="
grep -R "PORT\|app.run\|gunicorn" -n web/api app.py 2>/dev/null

echo
echo "=== RAILWAY FILES ==="
cat railway.json
cat Procfile
