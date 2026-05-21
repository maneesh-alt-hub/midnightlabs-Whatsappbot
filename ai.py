import logging
import re

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
        self._selected_topics: dict[str, str] = {}

    def reply(self, user_id: str, user_text: str, display_name: str | None = None) -> str:
        self._memory.add_user_message(user_id, user_text)
        routed_reply = self._route_agency_message(user_id, user_text, display_name)
        if routed_reply:
            self._memory.add_assistant_message(user_id, routed_reply)
            return routed_reply

        transcript = self._memory.get_transcript(user_id)
        name_hint = f"The user's WhatsApp display name is {display_name}." if display_name else ""
        selected_topic = self._selected_topics.get(user_id, "agency general")

        prompt = f"""
{settings.bot_system_prompt}

You represent {settings.agency_name}, {settings.agency_description}.
Agency services: {settings.agency_services}.
The user's selected topic is: {selected_topic}.

Strict rules:
- Only answer questions about {settings.agency_name}, its services, pricing process, project discovery, support, portfolio, product launches, WhatsApp automation, AI agents, websites, or working with the agency.
- Do not answer general knowledge, coding, homework, politics, entertainment, medical, legal, financial, or unrelated questions.
- If the user asks something unrelated, politely say you can only help with {settings.agency_name} agency-related questions and show the menu.
- Do not invent exact prices, guarantees, or portfolio items. Ask for project details or direct the user to a human when needed.
- Keep WhatsApp replies short and easy to scan.

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
            text = self._fallback_for_topic(user_id)
            self._memory.add_assistant_message(user_id, text)
            return text

        text = (response.text or "").strip()
        if not text:
            text = "Sorry, I could not generate a reply right now. Please try again."
        if len(text) > settings.max_reply_chars:
            text = text[: settings.max_reply_chars].rstrip() + "..."
        self._memory.add_assistant_message(user_id, text)
        return text

    def _route_agency_message(
        self,
        user_id: str,
        user_text: str,
        display_name: str | None = None,
    ) -> str | None:
        text = user_text.strip()
        normalized = re.sub(r"\s+", " ", text.lower())

        if normalized in {"hi", "hii", "hiii", "hello", "hey", "start", "menu", "help"}:
            self._selected_topics.pop(user_id, None)
            return self._menu(display_name)

        if normalized in {"back", "main menu", "options"}:
            self._selected_topics.pop(user_id, None)
            return self._menu(display_name)

        selected_topic = self._match_topic(normalized)
        if selected_topic:
            self._selected_topics[user_id] = selected_topic
            return self._topic_intro(selected_topic)

        if self._looks_unrelated(normalized):
            return self._agency_only_reply()

        if user_id not in self._selected_topics:
            return (
                f"I can help with {settings.agency_name} agency-related questions only. "
                "Please choose an option first:\n\n"
                f"{self._menu()}"
            )

        return None

    def _match_topic(self, normalized: str) -> str | None:
        if normalized in {"1", "one"} or any(word in normalized for word in ["service", "offer", "website", "chatbot", "automation"]):
            return "services"
        if normalized in {"2", "two"} or any(word in normalized for word in ["price", "pricing", "cost", "package", "budget"]):
            return "pricing"
        if normalized in {"3", "three"} or any(word in normalized for word in ["start", "new project", "build", "hire", "quote"]):
            return "new_project"
        if normalized in {"4", "four"} or any(word in normalized for word in ["support", "issue", "bug", "existing", "maintenance"]):
            return "support"
        if normalized in {"5", "five"} or any(word in normalized for word in ["portfolio", "case stud", "work", "examples"]):
            return "portfolio"
        if normalized in {"6", "six"} or any(word in normalized for word in ["human", "person", "call", "team", "contact"]):
            return "human"
        return None

    def _menu(self, display_name: str | None = None) -> str:
        greeting = f"Hi {display_name}!" if display_name else "Hi!"
        return (
            f"{greeting} Welcome to {settings.agency_name}. Please choose an option:\n\n"
            "1. Services we offer\n"
            "2. Pricing / package fit\n"
            "3. Start a new project\n"
            "4. Existing project support\n"
            "5. Portfolio / case studies\n"
            "6. Talk to a human\n\n"
            "Reply with a number."
        )

    def _topic_intro(self, topic: str) -> str:
        if topic == "services":
            return (
                f"{settings.agency_name} helps with {settings.agency_services}.\n\n"
                "What are you trying to build or improve?"
            )
        if topic == "pricing":
            return (
                "Pricing depends on scope, timeline, and complexity. "
                "Tell me what you need, your target launch date, and your rough budget range."
            )
        if topic == "new_project":
            return (
                "Great. To start a new project, send:\n"
                "1. What you want built\n"
                "2. Your goal\n"
                "3. Timeline\n"
                "4. Budget range"
            )
        if topic == "support":
            return (
                "Sure. Please describe the issue, share the project name, and tell me what changed recently."
            )
        if topic == "portfolio":
            if settings.agency_portfolio_link:
                return f"You can view our work here: {settings.agency_portfolio_link}\n\nWhat kind of example are you looking for?"
            return "Tell me what kind of work you want to see: websites, automations, AI agents, or launch funnels."
        if topic == "human":
            message = settings.agency_contact
            if settings.agency_booking_link:
                message += f"\n\nBook a call: {settings.agency_booking_link}"
            return message
        return self._menu()

    def _agency_only_reply(self) -> str:
        return (
            f"I can only help with {settings.agency_name} agency-related questions here.\n\n"
            "Please choose:\n"
            "1. Services\n"
            "2. Pricing\n"
            "3. New project\n"
            "4. Support\n"
            "5. Portfolio\n"
            "6. Human"
        )

    def _looks_unrelated(self, normalized: str) -> bool:
        unrelated_patterns = [
            "weather",
            "news",
            "movie",
            "song",
            "lyrics",
            "homework",
            "solve this",
            "write code",
            "python",
            "javascript",
            "politics",
            "medical",
            "doctor",
            "legal",
            "stock",
            "crypto",
        ]
        return any(pattern in normalized for pattern in unrelated_patterns)

    def _fallback_for_topic(self, user_id: str) -> str:
        topic = self._selected_topics.get(user_id)
        if topic == "services":
            return (
                "Got it. We can help scope this under our services. "
                "Please share your goal, deadline, and any reference links."
            )
        if topic == "pricing":
            return (
                "Thanks. To estimate pricing, please send the project scope, deadline, "
                "must-have features, and rough budget range."
            )
        if topic == "new_project":
            return (
                "Thanks, we can help with that. Please send:\n"
                "1. What you want built\n"
                "2. Main goal\n"
                "3. Timeline\n"
                "4. Budget range\n"
                "5. Any reference links"
            )
        if topic == "support":
            return (
                "Thanks. Please send the project name, the issue, screenshots if any, "
                "and when it started."
            )
        if topic == "portfolio":
            if settings.agency_portfolio_link:
                return f"Our portfolio is here: {settings.agency_portfolio_link}"
            return "Tell me which type of work you want to see: websites, automation, AI agents, or launch funnels."
        if topic == "human":
            return self._topic_intro("human")
        return self._agency_only_reply()
