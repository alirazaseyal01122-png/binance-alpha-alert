
import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# BINANCE SPOT SUPPORT SIGNAL BOT
# TOP 500 USDT PAIRS
# SIGNAL ONLY - NO AUTO TRADING
# ============================================================

BINANCE_URL = "https://api.binance.com"
TELEGRAM_URL = "https://api.telegram.org"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")

STATE_FILE = "support_signal_state.json"

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

TOP_PAIRS = 500

# 1H candles
KLINE_LIMIT = 120

# Number of simultaneous Binance requests
MAX_WORKERS = 6

# Maximum distance from support for a BUY signal
SUPPORT_DISTANCE_MAX = 0.018

# Support breakdown threshold
BREAKDOWN_DISTANCE = 0.008

# Volume confirmation
VOLUME_MULTIPLIER = 1.20

# Same signal cooldown
SIGNAL_COOLDOWN_HOURS = 8

# Pakistan Time
PKT = timezone(timedelta(hours=5))

session = requests.Session()

session.headers.update({
    "User-Agent": "Binance-Support-Signal-Bot/1.0"
})


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing.")
        return False

    if not CHAT_ID:
        print("ERROR: TELEGRAM_CHAT_ID is missing.")
        return False

    url = f"{TELEGRAM_URL}/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    try:

        response = session.post(
            url,
            json=payload,
            timeout=20
        )

        if response.status_code == 200:

            print("Telegram message sent successfully.")

            return True

        print(
            "Telegram error:",
            response.status_code,
            response.text[:500]
        )

        return False

    except Exception as error:

        print(
            "Telegram connection error:",
            error
        )

        return False


# ============================================================
# TELEGRAM TEST
# ============================================================

def telegram_test():

    message = (
        "🧪 BINANCE SUPPORT SIGNAL BOT TEST\n\n"

        "✅ GitHub Action: Working\n"
        "✅ Python: Working\n"
        "✅ Telegram Bot: Connected\n"
        "✅ Binance Spot Scanner: Starting\n\n"

        "📊 Scanner:\n"
        "• Top 500 Binance USDT Spot Pairs\n"
        "• 1H Support Detection\n"
        "• RSI Confirmation\n"
        "• EMA20 / EMA50\n"
        "• Volume Confirmation\n"
        "• 4H Trend Confirmation\n\n"

        "🟢 Support Buy Signals: ON\n"
        "🔴 Support Breakdown: ON\n"
        "🤖 Auto Trading: OFF\n\n"

        "🕐 Manual workflow test successful.\n\n"

        "⚡ Binance Support Signal Bot is running."
    )

    return send_telegram(message)


# ============================================================
# STATE
# ============================================================

def load_state():

    if not os.path.exists(STATE_FILE):
        return {}

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(
            "State file read error:",
            error
        )

        return {}


def save_state(state):

    try:

        temporary_file = STATE_FILE + ".tmp"

        with open(
            temporary_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                state,
                file,
                indent=2
            )

        os.replace(
            temporary_file,
            STATE_FILE
        )

    except Exception as error:

        print(
            "State save error:",
            error
        )


def can_send(state, signal_key):

    last_time = state.get(signal_key)

    if not last_time:
        return True

    try:

        elapsed = time.time() - float(last_time)

        cooldown = SIGNAL_COOLDOWN_HOURS * 3600

        return elapsed >= cooldown

    except Exception:

        return True


# ============================================================
# BINANCE API
# ============================================================

def binance_get(
    endpoint,
    params=None,
    retries=3
):

    url = BINANCE_URL + endpoint

    for attempt in range(retries):

        try:

            response = session.get(
                url,
                params=params,
                timeout=20
            )

            if response.status_code == 200:

                return response.json()

            if response.status_code in (418, 429):

                wait_seconds = 10 * (attempt + 1)

                retry_after = response.headers.get(
                    "Retry-After"
                )

                if retry_after:

                    try:
                        wait_seconds = max(
                            wait_seconds,
                            int(retry_after)
                        )

                    except Exception:
                        pass

                print(
                    f"Binance rate limit "
                    f"{response.status_code}. "
                    f"Waiting {wait_seconds}s."
                )

                time.sleep(wait_seconds)

                continue

            print(
                f"Binance HTTP error "
                f"{response.status_code}: "
                f"{response.text[:300]}"
            )

        except Exception as error:

            print(
                "Binance request error:",
                error
            )

            if attempt < retries - 1:

                time.sleep(
                    2 * (attempt + 1)
                )

    return None


