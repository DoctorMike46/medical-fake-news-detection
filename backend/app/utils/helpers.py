
LANG_WHITELIST = {"it", "en"}


def safe_str(x):
    return str(x).strip() if isinstance(x, (str, int, float)) else ""


def filter_by_lang(posts, whitelist=LANG_WHITELIST):
    out = []
    for p in posts or []:
        lang = (p.get("lang") or "").lower()
        if not whitelist or lang in whitelist:
            out.append(p)
    return out


def dedupe_posts(posts):
    """Deduplica su (source,id) oppure url."""
    seen_keys = set()
    out = []
    for p in posts or []:
        key = (p.get("source"), p.get("id")) if p.get("source") and p.get("id") else ("url", p.get("url"))
        if key not in seen_keys:
            seen_keys.add(key)
            out.append(p)
    return out


def post_enrich(p, query, campaign_id):
    p = dict(p or {})
    p["query"] = safe_str(query)
    p["campaign_id"] = str(campaign_id) if campaign_id else None
    p["processed"] = p.get("processed", False)
    p["stato_post"] = p.get("stato_post", "da verificare")
    return p

def normalize_is_fake(doc):
    g = (doc.get("analysis_results") or {}).get("grado_disinformazione")
    return g if g in (0, 1, -1, 2, 3) else 1