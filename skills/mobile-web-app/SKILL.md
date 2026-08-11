---
name: mobile-web-app
description: "Генерирует файлы мобильного веб-приложения (PWA) из статического сайта: web manifest, service worker, meta-теги для iOS и Android, раскладку мобильного приложения с адаптацией под десктоп. Используй, когда нужно превратить статический сайт в приложение, которое можно добавить на главный экран iPhone или Android, а также вместе со скиллом sourcecraft-sites или при публикации на GitHub Pages."
---

# Mobile Web App: мобильное веб-приложение из статического сайта

Скилл превращает статический сайт в мобильное веб-приложение (PWA): создаёт в целевой директории файлы приложения — app shell, manifest, service worker, иконку и стили — благодаря которым страницу можно «Добавить на главный экран» на iPhone и Android и открывать как самостоятельное приложение.

Скилл только генерирует файлы, публикацию делает другой инструмент: `sourcecraft-sites` (SourceCraft Sites) или GitHub Pages. Сценарии запуска:

- отдельно — скилл создаёт приложение в текущей директории;
- в связке с sourcecraft-sites — приложение создаётся в каталоге `site/` клонированного репозитория (см. раздел «Совместное использование»).

## Параметры

Параметры передаются в промпте или уточняются в чате. Не начинай работу, пока не известны имя приложения и решение по нижней навигации.

- `app_name` (обязательный) — название приложения; короткая версия до 12 символов идёт в `short_name`.
- `bottom_nav` (обязательный вопрос) — нужна ли нижняя навигация. Спроси пользователя; если да — уточни разделы (2–4 пункта, например «Главная», «Каталог», «О себе»). Если ответа нет — переспроси один раз.
- `description` (по умолчанию пусто) — краткое описание приложения для manifest.
- `lang` (по умолчанию `ru`) — язык интерфейса.
- `theme_color` (по умолчанию `#1e3a8a`) — основной цвет приложения: шапка, статус-бар, иконка.
- `background_color` (по умолчанию `#f8fafc`) — цвет фона до загрузки страницы.
- `dir` (по умолчанию `site`) — директория, куда кладутся файлы приложения. Если её нет — создать; если в ней уже есть `index.html` (например, приветственная страница из sourcecraft-sites) — заменить его каркасом приложения.

## Файлы

Создай в `dir` структуру:

```
<dir>/
  index.html
  styles.css
  app.js
  manifest.webmanifest
  sw.js
  icon.svg
```

Все внутренние ссылки — только относительные пути вида `./name`. Сайт публикуется из поддиректории (`https://<org>.sourcecraft.site/<repo>` или GitHub Pages-проект), поэтому абсолютные пути вида `/assets/...` сломают приложение.

## Шаги

1. Уточни параметры: `app_name` и вопрос про нижнюю навигацию (обязательно). Остальное бери из промпта или значения по умолчанию. Определись с `dir`: в связке с sourcecraft-sites это `<клон репозитория>/site`.

2. Создай `index.html`:

   - `<html lang="<lang>">`, `<meta charset="utf-8">`, viewport `width=device-width, initial-scale=1, viewport-fit=cover`.
   - Meta-теги для iOS и Android:

     ```html
     <meta name="mobile-web-app-capable" content="yes">
     <meta name="apple-mobile-web-app-capable" content="yes">
     <meta name="apple-mobile-web-app-title" content="<app_name>">
     <meta name="apple-mobile-web-app-status-bar-style" content="default">
     <meta name="theme-color" content="<theme_color>">
     <link rel="manifest" href="manifest.webmanifest">
     <link rel="icon" type="image/svg+xml" href="icon.svg">
     ```

     `apple-touch-icon` (PNG 180×180) добавляй, только если пользователь предоставил готовый PNG.
   - Каркас приложения: `<header>` с названием, `<main>` с контентом и, если выбрана нижняя навигация, `<nav>` с таб-баром в конце `<body>`. Стили подключи до скриптов, скрипт — `<script src="app.js" defer></script>`.
   - Таб-бар переключает разделы показом/скрытием секций внутри `<main>` без смены URL: это не ломает `start_url` и кэш service worker.

3. Создай `manifest.webmanifest` (валидный JSON):

   ```json
   {
     "name": "<app_name>",
     "short_name": "<короткая версия до 12 символов>",
     "description": "<description>",
     "lang": "<lang>",
     "start_url": "./",
     "scope": "./",
     "display": "standalone",
     "background_color": "<background_color>",
     "theme_color": "<theme_color>",
     "icons": [
       { "src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any" }
     ]
   }
   ```

4. Создай `sw.js` — короткий service worker «сеть с фолбэком на кэш». Версия кэша позволяет предсказуемо обновлять приложение:

   ```js
   const CACHE = "mobile-web-app-v1";
   const PRECACHE = ["./", "./index.html", "./styles.css", "./app.js", "./manifest.webmanifest", "./icon.svg"];

   self.addEventListener("install", (event) => {
     event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
     self.skipWaiting();
   });

   self.addEventListener("activate", (event) => {
     event.waitUntil(
       caches.keys().then((keys) =>
         Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
       )
     );
     self.clients.claim();
   });

   self.addEventListener("fetch", (event) => {
     if (event.request.method !== "GET") return;
     event.respondWith(
       caches.match(event.request).then((cached) => {
         const network = fetch(event.request)
           .then((response) => {
             if (response.ok) {
               const copy = response.clone();
               caches.open(CACHE).then((cache) => cache.put(event.request, copy));
             }
             return response;
           })
           .catch(() => cached);
         return cached || network;
       })
     );
   });
   ```

   Если в приложении появляются новые статические файлы — добавь их в `PRECACHE` и увеличь версию в `CACHE`.

