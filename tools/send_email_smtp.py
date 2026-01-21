import os
import json
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone

def main():
    smtp_host = os.environ["SMTP_HOST"].strip()
    smtp_port = int(os.environ.get("SMTP_PORT", "587").strip())
    smtp_user = os.environ["SMTP_USER"].strip()
    smtp_pass = os.environ["SMTP_PASS"].strip()

    mail_to = os.environ["MAIL_TO"].strip()
    mail_from = os.environ.get("MAIL_FROM", smtp_user).strip()

    subject_prefix = os.environ.get("SUBJECT_PREFIX", "Automega feed").strip()
    changes_json_path = os.environ.get("CHANGES_JSON", "data/automega_changes.json").strip()

    # Načti změny
    if not os.path.exists(changes_json_path):
        print(f"Changes file not found: {changes_json_path} -> no email")
        return

    with open(changes_json_path, "r", encoding="utf-8") as f:
        changes = json.load(f)

    new_codes = changes.get("new_codes", []) or []
    missing_codes = changes.get("missing_codes", []) or []
    ts = changes.get("timestamp") or datetime.now(timezone.utc).isoformat()

    # Pokud nejsou změny, neodesílej
    if len(new_codes) == 0 and len(missing_codes) == 0:
        print("No changes -> email not sent.")
        return

    # SUBJECT (bez kódů)
    subject = f"{subject_prefix} – změny (nové: {len(new_codes)}, chybí: {len(missing_codes)})"

    # TEXT EMAILU (s instrukcemi)
    lines = []
    lines.append("AUTOMEGA FEED – NOTIFIKACE O ZMĚNÁCH")
    lines.append(f"Čas (UTC): {ts}")
    lines.append("")
    lines.append("------------------------------------------------------------------")
    lines.append("CO UDĚLAT V SHOPTETU / NA CARVIN.CZ")
    lines.append("------------------------------------------------------------------")
    lines.append("")
    lines.append("1) CHYBĚJÍCÍ PRODUKTY (zmizely z feedu)")
    lines.append("   - postupně vyhledejte produkty na Carvin.cz podle kódu")
    lines.append("   - u každého nastavte: Zakázat objednání")
    lines.append("   - ponechte produkt viditelný (pokud chcete zachovat SEO / URL)")
    lines.append("")
    lines.append("2) NOVÉ PRODUKTY (nově přidané ve feedu)")
    lines.append("   - postupně vyhledejte produkty na Carvin.cz podle kódu")
    lines.append("   - nastavte: Zobrazit produkt")
    lines.append("   - pokud je produkt skrytý, zařaďte ho do e-shopu")
    lines.append("   - případně vytvořte / přiřaďte kategorii")
    lines.append("")
    lines.append("------------------------------------------------------------------")
    lines.append("PŘEHLED ZMĚN (KÓDY)")
    lines.append("------------------------------------------------------------------")
    lines.append("")

    if new_codes:
        lines.append(f"NOVÉ produkty ({len(new_codes)}):")
        for c in new_codes:
            lines.append(f"- {c}")
        lines.append("")
    else:
        lines.append("NOVÉ produkty: 0")
        lines.append("")

    if missing_codes:
        lines.append(f"CHYBĚJÍCÍ produkty ({len(missing_codes)}):")
        for c in missing_codes:
            lines.append(f"- {c}")
        lines.append("")
    else:
        lines.append("CHYBĚJÍCÍ produkty: 0")
        lines.append("")

    body = "\n".join(lines)

    # sestavení emailu
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    # odeslání přes Gmail SMTP
    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as s:
        s.ehlo()
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)

    print(f"Email sent to {mail_to} with subject: {subject}")

if __name__ == "__main__":
    main()
