---
name: vm-deploy
description: "Разворачивает Python-проект (телеграм-бот, сайт, любое приложение на uv) на готовой виртуальной машине Yandex Cloud по SSH: права на SSH-ключ, установка uv на VM, копирование проекта в ~/projects/, создание окружения и скриптов запуска/остановки/статуса. Используй, когда нужно разместить проект на удалённом сервере."
---

# VM Deploy: развёртывание Python-проекта на виртуальной машине

Скилл размещает Python-проект на виртуальной машине Yandex Cloud, доступной по SSH. Машина уже создана, её адрес, имя пользователя и файл с приватным SSH-ключом лежат в файле `vm.yml` (допускается `vm.yaml`). Проект копируется в `~/projects/<имя-проекта>` на VM, там создаётся окружение через `uv`, устанавливаются зависимости, а на локальной машине генерируются скрипты запуска, остановки и проверки статуса (`.bat` на Windows, `.sh` на macOS/Linux), которые подключаются к VM по SSH.

Скилл рассчитан на работу с разных машин (Windows, macOS, Linux) и с разными проектами: телеграм-бот в режиме поллинга, веб-сервис, любое изолированное через `uv` приложение. Копирование на VM выполняется только через `scp` — он есть в составе OpenSSH на любых платформах, тогда как `rsync`/rclone на Windows обычно не установлены. Не запускай ничего на VM, пока не исправлены права на ключ.

## Параметры

Параметры передаются в промпте или уточняются в чате:

- `vm_file` (по умолчанию `vm.yml` в корне рабочей директории) — YAML-файл с ключами `ip`, `user`, `key`. Файл ищется в корне workspace; если его нет — спроси пользователя, где он. Возможный формат:

  ```yaml
  ip: 51.250.28.73
  user: yc-user
  key: team-0.key
  ```

  Значение `key` — имя файла с приватным SSH-ключом; путь до ключа резолвится относительно каталога `vm_file` (например, `vm.yml` в корне и `team-0.key` рядом с ним).

- `project_dir` (обязательный) — каталог локального проекта, который нужно развернуть.

- `project_name` (по умолчанию — базовое имя `project_dir`) — имя проекта; используется как имя удалённого каталога `~/projects/<project_name>`. Пробелы и спецсимволы в имени замени на `-`.

- `entry` (обязательный) — файл, который запускает проект. Определяется автоматически: проверь по очереди `bot.py`, `main.py`, `app.py` в корне проекта; если ни один не найден или их несколько — уточни у пользователя.

- Тип зависимостей определяется автоматически по файлам проекта:
  - есть `pyproject.toml` (uv-проект) — подготовка окружения через `uv sync`;
  - иначе есть `requirements.txt` — через `uv venv` + `uv pip install -r requirements.txt`.

## Предусловия

1. Найди `vm_file` и прочитай из него `ip`, `user`, `key`. Проверь, что файл ключа существует по вычисленному пути.

2. Убедись, что `ssh` доступен локально: `ssh -V`.

3. Проверь права на файл ключа и исправь их — без этого SSH откажется работать. Команды зависят от ОС локальной машины:

   - Windows (cmd):

     ```
     icacls "<путь-до-ключа>" /inheritance:r
     icacls "<путь-до-ключа>" /grant:r "%username%":"(R)"
     ```

     В PowerShell замени `%username%` на `$env:USERNAME`:

     ```
     icacls "<путь-до-ключа>" /grant:r "$env:USERNAME":"(R)"
     ```

   - macOS/Linux — ключ должен быть доступен только владельцу:

     ```
     chmod 600 "<путь-до-ключа>"
     ```

     Если ключ лежит в Git Bash/WSL на Windows — тоже используй `chmod 600`.

4. Проверь подключение (флаг `StrictHostKeyChecking=accept-new` убирает вопрос о подтверждении host key при первом входе):

   ```
   ssh -i "<путь-до-ключа>" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new <user>@<ip> "echo OK"
   ```

   Если подключение не проходит — смотри Troubleshooting.

## Шаги

