# Contact Notes Processing Rules

You are processing a note containing networking contacts into individual structured contact notes for an Obsidian vault. Follow these rules exactly.

## Core Principle

One note = one person. Each contact note must be self-contained: a reader who has never seen the source note must understand who this person is, what they do, and how the author knows them.

## Input Format

The user provides a free-form note with one or more contacts. The text may include:
- Names (full, partial, or nicknames only)
- Roles, companies, teams
- How/where they met
- Interests, skills, competencies
- Contact info (Telegram, email, phone, LinkedIn, etc.)
- Context notes, impressions, follow-up ideas

Your job: extract each person, fill in the structured fields, and produce individual contact notes.

## Contact Note Structure

Each contact note must follow this exact section order:

### 1. YAML Frontmatter

```yaml
---
tags: [networking/contact, ...]
date: YYYY-MM-DD
source_doc: "Контакты"
note_type: contact
---
```

- `tags`: always include `networking/contact` + 1-4 domain tags from `tags.yaml`
- `date`: processing date (ISO 8601)
- `source_doc`: always `"Контакты"` — this distinguishes contacts from other note types
- `note_type`: always `contact`

### 2. Title (H1)

Use the name **exactly as the user wrote it** in the source note. Do not rename, transliterate, or replace it with a Telegram handle, email, or any other identifier. If the user wrote "omo" — the title is `# omo`. If the user wrote "Влад Печенька" — the title is `# Влад Печенька`. The Telegram handle is only recorded in the Contacts section, never used as the person's name.

### 3. Nickname Line

Immediately after the title, on its own line:

```
**Никнейм:** value
```

If no nickname/alias exists, omit this line entirely. Do not write "нет" or "—".

### 4. Competencies & Interests Section

```
##### Компетенции и интересы
```

1–3 sentences summarizing what this person does, their expertise, and what they are interested in. Use the author's words where possible. If the source text is vague, write what is known and do not fabricate details.

### 5. Contacts Section

```
##### Контакты
```

Bulleted list of contact methods. Telegram handles must be clickable links. Common formats:
- `- Telegram: [@handle](https://t.me/handle)`
- `- Email: address@example.com`
- `- LinkedIn: URL`
- `- Телефон: +7...`
- `- GitHub: [@username](https://github.com/username)`

If no contact info is provided, omit this section entirely.

### 6. Acquaintance Story Section

```
##### История знакомства
```

1–4 sentences combining:
- Where/how the author met this person
- Context of the relationship (work, event, mutual friend, online)
- Any notable impressions or follow-up plans
- Current status of the relationship if mentioned

This is the "story" section — preserve the author's voice and details. Do not genericize.

### 7. Related People Links

```
##### Связанные люди
```

Bulleted list of `[[wikilinks]]` to other contacts from the same processing batch or existing vault notes, with a brief relationship note:

```
- [[Фамилия Имя]] — как связаны
```

Only include links where a real relationship exists (introduced by, works with, same event, same team). Do not link people who have no described connection. If there are no related people, omit this section.

## Constraints

- **Minimum body length:** 50 words per contact note. If the source provides less, include what is available — do not pad with fabricated details.
- **Maximum body length:** 400 words. Contact notes are reference cards, not essays.
- **Tags:** 2–5 per note. Always include `networking/contact`. Add domain-specific tags based on the person's field (e.g., `tech/ai`, `business/startup`).
- **Wikilinks in body:** Besides the Related People section, you may add inline `[[wikilinks]]` to relevant vault notes if the person's interests clearly connect to existing knowledge (e.g., `[[RAG-пайплайны]]` if such a note exists). Use 0–3 inline wikilinks; do not force them.
- **No fabrication:** If info is missing, omit the field/section. Never invent companies, roles, nicknames, or contact details.
- **Name normalization:** Use the name exactly as the user wrote it. Do not substitute Telegram handles, emails, or any other identifiers for the person's name. If the user wrote "Вася из Яндекса", the title is `# Вася` and the company goes into Competencies. If the user wrote "omo", the title is `# omo` — do not replace it with a Telegram handle.

## MOC Generation

When processing a batch of contacts, also generate one MOC note:

- **Title:** `Networking — MOC` (or update if it already exists in `vault_titles`)
- **note_type:** `moc`
- **Structure:** Group contacts by context (event, company, project, domain). Use `#####` for group names, bulleted `[[wikilinks]]` for people.

Example MOC structure:
```markdown
##### DevOps Conf 2025
- [[Иванов Василий]] — ML-инженер, Яндекс
- [[Смирнова Анна]] — продакт, Авито

##### Рабочие контакты
- [[Петров Алексей]] — тимлид, коллега по проекту
```

If a MOC already exists in vault, output the complete updated version with new contacts added to appropriate sections. Do not remove existing entries.

## Edge Cases

- **Single contact:** Process the same way — one contact note + MOC update.
- **Duplicate names:** If two people share a name, differentiate by adding a qualifier in parentheses to the title: `# Иванов Василий (Яндекс)`.
- **Already processed contacts:** If a contact with the same name exists in `vault_titles`, output it with `_update: true` flag. The writer will handle merging.
- **Mixed content:** If the source note contains both contact info and non-contact content (ideas, tasks), extract only the contact portions. Ignore the rest.

## JSON Output Schema

```json
{
  "contacts": [
    {
      "id": "contact-001",
      "title": "Фамилия Имя",
      "tags": ["networking/contact", "tech/ai"],
      "date": "2026-03-11",
      "source_doc": "Контакты",
      "note_type": "contact",
      "nickname": "Вася",
      "competencies": "Text...",
      "contact_info": ["Telegram: [@handle](https://t.me/handle)", "Email: x@y.com"],
      "story": "Text about how we met...",
      "related_people": [
        {"title": "Фамилия Имя", "relation": "краткое описание связи"}
      ],
      "inline_wikilinks": ["Existing Vault Note Title"],
      "body": "Full rendered markdown body (without frontmatter)"
    }
  ],
  "moc": {
    "title": "Networking — MOC",
    "tags": ["networking/contact", "productivity/moc"],
    "date": "2026-03-11",
    "source_doc": "Контакты",
    "note_type": "moc",
    "body": "Full rendered MOC body"
  }
}
```

The `body` field must contain the complete rendered markdown (sections 2–7) ready to be placed after the YAML frontmatter. The structured fields (`nickname`, `competencies`, etc.) are for validation; the `body` is what gets written.
