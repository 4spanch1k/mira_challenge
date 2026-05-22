import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw_value: str) -> set[int]:
    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        value = item.strip()
        if value.isdigit():
            admin_ids.add(int(value))
    return admin_ids


@dataclass(frozen=True)
class Settings:
    bot_token: str
    mira_link: str
    db_path: str
    admin_ids: set[int]
    bot_username: str
    webapp_url: str
    groq_api_key: str
    groq_vision_model: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Fill it in .env")

    return Settings(
        bot_token=bot_token,
        mira_link=os.getenv("MIRA_LINK", "https://t.me/Mira").strip(),
        db_path=os.getenv("DB_PATH", "mira_challenge.db").strip(),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        bot_username=os.getenv("BOT_USERNAME", "").strip(),
        webapp_url=os.getenv("WEBAPP_URL", "").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_vision_model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip(),
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "screenshots").strip(),
    )


settings = load_settings()
