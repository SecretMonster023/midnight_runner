"""Read-only WordPress REST API connectivity checks. Never prints secrets or response bodies."""
import os
import re
import requests
from requests.auth import HTTPBasicAuth

base = os.environ["WP_URL"].rstrip("/")
username = os.environ["WP_USERNAME"]
password = os.environ["WP_APP_PASSWORD"]
if not base.startswith("https://"):
    raise SystemExit("WP_URL must use HTTPS")

checks = [
    ("Public REST index", "/wp-json/", None, None),
    ("Authenticated identity", "/wp-json/wp/v2/users/me", HTTPBasicAuth(username, password), {"context": "edit"}),
    ("Authenticated posts (simple)", "/wp-json/wp/v2/posts", HTTPBasicAuth(username, password), {"per_page": 1}),
    ("Authenticated draft lookup", "/wp-json/wp/v2/posts", HTTPBasicAuth(username, password), {"context": "edit", "status": "draft", "per_page": 1}),
]
for label, path, auth, params in checks:
    try:
        response = requests.get(base + path, auth=auth, params=params, timeout=20, allow_redirects=False)
        code = "non-json"
        try:
            data = response.json()
            if isinstance(data, dict) and isinstance(data.get("code"), str):
                candidate = data["code"]
                if re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", candidate):
                    code = candidate
            elif response.ok:
                code = "ok"
        except ValueError:
            pass
        print(f"{label}: HTTP {response.status_code}; response={code}; redirected={'yes' if response.is_redirect else 'no'}", flush=True)
    except requests.RequestException as exc:
        print(f"{label}: connection error ({type(exc).__name__})", flush=True)
print("Read-only diagnostics finished; no WordPress content was changed.")
