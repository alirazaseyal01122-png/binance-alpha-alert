
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
          fetch-depth: 0

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
          git config user.name "Binance Web3 Monitor"
          git config user.email "binance-web3-monitor@users.noreply.github.com"

          git add alpha_tokens.json wallet_tokens.json

          if git diff --cached --quiet; then
            echo "No token state changes."
            exit 0
          fi

          git commit -m "Update Binance token states"

          git pull --rebase origin main

          git push origin main
