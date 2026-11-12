import os

# Tests must never pick up a real key from backend/.env or the shell.
os.environ["HYBRIDSCOPE_SKIP_DOTENV"] = "1"
for _key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_MODEL_LIVE",
             "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "ALERT_WEBHOOK_URL"):
    os.environ.pop(_key, None)
