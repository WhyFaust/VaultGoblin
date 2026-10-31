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

This file is the **frozen contract** for the `{{slug}}` wiki-space. Once written it
should change only when the schema itself evolves; never edit it during normal
ingest or compile cycles.

## Mode

`{{mode}}`

- **project** — fixed core pages (overview, architecture, components, workflows,
  goals-and-roadmap, glossary, open-questions). Entities and concepts grow as
  raw is added; core pages must always exist.
- **corpus** — only entities/concepts/comparisons/queries grow as raw is added.
  No mandatory page set.

## Description

{{description}}

## Layout

```
{{slug}}/
├── SCHEMA.md          # this file (frozen)
├── index.md           # auto-regenerated each compile
├── log.md             # append-only ingest/compile journal
├── raw/               # immutable inputs, never edited by LLM
│   ├── articles/
│   ├── docs/
│   ├── transcripts/
│   └── assets/
├── pages/             # core knowledge pages (project mode only)
├── entities/          # services, integrations, external systems
├── concepts/          # domain concepts
├── comparisons/       # A vs B writeups
├── queries/           # saved useful questions and answers
└── readouts/          # dated patch/experiment readouts (immutable after verdict)
```

## Frontmatter contract

Every wiki page **must** carry these fields:

- `note_type: wiki`
- `wiki_project: {{slug}}` (must match enclosing folder)
- `wiki_page_type`: one of `core | entity | concept | comparison | query | readout | raw | meta`
- `wiki_status`: one of `stub | draft | stable | stale | contradicted | ingested`
- `date`: ISO date of last touch
- `source_doc`: synthetic id `wiki:{{slug}}:<page_type>:<stem>` (raw notes may
  carry the original filename instead)

Optional but reserved:

- `confidence`: `high | medium | low` — pages tagged `low` must open with a
  `> [!warning]` callout
- `sources`: list of `raw/...md` paths that the page draws on
- `related`: list of slugs (NOT `[[wikilinks]]`) for cross-reference

## Invariants

1. **No silent rewrites.** `wiki_compile.py` snapshots existing wikilinks
   before prompting the LLM. If a `[[link]]` from the snapshot disappears
   from a page after merge, the compile fails with `WIKI_LINKS_LOST`.
2. **Single writer.** Only `vault_writer.py` touches files inside this
   wiki-space. No script appends to `log.md` directly.
3. **Wiki contour isolation.** Atomic notes / MOCs / contacts never land
   inside `{{slug}}/`; wiki pages never land outside it.
4. **Machine-owned pages.** Compiled pages (`pages/`, `entities/`,
   `concepts/`, `comparisons/`, `queries/`, `readouts/`) are rewritten by
   `wiki_compile.py` from `raw/` + snapshot. Hand-edits to their prose are
   not guaranteed to survive the next compile — add a `raw/` input and
   recompile instead of editing pages by hand.
