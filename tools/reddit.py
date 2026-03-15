"""PRAW-based Reddit search tool for the WinLossAgent."""

import logging
import os

import praw

logger = logging.getLogger(__name__)


def search_reddit(query: str, subreddit: str = "all", limit: int = 10) -> str:
    """Search Reddit posts and return titles, scores, URLs, and top comments.

    Searches the given subreddit (default: all) for posts matching the query.
    Returns structured text with up to `limit` results. Never raises — errors
    are returned as a plain-text message so the agent can continue gracefully.

    Args:
        query: Search terms to look for.
        subreddit: Subreddit name to search within (default "all").
        limit: Maximum number of posts to return (default 10).

    Returns:
        Newline-separated structured text with post details.
    """
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID", ""),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
            username=os.getenv("REDDIT_USERNAME", ""),
            password=os.getenv("REDDIT_PASSWORD", ""),
            user_agent="CheeseCake/1.0 growth-intelligence",
        )
        results = []
        sub = reddit.subreddit(subreddit)
        for post in sub.search(query, limit=limit):
            top_comment = ""
            try:
                post.comments.replace_more(limit=0)
                if post.comments.list():
                    top_comment = post.comments.list()[0].body[:300]
            except Exception:
                pass

            results.append(
                f"Title: {post.title}\n"
                f"Score: {post.score} | URL: {post.url}\n"
                f"Top comment: {top_comment}\n"
            )

        if not results:
            return f"No Reddit posts found for query: {query}"
        return "\n---\n".join(results)

    except Exception as e:
        logger.error("Reddit search failed: %s", e)
        return f"Reddit search unavailable: {e}"
