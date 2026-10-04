# Midnight Runner — Trade Business Lab

Phase 1 content generator for **Trade Business Lab**.

## What it does

- Reads the editorial queue from `topics.json`.
- Uses the OpenAI API to generate contractor-software article drafts.
- Generates one new article by default.
- Saves drafts as Markdown in `content/`.
- Skips drafts that already exist.
- Requires human review before publication.

## Phase 1 safety rules

The generator is intentionally conservative. It must not invent current pricing, product features, statistics, reviews, affiliate terms, or vendor claims. Claims needing current research are marked `[VERIFY]`.

Automatic WordPress publishing is **not enabled yet**. Scheduled generation is also disabled until the first draft passes review.

## GitHub secret required

Create a repository secret named:

`OPENAI_API_KEY`

The old `GEMINI_API_KEY` is no longer used.

## Testing

Run **Trade Business Lab Draft Generator** manually from GitHub Actions with `max_articles = 1`.

The first queued article is:

**Jobber vs Housecall Pro: Which Is Better for a Small Contractor?**

## Next phases

1. Review and improve the first generated draft.
2. Add verified vendor-source research to the generation pipeline.
3. Add affiliate-link configuration.
4. Connect WordPress and create drafts through the WordPress API.
5. Add scheduled generation only after quality controls are proven.
