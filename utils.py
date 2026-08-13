import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
import re

# Temporary storage folder
TEMP_FOLDER = 'results/temp'
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Processed submissions set (to avoid duplicates)
PROCESSED_FILE = 'results/processed_ids.txt'

def generate_token():
    """Generate a unique token for temporary storage."""
    return str(uuid.uuid4())

def save_temp_data(token, data):
    """Store extracted data in a temp JSON file with expiry (30 min)."""
    data['expires_at'] = (datetime.now() + timedelta(minutes=30)).isoformat()
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_temp_data(token):
    """Load temp data if not expired."""
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Check expiry
    expiry = datetime.fromisoformat(data['expires_at'])
    if datetime.now() > expiry:
        os.remove(path)
        return None
    return data

def delete_temp_data(token):
    """Remove the temp file."""
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    if os.path.exists(path):
        os.remove(path)

def validate_token(token):
    """Check if token exists and is not expired."""
    return load_temp_data(token) is not None

def normalize_date(date_str):
    """
    Try to convert various date formats to YYYY-MM-DD.
    If all fail, return the original string (user can edit).
    """
    if not date_str:
        return None
    date_str = date_str.strip()
    
    # List of possible formats (order matters)
    formats = [
        '%Y-%m-%d',           # 2026-08-12
        '%m/%d/%Y',           # 08/12/2026
        '%d/%m/%Y',           # 12/08/2026
        '%b %d, %Y',          # Aug 12, 2026
        '%B %d, %Y',          # August 12, 2026
        '%d-%b-%Y',           # 12-Aug-2026
        '%Y/%m/%d',           # 2026/08/12
        '%m-%d-%Y',           # 08-12-2026
        '%d.%m.%Y',           # 12.08.2026
        '%b. %d, %Y',         # Aug. 12, 2026
        '%d %b %Y'            # 12 Aug 2026
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    # If all fail, return original (user can fix manually)
    return date_str

def get_submission_id(record):
    """
    Generate a unique ID for a receipt based on date, merchant, total.
    This is used to prevent duplicate submissions.
    """
    date = record.get('date', '')
    merchant = record.get('merchant', '')
    total = record.get('total', '')
    # Create a hash to keep IDs short and consistent
    raw = f"{date}_{merchant}_{total}".lower().strip()
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def is_duplicate(submission_id):
    """Check if this submission ID has been already saved."""
    if not os.path.exists(PROCESSED_FILE):
        return False
    with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
        processed = set(line.strip() for line in f)
    return submission_id in processed

def mark_processed(submission_id):
    """Record a submission ID to prevent duplicates."""
    with open(PROCESSED_FILE, 'a', encoding='utf-8') as f:
        f.write(submission_id + '\n')