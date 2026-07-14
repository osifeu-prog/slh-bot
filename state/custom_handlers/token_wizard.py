import json

WIZARD_STEPS = {
    "start": (
        "🧙 Welcome to the SLH Token Wizard!\n\n"
        "I'll guide you through setting up your wallet and interacting with the SLH token.\n"
        "Reply with the number of the step you want, or type /token_wizard again to restart.\n\n"
        "1️⃣ What is SLH?\n"
        "2️⃣ Create a wallet (MetaMask)\n"
        "3️⃣ Add BSC network\n"
        "4️⃣ Get testnet BNB\n"
        "5️⃣ Add SLH token to wallet\n"
        "6️⃣ Buy / Send SLH"
    ),
    "1": "📘 SLH is the native token...\nTotal supply: 111,186.33 SLH.\nContract: BSC Testnet.\n\nType /token_wizard to go back.",
    "2": "🦊 Create a MetaMask wallet:\n1. Install MetaMask...\n\nType /token_wizard to return.",
    "3": "🌐 Add BSC Testnet to MetaMask:\n• RPC: https://data-seed-prebsc-1-s1.binance.org:8545/\n• Chain ID: 97\n\nType /token_wizard to return.",
    "4": "💧 Get testnet BNB from https://testnet.binance.org/faucet-smart\n\nType /token_wizard to return.",
    "5": "➕ Add SLH token to MetaMask:\nContract address (provided later), Symbol: SLH, Decimals: 18.\n\nType /token_wizard to return.",
    "6": "💸 Earn SLH by completing courses (/progress), staking (/stake_join), or receiving via /token send.\n\nType /token_wizard to return.",
}

def register(bot):
    @bot.message_handler(commands=['token_wizard'])
    def wizard(msg):
        args = msg.text.split()
        step = args[1] if len(args) > 1 else "start"
        if step in WIZARD_STEPS:
            bot.send_message(msg.chat.id, WIZARD_STEPS[step])
        else:
            bot.send_message(msg.chat.id, "Step not found. Type /token_wizard to see the menu.")
