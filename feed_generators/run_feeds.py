import argparse
import logging
import sys
from typing import Callable, Dict, Iterable, List

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
        try:
            result = runner()
            if result is False:
                failures.append(feed)
                logger.error("Feed '%s' reported failure (returned False)", feed)
            else:
                successes.append(feed)
                logger.info("Feed '%s' completed", feed)
        except Exception as exc:  # noqa: BLE001
            failures.append(feed)
            logger.exception("Feed '%s' raised an error: %s", feed, exc)

    logger.info("=" * 60)
    logger.info("Feed generation summary")
    logger.info("  Successful: %d", len(successes))
    logger.info("  Failed: %d", len(failures))

    if successes:
        logger.info("  ✓ %s", ", ".join(successes))
    if failures:
        logger.error("  ✗ %s", ", ".join(failures))

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
