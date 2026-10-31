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

# Log — {{title}}

Append-only journal of ingest / compile / update events. Each row is a
single line summary written by the script that performed the action.
Newest entries at the bottom.

| Date | Event | Summary |
|------|-------|---------|
| {{date}} | init | wiki-space created in {{mode}} mode |
