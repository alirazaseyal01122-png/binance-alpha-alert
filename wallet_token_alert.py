name: Binance Alpha + Web3 Wallet Monitor

on:
  schedule:
    - cron: "*/2 * * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:

      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          persist-credentials: true

      - name: Install Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install requests
        run: pip install requests

      # Binance Alpha Monitor
      - name: Run Binance Alpha Monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python alpha_alert.py

      # Binance Web3 Wallet Monitor
      - name: Run Binance Web3 Wallet Monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python wallet_token_alert.py

      # Save both token databases
      - name: Save token state
        run: |
          git config user.name "Binance Token Monitor"
          git config user.email "binance-token-bot@users.noreply.github.com"

          git add alpha_tokens.json wallet_tokens.json

          git diff --cached --quiet || git commit -m "Update token monitor state"

          git push
