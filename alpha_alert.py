
import os
import json
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALPHA_URL = (
    "https://www.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/cex/alpha/all/token/list"
)

STATE_FILE = "alpha_tokens.json"


def get_alpha_tokens():
    response = requests.get(
        ALPHA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

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
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {}


def save_tokens(tokens):

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            tokens,
            f,
            ensure_ascii=False,
            indent=2
        )


def pakistan_time(timestamp):

    if not timestamp:
        return "N/A"

    try:

        # Binance timestamp = milliseconds
        utc_time = datetime.fromtimestamp(
            int(timestamp) / 1000,
            tz=timezone.utc
        )

        # Pakistan = UTC + 5
        pkt = utc_time.astimezone(
            timezone(timedelta(hours=5))
        )

        return pkt.strftime(
            "%d-%m-%Y %I:%M:%S %p PKT"
        )

    except Exception:

        return str(timestamp)


def main():

    if not BOT_TOKEN:
        raise Exception(
            "TELEGRAM_BOT_TOKEN missing"
        )

    if not CHAT_ID:
        raise Exception(
            "TELEGRAM_CHAT_ID missing"
        )

    tokens = get_alpha_tokens()

    old_tokens = load_old_tokens()

    current_tokens = {}

    for token in tokens:

        alpha_id = token.get("alphaId")

        if alpha_id:

            current_tokens[alpha_id] = token


    print(
        "Current Alpha tokens:",
        len(current_tokens)
    )


    # پہلی دفعہ Bot چلنے پر
    # موجودہ Tokens صرف محفوظ ہوں گے
    if not old_tokens:

        save_tokens(current_tokens)

        send_telegram(
            "✅ Binance Alpha Monitor Started\n\n"
            f"Current Alpha tokens recorded: "
            f"{len(current_tokens)}\n\n"
            "🚨 From now on, you will receive "
            "an alert only when a NEW Binance "
            "Alpha token appears."
        )

        return


    # نئے Alpha Tokens تلاش کریں

    new_tokens = []

    for alpha_id, token in current_tokens.items():

        if alpha_id not in old_tokens:

            new_tokens.append(token)


    print(
        "New Alpha tokens:",
        len(new_tokens)
    )


    # نئے Tokens کے Alerts

    for token in new_tokens:

        symbol = token.get(
            "symbol",
            "N/A"
        )

        name = token.get(
            "name",
            "N/A"
        )

        alpha_id = token.get(
            "alphaId",
            "N/A"
        )

        chain = token.get(
            "chainName",
            "N/A"
        )

        contract = token.get(
            "contractAddress",
            "N/A"
        )

        listing_time = pakistan_time(
            token.get("listingTime")
        )


        message = (
            "🚨 NEW BINANCE ALPHA TOKEN\n\n"

            f"🪙 Name: {name}\n"
            f"🔹 Symbol: {symbol}\n"
            f"🆔 Alpha ID: {alpha_id}\n"
            f"🌐 Network: {chain}\n\n"

            f"📜 Contract:\n"
            f"{contract}\n\n"

            f"🇵🇰 Listing Time:\n"
            f"{listing_time}\n\n"

            "⚡ Binance Alpha Monitor"
        )


        send_telegram(message)

        print(
            "Telegram alert sent:",
            alpha_id
        )


    # نئی فہرست محفوظ کریں

    save_tokens(current_tokens)

    print(
        "Alpha database updated successfully."
    )


if __name__ == "__main__":
    main()
