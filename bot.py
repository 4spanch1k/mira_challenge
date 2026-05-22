import asyncio
import html
import json
import logging
from datetime import datetime
from typing import Optional

import aiosqlite
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


class UploadScreenshot(StatesGroup):
    waiting_for_screenshot = State()


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                source TEXT,
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
                source TEXT,
                meta TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                prompt_id TEXT,
                file_id TEXT,
                file_type TEXT,
                caption TEXT,
                status TEXT,
                created_at TEXT
            )
        """)
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
            INSERT INTO users (telegram_id, username, first_name, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                source = users.source,
                updated_at = excluded.updated_at
            """,
            (user.id, user.username, user.first_name, final_source, now_iso(), now_iso()),
        )
        await db.commit()


async def get_user_source(telegram_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT source FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] else "direct"


async def add_event(telegram_id: int, event: str, prompt_id: Optional[str] = None, meta: Optional[dict] = None) -> None:
    source = await get_user_source(telegram_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO events (telegram_id, event, prompt_id, source, meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, event, prompt_id, source, json.dumps(meta or {}, ensure_ascii=False), now_iso()),
        )
        await db.commit()


async def save_submission(telegram_id: int, prompt_id: str, file_id: str, file_type: str, caption: Optional[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO submissions (telegram_id, prompt_id, file_id, file_type, caption, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, prompt_id, file_id, file_type, caption, "new", now_iso()),
        )
        await db.commit()

    await add_event(telegram_id, "screenshot_uploaded", prompt_id, {"file_type": file_type})


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        queries = {
            "users": "SELECT COUNT(*) FROM users",
            "prompt_sent": "SELECT COUNT(*) FROM events WHERE event IN ('prompt_sent', 'prompt_sent_from_webapp')",
            "done": "SELECT COUNT(*) FROM events WHERE event IN ('done_clicked', 'done_clicked_from_webapp')",
            "screenshots": "SELECT COUNT(*) FROM submissions",
        }
        for key, query in queries.items():
            cursor = await db.execute(query)
            row = await cursor.fetchone()
            stats[key] = row[0] if row else 0

        cursor = await db.execute(
            """
            SELECT prompt_id, COUNT(*)
            FROM events
            WHERE event IN ('prompt_sent', 'prompt_sent_from_webapp')
            GROUP BY prompt_id
            ORDER BY COUNT(*) DESC
            """
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


async def get_leaderboard(limit: int = 10) -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
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
                GROUP BY telegram_id
            ) done ON done.telegram_id = u.telegram_id
            LEFT JOIN (
                SELECT telegram_id, COUNT(*) AS sub_count
                FROM submissions
                GROUP BY telegram_id
            ) sub ON sub.telegram_id = u.telegram_id
            ORDER BY points DESC, sub_count DESC, done_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for prompt_id, data in PROMPTS.items():
        buttons.append([InlineKeyboardButton(text=data["title"], callback_data=f"prompt:{prompt_id}")])
    buttons.append([
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


def prompt_message_text(prompt_id: str) -> str:
    data = PROMPTS[prompt_id]
    prompt_text = html.escape(data["prompt"])
    return (
        f"<b>{html.escape(data['title'])}</b>\n\n"
        f"{html.escape(data['short'])}\n\n"
        "Скопируй промпт ниже, открой Mira и вставь его туда 👇\n\n"
        f"<pre>{prompt_text}</pre>\n\n"
        "После результата вернись сюда и нажми «Я сделал»."
    )


async def send_prompt_message(message: Message, prompt_id: str) -> None:
    await message.answer(prompt_message_text(prompt_id), reply_markup=prompt_keyboard(prompt_id))


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


async def send_leaderboard_message(message: Message, event_name: str = "leaderboard_opened") -> None:
    await upsert_user(message)
    await add_event(message.from_user.id, event_name)
    rows = await get_leaderboard()
    if not rows:
        await message.answer("Пока leaderboard пустой. Будь первым.")
        return
    lines = ["🏆 <b>Leaderboard</b>\n"]
    for index, row in enumerate(rows, start=1):
        telegram_id, username, first_name, done_count, sub_count, points = row
        name = f"@{username}" if username else (first_name or f"user_{telegram_id}")
        lines.append(f"{index}. {html.escape(name)} — {points} баллов ({done_count} done, {sub_count} скринов)")
    await message.answer("\n".join(lines))


async def send_main_menu(message: Message) -> None:
    stats = await get_stats()
    text = (
        "🚀 <b>Mira 2-Minute Challenge</b>\n\n"
        "Выбери задачу, получи готовый промпт, открой Mira и сделай результат за 2 минуты.\n\n"
        f"Уже сделали: <b>{stats['done']}</b>\n"
        f"Скринов в подборке: <b>{stats['screenshots']}</b>\n\n"
        "Выбирай задачу 👇"
    )
    if WEBAPP_URL:
        await message.answer(text, reply_markup=challenge_reply_keyboard())
        await message.answer("Если Mini App не открылся, выбери задачу здесь:", reply_markup=main_menu_keyboard())
        return
    await message.answer(text, reply_markup=main_menu_keyboard())


async def send_main_menu_callback(callback: CallbackQuery) -> None:
    stats = await get_stats()
    text = (
        "🚀 <b>Mira 2-Minute Challenge</b>\n\n"
        "Выбери задачу, получи готовый промпт, открой Mira и сделай результат за 2 минуты.\n\n"
        f"Уже сделали: <b>{stats['done']}</b>\n"
        f"Скринов в подборке: <b>{stats['screenshots']}</b>\n\n"
        "Выбирай задачу 👇"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    source = command.args if command and command.args else "direct"
    await upsert_user(message, source=source)
    await add_event(message.from_user.id, "start", meta={"source": source})
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


@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await add_event(callback.from_user.id, "back_to_menu")
    await send_main_menu_callback(callback)
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
    await add_event(callback.from_user.id, "leaderboard_opened")
    rows = await get_leaderboard()
    if not rows:
        text = "🏆 Пока leaderboard пустой.\n\nСделай первый результат и залети в топ."
    else:
        lines = ["🏆 <b>Leaderboard</b>\n"]
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
    data = PROMPTS.get(prompt_id)
    if not data:
        await callback.answer("Промпт не найден", show_alert=True)
        return
    await add_event(callback.from_user.id, "prompt_sent", prompt_id)
    await callback.message.edit_text(prompt_message_text(prompt_id), reply_markup=prompt_keyboard(prompt_id))
    await callback.answer()


@router.callback_query(F.data.startswith("done:"))
async def cb_done(callback: CallbackQuery) -> None:
    prompt_id = callback.data.split(":", 1)[1]
    if prompt_id not in PROMPTS:
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await add_event(callback.from_user.id, "done_clicked", prompt_id)
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
    if prompt_id not in PROMPTS:
        await callback.answer("Задача не найдена", show_alert=True)
        return
    await state.set_state(UploadScreenshot.waiting_for_screenshot)
    await state.update_data(prompt_id=prompt_id)
    await add_event(callback.from_user.id, "upload_requested", prompt_id)
    await callback.message.answer(
        "📸 Отправь сюда скрин результата из Mira.\n\n"
        "Можно просто фото/скриншот. Если хочешь — добавь подпись, что именно сделал."
    )
    await callback.answer()


@router.message(UploadScreenshot.waiting_for_screenshot, F.photo)
async def handle_photo_screenshot(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        await message.answer("Не понял, к какой задаче относится скрин. Нажми /start и попробуй ещё раз.")
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await save_submission(message.from_user.id, prompt_id, file_id, "photo", message.caption)
    await state.clear()
    await message.answer(
        "🔥 Скрин принял.\n\nТеперь ты участвуешь в подборке лучших результатов дня.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton(text="🔁 Сделать ещё задачу", callback_data="back")],
            ]
        ),
    )


@router.message(UploadScreenshot.waiting_for_screenshot, F.document)
async def handle_document_screenshot(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        await message.answer("Не понял, к какой задаче относится файл. Нажми /start и попробуй ещё раз.")
        await state.clear()
        return
    document = message.document
    if not document or not (document.mime_type or "").startswith("image/"):
        await message.answer("Это не похоже на изображение. Отправь скрин как фото или картинку.")
        return
    await save_submission(message.from_user.id, prompt_id, document.file_id, "document_image", message.caption)
    await state.clear()
    await message.answer(
        "🔥 Скрин принял.\n\nТеперь ты участвуешь в подборке лучших результатов дня.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton(text="🔁 Сделать ещё задачу", callback_data="back")],
            ]
        ),
    )


@router.message(UploadScreenshot.waiting_for_screenshot)
async def handle_wrong_screenshot(message: Message) -> None:
    await message.answer("Нужно отправить именно скрин: фото или изображение.\n\nПросто прикрепи скрин ответа Mira.")


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext) -> None:
    await upsert_user(message)
    try:
        payload = json.loads(message.web_app_data.data)
    except (TypeError, json.JSONDecodeError):
        await message.answer("Не понял действие из Mini App. Нажми /start и попробуй ещё раз.")
        return

    action = payload.get("action")
    prompt_id = payload.get("prompt_id")

    if action in {"select_prompt", "done_clicked", "upload_requested"} and prompt_id not in PROMPTS:
        await message.answer("Задача не найдена. Нажми /start и попробуй ещё раз.")
        return

    if action == "select_prompt":
        await add_event(message.from_user.id, "prompt_sent_from_webapp", prompt_id)
        await send_prompt_message(message, prompt_id)
        return

    if action == "done_clicked":
        await add_event(message.from_user.id, "done_clicked_from_webapp", prompt_id)
        await message.answer(
            "✅ Результат засчитан. Хочешь попасть в подборку — отправь скрин.",
            reply_markup=after_done_keyboard(prompt_id),
        )
        return

    if action == "upload_requested":
        await state.set_state(UploadScreenshot.waiting_for_screenshot)
        await state.update_data(prompt_id=prompt_id)
        await add_event(message.from_user.id, "upload_requested_from_webapp", prompt_id)
        await message.answer(
            "📸 Отправь сюда скрин результата из Mira.\n\n"
            "Можно просто фото/скриншот. Если хочешь — добавь подпись, что именно сделал."
        )
        return

    if action == "leaderboard_opened":
        await send_leaderboard_message(message, "leaderboard_opened_from_webapp")
        return

    if action == "stats_opened":
        await send_stats_message(message, "stats_opened_from_webapp")
        return

    await message.answer("Неизвестное действие из Mini App. Нажми /start и попробуй ещё раз.")


@router.message(F.text == "🏆 Leaderboard")
async def text_leaderboard(message: Message) -> None:
    await send_leaderboard_message(message)


@router.message(F.text == "📊 Статистика")
async def text_stats(message: Message) -> None:
    await send_stats_message(message)


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
