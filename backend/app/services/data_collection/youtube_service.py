import logging
from datetime import datetime, timezone
from typing import List, Optional
from googleapiclient.discovery import build
from tenacity import retry, wait_exponential, stop_after_attempt
from app.core.config import Config
import os
from dotenv import load_dotenv
from app.nlp.preprocessing.language_detector import LanguageDetector
from app.nlp.preprocessing.text_cleaner import TextCleaner
load_dotenv()

YOUTUBE_API_KEY = Config.YOUTUBE_API_KEY
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _iso(s: str) -> Optional[str]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    except Exception:
        return None

@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3))
def _yt_build():
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY, cache_discovery=False)

def search_youtube_comments(query: str, max_comments: int = 100, include_replies: bool = True, campaign_id: Optional[str] = None) -> List[dict]:
    if not YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY non configurata.")
        return []
    yt = _yt_build()

    text_cleaner = TextCleaner()
    language_detector = LanguageDetector()  

    # 1) cerca video (con relevanceLanguage per IT se utile)
    video_ids = []
    try:
        req = yt.search().list(
            q=query, type="video", part="id",
            maxResults=25, order="relevance", relevanceLanguage="it"
        )
        while True:
            resp = req.execute()
            for it in resp.get("items", []):
                video_ids.append(it["id"]["videoId"])
            if "nextPageToken" in resp and len(video_ids) < 100:
                req = yt.search().list(
                    q=query, type="video", part="id",
                    maxResults=25, order="relevance",
                    relevanceLanguage="it", pageToken=resp["nextPageToken"]
                )
            else:
                break
    except Exception as e:
        logger.error(f"Errore ricerca video: {e}")
        return []

    out, seen = [], set()

    # 2) commenti per video (paginazione)
    for vid in video_ids:
        if len(out) >= max_comments: break
        try:
            req = yt.commentThreads().list(
                part="snippet,replies",
                videoId=vid,
                maxResults=min(100, max_comments - len(out)),
                textFormat="plainText",
                order="relevance",
            )
            while True:
                resp = req.execute()
                for item in resp.get("items", []):
                    top = item["snippet"]["topLevelComment"]["snippet"]
                    cid = item["snippet"]["topLevelComment"]["id"]
                    if cid in seen: 
                        continue
                    seen.add(cid)
                    text = text_cleaner.extract_clean_text_for_analysis(top.get("textDisplay") or top.get("textOriginal"))
                    lang = language_detector.detect_language(text)
                    out.append({
                        "source": "youtube",
                        "id": cid,
                        "parent_id": None,
                        "video_id": vid,
                        "title": f"Commento su video: {vid}",
                        "text": text,
                        "url": f"https://www.youtube.com/watch?v={vid}&lc={cid}",
                        "author_name": top.get("authorDisplayName"),
                        "author_handle": None,
                        "created_utc": _iso(top.get("publishedAt")),
                        "lang": lang,
                        "platform_meta": {
                            "likeCount": top.get("likeCount"),
                            "canRate": top.get("canRate"),
                            "viewerRating": top.get("viewerRating")
                        },
                        "query": query,
                        "processed": False,
                        "campaign_id": str(campaign_id) if campaign_id else None,
                    })
                    if len(out) >= max_comments: break

                    if include_replies:
                        for r in item.get("replies", {}).get("comments", []):
                            rs = r["snippet"]
                            rcid = r["id"]
                            if rcid in seen: 
                                continue
                            seen.add(rcid)
                            rtext = text_cleaner.extract_clean_text_for_analysis(rs.get("textDisplay") or rs.get("textOriginal"))
                            rlang = language_detector.detect_language(rtext)
                            out.append({
                                "source": "youtube",
                                "id": rcid,
                                "parent_id": cid,
                                "video_id": vid,
                                "title": f"Reply su video: {vid}",
                                "text": rtext,
                                "url": f"https://www.youtube.com/watch?v={vid}&lc={rcid}",
                                "author_name": rs.get("authorDisplayName"),
                                "author_handle": None,
                                "created_utc": _iso(rs.get("publishedAt")),
                                "lang": rlang,
                                "platform_meta": {
                                    "likeCount": rs.get("likeCount"),
                                },
                                "query": query,
                                "processed": False,
                                "campaign_id": str(campaign_id) if campaign_id else None,
                            })
                            if len(out) >= max_comments: break
                    if len(out) >= max_comments: break

                if "nextPageToken" in resp and len(out) < max_comments:
                    req = yt.commentThreads().list(
                        part="snippet,replies",
                        videoId=vid,
                        maxResults=min(100, max_comments - len(out)),
                        textFormat="plainText",
                        order="relevance",
                        pageToken=resp["nextPageToken"]
                    )
                else:
                    break

        except Exception as e:
            logger.warning(f"Commenti non disponibili per video {vid}: {e}")
            continue

    logger.info(f"YouTube: raccolti {len(out)} commenti per '{query}'")
    return out
