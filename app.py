from flask import Flask, request, jsonify
from flask_cors import CORS
import requests  # To send requests to scraper.py

app = Flask(__name__)
CORS(app)  # Allows Wix to communicate with your API

@app.route('/', methods=['GET'])
def home():
    return "Flask API is running!"

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    url = data.get("url")  # Extract the URL from Wix

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Send URL to scraper.py
        scraper_response = requests.post("https://render-scraper-1wjr.onrender.com/scrape", json={"url": url})

        if scraper_response.status_code == 200:
            return jsonify(scraper_response.json())  # Return the scraped data to Wix
        else:
            return jsonify({"error": "Scraper failed", "details": scraper_response.text}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # Keep Flask API on port 5000
