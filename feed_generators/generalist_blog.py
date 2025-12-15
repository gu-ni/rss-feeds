import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def ensure_feeds_directory() -> Path:
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def parse_date(text: str) -> Optional[datetime]:
    """Parse dates like 'Nov 04, 2025' or 'September 24, 2025'."""
    text = text.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    logger.warning("Could not parse date: %s", text)
    return None


def extract_articles(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: List[dict] = []

    for link in soup.select("a.blog-menu-article-link"):
        href = link.get("href")
        if not href:
            continue

        # Titles / description / date
        title_elem = link.select_one("h1")
        desc_elem = link.select_one("h2")
        date_elem = link.select_one("p")

        title = title_elem.get_text(strip=True) if title_elem else None
        description = desc_elem.get_text(strip=True) if desc_elem else (title or "")
        date = parse_date(date_elem.get_text(strip=True)) if date_elem else None

        if not title:
            continue

        articles.append(
            {
                "title": title,
                "link": href if href.startswith("http") else f"https://generalistai.com{href}",
                "description": description,
                "date": date or datetime.now(pytz.UTC),
                "category": "Generalist AI",
            }
        )

    return articles


def generate_rss_feed(articles: List[dict], feed_name: str = "generalist_blog"):
    fg = FeedGenerator()
    fg.title("Generalist AI Blog")
    fg.description("Research updates and news from Generalist AI")
    fg.language("en")
    fg.link(href="https://generalistai.com/blog", rel="alternate")
    fg.link(
        href=f"https://raw.githubusercontent.com/gu-ni/rss-feeds/main/feeds/feed_{feed_name}.xml",
        rel="self",
    )

    for article in sorted(articles, key=lambda a: a["date"], reverse=True):
        fe = fg.add_entry()
        fe.id(article["link"])
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["description"])
        fe.published(article["date"])
        fe.category(term=article["category"])

    return fg


def save_rss_feed(feed_generator: FeedGenerator, feed_name: str = "generalist_blog") -> Path:
    feeds_dir = ensure_feeds_directory()
    output_filename = feeds_dir / f"feed_{feed_name}.xml"
    feed_generator.rss_file(str(output_filename), pretty=True)
    logger.info("Saved feed to %s", output_filename)
    return output_filename


def main(feed_name: str = "generalist_blog", html_file: str | None = None) -> bool:
    try:
        if html_file:
            html_content = Path(html_file).read_text(encoding="utf-8", errors="ignore")
            logger.info("Using HTML from %s", html_file)
        else:
            default_snapshot = get_project_root() / "htmls" / "Generalist - Blog.html"
            if not default_snapshot.exists():
                logger.error("Local snapshot not found: %s", default_snapshot)
                return False
            html_content = default_snapshot.read_text(encoding="utf-8", errors="ignore")
            logger.info("Using local snapshot: %s", default_snapshot)

        articles = extract_articles(html_content)
        if not articles:
            logger.warning("No articles found for Generalist AI blog")
            return False

        feed = generate_rss_feed(articles, feed_name)
        save_rss_feed(feed, feed_name)
        logger.info("Generated Generalist AI blog feed with %d articles", len(articles))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate Generalist AI blog feed: %s", exc)
        return False


if __name__ == "__main__":
    main()
