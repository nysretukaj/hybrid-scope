import os

# Tests must never pick up a real key from backend/.env or the shell.
os.environ["HYBRIDSCOPE_SKIP_DOTENV"] = "1"
for _key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_MODEL_LIVE",
             "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "ALERT_WEBHOOK_URL"):
    os.environ.pop(_key, None)
# ...nor a local Ollama server: tests that need it replace the client with a fake.
os.environ["OLLAMA_ENABLED"] = "0"
os.environ["IMAGE_MODEL_ENABLED"] = "0"  # no CLIP download in tests; tests that need it use a fake
