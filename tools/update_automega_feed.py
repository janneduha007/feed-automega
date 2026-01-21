import os
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone

OUT_XML_PATH = Path("feeds/automega.xml")
SNAPSHOT_PATH = Path("data/automega_snapshot.json")
CHANGES_JSON_PATH = Path("data/automega_changes.json")
CHANGES_MD_PATH = Path("data/automega_changes.md")

OUT_OF_STOCK_TEXT = "Odesíláme do 3-5 dnů"

def parse_shopitems(xml_text: str):
    root = ET.fromstring(xml_text)  # <SHOP>
    items = root.findall("SHOPITEM")
    by_code = {}
    for it in items:
        code = (it.findtext("CODE") or "").strip()
        if not code:
            continue
        by_code[code] = it
    return root, by_code

def ensure_dirs():
    OUT_XML_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHANGES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHANGES_MD_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_snapshot():
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None

def save_snapshot(items_by_code):
    # Uložíme XML každého SHOPITEM bez XML hlavičky
    snap = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": {}
    }
    for code, item in items_by_code.items():
        xml = ET.tostring(item, encoding="unicode")
        snap["items"][code] = xml
    SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

def compute_changes(prev_snapshot, current_codes):
    prev_codes = set()
    if prev_snapshot and isinstance(prev_snapshot, dict) and "items" in prev_snapshot:
        prev_codes = set(prev_snapshot["items"].keys())

    cur_codes = set(current_codes)

    new_codes = sorted(cur_codes - prev_codes)
    missing_codes = sorted(prev_codes - cur_codes)

    changes = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "new_count": len(new_codes),
        "missing_count": len(missing_codes),
        "new_codes": new_codes,
        "missing_codes": missing_codes
    }
    return changes

def write_changes_files(changes):
    CHANGES_JSON_PATH.write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")

    # hezký markdown pro email
    lines = []
    lines.append(f"# Automega feed změny")
    lines.append(f"- Čas (UTC): {changes.get('timestamp_utc','')}")
    lines.append("")
    lines.append(f"## Nové produkty ({changes['new_count']})")
    if changes["new_codes"]:
        for c in changes["new_codes"][:200]:
            lines.append(f"- {c}")
        if len(changes["new_codes"]) > 200:
            lines.append(f"- ... a dalších {len(changes['new_codes']) - 200}")
    else:
        lines.append("- (žádné)")
    lines.append("")
    lines.append(f"## Zmizelé produkty ({changes['missing_count']})")
    if changes["missing_codes"]:
        for c in changes["missing_codes"][:200]:
            lines.append(f"- {c}")
        if len(changes["missing_codes"]) > 200:
            lines.append(f"- ... a dalších {len(changes['missing_codes']) - 200}")
    else:
        lines.append("- (žádné)")
    lines.append("")

    CHANGES_MD_PATH.write_text("\n".join(lines), encoding="utf-8")

def _get_or_create(parent: ET.Element, tag: str) -> ET.Element:
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    return el

def _set_stock_zero(item: ET.Element) -> None:
    stock = item.find("STOCK")
    if stock is None:
        stock = ET.SubElement(item, "STOCK")
    amount = _get_or_create(stock, "AMOUNT")
    amount.text = "0"

    # minimal amount necháme být, ale pokud chybí, dáme 1
    min_amt = stock.find("MINIMAL_AMOUNT")
    if min_amt is None:
        min_amt = ET.SubElement(stock, "MINIMAL_AMOUNT")
        min_amt.text = "1"

def _set_out_of_stock_availability(item: ET.Element, text: str) -> None:
    # Shoptet import (podle tvého logu) povoluje AVAILABILITY_OUT_OF_STOCK
    el = item.find("AVAILABILITY_OUT_OF_STOCK")
    if el is None:
        el = ET.SubElement(item, "AVAILABILITY_OUT_OF_STOCK")
    el.text = text

    # pokud dodavatel má <AVAILABILITY>, odstraníme, aby se nemíchalo
    av = item.find("AVAILABILITY")
    if av is not None:
        item.remove(av)

def _supplier_amount(item: ET.Element):
    amt = (item.findtext("STOCK/AMOUNT") or "").strip()
    try:
        return int(float(amt))
    except Exception:
        return None

def normalize_item_for_output(item: ET.Element, force_out_of_stock: bool = False) -> ET.Element:
    """
    - odstraní nepovolené tagy: PRODUCT_VISIBILITY
    - pokud je dodavatel vyprodaný (AMOUNT<=0) nebo force_out_of_stock=True:
        -> vynutí AMOUNT=0 + AVAILABILITY_OUT_OF_STOCK="Odesíláme do 3-5 dnů"
    """
    # odstranit PRODUCT_VISIBILITY (Shoptet ho odmítá)
    pv = item.find("PRODUCT_VISIBILITY")
    if pv is not None:
        item.remove(pv)

    amt = _supplier_amount(item)
    is_out = force_out_of_stock or (amt is not None and amt <= 0)

    if is_out:
        _set_stock_zero(item)
        _set_out_of_stock_availability(item, OUT_OF_STOCK_TEXT)

    return item

def write_output_feed(current_items_by_code, prev_snapshot):
    """
    Výstup = všechny aktuální položky + chybějící položky ze snapshotu (forced out-of-stock).
    """
    out_root = ET.Element("SHOP")

    current_codes = set(current_items_by_code.keys())

    # 1) current items (normalizace vyprodání podle dodavatele)
    for code in sorted(current_items_by_code.keys()):
        it = current_items_by_code[code]
        out_root.append(normalize_item_for_output(it, force_out_of_stock=False))

    # 2) missing items (ze snapshotu) -> forced out-of-stock
    missing_codes = []
    if prev_snapshot and isinstance(prev_snapshot, dict) and "items" in prev_snapshot:
        prev_codes = set(prev_snapshot["items"].keys())
        missing_codes = sorted(prev_codes - current_codes)

        for code in missing_codes:
            xml = prev_snapshot["items"][code]
            try:
                missing_item = ET.fromstring(xml)
                out_root.append(normalize_item_for_output(missing_item, force_out_of_stock=True))
            except Exception:
                # pokud je xml poškozené, přeskočíme
                pass

    tree = ET.ElementTree(out_root)

    # pretty print (ET nemá hezký pretty, ale Shoptetu to nevadí)
    OUT_XML_PATH.write_text(ET.tostring(out_root, encoding="unicode"), encoding="utf-8")

    return len(current_items_by_code), len(missing_codes)

def main():
    ensure_dirs()

    xml_file = os.environ.get("AUTOMEGA_FEED_FILE", "").strip()
    if not xml_file:
        raise RuntimeError("Missing env AUTOMEGA_FEED_FILE")

    xml_text = Path(xml_file).read_text(encoding="utf-8", errors="replace")

    # parse current feed
    _, cur_by_code = parse_shopitems(xml_text)

    prev_snapshot = load_snapshot()

    # changes (new/missing)
    changes = compute_changes(prev_snapshot, cur_by_code.keys())
    write_changes_files(changes)

    # output feed + missing from snapshot forced out-of-stock
    cur_count, missing_count = write_output_feed(cur_by_code, prev_snapshot)

    # snapshot update
    save_snapshot(cur_by_code)

    print(f"Current: {cur_count} | Missing carried over (forced out-of-stock): {missing_count}")

if __name__ == "__main__":
    main()
