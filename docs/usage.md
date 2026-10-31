# Установка и работа между ПК

Русский | [English](usage_en.md)

## Общие знания Codex

Сначала настройте синхронизацию одного Obsidian vault на устройствах. VaultGoblin
не передаёт файлы сам: это делает ваш Obsidian Sync, Remotely Save или другой
выбранный механизм. Дождитесь завершения синхронизации.

Клонируйте проект в постоянную папку и выполните из его корня:

```bash
git clone https://github.com/WhyFaust/VaultGoblin.git
cd VaultGoblin
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/путь/к/Obsidian Vault" --device main-pc
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Нужен Python 3.10+ с SQLite FTS5. Для этого компонента пакеты устанавливать не нужно.
На Windows используйте `python`. Пример для PowerShell:

```powershell
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py install --vault "C:\Users\name\Documents\Obsidian Vault" --device windows-pc
python .\skills\codex-shared-knowledge\scripts\shared_knowledge.py export
```

Имя устройства: строчные латинские буквы, цифры, `_` и `-`, до 64 символов.
На втором ПК повторите команды с его путём к тому же vault и другим именем.
Авторизацию, внутренние базы и папку `memories` Codex между ПК копировать не нужно.

Установщик записывает местные настройки в `CODEX_HOME/shared-knowledge.json`,
копирует навык в `CODEX_HOME/skills/` и добавляет небольшой блок в `AGENTS.md`.
По умолчанию `CODEX_HOME` — `~/.codex`. Остальные инструкции сохраняются.
Для новых правил откройте новый чат Codex.

Если Codex ещё не сформировал локальную память, экспорт вернёт `no_local_memory`.
Это не мешает чтению знаний другого устройства. Созданием нативной памяти
управляет Codex; VaultGoblin её не генерирует и не изменяет.

## Проверка чтения

```bash
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py recall "SQLite" --project my-project
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py search "SQLite" --limit 3
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py read "ID-ИЗ-ВЫДАЧИ"
```

Для проверки возьмите слова из реально экспортированной темы. Пустая выдача на
произвольный запрос ничего не доказывает. `--project` — строгий фильтр; для общего
контекста опустите его. `warnings` сообщает о неполной синхронизации или изменённом
источнике. [Формат, ограничения поиска и восстановление](shared-knowledge.md).

## Автоэкспорт

Экспорт выполняется отдельно от поиска и не вызывает модель. На Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\skills\codex-shared-knowledge\scripts\install_export_task.ps1 -PythonPath (Get-Command python.exe).Source
```

Задача `Codex Shared Knowledge Export` запускается при входе и каждые 5 минут
для текущего пользователя. Лог: `CODEX_HOME/shared-knowledge-export.log`.
Задача использует текущий клон; не переносите его без переустановки задачи.
Если Python находится в `.venv`, передайте его полный путь в `-PythonPath`.

На Linux используйте уже настроенный пользовательский systemd timer. Команда:

```text
/absolute/path/to/python3 /absolute/path/to/VaultGoblin/skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Сохраните в сервисе местный `CODEX_HOME`, если он отличается от `~/.codex`.
Без планировщика экспорт можно запускать вручную.

## Обновление существующей установки

```bash
git pull --ff-only
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py install \
  --vault "/местный/путь/к/vault" --device existing-device-name
python3 skills/codex-shared-knowledge/scripts/shared_knowledge.py export
```

Сохраните прежние `vault_path` и `device` из местного JSON. `repository_path`
обновится на этот клон; произвольные дополнительные настройки сохранятся.
Установленный навык — рабочая копия, редактировать нужно исходники в Git-клоне.

После перехода со старой структуры переустановите задачу или поправьте `ExecStart`
таймера: скрипт теперь находится в `skills/codex-shared-knowledge/scripts/`.
Для импорта и Wiki перенесите свой `config.toml`, `processed.json` и реестры из
прежней папки компонента в `pipeline/`, не заменяя их примером. Индекс vault теперь
по умолчанию в `~/.cache/vaultgoblin/`: его можно построить заново явной командой
или указать прежний каталог в `[memory].db_dir`. Заметки и их ID не меняются.

Установка импорта и Wiki: [руководство пайплайна](pipeline.md).

Хуки завершения хода и сессии: [настройка автоматизации](automation.md).
