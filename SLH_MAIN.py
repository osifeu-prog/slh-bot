from SLH_GATEWAY import SLHGateway
from SLH_BOT_ADAPTER import SLHBotAdapter


def main():
    print("🚀 SLH SYSTEM START")

    gateway = SLHGateway()
    bot = SLHBotAdapter(gateway)

    try:
        bot.chat()
    except KeyboardInterrupt:
        print("\n🛑 SYSTEM STOPPED")


if __name__ == "__main__":
    main()
