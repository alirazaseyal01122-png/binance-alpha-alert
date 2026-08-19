
import os
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN نہیں ملا")

if not CHAT_ID:
    raise Exception("TELEGRAM_CHAT_ID نہیں ملا")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

response = requests.post(
    url,
    data={
        "chat_id": CHAT_ID,
        "text": "✅ TEST SUCCESS - Binance Alpha Alert Bot connected!"
    }
)

print(response.status_code)
print(response.text)

if response.status_code != 200:
    raise Exception("Telegram message failed")

print("Telegram message sent successfully")
