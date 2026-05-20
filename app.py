import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from flask import Flask, Response, jsonify, request

from ai import GeminiAgent
from config import settings
from memory import ConversationMemory
from whatsapp import WhatsAppClient, parse_incoming_text_messages, verify_meta_signature


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)
memory = ConversationMemory()
processed_message_ids: set[str] = set()
processed_lock = Lock()


def get_agent() -> GeminiAgent:
    if "agent" not in app.config:
        app.config["agent"] = GeminiAgent(memory)
    return app.config["agent"]


def get_whatsapp_client() -> WhatsAppClient:
    if "whatsapp_client" not in app.config:
        app.config["whatsapp_client"] = WhatsAppClient()
    return app.config["whatsapp_client"]


@app.get("/")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok", "service": "whatsapp-gemini-agent"}, 200


@app.get("/admin/templates")
def list_templates() -> tuple[Response, int] | Response:
    auth_error = require_admin()
    if auth_error:
        return auth_error

    templates = get_whatsapp_client().list_templates()
    return jsonify(templates), 200


@app.post("/admin/send-template")
def send_template() -> tuple[Response, int] | Response:
    auth_error = require_admin()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    to = payload.get("to")
    template_name = payload.get("template_name")
    language_code = payload.get("language_code", "en_US")
    body_parameters = payload.get("body_parameters")
    components = payload.get("components")

    if not to or not template_name:
        return jsonify({"error": "to and template_name are required"}), 400
    if body_parameters is not None and not isinstance(body_parameters, list):
        return jsonify({"error": "body_parameters must be a list"}), 400
    if components is not None and not isinstance(components, list):
        return jsonify({"error": "components must be a list"}), 400

    result = get_whatsapp_client().send_template(
        to=to,
        template_name=template_name,
        language_code=language_code,
        body_parameters=body_parameters,
        components=components,
    )
    return jsonify(result), 200


@app.get("/webhook")
def verify_webhook() -> Response:
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == settings.whatsapp_verify_token and challenge:
        logger.info("WhatsApp webhook verified.")
        return Response(challenge, status=200, mimetype="text/plain")

    logger.warning("WhatsApp webhook verification failed.")
    return Response("Forbidden", status=403)


@app.post("/webhook")
def receive_webhook() -> Response | tuple[Response, int]:
    raw_body = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(raw_body, signature):
        logger.warning("Rejected webhook with invalid Meta signature.")
        return Response("Forbidden", status=403)

    payload = request.get_json(silent=True) or {}
    incoming_messages = parse_incoming_text_messages(payload)
    for incoming in incoming_messages:
        if mark_processed(incoming.message_id):
            if settings.process_messages_async:
                executor.submit(handle_message, incoming)
            else:
                handle_message(incoming)

    return jsonify({"status": "received"}), 200


def mark_processed(message_id: str) -> bool:
    with processed_lock:
        if message_id in processed_message_ids:
            return False
        processed_message_ids.add(message_id)
    return True


def require_admin() -> tuple[Response, int] | None:
    if not settings.admin_api_key:
        return jsonify({"error": "ADMIN_API_KEY is not configured"}), 503

    received_key = request.headers.get("X-Admin-Api-Key")
    if received_key != settings.admin_api_key:
        return jsonify({"error": "Unauthorized"}), 401

    return None


def handle_message(incoming) -> None:
    try:
        logger.info("Incoming WhatsApp message from %s: %s", incoming.from_number, incoming.text)
        reply = get_agent().reply(
            user_id=incoming.from_number,
            user_text=incoming.text,
            display_name=incoming.display_name,
        )
        get_whatsapp_client().send_text(incoming.from_number, reply)
        logger.info("Sent WhatsApp reply to %s", incoming.from_number)
    except Exception:
        logger.exception("Failed to process incoming WhatsApp message.")


if __name__ == "__main__":
    app.run(host=settings.flask_host, port=settings.flask_port)
