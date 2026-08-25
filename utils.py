# utils.py – with defensive directory creation

import os
import json
import uuid
import hashlib
import re
from datetime import datetime, timedelta
import portalocker

# ---------- Constants ----------
TEMP_FOLDER = 'results/temp'
DB_FILE = 'receipts_db.json'

# Ensure temp folder exists at module load
os.makedirs(TEMP_FOLDER, exist_ok=True)

# ================================================================
# SESSION / TEMP DATA FUNCTIONS
# ================================================================

def generate_token():
    return str(uuid.uuid4())

def save_temp_data(token, data):
    """Store extracted data in a temp JSON file with expiry (30 min)."""
    # Ensure directory exists
    os.makedirs(TEMP_FOLDER, exist_ok=True)   # <-- FIX
    data['expires_at'] = (datetime.now() + timedelta(minutes=30)).isoformat()
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_temp_data(token):
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    expiry = datetime.fromisoformat(data['expires_at'])
    if datetime.now() > expiry:
        os.remove(path)
        return None
    return data

def delete_temp_data(token):
    path = os.path.join(TEMP_FOLDER, f'{token}.json')
    if os.path.exists(path):
        os.remove(path)

def validate_token(token):
    return load_temp_data(token) is not None

# ================================================================
# DATE NORMALIZATION
# ================================================================

def normalize_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = [
        '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
        '%b %d, %Y', '%B %d, %Y', '%d-%b-%Y',
        '%Y/%m/%d', '%m-%d-%Y', '%d.%m.%Y',
        '%b. %d, %Y', '%d %b %Y'
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str

# ================================================================
# SUBMISSION ID
# ================================================================

def get_submission_id(record):
    date = record.get('date', '')
    merchant = record.get('merchant', '')
    total = record.get('total', '')
    raw = f"{date}_{merchant}_{total}".lower().strip()
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

# ================================================================
# SINGLE JSON DATABASE
# ================================================================

def load_all_records():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_record(record):
    # Ensure the directory for DB_FILE exists (it's root, but just in case)
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with open(DB_FILE, 'a+', encoding='utf-8') as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        f.seek(0)
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = []
        submission_id = record.get('submission_id')
        if any(r.get('submission_id') == submission_id for r in data):
            raise ValueError("Duplicate record rejected: submission_id already exists.")
        data.append(record)
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_duplicate_record(submission_id):
    records = load_all_records()
    return any(r.get('submission_id') == submission_id for r in records)

# ================================================================
# CLEANUP
# ================================================================

def cleanup_expired_temp_files():
    now = datetime.now()
    for fname in os.listdir(TEMP_FOLDER):
        if fname.endswith('.json'):
            path = os.path.join(TEMP_FOLDER, fname)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                expiry = datetime.fromisoformat(data.get('expires_at', now.isoformat()))
                if now > expiry:
                    os.remove(path)
            except (json.JSONDecodeError, KeyError, OSError):
                os.remove(path)