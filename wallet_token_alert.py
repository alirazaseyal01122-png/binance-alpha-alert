```python
import os
import json
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BINANCE_WEB3_URL = (
    "https://web3.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/market/token/pulse/"
    "unified/rank/list/ai"
)

BINANCE_DYNAMIC_URL = (
    "https://web3.binance.com/bapi/defi/v4/public/"
    "wallet-direct/buw/wallet/market/token/dynamic/info"
)

STATE_FILE = "wallet_tokens.json"

# ==============================
# فلٹرز
# ==============================

MAX_SUPPLY = 500_000_000
MIN_LIQUIDITY = 100_000
MIN_MARKET_CAP = 500_000
MIN_HOLDERS = 100
MIN_VOLUME_24H = 50_000

# صرف گزشتہ 24 گھنٹوں میں لانچ ہونے والے ٹوکن
MAX_TOKEN_AGE_HOURS = 24

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


def get_value(data, *keys):

    for key in keys:

        value = data.get(key)

        if value is not None:
            return value

    return None


def safe_number(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):

            value = (
                value
                .replace(",", "")
                .replace("$", "")
                .strip()
            )

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


def format_supply(value):

    number = safe_number(value)

    if number is None:
        return "N/A"

    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.2f}B"

    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"

    if number >= 1_000:
        return f"{number / 1_000:.2f}K"

    return f"{number:.2f}"


def parse_timestamp(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):

            value = value.strip()

            if value.replace(".", "", 1).isdigit():
                value = float(value)

            else:

                text = value.replace(
                    "Z",
                    "+00:00"
                )

                dt = datetime.fromisoformat(text)

                if dt.tzinfo is None:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

                return dt

        if isinstance(value, (int, float)):

            timestamp = float(value)

            if timestamp > 10_000_000_000:
                timestamp /= 1000

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

    return (
        now - dt
    ).total_seconds() / 3600


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

    # =================================
    # Binance Web3 tokens حاصل کریں
    # =================================

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
                    "launchTime": token.get(
                        "launchTime"
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

    # =================================
    # پہلی مرتبہ چلنے پر
    # پرانے tokens محفوظ کریں
    # =================================

    if not old_tokens:

        save_tokens(
            current_tokens
        )

        send_telegram(
            "✅ Binance Web3 Wallet Monitor Started\n\n"
            f"🌐 Chains: {len(CHAINS)}\n"
            f"🪙 Existing tokens recorded: "
            f"{len(current_tokens)}\n\n"
            "🔒 Filters enabled:\n"
            "• Launch ≤ 24 hours\n"
            "• Supply < 500M\n"
            "• Liquidity ≥ $100K\n"
            "• Market Cap ≥ $500K\n"
            "• Holders ≥ 100\n"
            "• 24h Volume ≥ $50K\n\n"
            "🚨 Old tokens will NOT be alerted."
        )

        return

    # =================================
    # صرف نئے tokens
    # =================================

    new_tokens = []

    for token_key, token in current_tokens.items():

        if token_key not in old_tokens:

            new_tokens.append(token)

    print(
        "New Wallet/Web3 tokens:",
        len(new_tokens)
    )

    # =================================
    # ہر نئے token کی جانچ
    # =================================

    for token in new_tokens:

        symbol = token.get(
            "symbol",
            "N/A"
        )

        chain_id = token.get(
            "chainId"
        )

        chain_name = token.get(
            "chainName",
            "N/A"
        )

        contract = token.get(
            "contractAddress"
        )

        try:

            dynamic = get_token_dynamic(
                chain_id,
                contract
            )

            # =========================
            # Launch Time
            # =========================

            launch_time = get_value(
                dynamic,
                "launchTime",
                "launch_time"
            )

            if launch_time is None:

                launch_time = token.get(
                    "launchTime"
                )

            age = token_age_hours(
                launch_time
            )

            print(
                f"{symbol} | "
                f"{chain_name} | "
                f"Launch: "
                f"{pakistan_time(launch_time)}"
            )

            # Launch Time لازمی ہے
            if age is None:

                print(
                    "SKIPPED: launch time unavailable",
                    symbol
                )

                continue

            # مستقبل کی غلط تاریخ
            if age < 0:

                print(
                    "SKIPPED: future launch time",
                    symbol
                )

                continue

            # 24 گھنٹے سے پرانا
            if age > MAX_TOKEN_AGE_HOURS:

                print(
                    "SKIPPED: old token",
                    symbol,
                    f"{age:.2f} hours old"
                )

                continue

            # =========================
            # Total Supply
            # =========================

            total_supply = safe_number(
                get_value(
                    dynamic,
                    "totalSupply",
                    "total_supply"
                )
            )

            if total_supply is None:

                print(
                    "SKIPPED: supply unavailable",
                    symbol
                )

                continue

            if total_supply >= MAX_SUPPLY:

                print(
                    "SKIPPED: supply too high",
                    symbol
                )

                continue

            # =========================
            # Liquidity
            # =========================

            liquidity = safe_number(
                get_value(
                    dynamic,
                    "liquidity"
                )
            )

            if liquidity is None:

                liquidity = safe_number(
                    token.get("liquidity")
                )

            if liquidity is None:

                print(
                    "SKIPPED: liquidity unavailable",
                    symbol
                )

                continue

            if liquidity < MIN_LIQUIDITY:

                print(
                    "SKIPPED: liquidity too low",
                    symbol
                )

                continue

            # =========================
            # Market Cap
            # =========================

            market_cap = safe_number(
                get_value(
                    dynamic,
                    "marketCap",
                    "market_cap"
                )
            )

            if market_cap is None:

                market_cap = safe_number(
                    token.get("marketCap")
                )

            if market_cap is None:

                print(
                    "SKIPPED: market cap unavailable",
                    symbol
                )

                continue

            if market_cap < MIN_MARKET_CAP:

                print(
                    "SKIPPED: market cap too low",
                    symbol
                )

                continue

            # =========================
            # Holders
            # =========================

            holders = get_value(
                dynamic,
                "holders",
                "holderCount"
            )

            if holders is None:

                holders = token.get(
                    "holders"
                )

            holders = safe_number(
                holders
            )

            if holders is None:

                print(
                    "SKIPPED: holders unavailable",
                    symbol
                )

                continue

            if holders < MIN_HOLDERS:

                print(
                    "SKIPPED: holders too low",
                    symbol
                )

                continue

            # =========================
            # 24h Volume
            # =========================

            volume_24h = safe_number(
                get_value(
                    dynamic,
                    "volume24h",
                    "volume_24h"
                )
            )

            if volume_24h is None:

                volume_24h = safe_number(
                    token.get("volume24h")
                )

            if volume_24h is None:

                print(
                    "SKIPPED: volume unavailable",
                    symbol
                )

                continue

            if volume_24h < MIN_VOLUME_24H:

                print(
                    "SKIPPED: volume too low",
                    symbol
                )

                continue

            # =========================
            # Price
            # =========================

            price = get_value(
                dynamic,
                "price"
            )

            if price is None:
                price = token.get(
                    "price"
                )

            circulating_supply = safe_number(
                get_value(
                    dynamic,
                    "circulatingSupply",
                    "circulating_supply"
                )
            )

            # =========================
            # Telegram Alert
            # =========================

            message = (
                "🟢 NEW QUALIFIED BINANCE WEB3 TOKEN\n\n"

                f"🪙 Symbol: {symbol}\n"
                f"⛓️ Chain: {chain_name}\n\n"

                f"📦 Total Supply: "
                f"{format_supply(total_supply)}\n"

                f"🔄 Circulating Supply: "
                f"{format_supply(circulating_supply)}\n\n"

                f"💵 Price: {format_money(price)}\n"
                f"💧 Liquidity: "
                f"{format_money(liquidity)}\n"
                f"📊 Market Cap: "
                f"{format_money(market_cap)}\n"
                f"📈 24h Volume: "
                f"{format_money(volume_24h)}\n"
                f"👥 Holders: "
                f"{int(holders)}\n\n"

                f"⏰ Launch Time:\n"
                f"{pakistan_ti
                f"🕐 Age: "
                f"{age:.1f} hours\n\n"

                f"📜 Contract:\n"
                f"{contract}\n\n"

                "✅ Supply < 500M\n"
                "✅ Liquidity ≥ $100K\n"
                "✅ Market Cap ≥ $500K\n"
                "✅ Holders ≥ 100\n"
                "✅ 24h Volume ≥ $50K\n"
                "✅ Launch ≤ 24 hours\n\n"

                "⚠️ یہ فلٹر صرف ابتدائی چھان بین ہے، "
                "منافع یا حفاظت کی ضمانت نہیں۔"
            )

            try:

                send_telegram(
                    message
                )

                print(
                    "QUALIFIED ALERT SENT:",
                    symbol,
                    chain_name
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

    # =================================
    # Database update
    # =================================

    save_tokens(
        current_tokens
    )

    print(
        "Wallet token database updated."
    )


if __name__ == "__main__":
    main()
```
