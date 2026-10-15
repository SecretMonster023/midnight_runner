import json
import re
from urllib.parse import urlparse

from openai import OpenAI

QC_PROMPT = """You are the senior publication editor for Trade Business Lab.
Rewrite the supplied draft as a useful, concise buying guide for home-service contractors.
Do not add facts, URLs, prices, tests, experiences, or features. Preserve material caveats.
Attribute vendor marketing claims. Use only source URLs present in the working draft or its
research packet. Turn relevant verified URLs into descriptive inline Markdown links:
[Jobber pricing](https://www.getjobber.com/pricing/). Link claims where discussed, not in a
'Vendor pages cited' dump. Never write unlinked 'See Jobber pricing' references.
Use real ## section headings and ### subsections, never bare section labels.
Start with exactly one affiliate disclosure followed by ## Verdict.
Use one compact comparison table (3 columns, 3-5 product rows; no mixed 'Trial' rows).
Keep meaningful product drawbacks, but consolidate repeated checklists into one
## What to verify before you buy section near the end.
No editor notes, instructions, filler, redundant conclusions, or raw URL lists.
End with a useful buying action, not a generic summary.
Return ONLY finished Markdown, no YAML front matter.
"""

BANNED = (
    "editor notes", "if you want, i can", "planned internal links",
    "affiliate links still needing insertion", "vendor pages cited",
    "significant vendor-sourced details and where to check them",
    "what to verify right away with vendors", "practical decision checklist",
    "final, practical recommendations", "what the table shows",
)

def validate(article: str, allowed_urls: set[str]) -> list[str]:
    errors = []
    lines = article.splitlines()
    headings = re.findall(r"(?m)^## (.+)$", article)
    if not headings or headings[0].strip().lower() != "verdict":
        errors.append("first section must be ## Verdict")
    if len(headings) < 3:
        errors.append("at least three ## sections required")
    if sum("affiliate disclosure" in line.lower() for line in lines) != 1:
        errors.append("exactly one affiliate disclosure required")
    if not any("affiliate disclosure" in line.lower() for line in lines[:5]):
        errors.append("affiliate disclosure must be near top")
    if len(article) < 1200:
        errors.append("article too short")
    for phrase in BANNED:
        if phrase in article.lower():
            errors.append("banned editorial phrase: " + phrase)
    if re.search(r"(?im)^\s*(?:#{1,4}\s*)?verdict\s*\([^)]*sentences[^)]*\)", article):
        errors.append("leaked verdict instructions")
    if re.search(r"(?m)^(?!.*\]\(https?://).*https?://\S+", article):
        errors.append("bare URLs instead of Markdown links")
    links = re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", article)
    if len(links) < 3:
        errors.append("fewer than three clickable source links")
    if any(url not in allowed_urls for url in links):
        errors.append("unapproved or invented source URL")
    if article.count("|---") + article.count("| ---") > 1:
        errors.append("more than one comparison table")
    if not re.search(r"(?im)^## What to verify before you buy\s*$", article):
        errors.append("missing consolidated buying checklist")
    # Detect common unformatted standalone section labels.
    for label in ("Meaningful drawbacks", "Comparison table (quick view)",
                  "Who each product fits", "What the table shows",
                  "Final, practical recommendations"):
        if re.search(r"(?im)^" + re.escape(label) + r"[^\n]*$", article):
            errors.append("unformatted or redundant section: " + label)
    return errors

def quality_control(client: OpenAI, model: str, topic: dict, working_draft: str,
                    allowed_urls=None) -> str:
    allowed_urls = set(allowed_urls or [])
    # Also allow original draft links if this function is used without a research packet.
    if not allowed_urls:
        allowed_urls = set(re.findall(r"https?://[^\s)<>]+", working_draft))
    prompt = (f"Title: {topic['title']}\nAudience: {topic['audience']}\n"
              f"Allowed source URLs (do not invent others):\n" +
              "\n".join(sorted(allowed_urls)) +
              "\n\nWORKING DRAFT:\n" + working_draft)
    errors = []
    for attempt in range(3):
        instructions = QC_PROMPT
        if errors:
            instructions += ("\nYour previous version failed checks. Fix ALL these issues "
                             "without adding new facts:\n- " + "\n- ".join(errors))
        response = client.responses.create(model=model, instructions=instructions, input=prompt)
        final = response.output_text.strip()
        final = re.sub(r"^---\s*\n[\s\S]*?\n---\s*\n", "", final).strip()
        errors = validate(final, allowed_urls)
        if not errors:
            safe_title = json.dumps(topic["title"], ensure_ascii=False)
            return f"---\ntitle: {safe_title}\npost_status: draft\n---\n\n{final}"
        prompt += ("\n\nPREVIOUS FAILED VERSION:\n" + final)
    raise ValueError("Publication gate failed after 3 attempts: " + "; ".join(errors))
