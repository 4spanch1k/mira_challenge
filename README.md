<div align="center">

<img src="./assets/mira-challenge-avatar.png" width="140" alt="Мира Челлендж Avatar" />

# 🚀 Mira Growth Engine

**Growth Engine для Mira: любой админ канала, комьюнити или бизнеса может создать свой AI-челлендж, получить growth-kit и запустить его у себя.**

Creator создаёт campaign → получает growth-kit → публикует пост → участники проходят челлендж → Mira usage → результат → скрин → leaderboard → статистика.

<br />

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)
![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram)

</div>

---

## 🧠 Идея

Раньше проект был простым челленджем с промптами. Теперь это система кампаний:

- default campaign: `Mira 2-Minute Challenge`;
- custom campaigns для каналов, чатов, комьюнити и бизнеса;
- каждая campaign имеет 5 задач, 5 промптов, пост для запуска, CTA, leaderboard и stats.

Главная формула:

> **Campaign creator → growth-kit → participant challenge → Mira usage → result → screenshot → leaderboard → stats.**

---

## 🔥 Как работает флоу

```text
/start
  ↓
выбор задачи
  ↓
готовый промпт
  ↓
кнопка «Открыть Mira»
  ↓
результат в Mira
  ↓
кнопка «Я сделал»
  ↓
опционально: скрин результата
  ↓
leaderboard / подборка лучших
```

---

## ✨ Основные функции

- ✅ Telegram-бот + Mini App;
- ✅ campaign/challenge система;
- ✅ default campaign без потери старой механики;
- ✅ FSM wizard для создания growth-kit;
- ✅ `/start challenge_{campaign_id}` ссылки;
- ✅ Telegram Mini App на чистом HTML/CSS/JS;
- ✅ 5 готовых сценариев использования Mira;
- ✅ кнопка перехода в Mira по UTM/ref-ссылке;
- ✅ фиксация действия «Я сделал»;
- ✅ загрузка скринов результата;
- ✅ leaderboard по активности;
- ✅ простая статистика;
- ✅ SQLite-база;
- ✅ source tracking через `/start source`;
- ✅ admin-команда для просмотра метрик.

---

## 🧩 Как работает campaign

Каждая campaign содержит:

- `campaign_id`;
- creator;
- title, niche, audience, goal, platform;
- 5 задач и 5 промптов;
- post text для запуска;
- CTA;
- leaderboard;
- статистику;
- submissions/скрины.

Default campaign всегда имеет `id=1`. Если пользователь открывает несуществующую ссылку, бот мягко переключает его на default campaign.

Ссылка на кампанию:

```text
https://t.me/YOUR_BOT_USERNAME?start=challenge_123
```

---

## 🏗️ Создание челленджа

В `/start` нажми `Создать челлендж`. Бот задаст 4 вопроса:

1. ниша;
2. аудитория;
3. нужный результат;
4. площадка запуска.

После этого бот выдаст growth-kit:

- название челленджа;
- ссылку вида `/start challenge_{id}`;
- 5 задач;
- 5 промптов;
- готовый пост для канала/чата;
- CTA;
- кнопки статистики и повторного создания.

AI API для генерации growth-kit не нужен: промпты создаются шаблонно на основе `niche`, `audience`, `goal`.

---

## 📌 MVP-сценарии

| Категория | Что получает пользователь |
|---|---|
| 📱 Telegram-канал | слабые места, идеи постов, офферы, контент-план |
| 📊 Контент-план | темы, хуки, форматы, CTA, идеи для Reels/TikTok |
| 💸 Оффер | 5 вариантов оффера, боли ЦА, продающий текст |
| 🧠 Экзамен | объяснение темы, план подготовки, тесты, шпаргалка |
| 🧑‍💻 Резюме / профиль | bio, описание опыта, отклик, позиционирование |

---

## 🛠️ Стек

```text
Python 3.10+
Aiogram 3.x
SQLite
Aiosqlite
python-dotenv
```

---

## 📁 Структура проекта

```text
mira_challenge_bot/
├── bot.py
├── config.py
├── requirements.txt
├── supabase_schema.sql
├── .env.example
├── README.md
├── miniapp/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── assets/
│       └── avatar.png
└── assets/
    ├── avatar.png
    └── mira-challenge-avatar.png
```

---

## ⚙️ Установка

### 1. Клонируй репозиторий

```bash
git clone https://github.com/your-username/mira-challenge-bot.git
cd mira-challenge-bot
```

