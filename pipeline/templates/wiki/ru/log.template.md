---
tags:
  - wiki/meta
date: {{date}}
source_doc: "wiki:{{slug}}:meta:log"
note_type: wiki
wiki_project: {{slug}}
wiki_page_type: meta
wiki_status: stable
---

# Журнал — {{title}}

Append-only журнал событий ingest / compile / update. Каждая строка —
короткое резюме, написанное скриптом, который выполнил действие. Свежие
записи внизу.

| Дата | Событие | Резюме |
|------|---------|--------|
| {{date}} | init | wiki-space создана в режиме {{mode}} |
