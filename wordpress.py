import os
import re
import sys
from pathlib import Path

import requests

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USERNAME = os.environ.get("WP_USERNAME", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")
PUBLISH_DIR = Path(__file__).parent / "publish"

if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
    raise ValueError("WP_URL, WP_USERNAME, and WP_APP_PASSWORD are required.")

def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value

def split_title(markdown, fallback):
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return line[2:].strip(), "\n".join(lines[:i] + lines[i + 1:]).strip()
    return fallback.replace("-", " ").title(), markdown.strip()

def inline_markdown(text):
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text

def markdown_to_html(markdown):
    lines = markdown.splitlines()
    out, paragraph, list_items = [], [], []

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + inline_markdown(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def flush_list():
        if list_items:
            out.append("<ul>" + "".join(f"<li>{inline_markdown(x)}</li>" for x in list_items) + "</ul>")
            list_items.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph(); flush_list(); continue
        if line.startswith("### "):
            flush_paragraph(); flush_list(); out.append(f"<h3>{inline_markdown(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_paragraph(); flush_list(); out.append(f"<h2>{inline_markdown(line[3:])}</h2>")
        elif line.startswith("- "):
            flush_paragraph(); list_items.append(line[2:])
        elif line.startswith("|"):
            # Preserve tables as preformatted text rather than risk corrupt HTML.
            flush_paragraph(); flush_list(); out.append(f"<pre>{line}</pre>")
        else:
            flush_list(); paragraph.append(line)
    flush_paragraph(); flush_list()
    return "\n".join(out)

def wp_request(method, endpoint, **kwargs):
    url = f"{WP_URL}/wp-json/wp/v2/{endpoint.lstrip('/')}"
    response = requests.request(
        method, url, auth=(WP_USERNAME, WP_APP_PASSWORD), timeout=30, **kwargs
    )
    if not response.ok:
        # Do not log request headers, credentials, response bodies, or full URLs.
        # WordPress REST errors normally provide a machine-readable code and message.
        code = "unknown"
        message = "No structured WordPress error message returned"
        try:
            detail = response.json()
            if isinstance(detail, dict):
                raw_code = detail.get("code")
                raw_message = detail.get("message")
                if isinstance(raw_code, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", raw_code):
                    code = raw_code
                if isinstance(raw_message, str):
                    # Avoid printing unexpected secrets or arbitrary server responses.
                    safe_messages = {
                        "rest_forbidden": "WordPress denied access",
                        "rest_cannot_view": "WordPress denied permission to view posts",
                        "rest_not_logged_in": "WordPress did not recognize an authenticated user",
                        "rest_invalid_param": "WordPress rejected a request parameter",
                        "rest_no_route": "WordPress could not find the requested API route",
                        "application_passwords_disabled": "WordPress Application Passwords are disabled",
                        "incorrect_password": "WordPress rejected the password",
                    }
                    message = safe_messages.get(code, "WordPress returned a structured error")
        except ValueError:
            message = "Non-JSON response (possibly hosting firewall or security plugin)"
        print(f"WordPress API diagnostic: HTTP {response.status_code}; code={code}; detail={message}; endpoint={endpoint.split('/')[0]}")
        raise RuntimeError("WordPress API request failed; see sanitized diagnostic above")
    return response.json()

def upsert_draft(path):
    markdown = path.read_text(encoding="utf-8")
    title, body = split_title(markdown, path.stem)
    slug = slugify(path.stem)
    html = markdown_to_html(body)

    existing = wp_request("GET", "posts", params={"slug": slug, "status": "draft,pending,future,publish,private", "context": "edit"})
    payload = {"title": title, "slug": slug, "content": html, "status": "draft"}

    if existing:
        post = existing[0]
        if post.get("status") == "publish":
            print(f"Refusing to overwrite published post: {slug}")
            return
        result = wp_request("POST", f"posts/{post['id']}", json=payload)
        print(f"Updated WordPress draft #{result['id']}: {title}")
    else:
        result = wp_request("POST", "posts", json=payload)
        print(f"Created WordPress draft #{result['id']}: {title}")

def main():
    requested = sys.argv[1:] or [str(p) for p in sorted(PUBLISH_DIR.glob("*.md"))]
    if not requested:
        print("No publish-ready Markdown files found.")
        return
    for item in requested:
        path = Path(item)
        if not path.exists() or path.parent.resolve() != PUBLISH_DIR.resolve():
            raise ValueError(f"Only files in publish/ may be uploaded: {item}")
        upsert_draft(path)

if __name__ == "__main__":
    main()
