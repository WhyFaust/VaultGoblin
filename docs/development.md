# Разработка

Русский | [English](development_en.md)

## Структура

Два компонента независимы: навык общих знаний использует только стандартную
библиотеку, а `pipeline/` содержит импорт и Wiki с отдельными зависимостями.
Установленная копия навыка не является источником изменений.

| Каталог | Назначение |
|---|---|
| `skills/codex-shared-knowledge/scripts/` | Экспорт, FTS5-поиск и установка задачи Windows |
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
