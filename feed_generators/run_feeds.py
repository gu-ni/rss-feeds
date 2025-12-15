import argparse
import logging
import sys
import hashlib
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple
import xml.etree.ElementTree as ET

from feed_generators import (
    anthropic_changelog_claude_code,
    anthropic_eng_blog,
    anthropic_news_blog,
    anthropic_research_blog,
    anthropic_red_blog,
    blogsurgeai_feed_generator,
    chanderramesh_blog,
    hamel_blog,
    generalist_blog,
    ollama_blog,
    openai_research_blog,
    paulgraham_blog,
    thinkingmachines_blog,
    meta_blog,
    windsurf_blog,
    windsurf_changelog,
    windsurf_next_changelog,
    xainews_blog,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


FEED_RUNNERS: Dict[str, Callable[[], object]] = {
    "anthropic_news_blog": anthropic_news_blog.main,
    "anthropic_eng_blog": anthropic_eng_blog.main,
    "anthropic_research_blog": anthropic_research_blog.main,
    "anthropic_changelog_claude_code": anthropic_changelog_claude_code.main,
    "anthropic_red_blog": anthropic_red_blog.main,
    "openai_research_blog": openai_research_blog.main,
    "ollama_blog": ollama_blog.main,
    "paulgraham_blog": paulgraham_blog.main,
    "blogsurgeai_feed_generator": blogsurgeai_feed_generator.generate_blogsurgeai_feed,
    "xainews_blog": xainews_blog.main,
    "meta_blog": meta_blog.main,
    "generalist_blog": generalist_blog.main,
    "chanderramesh_blog": chanderramesh_blog.main,
    "thinkingmachines_blog": thinkingmachines_blog.main,
    "hamel_blog": hamel_blog.main,
    "windsurf_blog": windsurf_blog.main,
    "windsurf_changelog": windsurf_changelog.main,
    "windsurf_next_changelog": windsurf_next_changelog.main,
}

# Map feed runner keys to their expected output filenames to detect updates
FEED_OUTPUT_FILES: Dict[str, str] = {
    "anthropic_news_blog": "feed_anthropic_news.xml",
    "anthropic_eng_blog": "feed_anthropic_engineering.xml",
    "anthropic_research_blog": "feed_anthropic_research.xml",
    "anthropic_changelog_claude_code": "feed_anthropic_changelog_claude_code.xml",
    "anthropic_red_blog": "feed_anthropic_red.xml",
    "openai_research_blog": "feed_openai_research.xml",
    "ollama_blog": "feed_ollama.xml",
    "paulgraham_blog": "feed_paulgraham.xml",
    "blogsurgeai_feed_generator": "feed_blogsurgeai.xml",
    "xainews_blog": "feed_xainews.xml",
    "meta_blog": "feed_meta_blog.xml",
    "generalist_blog": "feed_generalist_blog.xml",
    "chanderramesh_blog": "feed_chanderramesh.xml",
    "thinkingmachines_blog": "feed_thinkingmachines.xml",
    "hamel_blog": "feed_hamel.xml",
    "windsurf_blog": "feed_windsurf_blog.xml",
    "windsurf_changelog": "feed_windsurf_changelog.xml",
    "windsurf_next_changelog": "feed_windsurf_next_changelog.xml",
}

def file_checksum(path: Path) -> str:
    """Return md5 checksum for a file (or empty string if not found)."""
    if not path.exists():
        return ""
    md5 = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def read_feed_entries(path: Path) -> List[Tuple[str, str, str]]:
    """Read titles/links/ids from an existing feed file."""
    if not path.exists():
        return []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        items = []
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            # Prefer guid, then link, then title as identifier
            identifier = guid or link or title
            if identifier:
                items.append((identifier, title, link))
        return items
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not parse feed file %s: %s", path, exc)
        return []


def parse_feed_names(raw_names: Iterable[str]) -> List[str]:
    """Parse comma/space separated feed names."""
    parsed: List[str] = []
    for name in raw_names:
        if not name:
            continue
        for part in name.split(","):
            stripped = part.strip()
            if stripped:
                parsed.append(stripped)
    return parsed


def run_selected_feeds(feeds: List[str]) -> int:
    """Run the selected feed generator callables sequentially."""
    successes: List[str] = []
    failures: List[str] = []
    updated: List[str] = []
    new_entries: Dict[str, List[Tuple[str, str, str]]] = {}
    created_feeds: List[str] = []

    for feed in feeds:
        runner = FEED_RUNNERS.get(feed)
        if not runner:
            logger.error(
                "Unknown feed '%s'. Valid options: %s",
                feed,
                ", ".join(sorted(FEED_RUNNERS)),
            )
            failures.append(feed)
            continue

        logger.info("Running feed: %s", feed)

        # Capture pre-run checksum for the expected output file (if known)
        output_file = FEED_OUTPUT_FILES.get(feed)
        output_path = Path("feeds") / output_file if output_file else None
        before_checksum = file_checksum(output_path) if output_path else ""
        before_exists = output_path.exists() if output_path else False
        before_entries = read_feed_entries(output_path) if output_path else []
        before_ids = {entry[0] for entry in before_entries}

        try:
            result = runner()
            if result is False:
                failures.append(feed)
                logger.error("Feed '%s' reported failure (returned False)", feed)
            else:
                successes.append(feed)
                logger.info("Feed '%s' completed", feed)

                # Detect file changes (new or modified) if we know the output path
                if output_path:
                    after_checksum = file_checksum(output_path)
                    after_entries = read_feed_entries(output_path)
                    after_ids = {entry[0] for entry in after_entries}
                    new_items = [entry for entry in after_entries if entry[0] not in before_ids]

                    if not before_exists and after_entries:
                        created_feeds.append(feed)
                        logger.info(
                            "🔔🔔🔔 Feed '%s' created %d entries (new file): %s",
                            feed,
                            len(after_entries),
                            output_path,
                        )
                    elif after_checksum and after_checksum != before_checksum:
                        updated.append(feed)
                        if new_items:
                            new_entries[feed] = new_items
                            logger.info(
                                "🔔🔔🔔 Feed '%s' updated: %d new entries written to %s",
                                feed,
                                len(new_items),
                                output_path,
                            )
                        else:
                            logger.info("💤💤💤 Feed '%s' updated file but no new entries detected", feed)
                    else:
                        logger.info("Feed '%s' had no changes", feed)
        except Exception as exc:  # noqa: BLE001
            failures.append(feed)
            logger.exception("Feed '%s' raised an error: %s", feed, exc)

    logger.info("=" * 60)
    logger.info("Feed generation summary")
    logger.info("  Successful: %d", len(successes))
    logger.info("  Failed: %d", len(failures))
    logger.info("  Updated files: %d", len(updated))

    if successes:
        logger.info("  ✓ %s", ", ".join(successes))
    if failures:
        logger.error("  ✗ %s", ", ".join(failures))
    if created_feeds:
        logger.info("  📄 Created feeds: %s", ", ".join(created_feeds))
    if updated:
        logger.info("  🔄 Updated outputs: %s", ", ".join(updated))
    if new_entries:
        for feed, entries in new_entries.items():
            sample_titles = [title or link for _, title, link in entries][:5]
            logger.info("    • %s: %d new items. Latest: %s", feed, len(entries), "; ".join(sample_titles))
    if not updated and not created_feeds:
        logger.info("  No feed files changed")

    return 0 if not failures else 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run selected feed generator scripts and write their XML outputs to feeds/"
        )
    )
    parser.add_argument(
        "--feeds",
        "-f",
        nargs="*",
        default=None,
        help=(
            "Space or comma separated list of feed generator names to run. "
            "Defaults to all known feeds."
        ),
    )
    args = parser.parse_args(argv)

    selected = (
        parse_feed_names(args.feeds) if args.feeds is not None else list(FEED_RUNNERS)
    )

    if not selected:
        parser.error("No feeds specified.")

    return run_selected_feeds(selected)


if __name__ == "__main__":
    sys.exit(main())
