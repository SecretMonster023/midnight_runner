from openai import OpenAI

QC_PROMPT = """You are the senior editor and publication quality-control gate for Trade Business Lab.

Edit the supplied evidence-grounded working draft into a clean, useful article for home-service contractors.

Rules:
- Do not add new factual information.
- Preserve source links that support factual claims.
- Do not invent prices, features, statistics, URLs, testimonials, affiliate links, or firsthand experience.
- Attribute vendor performance and marketing claims to the vendor.
- Remove EDITOR NOTES, internal workflow notes, planned-link placeholders, and assistant-style closings.
- Remove repetition, filler, hype, excessive caveats, and awkward AI phrasing.
- Recommendations must match the evidence: prefer "better for X" over unsupported claims that one product is objectively better.
- Preserve meaningful drawbacks and tradeoffs.
- Write like a careful trade-business editor: direct, specific, varied sentences; no keyword stuffing or robotic templates.
- Open with a 2-3 sentence verdict that explains which buyer should choose which option.
- Use actual Markdown ## headings and ### subheadings, not bare lines that look like headings.
- Keep paragraphs short (2-4 sentences), with simple language and few nested bullets.
- Make each section answer a practical buying question, not merely enumerate features.
- Include at most one concise comparison table with 3 columns and 5 short rows. Each table cell must be a short phrase (ideally under 35 characters); NO citations, prices plus footnotes, URLs, or long descriptions inside cells. Explain details and cite in normal paragraphs below.
- Explain the significance of the table rather than repeating every row.
- Use descriptive source links sparingly and close to supported claims; avoid repetitive citation chains.
- End with a practical buying checklist or decision, not a repetitive generic Summary.
- Never fabricate hands-on testing, customer experiences, testimonials, or statistics.
- Preserve accuracy and material qualifications even when simplifying prose.
- Keep exactly one affiliate disclosure near the top, before the main content; never repeat it as a heading, note, or paragraph elsewhere.
- Prefer short standalone bullet points rather than nested lists. Avoid an exhaustive sources dump at the bottom; use linked source names in context.
- Keep a concise "What to verify before you buy" section when appropriate.
- Output only the finished Markdown article, with no preface or afterword.
"""

BANNED_PUBLICATION_PHRASES = (
    "EDITOR NOTES",
    "If you want, I can",
    "planned internal links",
    "affiliate links still needing insertion",
)

def quality_control(client: OpenAI, model: str, topic: dict, working_draft: str) -> str:
    prompt = f"""Edit this working draft for publication.

Title: {topic['title']}
Audience: {topic['audience']}
Search intent: {topic['intent']}

WORKING DRAFT
==============
{working_draft}
==============
END WORKING DRAFT

Return only the final publish-ready Markdown.
"""
    import re
    for attempt in range(2):
        extra = (
            " Your previous response omitted Markdown headings. Rewrite with at least "
            "three literal lines beginning with ## followed by a space."
            if attempt else ""
        )
        response = client.responses.create(
            model=model, instructions=QC_PROMPT + extra, input=prompt
        )
        final = response.output_text.strip()
        if re.search(r"(?m)^## .+", final):
            break
    else:
        raise ValueError("Publication gate failed after retry: missing Markdown section headings.")

    failures = [phrase for phrase in BANNED_PUBLICATION_PHRASES if phrase.lower() in final.lower()]
    if failures:
        raise ValueError(f"Publication gate failed; QC output contains internal text: {failures}")

    if len(final) < 1000:
        raise ValueError("Publication gate failed; QC output is unexpectedly short.")

    # Deterministically remove duplicate affiliate-disclosure paragraphs/headings.
    # Preserve the first disclosure and keep it near the top.
    lines = final.splitlines()
    seen_disclosure = False
    cleaned = []
    for line in lines:
        if "affiliate disclosure" in line.lower() or line.lower().lstrip().startswith("disclosure:"):
            if seen_disclosure:
                continue
            seen_disclosure = True
        cleaned.append(line)
    final = "\n".join(cleaned).strip()

    # Git it Write reads YAML front matter to set the WordPress post status.
    # Enforce draft-only imports even when the model emits its own front matter.
    import re
    final = re.sub(r"^---\s*\n[\s\S]*?\n---\s*\n", "", final).lstrip()
    import json
    safe_title = json.dumps(topic["title"], ensure_ascii=False)
    return f"---\ntitle: {safe_title}\npost_status: draft\n---\n\n{final}"
