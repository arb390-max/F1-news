import feedparser
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── F1 RSS feeds (no API key required) ────────────────────────────────────────
RSS_FEEDS = {
    "Formula1.com": "https://www.formula1.com/content/fom-website/en/latest/all.xml",
    "Autosport": "https://www.autosport.com/rss/f1/news/",
    "Motorsport.com": "https://www.motorsport.com/rss/f1/news/",
    "RaceFans": "https://www.racefans.net/feed/",
    "The Race": "https://the-race.com/feed/",
    "PlanetF1": "https://www.planetf1.com/feed/",
    "GPFans": "https://www.gpfans.com/en/rss/",
    "Crash.net F1": "https://www.crash.net/rss/f1",
}

MAX_ARTICLES_PER_SOURCE = 20


def parse_date(entry) -> str:
    """Return an ISO-8601 UTC date string from a feed entry, or empty string."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return ""


def scrape_feed(source_name: str, url: str) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns a list of article dicts."""
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            # Summary: strip HTML tags roughly via feedparser's sanitised value
            summary = ""
            if hasattr(entry, "summary"):
                import re
                summary = re.sub(r"<[^>]+>", "", entry.summary).strip()

            articles.append(
                {
                    "source": source_name,
                    "title": getattr(entry, "title", "").strip(),
                    "url": getattr(entry, "link", "").strip(),
                    "published_at": parse_date(entry),
                    "summary": summary[:500],  # cap length
                    "author": getattr(entry, "author", "").strip(),
                    "tags": [
                        t.get("term", "") for t in getattr(entry, "tags", [])
                    ],
                }
            )
    except Exception as exc:
        print(f"  [WARN] Failed to fetch '{source_name}': {exc}")

    return articles


def main():
    print(f"Scraping {len(RSS_FEEDS)} F1 RSS feeds…")
    all_articles: list[dict] = []

    for name, url in RSS_FEEDS.items():
        print(f"  → {name}")
        items = scrape_feed(name, url)
        all_articles.extend(items)
        print(f"     {len(items)} articles fetched")

    # Sort newest first (empty dates go to the end)
    all_articles.sort(key=lambda a: a["published_at"] or "0", reverse=True)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(all_articles),
        "sources": list(RSS_FEEDS.keys()),
        "articles": all_articles,
    }

    # ── Write to docs/f1_news.json ─────────────────────────────────────────────
    out_path = Path("docs") / "f1_news.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Saved {len(all_articles)} articles → {out_path}")


if __name__ == "__main__":
    main()