1. Определи параметры проекта: найди `entry`, определи тип зависимостей, проверь, есть ли в проекте `.env` с секретами (если есть — он нужен и на VM, но не выводи его содержимое в чат и не показывай в логах).

2. Установи `uv` на VM, если его нет. Бинарь ставится в `~/.local/bin`; в неинтерактивных ssh-сессиях PATH из профиля не подхватывается, поэтому в каждую ssh-команду, где нужен `uv`, добавляй export PATH:

   ```
   ssh -i "<путь-до-ключа>" <user>@<ip> "command -v uv || (curl -LsSf https://astral.sh/uv/install.sh | sh)"
   ```

   Затем проверь установку:

   ```
   ssh -i "<путь-до-ключа>" <user>@<ip> "export PATH=\"\$HOME/.local/bin:\$PATH\" && uv --version"
   ```

   Обрати внимание: `\$HOME` и `\$PATH` экранированы, чтобы локальная оболочка не подставила свои значения. Если `curl` на VM нет — фолбэк `pip install uv` (при наличии pip). Когда после этого в командах используется `uv`, всегда пиши префикс `export PATH="$HOME/.local/bin:$PATH" && ...` или вызывай полный путь `~/.local/bin/uv`.

3. Создай удалённый каталог проекта:

   ```
   ssh -i "<путь-до-ключа>" <user>@<ip> "mkdir -p ~/projects/<project_name>"
   ```

4. Скопируй проект на VM только через `scp`. Никогда не копируй на VM файл `vm_file` и приватные ключи (`*.key`) — удали их из каталога проекта перед копированием или после неё. `scp -r` не умеет исключать файлы, поэтому сначала копируется весь каталог, потом на VM удаляется лишнее:

   ```
   scp -r -i "<путь-до-ключа>" "<project_dir>" <user>@<ip>:~/projects/
   ssh -i "<путь-до-ключа>" <user>@<ip> "cd ~/projects/<project_name> && rm -rf -- .venv .git __pycache__ .pytest_cache"
   ```

   Удаляй на VM ровно то, что присутствует локально и не должно попасть на VM: окружение и мусор (`.venv`, `.git`, `__pycache__`, `.pytest_cache`), а также `vm.yml`, `vm.yaml` и любые `*.key` в каталоге проекта. `scp -r` копирует и скрытые файлы, поэтому `.env` окажется на VM автоматически, если он есть в `project_dir`.

   После копирования проверь состав удалённого каталога: `ssh ... "ls -la ~/projects/<project_name>"`. Файл `.env` должен оказаться на VM (если был локально), `vm.yml` и ключи — нет.

5. Создай окружение на VM в зависимости от типа проекта:

   - uv-проект (`pyproject.toml`):

     ```
     ssh -i "<путь-до-ключа>" <user>@<ip> "export PATH=\"\$HOME/.local/bin:\$PATH\" && cd ~/projects/<project_name> && uv venv && uv sync"
     ```

   - проект с `requirements.txt`:

     ```
     ssh -i "<путь-до-ключа>" <user>@<ip> "export PATH=\"\$HOME/.local/bin:\$PATH\" && cd ~/projects/<project_name> && uv venv && uv pip install -r requirements.txt"
     ```

     Если `uv` не находит нужную версию Python — uv сам скачает managed Python при вызове `uv venv`; при необходимости добавь явно `uv python install <версия>`.

