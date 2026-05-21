# Mira 2-Minute Challenge Bot

MVP Telegram-бот без Mini App.

## Что умеет

- `/start`
- выбор из 5 задач
- выдача готового промпта
- кнопка `Открыть Mira`
- кнопка `Я сделал`
- загрузка скрина
- leaderboard
- простая статистика
- SQLite база

## Установка

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Для Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

## Настройка

В проекте уже создан файл `.env`. Открой его и заполни:

```env
BOT_TOKEN=токен_из_BotFather
MIRA_LINK=твоя_UTM_ссылка_на_Mira
ADMIN_IDS=твой_telegram_id
BOT_USERNAME=username_бота
DB_PATH=mira_challenge.db
```

Если нужно сбросить шаблон, используй `.env.example`.

## Важно

Telegram-бот не может точно узнать, нажал ли пользователь URL-кнопку `Открыть Mira`.

Точно трекаются:

- старт бота;
- выдача промпта;
- нажатие `Я сделал`;
- загрузка скрина;
- источник из `/start source`.

Переходы в Mira должны считаться через UTM/реф-ссылку хакатона.
