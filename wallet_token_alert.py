import os
import json
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Binance Web3 Unified Token Rank
BINANCE_WEB3_URL = (
    "https://web3.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/market/token/pulse/"
    "unified/rank/list/ai"
)

STATE_FILE = "wallet_tokens.json"

# Binance Web3 currently documented chains
CHAINS = {
    "56": "BSC",
    "1": "Ethereum",
    "8453": "Base",
    "CT_501": "Solana"
}


def get_wallet_tokens(chain_id):

    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "binance-web3/3.0"
    }

    payload = {
        "rankType": 10,
        "chainId": chain_id,
        "period": 10,
        "sortBy": 10,
        "orderAsc": False,
        "page": 1,
        "size": 200,

        # نئے / تازہ ٹوکنز کو ترجیح
        "launchTimeMin": 0,

        # بہت کم liquidity والے spam tokens کو
        # ابھی filter نہیں کر رہے
        # تاکہ نئے tokens miss نہ ہوں
    }

    response = requests.post(
        BINANCE_WEB3_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if result.get("code") != "000000":
        raise Exception(
            f"Binance Web3 API Error: {result}"
        )

    data = result.get("data") or {}

    return data.get("tokens", [])


def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

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

        utc_time = datetime.fromtimestamp(
            int(timestamp) / 1000,
            tz=timezone.utc
        )

        pkt = utc_time.astimezone(
            timezone(timedelta(hours=5))
        )

        return pkt.strftime(
            "%d-%m-%Y %I:%M:%S %p PKT"
        )

    except Exception:

        return str(timestamp)


def safe_number(value):

    if value is None:
        return "N/A"

    try:

        number = float(value)

        if number >= 1_000_000_000:
            return f"${number / 1_000_000_000:.2f}B"

        if number >= 1_000_000:
            return f"${number / 1_000_000:.2f}M"

        if number >= 1_000:
            return f"${number / 1_000:.2f}K"

        return f"${number:.6f}"

    except Exception:

        return str(value)


def main():

    if not BOT_TOKEN:
        raise Exception(
            "TELEGRAM_BOT_TOKEN missing"
        )

    if not CHAT_ID:
        raise Exception(
            "TELEGRAM_CHAT_ID missing"
        )

    old_tokens = load_old_tokens()

    current_tokens = {}

    total_found = 0

    for chain_id, chain_name in CHAINS.items():

        try:

            tokens = get_wallet_tokens(
                chain_id
            )

            print(
                f"{chain_name}: "
                f"{len(tokens)} tokens received"
            )

            total_found += len(tokens)

            for token in tokens:

                contract = token.get(
                    "contractAddress"
                )

                if not contract:
                    continue

                # Chain + contract = unique ID
                token_key = (
                    f"{chain_id}:"
                    f"{contract.lower()}"
                )

                current_tokens[token_key] = {
                    "chainId": chain_id,
                    "chainName": chain_name,
                    "contractAddress": contract,
                    "symbol": token.get(
                        "symbol",
                        "N/A"
                    ),
                    "price": token.get(
                        "price"
                    ),
                    "marketCap": token.get(
                        "marketCap"
                    ),
                    "liquidity": token.get(
                        "liquidity"
                    ),
                    "holders": token.get(
                        "holders"
                    ),
                    "launchTime": token.get(
                        "launchTime"
                    ),
                    "volume1m": token.get(
                        "volume1m"
                    ),
                    "volume5m": token.get(
                        "volume5m"
                    ),
                    "volume24h": token.get(
                        "volume24h"
                    )
                }

        except Exception as e:

            print(
                f"ERROR {chain_name}: {e}"
            )

    print(
        "Total tokens received:",
        total_found
    )

    print(
        "Unique tokens:",
        len(current_tokens)
    )

    # پہلی مرتبہ Bot چلنے پر
    if not old_tokens:

        save_tokens(current_tokens)

        send_telegram(
            "✅ Binance Web3 Wallet Monitor Started\n\n"
            f"🌐 Chains monitored: "
            f"{len(CHAINS)}\n"
            f"🪙 Tokens recorded: "
            f"{len(current_tokens)}\n\n"
            "🚨 From now on, Telegram alerts "
            "will be sent when a NEW Binance "
            "Web3 token is detected."
        )

        return

    # نئے tokens
    new_tokens = []

    for token_key, token in current_tokens.items():

        if token_key not in old_tokens:

            new_tokens.append(token)

    print(
        "New Wallet/Web3 tokens:",
        len(new_tokens)
    )

    # Telegram alerts
    for token in new_tokens:

        symbol = token.get(
            "symbol",
            "N/A"
        )

        chain_name = token.get(
            "chainName",
            "N/A"
        )

        contract = token.get(
            "contractAddress",
            "N/A"
        )

        price = safe_number(
            token.get("price")
        )

        market_cap = safe_number(
            token.get("marketCap")
        )

        liquidity = safe_number(
            token.get("liquidity")
        )

        volume_24h = safe_number(
            token.get("volume24h")
        )

        holders = token.get(
            "holders",
            "N/A"
        )

        launch_time = pakistan_time(
            token.get("launchTime")
        )

        message = (
            "🚨 NEW BINANCE WEB3 TOKEN\n\n"

            f"🪙 Symbol: {symbol}\n"
            f"⛓️ Chain: {chain_name}\n\n"

            f"💵 Price: {price}\n"
            f"💧 Liquidity: {liquidity}\n"
            f"📊 Market Cap: {market_cap}\n"
            f"📈 24h Volume: {volume_24h}\n"
            f"👥 Holders: {holders}\n\n"

            f"⏰ Launch Time:\n"
            f"{launch_time}\n\n"

            f"📜 Contract:\n"
            f"{contract}\n\n"

            "⚡ Binance Web3 Wallet Monitor"
        )

        try:

            send_telegram(message)

            print(
                "Telegram alert sent:",
                symbol,
                chain_name,
                contract
            )

        except Exception as e:

            print(
                "Telegram error:",
                e
            )

    save_tokens(current_tokens)

    print(
        "Wallet token database updated."
    )


if __name__ == "__main__":
    main()
