# Comparing approaches

[Русский](comparison.md) | English

Checked on 2026-10-31 against project sources and documentation. This compares
capabilities and adoption costs, not measured speed or retrieval quality.
Competitors were not installed into the working vault.

| Tool | Main purpose | Suitable when |
|---|---|---|
| VaultGoblin | Per-device native Codex memory export, bounded FTS5 recall and a separate Wiki pipeline | You already sync a vault and need earlier decisions with a small context budget |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | Markdown, a relationship graph, MCP tools, semantic and hybrid search | Several AI clients need to create and edit a shared knowledge base through a server |
| [QMD](https://github.com/tobi/qmd) | Local BM25, vector search and model reranking | Meaning-based retrieval over a large document collection justifies maintaining local models |
| [Obsidian Mind](https://github.com/breferrari/obsidian-mind) | An organized vault, session context, message classification and hooks; optional QMD | You want a broader multi-agent workflow and its note structure |
| [Obsidian Memory](https://github.com/kkonstvol-lab/obsidian-memory) | Source-backed Wiki, separate operational agent memory and runtime hooks | You want a broader knowledge workflow with its own contracts and checks |
| [Obsidian CLI](https://obsidian.md/help/cli) | Reading, searching and controlling Obsidian itself | Actions in Obsidian are needed; the CLI requires the app to run |

## Decision for VaultGoblin

Keep two independent components and existing vault synchronization. Lexical search
is a simple, testable choice for short technical queries with IDs, function names
and projects. Its limitation is real: a query with no vocabulary overlap may miss
the right topic. A small RU/EN alias dictionary does not fully solve that.

Useful practices from the comparison:

- Explicit data boundaries: native memory, shared exports, Wiki and regular notes
  are separate. Maintenance must not mutate Wiki sources or generated exports.
- Small automation handlers: hooks export prepared memory; a timer catches delayed
  updates, while context retrieval follows the task.
- Failure-based tests: filename conflicts, interrupted manifests, parallel search
  and partial writer results need specific regressions.
- One code source and a short second-device setup, without independently maintained
  script copies.

These changes are included in this revision. See the [independent audit and fixes](audit_en.md)
and [automation behavior](automation_en.md).

Choose the next extension using measured misses on an anonymized set of real
queries. If lexical recall proves insufficient, first benchmark QMD on a separate
shared-knowledge collection while preserving budgets and source checks. MCP becomes
useful when another client cannot conveniently use the existing CLI. These features
have not been added without a demonstrated need.

Comparative recall, latency on the same corpus, RAM usage and competitors on the
second PC were not tested. Stars and project claims were not treated as reliability
evidence.
