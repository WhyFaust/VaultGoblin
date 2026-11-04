---
name: vaultgoblin-setup
description: Set up or migrate the VaultGoblin Codex plugin, configure an existing local Obsidian vault
  and unique device name, or repair or disable its knowledge export automation. Preserve local settings
  and use the installed setup workflow; ordinary knowledge recall uses codex-shared-knowledge.
metadata:
  short-description: Configure VaultGoblin and its export automation
  version: 0.1.1
---

# Настройка VaultGoblin

Python 3.10+ с SQLite FTS5 должен быть доступен как `python` на Windows или
`python3` на Linux/macOS. На Windows рядом с ним нужен `pythonw.exe`, доступный
через PATH. Плагин не устанавливает Python и не вызывает модель для экспорта.

Скрипт настройки находится в `../codex-shared-knowledge/scripts/plugin_setup.py`
относительно каталога этого навыка. Используй его абсолютный путь из установленного
плагина. Не запускай старый скрипт из `repository_path` или другого клона.

Прочитай `CODEX_HOME/shared-knowledge.json`, если он существует, и сохраняй
текущие vault, device и дополнительные поля. При первой настройке узнай местный
путь к уже синхронизируемому Obsidian vault и уникальное имя устройства.
Настройка плагина не разрешает выбирать или создавать другой vault за пользователя.

Выполни `python <абсолютный-путь>/plugin_setup.py` для существующей установки.
При первой настройке добавь `--vault "<местный путь>" --device <имя>`.
На Windows настройка включает тихую задачу экспорта при входе и каждые пять минут.
Если пользователь запросил ручной режим, передай `--no-automation`.
Для отключения существующей автоматизации используй `--no-automation` без
`--vault` и `--device`. Этот путь не проверяет доступность vault или FTS5,
не устанавливает runtime и сохраняет прежние местные параметры.

Настройщик сохраняет runtime вне кэша плагина, переносит распознанную прежнюю
копию навыка в backup и удаляет только собственные устаревшие hooks и правила.
Чужие обработчики, инструкции, память, настройки vault и ID тем сохраняются.
Новые hooks нужно просмотреть и разрешить в Codex Settings > Hooks или `/hooks`.
Не записывай `trusted_hash` и не представляй установку плагина как доверие hooks.

Если клиент не обнаруживает hooks плагина, Setup с `--profile-hooks` регистрирует
`SessionStart`, `Stop` и `SessionEnd` в hooks.json текущего профиля. Точка запуска
хранится в `CODEX_HOME/scripts/vaultgoblin_hook.py`, runtime — в
`CODEX_HOME/vaultgoblin/runtime/`. Эти пути сохраняются при замене кэша плагина.
Setup запоминает выбранный режим и распознаёт уже существующие собственные
профильные hooks. При обновлении повторяй Setup из новой установленной версии.
Профильный режим предотвращает повторный экспорт через плагинные события.
Проверь определения обычным способом в Settings > Hooks. Отключение через
`--no-automation` работает и для профильных hooks без доступного vault.

На Linux для поздней записи памяти используй событийный `watch` и пользовательский
сервис из `docs/automation.md` в корне плагина. Установка зависимости и сервиса
выполняется в рамках запрошенной автоматизации. На macOS доступны ручной экспорт
и поиск; автоматический наблюдатель этой версии поддерживает Linux.

Проверь результат команды. Сообщи местный профиль, устройство, выбранный режим
автоэкспорта и оставшийся шаг доверия hooks. Не запускай экспорт реальной памяти
как проверку установки, если пользователь поручил только настройку.
