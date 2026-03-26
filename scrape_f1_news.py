import feedparser
import json
import re
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── F1 RSS feeds (no API key required) ────────────────────────────────────────
RSS_FEEDS = {
    "Autosport":        "https://www.autosport.com/rss/f1/news/",
    "Motorsport.com":   "https://www.motorsport.com/rss/f1/news/",
    "RaceFans":         "https://www.racefans.net/feed/",
    "The Race":         "https://the-race.com/feed/",
    "PlanetF1":         "https://www.planetf1.com/feed/",
    "GPFans":           "https://www.gpfans.com/en/rss/",
    "Crash.net F1":     "https://www.crash.net/rss/f1",
    "BBC Sport F1":     "https://feeds.bbci.co.uk/sport/formula1/rss.xml",
    "Sky Sports F1":    "https://www.skysports.com/rss/12040",
    "ESPN F1":          "https://www.espn.com/espn/rss/f1/news",
}

MAX_ARTICLES_PER_SOURCE = 25

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def fetch_feed_text(url: str, index: int = 0) -> str | None:
    """Fetch raw feed XML using requests with cache-busting headers."""
    headers = {
        "User-Agent": USER_AGENTS[index % len(USER_AGENTS)],
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    sep = "&" if "?" in url else "?"
    busted_url = f"{url}{sep}_={int(time.time())}"

    try:
        resp = requests.get(busted_url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"    [requests error] {exc}")
        return None


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return ""


def is_fresh(date_str: str, max_days: int = 7) -> bool:
    if not date_str:
        return True
    try:
        pub = datetime.fromisoformat(date_str)
        age = (datetime.now(timezone.utc) - pub).days
        return age <= max_days
    except Exception:
        return True


def scrape_feed(source_name: str, url: str, index: int = 0) -> list[dict]:
    articles = []

    raw = fetch_feed_text(url, index)
    if raw:
        feed = feedparser.parse(raw)
    else:
        print(f"    [fallback] trying feedparser directly for {source_name}")
        feed = feedparser.parse(url)

    for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
        summary = strip_html(getattr(entry, "summary", ""))[:600]
        pub = parse_date(entry)

        articles.append({
            "source":       source_name,
            "title":        getattr(entry, "title", "").strip(),
            "url":          getattr(entry, "link",  "").strip(),
            "published_at": pub,
            "summary":      summary,
            "author":       getattr(entry, "author", "").strip(),
            "tags":         [t.get("term", "") for t in getattr(entry, "tags", [])],
        })

    return articles


def main():
    print(f"Scraping {len(RSS_FEEDS)} F1 RSS feeds… (cache-busted)")
    all_articles: list[dict] = []
    failed_sources: list[str] = []

    for i, (name, url) in enumerate(RSS_FEEDS.items()):
        print(f"  → {name}")
        items = scrape_feed(name, url, index=i)
        if items:
            all_articles.extend(items)
            print(f"     ✓ {len(items)} articles")
        else:
            failed_sources.append(name)
            print(f"     ✗ no articles returned")

    all_articles.sort(key=lambda a: a["published_at"] or "0", reverse=True)

    fresh = [a for a in all_articles if is_fresh(a["published_at"], max_days=7)]
    print(f"\n{len(fresh)} fresh articles (last 7 days) out of {len(all_articles)} total")

    output = {
        "last_updated":   datetime.now(timezone.utc).isoformat(),
        "total_articles": len(fresh),
        "sources_ok":     [s for s in RSS_FEEDS if s not in failed_sources],
        "sources_failed": failed_sources,
        "articles":       fresh,
    }

    out_path = Path("docs") / "f1_news.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ Saved → {out_path}")
