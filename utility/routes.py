from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from utility.web_Scrapper import crawl_website
from Databases.mongo import Bot_Retrieval
from On_boarding import chatbot
from embeddings_creator import embeddings_from_gcb
from Youtube_extractor import extract_and_store_descriptions

# app = Flask(__name__)
# CORS(app)  # Enable CORS if needed

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

logging.basicConfig(level=logging.INFO)


@app.route("/webscrapper", methods=["POST"], strict_slashes=False)
def scrapper():
    try:
        data = request.get_json(force=True)
        if not data or 'url' not in data:
            return jsonify({"error": "Missing 'url' parameter in JSON payload"}), 400

        url = data['url']
        app.logger.info(f"Received scraping request for URL: {url}")

        df = crawl_website(url)

        # Convert DataFrame to list of dicts for JSON serialization
        result_json = df.to_dict(orient="records")

        return jsonify({"result": result_json}), 200

    except Exception as e:
        app.logger.error(f"Error scraping URL: {e}", exc_info=True)
        return jsonify({"error": "The given URL does not have permission to scrape or an internal error occurred."}), 403

def on_boarding_Data(chatbot_id, version_id):
    Bot_information = Bot_Retrieval(chatbot_id, version_id)
    return Bot_information  # Ensure function returns the data

@app.route("/Onboarding", methods=["POST"], strict_slashes=False)
def onboard():
    try:
        request_data = request.get_json(force=True)
        if not request_data:
            return jsonify({"error": "JSON payload required"}), 400

        chatbot_id = request_data.get('chatbot_id')
        version_id = request_data.get('version_id')

        if not chatbot_id or not version_id:
            return jsonify({"error": "Both 'chatbot_id' and 'version_id' must be provided"}), 400

        bot_data = on_boarding_Data(chatbot_id, version_id)
        app.logger.info(f"Retrieved onboarding data for chatbot_id: {chatbot_id}, version_id: {version_id}")

        if not bot_data:
            return jsonify({"error": "No data found for given chatbot_id and version_id"}), 404

        return jsonify({"result": bot_data}), 200

    except Exception as e:
        app.logger.error(f"Error during onboarding data retrieval: {e}", exc_info=True)
        return jsonify({"error": "Internal server error occurred"}), 500



@app.route('/llm', methods=['POST'], strict_slashes=False)
def llm_endpoint():
    try:
        data = request.get_json()
        

        query = data.get("query")
        version_id = data.get("version_id")
        chatbot_id = data.get("chatbot_id")
        user_id = data.get("user_id")

        if not all([query, version_id, chatbot_id, user_id]):
            return jsonify({"error": "Missing required fields: query, version_id, chatbot_id, user_id"}), 400

        result = chatbot(chatbot_id, version_id, query, user_id)
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": f"An error occurred in llm_endpoint: {str(e)}"}), 500
    


@app.route('/file_uploads', methods=['POST'], strict_slashes=False)
def vector_embeddings():
    try:
        data = request.get_json()

        blob_names = data.get('blob_names')
        bucket_name = data.get('bucket_name')

        if not blob_names or not bucket_name:
            return jsonify({"error": "Missing required fields: blob_names, bucket_name"}), 400

        result = embeddings_from_gcb(bucket_name=bucket_name, blob_names=blob_names)
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": f"An error occurred in vector_embeddings: {str(e)}"}), 500
    

@app.route('/youtube_url', methods=['POST'])
def extract():
    data = request.json
    playlist_url = data.get('playlist_url')
    chatbot_id=data.get('chatbot_id')
    version_id=data.get('version_id')
    if not playlist_url and chatbot_id and version_id:
        return jsonify({'error': 'playlist_url, chatbot_id and version_id  is required'}), 400

    try:
        count = extract_and_store_descriptions(playlist_url,chatbot_id,version_id)
        return jsonify({'message': f'Successfully inserted {count} videos into MongoDB'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


