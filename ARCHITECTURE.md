# SLH OS Architecture

## Layers
1. Telegram Bot – 45+ commands, Admin panel
2. Flask API – agents, tasks, health, stats, logs
3. Web Dashboard – real-time monitoring
4. Kernel – EventBus + TaskPlugin
5. Agent OS – state, inbox, permissions
6. Marketplace – Plugin Store
7. Monetization – Free/Pro/Enterprise plans
8. Inspector/Master Agents – self-diagnostics

## Data Flow
User → Telegram → Bot → EventBus → Plugins → DB
                      ↓
                   Flask API → Dashboard
