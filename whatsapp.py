import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import requests

from config import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    from_number: str
    text: str
    display_name: str | None = None


class WhatsAppClient:
    def __init__(self) -> None:
        if not settings.whatsapp_access_token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN is required.")
        if not settings.whatsapp_phone_number_id:
            raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID is required.")

        self._base_url = (
            f"https://graph.facebook.com/{settings.meta_graph_api_version}/"
            f"{settings.whatsapp_phone_number_id}"
        )
        self._headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body,
            },
        }
        response = requests.post(
            f"{self._base_url}/messages",
            headers=self._headers,
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            logger.error("WhatsApp send failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
        return response.json()

    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str,
        body_parameters: list[str] | None = None,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        template: dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components is not None:
            template["components"] = components
        elif body_parameters:
            template["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": parameter}
                        for parameter in body_parameters
                    ],
                }
            ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }
        response = requests.post(
            f"{self._base_url}/messages",
            headers=self._headers,
            json=payload,
            timeout=20,
        )
        if response.status_code >= 400:
            logger.error("WhatsApp template send failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
        return response.json()

    def list_templates(self) -> dict[str, Any]:
        if not settings.whatsapp_business_account_id:
            raise RuntimeError("WHATSAPP_BUSINESS_ACCOUNT_ID is required to list templates.")

        response = requests.get(
            "https://graph.facebook.com/"
            f"{settings.meta_graph_api_version}/"
            f"{settings.whatsapp_business_account_id}/message_templates",
            headers=self._headers,
            params={"fields": "name,status,category,language,components"},
            timeout=20,
        )
        if response.status_code >= 400:
            logger.error("WhatsApp template list failed: %s %s", response.status_code, response.text)
        response.raise_for_status()
        return response.json()


def verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def parse_incoming_text_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts_by_wa_id = {
                contact.get("wa_id"): contact.get("profile", {}).get("name")
                for contact in value.get("contacts", [])
            }

            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                from_number = message.get("from")
                text = message.get("text", {}).get("body")
                message_id = message.get("id")
                if not from_number or not text or not message_id:
                    continue
                messages.append(
                    IncomingMessage(
                        message_id=message_id,
                        from_number=from_number,
                        text=text,
                        display_name=contacts_by_wa_id.get(from_number),
                    )
                )

    return messages
