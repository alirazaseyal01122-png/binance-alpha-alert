import os
import json
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALPHA_URL = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
DATA_FILE = "alpha_tokens.json"


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


def load_old_tokens():
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tokens(tokens):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


tokens = get_alpha_tokens()

old_tokens = load_old_tokens()

current_tokens = {}

for token in tokens:
    alpha_id = token.get("alphaId")

    if alpha_id:
        current_tokens[alpha_id] = token


new_tokens = [
    token
    for alpha_id, token in current_tokens.items()
    if alpha_id not in old_tokens
]


print("Current Alpha tokens:", len(current_tokens))
print("New Alpha tokens:", len(new_tokens))


for token in new_tokens:

    message = (
        "🚨 NEW BINANCE ALPHA TOKEN\n\n"
        f"Token: {token.get('symbol', 'N/A')}\n"
        f"Alpha ID: {token.get('alphaId', 'N/A')}\n"
        f"Network: {token.get('chainName', 'N/A')}\n"
        f"Contract: {token.get('contractAddress', 'N/A')}\n"
        f"Listing Time: {token.get('listingTime', 'N/A')}"
    )

    send_telegram(message)


save_tokens(current_tokens)

print("Alpha token database updated.")
