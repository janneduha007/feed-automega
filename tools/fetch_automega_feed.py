import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("AUTOMEGA_FEED_URL", "").strip()
OUT = os.environ.get("AUTOMEGA_FEED_FILE", "tmp/automega.xml")

if not URL:
    print("Missing AUTOMEGA_FEED_URL env var", file=sys.stderr)
    sys.exit(2)

Path(OUT).parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    # načti URL
    resp = page.goto(URL, wait_until="networkidle", timeout=300000)
    # vezmi text stránky (pokud endpoint vrací xml, bude to xml)
    content = page.content()
    # ale u xml endpointu bývá obsah v body jako raw; lepší je vzít response body:
    body = resp.body() if resp is not None else content.encode("utf-8", errors="ignore")
    Path(OUT).write_bytes(body)
    browser.close()

print(f"Wrote {OUT} ({Path(OUT).stat().st_size} bytes)")
