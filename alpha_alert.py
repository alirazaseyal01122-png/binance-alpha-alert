import os
import json
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALPHA_URL = "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"

STATE_FILE = "alpha_tokens.json"


def get_alpha_tokens():
    response = requests.get(ALPHA_URL, timeout=30)
    response.raise_for_status()

    result = response.json()

    if result.get("code") != "000000":
        raise Exception(f"Binance API Error: {result}")

    return result.get("data", [])


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    response.raise_for_status()


def load_old_tokens():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_tokens(tokens):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def format_listing_time(timestamp):
    if not timestamp:
        return "N/A"

    try:
        dt_utc = datetime.fromtimestamp(
            int(timestamp) / 1000,
            tz=timezone.utc
        )

        pkt = dt_utc.astimezone(
            timezone(timedelta(hours=5))
        )

        return pkt.strftime("%d-%m-%Y %I:%M:%S %p PKT")

    except Exception:
        return str(timestamp)


def main():
    if not BOT_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN missing")

    if not CHAT_ID:
        raise Exception("TELEGRAM_CHAT_ID missing")

    tokens = get_alpha_tokens()
    old_tokens = load_old_tokens()

    current_tokens = {}

    for token in tokens:
        alpha_id = token.get("alphaId")

        if alpha_id:
            current_tokens[alpha_id] = token

    print("Current Alpha tokens:", len(current_tokens))

    # پہلی دفعہ: موجودہ ٹوکن محفوظ کریں، الرٹ نہ بھیجیں
    if not old_tokens:
        save_tokens(current_tokens)

        print("Initial token database created.")
        return

    # صرف نئے ٹوکن تلاش کریں
    new_tokens = []

    for alpha_id, token in current_tokens.items():
        if alpha_id not in old_tokens:
            new_tokens.append(token)

    print("New tokens found:", len(new_tokens))

    # صرف نئے ٹوکن کا Telegram الرٹ
    for token in new_tokens:
        symbol = token.get("symbol", "N/A")
        alpha_id = token.get("alphaId", "N/A")
        chain = token.get("chainName", "N/A")
        contract = token.get("contractAddress", "N/A")
        listing_time = format_listing_time(
            token.get("listingTime")
        )

        message = (
            "🚨 NEW BINANCE ALPHA TOKEN\n\n"
            f"Token: {symbol}\n"
            f"Alpha ID: {alpha_id}\n"
            f"Network: {chain}\n"
            f"Contract: {contract}\n"
            f"Listing Time: {listing_time}"
        )

        send_telegram(message)

    # نئی فہرست محفوظ کریں
    save_tokens(current_tokens)

    print("Monitor completed successfully.")


if __name__ == "__main__":
    main()
