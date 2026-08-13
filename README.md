Receipt AI – Complete Documentation
AI‑powered receipt extraction, review, and analytics dashboard
Built with Flask, Novita AI (Vision + Text), and Chart.js.

📌 Overview
Receipt AI is a full‑stack web application that:

Uploads a receipt image (PNG, JPG, etc.).

Extracts structured data (merchant, date, amounts, category, etc.) using Novita AI models.

Shows an editable review form so you can correct any AI mistakes.

Saves the confirmed data to CSV and JSON, with the original image stored permanently.

Visualises your expenses in a dashboard with:

Filters (date range, category, merchant)

Summary cards (total receipts, total spent, average, min/max)

Bar chart (spending by category)

Line chart (spending trend over time)

Table with thumbnail images (click to enlarge)

One‑click export of filtered data as JSON

🚀 Features
✅ AI‑driven extraction – uses Novita’s Vision model (Qwen VL) for description and Text model (DeepSeek V3.2) for structured JSON.

✅ Human‑in‑the‑loop – user can edit every field before saving.

✅ Permanent image storage – receipt images are saved forever, linked in the JSON record.

✅ Duplicate prevention – prevents double‑saving the same receipt.

✅ Session management – temporary data expires after 30 minutes.

✅ Dashboard – filter, analyse, and export your expenses.

✅ CSV + JSON export – all data is stored in both formats.

✅ Responsive design – works on desktop and mobile.

🧰 Tech Stack
Component	Technology
Backend	Flask (Python 3.10+)
AI Integration	Novita AI API (OpenAI‑compatible client)
Frontend	HTML, CSS, JavaScript, Chart.js
Data Storage	CSV (append), JSON (individual records)
Image Storage	Local folder (images/)
Environment	python-dotenv, openai
📁 Folder Structure
text
project/
├── .env                      # Environment variables
├── app.py                    # Main Flask application
├── ai_service.py             # AI integration (Vision + Text)
├── utils.py                  # Helper functions (tokens, dates, duplicates)
├── templates/                # HTML templates
│   ├── index.html            # Upload page
│   ├── review.html           # Editable review form
│   ├── success.html          # Confirmation page
│   └── dashboard.html        # Dashboard with charts
├── images/                   # Permanently stored receipt images
├── results/                  # Temporary session data + processed IDs
│   └── temp/                 # Session temp files (auto‑cleaned)
├── results_clean/            # Final cleaned JSON records
├── uploads/                  # Temporary upload folder (auto‑deleted)
└── expenses_full.csv         # All receipts in one CSV file
⚙️ Installation
1. Clone the repository
bash
git clone https://github.com/yourusername/receipt-ai.git
cd receipt-ai
2. Create and activate a virtual environment (recommended)
bash
python -m venv venv
source venv/bin/activate       # Linux/Mac
# or
venv\Scripts\activate          # Windows
3. Install dependencies
bash
pip install flask python-dotenv openai
4. Set up environment variables
Create a .env file in the project root with the following content:

env
# Novita AI API key (get from https://novita.ai)
NOVITA_API_KEY=your-api-key-here

# Flask secret key – generate one with:
# python -c 'import secrets; print(secrets.token_hex(32))'
SECRET_KEY=your-super-secret-random-hex-string
5. Run the application
bash
python app.py
The server will start at http://localhost:3000.
Visit that URL in your browser.

🧑‍💻 Usage
Upload a Receipt
On the home page, click Choose image and select a receipt image (PNG, JPG, JPEG, GIF).

Click Upload & Process.

Wait a few seconds for the AI to extract the data.

Review & Edit
The system shows a pre‑filled form with all extracted fields.

Correct any mistakes (e.g., adjust the total, change the category).

Fields marked with * are required.

Tip: The raw description is shown below for reference.

Confirm & Save
Click Accept & Save to store the receipt.

The data is appended to expenses_full.csv and a clean JSON file is saved in results_clean/.

You’ll see a success page with a summary.

Dashboard
Click the Dashboard link (or visit /dashboard).

Use the filters at the top to narrow down receipts by date range, category, or merchant.

Summary cards show key metrics.

Charts update automatically based on the filtered data.

The table shows all receipts with clickable thumbnail images.

Click Export Filtered Data (JSON) to download the current filtered view as JSON.

🔧 Configuration
Environment Variable	Description
NOVITA_API_KEY	Your Novita AI API key.
SECRET_KEY	Flask secret key – must be set to a random string in production.
PORT	(optional) Port number, defaults to 3000.
Custom Categories
The default categories are:
FOOD, TRANSPORTATION, HOUSING, HEALTHCARE, ENTERTAINMENT, SHOPPING, EDUCATION, PERSONAL_CARE, TRAVEL, INSURANCE, OTHER

You can change the list in app.py (look for valid_categories in the /confirm route) and in the dashboard dropdown (in templates/dashboard.html).

AI Models
You can switch to other models supported by Novita AI by editing VISION_MODEL and TEXT_MODEL in ai_service.py.
Current:

Vision: qwen/qwen3-vl-235b-a22b-instruct

Text: deepseek/deepseek-v3.2

📊 Data Format
CSV (expenses_full.csv)
Columns:

text
timestamp, image_name, image_path, merchant, date, time, subtotal, tax, total, payment_method, category, raw_description, processed_at
JSON (results_clean/*_clean.json)
Example record:

json
{
  "timestamp": "2026-08-12T16:25:38.693615",
  "image_name": "2026-08-12_15.49.57.jpg",
  "image_path": "images/2026-08-12_15.49.57_20260812_162432.jpg",
  "merchant": "Lazy Dog Restaurant & Bar",
  "date": "2026-08-06",
  "time": "1:30 PM",
  "subtotal": 73.9,
  "tax": 7.21,
  "total": 81.11,
  "payment_method": "Cash",
  "category": "FOOD",
  "raw_description": "Here is a detailed description...",
  "processed_at": "2026-08-12T16:25:38.693615"
}
🌐 API Endpoints (for developers)
Endpoint	Method	Description
/	GET	Home page (upload form).
/upload	POST	Accepts image file, processes AI, renders review form.
/confirm	POST	Accepts edited form data, saves to CSV/JSON.
/dashboard	GET	Renders the dashboard with filter parameters.
/export	GET	Returns filtered data as JSON (same filters as dashboard).
/images/<filename>	GET	Serves a receipt image from the images/ folder.
All endpoints return HTML (except /export which returns JSON) and use Flask’s session/token system for temporary data.

