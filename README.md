# teen-museum-residence-2026
Материалы совместной летней школы с ГМИИ им. Пушкина

## Skills

### sourcecraft-sites
Создаёт и публикует простой статический сайт на SourceCraft Sites: создаёт публичный репозиторий через CLI `src`, наполняет его файлами `site/index.html` и `.sourcecraft/sites.yaml`, пушит в `main` и сообщает адрес `https://<org-slug>.sourcecraft.site/<repo-slug>`.

Установка: скопируйте папку `skills/sourcecraft-sites` в `~/.config/opencode/skills/sourcecraft-sites/` (глобально) или в `.opencode/skills/sourcecraft-sites/` текущего проекта, затем перезапустите opencode.

Пример запроса: «Создай сайт на SourceCraft Sites для организации myorg».

### mobile-web-app
Генерирует файлы мобильного веб-приложения (PWA) из статического сайта: web manifest, service worker, meta-теги для iOS и Android, раскладку мобильного приложения с адаптацией под десктоп. Готовый сайт можно «Добавить на главный экран» на iPhone и Android. Скилл только создаёт файлы; публикацию делает sourcecraft-sites или GitHub Pages.

Установка: скопируйте папку `skills/mobile-web-app` в `~/.config/opencode/skills/mobile-web-app/` (глобально) или в `.opencode/skills/mobile-web-app/` текущего проекта, затем перезапустите opencode.

Пример запроса: «Сделай сайт мобильным приложением с нижней навигацией — Главная/Каталог/О себе — и опубликуй на SourceCraft Sites для организации myorg».
