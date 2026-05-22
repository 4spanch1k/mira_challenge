import asyncio
import base64
import html
import json
import logging
import uuid
from datetime import UTC, datetime
from io import BytesIO
from typing import Optional

import aiosqlite
import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from config import settings

BOT_TOKEN = settings.bot_token
MIRA_LINK = settings.mira_link
DB_PATH = settings.db_path
ADMIN_IDS = settings.admin_ids
WEBAPP_URL = settings.webapp_url
GROQ_API_KEY = settings.groq_api_key
GROQ_VISION_MODEL = settings.groq_vision_model
SUPABASE_URL = settings.supabase_url
SUPABASE_SERVICE_ROLE_KEY = settings.supabase_service_role_key
SUPABASE_STORAGE_BUCKET = settings.supabase_storage_bucket

logging.basicConfig(level=logging.INFO)
router = Router()

PROMPTS = {
    "channel_audit": {
        "title": "📱 Разбор Telegram-канала",
        "short": "Найти слабые места, идеи постов и офферы",
        "prompt": """Мира, выступи как маркетолог и редактор Telegram-каналов.

Проанализируй мой канал по пунктам:
1. позиционирование;
2. описание;
3. контент;
4. доверие;
5. вовлечение;
6. монетизация.

Дай:
— 5 слабых мест;
— 10 идей постов;
— 3 оффера;
— контент-план на 7 дней;
— что изменить сегодня, чтобы канал выглядел сильнее.

Моя ниша: [вставь нишу]
Моя аудитория: [вставь ЦА]
Описание канала: [вставь описание]""",
    },
    "content_plan": {
        "title": "📊 Контент-план на 7 дней",
        "short": "Темы, хуки, форматы и CTA",
        "prompt": """Мира, выступи как SMM-стратег.

Сделай мне контент-план на 7 дней для моей ниши.

Дай:
— темы постов;
— короткие хуки;
— формат каждого поста;
— цель поста;
— CTA;
— идеи для Reels/TikTok/Stories.

Моя ниша: [вставь нишу]
Моя аудитория: [вставь ЦА]
Что я продаю/продвигаю: [вставь продукт]""",
    },
    "offer": {
        "title": "💸 Продающий оффер",
        "short": "Упаковать продукт так, чтобы хотелось купить",
        "prompt": """Мира, выступи как маркетолог прямого отклика.

Помоги мне упаковать оффер так, чтобы человек понял ценность за 10 секунд.

Дай:
— 5 вариантов сильного оффера;
— боли аудитории;
— желаемый результат клиента;
— почему стоит купить сейчас;
— короткий продающий текст;
— CTA.

Мой продукт/услуга: [вставь]
ЦА: [вставь]
Цена/формат: [вставь]""",
    },
    "exam": {
        "title": "🧠 Подготовка к экзамену",
        "short": "План, объяснение, тесты и шпаргалка",
        "prompt": """Мира, выступи как личный преподаватель.

Помоги мне подготовиться к экзамену по теме: [вставь тему].

Дай:
— объяснение простыми словами;
— план подготовки на 7 дней;
— главные термины;
— 10 тестовых вопросов;
— типичные ошибки;
— короткую шпаргалку для повторения.""",
    },
    "profile": {
        "title": "🧑‍💻 Резюме / профиль",
        "short": "Упаковка себя, bio, отклик, позиционирование",
        "prompt": """Мира, выступи как карьерный консультант и копирайтер.

Помоги мне упаковать резюме или профиль.

Дай:
— сильное описание обо мне;
— 5 вариантов bio;
— список сильных сторон;
— как лучше описать опыт;
— текст для отклика клиенту/работодателю;
— что улучшить в позиционировании.

Моя сфера: [вставь]
Мой опыт: [вставь]
Кого хочу привлечь: [вставь]""",
    },
}

DEFAULT_CAMPAIGN_ID = 1


class UploadScreenshot(StatesGroup):
    waiting_for_screenshot = State()


class CreateCampaign(StatesGroup):
    waiting_for_niche = State()
    waiting_for_audience = State()
    waiting_for_goal = State()
    waiting_for_platform = State()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def normalize_bot_username() -> str:
    username = settings.bot_username.strip()
    return username[1:] if username.startswith("@") else username


def campaign_link(campaign_id: int) -> str:
    username = normalize_bot_username() or "mira_challenge_bot"
    return f"https://t.me/{username}?start=challenge_{campaign_id}"


def build_default_post_text() -> str:
    return (
        "🚀 Запускаем Mira 2-Minute Challenge\n\n"
        "Суть простая: выбираешь задачу, получаешь готовый промпт, открываешь Mira "
        "и за 2 минуты получаешь результат.\n\n"
        "Можно сделать:\n"
        "— контент-план на неделю;\n"
        "— разбор Telegram-канала;\n"
        "— продающий оффер;\n"
        "— план подготовки к экзамену;\n"
        "— упаковку резюме или профиля.\n\n"
        f"Старт здесь:\n{campaign_link(DEFAULT_CAMPAIGN_ID)}\n\n"
        "Лучшие результаты попадут в подборку дня."
    )


def generate_campaign_title(niche: str) -> str:
    return f"Mira Challenge для {niche.strip()}"


def generate_campaign_prompts(niche: str, audience: str, goal: str) -> list[dict]:
    return [
        {
            "prompt_key": "quick_audit",
            "title": "🔎 Быстрый разбор",
            "short": "Найти слабые места и точки роста",
            "prompt_text": f"""Мира, выступи как эксперт в нише {niche}.
Проанализируй ситуацию для аудитории: {audience}.
Цель: {goal}.

Дай:
— 5 слабых мест;
— 5 точек роста;
— 3 быстрых действия на сегодня;
— что можно улучшить за 2 минуты.""",
        },
        {
            "prompt_key": "seven_day_plan",
            "title": "📅 План на 7 дней",
            "short": "Пошаговый план под цель",
            "prompt_text": f"""Мира, составь план на 7 дней для аудитории: {audience}.
Ниша: {niche}.
Цель: {goal}.

Дай:
— задачу на каждый день;
— что сделать;
— какой результат должен получиться;
— как проверить прогресс.""",
        },
        {
            "prompt_key": "content_ideas",
            "title": "💡 Идеи контента",
            "short": "Темы, хуки и CTA",
            "prompt_text": f"""Мира, придумай идеи контента для ниши {niche}.
Аудитория: {audience}.
Цель контента: {goal}.

Дай:
— 10 идей постов;
— 10 хуков;
— 5 коротких CTA;
— 3 идеи для Reels/TikTok/Stories.""",
        },
        {
            "prompt_key": "offer",
            "title": "💸 Оффер",
            "short": "Упаковать ценность в понятный оффер",
            "prompt_text": f"""Мира, помоги упаковать оффер для аудитории: {audience}.
Ниша: {niche}.
Цель: {goal}.

Дай:
— 5 вариантов оффера;
— боли аудитории;
— желаемый результат;
— почему стоит действовать сейчас;
— короткий продающий текст.""",
        },
        {
            "prompt_key": "checklist",
            "title": "✅ Чеклист",
            "short": "Список действий без воды",
            "prompt_text": f"""Мира, сделай практический чеклист для аудитории: {audience}.
Ниша: {niche}.
Цель: {goal}.

Дай:
— 10 конкретных шагов;
— что сделать первым;
— типичные ошибки;
— быстрый результат за 2 минуты.""",
        },
    ]


