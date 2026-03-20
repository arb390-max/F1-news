"""
f1_scraper.py
Scrapes F1 news from multiple RSS feeds and saves results to docs/ for GitHub Pages.
No API keys required — pure RSS/HTML parsing.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

# ---------------------------------------------------------------------------
# RSS Feed Sources
# ---------------------------------------------------------------------------
RSS_FEEDS = {
    "Autosport":        "https://www.autosport.com/rss/f1/news/",
    "Motorsport.com":   "https://www.motorsport.com/rss/f1/news/",
    "F1.com":           "https://www.formula1.com/content/fom-website/en/latest/all.xml",
    "RaceFans":         "https://www.racefans.net/feed/",
    "GPFans":           "https://www.gpfans.com/en/rss/",
    "PlanetF1":         "https://planetf1.com/feed/",
    "The Race":         "https://the-race.com/feed/",
}

# Output goes to docs/ so GitHub Pages can serve it directly
OUTPUT_DIR = Path("docs")
JSON_FILE  = OUTPUT_DIR / "latest_news.json"
MD_FILE    = OUTPUT_DIR / "index.md"        # index.md becomes the Pages homepage

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; F1NewsScraper/1.0; +https://github.com)"
    )
}

MAX_ITEMS_PER_FEED = 10  # cap per source to keep output manageable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_html(raw: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def parse_date(entry) -> str:
    """Return an ISO-8601 UTC string from a feedparser entry, or empty string."""
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = dateparser.parse(raw)
                if dt:
                    dt = dt.astimezone(timezone.utc)
                    return dt.isoformat()
            except Exception:
                pass
    return ""


def fetch_feed(name: str, url: str) -> list[dict]:
    """Fetch and parse a single RSS feed, returning a list of article dicts."""
    articles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
            title   = clean_html(getattr(entry, "title", ""))
            link    = getattr(entry, "link", "")
            summary = clean_html(
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
            )
            pub_date = parse_date(entry)

            if not title or not link:
                continue

            articles.append(
                {
                    "source":    name,
                    "title":     title,
                    "url":       link,
                    "summary":   summary[:500] + ("…" if len(summary) > 500 else ""),
                    "published": pub_date,
                }
            )

        print(f"  ✓  {name}: {len(articles)} articles")

    except requests.RequestException as exc:
        print(f"  ✗  {name}: HTTP error — {exc}")
    except Exception as exc:
        print(f"  ✗  {name}: Unexpected error — {exc}")

    return articles


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicates by URL, keeping first occurrence."""
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def sort_articles(articles: list[dict]) -> list[dict]:
    """Sort newest-first; articles without a date go to the bottom."""
    def key(a):
        d = a.get("published", "")
        return d if d else "0000"

    return sorted(articles, key=key, reverse=True)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_json(articles: list[dict], path: Path) -> None:
    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "count":      len(articles),
        "articles":   articles,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n📄  JSON  → {path}  ({len(articles)} articles)")


def write_markdown(articles: list[dict], path: Path) -> None:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "---",
        "title: F1 News",
        "---",
        "",
        "# 🏎️  F1 News — Latest Headlines",
        "",
        f"_Last updated: {now_str}_  ",
        f"_Total articles: {len(articles)}_",
        "",
        "---",
        "",
    ]

    for i, a in enumerate(articles, 1):
        pub = f"  _{a['published'][:10]}_" if a.get("published") else ""
        lines.append(f"### {i}. [{a['title']}]({a['url']})")
        lines.append(f"**Source:** {a['source']}{pub}  ")
        if a.get("summary"):
            lines.append(f"{a['summary']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"📝  Markdown → {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("🏁  F1 RSS Scraper starting…\n")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_articles: list[dict] = []
    for name, url in RSS_FEEDS.items():
        all_articles.extend(fetch_feed(name, url))

    all_articles = deduplicate(all_articles)
    all_articles = sort_articles(all_articles)

    write_json(all_articles, JSON_FILE)
    write_markdown(all_articles, MD_FILE)

    print(f"\n✅  Done — {len(all_articles)} unique articles scraped.")


if __name__ == "__main__":
    main()
