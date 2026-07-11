# SLH Stable State - 2026-07-11

## Railway Production
Status: SUCCESS

Commit:
a27a8d1cc84b0c236754d743cc32cb5fc4a81582

Branch:
main

## Dashboard

Legacy:
GET /dashboard

Production V2:
GET /dashboard-v2

Status:
LIVE ✅

## API

Health:
GET /api/health

Expected:
{"status":"ok","version":"2.0"}

## Deployment

Repository:
osifeu-prog/slh-bot

Builder:
Dockerfile

Start:
sh /app/start_slh.sh

Volume:
 /app/state

## Notes

Dashboard V2 was merged from dashboard-v2-development
into main.

Railway source is now synchronized with production.
