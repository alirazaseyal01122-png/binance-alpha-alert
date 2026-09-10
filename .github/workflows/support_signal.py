import os
import json
import time
import math
import requests
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# BINANCE SUPPORT SIGNAL BOT
# Top 500 Binance Spot USDT pairs
# Signal only - NO automatic trading
# ============================================================

BINANCE_URL = "https://api.binance.com"
TELEGRAM_URL = "https://api.telegram.org"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "support_signal_state.json"

TOP_PAIRS = 500
KLINE_LIMIT = 120
MAX_WORKERS = 8

# Signal settings
SUPPORT_DISTANCE_MAX = 0.018       # 1.8%
BREAKDOWN_DISTANCE = 0.008         # 0.8%
VOLUME_MULTIPLIER = 1.20

# Avoid sending the same signal repeatedly
SIGNAL_COOLDOWN_HOURS = 8

PKT = timezone(timedelta(hours=5))

session = requests.Session()
session.headers.update({
    "User-Agent": "Binance-Support-Signal-Bot/1.0"
})


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing.")
        return False

    url = f"{TELEGRAM_URL}/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    try:
        r = session.post(url, json=payload, timeout=15)

        if r.status_code == 200:
            print("Telegram sent successfully.")
            return True

        print("Telegram error:", r.status_code, r.text[:500])
        return False

    except Exception as e:
        print("Telegram exception:", e)
        return False


# ============================================================
# STATE
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print("State save error:", e)


def can_send(state, key):
    last = state.get(key)

    if not last:
        return True

    try:
        last_time = float(last)
        age = time.time() - last_time

        return age >= SIGNAL_COOLDOWN_HOURS * 3600

    except Exception:
        return True


# ============================================================
# BINANCE REQUEST
# ============================================================

def binance_get(endpoint, params=None, retries=3):
    url = BINANCE_URL + endpoint

    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=15)

            if r.status_code == 200:
                return r.json()

            if r.status_code in (418, 429):
                wait_time = 10 * (attempt + 1)

                retry_after = r.headers.get("Retry-After")

                if retry_after:
                    try:
                        wait_time = max(wait_time, int(retry_after))
                    except Exception:
                        pass

                print(
                    f"Rate limit {r.status_code}. "
                    f"Waiting {wait_time}s..."
                )

                time.sleep(wait_time)
                continue

            print(
                f"Binance HTTP {r.status_code}: "
                f"{r.text[:200]}"
            )

        except Exception as e:
            print("Request error:", e)

            if attempt < retries - 1:
                time.sleep(2)

    return None


# ============================================================
# GET TOP 500 USDT SPOT PAIRS
# ============================================================

def get_top_500_pairs():

    print("Loading Binance Spot exchange information...")

    info = binance_get(
        "/api/v3/exchangeInfo",
        {"permissions": "SPOT"}
    )

    if not info:
        print("Could not load exchangeInfo.")
        return []

    valid_symbols = set()

    for s in info.get("symbols", []):

        if s.get("status") != "TRADING":
            continue

        if s.get("quoteAsset") != "USDT":
            continue

        if not s.get("isSpotTradingAllowed", True):
            continue

        valid_symbols.add(s["symbol"])

    print(
        f"Valid Binance USDT Spot pairs: "
        f"{len(valid_symbols)}"
    )

    print("Loading 24h volume...")

    tickers = binance_get("/api/v3/ticker/24hr")

    if not tickers:
        print("Could not load 24h tickers.")
        return []

    ranked = []

    for ticker in tickers:

        symbol = ticker.get("symbol")

        if symbol not in valid_symbols:
            continue

        try:
            quote_volume = float(
                ticker.get("quoteVolume", 0)
            )

            last_price = float(
                ticker.get("lastPrice", 0)
            )

            price_change = float(
                ticker.get("priceChangePercent", 0)
            )

            if quote_volume <= 0 or last_price <= 0:
                continue

            ranked.append({
                "symbol": symbol,
                "quote_volume": quote_volume,
                "price": last_price,
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
        f"Top {len(top)} Binance USDT pairs selected."
    )

    return top


# ============================================================
# KLINES
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

    if not data or len(data) < 50:
        return None

    candles = []

    for x in data:

        try:
            candles.append({
                "time": int(x[0]),
                "open": float(x[1]),
                "high": float(x[2]),
                "low": float(x[3]),
                "close": float(x[4]),
                "volume": float(x[5])
            })

        except Exception:
            continue

    return candles


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for price in values[period:]:
        result = (
            (price - result) * multiplier
        ) + result

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(closes, period=14):

    if len(closes) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1)) +
            gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) +
            losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    trs = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"])
        )

        trs.append(tr)

    return sum(trs[-period:]) / period


