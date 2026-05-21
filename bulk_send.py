import argparse
import csv
import logging
import time
from pathlib import Path

from whatsapp import WhatsAppClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send an approved WhatsApp template to opted-in contacts from a CSV."
    )
    parser.add_argument("--csv", required=True, help="CSV path with phone,name,opt_in columns.")
    parser.add_argument("--template", required=True, help="Approved WhatsApp template name.")
    parser.add_argument("--language", default="en_US", help="Template language code.")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between sends. Keep this conservative.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum contacts to send. 0 means no limit.")
    parser.add_argument("--dry-run", action="store_true", help="Print recipients without sending.")
    args = parser.parse_args()

    contacts = load_contacts(Path(args.csv))
    if args.limit:
        contacts = contacts[: args.limit]

    logger.info("Prepared %s opted-in contacts.", len(contacts))
    if args.dry_run:
        for contact in contacts:
            logger.info("DRY RUN: %s %s", contact["phone"], contact.get("name", ""))
        return

    client = WhatsAppClient()
    sent = 0
    failed = 0
    for contact in contacts:
        phone = contact["phone"]
        name = contact.get("name") or "there"
        try:
            client.send_template(
                to=phone,
                template_name=args.template,
                language_code=args.language,
                body_parameters=[name],
            )
            sent += 1
            logger.info("Sent template to %s", phone)
        except Exception as exc:
            failed += 1
            logger.error("Failed to send template to %s: %s", phone, exc)
        time.sleep(args.delay)

    logger.info("Done. sent=%s failed=%s", sent, failed)


def load_contacts(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"phone", "opt_in"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            opt_in = (row.get("opt_in") or "").strip().lower()
            if opt_in not in {"yes", "true", "1"}:
                continue
            phone = normalize_phone(row.get("phone", ""))
            if not phone:
                continue
            rows.append({"phone": phone, "name": (row.get("name") or "").strip()})
    return rows


def normalize_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if len(digits) < 8 or len(digits) > 15:
        return ""
    return digits


if __name__ == "__main__":
    main()