# ============================================================
# GET BINANCE SPOT SYMBOLS
# ============================================================

def get_spot_symbols():

    print(
        "Loading Binance Spot exchange information..."
    )

    data = binance_get(
        "/api/v3/exchangeInfo"
    )

    if not data:

        print(
            "ERROR: exchangeInfo unavailable."
        )

        return set()

    symbols = set()

    for item in data.get(
        "symbols",
        []
    ):

        try:

            if item.get("status") != "TRADING":
                continue

            if item.get("quoteAsset") != "USDT":
                continue

            if item.get(
                "isSpotTradingAllowed",
                True
            ) is not True:
                continue

            symbol = item.get("symbol")

            if symbol:
                symbols.add(symbol)

        except Exception:
            continue

    print(
        f"Valid USDT Spot pairs: {len(symbols)}"
    )

    return symbols


# ============================================================
# TOP 500 BY 24H QUOTE VOLUME
# ============================================================

def get_top_pairs():

    symbols = get_spot_symbols()

    if not symbols:
        return []

    print(
        "Loading Binance 24H market volume..."
    )

    tickers = binance_get(
        "/api/v3/ticker/24hr"
    )

    if not tickers:

        print(
            "ERROR: 24H ticker data unavailable."
        )

        return []

    ranked = []

    for ticker in tickers:

        symbol = ticker.get("symbol")

        if symbol not in symbols:
            continue

        try:

            quote_volume = float(
                ticker.get(
                    "quoteVolume",
                    0
                )
            )

            price = float(
                ticker.get(
                    "lastPrice",
                    0
                )
            )

            price_change = float(
                ticker.get(
                    "priceChangePercent",
                    0
                )
            )

            if quote_volume <= 0:
                continue

            if price <= 0:
                continue

            ranked.append({
                "symbol": symbol,
                "quote_volume": quote_volume,
                "price": price,
                "change": price_change
            })

        except Exception:
            continue

    ranked.sort(
        key=lambda x: x["quote_volume"],
        reverse=True
    )

    top = ranked[:TOP_PAIRS]

    print(
        f"Selected Top {len(top)} "
        "USDT Spot pairs by 24H volume."
    )

    return top


# ============================================================
# GET 1H CANDLES
# ============================================================

def get_klines(symbol):

    data = binance_get(
        "/api/v3/klines",
        {
            "symbol": symbol,
            "interval": "1h",
            "limit": KLINE_LIMIT
        }
    )

    if not data:
        return None

    if len(data) < 50:
        return None

    candles = []

    for item in data:

        try:

            candles.append({
                "time": int(item[0]),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            })

        except Exception:
            continue

    if len(candles) < 50:
        return None

    return candles


# ============================================================
# EMA
# ============================================================

