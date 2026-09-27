def load_handlers(bot, context):
    from handlers.logo_handler import register_logo_handler
    register_logo_handler(bot)

    print("📦 Loading modular handlers...")

    modules = [
        ("dashboard", "handlers.dashboard_handler"),
        ("os", "handlers.os_handler"),
        ("market", "handlers.market_handler"),
        ("monetization", "handlers.monetization_handler"),
        ("business_control", "handlers.business_control_handler"),
        ("bot_system_control", "handlers.bot_system_control_handler"),
        ("trade_terminal", "handlers.trade_terminal_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("agents", "handlers.agents_handler"),
        ("audit", "handlers.audit_handler"),
        ("deploy", "handlers.deploy_handler"),
        ("termux", "handlers.termux_handler"),
        ("payment", "handlers.payment_handler"),
        ("stars_audit", "handlers.stars_audit_handler"),
        ("p2p", "handlers.p2p_handler"),
        ("exchange", "handlers.exchange_handler"),
        ("ui_exchange", "handlers.ui_exchange_handler"),
        ("econ", "econ_handler"),
        ("wallet", "handlers.wallet_handler"),
        ("legacy_wallet", "handlers.legacy_wallet_handler"),
        ("arcade", "handlers.arcade_handler"),
        ("share", "handlers.share_handler"),
        ("store", "handlers.store_handler"),
        ("bot_factory", "handlers.bot_factory"),
        ("stars_store", "handlers.stars_store"),
        ("webapp_data", "handlers.webapp_data_handler"),
        ("e", "handlers.e_handler"),
        ("alpha_control", "handlers.alpha_control_handler"),
        ("reconcile", "handlers.reconcile_handler"),
        ("revenue", "handlers.revenue_handler"),
        ("ton_address", "handlers.ton_address_handler"),
        ("usdt_audit", "handlers.usdt_audit_handler"),
        ("recon_release", "handlers.recon_release_handler"),
        ("ton_balance", "handlers.ton_balance_handler"),
        ("ton_claim", "handlers.ton_claim_handler"),
        ("withdraw", "handlers.withdraw_request_handler"),
        ("terms", "handlers.terms_handler"),
        ("task", "handlers.task_handler"),
        ("mission", "handlers.mission_handler"),
        ("academy", "handlers.academy_handler"),
        ("academy_menu", "handlers.academy_menu_handler"),
        ("device", "handlers.device_handler"),
        ("esp_control", "handlers.esp_control"),
        ("esp_agent_control", "handlers.esp_agent_control"),
        ("feedback", "handlers.feedback_handler"),
        ("gateway", "handlers.gateway_handler"),
        ("file", "handlers.file_handler"),
        ("help", "handlers.help_handler"),
        ("join", "handlers.join_handler"),
        ("kb", "handlers.kb_handler"),
        ("leaderboard", "handlers.leaderboard_handler"),
        ("rewards", "handlers.rewards_handler"),
        ("vault", "handlers.vault_handler"),
        ("gifts", "handlers.gifts_handler"),
        ("agent_submission_guard", "handlers.agent_submission_guard"),
        ("learning_path", "learning_path"),
        ("lesson", "handlers.lesson_handler"),
        ("bot_identity", "handlers.bot_identity_handler"),
        ("map", "handlers.map_handler"),
        ("unified_system", "handlers.unified_system_handler"),
        ("project", "handlers.project_handler"),
        ("me", "handlers.me_handler"),
        ("monitor", "handlers.monitor_handler"),
        ("journal", "handlers.journal_handler"),
        ("endday", "handlers.endday_handler"),
        ("brief", "handlers.brief_handler"),
        ("claim", "handlers.claim_handler"),
        ("slh_deposit", "handlers.slh_deposit_handler"),
        ("morning", "handlers.morning_handler"),
        ("morning_check", "handlers.morning_check_handler"),
        ("ownership_transfer", "handlers.ownership_transfer_handler"),
        ("repeat", "handlers.repeat_handler"),
        ("system", "handlers.system_handler"),
        ("progress", "handlers.progress_handler"),
        ("health_monitor", "handlers.health_monitor_handler"),
        ("exec_log", "handlers.exec_log_handler"),
        ("snapshot", "handlers.snapshot_handler"),
        ("user", "handlers.user_handler"),
        ("services", "handlers.services_handler"),
        ("voting", "handlers.ai_voting_handler"),
        ("governance", "handlers.governance_canonical_handler"),
        ("broadcast", "handlers.broadcast_handler"),
        ("firewall", "handlers.firewall_handler"),
        ("staking", "handlers.staking_handler"),
        ("staking_revenue", "handlers.staking_revenue_handler"),
        ("dev", "handlers.dev_handler"),
        ("dev_admin", "handlers.dev_admin"),
        ("developer_access", "handlers.developer_access_handler"),
        ("ux", "handlers.ux_handler"),
        ("admin", "admin_handler"),
        ("admin_extras", "handlers.admin_extras"),
        ("askdebug", "handlers.askdebug_handler"),
        ("exec", "handlers.exec_handler"),
        ("exec_request", "handlers.exec_request_handler"),
        ("recovery", "handlers.recovery_handler"),
        ("recovery_verify", "handlers.recovery_verify_handler"),
        ("cleanup", "handlers.cleanup_handler"),
        ("autoexec", "handlers.autoexec_handler"),
        ("airdrop", "handlers.airdrop_handler"),
        ("slh_air", "handlers.slh_air_handler"),
        ("git", "handlers.git_handler"),
        ("ton", "ton_handler"),
        ("brief_legacy", "brief_handler"),
        ("complete", "complete_handler"),
        ("diagnostic", "diagnostic_handler"),
        ("guide", "guide_handler"),
        ("junk", "junk_handler"),
        ("bug", "handlers.bug_handler"),
        ("roadmap", "roadmap_handler"),
        ("sandbox", "sandbox_handler"),
        ("test", "test_handler"),
        ("tutorial", "tutorial_handler"),
        ("viewfile", "viewfile_handler"),
        ("devsetup", "devsetup_handler"),
        ("refresh", "refresh_token_handler"),
    ]

    import importlib
    import inspect

    for name, mod_path in modules:
        try:
            m = importlib.import_module(mod_path)
            if hasattr(m, "register"):
                fn = m.register
                params = inspect.signature(fn).parameters
                if len(params) >= 2:
                    fn(bot, context)
                else:
                    fn(bot)
            elif hasattr(m, "register_llm_handler"):
                m.register_llm_handler(bot)
            elif hasattr(m, "register_help"):
                m.register_help(bot)
            elif hasattr(m, "register_repeat_handler"):
                m.register_repeat_handler(bot)
            elif hasattr(m, "init"):
                m.init(bot)
            elif hasattr(m, "register_learning_path"):
                m.register_learning_path(bot)
            elif hasattr(m, "register_handlers"):
                m.register_handlers(bot, context)
            else:
                raise Exception("No supported register function")
            print(f"✅ {name} loaded")
        except Exception as e:
            print(f"⚠️ {name} skipped:", str(e)[:120])

    try:
        from doctor_handler import register_doctor_handlers
        register_doctor_handlers(bot)
        print("✅ doctor loaded")
    except Exception as e:
        print("doctor skipped:", e)
    try:
        from language_handler import register_language
        register_language(bot)
        print("✅ language loaded")
    except Exception as e:
        print("language skipped:", e)
    try:
        from handlers.esp_handler import register_esp_handler
        register_esp_handler(bot)
        print("📡 esp loaded")
    except Exception as e:
        print("esp skipped:", e)
    try:
        from handlers.advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("🧠 advanced ask loaded")
    except Exception as e:
        print("ask skipped:", e)
    try:
        from handlers.natural_chat import register as register_natural_chat
        register_natural_chat(bot)
        print("💬 natural chat loaded")
    except Exception as e:
        print("natural chat skipped:", e)
    try:
        from store.fulfillment_recovery import recover_paid_orders, reconcile_telegram_stars
        stars = reconcile_telegram_stars()
        if stars.get("attempted"):
            print("[STARS] startup reconciliation:", stars)
        recovery = recover_paid_orders()
        print("[FULFILLMENT] startup recovery:", recovery)
        from store.fulfillment_recovery import start_recovery_loop
        start_recovery_loop()
    except Exception as e:
        print("[FULFILLMENT] recovery skipped:", type(e).__name__)

    try:
        from core.card_payment_service import start_card_recovery_loop
        start_card_recovery_loop()
        print("[CARD] automatic payment recovery loop started")
    except Exception as e:
        print("[CARD] recovery loop skipped:", type(e).__name__)

    print("✅ ALL HANDLERS READY")
