
"""Verified published articles for Trade Business Lab."""

PUBLISHED = {
    "jobber-vs-housecall-pro": {
        "url": "https://tradebusinesslab.com/jobber-vs-housecall-pro/",
        "label": "Jobber vs Housecall Pro comparison",
    },
    "best-hvac-software": {
        "url": "https://tradebusinesslab.com/best-hvac-software-small-business/",
        "label": "best HVAC software guide",
    },
    "best-plumbing-software": {
        "url": "https://tradebusinesslab.com/best-plumbing-software-small-business/",
        "label": "best plumbing software guide",
    },
}


def add_internal_links(article, topic):
    """Add links only to published articles."""
    candidates = [
        PUBLISHED[key]
        for key in topic.get("internal_links", [])
        if key in PUBLISHED and key != topic["id"]
    ]

    if not candidates and topic["id"] != "jobber-vs-housecall-pro":
        candidates = [PUBLISHED["jobber-vs-housecall-pro"]]

    links = []
    for item in candidates[:2]:
        if item["url"] not in article:
            links.append(
                f'[{item["label"]}]({item["url"]})'
            )

    if not links:
        return article

    return (
        article.rstrip()
        + "\n\n## Related reading\n\n"
        + " | ".join(links)
        + "\n"
    )
