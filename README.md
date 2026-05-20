# WhatsApp Gemini Agent

A Flask-based WhatsApp Cloud API bot that receives WhatsApp messages, sends them to Gemini, and replies through Meta's official WhatsApp Cloud API.

## What You Need

- Python 3.10+
- A Meta developer app with WhatsApp added
- A WhatsApp Business Account and phone number connected in Meta
- A WhatsApp Cloud API access token
- A free Gemini API key from Google AI Studio
- A public HTTPS URL for local testing, such as ngrok or Cloudflare Tunnel

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`:

```env
WHATSAPP_VERIFY_TOKEN=make-a-random-string
WHATSAPP_ACCESS_TOKEN=your-meta-access-token
WHATSAPP_PHONE_NUMBER_ID=your-meta-phone-number-id
WHATSAPP_BUSINESS_ACCOUNT_ID=your-whatsapp-business-account-id
WHATSAPP_APP_SECRET=your-meta-app-secret-optional-but-recommended
ADMIN_API_KEY=make-a-random-admin-secret
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_FALLBACK_MODELS=gemini-2.5-flash,gemini-2.0-flash-lite,gemini-2.0-flash
BOT_SYSTEM_PROMPT=You are a helpful WhatsApp assistant. Keep replies concise, friendly, and useful.
MAX_REPLY_CHARS=3500
PROCESS_MESSAGES_ASYNC=false
```

Run the Flask app:

```powershell
python app.py
```

In another terminal, expose it publicly:

```powershell
ngrok http 5000
```

Use this callback URL in Meta:

```text
https://your-ngrok-domain.ngrok-free.app/webhook
```

Use the exact same verify token that you put in `WHATSAPP_VERIFY_TOKEN`.

## Meta Dashboard Checklist

1. Open your Meta app in Meta for Developers.
2. Add or open the WhatsApp product.
3. Copy your `Phone number ID` into `WHATSAPP_PHONE_NUMBER_ID`.
4. Generate or use an access token and put it in `WHATSAPP_ACCESS_TOKEN`.
5. Go to WhatsApp webhooks and configure:
   - Callback URL: `https://your-public-domain/webhook`
   - Verify token: the value from `WHATSAPP_VERIFY_TOKEN`
6. Subscribe to the `messages` webhook field.
7. Send a WhatsApp message to your connected business/test number.

## Sending Product Launch Templates

WhatsApp templates are required when you message a customer first or message them outside the active customer-service conversation window. Templates must be created and approved in Meta before the API can send them.

Create a template:

1. Open Meta Business Suite or Meta Developers.
2. Go to WhatsApp Manager / Message templates.
3. Create a template such as `new_product_launch`.
4. Choose the right category, usually `Marketing` for product launches.
5. Add body text, for example: `Hi {{1}}, our new {{2}} is live. Want the launch link?`
6. Submit it for approval.

Set an admin key before using the local admin endpoints:

```env
ADMIN_API_KEY=make-a-random-admin-secret
```

Restart Flask after editing `.env`.

In PowerShell, store the same admin key for test calls:

```powershell
$env:ADMIN_API_KEY="make-a-random-admin-secret"
```

List approved templates:

```powershell
Invoke-RestMethod `
  -Headers @{ "X-Admin-Api-Key" = $env:ADMIN_API_KEY } `
  http://localhost:5000/admin/templates
```

Send a template:

```powershell
$body = @{
  to = "91XXXXXXXXXX"
  template_name = "new_product_launch"
  language_code = "en_US"
  body_parameters = @("Maneesh", "Smart Bottle")
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Headers @{ "X-Admin-Api-Key" = $env:ADMIN_API_KEY } `
  -ContentType "application/json" `
  -Body $body `
  http://localhost:5000/admin/send-template
```

For templates with headers, buttons, images, or more complex variables, pass Meta-compatible `components` JSON instead of `body_parameters`.

## How It Works

- `GET /webhook` handles Meta's webhook verification challenge.
- `POST /webhook` receives WhatsApp events.
- Text messages are parsed from Meta's webhook payload.
- The app sends the conversation context to Gemini.
- The generated reply is sent back through `/{PHONE_NUMBER_ID}/messages`.
- `POST /admin/send-template` sends approved template messages.
- `GET /admin/templates` lists templates for your WhatsApp Business Account.

## Notes

- Free-form replies work inside WhatsApp's customer service conversation window. To message users first or outside the allowed window, you need approved WhatsApp message templates.
- The current memory store is in-process only. Use Redis, Postgres, or another shared store before deploying multiple workers.
- Set `WHATSAPP_APP_SECRET` in production so incoming Meta webhook signatures are verified.
- Replace temporary Meta access tokens with a production token before launch.
- The Graph API version is configurable with `META_GRAPH_API_VERSION`.

## Deploying To Render

Create a Render Web Service from this GitHub repo.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Add the same environment variables from `.env.example` in Render's Environment tab.
- After deploy, use `https://your-render-service.onrender.com/webhook` as the Meta callback URL.
- Keep `WHATSAPP_VERIFY_TOKEN` exactly the same in Render and Meta.

## Deploying To Vercel

Vercel supports Flask as a Python Function. This repo lets Vercel use its default Python runtime and installs dependencies from `requirements.txt`.

In Vercel:

1. Import this GitHub repo.
2. Keep the framework preset as Python/Other if Vercel asks.
3. Add every variable from `.env.example` in Project Settings / Environment Variables.
4. Do not upload `.env`.
5. Deploy.
6. Open `https://your-vercel-domain.vercel.app/` and check for the health JSON.
7. Set Meta's callback URL to `https://your-vercel-domain.vercel.app/webhook`.
8. Keep the same `WHATSAPP_VERIFY_TOKEN` in Vercel and Meta.

For Vercel, keep:

```env
PROCESS_MESSAGES_ASYNC=false
```

Serverless platforms may stop background work after the HTTP response is returned, so the bot handles the WhatsApp message before returning `200`.

## References

- [Gemini API quickstart](https://ai.google.dev/gemini-api/docs/quickstart)
- [Meta WhatsApp Cloud API docs](https://developers.facebook.com/docs/whatsapp/cloud-api/)
- [Meta WhatsApp messages reference](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages)

## Quick Local Smoke Test

After starting the app:

```powershell
Invoke-RestMethod http://localhost:5000/
```

Expected response:

```json
{
  "service": "whatsapp-gemini-agent",
  "status": "ok"
}
```
