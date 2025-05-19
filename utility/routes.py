from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from utility.web_Scrapper import crawl_website
from Databases.mongo import Bot_Retrieval

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
