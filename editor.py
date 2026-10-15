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
    # Count Markdown table separator ROWS, not individual columns.
    # A single 3-column table contains multiple --- separators.
    separator_rows = [
        line for line in lines
        if "|" in line and re.fullmatch(r"[\\s|:-]+", line)
        and re.search(r"-{3,}", line)
    ]
    if len(separator_rows) > 1:
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

def seo_metadata(topic: dict) -> dict:
    """Stable SEO fields for Git it Write / Yoast; no additional API calls."""
    title = topic["title"]
    intent = topic["intent"]
    if intent == "commercial_best":
        keyword = re.sub(r"\\s*\\([^)]*\\)", "", title).strip().lower()
        seo_title = title.split(" (")[0] + " | Trade Business Lab"
        trade = ("HVAC" if "hvac" in title.lower() else
                 "plumbing" if "plumbing" in title.lower() else
                 "electrical" if "electrical" in title.lower() else "field service")
        description = (f"Compare Jobber, Housecall Pro, and ServiceTitan for small {trade} businesses. "
                       "Explore features, costs, and which software fits your crew.")
    elif intent == "commercial_comparison":
        keyword = title.split(":")[0].strip().lower()
        seo_title = title.split(":")[0] + ": Small Business Comparison"
        description = (f"Compare {title.split(':')[0]} for small contractors. "
                       "Explore features, costs, drawbacks, and which option fits your business.")
    else:
        keyword = title.split(":")[0].strip().lower()
        seo_title = title.split(":")[0] + ": Features, Costs & Fit"
        description = (f"Read our {title.split(':')[0]} for small contractors. "
                       "Explore features, costs, limitations, and who the software suits.")
    return {
        "keyword": keyword[:100],
        "title": seo_title[:65],
        "description": description[:155],
        "category": "software",
    }


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
            meta = seo_metadata(topic)
            return (
                f"---\ntitle: {safe_title}\npost_status: draft\n"
                f"taxonomy:\n    category:\n        - {meta['category']}\n"
                f"custom_fields:\n"
                f"    _yoast_wpseo_focuskw: {json.dumps(meta['keyword'])}\n"
                f"    _yoast_wpseo_title: {json.dumps(meta['title'])}\n"
                f"    _yoast_wpseo_metadesc: {json.dumps(meta['description'])}\n"
                f"---\n\n{final}"
            )
        prompt += ("\n\nPREVIOUS FAILED VERSION:\n" + final)
    raise ValueError("Publication gate failed after 3 attempts: " + "; ".join(errors))
