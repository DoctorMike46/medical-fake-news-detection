import logging
from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from app.services.analysis.factcheck_service import FactCheckService
from app.services.data_collection.data_collection_service import DataCollectionService
from app.services.llm.llm_manager import LLMManager
from app.utils.auth_decorators import jwt_required

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/trigger', methods=['POST', 'OPTIONS'])
@jwt_required
def trigger_analysis():
    """Avvia l'analisi dei post non processati"""
    DataCollectionService.trigger_analysis_for_campaign(current_app.mongo_manager)
    return jsonify({"message": "Analisi dei post avviata. Controlla i log per i dettagli."})


@analysis_bp.route('/ai_suggestion', methods=['POST', 'OPTIONS'])
@cross_origin()
@jwt_required
def get_ai_suggestion():
    """Fornisce suggerimenti AI per post singoli o report di campagna"""
    data = request.get_json()
    post_data = data.get('post_data')
    report_data = data.get('report_data')

    if not post_data and not report_data:
        return jsonify({"message": "Dati mancanti per la generazione del suggerimento AI."}), 400

    try:
        llm_manager = LLMManager() 
        current_llm_service = llm_manager.get_next_service()

        fact_check_service = FactCheckService(llm_manager)


        if post_data:
            # Analisi singolo post
            content = post_data.get('content', '').strip()
            if not content:
                return jsonify({"message": "Manca il campo 'content' in post_data."}), 400

            topic_guess = (
                post_data.get('keyword')
                or post_data.get('topic')
                or "salute"
            )

            fc = fact_check_service.run_factcheck(topic_guess, content)

            if fc.get("status") != "ok":
                return jsonify({
                    "message": "Analisi non riuscita",
                    "details": fc.get("error") or "unknown_error"
                }), 500

            factcheck = fc.get("factcheck", {}) or {}
            general = factcheck.get("general_claim", {}) or {}
            local_ = factcheck.get("local_claim", {}) or {}
            overall = factcheck.get("overall_verdict", "UNCERTAIN")
            conf = factcheck.get("confidence", 0.5)

            grado = fc.get("grado_disinformazione", 2)
            sentiment = fc.get("sentiment", "neutro")
            motivazione = fc.get("motivazione", "N/A")
            fonti = fc.get("fonti_utilizzate", [])

            ai_suggestion_text = (
                f"**Valutazione (dual-claim):** {overall} (confidenza {conf:.2f})\n"
                f"**Generale:** {general.get('verdict','UNCERTAIN')} — {general.get('reasoning','')}\n"
                f"**Locale/Temporale:** {local_.get('verdict','UNCERTAIN')} — {local_.get('reasoning','')}\n"
                f"**Grado di disinformazione (0/2/3):** {grado}\n"
                f"**Sentiment rilevato:** {sentiment}\n"
                f"**Fonti utilizzate:** {', '.join(fonti) if fonti else 'Nessuna.'}"
            )

            return jsonify({"suggestion": ai_suggestion_text}), 200

        elif report_data:
            campaign_name = report_data.get('campaign_name', 'N/A')
            
            keywords_val = report_data.get('keywords', [])
            if not isinstance(keywords_val, list):
                keywords_val = [str(keywords_val)]
            keywords = ", ".join([str(k) for k in keywords_val])

            platforms_val = report_data.get('social_platforms', [])
            if not isinstance(platforms_val, list):
                platforms_val = [str(platforms_val)]
            platforms = ", ".join([str(p) for p in platforms_val])
            
            duration = report_data.get('duration_days', 'N/A')
            
            total_posts = report_data.get('total_posts_count', 0)
            fake_news_count = report_data.get('total_fake_news_count', 0)
            real_posts_count = report_data.get('total_real_posts_count', 0)
            unknown_posts_count = report_data.get('total_unknown_posts_count', 0)

            author_monitored_count = report_data.get('totalMonitoredAuthors', 0)
            author_suspicious_count = report_data.get('suspiciousAuthors', 0)
            author_pending_count = report_data.get('pendingAuthors', 0)
            author_verify_count = report_data.get('verifiedAuthors', 0)

            sentiment_distribution_data = report_data.get('sentiment', [])
            sentiment_distribution = "\n".join([f"- {s['name']}: {s['value']} post" for s in sentiment_distribution_data if 'name' in s and 'value' in s])

            fake_news_distribution_data = report_data.get('fakePosts', [])
            fake_news_distribution = "\n".join([f"- {f['name']}: {f['value']} post" for f in fake_news_distribution_data if 'name' in f and 'value' in f])
            
            authors_summary = "\n".join([
                f"- {a['name']} ({a['post_count']} post, {a['fake_count']} fake news)" 
                for a in report_data.get('authorsSummary', [])[:5] 
            ])
            
            top_keywords = "\n".join([
                f"- {k['name']} ({k['value']} menzioni)" 
                for k in report_data.get('topKeywords', [])[:5] 
            ])

            prompt = f"""
            Genera un riepilogo finale dettagliato per il report di una campagna di monitoraggio sulla disinformazione medica.
            Fornisci insight sulla disinformazione rilevata, i pattern di sentiment, e i ruoli degli autori.
            
            Dati della Campagna:
            - Nome Campagna: {campaign_name}
            - Parole chiave: {keywords}
            - Piattaforme monitorate: {platforms}
            - Durata: {duration} giorni

            Statistiche Post:
            - Post Totali: {total_posts}
            - Fake News Rilevate: {fake_news_count}
            - Post Reali/Confermati: {real_posts_count}
            - Post Da Valutare: {unknown_posts_count}

            Statistiche Autori:
            - Autori Monitorati: {author_monitored_count}
            - Autori Sospetti: {author_suspicious_count}
            - Autori In Attesa: {author_pending_count}
            - Autori Verificati: {author_verify_count}

            Distribuzione Sentiment:
            {sentiment_distribution if sentiment_distribution else "Nessun dato di sentiment disponibile."}

            Distribuzione Fake News:
            {fake_news_distribution if fake_news_distribution else "Nessun dato sulle fake news disponibile."}

            Autori più Attivi (Top 5):
            {authors_summary if authors_summary else "Nessun autore attivo rilevato."}
            
            Parole Chiave Frequenti (Top 5):
            {top_keywords if top_keywords else "Nessuna parola chiave frequente rilevata."}

            Sulla base di questi dati, il tuo riepilogo dovrebbe:
            1. Identificare le principali tendenze di disinformazione e sentiment.
            2. Evidenziare i temi più dibattuti (anche se non sempre correlati a fake news).
            3. Nominare gli autori più attivi o quelli che hanno pubblicato fake news significative.
            4. In base alle statistiche sugli autori fornire un riepilogo dettagliato e suggerire delle azioni all'analista
            5. Suggerire Azioni per l'Analista: Cosa dovrebbe fare il team dopo questo report? (es. "Focus su autori X", "Monitorare nuove parole chiave", "Avviare campagne di sensibilizzazione su tema Y").

            Rispondi in italiano. Limite massimo: 300 parole.
            """

            ai_suggestion_text = current_llm_service.generate_text(prompt)
            return jsonify({"suggestion": ai_suggestion_text}), 200

    except Exception as e:
        logging.error(f"Errore nella generazione del suggerimento AI: {e}", exc_info=True)
        return jsonify({
            "message": f"Errore interno del server nella generazione del suggerimento AI: {str(e)}"
        }), 500