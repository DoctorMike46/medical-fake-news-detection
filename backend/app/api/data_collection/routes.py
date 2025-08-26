import time
import logging
from flask import Blueprint, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from app.services.data_collection.data_collection_service import DataCollectionService
from app.utils.auth_decorators import jwt_required

data_collection_bp = Blueprint('data_collection', __name__)


@data_collection_bp.route('/collect', methods=['POST'])
@jwt_required
def collect_posts():
    """Raccoglie post dai social media"""
    data = request.json
    query = data.get('query')
    source = data.get('source', 'all')
    num_posts = data.get('num_posts', 50)

    if not query:
        return jsonify({"error": "La query è obbligatoria"}), 400

    collected_count = DataCollectionService.collect_posts(query, source, num_posts)
    
    return jsonify({
        "message": f"Raccolti e salvati {collected_count} post per la query '{query}' da {source}."
    })


@data_collection_bp.route('/trends', methods=['GET'])
@jwt_required
def get_google_trends():
    """Recupera i termini di ricerca di tendenza da Google Trends per l'Italia"""
    trends_data = []
    driver = None

    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-blink-features=AutomationControlled") 
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        url = f'https://trends.google.it/trending?geo=IT&hl=it&category=7&hours=168' 

        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.mZ3RIc'))
        )

        trending_items = driver.find_elements(By.CSS_SELECTOR, '.mZ3RIc')
        trending_terms = [f"{item.text}" for item in trending_items]
        trends_data.extend(trending_terms)
        
        driver.quit()

        return jsonify({"status": "success", "trends": trends_data})
        
    except Exception as e:
        logging.error(f"Server error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as quit_e:
                logging.warning(f"Errore durante la chiusura del driver: {quit_e}")


@data_collection_bp.route('/who_news', methods=['GET'])
@jwt_required
def get_who_news():
    """Recupera le ultime notizie dal sito web dell'OMS"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get("https://www.who.int/news")
        time.sleep(5)
        
        news_items = driver.find_elements(By.CLASS_NAME, "list-view--item.vertical-list-item")
        news_data = []
        
        for item in news_items:
            try:
                date = item.find_element(By.CLASS_NAME, "timestamp").text
                title = item.find_element(By.CLASS_NAME, "heading.text-underline").text
                url = item.find_element(By.TAG_NAME, "a").get_attribute("href")
                news_data.append({"date": date, "title": title, "url": url})
            except:
                continue

        return jsonify({"status": "success", "articles": news_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        driver.quit()