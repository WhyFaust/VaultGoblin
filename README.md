# 🧌 VaultGoblin

**Гоблин, который таскает полезные знания между твоими ПК.**

Документы и заметки превращаются в связанную Wiki внутри Obsidian. Codex может
вспоминать решения с другого устройства коротким поисковым запросом: выдача
ограничена по размеру, а исходные заметки остаются в твоём vault.

| Компонент | Задача |
| --- | --- |
| [`dataweave/`](dataweave/) | Импорт документов и NotebookLM, атомарные заметки, Wiki, локальный поиск по vault. |
| [`codex-shared-knowledge/`](codex-shared-knowledge/) | Экспорт знаний Codex, перенос через Obsidian и короткие проверенные фрагменты для работы на другом ПК. |

Синхронизацию папки Obsidian выполняет уже настроенный Remotely Save или другой
выбранный тобой механизм. Каждый ПК хранит собственный поисковый индекс.

## Быстрый старт

Нужны Python 3.10+, SQLite с FTS5 и Obsidian vault. Для Wiki-компиляции нужен
авторизованный Codex или Claude CLI; для Google Drive и NotebookLM — их отдельная
локальная настройка. Общий поиск Codex работает на стандартной библиотеке Python.

```bash
git clone https://github.com/WhyFaust/VaultGoblin.git
cd VaultGoblin
```

### Общие знания Codex между ПК

На каждом устройстве установи навык, указав местный путь к vault и уникальное имя:

```bash
python3 codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/путь/к/Obsidian Vault" --device main-pc

python3 codex-shared-knowledge/scripts/shared_knowledge.py export
python3 codex-shared-knowledge/scripts/shared_knowledge.py recall "SQLite" --project my-project
```

На Windows используй `python`. Если устройство уже настроено, возьми его имя
из местного `CODEX_HOME/shared-knowledge.json`. На втором ПК укажи его собственный
путь к тому же синхронизируемому vault и другое имя устройства.

`recall` возвращает до двух фрагментов, `search` — до трёх указателей.
Полный JSON по умолчанию ограничен 6000 символами. При готовом индексе перед выдачей
сверяются только выбранные 1–3 источника. `--project` задаёт строгий фильтр;
для общего контекста его можно опустить. Индекс обновляется при изменении файлов,
экспорт запускается отдельно. Подробности: [установка и автоэкспорт](docs/shared-knowledge.md).

### Документы и Wiki

Для Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r dataweave/requirements.txt
cp dataweave/config.example.toml dataweave/config.toml
```

Укажи свой `vault_path` в `dataweave/config.toml`, затем создай пространство:

```bash
.venv/bin/python dataweave/scripts/wiki_init.py my-project \
  --mode project --title "Мой проект" --lang ru

.venv/bin/python dataweave/scripts/wiki_ingest.py my-project \
  /путь/к/источнику.md --kind docs --no-compile
```

Компиляция выполняется отдельной командой и обращается к выбранной модели:

```bash
.venv/bin/python dataweave/scripts/wiki_compile.py my-project --since-last-compile
.venv/bin/python dataweave/scripts/wiki_lint.py my-project --strict
```

Обработанные источники учитываются в переносимом журнале внутри vault.
Запись Wiki сохраняет существующие ссылки и проверяет, что исходные файлы
не изменились во время обработки. Подробные сценарии: [документация DataWeave](dataweave/README.md).

## Локальные данные

Настройки с реальными путями, авторизация, заметки, экспорты устройств, журнал
обработки и SQLite-индексы создаются локально и исключены из Git.
Исходные `memory_summary.md` и `MEMORY.md` остаются под управлением Codex;
экспорт создаёт отдельный справочный слой в Obsidian. Исторические сведения
из него нужно проверять по актуальному коду и сервисам.

## Проверка

```bash
python3 -m pip install pytest -r dataweave/requirements.txt
cd dataweave
python3 -m pytest -q
cd ..
python3 -m unittest discover -s codex-shared-knowledge/tests -v
```

При подготовке этой версии на Linux прошли 243 теста DataWeave и 48 тестов
общих знаний. GitHub Actions повторяет проверки при изменениях; общий поиск
также проверяется на Windows. Тесты используют временные данные.

## Происхождение

VaultGoblin — отдельный проект, который объединяет локально доработанный
[ObsidianDataWeave](https://github.com/howdeploy/ObsidianDataWeave) и навык
общих знаний Codex. Авторство и MIT-лицензия исходного проекта сохранены:
[LICENSE](LICENSE), [THIRD_PARTY.md](THIRD_PARTY.md).
