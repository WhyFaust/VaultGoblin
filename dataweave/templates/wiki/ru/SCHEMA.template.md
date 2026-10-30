---
tags:
  - wiki/meta
date: {{date}}
source_doc: "wiki:{{slug}}:meta:SCHEMA"
note_type: wiki
wiki_project: {{slug}}
wiki_page_type: meta
wiki_status: stable
wiki_mode: {{mode}}
---

# SCHEMA — {{title}}

Этот файл — **замороженный контракт** wiki-space `{{slug}}`. После создания
он меняется только при эволюции самой схемы. Не редактируй его в обычных
циклах ингеста или компиляции.

## Режим

`{{mode}}`

- **project** — фиксированные core-страницы (overview, architecture,
  components, workflows, goals-and-roadmap, glossary, open-questions).
  Entities и concepts растут по мере появления сырья; core-страницы
  обязаны существовать всегда.
- **corpus** — растут только entities/concepts/comparisons/queries по
  мере ингеста. Обязательного набора страниц нет.

## Описание

{{description}}

## Структура

```
{{slug}}/
├── SCHEMA.md          # этот файл (заморожен)
├── index.md           # авто-перегенерируется при каждом compile
├── log.md             # append-only журнал ingest / compile / update
├── raw/               # неизменяемое сырьё; LLM никогда не редактирует
│   ├── articles/
│   ├── docs/
│   ├── transcripts/
│   └── assets/
├── pages/             # core-страницы знания (только в режиме project)
├── entities/          # сервисы, интеграции, внешние системы
├── concepts/          # доменные концепты
├── comparisons/       # разборы A vs B
├── queries/           # сохранённые полезные запросы и ответы
└── readouts/          # датированные отчёты о патчах/экспериментах (immutable после verdict'а)
```

## Контракт frontmatter

Каждая wiki-страница **обязана** нести следующие поля:

- `note_type: wiki`
- `wiki_project: {{slug}}` (должен совпадать с именем родительской папки)
- `wiki_page_type`: одно из `core | entity | concept | comparison | query | readout | raw | meta`
- `wiki_status`: одно из `stub | draft | stable | stale | contradicted | ingested`
- `date`: ISO-дата последнего изменения
- `source_doc`: синтетический id `wiki:{{slug}}:<page_type>:<stem>` (raw-заметки
  могут нести вместо него оригинальное имя файла)

Опциональные, но зарезервированные поля:

- `confidence`: `high | medium | low` — страницы с `low` обязаны открываться
  блоком `> [!warning]`
- `sources`: список путей `raw/...md`, на которые опирается страница
- `related`: список slug'ов (НЕ `[[wikilinks]]`) для перекрёстных связей

## Инварианты

1. **Никаких молчаливых перезаписей.** `wiki_compile.py` снимает снапшот
   существующих wikilinks перед обращением к LLM. Если `[[ссылка]]` из
   снапшота исчезает со страницы после merge, compile падает с
   `WIKI_LINKS_LOST`.
2. **Единственный writer.** Только `vault_writer.py` пишет в файлы внутри
   этой wiki-space. Ни один скрипт не дописывает в `log.md` напрямую.
3. **Изоляция wiki-контура.** Атомарные заметки / MOC / контакты никогда
   не попадают внутрь `{{slug}}/`; wiki-страницы никогда не попадают
   наружу.
4. **Страницы принадлежат машине.** Скомпилированные страницы (`pages/`,
   `entities/`, `concepts/`, `comparisons/`, `queries/`, `readouts/`)
   перезаписываются `wiki_compile.py` из `raw/` + снапшота. Ручные правки
   их прозы не гарантированно переживают следующий compile — вместо правки
   страниц руками добавь вход в `raw/` и перекомпилируй.
