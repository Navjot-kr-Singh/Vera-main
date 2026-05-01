# AI Message Engine for Merchant Marketing

A production-ready, full-stack application that generates high-quality, context-aware marketing messages for merchants. Designed to mimic advanced AI behavior using a sophisticated rule-based engine.

## Features
- **Context-Aware Engine**: Weights triggers, categories, merchants, and customer context to generate highly personalized messages.
- **Dynamic Content**: Uses dynamic date handling to inject urgency (e.g. checking for weekends).
- **Scoring System**: Generates multiple variations of a message and scores them based on urgency, CTA presence, and offer details. Returns the top 3.
- **Explainable Reasoning**: Explains exactly why a message was constructed the way it was.
- **Premium UI**: A beautiful, responsive, glassmorphism UI built with Tailwind CSS.

## Architecture

1. **Backend (`server.py`)**: A Flask application running on port `8000` (specifically configured to avoid port 5000 as per requirements). It serves the frontend static files and exposes a POST `/api/generate` endpoint.
2. **Core Logic (`message_engine.py`)**: The brain of the application. It contains category configurations (tones, emojis, templates), trigger configurations (urgency prefixes/suffixes), and scoring algorithms. It does not rely on expensive API calls, making it blazingly fast and deterministic.
3. **Frontend (`static/`)**: A pure HTML/CSS/JS frontend using Tailwind via CDN. `app.js` handles form submission, API interaction, and dynamic UI updates.

## Setup Instructions

### Prerequisites
- Python 3.8+
- Flask

### Installation

1. Clone or navigate to the directory:
   ```bash
   cd /path/to/magicpin-ai-challenge
   ```

2. Install dependencies (Flask):
   ```bash
   pip install flask
   ```

3. Run the application:
   ```bash
   python server.py
   ```
   *The server will start on `http://0.0.0.0:8000`*

4. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

## Testing

A set of sample inputs is provided in `tests/sample_requests.json`. You can test these manually in the UI or by making POST requests to the `/api/generate` endpoint.

Example cURL request:
```bash
curl -X POST http://localhost:8000/api/generate \
-H "Content-Type: application/json" \
-d '{
  "category": "restaurant",
  "merchant_name": "Pizza Hut",
  "offer": "Buy 1 Get 1 Free",
  "trigger": "weekend",
  "customer_context": "inactive"
}'
```

### Output Format Example
```json
{
  "message": "We missed you! Come back for this: Weekend Special! Craving Pizza Hut? Buy 1 Get 1 Free this weekend! Order now! 🍕",
  "reasoning": "Message prioritizes weekend trigger with restaurant tone. Includes personalization for inactive customer. Highlights Buy 1 Get 1 Free to drive conversion.",
  "tags": [
    "leisure",
    "weekend",
    "restaurant"
  ],
  "confidence_score": 85,
  "alternative_variations": [
    {
      "message": "We missed you! Come back for this: Weekend Special! Treat yourself to Pizza Hut. Buy 1 Get 1 Free waiting for you! Visit today! 🍔",
      "reasoning": "",
      "tags": [""],
      "confidence_score": 85
    },
    {  }
  ]
}
```
