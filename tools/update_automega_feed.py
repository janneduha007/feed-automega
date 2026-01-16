#!/usr/bin/env python3
import os, json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_XML = REPO_ROOT / "feeds" / "automega.xml"
SNAPSHOT = REPO_ROOT / "data" / "automega_snapshot.json"

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def parse_shopitems(xml_text: str):
    # xml_text is expected to be <SHOP>...</SHOP>
    root = ET.fromstring(xml_text)
    items = root.findall("SHOPITEM")
    by_code = {}
    for it in items:
        code_el = it.find("CODE")
        if code_el is None or (code_el.text or "").strip() == "":
            continue
        code = code_el.text.strip()
        by_code[code] = it
    return root, by_code

def ensure_blocked(item: ET.Element):
    # PRODUCT_VISIBILITY=blocked
    vis = item.find("PRODUCT_VISIBILITY")
    if vis is None:
        vis = ET.SubElement(item, "PRODUCT_VISIBILITY")
    vis.text = "blocked"

    # STOCK/AMOUNT=0 (pojistka)
    stock = item.find("STOCK")
    if stock is None:
        stock = ET.SubElement(item, "STOCK")
    amount = stock.find("AMOUNT")
    if amount is None:
        amount = ET.SubElement(stock, "AMOUNT")
    amount.text = "0"
    min_amt = stock.find("MINIMAL_AMOUNT")
    if min_amt is None:
        min_amt = ET.SubElement(stock, "MINIMAL_AMOUNT")
        min_amt.text = "1"

def ensure_unblocked(item: ET.Element):
    vis = item.find("PRODUCT_VISIBILITY")
    if vis is not None and (vis.text or "").strip().lower() == "blocked":
        item.remove(vis)

def element_to_string(el: ET.Element) -> str:
    # No XML declaration; keep it as <SHOPITEM>...</SHOPITEM>
    return ET.tostring(el, encoding="unicode")

def pretty_shop(root: ET.Element) -> str:
    # Python's stdlib pretty printing is limited; keep minimal formatting.
    return ET.tostring(root, encoding="unicode")

def main():
    src_path = os.environ.get("AUTOMEGA_FEED_FILE", "").strip()
    if not src_path:
        raise SystemExit("Missing env AUTOMEGA_FEED_FILE")
    xml_text = read_text(Path(src_path))

    # Parse current feed
    cur_root, cur_by_code = parse_shopitems(xml_text)

    # Load snapshot (previous items)
    snap_items = {}
    if SNAPSHOT.exists():
        snap = json.loads(read_text(SNAPSHOT))
        snap_items = snap.get("items", {}) or {}

    # Determine missing codes (were in snapshot but not in current)
    missing_codes = [code for code in snap_items.keys() if code not in cur_by_code]

    # Build output <SHOP>
    out_root = ET.Element("SHOP")

    # Current items: ensure unblocked
    for code, item in cur_by_code.items():
        it_copy = ET.fromstring(element_to_string(item))  # deep copy
        ensure_unblocked(it_copy)
        out_root.append(it_copy)

    # Missing items: re-add from snapshot as blocked
    for code in missing_codes:
        try:
            it = ET.fromstring(snap_items[code])
            ensure_blocked(it)
            out_root.append(it)
        except Exception:
            # skip malformed snapshot record
            pass

    # Write output XML
    write_text(OUT_XML, pretty_shop(out_root))

    # Update snapshot with CURRENT items only (normalized as unblocked)
    new_snap = {"updatedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z", "items": {}}
    for code, item in cur_by_code.items():
        it_copy = ET.fromstring(element_to_string(item))
        ensure_unblocked(it_copy)
        new_snap["items"][code] = element_to_string(it_copy)

    write_text(SNAPSHOT, json.dumps(new_snap, ensure_ascii=False, indent=2))

    print(f"Current: {len(cur_by_code)} | Missing added as blocked: {len(missing_codes)}")
    print(f"Wrote: {OUT_XML} and {SNAPSHOT}")

if __name__ == "__main__":
    main()
