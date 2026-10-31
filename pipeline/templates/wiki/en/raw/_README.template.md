---
tags:
  - wiki/raw
date: {{date}}
source_doc: "wiki:{{slug}}:meta:raw-readme"
note_type: wiki
wiki_project: {{slug}}
wiki_page_type: meta
wiki_status: stable
---

# raw/ — {{title}}

This folder holds the **immutable inputs** that every compile pass reads
from. Files here are never modified by any wiki script — only added by
`wiki_ingest.py` and consumed (read-only) by `wiki_compile.py`.

## Subfolders

- `articles/` — long-form prose, blog posts, papers
- `docs/` — reference docs, README files, design docs
- `transcripts/` — meeting / podcast / interview transcripts
- `assets/` — code excerpts, JSON dumps, screenshots, anything else

## Naming convention

`<YYYY-MM-DD>-<slug>.md`. Slugs are kebab-case ASCII; `wiki_ingest.py`
generates them automatically from the input filename.

## Why a separate raw layer

The raw layer is the **source of truth**. Compiled wiki pages can be
regenerated from raw + SCHEMA at any time. Pages in `entities/`,
`concepts/`, etc. are *interpretations* — they accumulate, summarize,
and link, but the raw layer remains the audit trail.
