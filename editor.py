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
- Improve headings, scanability, paragraph flow, and comparison tables.
- Keep the affiliate disclosure near the top.
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
    response = client.responses.create(model=model, instructions=QC_PROMPT, input=prompt)
    final = response.output_text.strip()

    failures = [phrase for phrase in BANNED_PUBLICATION_PHRASES if phrase.lower() in final.lower()]
    if failures:
        raise ValueError(f"Publication gate failed; QC output contains internal text: {failures}")

    if len(final) < 1000:
        raise ValueError("Publication gate failed; QC output is unexpectedly short.")

    # Git it Write reads YAML front matter to set the WordPress post status.
    # Enforce draft-only imports even when the model emits its own front matter.
    import re
    final = re.sub(r"^---\s*\n[\s\S]*?\n---\s*\n", "", final).lstrip()
    return f"---\ntitle: {topic['title']}\npost_status: draft\n---\n\n{final}"
