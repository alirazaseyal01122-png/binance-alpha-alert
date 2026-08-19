
import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALPHA_URL = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


def get_alpha_tokens():
    response = requests.get(ALPHA_URL, timeout=20)
    response.raise_for_status()

    result = response.json()

    if result.get("code") != "000000":
        raise Exception(f"Binance API error: {result}")

    return result.get("data", [])


tokens = get_alpha_tokens()

print(f"Binance Alpha tokens found: {len(tokens)}")

for token in tokens[:10]:
    print(
        token.get("alphaId"),
        token.get("chainName"),
        token.get("contractAddress")
    )

send_telegram(
    f"✅ Binance Alpha connection successful!\n\n"
    f"Current Alpha tokens detected: {len(tokens)}"
    )
