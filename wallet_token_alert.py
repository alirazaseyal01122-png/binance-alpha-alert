import os
import json
import requests
from datetime import datetime, timezone, timedelta


# =========================================================
# TELEGRAM SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")


# =========================================================
# BINANCE WEB3 API
# =========================================================

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


# =========================================================
# SETTINGS
# =========================================================

# نئے ٹوکن کی زیادہ سے زیادہ عمر
MAX_TOKEN_AGE_MINUTES = 10

# BNB/BSC کے لیے زیادہ سے زیادہ Total Supply
BNB_MAX_SUPPLY = 600_000_000


# =========================================================
# CHAINS
# =========================================================

# صرف Ethereum اور BNB/BSC
CHAINS = {
    "1": "Ethereum",
    "56": "BNB Chain"
}


# =========================================================
# TELEGRAM SEND
# =========================================================

def send_telegram(message):

    if not BOT_TOKEN:
        raise Exception("TELEGRAM_BOT_TOKEN missing")

    if not CHAT_ID:
        raise Exception("TELEGRAM_CHAT_ID missing")

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

    result = response.json()

    if not result.get("ok"):
        raise Exception(
            f"Telegram API Error: {result}"
        )

    return result


# =========================================================
# TELEGRAM TEST
# =========================================================

def telegram_test():

    print("========================================")
    print("TELEGRAM TEST STARTED")
    print("========================================")

    test_message = (
        "🧪 BINANCE WEB3 MONITOR TEST\n\n"
        "✅ GitHub Action: Working\n"
        "✅ Python: Working\n"
        "✅ Telegram Bot: Connected\n\n"
        "🌐 Ethereum + BNB Chain Monitor\n"
        "⏱️ New token age limit: 10 minutes\n"
        "🕐 Manual workflow test successful."
    )

    try:

        result = send_telegram(test_message)

        print(
            "TELEGRAM TEST MESSAGE SENT SUCCESSFULLY"
        )

        print(
            "Telegram response:",
            result
        )

    except Exception as e:

        print(
            "TELEGRAM TEST FAILED:",
            e
        )

        raise


# =========================================================
# BINANCE WEB3 TOKEN LIST
# =========================================================

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


# =========================================================
# TOKEN DYNAMIC INFO
# =========================================================

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


# =========================================================
# DATABASE
# =========================================================

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

    except Exception as e:

        print(
            "State file read error:",
            e
        )

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


# =========================================================
# HELPERS
# =========================================================

def get_value(data, *keys):

    if not isinstance(data, dict):
        return None

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


# =========================================================
# TIME
# =========================================================

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

    return dt_to_string(pkt)


def dt_to_string(dt):

    return dt.strftime(
        "%d-%m-%Y %I:%M:%S %p PKT"
    )


