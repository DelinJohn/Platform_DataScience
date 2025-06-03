from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
from threading import Thread, Lock
from werkzeug.middleware.proxy_fix import ProxyFix
from .On_boarding import chatbot
from utility.web_Scrapper import crawl_website
from Databases.mongo import Bot_Retrieval
# from Platform_DataScience.utility.On_boarding_old import chatbot
from embeddings_creator import embeddings_from_gcb, embeddings_from_website_content
from Youtube_extractor import extract_and_store_descriptions

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
CORS(app)

logging.basicConfig(level=logging.INFO)

# Thread tracking variables
active_threads = 0
lock = Lock()

# Utility to mark thread completion
def mark_thread_done():
    global active_threads
    with lock:
        active_threads -= 1
        if active_threads == 0:
            app.logger.info("✅ All background tasks completed. Status: completed")

# Background processing functions

def process_scraping(url):
    try:
        app.logger.info(f"Started background scraping for URL: {url}")
        df = crawl_website(url)

        json_data = df.to_dict(orient="records")
        with open("website_data.json", "w") as f:
            json.dump(json_data, f, indent=4)

        app.logger.info(f"Scraping complete for URL: {url}")
    except Exception as e:
        app.logger.error(f"Error during background scraping: {str(e)}")
    finally:
        mark_thread_done()


def background_embedding_task(bucket, blobs):
    try:
        app.logger.info(f"Started embedding for bucket: {bucket}, blobs: {blobs}")
        embeddings_from_gcb(bucket_name=bucket, blob_names=blobs)
        app.logger.info(f"Completed embedding generation for blobs in bucket: {bucket}")
    except Exception as e:
        app.logger.error(f"Error during embedding generation: {str(e)}")
    finally:
        mark_thread_done()


def background_scrape(url, chatbot, version):
    try:
        app.logger.info(f"Started background scrape for playlist: {url}")
        count = extract_and_store_descriptions(url, chatbot, version)
        app.logger.info(f"Successfully inserted {count} videos from {url} for chatbot {chatbot}")
    except Exception as e:
        app.logger.error(f"Background scrape error: {str(e)}")
    finally:
        mark_thread_done()

# Routes

@app.route("/webscrapper", methods=["POST"], strict_slashes=False)
def scrapper():
    global active_threads
    try:
        data = request.get_json(force=True)
        url = data.get('url')
        if not url:
            return jsonify({"error": "Missing 'url' parameter"}), 400

        with lock:
            active_threads += 1
        Thread(target=process_scraping, args=(url,)).start()
        return jsonify({"result": "Scraping started in background."}), 200
    except Exception as e:
        app.logger.error(f"Scraper error: {e}", exc_info=True)
        return jsonify({"error": "Internal error"}), 500


@app.route("/file_uploads", methods=["POST"], strict_slashes=False)
def vector_embeddings():
    global active_threads
    try:
        data = request.get_json()
        blob_names = data.get('blob_names')
        bucket_name = data.get('bucket_name')

        if not blob_names or not bucket_name:
            return jsonify({"error": "Missing blob_names or bucket_name"}), 400

        with lock:
            active_threads += 1
        Thread(target=background_embedding_task, args=(bucket_name, blob_names)).start()

        return jsonify({"result": "Embedding started in background."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/youtube_url', methods=['POST'])
def extract():
    global active_threads
    data = request.json
    playlist_url = data.get('playlist_url')
    chatbot_id = data.get('chatbot_id')
    version_id = data.get('version_id')

    if not all([playlist_url, chatbot_id, version_id]):
        return jsonify({'error': 'playlist_url, chatbot_id, and version_id are required'}), 400

    with lock:
        active_threads += 1
    Thread(target=background_scrape, args=(playlist_url, chatbot_id, version_id)).start()

    return jsonify({'message': 'YouTube scraping started in background.'}), 200


@app.route("/Onboarding", methods=["POST"], strict_slashes=False)
def onboard():
    try:
        data = request.get_json(force=True)
        chatbot_id = data.get('chatbot_id')
        version_id = data.get('version_id')

        if not chatbot_id or not version_id:
            return jsonify({"error": "chatbot_id and version_id required"}), 400

        bot_data = Bot_Retrieval(chatbot_id, version_id)
        if not bot_data:
            return jsonify({"error": "No data found"}), 404

        return jsonify({"result": bot_data}), 200
    except Exception as e:
        app.logger.error(f"Onboarding error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/llm', methods=['POST'], strict_slashes=False)
def llm_endpoint():
    try:
        data = request.get_json()
        query = data.get("query")
        version_id = data.get("version_id")
        
        chatbot_id = data.get("chatbot_id")
        user_id = data.get("user_id")

        if not all([query, version_id, chatbot_id, user_id]):
            return jsonify({"error": "Missing required fields"}), 400

        result = chatbot(chatbot_id, version_id, query, user_id)
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": f"LLM error: {str(e)}"}), 500
    
   


@app.route("/status", methods=["GET"])
def get_status():
    with lock:
        if active_threads == 0:
            return jsonify({"status": "completed"})
        else:
            return jsonify({"status": f"{active_threads} task(s) still running"})



