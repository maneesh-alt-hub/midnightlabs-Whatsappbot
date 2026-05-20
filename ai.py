import logging

from google import genai

from config import settings
from memory import ConversationMemory


logger = logging.getLogger(__name__)


class GeminiAgent:
    def __init__(self, memory: ConversationMemory) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required.")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._memory = memory

    def reply(self, user_id: str, user_text: str, display_name: str | None = None) -> str:
        self._memory.add_user_message(user_id, user_text)
        transcript = self._memory.get_transcript(user_id)
        name_hint = f"The user's WhatsApp display name is {display_name}." if display_name else ""

        prompt = f"""
{settings.bot_system_prompt}

{name_hint}

Conversation so far:
{transcript}

Reply to the user's latest WhatsApp message. Keep the answer natural for chat.
""".strip()

        response = None
        errors: list[str] = []
        models = (settings.gemini_model, *settings.gemini_fallback_models)
        for model in dict.fromkeys(models):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                break
            except Exception as exc:
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                logger.warning("Gemini model %s failed: %s", model, exc)

        if response is None:
            logger.error("All Gemini models failed: %s", " | ".join(errors))
            text = "Sorry, the AI model is not available right now. Please try again in a minute."
            self._memory.add_assistant_message(user_id, text)
            return text

        text = (response.text or "").strip()
        if not text:
            text = "Sorry, I could not generate a reply right now. Please try again."
        if len(text) > settings.max_reply_chars:
            text = text[: settings.max_reply_chars].rstrip() + "..."
        self._memory.add_assistant_message(user_id, text)
        return text
