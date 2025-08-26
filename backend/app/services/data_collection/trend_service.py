from pytrends.request import TrendReq
import logging

logging.basicConfig(level=logging.INFO)

def get_google_trends(geo='IT', timeframe='now 24-H', category=71):
    """
    Recupera le query di ricerca di tendenza da Google Trends.
    :param geo: Codice paese (es. 'IT' per Italia).
    :param timeframe: Intervallo di tempo (es. 'now 24-H' per ultime 24 ore).
    :param category: Categoria di ricerca di Google Trends (71 per Health).
    :return: Lista di stringhe delle parole chiave di tendenza.
    """
    pytrends = TrendReq(hl='it-IT', tz=360)

    try:
        df_realtime = pytrends.realtime_search(ht='m', geo=geo, category=category)
        trending_topics = []
        if not df_realtime.empty:
            for index, row in df_realtime.iterrows():
                if 'title' in row and row['title']:
                    trending_topics.append(row['title'])
                if 'articles' in row and row['articles']:
                    for article in row['articles']:
                        if 'title' in article and article['title']:
                            trending_topics.append(article['title'])

        logging.info(f"Trovate {len(trending_topics)} parole chiave di tendenza da Google Trends.")
        return list(set(trending_topics))
    except Exception as e:
        logging.error(f"Errore nel recupero dei trend da Google Trends: {e}")
        return []