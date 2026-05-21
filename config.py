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
    )


settings = load_settings()
