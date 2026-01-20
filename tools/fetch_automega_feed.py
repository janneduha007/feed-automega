import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("AUTOMEGA_FEED_URL", "").strip()
OUT = os.environ.get("AUTOMEGA_FEED_FILE", "tmp/automega.xml")

if not URL:
    print("Missing AUTOMEGA_FEED_URL env var", file=sys.stderr)
    sys.exit(2)

out_path = Path(OUT)
out_path.parent.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/xml,text/xml,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Referer": "http://www.automega.cz/",
}

with sync_playwright() as p:
    # Use APIRequestContext - reliable for large responses
    request = p.request.new_context(extra_http_headers=HEADERS)
    resp = request.get(URL, timeout=300_000)

    status = resp.status
    ctype = resp.headers.get("content-type", "")
    body = resp.body()

    out_path.write_bytes(body)

    request.dispose()

print(f"HTTP {status}, Content-Type: {ctype}")
print(f"Wrote {OUT} ({out_path.stat().st_size} bytes)")
