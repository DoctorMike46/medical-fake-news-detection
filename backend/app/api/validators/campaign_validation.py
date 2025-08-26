
from app.services.data_collection.evergreen.topic_analyzer import TopicAnalyzer


ALLOWED_PLATFORMS = {"twitter", "reddit", "youtube", "facebook"}

def validate_and_prepare_campaign_inputs(name: str, keywords: list, platforms: list):
    """
    Valida e normalizza gli input di una campagna.
    Ritorna dict {name, keywords, platforms, topic_profiles}
    """
    errors = []

    if not isinstance(name, str) or len(name.strip()) < 3:
        errors.append("Il nome della campagna deve avere almeno 3 caratteri.")
    name = name.strip()

    if not isinstance(keywords, (list, tuple)) or not keywords:
        errors.append("Devi fornire almeno una keyword.")
    else:
        keywords = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
        keywords = list(dict.fromkeys(keywords))
        if not keywords:
            errors.append("Tutte le keyword erano vuote o non valide.")
        if any(len(k) < 2 for k in keywords):
            errors.append("Ogni keyword deve avere almeno 2 caratteri.")
        if len(keywords) > 10:
            errors.append("Massimo 10 keyword per campagna.")

    if not isinstance(platforms, (list, tuple)) or not platforms:
        errors.append("Devi selezionare almeno una piattaforma.")
    else:
        platforms = [p.strip().lower() for p in platforms if isinstance(p, str)]
        platforms = list(dict.fromkeys(platforms))
        invalid = [p for p in platforms if p not in ALLOWED_PLATFORMS]
        if invalid:
            errors.append(f"Piattaforme non valide: {', '.join(invalid)}")
        platforms = [p for p in platforms if p in ALLOWED_PLATFORMS]

    
    topic_analyzer = TopicAnalyzer()

    topic_profiles = []
    for kw in keywords:
        
        profile = topic_analyzer.generate_topic_profile(kw)
        
        topic_key = profile.get("topic_key", "")
        it_aliases = profile.get("aliases", {}).get("it", [])
        en_aliases = profile.get("aliases", {}).get("en", [])


        urls = topic_analyzer._build_institutional_sources(topic_key, it_aliases, en_aliases)
        topic_profiles.append({
            "keyword": kw,
            "topic_key": topic_key,
            "aliases_it": it_aliases,
            "aliases_en": en_aliases,
            "source_urls": urls
        })

    if errors:
        return {"errors": errors}

    return {
        "name": name,
        "keywords": keywords,
        "platforms": platforms,
        "topic_profiles": topic_profiles
    }
