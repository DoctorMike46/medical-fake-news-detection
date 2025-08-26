import logging
from datetime import datetime, timezone
from typing import List, Optional
import praw
from tenacity import retry, wait_exponential, stop_after_attempt
from app.core.config import Config
import os
from dotenv import load_dotenv
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REDDIT_CLIENT_ID = Config.REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET = Config.REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT = Config.REDDIT_USER_AGENT

@retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(3))
def _reddit():
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        check_for_async=False
    )

def search_reddit_posts(
    query: str,
    limit: int = 50,
    *,
    campaign_id: Optional[str] = None,
    subreddits: Optional[List[str]] = None
) -> List[dict]:
    try:
        reddit = _reddit()
    except Exception as e:
        logger.error(f"PRAW init error: {e}")
        return []

    # --- normalizzazione subreddits ---
    def _norm_subs(x):
        if x is None:
            return None
        if isinstance(x, (str, int, float)):
            s = str(x).strip()
            return [s] if s else None
        if isinstance(x, (list, tuple, set)):
            out = [str(v).strip() for v in x if str(v).strip()]
            return out or None
        return None

    subs_list = _norm_subs(subreddits)
    subs = "+".join(subs_list) if subs_list else "all"

    text_cleaner = TextCleaner()
    language_detector = LanguageDetector()

    posts = []
    try:
        for s in reddit.subreddit(subs).search(query, limit=limit, sort="relevance", time_filter="year"):
            text = text_cleaner.extract_clean_text_for_analysis(s.selftext if s.is_self else "")
            title = text_cleaner.extract_clean_text_for_analysis(s.title) if s.title else None
            lang = language_detector.detect_language((title or "") + " " + (text or ""))
            posts.append({
                "source": "reddit",
                "id": str(s.id),
                "parent_id": None,
                "title": title,
                "text": text if s.is_self else title,
                "url": f"https://www.reddit.com{s.permalink}",
                "author_name": s.author.name if s.author else None,
                "author_handle": None,
                "created_utc": datetime.fromtimestamp(s.created_utc, tz=timezone.utc).isoformat(),
                "lang": lang,
                "platform_meta": {
                    "score": s.score,
                    "num_comments": s.num_comments,
                    "subreddit": s.subreddit.display_name,
                    "over_18": s.over_18
                },
                "query": query,
                "processed": False,
                "campaign_id": str(campaign_id) if campaign_id else None
            })
    except Exception as e:
        logger.error(f"Errore ricerca Reddit: {e}")
        return posts

    logger.info(f"Reddit: raccolti {len(posts)} post per '{query}' (subs={subs})")
    return posts