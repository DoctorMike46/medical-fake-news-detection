import logging
from app.utils.helpers import safe_str, filter_by_lang, dedupe_posts, post_enrich, LANG_WHITELIST
from app.services.data_collection.twitter_service import search_tweets
from app.services.data_collection.reddit_service import search_reddit_posts
from app.services.data_collection.facebook_service import search_facebook_posts
from app.services.data_collection.youtube_service import search_youtube_comments
from app.services.data_collection.rss_service import RSSService
from app.services.analysis.analysis_orchestrator import AnalysisOrchestrator
from flask import current_app


class DataCollectionService:
    
    @staticmethod
    def collect_posts(query, source='all', num_posts=50):
        """Raccoglie post da diverse piattaforme social"""
        collected_count = 0
        mongo_manager = current_app.mongo_manager

        if source == 'facebook' or source == 'all':
            try:
                facebook_posts = search_facebook_posts(query, num_posts)
                for post in facebook_posts:
                    post['stato_post'] = 'da verificare'
                collected_count += mongo_manager.insert_posts('social_posts', facebook_posts)
            except Exception as e:
                logging.error(f"Errore durante la raccolta di post da Facebook: {e}")

        if source == 'twitter' or source == 'all':
            if not current_app.config.get('TWITTER_BEARER_TOKEN'):
                logging.warning("TWITTER_BEARER_TOKEN non configurato. Skip raccolta Twitter.")
            else:
                twitter_posts = search_tweets(query, num_posts)
                for post in twitter_posts:
                    post['stato_post'] = 'da verificare'
                collected_count += mongo_manager.insert_posts('social_posts', twitter_posts)
            
        if source == 'reddit' or source == 'all':
            if not (current_app.config.get('REDDIT_CLIENT_ID') and current_app.config.get('REDDIT_CLIENT_SECRET')):
                logging.warning("Credenziali Reddit non configurate. Skip raccolta Reddit.")
            else:
                reddit_posts = search_reddit_posts(query, num_posts)
                for post in reddit_posts:
                    post['stato_post'] = 'da verificare'
                collected_count += mongo_manager.insert_posts('social_posts', reddit_posts)

        if source == 'youtube' or source == 'all':
            if not current_app.config.get('YOUTUBE_API_KEY'):
                logging.warning("YOUTUBE_API_KEY non configurata. Skip raccolta YouTube.")
            else:
                youtube_comments = search_youtube_comments(query, num_posts)
                for post in youtube_comments:
                    post['stato_post'] = 'da verificare'
                collected_count += mongo_manager.insert_posts('social_posts', youtube_comments)

        if source == 'news' or source == 'rss' or source == 'all':
            try:
                rss_service = RSSService()
                news_articles = rss_service.search_rss_news(query, num_posts)
                for article in news_articles:
                    article['stato_post'] = 'da verificare'
                collected_count += mongo_manager.insert_posts('social_posts', news_articles)
            except Exception as e:
                logging.error(f"Errore durante la raccolta di articoli RSS/News: {e}")
            
        return collected_count

    @staticmethod
    def collect_posts_for_campaign(query, source, num_posts, campaign_id, mongo_manager):
        """Raccolta dati robusta per una campagna specifica"""
        collected_count = 0
        source = safe_str(source).lower()
        query = safe_str(query)
        num_posts = int(num_posts) if str(num_posts).isdigit() else 50
        num_posts = max(1, min(num_posts, 200))

        batch = []

        try:
            if source == 'twitter' or source == 'all':
                try:
                    twitter_posts = search_tweets(query=query, limit=num_posts, campaign_id=str(campaign_id))
                    twitter_posts = [post_enrich(p, query, campaign_id) for p in twitter_posts]
                    batch.extend(twitter_posts)
                except Exception as e:
                    logging.error(f"[collect] Twitter errore: {e}")

            if source == 'facebook' or source == 'all':
                try:
                    facebook_posts = search_facebook_posts(query=query, limit=num_posts, campaign_id=str(campaign_id))
                    facebook_posts = [post_enrich(p, query, campaign_id) for p in facebook_posts]
                    batch.extend(facebook_posts)
                except Exception as e:
                    logging.error(f"[collect] Facebook errore: {e}")

            if source == 'reddit' or source == 'all':
                try:
                    reddit_posts = search_reddit_posts(query=query, limit=num_posts, subreddits=None, campaign_id=str(campaign_id))
                    reddit_posts = [post_enrich(p, query, campaign_id) for p in reddit_posts]
                    batch.extend(reddit_posts)
                except Exception as e:
                    logging.error(f"[collect] Reddit errore: {e}")

            if source == 'youtube' or source == 'all':
                try:
                    youtube_comments = search_youtube_comments(query=query, max_comments=num_posts, include_replies=True, campaign_id=str(campaign_id))
                    youtube_comments = [post_enrich(p, query, campaign_id) for p in youtube_comments]
                    batch.extend(youtube_comments)
                except Exception as e:
                    logging.error(f"[collect] YouTube errore: {e}")

            if source == 'news' or source == 'rss' or source == 'all':
                try:
                    rss_service = RSSService()
                    news_articles = rss_service.search_rss_news(query=query, limit=num_posts, campaign_id=str(campaign_id))
                    news_articles = [post_enrich(p, query, campaign_id) for p in news_articles]
                    batch.extend(news_articles)
                except Exception as e:
                    logging.error(f"[collect] RSS/News errore: {e}")

            batch = filter_by_lang(batch, LANG_WHITELIST)
            batch = dedupe_posts(batch)

            if batch:
                collected_count += mongo_manager.insert_posts('social_posts', batch)

            return collected_count

        except Exception as e:
            logging.error(f"Errore in collect_posts_for_campaign: {e}", exc_info=True)
            return collected_count

    @staticmethod
    def trigger_analysis_for_campaign(mongo_manager):
        """Avvia l'analisi dei post per una campagna"""
        orchestrator_instance = AnalysisOrchestrator(mongo_manager)
        
        while True:
            initial_unprocessed_count = mongo_manager.db.social_posts.count_documents({"processed": False})
            
            if initial_unprocessed_count == 0:
                logging.info("Tutti i post non processati sono stati analizzati. Fine del ciclo di analisi.")
                break

            logging.info(f"Avvio un nuovo batch di analisi. Post non processati attuali: {initial_unprocessed_count}.")
            
            orchestrator_instance.run_analysis_batch(batch_size=50) 
            
            final_unprocessed_count = mongo_manager.db.social_posts.count_documents({"processed": False})
            
            posts_processed_in_this_batch = initial_unprocessed_count - final_unprocessed_count
            logging.info(f"Processati {posts_processed_in_this_batch} post in questo batch. Rimanenti: {final_unprocessed_count}.")
            
            if posts_processed_in_this_batch == 0 and initial_unprocessed_count > 0:
                logging.warning("Nessun post processato in questo batch, ma ci sono ancora post non processati. Controllare i log di errore e la configurazione dell'orchestratore.")
                break