def generate_post_text(title: str, audience: str, challenge_link: str) -> str:
    return f"""Запускаем мини-челлендж: {title}

Суть простая:
выбираешь задачу → получаешь готовый промпт → открываешь Mira → получаешь результат за 2 минуты.

Для кого:
{audience}

Что можно сделать:
— быстрый разбор;
— план на 7 дней;
— идеи контента;
— оффер;
— чеклист.

Старт здесь:
{challenge_link}

Лучшие результаты попадут в подборку дня."""


async def ensure_default_campaign(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("SELECT id FROM campaigns WHERE id = ?", (DEFAULT_CAMPAIGN_ID,))
    exists = await cursor.fetchone()
    now = now_iso()
    if not exists:
        await db.execute(
            """
            INSERT INTO campaigns (id, creator_id, title, niche, audience, goal, platform, post_text, cta, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_CAMPAIGN_ID,
                None,
                "Mira 2-Minute Challenge",
                "AI productivity",
                "Telegram users",
                "Помочь пользователю получить быстрый результат в Mira за 2 минуты",
                "Telegram",
                build_default_post_text(),
                "Выбери задачу и сделай результат в Mira за 2 минуты",
                now,
                now,
            ),
        )

    cursor = await db.execute("SELECT COUNT(*) FROM campaign_prompts WHERE campaign_id = ?", (DEFAULT_CAMPAIGN_ID,))
    prompt_count = (await cursor.fetchone())[0]
    if prompt_count == 0:
        for index, (prompt_key, data) in enumerate(PROMPTS.items(), start=1):
            await db.execute(
                """
                INSERT INTO campaign_prompts (campaign_id, prompt_key, title, short, prompt_text, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (DEFAULT_CAMPAIGN_ID, prompt_key, data["title"], data["short"], data["prompt"], index, now),
            )


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


async def supabase_request(method: str, path: str, *, json_body: Optional[dict | list] = None, data: Optional[bytes] = None, headers: Optional[dict] = None) -> Optional[dict | list]:
    if not supabase_enabled():
        return None

    request_headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    if json_body is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})

    url = f"{SUPABASE_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json_body, data=data, headers=request_headers, timeout=20) as response:
                text = await response.text()
                if response.status >= 400:
                    logging.warning("Supabase request failed: %s %s %s", method, path, text[:500])
                    return None
                if not text:
                    return None
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None
    except aiohttp.ClientError as error:
        logging.warning("Supabase request error: %s %s %s", method, path, error)
        return None


async def supabase_insert(table: str, payload: dict) -> None:
    await supabase_request(
        "POST",
        f"/rest/v1/{table}",
        json_body=payload,
        headers={"Prefer": "return=minimal"},
    )


async def supabase_upsert(table: str, payload: dict, conflict_key: str) -> None:
    await supabase_request(
        "POST",
        f"/rest/v1/{table}?on_conflict={conflict_key}",
        json_body=payload,
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
    )


async def upload_screenshot_to_supabase(telegram_id: int, file_id: str, image_bytes: bytes, mime_type: str) -> Optional[str]:
    if not supabase_enabled():
        return None

    extension = "png" if mime_type == "image/png" else "jpg"
    path = f"{telegram_id}/{uuid.uuid4().hex}-{file_id[:10]}.{extension}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{path}",
                data=image_bytes,
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": mime_type,
                    "x-upsert": "false",
                },
                timeout=30,
            ) as response:
                if response.status >= 400:
                    logging.warning("Supabase storage upload failed: %s", (await response.text())[:500])
                    return None
    except aiohttp.ClientError as error:
        logging.warning("Supabase storage upload error: %s", error)
        return None

    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{path}"


