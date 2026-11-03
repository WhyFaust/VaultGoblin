# Установка и работа между ПК

Русский | [English](usage_en.md)

## Плагин Codex

Сначала настройте синхронизацию одного Obsidian vault на устройствах. VaultGoblin
не передаёт файлы сам: это делает ваш Obsidian Sync, Remotely Save или другой
выбранный механизм. Дождитесь завершения синхронизации.

Нужны Python 3.10+ с SQLite FTS5 и Codex с поддержкой установки плагинов.
Поиск и экспорт используют стандартную библиотеку, без API, модели и сервера.
На Windows `python` и `pythonw.exe` должны быть доступны в `PATH`.

```bash
codex plugin marketplace add WhyFaust/VaultGoblin
codex plugin add vaultgoblin@vaultgoblin
```

В Codex откройте **Setup** у плагина или явно вызовите `$vaultgoblin-setup`.
При первой настройке укажите путь к существующему vault и имя устройства.
Имя состоит из строчных латинских букв, цифр, `_` и `-`, до 64 символов.
На другом ПК используйте его местный путь к тому же vault и другое имя.

Setup запускает `skills/codex-shared-knowledge/scripts/plugin_setup.py` из активного
плагина. Для первой установки ему нужны `--vault` и `--device`; повторный запуск
без них сохраняет прежние поля `CODEX_HOME/shared-knowledge.json`. По умолчанию
`CODEX_HOME` — `~/.codex`. На Windows Setup также устанавливает тихую задачу
экспорта при входе и раз в 5 минут.

Разрешите новые определения в **Settings > Hooks** или `/hooks`. Установщик не
меняет `trusted_hash` и не обходит проверку доверия Codex. После обновления кода
плагина может потребоваться повторное разрешение hooks. Для обнаружения навыков
откройте новый чат.

## Миграция и обновление

При переходе с прежнего навыка запустите Setup без новых параметров. Он сохраняет
vault, имя устройства, дополнительные местные настройки, индекс и экспортированные
темы. Удаляются только прежние обработчики с меткой VaultGoblin и собственный
блок инструкций в `AGENTS.md`; распознанная копия старого навыка переносится в
`CODEX_HOME/backups/vaultgoblin-plugin/`. Посторонние hooks и правила остаются.

При работе через плагин код берётся из его активной установки. Старое поле
`repository_path` не переключает выполнение на клон. Setup и `SessionStart`
обновляют стабильную копию двух Python-скриптов и установщика задачи в
`CODEX_HOME/vaultgoblin/runtime/`. Задача Windows использует этот путь, поэтому
обновление каталога кэша плагина не оставляет ссылку на удалённую версию.

Обновляйте плагин через Codex; при необходимости повторите Setup без параметров.
Исходники меняют в Git-клоне, а не в кэше плагина и не в стабильном runtime.

Авторизацию, внутренние базы Codex и папку `memories` между ПК не копируют.
Если локальная память ещё не создана, экспорт возвращает `no_local_memory`,
но знания другого устройства доступны для чтения. VaultGoblin не генерирует
и не изменяет нативную память Codex.

## Поиск и ручной экспорт

Навык `codex-shared-knowledge` выбирает подходящий скрипт активного плагина.
Для ручной команды после Setup можно использовать стабильный runtime.
Пример для стандартного `CODEX_HOME` на Linux/macOS:

```bash
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py recall "SQLite" --project my-project
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py search "SQLite" --limit 3
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py read "ID-ИЗ-ВЫДАЧИ"
python3 ~/.codex/vaultgoblin/runtime/shared_knowledge.py export
```

На Windows PowerShell используйте `python` и путь
`"$HOME\.codex\vaultgoblin\runtime\shared_knowledge.py"`.
Для другого `CODEX_HOME` замените путь своим.

Для проверки чтения возьмите слова из реально экспортированной темы. Пустая
выдача на произвольный запрос ничего не доказывает. `--project` — строгий фильтр;
для общего контекста опустите его. `warnings` сообщает о неполной синхронизации
или изменённом источнике. [Формат, ограничения и восстановление](shared-knowledge.md).

## Автоматизация и удаление плагина

На Linux используйте событийный `watch` и пользовательский systemd-сервис;
плагин не запускает экспорт на каждый конец чата. На macOS используйте ручной
экспорт. Подробности и отдельная установка автоматизации Windows —
в [руководстве автоматизации](automation.md).

Перед удалением плагина запустите Setup с `--no-automation`, например попросите
`$vaultgoblin-setup` отключить автоматизацию. Это отключает hooks плагина через
местную настройку и удаляет только его задачу текущего профиля. Затем удалите
плагин средствами Codex. Сама по себе деинсталляция плагина не удаляет задачу
Windows; пользовательские настройки и знания сохраняются.

## Установка без плагина

Если ваш Codex не поддерживает plugin CLI, установите навык из постоянного клона:

```bash
git clone https://github.com/WhyFaust/VaultGoblin.git
cd VaultGoblin
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/путь/к/Obsidian Vault" --device main-pc
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

На Windows используйте `python`. `install` сохраняет настройки, копирует навык
в `CODEX_HOME/skills/`, добавляет условный поиск в `AGENTS.md` и подготавливает
стабильный runtime. Откройте новый чат. Для обновления выполните `git pull --ff-only`
и повторите `install` с прежними `vault_path` и `device`; дополнительные местные
поля сохраняются. Настройка автоматизации описана [отдельно](automation.md).

Установка импорта и Wiki: [руководство пайплайна](pipeline.md). Если переносите
прежнюю установку пайплайна, сохраните свои `config.toml`, `processed.json` и
реестры в `pipeline/`, не заменяя их примерами. Индекс vault можно перестроить
явной командой либо сохранить прежний каталог через `[memory].db_dir`.