5. Создай `app.js`:

   ```js
   if ("serviceWorker" in navigator) {
     navigator.serviceWorker.register("./sw.js");
   }
   ```

6. Создай `styles.css` — mobile-first, на десктопе полная адаптивная развёртка:

   - База: `min-height: 100dvh` с фолбэком `100vh` для старых браузеров; `overscroll-behavior: none` на `body`; `-webkit-tap-highlight-color: transparent`; `touch-action: manipulation`; системный шрифт (`system-ui` стек).
   - Шапка и таб-бар (если есть) — `position: sticky` с учётом safe-area: `env(safe-area-inset-top)` / `env(safe-area-inset-bottom)`. Таб-бар не должен перекрывать контент: `main` получает нижний padding `calc(<место таб-бара> + env(safe-area-inset-bottom))`.
   - Тач-цели (кнопки, пункты таб-бара) — не меньше 44×44 px; `user-select: none` только на элементах интерфейса, не на контенте.
   - Десктоп (`@media (min-width: 768px)`): контент раскладывается на всю ширину окна (например, CSS Grid на несколько колонок), ограничение телефонной ширины снимается, шапка и навигация растягиваются на всю ширину. Никакой «телефонной рамки» по центру.
   - Цвета бери из параметров, по умолчанию светлая схема.

7. Создай `icon.svg` — квадратный SVG (viewBox 512×512): закруглённый фон цвета `theme_color`, по центру символ или первые буквы `app_name` контрастным цветом. PNG-иконки не генерируй. Если пользователь дал PNG 180/192/512 — сохрани в `dir`, добавь `apple-touch-icon` в `index.html` и пункты в `icons` manifest.

8. Проверь результат по чек-листу и сообщи пользователю пути к файлам и дальнейшие шаги.

## Чек-лист

- В `dir` лежат все шесть файлов.
- Все внутренние ссылки относительные (`./...`), нет абсолютных путей от корня домена.
- `manifest.webmanifest` — валидный JSON; `start_url` и `scope` равны `./`; `theme_color` совпадает с meta-тегом `theme-color`; `display: standalone`.
- `<html lang="...">` задан; viewport содержит `viewport-fit=cover`.
- Список `PRECACHE` в `sw.js` покрывает все созданные файлы.
- Если выбрана нижняя навигация — на телефоне это закреплённый таб-бар с учётом safe-area.

## Тестирование

- Скилл не публикует сайт; установку на устройство проверяют по HTTPS-адресу после публикации.
- iPhone: открыть сайт в Safari → «Поделиться» → «На главный экран». Android: Chrome → меню → «Установить приложение» или «Добавить на главный экран».
- Быстрый локальный просмотр: `npx serve <dir>` — на `localhost` service worker работает без HTTPS.
- После публикации: открой страницу на телефоне, добавь на главный экран, отключи сеть и проверь, что приложение открывается из кэша.

## Совместное использование

- **sourcecraft-sites**: сначала запусти скилл `sourcecraft-sites` — он создаст и склонирует репозиторий в `sites/<repo>` с файлами `site/index.html` и `.sourcecraft/sites.yaml`. Затем запусти этот скилл с `dir = sites/<repo>/site` — файлы приложения заменят приветственную страницу; `.sourcecraft/sites.yaml` не трогай. После этого закоммить и запушь по шагам скилла sourcecraft-sites.
- **GitHub Pages**: скилл создаёт файлы в `dir`; для публикации положи содержимое `dir` в корень ветки или в `docs/`, включи Pages в настройках репозитория и получи HTTPS-адрес. Пуш и настройку делает пользователь или другой скилл — этот скилл не выполняет git-операции.

## Troubleshooting

- **Service worker не регистрируется** — сайт открыт по HTTP; SW работает только по HTTPS или `localhost`.
- **После обновления открывается старая версия** — увеличь версию кэша (`CACHE`) в `sw.js` и добавь новые файлы в `PRECACHE`.
- **На iPhone вместо иконки превью страницы** — iOS требует PNG-иконку (`apple-touch-icon` 180×180), а по умолчанию мы используем только SVG. Попроси пользователя дать PNG и подключи его.
- **Таб-бар перекрывает контент** — добавь `main` нижний padding на высоту таб-бара плюс `env(safe-area-inset-bottom)`.
- **Manifest не читается** — проверь JSON-валидность и относительность пути к иконке.
- **Сайт в поддиректории открывается не оттуда** — убедись, что `start_url: "./"` и `scope: "./"`, а не `/`.
- **После смены manifest или иконок на iOS ничего не меняется** — удали приложение с главного экрана и добавь заново.