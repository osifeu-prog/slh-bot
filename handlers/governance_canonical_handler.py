"""Adapter that binds the existing Governance commands to canonical db state."""

from core import governance_store
from handlers import governance_handler as legacy


def register(bot, context=None):
    # Migrate legacy governance.json exactly once when canonical state is absent.
    governance_store.ensure_canonical()

    # Keep command behavior in the existing handler while replacing its
    # persistence boundary. All subsequent reads/writes use db.json.
    legacy._load_gov = governance_store.load_governance
    legacy._save_gov = governance_store.save_governance
    legacy.register(bot, context)
