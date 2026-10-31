# Документы, заметки и Wiki

Русский | [English](pipeline_en.md)

## Установка

Компонент необязателен для поиска общих знаний Codex. Из корня проекта:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r pipeline/requirements.txt
cp pipeline/config.example.toml pipeline/config.toml
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements.txt
Copy-Item pipeline/config.example.toml pipeline/config.toml
```

Копируйте пример только для новой установки. В существующей сохраняйте свой
`config.toml` и реестры обработки. Укажите `vault.vault_path`; для путей Windows
в TOML удобны `/` или одинарные кавычки. Пустой `rclone.staging_dir` означает
временную папку ОС. Для Google Drive отдельно настройте rclone и `rclone.remote`.

Дальше команды выполняются из `pipeline/`. На Windows заменяйте
`../.venv/bin/python` на `..\.venv\Scripts\python.exe -X utf8`.

## Wiki из выбранных источников

```bash
cd pipeline
../.venv/bin/python scripts/wiki_init.py my-project --mode project --title "Мой проект" --lang ru
../.venv/bin/python scripts/wiki_ingest.py my-project /path/to/source.md --kind docs --no-compile
../.venv/bin/python scripts/wiki_compile.py my-project --since-last-compile --dry-run
../.venv/bin/python scripts/wiki_compile.py my-project --since-last-compile
../.venv/bin/python scripts/wiki_lint.py my-project --strict
```

Обычная компиляция вызывает авторизованный Codex CLI. `--backend claude` выбирает
другой поддерживаемый backend; `VAULTGOBLIN_BACKEND` задаёт выбор для окружения.
При запуске внутри агента автоопределение учитывает его окружение. Модель и её
настройки определяет CLI, а не VaultGoblin. `--dry-run` не вызывает модель.

`project` создаёт основные страницы проекта; `corpus` начинает с общей структуры
и накапливает сущности и понятия. Для шаблонов доступны `--lang ru` и `--lang en`.
`wiki_ingest.py` принимает файл или каталог с `--kind articles|docs|transcripts|assets`.

Wiki живёт в `<vault>/<wiki_folder>/<slug>/`:

| Слой | Назначение |
|---|---|
| `raw/` | Неизменяемые исходники |
| `pages/`, `entities/`, `concepts/`, `comparisons/`, `queries/` | Скомпилированные страницы |
| `SCHEMA.md`, `index.md`, `log.md` | Контракт, навигация и журнал обработанных источников |

Компиляция сохраняет существующие wikilinks и проверяет снимок источников перед
записью. Переносимый журнал хранит SHA-256 нормализованного UTF-8 текста в
`log.md`; локальный путь не входит в идентичность источника. Исторические хеши
поддерживаются. `raw/_README.md` не является входом.

Для одной новой порции используйте `wiki_update.py <slug> raw/docs/file.md`.
`--raw-only` явно выбирает источники для повторной обработки; `--update-only`
обновляет навигацию без подтверждения новых источников. Старые локальные
подтверждения переносит `wiki_compile.py <slug> --migrate-compile-state`.
Сначала проверьте его с `--dry-run`: изменившиеся и неизвестные входы не подтверждаются.

Завершайте синхронизацию перед переключением ПК. Один процесс записи на Wiki;
общей транзакции для всех страниц нет. При частичном сбое некоторые страницы уже
могут обновиться: исправьте причину и повторите с новым снимком. Не обходите ошибки
`WIKI_LINKS_LOST`, `WIKI_SNAPSHOT_CHANGED` и `WIKI_WRITE_FORBIDDEN`.

## Атомарные заметки и контакты

| Задача | Команда после `../.venv/bin/python` |
|---|---|
| Документ `.docx`, локальный или из rclone | `scripts/process.py "Document.docx"` |
| Существующая заметка | `scripts/process_note.py "Note Title" --mode atomize` |
| Сохранить одну заметку и доработать её | `scripts/process_note.py "Note Title" --mode enrich` |
| Контакты из заметки | `scripts/process_contacts.py "Contacts Note"` |
| Готовый JSON-план без вызова модели | `scripts/process.py plan.json --from-plan` |
| Только Markdown из плана | `scripts/generate_notes.py plan.json` |

Для автоматических запусков, где поддерживается, задавайте
`--non-interactive --on-conflict skip|overwrite`. Сначала смотрите `--help`.
Семантическая обработка вызывает модель; она должна сохранять смысл исходника.
Обычные заметки и Wiki изолированы. Правила находятся в `rules/`, промпты —
в `prompts/`, примеры — в `examples/`. Запись генерации проходит через
`vault_writer.py`, который проверяет контур и конфликты.

## NotebookLM

Необязательная интеграция требует местной авторизации. Для установки браузерных
зависимостей выполните из `pipeline/`:

```bash
../.venv/bin/python scripts/notebooklm_setup.py --skip-login
```

Затем в отдельном интерактивном терминале запустите `../.venv/bin/notebooklm login`,
войдите в Google и завершите вход по подсказке. На Windows команда находится в
`..\.venv\Scripts\notebooklm.exe`. Учётные данные не синхронизируются через Git.

`process_notebook.py <id>` забирает подготовленные заметки и обрабатывает их;
`fetch_notebook.py <id>` только выгружает вход. Дополнения: `--include-sources`,
`--include-mindmap`, `--profile <name>`. При `NOTEBOOKLM_AUTH_REQUIRED` проверьте
зависимости и местную сессию, не копируйте авторизацию другого ПК.

`research_notebook.py run <id> "query" --dry-run` показывает план research.
Без `--dry-run` выполняется research и однократный импорт результатов.
`research_notebook.py dedupe <id> --dry-run` показывает дубли для явной чистки.
Прерывание импорта не повод автоматически повторять его: сначала проверьте результат.

## Поиск и обслуживание vault

`memory_index.py status` показывает отдельный индекс всего vault. Первый
`memory_index.py build` запускается явно; после него writer может обновлять индекс
через `[memory].auto_update`. `search "query" --json` поддерживает `--folder`,
`--tag`, `--limit`, `--prefix` и `--raw`. Это не индекс общих знаний Codex.

`doctor.py` проверяет местную установку и выбранный backend; rclone и NotebookLM
нужны только своим сценариям. `audit_vault.py`, `dedup_vault.py`,
`fix_similar_notes.py`, `fix_atomic_notes.py` и `archive_empty_notes.py` — явные
операции обслуживания. Начинайте с `--help` и `--dry-run`; не запускайте их
автоматически при обычном поиске знаний.
