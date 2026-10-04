import json
import os
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).parent
TOPICS_FILE = ROOT / "topics.json"
OUTPUT_DIR = ROOT / "content"

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "1"))

if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is missing.")

client = OpenAI(api_key=API_KEY)

SYSTEM_PROMPT = """You are the editorial engine for Trade Business Lab, an independent resource for home-service contractors and trade business owners.

Write practical commercial content for owners choosing business software. Be specific about who each option fits and why.

Accuracy rules:
- Never invent prices, discounts, commission rates, trial periods, customer counts, ratings, integrations, features, statistics, or quotes.
- The topic data names products to evaluate; it does NOT provide verified current product facts.
- If a factual claim would require current verification and no verified source material was supplied, do not state it as fact. Mark the point [VERIFY] for editorial research or phrase it as a question the editor should verify.
- Never claim firsthand testing, interviews, or personal use unless source material explicitly proves it.
- Do not manufacture citations, URLs, testimonials, or affiliate links.
- Clearly separate factual claims from editorial analysis.
- Avoid filler, hype, fake certainty, and generic SEO language.

Editorial requirements:
- Put an affiliate disclosure near the top.
- Give a concise recommendation early.
- Explain best fit by company size, trade, operational complexity, and buying priorities.
- Include a comparison table when appropriate.
- Include drawbacks and cases where each product is a poor fit.
- Include a section called "What to verify before you buy" for facts that can change.
- End with a useful decision framework, not a hard sell.
- Use Markdown.
"""

def load_topics():
    with TOPICS_FILE.open(encoding="utf-8") as handle:
        return sorted(json.load(handle), key=lambda item: item["priority"])

def prompt_for(topic):
    links = ", ".join(topic.get("internal_links", [])) or "none"
    products = ", ".join(topic["products"])
    return f"""Create a publication-quality draft using this editorial brief.

Title: {topic['title']}
Audience: {topic['audience']}
Search intent: {topic['intent']}
Products in scope: {products}
Planned internal-link slugs: {links}

This is a DRAFT for human review. Do not pretend you have live pricing or current vendor data. Use [VERIFY] wherever current factual verification is required.

At the end, add an "EDITOR NOTES" section containing:
- facts that need verification
- suggested primary-source pages to research (describe the page; do not invent URLs)
- affiliate links that still need insertion
- planned internal links
"""

def generate_article(topic):
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=prompt_for(topic),
    )
    return response.output_text.strip()

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    generated = 0

    for topic in load_topics():
        if generated >= MAX_ARTICLES:
            break

        path = OUTPUT_DIR / f"{topic['slug']}.md"
        if path.exists():
            print(f"Skipping existing draft: {path.name}")
            continue

        print(f"Generating: {topic['title']}")
        article = generate_article(topic)
        path.write_text(article + "\n", encoding="utf-8")
        print(f"Saved draft: {path}")
        generated += 1

    if generated == 0:
        print("No new drafts generated.")

if __name__ == "__main__":
    main()