async def verify_screenshot_with_groq(image_bytes: bytes, mime_type: str, prompt_id: str, image_url: Optional[str] = None) -> dict:
    if not GROQ_API_KEY:
        return {
            "status": "skipped",
            "accepted": True,
            "confidence": 0,
            "reason": "Groq API key is not configured.",
        }

    task = PROMPTS.get(prompt_id, {})
    if image_url:
        image_source = image_url
    else:
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        image_source = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You verify screenshots for a Telegram challenge. "
                    "Return strict JSON only with keys: accepted boolean, confidence number 0..1, reason string. "
                    "Accept only if the image appears to be a real AI/Mira answer screen or AI chat result related to the task. "
                    "Reject random photos, unrelated app screenshots, blank screens, memes, and images without visible generated text/result."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Task id: {prompt_id}\n"
                            f"Task title: {task.get('title', prompt_id)}\n"
                            f"Task short: {task.get('short', '')}\n"
                            "Does this screenshot show a real completed result for this task?"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": image_source}},
                ],
            },
        ],
        "temperature": 0,
        "max_completion_tokens": 300,
        "response_format": {"type": "json_object"},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    logging.warning("Groq verification failed: %s", text[:500])
                    return {"status": "error", "accepted": False, "confidence": 0, "reason": "Groq verification failed."}
                body = json.loads(text)
                content = body["choices"][0]["message"]["content"]
                result = json.loads(content)
                return {
                    "status": "verified",
                    "accepted": bool(result.get("accepted")),
                    "confidence": float(result.get("confidence", 0)),
                    "reason": str(result.get("reason", ""))[:500],
                }
    except (aiohttp.ClientError, KeyError, ValueError, json.JSONDecodeError) as error:
        logging.warning("Groq verification error: %s", error)
        return {"status": "error", "accepted": False, "confidence": 0, "reason": "Groq verification error."}


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        async def add_column_if_missing(table: str, column: str, definition: str) -> None:
            cursor = await db.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in await cursor.fetchall()}
            if column not in columns:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                source TEXT,
                active_campaign_id INTEGER,
                role TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                event TEXT,
                prompt_id TEXT,
                campaign_id INTEGER,
                source TEXT,
                meta TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                campaign_id INTEGER,
                prompt_id TEXT,
                file_id TEXT,
                file_type TEXT,
                caption TEXT,
                status TEXT,
                verification_status TEXT,
                verification_reason TEXT,
                verification_confidence REAL,
                screenshot_url TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_uploads (
                telegram_id INTEGER PRIMARY KEY,
                campaign_id INTEGER,
                prompt_id TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                title TEXT,
                niche TEXT,
                audience TEXT,
                goal TEXT,
                platform TEXT,
                post_text TEXT,
                cta TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaign_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                prompt_key TEXT,
                title TEXT,
                short TEXT,
                prompt_text TEXT,
                sort_order INTEGER,
                created_at TEXT
            )
        """)
        await add_column_if_missing("users", "active_campaign_id", "INTEGER")
        await add_column_if_missing("users", "role", "TEXT")
        await add_column_if_missing("events", "campaign_id", "INTEGER")
        await add_column_if_missing("submissions", "campaign_id", "INTEGER")
        await add_column_if_missing("submissions", "verification_status", "TEXT")
        await add_column_if_missing("submissions", "verification_reason", "TEXT")
        await add_column_if_missing("submissions", "verification_confidence", "REAL")
        await add_column_if_missing("submissions", "screenshot_url", "TEXT")
        await add_column_if_missing("pending_uploads", "campaign_id", "INTEGER")
        await ensure_default_campaign(db)
        await db.execute("UPDATE users SET active_campaign_id = ? WHERE active_campaign_id IS NULL", (DEFAULT_CAMPAIGN_ID,))
        await db.execute("UPDATE events SET campaign_id = ? WHERE campaign_id IS NULL", (DEFAULT_CAMPAIGN_ID,))
        await db.execute("UPDATE submissions SET campaign_id = ? WHERE campaign_id IS NULL", (DEFAULT_CAMPAIGN_ID,))
        await db.execute("UPDATE pending_uploads SET campaign_id = ? WHERE campaign_id IS NULL", (DEFAULT_CAMPAIGN_ID,))
        await db.commit()


async def upsert_user(message: Message, source: Optional[str] = None) -> None:
    user = message.from_user
    if not user:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT source FROM users WHERE telegram_id = ?", (user.id,))
        row = await cursor.fetchone()
        old_source = row[0] if row else None
        final_source = old_source or source or "direct"

        await db.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, source, active_campaign_id, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, COALESCE(?, ?), COALESCE(?, 'participant'), ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                source = users.source,
                active_campaign_id = COALESCE(users.active_campaign_id, excluded.active_campaign_id),
                role = COALESCE(users.role, excluded.role),
                updated_at = excluded.updated_at
            """,
            (user.id, user.username, user.first_name, final_source, DEFAULT_CAMPAIGN_ID, DEFAULT_CAMPAIGN_ID, None, now_iso(), now_iso()),
        )
        await db.commit()
    await supabase_upsert(
        "users",
        {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "source": final_source,
            "active_campaign_id": DEFAULT_CAMPAIGN_ID,
            "role": "participant",
            "updated_at": now_iso(),
        },
        "telegram_id",
    )


