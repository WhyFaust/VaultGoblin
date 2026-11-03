# Разработка

Русский | [English](development_en.md)

## Структура

Два компонента независимы: навык общих знаний использует только стандартную
библиотеку, а `pipeline/` содержит импорт и Wiki с отдельными зависимостями.
Исходники меняют в Git-клоне. Корневой `plugin.json` содержит переносимый манифест;
`extensions.com.openai` задаёт `hooks/hooks.json` и onboarding-навык
`skills/vaultgoblin-setup/SKILL.md`. Каталог `.agents/plugins/marketplace.json`
публикует этот корень как плагин `vaultgoblin` в одноимённом marketplace.

Код выполняется из активной установки плагина. Setup и `SessionStart` обновляют
`CODEX_HOME/vaultgoblin/runtime/` для задачи Windows. Этот runtime, кэш плагина
и прежняя установленная копия навыка не являются источниками изменений.

| Каталог | Назначение |
|---|---|
| `plugin.json`, `.agents/plugins/marketplace.json` | Манифест плагина и каталог установки |
| `hooks/` | Переносимые определения hooks и точка запуска |
| `skills/vaultgoblin-setup/` | Первичная настройка, миграция и управление автоматизацией |
| `skills/codex-shared-knowledge/scripts/` | Экспорт, FTS5-поиск, runtime и установка задачи Windows |
| `skills/codex-shared-knowledge/tests/` | Регрессии экспорта, ID, области поиска и лимитов контекста |
| `pipeline/scripts/` | Команды обработки и общие модули |
| `pipeline/prompts/` | Короткие инструкции модели, без установки агента и справочника команд |
| `pipeline/rules/` | Контракты заметок, таксономии и Wiki |
| `pipeline/templates/wiki/` | RU/EN шаблоны Wiki |
| `pipeline/examples/` | Примеры обычных заметок |
| `pipeline/tests/` | Проверки Wiki, записи, индекса и обработки документов |
| `docs/` | Парные руководства RU/EN |

## Проверки

Из корня репозитория, Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest -r pipeline/requirements.txt
.venv/bin/python -W error::EncodingWarning -X warn_default_encoding -m unittest discover -s skills/codex-shared-knowledge/tests -q
cd pipeline
../.venv/bin/python -X utf8 -m pytest -q
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest -r pipeline/requirements.txt
.\.venv\Scripts\python.exe -W error::EncodingWarning -X warn_default_encoding -m unittest discover -s skills/codex-shared-knowledge/tests -q
Push-Location pipeline
..\.venv\Scripts\python.exe -X utf8 -m pytest -q
Pop-Location
```

Для плагина проверяйте манифест и marketplace, ссылки внутри пакета, обновление
runtime и миграцию прежних hooks без изменения посторонних настроек. Используйте
отдельные временные `CODEX_HOME` и vault. Настоящая установка Setup на Windows
изменяет планировщик, поэтому не запускайте её как обычную проверку файлов.

Отдельный job `plugin` устанавливает пакет через `codex-cli 0.157.1` в изолированном
`CODEX_HOME` на Ubuntu, без API и вызовов модели. Он проверяет установку пакета,
но не пользовательское доверие hooks и не работу планировщика Windows.

CI запускает оба набора на Linux и Windows. Тесты используют временные данные
и подменяют внешние вызовы. Они не подтверждают доступность NotebookLM, Google
Drive, модели или доставку файлов выбранным механизмом синхронизации Obsidian.

Для проверки CLI достаточно `--help`. `doctor.py` читает местную конфигурацию;
`memory_index.py build` индексирует настоящий vault и не является обычным тестом.
Прогон через внешнюю модель выполняйте отдельно по конкретной задаче.

## Локальные данные

Не коммитьте `config.toml`, `shared-knowledge.json`, авторизацию, `.env`,
`processed.json`, реестры дедупликации, staging, vault, экспорты памяти и базы
SQLite. Они исключены корневым `.gitignore`. Пример настроек не содержит личных
путей или учётных данных. Новые временные файлы создавайте через `tempfile`.

При переносе скрипта обновляйте вызовы, инструкции навыка, планировщик и оба
руководства. Для Wiki сохраняйте проверку снимка, ссылок и запись через writer.
Новый индекс должен оставаться совместимым с уже установленными устройствами.

## Проверка наблюдателя Linux

```bash
.venv/bin/python -m pip install -r skills/codex-shared-knowledge/requirements-watch.txt
.venv/bin/python skills/codex-shared-knowledge/tests/check_memory_watcher.py
```

Интеграционная проверка использует временные файлы, включая атомарную замену
и новую запись во время экспорта. Реальная память Codex не изменяется.
