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

# Binance Web3 Dynamic Token Info
BINANCE_DYNAMIC_URL = (
    "https://web3.binance.com/bapi/defi/v4/public/"
    "wallet-direct/buw/wallet/market/token/dynamic/info"
)

STATE_FILE = "wallet_tokens.json"

# صرف 500 ملین سے کم Total Supply والے ٹوکن
MAX_SUPPLY = 500_000_000

# Binance Web3 chains
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
        "launchTimeMin": 0
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


def get_token_dynamic(chain_id, contract_address):

    headers = {
        "Accept-Encoding": "identity",
        "User-Agent": "binance-web3/3.0"
    }

    params = {
        "chainId": chain_id,
        "contractAddress": contract_address
    }

    response = requests.get(
        BINANCE_DYNAMIC_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    if result.get("code") != "000000":
        raise Exception(
            f"Binance Dynamic API Error: {result}"
        )

    return result.get("data") or {}


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

        timestamp = float(timestamp)

        # اگر timestamp seconds میں ہو
        if timestamp < 10_000_000_000:
            timestamp = timestamp * 1000

        utc_time = datetime.fromtimestamp(
            timestamp / 1000,
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


def safe_supply(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.replace(",", "").strip()

        return float(value)

    except Exception:

        return None


def format_supply(value):

    if value is None:
        return "N/A"

    try:

        number = float(value)

        if number >= 1_000_000_000:
            return f"{number / 1_000_000_000:.2f}B"

        if number >= 1_000_000:
            return f"{number / 1_000_000:.2f}M"

        if number >= 1_000:
            return f"{number / 1_000:.2f}K"

        return f"{number:.2f}"

    except Exception:

        return str(value)


def get_value(data, *keys):

    for key in keys:

        value = data.get(key)

        if value is not None:
            return value

    return None


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
            "🟢 Supply Filter: BELOW 500M\n\n"
            "🚨 From now on, Telegram alerts "
            "will be sent only for NEW Web3 "
            "tokens with Total Supply below "
            "500 million."
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

    # نئے tokens کی Supply چیک کریں
    for token in new_tokens:

        symbol = token.get(
            "symbol",
            "N/A"
        )

        chain_name = token.get(
            "chainName",
            "N/A"
        )

        chain_id = token.get(
            "chainId"
        )

        contract = token.get(
            "contractAddress",
            "N/A"
        )

        try:

            dynamic = get_token_dynamic(
                chain_id,
                contract
            )

            total_supply = safe_supply(
                get_value(
                    dynamic,
                    "totalSupply",
                    "total_supply"
                )
            )

            circulating_supply = safe_supply(
                get_value(
                    dynamic,
                    "circulatingSupply",
                    "circulating_supply"
                )
            )

            print(
                f"{symbol} | "
                f"{chain_name} | "
                f"Total Supply: "
                f"{total_supply}"
            )

            # Supply نہ ملے تو الرٹ نہیں
            if total_supply is None:

                print(
                    "Supply unavailable - skipped:",
                    symbol,
                    chain_name
                )

                continue

            # 500 Million یا زیادہ = SKIP
            if total_supply >= MAX_SUPPLY:

                print(
                    "Supply filter rejected:",
                    symbol,
                    format_supply(total_supply)
                )

                continue

            price = safe_number(
                get_value(
                    dynamic,
                    "price"
                )
                or token.get("price")
            )

            market_cap = safe_number(
                get_value(
                    dynamic,
                    "marketCap",
                    "market_cap"
                )
                or token.get("marketCap")
            )

            liquidity = safe_number(
                get_value(
                    dynamic,
                    "liquidity"
                )
                or token.get("liquidity")
            )

            volume_24h = safe_number(
                get_value(
                    dynamic,
                    "volume24h",
                    "volume_24h"
                )
                or token.get("volume24h")
            )

            holders = get_value(
                dynamic,
                "holders",
                "holderCount"
            )

            if holders is None:
                holders = token.get(
                    "holders",
                    "N/A"
                )

            launch_time_value = get_value(
                dynamic,
                "launchTime",
                "launch_time"
            )

            if launch_time_value is None:
                launch_time_value = token.get(
                    "launchTime"
                )

            launch_time = pakistan_time(
                launch_time_value
            )

            message = (
                "🟢 NEW BINANCE WEB3 TOKEN\n\n"

                f"🪙 Symbol: {symbol}\n"
                f"⛓️ Chain: {chain_name}\n\n"

                f"📦 Total Supply: "
                f"{format_supply(total_supply)}\n"

                f"🔄 Circulating Supply: "
                f"{format_supply(circulating_supply)}\n\n"

                f"💵 Price: {price}\n"
                f"💧 Liquidity: {liquidity}\n"
                f"📊 Market Cap: {market_cap}\n"
                f"📈 24h Volume: {volume_24h}\n"
                f"👥 Holders: {holders}\n\n"

                f"⏰ Launch Time:\n"
                f"{launch_time}\n\n"

                f"📜 Contract:\n"
                f"{contract}\n\n"

                "🟢 Supply < 500M\n"
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

        except Exception as e:

            print(
                "Supply check error:",
                symbol,
                chain_name,
                e
            )

    # Database update
    save_tokens(current_tokens)

    print(
        "Wallet token database updated."
    )


if __name__ == "__main__":
    main()