async def set_user_role(telegram_id: int, role: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET role = ?, updated_at = ? WHERE telegram_id = ?", (role, now_iso(), telegram_id))
        await db.commit()


async def set_active_campaign(telegram_id: int, campaign_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET active_campaign_id = ?, updated_at = ? WHERE telegram_id = ?",
            (campaign_id, now_iso(), telegram_id),
        )
        await db.commit()


async def get_active_campaign_id(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT active_campaign_id FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return int(row[0]) if row and row[0] else DEFAULT_CAMPAIGN_ID


async def get_user_source(telegram_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT source FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] else "direct"


async def add_event(
    telegram_id: int,
    event: str,
    prompt_id: Optional[str] = None,
    meta: Optional[dict] = None,
    campaign_id: Optional[int] = None,
) -> None:
    source = await get_user_source(telegram_id)
    final_campaign_id = campaign_id or await get_active_campaign_id(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO events (telegram_id, event, prompt_id, campaign_id, source, meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, event, prompt_id, final_campaign_id, source, json.dumps(meta or {}, ensure_ascii=False), now_iso()),
        )
        await db.commit()
    await supabase_insert(
        "events",
        {
            "telegram_id": telegram_id,
            "event": event,
            "prompt_id": prompt_id,
            "campaign_id": final_campaign_id,
            "source": source,
            "meta": meta or {},
            "created_at": now_iso(),
        },
    )


async def set_pending_upload(telegram_id: int, campaign_id: int, prompt_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO pending_uploads (telegram_id, campaign_id, prompt_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                campaign_id = excluded.campaign_id,
                prompt_id = excluded.prompt_id,
                created_at = excluded.created_at
            """,
            (telegram_id, campaign_id, prompt_id, now_iso()),
        )
        await db.commit()


async def get_pending_upload(telegram_id: int) -> Optional[tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT campaign_id, prompt_id FROM pending_uploads WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return (int(row[0]) if row[0] else DEFAULT_CAMPAIGN_ID, row[1])


async def clear_pending_upload(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_uploads WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


async def save_submission(
    telegram_id: int,
    campaign_id: int,
    prompt_id: str,
    file_id: str,
    file_type: str,
    caption: Optional[str],
    status: str,
    verification: dict,
    screenshot_url: Optional[str],
) -> None:
    created_at = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO submissions (
                telegram_id, campaign_id, prompt_id, file_id, file_type, caption, status,
                verification_status, verification_reason, verification_confidence, screenshot_url, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                campaign_id,
                prompt_id,
                file_id,
                file_type,
                caption,
                status,
                verification.get("status"),
                verification.get("reason"),
                verification.get("confidence"),
                screenshot_url,
                created_at,
            ),
        )
        await db.commit()

    await supabase_insert(
        "submissions",
        {
            "telegram_id": telegram_id,
            "campaign_id": campaign_id,
            "prompt_id": prompt_id,
            "file_id": file_id,
            "file_type": file_type,
            "caption": caption,
            "status": status,
            "verification_status": verification.get("status"),
            "verification_reason": verification.get("reason"),
            "verification_confidence": verification.get("confidence"),
            "screenshot_url": screenshot_url,
            "created_at": created_at,
        },
    )
    await add_event(
        telegram_id,
        "screenshot_uploaded" if status == "accepted" else "screenshot_rejected",
        prompt_id,
        {"file_type": file_type, "verification": verification, "screenshot_url": screenshot_url},
        campaign_id=campaign_id,
    )


async def get_campaign(campaign_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_campaign_prompts(campaign_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM campaign_prompts
            WHERE campaign_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (campaign_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_campaign_prompt(campaign_id: int, prompt_key: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM campaign_prompts
            WHERE campaign_id = ? AND prompt_key = ?
            LIMIT 1
            """,
            (campaign_id, prompt_key),
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        cursor = await db.execute(
            """
            SELECT *
            FROM campaign_prompts
            WHERE campaign_id = ? AND prompt_key = ?
            LIMIT 1
            """,
            (DEFAULT_CAMPAIGN_ID, prompt_key),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_campaign(creator_id: int, niche: str, audience: str, goal: str, platform: str) -> int:
    title = generate_campaign_title(niche)
    cta = "Выбери задачу и получи результат в Mira за 2 минуты"
    now = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO campaigns (creator_id, title, niche, audience, goal, platform, post_text, cta, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (creator_id, title, niche, audience, goal, platform, "", cta, now, now),
        )
        campaign_id = cursor.lastrowid
        link = campaign_link(campaign_id)
        post_text = generate_post_text(title, audience, link)
        await db.execute("UPDATE campaigns SET post_text = ? WHERE id = ?", (post_text, campaign_id))
        generated_prompts = generate_campaign_prompts(niche, audience, goal)
        for index, data in enumerate(generated_prompts, start=1):
            await db.execute(
                """
                INSERT INTO campaign_prompts (campaign_id, prompt_key, title, short, prompt_text, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (campaign_id, data["prompt_key"], data["title"], data["short"], data["prompt_text"], index, now),
            )
        await db.commit()

    await supabase_insert(
        "campaigns",
        {
            "id": campaign_id,
            "creator_id": creator_id,
            "title": title,
            "niche": niche,
            "audience": audience,
            "goal": goal,
            "platform": platform,
            "post_text": post_text,
            "cta": cta,
            "created_at": now,
            "updated_at": now,
        },
    )
    for index, data in enumerate(generated_prompts, start=1):
        await supabase_insert(
            "campaign_prompts",
            {
                "campaign_id": campaign_id,
                "prompt_key": data["prompt_key"],
                "title": data["title"],
                "short": data["short"],
                "prompt_text": data["prompt_text"],
                "sort_order": index,
                "created_at": now,
            },
        )
    return campaign_id


async def get_stats(campaign_id: Optional[int] = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        campaign_clause = " AND campaign_id = ?" if campaign_id else ""
        campaign_params = (campaign_id,) if campaign_id else ()
        queries = {
            "users": "SELECT COUNT(*) FROM users",
            "prompt_sent": f"SELECT COUNT(*) FROM events WHERE event IN ('prompt_sent', 'prompt_sent_from_webapp'){campaign_clause}",
            "done": f"SELECT COUNT(*) FROM events WHERE event IN ('done_clicked', 'done_clicked_from_webapp'){campaign_clause}",
            "screenshots": f"SELECT COUNT(*) FROM submissions WHERE status IN ('new', 'accepted'){campaign_clause}",
        }
        for key, query in queries.items():
            if key == "users" and campaign_id:
                cursor = await db.execute("SELECT COUNT(DISTINCT telegram_id) FROM events WHERE campaign_id = ?", (campaign_id,))
            else:
                cursor = await db.execute(query, campaign_params if key != "users" else ())
            row = await cursor.fetchone()
            stats[key] = row[0] if row else 0

        cursor = await db.execute(
            f"""
            SELECT prompt_id, COUNT(*)
            FROM events
            WHERE event IN ('prompt_sent', 'prompt_sent_from_webapp'){campaign_clause}
            GROUP BY prompt_id
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """
            ,
            campaign_params,
        )
        stats["by_prompt"] = await cursor.fetchall()

        cursor = await db.execute(
            """
            SELECT source, COUNT(*)
            FROM users
            GROUP BY source
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """
        )
        stats["by_source"] = await cursor.fetchall()
        return stats


async def get_leaderboard(limit: int = 10, campaign_id: Optional[int] = None) -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        campaign_done_clause = "AND campaign_id = ?" if campaign_id else ""
        campaign_sub_clause = "WHERE status IN ('new', 'accepted') AND campaign_id = ?" if campaign_id else "WHERE status IN ('new', 'accepted')"
        params: tuple = (campaign_id, campaign_id, limit) if campaign_id else (limit,)
        cursor = await db.execute(
            f"""
            SELECT
                u.telegram_id,
                u.username,
                u.first_name,
                COALESCE(done.done_count, 0) AS done_count,
                COALESCE(sub.sub_count, 0) AS sub_count,
                COALESCE(done.done_count, 0) + COALESCE(sub.sub_count, 0) * 3 AS points
            FROM users u
            LEFT JOIN (
                SELECT telegram_id, COUNT(*) AS done_count
                FROM events
                WHERE event IN ('done_clicked', 'done_clicked_from_webapp')
                {campaign_done_clause}
                GROUP BY telegram_id
            ) done ON done.telegram_id = u.telegram_id
            LEFT JOIN (
                SELECT telegram_id, COUNT(*) AS sub_count
                FROM submissions
                {campaign_sub_clause}
                GROUP BY telegram_id
            ) sub ON sub.telegram_id = u.telegram_id
            ORDER BY points DESC, sub_count DESC, done_count DESC
            LIMIT ?
            """,
            params,
        )
        return await cursor.fetchall()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Я участник", callback_data="role:participant")],
            [InlineKeyboardButton(text="Создать челлендж", callback_data="role:creator")],
            [
                InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            ],
        ]
    )


async def campaign_tasks_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for data in await get_campaign_prompts(campaign_id):
        buttons.append([InlineKeyboardButton(text=data["title"], callback_data=f"prompt:{data['prompt_key']}")])
    buttons.append([
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def growth_kit_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть мой челлендж", url=campaign_link(campaign_id))],
            [InlineKeyboardButton(text="Скопировать пост", callback_data=f"campaign_post:{campaign_id}")],
            [InlineKeyboardButton(text="Статистика челленджа", callback_data=f"campaign_stats:{campaign_id}")],
            [InlineKeyboardButton(text="Создать ещё один", callback_data="role:creator")],
        ]
    )


def challenge_reply_keyboard() -> ReplyKeyboardMarkup:
    first_row = [KeyboardButton(text="🚀 Открыть Challenge", web_app=WebAppInfo(url=WEBAPP_URL))]
    return ReplyKeyboardMarkup(
        keyboard=[
            first_row,
            [KeyboardButton(text="🏆 Leaderboard"), KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def prompt_keyboard(prompt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть Mira", url=MIRA_LINK)],
            [InlineKeyboardButton(text="✅ Я сделал", callback_data=f"done:{prompt_id}")],
            [InlineKeyboardButton(text="📸 Отправить скрин в подборку", callback_data=f"upload:{prompt_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к задачам", callback_data="back")],
        ]
    )


def after_done_keyboard(prompt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Отправить скрин", callback_data=f"upload:{prompt_id}")],
            [
                InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard"),
                InlineKeyboardButton(text="🔁 Другая задача", callback_data="back"),
            ],
        ]
    )


def prompt_message_text(data: dict) -> str:
    prompt_text = html.escape(data["prompt_text"])
    return (
        f"<b>{html.escape(data['title'])}</b>\n\n"
        f"{html.escape(data['short'])}\n\n"
        "Скопируй промпт ниже, открой Mira и вставь его туда 👇\n\n"
        f"<pre>{prompt_text}</pre>\n\n"
        "После результата вернись сюда и нажми «Я сделал»."
    )


async def send_prompt_message(message: Message, campaign_id: int, prompt_key: str) -> None:
    data = await get_campaign_prompt(campaign_id, prompt_key)
    if not data:
        await message.answer("Промпт не найден. Нажми /start и попробуй ещё раз.")
        return
    await message.answer(prompt_message_text(data), reply_markup=prompt_keyboard(prompt_key))


async def send_stats_message(message: Message, event_name: str = "stats_opened") -> None:
    await upsert_user(message)
    await add_event(message.from_user.id, event_name)
    stats = await get_stats()
    text = (
        "📊 <b>Статистика челленджа</b>\n\n"
        f"Пользователей: <b>{stats['users']}</b>\n"
        f"Выдано промптов: <b>{stats['prompt_sent']}</b>\n"
        f"Нажали «Я сделал»: <b>{stats['done']}</b>\n"
        f"Скринов загружено: <b>{stats['screenshots']}</b>"
    )
    await message.answer(text)


async def send_campaign_stats(message: Message, campaign_id: Optional[int] = None) -> None:
    final_campaign_id = campaign_id or await get_active_campaign_id(message.from_user.id)
    campaign = await get_campaign(final_campaign_id) or await get_campaign(DEFAULT_CAMPAIGN_ID)
    stats = await get_stats(campaign["id"])
    top_prompt = stats["by_prompt"][0][0] if stats["by_prompt"] else "пока нет"
    text = (
        f"📊 <b>Статистика челленджа</b>\n\n"
        f"<b>{html.escape(campaign['title'])}</b>\n\n"
        f"Участников: <b>{stats['users']}</b>\n"
        f"Промптов выдано: <b>{stats['prompt_sent']}</b>\n"
        f"Нажали «Я сделал»: <b>{stats['done']}</b>\n"
        f"Скринов загружено: <b>{stats['screenshots']}</b>\n"
        f"Top prompt: <b>{html.escape(str(top_prompt))}</b>\n\n"
        f"Ссылка:\n{campaign_link(campaign['id'])}"
    )
    await message.answer(text)


async def send_leaderboard_message(message: Message, event_name: str = "leaderboard_opened") -> None:
    await upsert_user(message)
    campaign_id = await get_active_campaign_id(message.from_user.id)
    await add_event(message.from_user.id, event_name, campaign_id=campaign_id)
    rows = await get_leaderboard(campaign_id=campaign_id)
    if not rows:
        await message.answer("Пока leaderboard пустой. Будь первым.")
        return
    campaign = await get_campaign(campaign_id)
    lines = [f"🏆 <b>Leaderboard</b>\n{html.escape(campaign['title']) if campaign else 'Global'}\n"]
    for index, row in enumerate(rows, start=1):
        telegram_id, username, first_name, done_count, sub_count, points = row
        name = f"@{username}" if username else (first_name or f"user_{telegram_id}")
        lines.append(f"{index}. {html.escape(name)} — {points} баллов ({done_count} done, {sub_count} скринов)")
    await message.answer("\n".join(lines))


async def download_telegram_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    destination = BytesIO()
    await bot.download_file(file.file_path, destination)
    return destination.getvalue()


async def resolve_prompt_for_screenshot(message: Message, state: FSMContext) -> Optional[tuple[int, str]]:
    data = await state.get_data()
    campaign_id = data.get("campaign_id")
    prompt_id = data.get("prompt_id")
    if prompt_id:
        return (int(campaign_id) if campaign_id else await get_active_campaign_id(message.from_user.id), prompt_id)

    user = message.from_user
    if not user:
        return None
    pending = await get_pending_upload(user.id)
    if pending:
        return pending
    return None


async def process_screenshot(
    message: Message,
    state: FSMContext,
    bot: Bot,
    *,
    file_id: str,
    file_type: str,
    mime_type: str,
    caption: Optional[str],
) -> None:
    user = message.from_user
    if not user:
        return

    resolved = await resolve_prompt_for_screenshot(message, state)
    if not resolved:
        await message.answer("Не понял, к какой задаче относится скрин. Нажми «Отправить скрин» в Mini App или в боте и попробуй ещё раз.")
        await state.clear()
        return
    campaign_id, prompt_id = resolved

    await message.answer("Скрин получил. Проверяю, что это реальный результат Mira…")
    image_bytes = await download_telegram_file(bot, file_id)
    screenshot_url = await upload_screenshot_to_supabase(user.id, file_id, image_bytes, mime_type)
    verification = await verify_screenshot_with_groq(image_bytes, mime_type, prompt_id, screenshot_url)
    accepted = bool(verification.get("accepted"))
    status = "accepted" if accepted else "rejected"
    await save_submission(user.id, campaign_id, prompt_id, file_id, file_type, caption, status, verification, screenshot_url)
    await clear_pending_upload(user.id)
    await state.clear()

    if accepted:
        await message.answer(
            "✅ Скрин засчитан.\n\nТеперь ты участвуешь в подборке лучших результатов дня.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")],
                    [InlineKeyboardButton(text="🔁 Сделать ещё задачу", callback_data="back")],
                ]
            ),
        )
        return

    reason = verification.get("reason") or "AI не подтвердил, что это результат выполнения задания."
    await message.answer(
        "Скрин получил, но не засчитал.\n\n"
        f"Причина: {html.escape(str(reason))}\n\n"
        "Отправь скрин именно с результатом Mira по выбранной задаче."
    )


async def send_main_menu(message: Message) -> None:
    text = (
        "🚀 <b>Mira Growth Engine</b>\n\n"
        "Здесь можно:\n"
        "1. пройти AI-челлендж и получить результат в Mira за 2 минуты;\n"
        "2. создать свой челлендж для канала, чата или бизнеса.\n\n"
        "Что хочешь сделать?"
    )
    if WEBAPP_URL:
        await message.answer(text, reply_markup=challenge_reply_keyboard())
        await message.answer("Выбери режим:", reply_markup=main_menu_keyboard())
        return
    await message.answer(text, reply_markup=main_menu_keyboard())


async def send_main_menu_callback(callback: CallbackQuery) -> None:
    text = (
        "🚀 <b>Mira Growth Engine</b>\n\n"
        "Что хочешь сделать?"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())


async def send_participant_tasks(message: Message, campaign_id: int) -> None:
    campaign = await get_campaign(campaign_id) or await get_campaign(DEFAULT_CAMPAIGN_ID)
    await set_active_campaign(message.from_user.id, campaign["id"])
    stats = await get_stats(campaign["id"])
    text = (
        f"🚀 <b>{html.escape(campaign['title'])}</b>\n\n"
        f"{html.escape(campaign['cta'] or 'Выбери задачу и сделай результат в Mira за 2 минуты')}\n\n"
        f"Уже сделали: <b>{stats['done']}</b>\n"
        f"Скринов в подборке: <b>{stats['screenshots']}</b>\n\n"
        "Выбирай задачу 👇"
    )
    await message.answer(text, reply_markup=await campaign_tasks_keyboard(campaign["id"]))


async def edit_participant_tasks(callback: CallbackQuery, campaign_id: int) -> None:
    campaign = await get_campaign(campaign_id) or await get_campaign(DEFAULT_CAMPAIGN_ID)
    stats = await get_stats(campaign["id"])
    text = (
        f"🚀 <b>{html.escape(campaign['title'])}</b>\n\n"
        f"{html.escape(campaign['cta'] or 'Выбери задачу и сделай результат в Mira за 2 минуты')}\n\n"
        f"Уже сделали: <b>{stats['done']}</b>\n"
        f"Скринов в подборке: <b>{stats['screenshots']}</b>\n\n"
        "Выбирай задачу 👇"
    )
    await callback.message.edit_text(text, reply_markup=await campaign_tasks_keyboard(campaign["id"]))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    source = command.args if command and command.args else "direct"
    await upsert_user(message, source=source)
    campaign_id = DEFAULT_CAMPAIGN_ID
    if source.startswith("challenge_"):
        raw_campaign_id = source.removeprefix("challenge_")
        if raw_campaign_id.isdigit() and await get_campaign(int(raw_campaign_id)):
            campaign_id = int(raw_campaign_id)
            await set_active_campaign(message.from_user.id, campaign_id)
        else:
            await set_active_campaign(message.from_user.id, DEFAULT_CAMPAIGN_ID)
            await message.answer("Этот челлендж не найден, открыл дефолтный Mira Challenge.")
    await add_event(message.from_user.id, "start", meta={"source": source}, campaign_id=campaign_id)
    if source.startswith("challenge_"):
        await send_participant_tasks(message, campaign_id)
        return
    await send_main_menu(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await upsert_user(message)
    text = (
        "Как работает бот:\n\n"
        "1. Выбираешь задачу.\n"
        "2. Копируешь готовый промпт.\n"
        "3. Жмёшь «Открыть Mira».\n"
        "4. Вставляешь промпт в Mira.\n"
        "5. Возвращаешься и жмёшь «Я сделал».\n"
        "6. Если хочешь попасть в подборку — кидаешь скрин.\n\n"
        "Команды:\n/start — открыть меню\n/leaderboard — лучшие участники\n/stats — статистика"
    )
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await send_stats_message(message)


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message) -> None:
    await send_leaderboard_message(message)


@router.message(Command("campaign_stats"))
async def cmd_campaign_stats(message: Message) -> None:
    await send_campaign_stats(message)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Нет доступа.")
        return
    stats = await get_stats()
    text = (
        "🛠 <b>Admin stats</b>\n\n"
        f"Users: <b>{stats['users']}</b>\n"
        f"Prompt sent: <b>{stats['prompt_sent']}</b>\n"
        f"Done: <b>{stats['done']}</b>\n"
        f"Screenshots: <b>{stats['screenshots']}</b>\n\n"
        "<b>Top prompts:</b>\n"
    )
    if stats["by_prompt"]:
        for prompt_id, count in stats["by_prompt"]:
            title = PROMPTS.get(prompt_id, {}).get("title", prompt_id)
            text += f"— {html.escape(title)}: {count}\n"
    else:
        text += "Пока пусто\n"
    text += "\n<b>Top sources:</b>\n"
    if stats["by_source"]:
        for source, count in stats["by_source"]:
            text += f"— {html.escape(source or 'direct')}: {count}\n"
    else:
        text += "Пока пусто\n"
    await message.answer(text)


@router.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_main_menu_callback(callback)
    await callback.answer()


@router.callback_query(F.data == "role:participant")
async def cb_role_participant(callback: CallbackQuery) -> None:
    await set_user_role(callback.from_user.id, "participant")
    campaign_id = await get_active_campaign_id(callback.from_user.id)
    await add_event(callback.from_user.id, "role_participant_selected", campaign_id=campaign_id)
    campaign = await get_campaign(campaign_id)
    if not campaign:
        campaign_id = DEFAULT_CAMPAIGN_ID
        await set_active_campaign(callback.from_user.id, campaign_id)
    await edit_participant_tasks(callback, campaign_id)
    await callback.answer()


async def start_creator_wizard(message: Message, state: FSMContext, user_id: int) -> None:
    await state.clear()
    await state.set_state(CreateCampaign.waiting_for_niche)
    await set_user_role(user_id, "creator")
    await add_event(user_id, "role_creator_selected", campaign_id=await get_active_campaign_id(user_id))
    await message.answer(
        "Ок, соберём growth-kit для твоего челленджа.\n\n"
        "1/4 Какая ниша?\n"
        "Например: SMM, студенты, бизнес, фриланс, английский, дизайн"
    )


@router.callback_query(F.data == "role:creator")
async def cb_role_creator(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await start_creator_wizard(callback.message, state, callback.from_user.id)


@router.message(CreateCampaign.waiting_for_niche)
async def campaign_niche(message: Message, state: FSMContext) -> None:
    await state.update_data(niche=message.text.strip())
    await state.set_state(CreateCampaign.waiting_for_audience)
    await message.answer("2/4 Кто аудитория?\nНапример: владельцы Telegram-каналов до 10k подписчиков")


@router.message(CreateCampaign.waiting_for_audience)
async def campaign_audience(message: Message, state: FSMContext) -> None:
    await state.update_data(audience=message.text.strip())
    await state.set_state(CreateCampaign.waiting_for_goal)
    await message.answer("3/4 Какой результат им нужен?\nНапример: контент-план, разбор канала, оффер, план обучения")


@router.message(CreateCampaign.waiting_for_goal)
async def campaign_goal(message: Message, state: FSMContext) -> None:
    await state.update_data(goal=message.text.strip())
    await state.set_state(CreateCampaign.waiting_for_platform)
    await message.answer("4/4 Где будешь запускать?\nВыбери или напиши: канал / чат / личка / комьюнити")


@router.message(CreateCampaign.waiting_for_platform)
async def campaign_platform(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    niche = data["niche"]
    audience = data["audience"]
    goal = data["goal"]
    platform = message.text.strip()
    campaign_id = await create_campaign(message.from_user.id, niche, audience, goal, platform)
    await set_active_campaign(message.from_user.id, campaign_id)
    await add_event(message.from_user.id, "campaign_created", campaign_id=campaign_id)
    await add_event(message.from_user.id, "growth_kit_generated", campaign_id=campaign_id)
    await state.clear()

    campaign = await get_campaign(campaign_id)
    text = (
        "✅ <b>Growth-kit готов</b>\n\n"
        f"<b>Название:</b>\n{html.escape(campaign['title'])}\n\n"
        f"<b>Для кого:</b>\n{html.escape(campaign['audience'])}\n\n"
        f"<b>Цель:</b>\n{html.escape(campaign['goal'])}\n\n"
        f"<b>Ссылка на челлендж:</b>\n{campaign_link(campaign_id)}\n\n"
        "<b>Что внутри:</b>\n"
        "1. 5 задач\n"
        "2. 5 промптов\n"
        "3. готовый пост для канала\n"
        "4. CTA\n"
        "5. leaderboard\n"
        "6. сбор скринов / Result of the Day\n\n"
        f"<b>Пост для запуска:</b>\n<pre>{html.escape(campaign['post_text'])}</pre>\n\n"
        "<b>Что делать дальше:</b>\n"
        "1. Скопируй пост\n"
        "2. Опубликуй его в канале/чате\n"
        "3. Следи за статистикой\n"
        "4. Лучшие скрины публикуй как Result of the Day"
    )
    await message.answer(text, reply_markup=growth_kit_keyboard(campaign_id))


@router.callback_query(F.data.startswith("campaign_post:"))
async def cb_campaign_post(callback: CallbackQuery) -> None:
    campaign_id = int(callback.data.split(":", 1)[1])
    campaign = await get_campaign(campaign_id)
    if not campaign:
        await callback.answer("Челлендж не найден", show_alert=True)
        return
    await callback.message.answer(f"Скопируй текст ниже 👇\n\n<pre>{html.escape(campaign['post_text'])}</pre>")
    await callback.answer()


@router.callback_query(F.data.startswith("campaign_stats:"))
async def cb_campaign_stats(callback: CallbackQuery) -> None:
    campaign_id = int(callback.data.split(":", 1)[1])
    await send_campaign_stats(callback.message, campaign_id)
    await callback.answer()


@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await add_event(callback.from_user.id, "back_to_menu")
    await edit_participant_tasks(callback, await get_active_campaign_id(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery) -> None:
    await add_event(callback.from_user.id, "stats_opened")
    stats = await get_stats()
    text = (
        "📊 <b>Статистика челленджа</b>\n\n"
        f"Участников: <b>{stats['users']}</b>\n"
        f"Промптов выдано: <b>{stats['prompt_sent']}</b>\n"
        f"Нажали «Я сделал»: <b>{stats['done']}</b>\n"
        f"Скринов загружено: <b>{stats['screenshots']}</b>\n\n"
        "Главное — не просто перейти, а сделать результат."
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]),
    )
    await callback.answer()


@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(callback: CallbackQuery) -> None:
    campaign_id = await get_active_campaign_id(callback.from_user.id)
    await add_event(callback.from_user.id, "leaderboard_opened", campaign_id=campaign_id)
    rows = await get_leaderboard(campaign_id=campaign_id)
    if not rows:
        text = "🏆 Пока leaderboard пустой.\n\nСделай первый результат и залети в топ."
    else:
        campaign = await get_campaign(campaign_id)
        lines = [f"🏆 <b>Leaderboard</b>\n{html.escape(campaign['title']) if campaign else 'Global'}\n"]
        for index, row in enumerate(rows, start=1):
            telegram_id, username, first_name, done_count, sub_count, points = row
            name = f"@{username}" if username else (first_name or f"user_{telegram_id}")
            lines.append(f"{index}. {html.escape(name)} — <b>{points}</b> баллов ({done_count} done, {sub_count} скринов)")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prompt:"))
async def cb_prompt(callback: CallbackQuery) -> None:
    prompt_id = callback.data.split(":", 1)[1]
    campaign_id = await get_active_campaign_id(callback.from_user.id)
    data = await get_campaign_prompt(campaign_id, prompt_id)
    if not data:
        await callback.answer("Промпт не найден", show_alert=True)
        return
    await add_event(callback.from_user.id, "prompt_sent", prompt_id, campaign_id=campaign_id)
    await callback.message.edit_text(prompt_message_text(data), reply_markup=prompt_keyboard(prompt_id))
    await callback.answer()


@router.callback_query(F.data.startswith("done:"))
async def cb_done(callback: CallbackQuery) -> None:
    prompt_id = callback.data.split(":", 1)[1]
    campaign_id = await get_active_campaign_id(callback.from_user.id)
    if not await get_campaign_prompt(campaign_id, prompt_id):
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await add_event(callback.from_user.id, "done_clicked", prompt_id, campaign_id=campaign_id)
    text = (
        "✅ Красавчик, результат засчитан.\n\n"
        "Если хочешь попасть в подборку лучших результатов дня — отправь скрин ответа Mira.\n\n"
        "Скрин необязателен, но именно по ним будем выбирать Result of the Day."
    )
    await callback.message.edit_text(text, reply_markup=after_done_keyboard(prompt_id))
    await callback.answer("Засчитано")


@router.callback_query(F.data.startswith("upload:"))
async def cb_upload(callback: CallbackQuery, state: FSMContext) -> None:
    prompt_id = callback.data.split(":", 1)[1]
    campaign_id = await get_active_campaign_id(callback.from_user.id)
    if not await get_campaign_prompt(campaign_id, prompt_id):
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await state.set_state(UploadScreenshot.waiting_for_screenshot)
    await state.update_data(prompt_id=prompt_id, campaign_id=campaign_id)
    await set_pending_upload(callback.from_user.id, campaign_id, prompt_id)
    await add_event(callback.from_user.id, "upload_requested", prompt_id, campaign_id=campaign_id)
    await callback.message.answer(
        "📸 Отправь сюда скрин результата из Mira.\n\n"
        "Можно просто фото/скриншот. Если хочешь — добавь подпись, что именно сделал."
    )
    await callback.answer()


@router.message(UploadScreenshot.waiting_for_screenshot, F.photo)
async def handle_photo_screenshot(message: Message, state: FSMContext, bot: Bot) -> None:
    file_id = message.photo[-1].file_id
    await process_screenshot(
        message,
        state,
        bot,
        file_id=file_id,
        file_type="photo",
        mime_type="image/jpeg",
        caption=message.caption,
    )


@router.message(UploadScreenshot.waiting_for_screenshot, F.document)
async def handle_document_screenshot(message: Message, state: FSMContext, bot: Bot) -> None:
    document = message.document
    if not document or not (document.mime_type or "").startswith("image/"):
        await message.answer("Это не похоже на изображение. Отправь скрин как фото или картинку.")
        return
    await process_screenshot(
        message,
        state,
        bot,
        file_id=document.file_id,
        file_type="document_image",
        mime_type=document.mime_type or "image/png",
        caption=message.caption,
    )


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext) -> None:
    await upsert_user(message)
    try:
        payload = json.loads(message.web_app_data.data)
    except (TypeError, json.JSONDecodeError):
        await message.answer("Не понял действие из Mini App. Нажми /start и попробуй ещё раз.")
        return

    action = payload.get("action")
    prompt_id = payload.get("prompt_key") or payload.get("prompt_id")
    campaign_id = payload.get("campaign_id")
    if str(campaign_id or "").isdigit() and await get_campaign(int(campaign_id)):
        campaign_id = int(campaign_id)
    else:
        campaign_id = await get_active_campaign_id(message.from_user.id)

    if action in {"select_prompt", "done_clicked", "upload_requested"} and not await get_campaign_prompt(campaign_id, prompt_id):
        await message.answer("Задача не найдена. Нажми /start и попробуй ещё раз.")
        return

    if action == "creator_start":
        await start_creator_wizard(message, state, message.from_user.id)
        return

    if action == "select_prompt":
        await set_active_campaign(message.from_user.id, campaign_id)
        await add_event(message.from_user.id, "prompt_sent_from_webapp", prompt_id, campaign_id=campaign_id)
        await send_prompt_message(message, campaign_id, prompt_id)
        return

    if action == "done_clicked":
        await set_active_campaign(message.from_user.id, campaign_id)
        await add_event(message.from_user.id, "done_clicked_from_webapp", prompt_id, campaign_id=campaign_id)
        await message.answer(
            "✅ Результат засчитан. Хочешь попасть в подборку — отправь скрин.",
            reply_markup=after_done_keyboard(prompt_id),
        )
        return

    if action == "upload_requested":
        await set_active_campaign(message.from_user.id, campaign_id)
        await state.set_state(UploadScreenshot.waiting_for_screenshot)
        await state.update_data(prompt_id=prompt_id, campaign_id=campaign_id)
        await set_pending_upload(message.from_user.id, campaign_id, prompt_id)
        await add_event(message.from_user.id, "upload_requested_from_webapp", prompt_id, campaign_id=campaign_id)
        await message.answer(
            "📸 Отправь сюда скрин результата из Mira.\n\n"
            "Можно просто фото/скриншот. Если хочешь — добавь подпись, что именно сделал."
        )
        return

    if action == "leaderboard_opened":
        await set_active_campaign(message.from_user.id, campaign_id)
        await send_leaderboard_message(message, "leaderboard_opened_from_webapp")
        return

    if action == "stats_opened":
        await set_active_campaign(message.from_user.id, campaign_id)
        await send_stats_message(message, "stats_opened_from_webapp")
        return

    await message.answer("Неизвестное действие из Mini App. Нажми /start и попробуй ещё раз.")


@router.message(UploadScreenshot.waiting_for_screenshot)
async def handle_wrong_screenshot(message: Message) -> None:
    await message.answer("Нужно отправить именно скрин: фото или изображение.\n\nПросто прикрепи скрин ответа Mira.")


@router.message(F.text == "🏆 Leaderboard")
async def text_leaderboard(message: Message) -> None:
    await send_leaderboard_message(message)


@router.message(F.text == "📊 Статистика")
async def text_stats(message: Message) -> None:
    await send_stats_message(message)


@router.message(F.photo)
async def loose_photo_screenshot(message: Message, state: FSMContext, bot: Bot) -> None:
    file_id = message.photo[-1].file_id
    await process_screenshot(
        message,
        state,
        bot,
        file_id=file_id,
        file_type="photo",
        mime_type="image/jpeg",
        caption=message.caption,
    )


@router.message(F.document)
async def loose_document_screenshot(message: Message, state: FSMContext, bot: Bot) -> None:
    document = message.document
    if not document or not (document.mime_type or "").startswith("image/"):
        await message.answer("Я пока понимаю только кнопки и скрины результата.\n\nНажми /start и выбери задачу.")
        return
    await process_screenshot(
        message,
        state,
        bot,
        file_id=document.file_id,
        file_type="document_image",
        mime_type=document.mime_type or "image/png",
        caption=message.caption,
    )


@router.message()
async def fallback(message: Message) -> None:
    await upsert_user(message)
    await message.answer("Я пока понимаю только кнопки.\n\nНажми /start и выбери задачу.")


async def main() -> None:
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