# ============================================================
# SUPPORT DETECTION
# ============================================================

def find_support(candles):

    if len(candles) < 50:
        return None

    current_price = candles[-1]["close"]

    lows = [
        c["low"]
        for c in candles[:-3]
    ]

    if not lows:
        return None

    # Local lows
    local_lows = []

    for i in range(2, len(candles) - 2):

        current_low = candles[i]["low"]

        nearby = [
            candles[j]["low"]
            for j in range(i - 2, i + 3)
            if j != i
        ]

        if current_low <= min(nearby):
            local_lows.append({
                "price": current_low,
                "volume": candles[i]["volume"],
                "index": i
            })

    if not local_lows:
        return None

    atr = calculate_atr(candles)

    if not atr:
        atr = current_price * 0.01

    tolerance = max(
        current_price * 0.006,
        atr * 0.8
    )

    # Group nearby support levels
    clusters = []

    for point in local_lows:

        placed = False

        for cluster in clusters:

            avg_price = sum(
                p["price"] for p in cluster
            ) / len(cluster)

            if abs(point["price"] - avg_price) <= tolerance:

                cluster.append(point)
                placed = True
                break

        if not placed:
            clusters.append([point])

    if not clusters:
        return None

    # Only supports below current price
    valid_clusters = []

    for cluster in clusters:

        avg_price = sum(
            p["price"] for p in cluster
        ) / len(cluster)

        if avg_price < current_price:
            valid_clusters.append(cluster)

    if not valid_clusters:
        return None

    # Strongest nearby support
    valid_clusters.sort(
        key=lambda c: (
            len(c),
            max(p["volume"] for p in c)
        ),
        reverse=True
    )

    cluster = valid_clusters[0]

    support = sum(
        p["price"] for p in cluster
    ) / len(cluster)

    touches = len(cluster)

    return {
        "support": support,
        "touches": touches
    }


# ============================================================
# ANALYZE SYMBOL
# ============================================================

