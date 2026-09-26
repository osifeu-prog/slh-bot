"""Owner-declared BotFather inventory used to bootstrap SLH federation metadata.

These are declarations only. They do not prove liveness, source ownership,
Railway health, or Telegram token validity. A later heartbeat is required for
a bot to become HEALTHY.
"""

BOTFATHER_DECLARED = [
    "@SLH_AIR_bot",
    "@Slh_edu_Academia_bot",
    "@Tzvikas_BC_bot",
    "@Me_ad_main_bot",
    "@Staging_Token_bot",
    "@OsifAdmin_bot",
    "@Tax_Free_world_bot",
    "@SLH_investor_wallet_bot",
    "@slh_love_bot",
    "@Free_Eco_bot",
    "@SLH_Love_WALLE_bot",
    "@SLH_Supervisor_bot",
    "@Osifswork_BOT",
    "@SLH_Test_bot",
    "@WEWORK_teamviwer_bot",
    "@SLH_Spark_AI_BOT",
    "@SLH_Ledger_bot",
    "@SLH_ton_bot",
    "@SLH_Wallet_bot",
    "@ts_set_bot",
    "@Grdian_bot",
    "@Campaign_SLH_bot",
    "@Chance_Pais_bot",
    "@SLH_community_bot",
    "@SLH_Academia_bot",
    "@Buy_My_Shop_bot",
    "@MY_SUPER_ADMIN_bot",
    "@NIFTI_Publisher_Bot",
    "@Osifs_Factory_bot",
    "@G4meb0t_bot_bot",
    "@OsifShop_bot",
    "@MY_NFT_SHOP_bot",
    "@My_crazy_panel_bot",
    "@NFTY_madness_bot",
]


def normalized_username(username: str) -> str:
    value = str(username or "").strip()
    return value if value.startswith("@") else "@" + value
