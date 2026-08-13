import os
import base64
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url='https://api.novita.ai/openai/v1',
    api_key=os.getenv('NOVITA_API_KEY')
)

VISION_MODEL = 'qwen/qwen3-vl-235b-a22b-instruct'
TEXT_MODEL = 'deepseek/deepseek-v3.2'

def process_image(image_bytes, filename):
    """
    Takes image bytes, sends to Vision model for description,
    then sends description to Text model for structured JSON.
    Returns a dict with the extracted fields.
    """
    # Step 1: Vision description
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    vision_prompt = "Describe this receipt in detail, including all visible text, amounts, dates, and merchant information."

    vision_response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }
        ],
        temperature=0.3,
        max_tokens=600,
    )
    raw_description = vision_response.choices[0].message.content

    # Step 2: Text extraction
    extraction_prompt = f"""
Extract the following fields from this receipt description and return ONLY a JSON object with these exact keys:
- merchant (string)
- date (string, try to output in YYYY-MM-DD format if possible, else null)
- time (string, HH:MM AM/PM if available, else null)
- subtotal (number, amount before tax)
- tax (number, tax amount, or null)
- total (number, total amount paid. If tax is null, use subtotal as total)
- payment_method (string, e.g., "Visa", "Cash", "Shell Card", or null)
- category (string, MUST be one of: FOOD, TRANSPORTATION, HOUSING, HEALTHCARE, ENTERTAINMENT, SHOPPING, EDUCATION, PERSONAL_CARE, TRAVEL, INSURANCE, OTHER)

Rules:
- If you see "Sale $X", "Amount $X", or "Total $X", that is the total amount.
- Gas station / fuel / car repair = TRANSPORTATION
- Restaurant / cafe / groceries = FOOD
- Hotel / flight / rental = TRAVEL
- Insurance / AAA = INSURANCE
- Medical / pharmacy = HEALTHCARE
- Rent / utilities = HOUSING
- Shopping (clothes, electronics) = SHOPPING
- Gym / salon = PERSONAL_CARE
- Movies / concerts = ENTERTAINMENT
- Tuition / books = EDUCATION

Return ONLY the JSON, no extra text.

Description:
{raw_description}
    """

    text_response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": extraction_prompt}],
        temperature=0.1,
        max_tokens=300,
    )
    llm_output = text_response.choices[0].message.content

    # Parse JSON from response (handles markdown)
    try:
        # Try to extract JSON block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', llm_output, re.IGNORECASE)
        if json_match:
            llm_output = json_match.group(1)
        # Find first { ... }
        json_match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if json_match:
            llm_output = json_match.group(0)
        structured = json.loads(llm_output)
    except Exception:
        structured = {}

    # Ensure all expected keys exist
    defaults = {
        'merchant': None,
        'date': None,
        'time': None,
        'subtotal': None,
        'tax': None,
        'total': None,
        'payment_method': None,
        'category': 'OTHER'
    }
    for key, default in defaults.items():
        if key not in structured or structured[key] is None:
            structured[key] = default

    # Keep the raw description for later use (stored server‑side only)
    structured['raw_description'] = raw_description

    return structured