6. Сгенерируй скрипты. В каталоге проекта на локальной машине создай удалённый помощник `deploy.sh` и тонкие обёртки над ним: `start.bat`, `stop.bat`, `status.bat` (Windows) и `start.sh`, `stop.sh`, `status.sh` (Unix). Вся логика (запуск через `uv run`, остановка через kill) живёт в `deploy.sh` — так удаётся избежать проблем с экранированием кавычек между cmd/PowerShell и ssh. Значения `ip`, `user`, путь к ключу и имя проекта подставь в обёртки как есть, без чтения `vm.yml` в рантайме. Содержимое файлов — ниже.

   `deploy.sh` (копируется на VM и запускается удалённо): он сам подправляет PATH, переходит в свой каталог и умеет `start | stop | status`:

   ```bash
   #!/usr/bin/env bash
   set -u
   export PATH="$HOME/.local/bin:$PATH"
   cd "$(cd "$(dirname "$0")" && pwd)"
   ENTRY="<entry>"
   case "${1:-}" in
     start)
       # setsid создаёт отдельную группу процессов: kill группы потом остановит и uv, и python
       setsid nohup uv run python "$ENTRY" >> app.log 2>&1 < /dev/null &
       echo $! > app.pid
       echo "started, pid=$(cat app.pid), log: $(pwd)/app.log"
       ;;
     stop)
       pid="$(cat app.pid 2>/dev/null || true)"
       if [ -n "$pid" ]; then
         kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
       fi
       pkill -f "python .*${ENTRY}" 2>/dev/null || true
       rm -f app.pid
       echo "stopped"
       ;;
     status)
       pid="$(cat app.pid 2>/dev/null || true)"
       if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
         echo "running, pid=$pid"
         ps -o pid,etime,cmd -p "$pid"
         echo "--- app.log (last 20 lines) ---"
         tail -n 20 app.log 2>/dev/null || true
       else
         echo "not running"
       fi
       ;;
     *)
       echo "usage: deploy.sh {start|stop|status}" >&2
       exit 1
       ;;
   esac
   ```

   Если на VM нет `setsid` (проверь `command -v setsid`) — `kill -- -pid` не сработает, и остановка сработает через фолбэки `kill "$pid"` и `pkill -f "python .*<entry>"`.

   `start.bat` (Windows), в `<...>` — реальные значения из `vm.yml` и имя проекта:

   ```bat
   @echo off
   ssh -i "<абсолютный-путь-до-ключа>" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new <user>@<ip> "bash ~/projects/<project_name>/deploy.sh start"
   pause
   ```

   `stop.bat`:

   ```bat
   @echo off
   ssh -i "<абсолютный-путь-до-ключа>" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new <user>@<ip> "bash ~/projects/<project_name>/deploy.sh stop"
   pause
   ```

   `status.bat` — то же, но с `deploy.sh status`.

   `start.sh` (macOS/Linux):

   ```sh
   #!/usr/bin/env bash
   ssh -i "<абсолютный-путь-до-ключа>" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new <user>@<ip> "bash ~/projects/<project_name>/deploy.sh start"
   ```

   `stop.sh` и `status.sh` — по аналогии (замени `start` на `stop`/`status`). Сделай `.sh`-файлы исполняемыми: `chmod +x start.sh stop.sh status.sh`.

   Скопируй `deploy.sh` на VM и сделай исполняемым (заодно завершится шаг генерации):

   ```
   scp -i "<путь-до-ключа>" "<project_dir>/deploy.sh" <user>@<ip>:~/projects/<project_name>/deploy.sh
   ssh -i "<путь-до-ключа>" <user>@<ip> "chmod +x ~/projects/<project_name>/deploy.sh"
   ```

   Сгенерированные скрипты не содержат секретов, их можно коммитить; если не хочется — добавь их в `.gitignore` проекта.

7. Запусти проект и проверь:

   ```
   ssh -i "<путь-до-ключа>" <user>@<ip> "bash ~/projects/<project_name>/deploy.sh status"
   ```

   Должно быть `running, pid=...`. Посмотри хвост лога целиком: `ssh ... "tail -n 50 ~/projects/<project_name>/app.log"`. В логе не должно быть исключений и ошибок запуска.

   Проверка зависит от типа проекта:

   - Телеграм-бот (поллинг) — попроси пользователя написать боту `/start` и убедись, что он отвечает; при необходимости ещё раз посмотри лог.
   - Веб-сервис — на VM проверь, что процесс слушает порт: `ssh ... "ss -tlnp | grep python"`, и что отвечает локально: `ssh ... "curl -sI http://127.0.0.1:<порт>"`. Для доступа извне напомни пользователю про правила группы безопасности (security group) в консоли Yandex Cloud: входящий трафик на нужный порт должен быть разрешён, иначе сайт не откроется по публичному IP, хотя на самой VM он работает.

