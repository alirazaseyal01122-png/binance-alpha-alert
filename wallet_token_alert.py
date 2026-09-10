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

# ==============================
# سخت فلٹرز
# ==============================

MAX_SUPPLY = 500_000_000

MIN_LIQUIDITY = 100_000

MIN_MARKET_CAP = 500_000

MIN_HOLDERS = 100

MIN_VOLUME_24H = 50_000

# صرف گزشتہ 24 گھنٹوں میں لانچ ہونے والے ٹوکن
MAX_TOKEN_AGE_HOURS = 24


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


def safe_number(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()

        return float(value)

    except Exception:

        return None


def format_money(value):

    number = safe_number(value)

    if number is None:
        return "N/A"

    if number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"

    if number >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"

    if number >= 1_000:
        return f"${number / 1_000:.2f}K"

    return f"${number:.6f}"


def get_value(data, *keys):

    for key in keys:

        value = data.get(key)

        if value is not None:
            return value

    return None


def parse_timestamp(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.strip()

            # اگر string numeric ہے
            if value.replace(".", "", 1).isdigit():
                value = float(value)

            else:
                # ISO format
                text = value.replace("Z", "+00:00")

                dt = datetime.fromisoformat(text)

                if dt.tzinfo is None:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

                return dt

        if isinstance(value, (int, float)):

            timestamp = float(value)

            # milliseconds
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000

            return datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            )

    except Exception:

        return None

    return None


def pakistan_time(value):

    dt = parse_timestamp(value)

    if dt is None:
        return "N/A"

    pkt = dt.astimezone(
        timezone(timedelta(hours=5))
    )

    return pkt.strftime(
        "%d-%m-%Y %I:%M:%S %p PKT"
    )


def token_age_hours(value):

    dt = parse_timestamp(value)

    if dt is None:
        return None

    now = datetime.now(timezone.utc)

    age = (
        now - dt
    ).total_seconds() / 3600

    return age


def is_recent_launch(value):

    age = token_age_hours(value)

    if age is None:
        return False

    # مستقبل کی غلط timestamp کو بھی قبول نہیں کریں گے
    if age < 0:
        return False

    return age <= MAX_TOKEN_AGE_HOURS


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

    # ==============================
    # Binance Web3 سے موجودہ ٹوکنز
    # ==============================

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

    # ==========================================
    # پہلی مرتبہ بوٹ چلنے پر
    # موجودہ پرانے ٹوکن صرف محفوظ ہوں گے
    # ==========================================

    if not old_tokens:

        save_tokens(current_tokens)

        send_telegram(
            "✅ Binance Web3 Wallet Monitor Started\n\n"
            f"🌐 Chains monitored: {len(CHAINS)}\n"
            f"🪙 Existing tokens recorded: "
            f"{len(current_tokens)}\n\n"

            "🔒 Filters enabled:\n"
            "• Launch age ≤ 24 hours\n"
            "• Total Supply < 500M\n"
            "• Liquidity ≥ $100K\n"
            "• Market Cap ≥ $500K\n"
            "• Holders ≥ 100\n"
            "• 24h Volume ≥ $50K\n\n"

            "🚨 Existing old tokens will NOT be alerted."
        )

        return

    # ==========================================
    # صرف نئے tokens
    # ==========================================

    new_tokens = []

    for token_key, token in current_tokens.items():

        if token_key not in old_tokens:

            new_tokens.append(token)

    print(
        "New Wallet/Web3 tokens:",
        len(new_tokens)
    )

    # ==========================================
    # ہر نئے ٹوکن کی مکمل جانچ
    # ==========================================

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

            # Binance Dynamic API
            dynamic = get_token_dynamic(
                chain_id,
                contract
            )

            # ------------------------------
            # Launch Time
            # ------------------------------

            launch_time_value = get_value(
                dynamic,
                "launchTime",
                "launch_time"
            )

            if launch_time_value is None:

                launch_time_value = token.get(
                    "launchTime"
                )

            print(
                f"{symbol} | "
                f"{chain_name} | "
                f"Launch: "
                f"{pakistan_time(launch_time_value)}"
            )

            # ------------------------------
            # 24 Hour Launch Filter
            # ------------------------------

            age = token_age_hours(
                launch_time_value
            )

            if age is None:

                print(
                    "SKIPPED - Launch time unavailable:",
                    symbol
                )

                continue

            if age < 0:

                print(
                    "SKIPPED - Future launch time:",
                    symbol
                )

                continue

            if age > MAX_TOKEN_AGE_HOURS:

                print(
                    "SKIPPED - Old token:",
                    symbol,
                    f"{age:.2f} hours old"
                )

                continue

            # ------------------------------
            # Total Supply
            # ------------------------------

            total_supply = safe_supply(
                get_value(
                    dynamic,
                    "totalSupply",
                    "total_supply"
                )
            )

            if total_supply is None:

                print(
                    "SKIPPED - Supply unavailable:",
                    symbol
                )

                continue

            if total_supply >= MAX_SUPPLY:

                print(
                    "SKIPPED - Supply too high:",
                    symbol,
                    format_supply(total_supply)
                )

                continue

            # ------------------------------
            # Circulating Supply
            # ------------------------------

            circulating_supply = safe_supply(
                get_value(
                    dynamic,
                    "circulatingSupply",
                    "circulating_supply"
                )
            )

            # ------------------------------
            # Liquidity
            # ------------------------------

            liquidity = safe_number(
                get_value(
                    dynamic,
                    "liquidity"
                )
                or token.get("liquidity")
            )

            if liquidity is None:

                print(
                    "SKIPPED - Liquidity unavailable:",
                    symbol
                )

                continue

            if liquidity < MIN_LIQUIDITY:

                print(
                    "SKIPPED - Liquidity too low:",
                    symbol,
                    liquidity
                )

                continue

            # ------------------------------
            # Market Cap
            # ------------------------------

            market_cap = safe_number(
                get_value(
                    dynamic,
                    "marketCap",
                    "market_cap"
                )
                or token.get("marketCap")
            )

            if market_cap is None:

                print(
                    "SKIPPED - Market Cap unavailable:",
                    symbol
                )

                continue

            if market_cap < MIN_MARKET_CAP:

                print(
                    "SKIPPED - Market Cap too low:",
                    symbol,
                    market_cap
                )

                continue

            # ------------------------------
            # Holders
            # ------------------------------

            holders = get_value(
                dynamic,
                "holders",
                "holderCount"
            )

            if holders is None:

                holders = token.get(
                    "holders"
                )

            holders_number = safe_number(
                holders
            )

            if holders_number is None:

                print(
                    "SKIPPED - Holders unavailable:",
                    symbol
                )

                continue

            if holders_number < MIN_HOLDERS:

                print(
                    "SKIPPED - Too few holders:",
                    symbol,
                    holders_number
                )

                continue

            # ------------------------------
            # 24h Volume
            # ------------------------------

            volume_24h = safe_number(
                get_value(
                    dynamic,
                    "volume24h",
                    "volume_24h"
                )
                or token.get("volume24h")
            )

            if volume_24h is None:

                print(
                    "SKIPPED - 24h volume unavailable:",
                    symbol
                )

                continue

            if volume_24h < MIN_VOLUME_24H:

                print(
                    "SKIPPED - Volume too low:",
                    symbol,
                    volume_24h
                )

                continue

            # ------------------------------
            # Price
            # ------------------------------

            price = get_value(
                dynamic,
                "price"
            )

            if price is None:
                price = token.get(
                    "price"
                )

            # ------------------------------
            # سب فلٹر پاس
            # ------------------------------

            launch_age_text = (
                f"{age:.1f} hours ago"
            )

            message = (
                "🟢 NEW QUALIFIED BINANCE WEB3 TOKEN\n\n"

                f"🪙 Symbol: {symbol}\n"
                f"⛓️ Chain: {chain_name}\n\n"

                f"📦 Total Supply: "
                f"{format_supply(total_supply)}\n"

                f"🔄 Circulating Supply: "
                f"{format_supply(circulating_supply)}\n\n"

                f"💵 Price: {format_money(price)}\n"
                f"💧 Liquidity: {format_money(liquidity)}\n"
                f"📊 Market Cap: {format_money(market_cap)}\n"
                f"📈 24h Volume: {format_money(volume_24h)}\n"
                f"👥 Holders: {int(holders_number)}\n\n"

                f"⏰ Launch Time:\n"
                f"{pakistan_time(launch_time_value)}\n"
                f"🕐 Age: {launch_age_text}\n\n"

                f"📜 Contract:\n"
                f"{contract}\n\n"

                "✅ Supply < 500M\n"
                "✅ Liquidity ≥ $100K\n"
                "✅ Market Cap ≥ $500K\n"
                "✅ Holders ≥ 100\n"
                "✅ 24h Volume ≥ $50K\n"
                "✅ Launch ≤ 24 hours\n\n"

                "⚠️ Filtered candidate — "
                "not a guarantee of profit or safety."
            )

            try:

                send_telegram(
                    message
                )

                print(
                    "QUALIFIED ALERT SENT:",
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
                "Token check error:",
                symbol,
                chain_name,
                e
            )

    # ==========================================
    # Database Update
    # ==========================================

    save_tokens(
        current_tokens
    )

    print(
        "Wallet token database updated."
    )


if __name__ == "__main__":
    main()
