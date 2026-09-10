name: Binance Alpha + Web3 + Support Signal Monitor

on:
  schedule:
    - cron: "*/2 * * * *"
  workflow_dispatch:

concurrency:
  group: binance-alpha-web3-support-monitor
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:

      # =====================================================
      # CHECKOUT
      # =====================================================

      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          fetch-depth: 0
          persist-credentials: true

      # =====================================================
      # PYTHON
      # =====================================================

      - name: Install Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      # =====================================================
      # REQUESTS
      # =====================================================

      - name: Install requests
        run: |
          python -m pip install --upgrade pip
          pip install requests

      # =====================================================
      # BINANCE ALPHA
      # =====================================================

      - name: Run Binance Alpha Monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python alpha_alert.py

      # =====================================================
      # BINANCE WEB3 WALLET
      # =====================================================

      - name: Run Binance Web3 Wallet Monitor
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GITHUB_EVENT_NAME: ${{ github.event_name }}
        run: |
          python wallet_token_alert.py

      # =====================================================
      # SUPPORT SIGNAL BOT
      # =====================================================

      - name: Run Binance Support Signal Bot
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python support_signal.py

      # =====================================================
      # SAVE ALL STATES
      # =====================================================

      - name: Save bot states
        run: |
          git config user.name "Binance Monitor"
          git config user.email "binance-monitor@users.noreply.github.com"

          git add alpha_tokens.json
          git add wallet_tokens.json
          git add support_signal_state.json

          if git diff --cached --quiet; then
            echo "No state changes to commit."
            exit 0
          fi

          git commit -m "Update Binance monitor states"

          git fetch origin main

          git merge --no-edit origin/main || {
            echo "Merge conflict detected."
            echo "Aborting state update safely."
            git merge --abort || true
            exit 0
          }

          git push origin main