### 2. Создай виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate
```

Для Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Установи зависимости

```bash
pip install -r requirements.txt
```

### 4. Создай `.env`

```bash
cp .env.example .env
```

Для Windows:

```bash
copy .env.example .env
```

### 5. Заполни переменные

```env
BOT_TOKEN=your_telegram_bot_token
MIRA_LINK=https://t.me/Mira?start=your_ref_or_utm
ADMIN_IDS=123456789
BOT_USERNAME=your_bot_username
WEBAPP_URL=https://your-miniapp-domain.com
DB_PATH=mira_challenge.db
```

### 6. Запусти бота

```bash
python bot.py
```

---

## 🔐 Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | токен бота из BotFather |
| `MIRA_LINK` | персональная UTM/ref-ссылка на Mira |
| `ADMIN_IDS` | Telegram ID админов через запятую |
| `BOT_USERNAME` | username бота |
| `WEBAPP_URL` | HTTPS-ссылка на Telegram Mini App |
| `GROQ_API_KEY` | ключ Groq для проверки реальности скринов |
| `GROQ_VISION_MODEL` | vision-модель Groq |
| `SUPABASE_URL` | URL проекта Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service role key для серверной записи в Supabase |
| `SUPABASE_STORAGE_BUCKET` | bucket для скринов, по умолчанию `screenshots` |
| `DB_PATH` | путь до SQLite-базы |

SQLite остаётся fallback-хранилищем. Если Supabase-переменные не заполнены, бот продолжит работать локально.

---

## 🛰️ Mini App

Mini App лежит в папке `miniapp/` и работает как статический сайт без сборки:

```bash
cd miniapp
python -m http.server 8000
```

Локально он откроется по адресу:

```text
http://localhost:8000
```

Для Telegram Mini App нужен публичный HTTPS URL. Самый быстрый вариант — задеплоить папку `miniapp/` на Vercel или Netlify и вставить полученный URL в `.env`:

```env
WEBAPP_URL=https://your-miniapp-domain.com
```

После этого `/start` покажет кнопку `🚀 Открыть Challenge`. Старые inline-кнопки выбора задач остаются ниже как fallback.

### Деплой на Vercel

```bash
cd miniapp
vercel
```

В настройках проекта на Vercel укажи корневой директорией `miniapp`, если деплоишь из всего репозитория.

### Деплой на Netlify

```bash
cd miniapp
netlify deploy --prod --dir .
```

---

## 🧩 Команды бота

| Команда | Что делает |
|---|---|
| `/start` | открывает Mira Growth Engine |
| `/start challenge_123` | открывает конкретный челлендж |
| `/help` | показывает инструкцию |
| `/stats` | показывает общую статистику |
| `/campaign_stats` | показывает статистику активного челленджа |
| `/leaderboard` | показывает топ участников |
| `/admin` | показывает расширенную статистику для админов |

---

## 📊 Что трекается

Бот сохраняет в SQLite:

- пользователя;
- источник входа;
- выбранный промпт;
- выдачу промпта;
- нажатие «Я сделал»;
- загрузку скрина;
- статистику по источникам;
- leaderboard.

---

## 🧠 Проверка скринов через Groq

Когда пользователь отправляет скрин результата, бот скачивает изображение из Telegram и проверяет его через Groq Vision:

- если скрин похож на реальный AI/Mira-результат по выбранной задаче — submission получает `status=accepted`;
- если это случайный скрин, пустой экран или нерелевантная картинка — `status=rejected`;
- leaderboard считает только `accepted` и старые `new` submissions.

Для включения проверки заполни:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
```

---

## 🗄️ Supabase

Схема лежит в [`supabase_schema.sql`](./supabase_schema.sql). Выполни её в Supabase SQL Editor, затем заполни:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_STORAGE_BUCKET=screenshots
```

Service role key используй только на сервере бота. Не добавляй его в Mini App и не коммить `.env`.

> Важно: Telegram не сообщает боту, нажал ли пользователь внешнюю URL-кнопку.  
> Поэтому клики в Mira считаются через UTM/ref-ссылку, а бот фиксирует внутренние действия пользователя.

---

## 🏆 Как считаются баллы

```text
+1 балл — пользователь нажал «Я сделал»
+3 балла — пользователь отправил скрин результата
```

Leaderboard нужен не ради сложной геймификации, а чтобы создать социальное доказательство и UGC.

---

## 🚀 Growth-механика

Ключевая формула:

> **Задача → промпт → Mira → результат → скрин → подборка → новые участники**

Бот можно продвигать через:

- Telegram-каналы;
- студенческие чаты;
- SMM-чаты;
- предпринимательские комьюнити;
- фриланс-сообщества;
- личные сообщения админам каналов.

---

## 🗣️ Пример поста для запуска

```text
🚀 Запускаем Мира Челлендж

Суть простая: выбираешь задачу, получаешь готовый промпт, открываешь Mira и за 2 минуты получаешь результат.

Можно сделать:
— контент-план на неделю;
— разбор Telegram-канала;
— продающий оффер;
— идеи для Reels/TikTok;
— план подготовки к экзамену;
— упаковку резюме или профиля.

Нажимаешь «Я сделал» — участвуешь в челлендже.
Загрузишь скрин — можешь попасть в подборку лучших результатов дня.

Старт здесь: @YOUR_BOT
```

---

## 🧪 Roadmap

### Day 1 — MVP

- [x] `/start`
- [x] 5 категорий задач
- [x] выдача промптов
- [x] кнопка «Открыть Mira»
- [x] кнопка «Я сделал»
- [x] приём скринов
- [x] SQLite-логирование

### Day 2 — Launch

- [ ] seed из 10–15 первых результатов;
- [ ] первые публикации в каналах;
- [ ] leaderboard;
- [ ] сбор обратной связи;
- [ ] отключение слабых сценариев.

### Day 3+ — Scale

- [ ] niche-промпты под разные аудитории;
- [ ] Result of the Day;
- [ ] партнёрские размещения;
- [ ] микроинфлюенсеры;
- [ ] финальный отчёт для хакатона.

---

## 🎯 Главный принцип

> **Не строим большой продукт.  
> Строим машину лидов.**

---

## 📄 License

MIT

---

<div align="center">

Made for **Mira Growth Hackathon** ⚡

</div>