8. Итог — сообщи пользователю: имя проекта на VM (`~/projects/<project_name>`), как запускать (`start.bat`/`start.sh`), останавливать и смотреть статус, путь к логу `app.log`.

## Обновление проекта (re-deploy)

Развёртывание повторяется по шагам 2–7. Сначала останови старый процесс, потом обнови файлы и запусти заново:

1. `ssh ... "bash ~/projects/<project_name>/deploy.sh stop"`
2. Скопируй изменённые файлы на VM через `scp`. Заново перекопируй весь каталог (команда из шага 4, включая чистку на VM) либо только изменённые файлы по одному: `scp -i "<ключ>" <файл> <user>@<ip>:~/projects/<project_name>/`.
3. При изменении зависимостей повтори шаг 5 (создание окружения).
4. `ssh ... "bash ~/projects/<project_name>/deploy.sh start"`, затем проверь статус и лог.

## Чек-лист

- `vm_file` найден, `ip`/`user`/`key` прочитаны, путь до ключа верный.
- Права на ключ исправлены: Windows — `icacls /inheritance:r` + `/grant:r`, Unix — `chmod 600`.
- `ssh "echo OK"` проходит с `StrictHostKeyChecking=accept-new`.
- `uv` установлен на VM и работает (`uv --version` через `export PATH="$HOME/.local/bin:$PATH"`).
- Проект лежит в `~/projects/<project_name>`; там нет `vm.yml`, приватных ключей, `.venv`, `.git`; `.env` на месте.
- Окружение создано (`uv sync` или `uv pip install -r requirements.txt`), приложение стартует без ошибок.
- В проекте сгенерированы `deploy.sh` (загружен на VM) и обёртки `start`/`stop`/`status` для платформы пользователя.
- `deploy.sh status` показывает `running`, в `app.log` нет ошибок; проверка для бота/веб-сервиса пройдена (или пользователю сообщено, что нужно сделать).

## Troubleshooting

- Если появляется ошибка соединения с api.telegram.org - используй явный ip-адрес 149.154.167.220, можно прописать такой адрес в /etc/hosts (но лучше предварительно убедиться, что с ним есть соединение)
- `UNPROTECTED PRIVATE KEY FILE` или `Permissions 0644 ... are too open` — ключ доступен другим пользователям; исправь права: `chmod 600` (Unix) или icacls-команды из Предусловий (Windows).
- Подключение висит на запросе `Are you sure you want to continue connecting` — первый вход; используй `-o StrictHostKeyChecking=accept-new` один раз, чтобы принять host key автоматически.
- `uv: command not found` при запуске из-под ssh — в неинтерактивной сессии не подгружается PATH из профиля; добавляй `export PATH="$HOME/.local/bin:$PATH" && ...` в начало команды или используй полный путь `~/.local/bin/uv`.
- `Host key verification failed` — host key изменился (пересоздание VM); удали старую запись `ssh-keygen -R <ip>` и повтори подключение с `accept-new`.
- После `stop` процесс ещё жив — проверь `ps -ef | grep <entry>`; если процессы запускались вне `setsid` — добей вручную: `pkill -f "python .*<entry>"`.
- `setsid: command not found` — утилита отсутствует на VM; остановка сработает через фолбэк `kill $(cat app.pid)` + `pkill`.
- Проект запущен, но внешне не отвечает (веб) — проверь `ss -tlnp` на VM (слушает ли порт, не только 127.0.0.1) и правила security group в консоли Yandex Cloud.
- `permission denied` при `scp` — проверь права на удалённый каталог и его владельца (`ls -la ~/projects`).
- `curl: command not found` на VM — используй `python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:<порт>').status)"`.
- Проблемы с зависимостями — убедись, что на VM работает тот же механизм установки, что и локально (`uv sync` для uv-проекта, иначе `requirements.txt`); при несовпадении версии Python uv сам скачает managed Python.