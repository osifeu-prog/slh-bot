# API Reference

Base URL: `http://localhost:5000/api`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/stats` | GET | System statistics |
| `/logs?n=50` | GET | Last N log lines |
| `/agents` | GET/POST | List/Create agents |
| `/tasks` | GET/POST | List/Create tasks |
| `/subscriptions` | GET | All subscriptions |
| `/subscriptions/me?user_id=` | GET | User's plan |
