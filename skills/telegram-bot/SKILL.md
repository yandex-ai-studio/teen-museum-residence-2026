---
name: telegram-bot
description: "Создаёт и запускает Telegram-бота на pyTelegramBotAPI (telebot) в режиме поллинга: проект, .env с секретами, requirements.txt, локальное окружение через uv, локальный запуск; по отдельной просьбе — развёртывание на удалённом сервере по SSH. Используй, когда нужно сделать телеграм-бота."
---

# Telegram Bot: бот на telebot в режиме поллинга

Скилл создаёт проект Telegram-бота на библиотеке pyTelegramBotAPI (telebot) и запускает его на локальной машине. Бот работает только в режиме поллинга — никаких вебхуков и веб-серверов. Секреты хранятся в `.env`, зависимости — в `requirements.txt`, окружение создаётся менеджером `uv`. По отдельной явной просьбе пользователя скилл может развернуть бота на удалённом облачном сервере, доступном по SSH.

Скилл рассчитан на работу на разных машинах (Windows, macOS, Linux): не предполагай инструментов конкретной платформы, запускай Python через `uv run`, используй относительные пути. SSH проверяй только при запросе развёртывания на сервере.

## Параметры

Параметры передаются в промпте или уточняются в чате. Не начинай писать код, пока не известны имя бота и его функциональность.

- `bot_name` (обязательный) — имя бота; используется как имя проекта и каталога `bots/<bot_name>`.
- `functionality` (обязательный) — что умеет бот: команды, текстовые ответы, инлайн-клавиатуры, callback-кнопки, состояния, обращения к внешним API. Переспроси, если из запроса непонятно.
- `dir` (по умолчанию `bots/<bot_name>` в текущей рабочей директории) — каталог проекта; создать при необходимости.
- Для удалённого развёртывания дополнительные параметры описаны в разделе «Удалённый сервер».

## Предусловия

1. Проверь наличие `uv`: `uv --version`. Если команда не найдена — сообщи пользователю, как установить менеджер, и дождись подтверждения:

   - Windows: `winget install astral-sh.uv` или `pip install uv`
   - macOS: `brew install uv` или `pip install uv`
   - Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` или `pip install uv`

   Фолбэк на обычное окружение `python -m venv .venv` + `pip install -r requirements.txt` — только с явного согласия пользователя.

2. SSH и `scp` проверяй только на шаге развёртывания на сервере. Для локальной работы они не нужны.

## Шаги

1. Уточни `bot_name` и `functionality`. Определи `dir` (по умолчанию `bots/<bot_name>`), создай каталог, если его нет.

2. Секреты — файл `.env`:

   - Если в `dir` уже есть `.env` — используй его: прочитай, какие ключи заданы, и не перезаписывай файл без необходимости.
   - Если `.env` нет — опроси пользователя. Всегда запрашивай `TELEGRAM_TOKEN`; остальные ключи запрашивай, только если они реально нужны под `functionality` (например, ключ внешнего API). Запиши `.env` в кодировке UTF-8, каждая строка `KEY=value` без кавычек:

     ```
     TELEGRAM_TOKEN=123456:ABC-DEF...
     ```

   - Создай рядом `.env.example` с теми же ключами, но без значений.
   - Никогда не выводи токены и значения секретов в чат, логи, код или коммиты.

3. Структура проекта в `dir`:

   ```
   <dir>/
     bot.py             # главный файл: обработчики и запуск поллинга
     requirements.txt   # зависимости
     .env               # секреты (в git не попадает)
     .env.example       # шаблон ключей без значений
     .gitignore         # .env, .venv, __pycache__/
   ```

   `.gitignore`:

   ```
   .env
   .venv/
   __pycache__/
   *.pyc
   ```

4. Код `bot.py` — только поллинг:

   - Начало файла: загрузка секретов через python-dotenv и проверка токена.
   - Обработчики под запрошенную `functionality`.
   - Запуск строго поллингом: `bot.infinity_polling(...)`. Не вызывай `set_webhook`/`delete_webhook` из кода и не поднимай HTTP-сервер. Каркас:

   ```python
   import os

   import telebot
   from dotenv import load_dotenv

   load_dotenv()

   TOKEN = os.getenv("TELEGRAM_TOKEN")
   if not TOKEN:
       raise SystemExit("TELEGRAM_TOKEN не найден в файле .env")

   bot = telebot.TeleBot(TOKEN)

   @bot.message_handler(commands=["start"])
   def on_start(message):
       bot.reply_to(message, f"Привет, {message.from_user.first_name}!")

   @bot.message_handler(func=lambda message: True)
   def on_text(message):
       bot.reply_to(message, message.text)

   if __name__ == "__main__":
       bot.infinity_polling(timeout=60, long_polling_timeout=60)
   ```

   Готовые фрагменты под функциональность:

   - Команда: `@bot.message_handler(commands=["help"])` — аналогично `start`.
   - Инлайн-клавиатура:

     ```python
     from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

     @bot.message_handler(commands=["menu"])
     def on_menu(message):
         kb = InlineKeyboardMarkup()
         kb.add(InlineKeyboardButton("Нажми", callback_data="press"))
         bot.send_message(message.chat.id, "Меню", reply_markup=kb)
     ```

   - Обработка нажатий на кнопки:

     ```python
     @bot.callback_query_handler(func=lambda call: True)
     def on_callback(call):
         bot.answer_callback_query(call.id)
         bot.edit_message_text("Нажато", call.message.chat.id, call.message.message_id)
     ```

   - Долгие операции (сеть, генерация) выноси в отдельный поток или очередь — обработчики поллинга иначе блокируют друг друга.

5. Зависимости и окружение:

   - Запиши в `requirements.txt` только реально используемые библиотеки и сразу обновляй файл при добавлении новых импортов. Минимум:

     ```
     pyTelegramBotAPI>=4.14.0
     python-dotenv>=1.0.0
     ```

   - Создай окружение и установи зависимости в `dir`:

     ```
     uv venv
     uv pip install -r requirements.txt
     ```

   - Запускай Python только через `uv run python ...` — так локальное окружение используется одинаково на всех платформах.

6. Локальный запуск (основной сценарий):

   - Запусти бота: `uv run python bot.py` (из `dir`).
   - Проверь логи: не должно быть ошибок авторизации и исключений.
   - Попроси пользователя написать боту `/start` и проверить ответ; при необходимости посмотри логи ещё раз.
   - Остановка — Ctrl+C. Сообщи пользователю команду для следующего запуска.

7. Удалённый сервер (только по явной просьбе «разверни на сервере»):

   - Уточни: `host`, `user`, порт (по умолчанию 22), способ авторизации (SSH-ключ или пароль) и `remote_path` на сервере (по умолчанию `/home/<user>/bots/<bot_name>`, используй абсолютный путь).
   - Проверь доступ и наличие инструментов: `ssh <user>@<host> "python3 --version && which uv"`. Если `uv` на сервере нет — предложи установку: `curl -LsSf https://astral.sh/uv/install.sh | sh` или `pip install uv`.
   - Перенеси файлы проекта без служебных каталогов:

     ```
     scp bot.py requirements.txt .env.example .gitignore <user>@<host>:<remote_path>/
     ```

     Файл `.env`: спроси пользователя — скопировать локальный `.env` на сервер (`scp .env <user>@<host>:<remote_path>/`) или задать токен заново; значения секретов не выводи.
   - Создай окружение на сервере:

     ```
     ssh <user>@<host> "cd <remote_path> && uv venv && uv pip install -r requirements.txt"
     ```

   - Настрой постоянную работу. Если на сервере есть systemd — unit `/etc/systemd/system/bot-<bot_name>.service`:

     ```
     [Unit]
     Description=Telegram bot <bot_name>
     After=network-online.target

     [Service]
     Type=simple
     User=<user>
     WorkingDirectory=<remote_path>
     ExecStart=<remote_path>/.venv/bin/python bot.py
     Restart=always
     RestartSec=5

     [Install]
     WantedBy=multi-user.target
     ```

     Установка юнита: скопируй файл на сервер, затем `systemctl daemon-reload && systemctl enable --now bot-<bot_name>.service`. Если systemd недоступен — фолбэк: `ssh <user>@<host> "cd <remote_path> && nohup .venv/bin/python bot.py > bot.log 2>&1 &"` или сессия `tmux`.
   - Проверь: посмотри журнал `ssh <user>@<host> "journalctl -u bot-<bot_name>.service -n 20 --no-pager"`, затем попроси пользователя написать боту `/start`.

