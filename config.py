import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    flask_host: str = os.getenv("FLASK_HOST", "0.0.0.0")
    flask_port: int = _get_int("FLASK_PORT", 5000)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    whatsapp_business_account_id: str = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
    whatsapp_app_secret: str = os.getenv("WHATSAPP_APP_SECRET", "")
    meta_graph_api_version: str = os.getenv("META_GRAPH_API_VERSION", "v25.0")
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models: tuple[str, ...] = tuple(
        model.strip()
        for model in os.getenv(
            "GEMINI_FALLBACK_MODELS",
            "gemini-flash-lite-latest,gemini-2.0-flash-lite,gemini-2.0-flash",
        ).split(",")
        if model.strip()
    )

    bot_system_prompt: str = os.getenv(
        "BOT_SYSTEM_PROMPT",
        "You are a helpful WhatsApp assistant for this agency. Keep replies concise, friendly, and useful.",
    )
    max_reply_chars: int = _get_int("MAX_REPLY_CHARS", 3500)
    process_messages_async: bool = _get_bool("PROCESS_MESSAGES_ASYNC", False)
    max_incoming_message_age_seconds: int = _get_int("MAX_INCOMING_MESSAGE_AGE_SECONDS", 300)

    agency_name: str = os.getenv("AGENCY_NAME", "Midnight Labs")
    agency_description: str = os.getenv(
        "AGENCY_DESCRIPTION",
        "a digital agency that helps clients with websites, automation, AI agents, and launch systems",
    )
    agency_services: str = os.getenv(
        "AGENCY_SERVICES",
        "websites, landing pages, WhatsApp automation, AI chatbots, product launch funnels, and custom software",
    )
    agency_contact: str = os.getenv("AGENCY_CONTACT", "Reply here and our team will follow up.")
    agency_booking_link: str = os.getenv("AGENCY_BOOKING_LINK", "")
    agency_portfolio_link: str = os.getenv("AGENCY_PORTFOLIO_LINK", "")


settings = Settings()
