# SLH KERNEL RULES (IMMUTABLE)

1. Only one runtime kernel exists: SLH_KERNEL.py
2. All input enters via kernel.emit()
3. All execution passes kernel.route()
4. No module may access OS directly
5. No duplicate event loops allowed
6. All modules must implement BaseModule contract
7. Telegram is an adapter, not a core system