def analyze_symbol(pair):

    symbol = pair["symbol"]

    candles = get_klines(symbol)

    if not candles:
        return None

    closes = [c["close"] for c in candles]

    current = closes[-1]

    support_data = find_support(candles)

    if not support_data:
        return None

    support = support_data["support"]
    touches = support_data["touches"]

    if current <= 0 or support <= 0:
        return None

    distance = (current - support) / support

    rsi = calculate_rsi(closes)

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    atr = calculate_atr(candles)

    if not rsi or not ema20 or not ema50 or not atr:
        return None

    recent_volume = sum(
        c["volume"] for c in candles[-5:]
    ) / 5

    previous_volume = sum(
        c["volume"] for c in candles[-25:-5]
    ) / 20

    volume_ratio = (
        recent_volume / previous_volume
        if previous_volume > 0
        else 1
    )

    # ========================================================
    # 4H confirmation using 1H candles
    # ========================================================

    four_hour = []

    for i in range(0, len(candles) - 3, 4):

        group = candles[i:i + 4]

        if len(group) < 4:
            continue

        four_hour.append({
            "open": group[0]["open"],
            "high": max(x["high"] for x in group),
            "low": min(x["low"] for x in group),
            "close": group[-1]["close"]
        })

    if len(four_hour) >= 20:

        closes4 = [
            x["close"]
            for x in four_hour
        ]

        ema20_4h = ema(closes4, 20)

    else:
        ema20_4h = None

    # ========================================================
    # SUPPORT DISTANCE
    # ========================================================

    near_support = (
        0 <= distance <= SUPPORT_DISTANCE_MAX
    )

    # ========================================================
    # BREAKDOWN
    # ========================================================

    breakdown = (
        current < support * (1 - BREAKDOWN_DISTANCE)
    )

    # ========================================================
    # BOUNCE CONFIRMATION
    # ========================================================

    last_candle = candles[-1]
    previous_candle = candles[-2]

    bounce = (
        last_candle["close"] > previous_candle["close"]
        and
        last_candle["low"] <= support * 1.012
    )

    volume_confirmed = (
        volume_ratio >= VOLUME_MULTIPLIER
    )

    rsi_good = (
        28 <= rsi <= 58
    )

    ema_bullish = (
        current >= ema20
        and ema20 >= ema50
    )

    four_hour_bullish = True

    if ema20_4h:
        four_hour_bullish = current >= ema20_4h

    # ========================================================
    # SIGNAL SCORE
    # ========================================================

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

    # ========================================================
    # BREAKDOWN FIRST
    # ========================================================

    if breakdown:

        return {
            "type": "BREAKDOWN",
            "symbol": symbol,
            "price": current,
            "support": support,
            "distance": distance,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
            "volume_ratio": volume_ratio,
            "touches": touches,
            "score": score
        }

    # ========================================================
    # BUY SIGNAL
    # ========================================================

    if near_support and score >= 7:

        # Stop below support + ATR protection
        stop_loss = min(
            support * 0.985,
            support - atr * 0.7
        )

        risk = current - stop_loss

        if risk <= 0:
            return None

        tp1 = current + risk * 1.5
        tp2 = current + risk * 2.5

        if score >= 10:
            strength = "🔥 VERY STRONG"
        elif score >= 8:
            strength = "🟢 STRONG"
        else:
            strength = "🟡 MEDIUM"

        return {
            "type": "BUY",
            "symbol": symbol,
            "price": current,
            "support": support,
            "distance": distance,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
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
# FORMAT PRICE
# ============================================================

def fmt_price(value):

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
# SIGNAL MESSAGE
# ============================================================

def build_message(signal):

    symbol = signal["symbol"]

    if signal["type"] == "BREAKDOWN":

        return (
            "🔴 BINANCE SUPPORT BREAKDOWN\n\n"
            f"🪙 Coin: {symbol}\n"
            f"💵 Price: ${fmt_price(signal['price'])}\n"
            f"🧱 Broken Support: ${fmt_price(signal['support'])}\n"
            f"📉 RSI: {signal['rsi']:.1f}\n"
            f"📊 Volume: {signal['volume_ratio']:.2f}x\n"
            f"🔎 Support Touches: {signal['touches']}\n\n"
            "⚠️ مضبوط Support ٹوٹ گیا ہے۔\n"
            "اس وقت Support Buy سگنل نہیں ہے۔"
        )

    distance_percent = signal["distance"] * 100

    return (
        "🟢 BINANCE SUPPORT BUY SIGNAL\n\n"
        f"🪙 Coin: {symbol}\n"
        f"⭐ Strength: {signal['strength']}\n"
        f"🎯 Score: {signal['score']}/12\n\n"
        f"💵 Price: ${fmt_price(signal['price'])}\n"
        f"🧱 Support: ${fmt_price(signal['support'])}\n"
        f"📏 Support Distance: {distance_percent:.2f}%\n\n"
        f"📈 RSI: {signal['rsi']:.1f}\n"
        f"📊 Volume: {signal['volume_ratio']:.2f}x\n"
        f"🔎 Support Touches: {signal['touches']}\n"
        f"📐 EMA20: ${fmt_price(signal['ema20'])}\n"
        f"📐 EMA50: ${fmt_price(signal['ema50'])}\n\n"
        f"🛒 Entry Zone: ${fmt_price(signal['support'])}"
        f" - ${fmt_price(signal['price'])}\n"
        f"🛑 Stop Loss: ${fmt_price(signal['stop_loss'])}\n"
        f"🎯 TP1: ${fmt_price(signal['tp1'])}\n"
        f"🎯 TP2: ${fmt_price(signal['tp2'])}\n\n"
        "⚠️ یہ صرف تکنیکی سگنل ہے، خودکار خریداری نہیں۔"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("BINANCE SUPPORT SIGNAL BOT")
    print("=" * 60)

    state = load_state()

    pairs = get_top_500_pairs()

    if not pairs:
        print("No pairs found.")
        return

    signals = []

    print(
        f"Scanning {len(pairs)} Binance Spot pairs..."
    )

    # ========================================================
    # Parallel scanning
    # ========================================================

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                analyze_symbol,
                pair
            ): pair["symbol"]
            for pair in pairs
        }

        completed = 0

        for future in as_completed(futures):

            symbol = futures[future]

            completed += 1

            try:
                result = future.result()

                if result:
                    signals.append(result)

                    print(
                        f"SIGNAL: {symbol} "
                        f"{result['type']}"
                    )

            except Exception as e:
                print(
                    f"{symbol}: analysis error: {e}"
                )

            if completed % 50 == 0:
                print(
                    f"Progress: "
                    f"{completed}/{len(pairs)}"
                )

    # ========================================================
    # Sort strongest first
    # ========================================================

    signals.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    print(
        f"Total signals found: {len(signals)}"
    )

    # ========================================================
    # Telegram
    # ========================================================

    sent = 0

    for signal in signals:

        key = (
            f"{signal['symbol']}:"
            f"{signal['type']}"
        )

        if not can_send(state, key):
            continue

        message = build_message(signal)

        if send_telegram(message):

            state[key] = time.time()

            sent += 1

            # Small delay to avoid Telegram flooding
            time.sleep(0.5)

    save_state(state)

    print(
        f"Telegram signals sent: {sent}"
    )

    print("Support scan completed.")


if __name__ == "__main__":
    main()