def token_age_minutes(value):

    dt = parse_timestamp(value)

    if dt is None:
        return None

    now = datetime.now(timezone.utc)

    return (
        now - dt
    ).total_seconds() / 60


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise Exception(
            "TELEGRAM_BOT_TOKEN missing"
        )

    if not CHAT_ID:
        raise Exception(
            "TELEGRAM_CHAT_ID missing"
        )

    # =====================================================
    # MANUAL RUN TELEGRAM TEST
    # =====================================================

    if GITHUB_EVENT_NAME == "workflow_dispatch":

        telegram_test()

    # =====================================================
    # LOAD DATABASE
    # =====================================================

    old_tokens = load_old_tokens()

    current_tokens = {}

    total_found = 0

    # =====================================================
    # GET BINANCE WEB3 TOKENS
    # =====================================================

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

    # =====================================================
    # FIRST RUN
    # =====================================================

    if not old_tokens:

        save_tokens(
            current_tokens
        )

        send_telegram(
            "✅ Binance Web3 Wallet Monitor Started\n\n"
            "🌐 Chains monitored:\n"
            "• Ethereum\n"
            "• BNB Chain\n\n"
            "⏱️ New token age limit: 10 minutes\n\n"
            "🔵 Ethereum:\n"
            "• No supply filter\n"
            "• No liquidity filter\n"
            "• No market cap filter\n"
            "• No holders filter\n"
            "• No volume filter\n\n"
            "🟡 BNB Chain:\n"
            "• Total Supply < 600M\n\n"
            "🚨 Old tokens will NOT be alerted."
        )

        return

    # =====================================================
    # FIND NEW TOKENS
    # =====================================================

    new_tokens = []

    for token_key, token in current_tokens.items():

        if token_key not in old_tokens:

            new_tokens.append(token)

    print(
        "New Wallet/Web3 tokens:",
        len(new_tokens)
    )

    # =====================================================
    # CHECK EACH NEW TOKEN
    # =====================================================

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

            # =================================================
            # LAUNCH TIME
            # =================================================

            launch_time = get_value(
                dynamic,
                "launchTime",
                "launch_time"
            )

            if launch_time is None:

                launch_time = token.get(
                    "launchTime"
                )

            age_minutes = token_age_minutes(
                launch_time
            )

            print(
                f"{symbol} | "
                f"{chain_name} | "
                f"Launch: "
                f"{pakistan_time(launch_time)}"
            )

            if age_minutes is None:

                print(
                    "SKIPPED: launch time unavailable",
                    symbol
                )

                continue

            if age_minutes < 0:

                print(
                    "SKIPPED: future launch time",
                    symbol
                )

                continue

            if age_minutes > MAX_TOKEN_AGE_MINUTES:

                print(
                    "SKIPPED: token older than 10 minutes",
                    symbol,
                    f"{age_minutes:.2f} minutes old"
                )

                continue

            # =================================================
            # TOTAL SUPPLY
            # =================================================

            total_supply = safe_number(
                get_value(
                    dynamic,
                    "totalSupply",
                    "total_supply"
                )
            )

            if total_supply is None:

                total_supply = safe_number(
                    token.get(
                        "totalSupply"
                    )
                )

            # =================================================
            # BNB CHAIN SUPPLY FILTER
            # =================================================

            if chain_id == "56":

                if total_supply is None:

                    print(
                        "SKIPPED BNB: supply unavailable",
                        symbol
                    )

                    continue

                if total_supply >= BNB_MAX_SUPPLY:

                    print(
                        "SKIPPED BNB: supply >= 600M",
                        symbol,
                        format_supply(total_supply)
                    )

                    continue

            # =================================================
            # OPTIONAL INFORMATION
            # =================================================

            liquidity = safe_number(
                get_value(
                    dynamic,
                    "liquidity"
                )
            )

            market_cap = safe_number(
                get_value(
                    dynamic,
                    "marketCap",
                    "market_cap"
                )
            )

            volume_24h = safe_number(
                get_value(
                    dynamic,
                    "volume24h",
                    "volume_24h"
                )
            )

            holders = safe_number(
                get_value(
                    dynamic,
                    "holders",
                    "holderCount"
                )
            )

            price = get_value(
                dynamic,
                "price"
            )

            circulating_supply = safe_number(
                get_value(
                    dynamic,
                    "circulatingSupply",
                    "circulating_supply"
                )
            )

            # =================================================
            # MESSAGE
            # =================================================

            launch_time_text = pakistan_time(
                launch_time
            )

            if chain_id == "1":

                title = (
                    "🔵 NEW ETHEREUM BINANCE WEB3 TOKEN"
                )

                filter_text = (
                    "✅ Ethereum token\n"
                    "✅ No supply filter\n"
                    "✅ No liquidity filter\n"
                    "✅ No market cap filter\n"
                    "✅ No holders filter\n"
                    "✅ No volume filter"
                )

            else:

                title = (
                    "🟡 NEW BNB CHAIN BINANCE WEB3 TOKEN"
                )

                filter_text = (
                    "✅ BNB Supply < 600M\n"
                    "✅ Launch age ≤ 10 minutes"
                )

            message_lines = [

                title,
                "",

                f"🪙 Symbol: {symbol}",
                f"⛓️ Chain: {chain_name}",
                "",

                "📦 Total Supply: "
                f"{format_supply(total_supply)}",

                "🔄 Circulating Supply: "
                f"{format_supply(circulating_supply)}",

                "",

                f"💵 Price: {format_money(price)}",

                "💧 Liquidity: "
                f"{format_money(liquidity)}",

                "📊 Market Cap: "
                f"{format_money(market_cap)}",

                "📈 24h Volume: "
                f"{format_money(volume_24h)}",

                (
                    f"👥 Holders: {int(holders)}"
                    if holders is not None
                    else "👥 Holders: N/A"
                ),

                "",

                "⏰ Launch Time:",
                launch_time_text,

                f"🕐 Age: {age_minutes:.1f} minutes",

                "",

                "📜 Contract:",
                contract,

                "",

                filter_text,

                "",

                "⚠️ یہ فلٹر صرف ابتدائی چھان بین ہے، "
                "منافع یا حفاظت کی ضمانت نہیں۔"
            ]

            message = "\n".join(
                message_lines
            )

            # =================================================
            # SEND ALERT
            # =================================================

            try:

                send_telegram(
                    message
                )

                print(
                    "ALERT SENT:",
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

    # =====================================================
    # UPDATE DATABASE
    # =====================================================

    save_tokens(
        current_tokens
    )

    print(
        "Wallet token database updated."
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
