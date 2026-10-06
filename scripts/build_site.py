#!/usr/bin/env python3
"""
Builds the website folder for GitHub Pages:
  1. copies index.html (the tracker) into the output folder
  2. downloads today's TCGplayer prices from swu-db.com into swu_prices.js

The list of sets is read from the SETS block in index.html, so adding a set
to the tracker is all it takes for its prices to be downloaded too.

Usage: python3 scripts/build_site.py [output_folder]   (default: _site)
"""
import datetime
import json
import pathlib
import re
import shutil
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
API = "https://api.swu-db.com/cards/{}"
# Only the fields the tracker uses, to keep the price file small
KEEP = ("Set", "Number", "Name", "Subtitle", "VariantType", "MarketPrice", "LowPrice", "tcgplayerId")


def set_codes():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    start = html.index("const SETS = [")
    block = html[start:html.index("];", start)]
    codes = re.findall(r"code:\s*'([A-Z0-9]+)'", block)
    if not codes:
        sys.exit("Couldn't find any set codes in index.html")
    return codes


def fetch_set(code):
    url = API.format(code.lower())
    headers = {"User-Agent": "swu-collection-tracker (GitHub Actions)", "Accept": "application/json"}
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as resp:
                data = json.load(resp)
            cards = data.get("data") if isinstance(data, dict) else data
            if isinstance(cards, list):
                return [{k: c[k] for k in KEEP if c.get(k) not in (None, "")} for c in cards]
            print(f"  {code}: unexpected response", file=sys.stderr)
        except Exception as e:  # network hiccup, timeout, bad JSON
            print(f"  {code} attempt {attempt}: {e}", file=sys.stderr)
        time.sleep(5 * attempt)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "index.html", OUT / "index.html")

    sets = {}
    for code in set_codes():
        cards = fetch_set(code)
        sets[code] = cards
        print(f"{code}: {'%d cards' % len(cards) if cards is not None else 'FAILED'}")
        time.sleep(1)  # be polite to swu-db.com

    if not any(v for v in sets.values()):
        # Failing the build keeps yesterday's site (and prices) online
        sys.exit("No prices downloaded; keeping the previous deployment.")

    payload = {
        "fetchedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sets": sets,
    }
    js = "window.SWU_PRICE_DATA = " + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";\n"
    (OUT / "swu_prices.js").write_text(js, encoding="utf-8")
    print(f"Wrote {OUT / 'swu_prices.js'} ({len(js) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