8. Итог — сообщи пользователю пути к созданным файлам, команду локального запуска и, если делался деплой, имя сервиса и путь на сервере.

## Чек-лист

- В `dir` лежат `bot.py`, `requirements.txt`, `.env`, `.env.example`, `.gitignore`.
- `.env` добавлен в `.gitignore`; в коде и коммитах нет секретов.
- В `bot.py` нет вебхук-вызовов и веб-сервера — только `infinity_polling()`.
- В `requirements.txt` перечислены все импортируемые библиотеки (минимум `pyTelegramBotAPI`, `python-dotenv`).
- Окружение создано через `uv venv`, зависимости — `uv pip install -r requirements.txt`, запуск — `uv run python bot.py`.
- Локальный запуск проверен: бот отвечает на `/start`.
- (Если делался деплой) — сервис на сервере работает, `Restart=always`, лог проверен.

## Troubleshooting

- `uv: command not found` — uv не установлен; дай команды установки из раздела «Предусловия» и дождись подтверждения.
- `Invalid token: 401 Unauthorized` — неверный `TELEGRAM_TOKEN`; проверь `.env`, токен выдаёт @BotFather.
- `Conflict: can't use getUpdates method while a webhook is active` — бот уже запущен через вебхук (например, другими инструментами); предложи пользователю снять вебхук: `curl -X POST https://api.telegram.org/bot<TOKEN>/deleteWebhook`, затем запусти заново.
- Бот не отвечает — проверь, что пользователь написал именно боту, посмотри логи запуска; для групп проверь privacy mode (`/setprivacy` у @BotFather).
- Бот «молчит» при долгой операции — обработчики поллинга выполняются в одном потоке; длительные вызовы выноси в отдельные потоки или очереди.
- Терминал занят процессом бота — это нормально для поллинга; на сервере используй systemd, `tmux` или `nohup`.
- `permission denied` при `ssh`/`scp` — проверь ключ и права на `remote_path`.
- Бот не встаёт после перезапуска сервера — проверь, что юнит включён (`systemctl enable bot-<bot_name>.service`) и лог `ExecStart` в `journalctl -u ...`.