def calculate_ema(
    values,
    period
):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(
        values[:period]
    ) / period

    for value in values[period:]:

        result = (
            (value - result)
            * multiplier
        ) + result

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    closes,
    period=14
):

    if len(closes) <= period:
        return None

    gains = []
    losses = []

    for index in range(
        1,
        len(closes)
    ):

        change = (
            closes[index]
            - closes[index - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    average_gain = (
        sum(gains[:period])
        / period
    )

    average_loss = (
        sum(losses[:period])
        / period
    )

    for index in range(
        period,
        len(gains)
    ):

        average_gain = (
            (
                average_gain
                * (period - 1)
            )
            + gains[index]
        ) / period

        average_loss = (
            (
                average_loss
                * (period - 1)
            )
            + losses[index]
        ) / period

    if average_loss == 0:
        return 100.0

    relative_strength = (
        average_gain
        / average_loss
    )

    return (
        100
        - (
            100
            / (1 + relative_strength)
        )
    )


# ============================================================
# ATR
# ============================================================

def calculate_atr(
    candles,
    period=14
):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for index in range(
        1,
        len(candles)
    ):

        current = candles[index]
        previous = candles[index - 1]

        true_range = max(
            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            )
        )

        true_ranges.append(
            true_range
        )

    return (
        sum(true_ranges[-period:])
        / period
    )


# ============================================================
# SUPPORT DETECTION
# ============================================================

def find_support(candles):

    if len(candles) < 50:
        return None

    current_price = candles[-1]["close"]

    local_lows = []

    # Ignore the latest 2 candles because
    # they are still developing.
    last_index = len(candles) - 3

    for index in range(
        2,
        last_index
    ):

        current_low = candles[index]["low"]

        nearby_lows = []

        for neighbour in range(
            index - 2,
            index + 3
        ):

            if neighbour == index:
                continue

            nearby_lows.append(
                candles[neighbour]["low"]
            )

        if not nearby_lows:
            continue

        if current_low <= min(
            nearby_lows
        ):

            local_lows.append({
                "price": current_low,
                "volume": candles[index]["volume"],
                "index": index
            })

    if not local_lows:
        return None

    atr = calculate_atr(
        candles
    )

    if not atr:

        atr = current_price * 0.01

    tolerance = max(
        current_price * 0.006,
        atr * 0.8
    )

    clusters = []

    for point in local_lows:

        placed = False

        for cluster in clusters:

            average_price = (
                sum(
                    item["price"]
                    for item in cluster
                )
                / len(cluster)
            )

            if abs(
                point["price"]
                - average_price
            ) <= tolerance:

                cluster.append(point)

                placed = True

                break

        if not placed:

            clusters.append(
                [point]
            )

    valid_clusters = []

    for cluster in clusters:

        average_price = (
            sum(
                item["price"]
                for item in cluster
            )
            / len(cluster)
        )

        if average_price < current_price:

            valid_clusters.append(
                cluster
            )

    if not valid_clusters:
        return None

    # Prefer:
    # 1. More touches
    # 2. Higher volume
    # 3. Nearest support
    valid_clusters.sort(
        key=lambda cluster: (
            len(cluster),
            max(
                item["volume"]
                for item in cluster
            ),
            -abs(
                current_price
                - (
                    sum(
                        item["price"]
                        for item in cluster
                    )
                    / len(cluster)
                )
            )
        ),
        reverse=True
    )

    best_cluster = valid_clusters[0]

    support = (
        sum(
            item["price"]
            for item in best_cluster
        )
        / len(best_cluster)
    )

    return {
        "support": support,
        "touches": len(best_cluster)
    }


# ============================================================
# 4H CONFIRMATION
# ============================================================

def calculate_4h_ema20(candles):

    four_hour_candles = []

    # Start from complete 4H groups.
    usable_length = (
        len(candles) // 4
    ) * 4

    grouped = candles[
        len(candles) - usable_length:
    ]

    for index in range(
        0,
        len(grouped),
        4
    ):

        group = grouped[
            index:index + 4
        ]

        if len(group) < 4:
            continue

        four_hour_candles.append({
            "open": group[0]["open"],
            "high": max(
                item["high"]
                for item in group
            ),
            "low": min(
                item["low"]
                for item in group
            ),
            "close": group[-1]["close"]
        })

    if len(four_hour_candles) < 20:
        return None

    closes = [
        item["close"]
        for item in four_hour_candles
    ]

    return calculate_ema(
        closes,
        20
    )


# ============================================================
# ANALYZE ONE SYMBOL
# ============================================================

def analyze_symbol(pair):

    symbol = pair["symbol"]

    candles = get_klines(
        symbol
    )

    if not candles:
        return None

    closes = [
        item["close"]
        for item in candles
    ]

    current_price = closes[-1]

    support_data = find_support(
        candles
    )

    if not support_data:
        return None

    support = support_data["support"]
    touches = support_data["touches"]

    if support <= 0:
        return None

    distance = (
        current_price - support
    ) / support

    rsi = calculate_rsi(
        closes
    )

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    atr = calculate_atr(
        candles
    )

    if (
        rsi is None
        or ema20 is None
        or ema50 is None
        or atr is None
    ):
        return None

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    recent_volume = (
        sum(
            item["volume"]
            for item in candles[-5:]
        )
        / 5
    )

    previous_volume = (
        sum(
            item["volume"]
            for item in candles[-25:-5]
        )
        / 20
    )

    if previous_volume > 0:

        volume_ratio = (
            recent_volume
            / previous_volume
        )

    else:

        volume_ratio = 1.0

    # --------------------------------------------------------
    # 4H
    # --------------------------------------------------------

    ema20_4h = calculate_4h_ema20(
        candles
    )

    # --------------------------------------------------------
    # Conditions
    # --------------------------------------------------------

    near_support = (
        0 <= distance
        <= SUPPORT_DISTANCE_MAX
    )

    breakdown = (
        current_price
        < support
        * (1 - BREAKDOWN_DISTANCE)
    )

    last_candle = candles[-1]
    previous_candle = candles[-2]

    bounce = (
        last_candle["close"]
        > previous_candle["close"]
        and
        last_candle["low"]
        <= support * 1.012
    )

    volume_confirmed = (
        volume_ratio
        >= VOLUME_MULTIPLIER
    )

    rsi_good = (
        28 <= rsi <= 58
    )

    ema_bullish = (
        current_price >= ema20
        and
        ema20 >= ema50
    )

    four_hour_bullish = True

    if ema20_4h is not None:

        four_hour_bullish = (
            current_price
            >= ema20_4h
        )

    # --------------------------------------------------------
    # SCORE
    # Maximum score = 12
    # --------------------------------------------------------

    score = 0

    if touches >= 3:

        score += 3

    elif touches == 2:

        score += 2

    else:

        score += 1

    if near_support:
        score += 2

    if bounce:
        score += 2

    if volume_confirmed:
        score += 2

    if rsi_good:
        score += 1

    if ema_bullish:
        score += 1

    if four_hour_bullish:
        score += 1

    # --------------------------------------------------------
    # BREAKDOWN
    # --------------------------------------------------------

    if breakdown:

        return {
            "type": "BREAKDOWN",
            "symbol": symbol,
            "price": current_price,
            "support": support,
            "distance": distance,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
            "ema20_4h": ema20_4h,
            "volume_ratio": volume_ratio,
            "touches": touches,
            "score": score
        }

    # --------------------------------------------------------
    # BUY SIGNAL
    # --------------------------------------------------------

    if near_support and score >= 7:

        stop_loss = min(
            support * 0.985,
            support - atr * 0.7
        )

        risk = (
            current_price
            - stop_loss
        )

        if risk <= 0:
            return None

        tp1 = (
            current_price
            + risk * 1.5
        )

        tp2 = (
            current_price
            + risk * 2.5
        )

        if score >= 10:

            strength = "🔥 VERY STRONG"

        elif score >= 8:

            strength = "🟢 STRONG"

        else:

            strength = "🟡 MEDIUM"

        return {
            "type": "BUY",
            "symbol": symbol,
            "price": current_price,
            "support": support,
            "distance": distance,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
            "ema20_4h": ema20_4h,
            "volume_ratio": volume_ratio,
            "touches": touches,
            "score": score,
            "strength": strength,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2
        }

    return None


# ============================================================
# PRICE FORMAT
# ============================================================

def format_price(value):

    if value >= 1000:

        return f"{value:,.2f}"

    if value >= 1:

        return f"{value:.4f}"

    if value >= 0.01:

        return f"{value:.6f}"

    if value >= 0.0001:

        return f"{value:.8f}"

    return f"{value:.10f}"


# ============================================================
# BUILD TELEGRAM MESSAGE
# ============================================================

def build_message(signal):

    symbol = signal["symbol"]

    if signal["type"] == "BREAKDOWN":

        return (
            "🔴 BINANCE SUPPORT BREAKDOWN\n\n"

            f"🪙 Coin: {symbol}\n"
            f"💵 Price: ${format_price(signal['price'])}\n"
            f"🧱 Broken Support: "
            f"${format_price(signal['support'])}\n\n"

            f"📉 RSI: {signal['rsi']:.1f}\n"
            f"📊 Volume: "
            f"{signal['volume_ratio']:.2f}x\n"
            f"🔎 Support Touches: "
            f"{signal['touches']}\n\n"

            "⚠️ مضبوط Support ٹوٹ گیا ہے۔\n"
            "اس وقت Support Buy سگنل نہیں ہے۔"
        )

    distance_percent = (
        signal["distance"] * 100
    )

    ema4h_text = "N/A"

    if signal["ema20_4h"] is not None:

        ema4h_text = (
            "$"
            + format_price(
                signal["ema20_4h"]
            )
        )

    return (
        "🟢 BINANCE SUPPORT BUY SIGNAL\n\n"

        f"🪙 Coin: {symbol}\n"
        f"⭐ Strength: {signal['strength']}\n"
        f"🎯 Score: {signal['score']}/12\n\n"

        f"💵 Price: "
        f"${format_price(signal['price'])}\n"

        f"🧱 Support: "
        f"${format_price(signal['support'])}\n"

        f"📏 Support Distance: "
        f"{distance_percent:.2f}%\n\n"

        f"📈 RSI: {signal['rsi']:.1f}\n"

        f"📊 Volume: "
        f"{signal['volume_ratio']:.2f}x\n"

        f"🔎 Support Touches: "
        f"{signal['touches']}\n\n"

        f"📐 EMA20: "
        f"${format_price(signal['ema20'])}\n"

        f"📐 EMA50: "
        f"${format_price(signal['ema50'])}\n"

        f"📐 4H EMA20: "
        f"{ema4h_text}\n\n"

        f"🛒 Entry Zone: "
        f"${format_price(signal['support'])}"
        f" - "
        f"${format_price(signal['price'])}\n"

        f"🛑 Stop Loss: "
        f"${format_price(signal['stop_loss'])}\n"

        f"🎯 TP1: "
        f"${format_price(signal['tp1'])}\n"

        f"🎯 TP2: "
        f"${format_price(signal['tp2'])}\n\n"

        "⚠️ یہ صرف تکنیکی سگنل ہے، "
        "خودکار خریداری نہیں۔"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("BINANCE SPOT SUPPORT SIGNAL BOT")
    print("TOP 500 USDT PAIRS")
    print("SIGNAL ONLY - NO AUTO TRADING")
    print("=" * 65)

    # --------------------------------------------------------
    # Manual GitHub test
    # --------------------------------------------------------

    if GITHUB_EVENT_NAME == "workflow_dispatch":

        print(
            "Manual workflow detected."
        )

        print(
            "Sending Telegram test..."
        )

        if telegram_test():

            print(
                "TEST SUCCESS"
            )

        else:

            print(
                "TEST FAILED"
            )

        time.sleep(2)

    # --------------------------------------------------------
    # Check credentials
    # --------------------------------------------------------

    if not BOT_TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN missing."
        )

        return

    if not CHAT_ID:

        print(
            "ERROR: TELEGRAM_CHAT_ID missing."
        )

        return

    # --------------------------------------------------------
    # Load state
    # --------------------------------------------------------

    state = load_state()

    # --------------------------------------------------------
    # Get Top 500
    # --------------------------------------------------------

    pairs = get_top_pairs()

    if not pairs:

        print(
            "No Binance pairs available."
        )

        return

    print(
        f"Starting scan of "
        f"{len(pairs)} pairs..."
    )

    signals = []

    # --------------------------------------------------------
    # Parallel analysis
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_map = {}

        for pair in pairs:

            future = executor.submit(
                analyze_symbol,
                pair
            )

            future_map[
                future
            ] = pair["symbol"]

        completed = 0

        for future in as_completed(
            future_map
        ):

            symbol = future_map[
                future
            ]

            completed += 1

            try:

                result = future.result()

                if result:

                    signals.append(
                        result
                    )

                    print(
                        f"SIGNAL FOUND: "
                        f"{symbol} "
                        f"{result['type']} "
                        f"Score={result['score']}"
                    )

            except Exception as error:

                print(
                    f"{symbol}: "
                    f"analysis error: "
                    f"{error}"
                )

            if completed % 50 == 0:

                print(
                    f"Progress: "
                    f"{completed}/"
                    f"{len(pairs)}"
                )

    # --------------------------------------------------------
    # Strongest signals first
    # --------------------------------------------------------

    signals.sort(
        key=lambda item: item.get(
            "score",
            0
        ),
        reverse=True
    )

    print(
        f"Total signals found: "
        f"{len(signals)}"
    )

    # --------------------------------------------------------
    # Send Telegram
    # --------------------------------------------------------

    sent = 0

    for signal in signals:

        signal_key = (
            f"{signal['symbol']}:"
            f"{signal['type']}"
        )

        if not can_send(
            state,
            signal_key
        ):

            print(
                f"Cooldown active: "
                f"{signal_key}"
            )

            continue

        message = build_message(
            signal
        )

        if send_telegram(
            message
        ):

            state[
                signal_key
            ] = time.time()

            sent += 1

            # Prevent Telegram flooding
            time.sleep(0.7)

    # --------------------------------------------------------
    # Save state
    # --------------------------------------------------------

    save_state(
        state
    )

    print(
        f"Telegram signals sent: "
        f"{sent}"
    )

    # --------------------------------------------------------
    # PKT completion time
    # --------------------------------------------------------

    now_pkt = datetime.now(
        PKT
    )

    print(
        "Scan completed at:",
        now_pkt.strftime(
            "%d-%m-%Y %I:%M:%S %p PKT"
        )
    )

    print(
        "Support Signal Bot completed."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
