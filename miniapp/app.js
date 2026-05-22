const tg = window.Telegram?.WebApp;

// заменить на свою UTM-ссылку
const MIRA_LINK = "https://t.me/Mira";

const PROMPTS = {
  channel_audit: {
    icon: "📱",
    title: "Разбор Telegram-канала",
    short: "Идеи, слабые места, офферы",
    prompt: `Мира, выступи как маркетолог и редактор Telegram-каналов.

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
Описание канала: [вставь описание]`,
  },
  content_plan: {
    icon: "📊",
    title: "Контент-план",
    short: "Посты, хуки, Reels/TikTok",
    prompt: `Мира, выступи как SMM-стратег.

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
Что я продаю/продвигаю: [вставь продукт]`,
  },
  offer: {
    icon: "💸",
    title: "Продающий оффер",
    short: "Упакуй продукт за 10 секунд",
    prompt: `Мира, выступи как маркетолог прямого отклика.

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
Цена/формат: [вставь]`,
  },
  exam: {
    icon: "🧠",
    title: "Подготовка к экзамену",
    short: "План, тесты, шпаргалка",
    prompt: `Мира, выступи как личный преподаватель.

Помоги мне подготовиться к экзамену по теме: [вставь тему].

Дай:
— объяснение простыми словами;
— план подготовки на 7 дней;
— главные термины;
— 10 тестовых вопросов;
— типичные ошибки;
— короткую шпаргалку для повторения.`,
  },
  profile: {
    icon: "🧑‍💻",
    title: "Резюме / профиль",
    short: "Bio, опыт, отклик",
    prompt: `Мира, выступи как карьерный консультант и копирайтер.

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
Кого хочу привлечь: [вставь]`,
  },
};

const screens = {
  home: document.querySelector("#home-screen"),
  detail: document.querySelector("#detail-screen"),
  success: document.querySelector("#success-screen"),
  leaderboard: document.querySelector("#leaderboard-screen"),
  stats: document.querySelector("#stats-screen"),
};

const taskList = document.querySelector("#task-list");
const detailTitle = document.querySelector("#detail-title");
const detailKicker = document.querySelector("#detail-kicker");
const detailDescription = document.querySelector("#detail-description");
const promptPreview = document.querySelector("#prompt-preview");
const toast = document.querySelector("#toast");
const navButtons = {
  home: document.querySelector("#nav-home"),
  leaderboard: document.querySelector("#nav-leaderboard"),
  stats: document.querySelector("#nav-stats"),
};

let currentPromptId = "content_plan";
let toastTimeout;

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.("#080812");
  tg.setBackgroundColor?.("#080812");
}

function haptic(type = "impact") {
  if (!tg?.HapticFeedback) return;
  if (type === "success") {
    tg.HapticFeedback.notificationOccurred("success");
    return;
  }
  tg.HapticFeedback.impactOccurred("light");
}

function sendData(payload) {
  if (!tg?.sendData) {
    showToast("Открыто в браузере: событие не отправлено");
    return;
  }
  tg.sendData(JSON.stringify(payload));
}

function showScreen(screenName) {
  Object.values(screens).forEach((screen) => {
    screen.classList.remove("screen-active");
  });
  Object.values(navButtons).forEach((button) => {
    button.classList.remove("nav-button-active");
  });
  navButtons[screenName]?.classList.add("nav-button-active");
  screens[screenName].classList.add("screen-active");
  window.scrollTo({ top: 0, behavior: "auto" });
}

function showToast(message) {
  clearTimeout(toastTimeout);
  toast.textContent = message;
  toast.classList.add("toast-visible");
  toastTimeout = window.setTimeout(() => {
    toast.classList.remove("toast-visible");
  }, 1800);
}

function renderTasks() {
  taskList.innerHTML = "";
  Object.entries(PROMPTS).forEach(([promptId, prompt], index) => {
    const button = document.createElement("button");
    button.className = "task-card";
    button.type = "button";
    button.style.animationDelay = `${index * 55}ms`;
    button.innerHTML = `
      <span class="task-icon" aria-hidden="true">${prompt.icon}</span>
      <span>
        <span class="task-title">${prompt.title}</span>
        <span class="task-description">${prompt.short}</span>
      </span>
    `;
    button.addEventListener("click", () => selectPrompt(promptId));
    taskList.append(button);
  });
}

function selectPrompt(promptId) {
  const prompt = PROMPTS[promptId];
  if (!prompt) return;

  currentPromptId = promptId;
  detailKicker.textContent = prompt.icon + " Challenge task";
  detailTitle.textContent = prompt.title;
  detailDescription.textContent = prompt.short;
  promptPreview.textContent = prompt.prompt;
  haptic();
  showScreen("detail");
}

async function copyPrompt() {
  const prompt = PROMPTS[currentPromptId]?.prompt;
  if (!prompt) return;

  try {
    await navigator.clipboard.writeText(prompt);
    haptic("success");
    showToast("Промпт скопирован");
  } catch {
    showToast("Не удалось скопировать");
  }
}

function openMira() {
  haptic();
  if (tg?.openTelegramLink && MIRA_LINK.startsWith("https://t.me/")) {
    tg.openTelegramLink(MIRA_LINK);
    return;
  }
  window.open(MIRA_LINK, "_blank", "noopener,noreferrer");
}

function markDone() {
  haptic("success");
  sendData({ action: "done_clicked", prompt_id: currentPromptId });
  showScreen("success");
}

function requestUpload() {
  haptic();
  sendData({ action: "upload_requested", prompt_id: currentPromptId });
  window.setTimeout(() => tg?.close?.(), 180);
}

function refreshLeaderboardInBot() {
  haptic();
  sendData({ action: "leaderboard_opened" });
  window.setTimeout(() => tg?.close?.(), 180);
}

function refreshStatsInBot() {
  haptic();
  sendData({ action: "stats_opened" });
  window.setTimeout(() => tg?.close?.(), 180);
}

document.querySelector("#detail-back").addEventListener("click", () => showScreen("home"));
document.querySelector("#leaderboard-back").addEventListener("click", () => showScreen("home"));
document.querySelector("#stats-back").addEventListener("click", () => showScreen("home"));
document.querySelector("#copy-prompt").addEventListener("click", copyPrompt);
document.querySelector("#open-mira").addEventListener("click", openMira);
document.querySelector("#mark-done").addEventListener("click", markDone);
document.querySelector("#request-upload").addEventListener("click", requestUpload);
document.querySelector("#success-upload").addEventListener("click", requestUpload);
document.querySelector("#success-home").addEventListener("click", () => showScreen("home"));
document.querySelector("#open-leaderboard").addEventListener("click", () => showScreen("leaderboard"));
document.querySelector("#refresh-leaderboard").addEventListener("click", refreshLeaderboardInBot);
document.querySelector("#refresh-stats").addEventListener("click", refreshStatsInBot);
navButtons.home.addEventListener("click", () => showScreen("home"));
navButtons.leaderboard.addEventListener("click", () => showScreen("leaderboard"));
navButtons.stats.addEventListener("click", () => showScreen("stats"));

initTelegram();
renderTasks();
