import os
import sys
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

CHANGES_JSON = os.environ.get("CHANGES_JSON", "data/automega_changes.json")
CHANGES_MD = os.environ.get("CHANGES_MD", "data/automega_changes.md")

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587").strip())
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()

MAIL_TO = os.environ.get("MAIL_TO", "").strip()
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER).strip()

SUBJECT_PREFIX = os.environ.get("SUBJECT_PREFIX", "Automega feed změny").strip()

missing = [k for k, v in {
    "SMTP_HOST": SMTP_HOST,
    "SMTP_PORT": SMTP_PORT,
    "SMTP_USER": SMTP_USER,
    "SMTP_PASS": SMTP_PASS,
    "MAIL_TO": MAIL_TO,
    "MAIL_FROM": MAIL_FROM,
}.items() if not v]
if missing:
    print("Missing env vars: " + ", ".join(missing), file=sys.stderr)
    sys.exit(2)

changes_path = Path(CHANGES_JSON)
if not changes_path.exists():
    print(f"Missing changes file: {CHANGES_JSON}", file=sys.stderr)
    sys.exit(3)

changes = json.loads(changes_path.read_text(encoding="utf-8"))
new_codes = changes.get("new_codes", []) or []
missing_codes = changes.get("missing_codes", []) or []
ts = changes.get("timestamp_utc", "")

if len(new_codes) == 0 and len(missing_codes) == 0:
    print("No changes -> email not sent.")
    sys.exit(0)

body = Path(CHANGES_MD).read_text(encoding="utf-8") if Path(CHANGES_MD).exists() else json.dumps(changes, indent=2, ensure_ascii=False)

subject = f"{SUBJECT_PREFIX} (nové: {len(new_codes)}, zmizelé: {len(missing_codes)})"
if ts:
    subject += f" | {ts}"

msg = EmailMessage()
msg["From"] = MAIL_FROM
msg["To"] = MAIL_TO
msg["Subject"] = subject
msg.set_content(body)

with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
    server.ehlo()
    try:
        server.starttls()
        server.ehlo()
    except Exception:
        pass
    server.login(SMTP_USER, SMTP_PASS)
    server.send_message(msg)

print(f"Email sent to {MAIL_TO}")
