import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


MONTH_REGEX = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
)
GENERIC_TITLES = {
    "",
    "Featured",
    "The Latest",
    "About",
    "Meta AI",
    "AI Research",
    "Back",
    "Meta AI>",
    "AI Research>",
    "About>",
    "Learn More",
}


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def ensure_feeds_directory() -> Path:
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_blog_content(url: str = "https://ai.meta.com/blog/") -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_date_from_text(text: str) -> Optional[datetime]:
    match = MONTH_REGEX.search(text)
    if not match:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(match.group(), fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    return None


def normalize_title(title: str) -> str:
    cleaned = " ".join(title.split()).strip()
    if cleaned.lower() in {t.lower() for t in GENERIC_TITLES}:
        return ""
    return cleaned


def slugify_link(link: str) -> Optional[str]:
    if "/blog/" not in link:
        return None
    slug = link.split("/blog/", 1)[1].strip("/")
    if not slug:
        return None
    return slug.split("?")[0]


def extract_articles(html_content: str) -> Dict[str, dict]:
    soup = BeautifulSoup(html_content, "html.parser")
    articles: Dict[str, dict] = {}

    for anchor in soup.select('a[href*="ai.meta.com/blog/"], a[href^="/blog/"]'):
        href = anchor.get("href", "")
        if not href:
            continue
        if "page=" in href:
            continue

        if href.startswith("/"):
            link = f"https://ai.meta.com{href}"
        else:
            link = href

        slug = slugify_link(link)
        if not slug:
            continue

        raw_title = normalize_title(anchor.get_text(" ", strip=True))
        if not raw_title:
            # Try aria-label or title attributes
            raw_title = normalize_title(
                anchor.get("aria-label") or anchor.get("title") or ""
            )
        if not raw_title:
            # Fallback to slug prettified
            raw_title = slug.replace("-", " ").title()

        # Look for a nearby date string in parent / ancestors
        date = None
        parent = anchor
        for _ in range(4):
            if not parent:
                break
            text = " ".join(parent.get_text(" ", strip=True).split())
            date = parse_date_from_text(text)
            if date:
                break
            parent = parent.parent

        existing = articles.get(slug)
        if existing:
            # Keep the better title (prefer non-generic) and date if missing
            if existing["title"] in GENERIC_TITLES and raw_title not in GENERIC_TITLES:
                existing["title"] = raw_title
                existing["description"] = raw_title
            if not existing.get("date") and date:
                existing["date"] = date
            continue

        articles[slug] = {
            "title": raw_title or slug.replace("-", " ").title(),
            "link": link,
            "description": raw_title or slug.replace("-", " ").title(),
            "date": date,
            "category": "AI at Meta",
        }

    # Drop entries that don't have a reasonable title
    filtered = {
        slug: art for slug, art in articles.items() if len(art["title"]) >= 5
    }
    return filtered


def generate_rss_feed(articles: Dict[str, dict], feed_name: str = "meta_blog"):
    fg = FeedGenerator()
    fg.title("AI at Meta Blog")
    fg.description("Latest updates from the AI at Meta blog")
    fg.language("en")
    fg.link(
        href=f"https://raw.githubusercontent.com/gu-ni/rss-feeds/main/feeds/feed_{feed_name}.xml",
        rel="self",
    )
    fg.link(href="https://ai.meta.com/blog/", rel="alternate")
    fg.author({"name": "Meta"})

    def sort_key(item: dict):
        # Articles with dates first, then undated
        return (item["date"] is not None, item["date"] or datetime.min.replace(tzinfo=pytz.UTC))

    for article in sorted(articles.values(), key=sort_key, reverse=True):
        fe = fg.add_entry()
        fe.id(article["link"])
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["description"])
        if article["date"]:
            fe.published(article["date"])
        fe.category(term=article["category"])

    return fg


def save_rss_feed(feed_generator: FeedGenerator, feed_name: str = "meta_blog") -> Path:
    feeds_dir = ensure_feeds_directory()
    output_filename = feeds_dir / f"feed_{feed_name}.xml"
    feed_generator.rss_file(str(output_filename), pretty=True)
    logger.info("Saved feed to %s", output_filename)
    return output_filename


def main(feed_name: str = "meta_blog", html_file: str | None = None) -> bool:
    try:
        if html_file:
            logger.info("Reading AI at Meta blog HTML from %s", html_file)
            html_content = Path(html_file).read_text(encoding="utf-8", errors="ignore")
        else:
            default_snapshot = get_project_root() / "htmls" / "AI at Meta Blog.html"
            if default_snapshot.exists():
                logger.info("Using local snapshot: %s", default_snapshot)
                html_content = default_snapshot.read_text(encoding="utf-8", errors="ignore")
            else:
                logger.info("Fetching AI at Meta blog content from the web")
                html_content = fetch_blog_content()

        articles = extract_articles(html_content)
        if not articles:
            logger.warning("No articles found for AI at Meta blog")
            return False

        feed = generate_rss_feed(articles, feed_name)
        save_rss_feed(feed, feed_name)
        logger.info("Generated AI at Meta blog feed with %d articles", len(articles))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate AI at Meta blog feed: %s", exc)
        return False


if __name__ == "__main__":
    main()
