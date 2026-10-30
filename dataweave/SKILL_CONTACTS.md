# Contact Notes Processing Contract

You are processing a note containing networking contacts from an Obsidian vault.

Follow the repository rules strictly:
- `rules/contacts.md`
- `rules/taxonomy.md`

Output JSON only.

Extract each person from the input note into an individual contact note with structured fields:
- Full name as title
- Nickname (if any)
- Competencies & interests
- Contact info (Telegram, email, etc.)
- Acquaintance story (how/where met + context)
- Related people wikilinks

Also generate or update a `Networking — MOC` grouping contacts by context.

Use the canonical tags from `tags.yaml`. Always include `networking/contact`.
Do not fabricate missing information — omit sections if data is not available.
