name: YouTube Update

on:
  schedule:
    - cron: '0 7 * * *'
  workflow_dispatch:

jobs:
  fetch-youtube:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Fetch YouTube data
        run: python scripts/fetch-youtube.py

      - name: Commit data
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/youtube.json
          git diff --staged --quiet || git commit -m "YouTube Update $(date +'%Y-%m-%d')"
          git push
