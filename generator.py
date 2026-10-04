import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

ROOT = Path(__file__).parent
TOPICS_FILE = ROOT / "topics.json"
SOURCES_FILE = ROOT / "sources.json"
OUTPUT_DIR = ROOT / "content"
RESEARCH_DIR = ROOT / "research"

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
MAX_ARTICLES = int(os.environ.get("MAX_ARTICLES", "1"))
TOPIC_ID = os.environ.get("TOPIC_ID", "").strip()
REGENERATE = os.environ.get("REGENERATE", "false").lower() == "true"

if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is missing.")

client = OpenAI(api_key=API_KEY)

SYSTEM_PROMPT = """You are the editorial engine for Trade Business Lab, an independent resource for home-service contractors and trade business owners.

Write practical commercial content for owners choosing business software. The supplied RESEARCH PACKET is evidence collected from official vendor-controlled sources immediately before generation.

Evidence rules:
- Treat the research packet as the only source of current product facts.
- Never invent or infer prices, discounts, plan inclusions, trial periods, customer counts, ratings, integrations, features, statistics, contract terms, or quotes.
- A factual claim may appear only when the research packet directly supports it.
- Cite factual claims inline with Markdown links to the exact official source supplied in the packet.
- Vendor marketing claims must be attributed to the vendor, not presented as independently proven results.
- If evidence conflicts or is ambiguous, say so rather than resolving it yourself.
- Never claim firsthand testing, interviews, or personal use.
- Never manufacture URLs, testimonials, reviews, or affiliate links.
- Editorial recommendations may be reasoned from verified facts, but clearly present them as analysis.
- Do not litter the reader-facing article with labels such as "(Editorial)" or "[VERIFY]". Put unresolved research needs only in EDITOR NOTES.
- Avoid filler, hype, fake certainty, and generic SEO language.

Editorial requirements:
- Start with a short affiliate disclosure.
- Give a concise bottom-line recommendation early.
- Explain fit by company size, trade, operational complexity, and buying priorities.
- Include a useful comparison table when appropriate.
- Include current pricing only when supported by the packet and state the retrieval date.
- Include meaningful drawbacks and cases where each product is a poor fit.
- Include a short "What to verify before you buy" section for especially changeable facts.
- End with a practical decision framework, not a hard sell.
- Use natural, publication-ready Markdown.
"""

def load_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)

def clean_page(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:30000]

def fetch_source(source):
    url = source["url"]
    host = urlparse(url).hostname or ""
    if not (host.endswith("getjobber.com") or host.endswith("housecallpro.com") or host.endswith("servicetitan.com")):
        raise ValueError(f"Unapproved source domain: {host}")
    response = requests.get(
        url,
        timeout=25,
        headers={"User-Agent": "TradeBusinessLabResearchBot/1.0 (+https://tradebusinesslab.com)"}
    )
    response.raise_for_status()
    return {
        "label": source["label"],
        "url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "text": clean_page(response.text)
    }

def build_research_packet(topic, source_map):
    packet = {"topic_id": topic["id"], "products": {}, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    for product in topic["products"]:
        configured = source_map.get(product, [])
        if not configured:
            packet["products"][product] = {"error": "No official sources configured.", "sources": []}
            continue
        gathered = []
        for source in configured:
            try:
                gathered.append(fetch_source(source))
            except Exception as exc:
                gathered.append({"label": source["label"], "url": source["url"], "error": str(exc)})
        packet["products"][product] = {"sources": gathered}
    return packet

def research_text(packet):
    chunks = [f"Research retrieved: {packet['retrieved_at']}"]
    for product, data in packet["products"].items():
        chunks.append(f"\n## {product}")
        for source in data.get("sources", []):
            chunks.append(f"\nSOURCE: {source.get('label')}\nURL: {source.get('url')}")
            if source.get("error"):
                chunks.append(f"FETCH ERROR: {source['error']}")
            else:
                chunks.append(source["text"])
    return "\n".join(chunks)

def prompt_for(topic, packet):
    links = ", ".join(topic.get("internal_links", [])) or "none"
    products = ", ".join(topic["products"])
    return f"""Create a publication-quality draft using this editorial brief and research packet.

Title: {topic['title']}
Audience: {topic['audience']}
Search intent: {topic['intent']}
Products in scope: {products}
Planned internal-link slugs: {links}

RESEARCH PACKET
================
{research_text(packet)}
================
END RESEARCH PACKET

At the end add an EDITOR NOTES section with:
- any important facts still unsupported or ambiguous
- failed source fetches
- affiliate links still needing insertion
- planned internal links
- the research retrieval timestamp

Do not include a claim just because it sounds likely. If the packet does not support it, omit it from the reader-facing article.
"""

def generate_article(topic, packet):
    response = client.responses.create(model=MODEL, instructions=SYSTEM_PROMPT, input=prompt_for(topic, packet))
    return response.output_text.strip()

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    RESEARCH_DIR.mkdir(exist_ok=True)
    topics = sorted(load_json(TOPICS_FILE), key=lambda item: item["priority"])
    source_map = load_json(SOURCES_FILE)

    if TOPIC_ID:
        topics = [t for t in topics if t["id"] == TOPIC_ID]
        if not topics:
            raise ValueError(f"Unknown TOPIC_ID: {TOPIC_ID}")

    generated = 0
    for topic in topics:
        if generated >= MAX_ARTICLES:
            break
        path = OUTPUT_DIR / f"{topic['slug']}.md"
        if path.exists() and not REGENERATE:
            print(f"Skipping existing draft: {path.name}")
            continue

        print(f"Researching official sources for: {topic['title']}")
        packet = build_research_packet(topic, source_map)
        research_path = RESEARCH_DIR / f"{topic['slug']}.json"
        research_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

        print(f"Generating evidence-grounded draft: {topic['title']}")
        article = generate_article(topic, packet)
        path.write_text(article + "\n", encoding="utf-8")
        print(f"Saved draft: {path}")
        generated += 1

    if generated == 0:
        print("No new drafts generated.")

if __name__ == "__main__":
    main()
