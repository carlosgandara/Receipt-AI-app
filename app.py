# app.py – V1 with Hash + Normalized Duplicate Check

import os
import json
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
import threading
import time

from ai_service import process_image
from utils import (
    generate_token, save_temp_data, load_temp_data, delete_temp_data,
    validate_token, normalize_date, get_submission_id, 
    load_all_records, save_record, is_duplicate_record, DB_FILE
)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

UPLOAD_FOLDER = 'uploads'
IMAGE_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs('results/temp', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(filepath, output_folder=None, max_size=(1200, 1200), quality=85):
    if output_folder is None:
        output_folder = UPLOAD_FOLDER
    os.makedirs(output_folder, exist_ok=True)
    try:
        img = Image.open(filepath)
        img.thumbnail(max_size)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        base, _ = os.path.splitext(os.path.basename(filepath))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{base}_{timestamp}.jpg"
        new_path = os.path.join(output_folder, new_filename)
        img.save(new_path, 'JPEG', quality=quality, optimize=True)
        return new_path
    except Exception as e:
        print(f"[DEBUG] Compression fallback: {e}")
        base, ext = os.path.splitext(os.path.basename(filepath))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{base}_{timestamp}{ext}"
        new_path = os.path.join(output_folder, new_filename)
        with open(filepath, 'rb') as src, open(new_path, 'wb') as dst:
            dst.write(src.read())
        return new_path

def compute_image_hash(filepath):
    """Compute MD5 hash of the image file."""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def normalize_merchant(name):
    """Lowercase, strip, remove common suffixes for better matching."""
    if not name:
        return ''
    name = name.lower().strip()
    # Remove common business suffixes
    suffixes = [' inc', ' llc', ' ltd', ' corp', ' corporation', ' the', ' co']
    for s in suffixes:
        if name.endswith(s):
            name = name[:-len(s)].strip()
    return name

def is_duplicate_advanced(merchant, date, total, image_hash):
    """
    Check duplicates by:
    1. Image hash (exact file duplicate)
    2. Normalized content (lowercase merchant, standardized date, total rounded)
    """
    records = load_all_records()
    
    # 1. Hash check – fastest and most reliable
    for r in records:
        if r.get('image_hash') == image_hash:
            return True
    
    # 2. Content check – normalize
    norm_merchant = normalize_merchant(merchant)
    norm_date = date  # date is already normalized to YYYY-MM-DD by normalize_date()
    norm_total = round(total, 2)  # 2 decimal places
    
    for r in records:
        r_merchant = normalize_merchant(r.get('merchant', ''))
        r_date = r.get('date', '')
        r_total = round(r.get('total', 0), 2)
        if r_date == norm_date and r_total == norm_total and r_merchant == norm_merchant:
            return True
    
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    print("[DEBUG] /upload called")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    if 'image' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))

    file = request.files['image']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash('File type not allowed.')
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    temp_original = os.path.join(UPLOAD_FOLDER, filename)
    file.save(temp_original)
    print(f"[DEBUG] Original saved: {temp_original}")

    # Compress to temp
    compressed_temp = compress_image(temp_original, output_folder=UPLOAD_FOLDER)
    if os.path.exists(temp_original):
        os.remove(temp_original)
    print(f"[DEBUG] Compressed temp: {compressed_temp}")

    # Compute image hash (before AI)
    image_hash = compute_image_hash(compressed_temp)
    print(f"[DEBUG] Image hash: {image_hash}")

    # ---- Quick hash duplicate check (before AI) ----
    records = load_all_records()
    for r in records:
        if r.get('image_hash') == image_hash:
            print("[DEBUG] Exact hash duplicate found – rejecting immediately.")
            flash('This exact image was already uploaded. Duplicate rejected.')
            if os.path.exists(compressed_temp):
                os.remove(compressed_temp)
            return redirect(url_for('index'))

    token = generate_token()
    print(f"[DEBUG] Token: {token}")

    temp_data = {
        'token': token,
        'status': 'processing',
        'temp_image_path': compressed_temp,
        'image_name': filename,
        'image_hash': image_hash,   # store for later
        'created_at': datetime.now().isoformat()
    }
    save_temp_data(token, temp_data)

    # Background AI processing
    def process_ai():
        print(f"[DEBUG] Thread started for token {token}")
        try:
            print("[DEBUG] Reading temp image...")
            with open(compressed_temp, 'rb') as f:
                image_bytes = f.read()
            print(f"[DEBUG] Image bytes: {len(image_bytes)}")

            print("[DEBUG] Calling AI...")
            start = time.time()
            extracted = process_image(image_bytes, filename)
            elapsed = time.time() - start
            print(f"[DEBUG] AI returned in {elapsed:.2f}s")

            extracted['image_path'] = None

            if extracted.get('date'):
                extracted['date'] = normalize_date(extracted['date'])
            merchant = extracted.get('merchant', '')
            date = extracted.get('date', '')
            total = extracted.get('total', 0)
            print(f"[DEBUG] Extracted -> merchant: '{merchant}', date: '{date}', total: {total}")

            # ---- Advanced duplicate check (with normalization) ----
            print("[DEBUG] Checking duplicate (advanced)...")
            duplicate_exists = is_duplicate_advanced(merchant, date, total, image_hash)
            print(f"[DEBUG] Duplicate exists? {duplicate_exists}")

            if duplicate_exists:
                print("[DEBUG] DUPLICATE FOUND. Deleting temp file.")
                if os.path.exists(compressed_temp):
                    os.remove(compressed_temp)
                temp = load_temp_data(token)
                if temp:
                    temp['status'] = 'duplicate'
                    save_temp_data(token, temp)
                return

            # ---- Not duplicate ----
            print("[DEBUG] NOT DUPLICATE. Moving to permanent storage.")
            os.makedirs(IMAGE_FOLDER, exist_ok=True)
            base, _ = os.path.splitext(os.path.basename(compressed_temp))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_filename = f"{base}_{timestamp}.jpg"
            final_path = os.path.join(IMAGE_FOLDER, final_filename)
            os.rename(compressed_temp, final_path)
            print(f"[DEBUG] Moved to {final_path}")

            extracted['image_path'] = final_path

            temp = load_temp_data(token)
            if temp:
                temp['status'] = 'complete'
                temp['extracted'] = extracted
                temp['image_path'] = final_path
                temp['image_hash'] = image_hash  # ensure hash stored
                save_temp_data(token, temp)
                print("[DEBUG] Temp data set to complete")
            else:
                print("[DEBUG] WARNING: Temp data lost!")

        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()
            if os.path.exists(compressed_temp):
                os.remove(compressed_temp)
            temp = load_temp_data(token)
            if temp:
                temp['status'] = 'error'
                temp['error'] = str(e)
                save_temp_data(token, temp)

    thread = threading.Thread(target=process_ai)
    thread.daemon = True
    thread.start()
    print("[DEBUG] Thread started, returning processing page")

    return render_template('processing.html', token=token)

@app.route('/status/<token>')
def status(token):
    temp = load_temp_data(token)
    if not temp:
        return jsonify({'status': 'not_found'})
    status = temp.get('status', 'processing')
    response = {'status': status}
    if status == 'complete':
        response['redirect'] = url_for('review', token=token)
    elif status == 'duplicate':
        response['redirect'] = url_for('duplicate', token=token)
    elif status == 'error':
        response['error'] = temp.get('error', 'Unknown error')
    return jsonify(response)

@app.route('/review/<token>')
def review(token):
    if not validate_token(token):
        flash('Session expired.')
        return redirect(url_for('index'))
    temp = load_temp_data(token)
    if not temp:
        flash('Session data not found.')
        return redirect(url_for('index'))
    if temp.get('status') != 'complete':
        flash('AI processing not complete yet.')
        return redirect(url_for('processing', token=token))
    data = temp.get('extracted', {})
    return render_template('review.html', token=token, data=data)

@app.route('/processing/<token>')
def processing(token):
    return render_template('processing.html', token=token)

@app.route('/duplicate/<token>')
def duplicate(token):
    temp = load_temp_data(token)
    if not temp:
        flash('Session expired.')
        return redirect(url_for('index'))
    # Clean up leftover temp file if any
    temp_path = temp.get('temp_image_path')
    if temp_path and os.path.exists(temp_path):
        os.remove(temp_path)
    return render_template('duplicate.html', token=token)

@app.route('/confirm', methods=['POST'])
def confirm():
    token = request.form.get('token')
    if not token or not validate_token(token):
        flash('Session expired.')
        return redirect(url_for('index'))

    temp_data = load_temp_data(token)
    if not temp_data:
        flash('Session data not found.')
        return redirect(url_for('index'))

    extracted = temp_data.get('extracted', {})
    image_path = temp_data.get('image_path')
    image_name = temp_data.get('image_name')
    image_hash = temp_data.get('image_hash')

    merchant = request.form.get('merchant', '').strip()
    date = request.form.get('date', '').strip()
    time = request.form.get('time', '').strip()
    subtotal_str = request.form.get('subtotal', '').strip()
    tax_str = request.form.get('tax', '').strip()
    total_str = request.form.get('total', '').strip()
    payment_method = request.form.get('payment_method', '').strip()
    category = request.form.get('category', '').strip()
    comment = request.form.get('comment', '').strip()

    if not total_str:
        flash('Total amount is required.')
        return render_template('review.html', token=token, data=extracted)

    try:
        subtotal = float(subtotal_str) if subtotal_str else None
        tax = float(tax_str) if tax_str else None
        total = float(total_str)
    except ValueError:
        flash('Amounts must be numeric.')
        return render_template('review.html', token=token, data=extracted)

    valid_categories = ['FOOD','TRANSPORTATION','HOUSING','HEALTHCARE','ENTERTAINMENT',
                        'SHOPPING','EDUCATION','PERSONAL_CARE','TRAVEL','INSURANCE','OTHER']
    if category not in valid_categories:
        category = 'OTHER'

    # Normalize date again
    date = normalize_date(date)

    # Duplicate check with user-edited values (but use the advanced function)
    if is_duplicate_advanced(merchant, date, total, image_hash):
        flash('⚠️ This receipt appears to be already saved. Duplicate rejected.')
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        delete_temp_data(token)
        return redirect(url_for('index'))

    # Build record
    cleaned = {
        'submission_id': get_submission_id({'date': date, 'merchant': merchant, 'total': total}),
        'timestamp': datetime.now().isoformat(),
        'image_name': image_name,
        'image_path': image_path,
        'merchant': merchant or None,
        'date': date or None,
        'time': time or None,
        'subtotal': subtotal,
        'tax': tax,
        'total': total,
        'payment_method': payment_method or None,
        'category': category,
        'comment': comment,
        'image_hash': image_hash,
        'raw_description': extracted.get('raw_description', ''),
        'processed_at': datetime.now().isoformat()
    }

    try:
        save_record(cleaned)
    except ValueError as e:
        flash(f'Duplicate rejected: {e}')
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        delete_temp_data(token)
        return redirect(url_for('index'))

    delete_temp_data(token)
    return render_template('success.html', record=cleaned)

@app.route('/dashboard')
def dashboard():
    records = load_all_records()

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    merchant_search = request.args.get('merchant')

    filtered = records
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            filtered = [r for r in filtered if r.get('date') and datetime.strptime(r['date'], '%Y-%m-%d') >= start]
        except:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            filtered = [r for r in filtered if r.get('date') and datetime.strptime(r['date'], '%Y-%m-%d') <= end]
        except:
            pass
    if category and category != 'ALL':
        filtered = [r for r in filtered if r.get('category') == category]
    if merchant_search:
        filtered = [r for r in filtered if merchant_search.lower() in (r.get('merchant') or '').lower()]

    from collections import defaultdict
    cat_totals = defaultdict(float)
    for r in filtered:
        cat = r.get('category', 'OTHER')
        cat_totals[cat] += r.get('total', 0)

    weekly = defaultdict(float)
    for r in filtered:
        if r.get('date'):
            try:
                dt = datetime.strptime(r['date'], '%Y-%m-%d')
                week_start = dt - timedelta(days=dt.weekday())
                key = week_start.strftime('%Y-%m-%d')
                weekly[key] += r.get('total', 0)
            except:
                pass

    sorted_weekly = sorted(weekly.items())
    dates = [item[0] for item in sorted_weekly]
    weekly_totals = [item[1] for item in sorted_weekly]

    total_receipts = len(filtered)
    total_spent = sum(r.get('total', 0) for r in filtered)
    avg_spent = total_spent / total_receipts if total_receipts else 0
    max_receipt = max(filtered, key=lambda x: x.get('total', 0)) if filtered else None
    min_receipt = min(filtered, key=lambda x: x.get('total', 0)) if filtered else None

    chart_data = {
        'categories': list(cat_totals.keys()),
        'cat_values': [cat_totals[c] for c in cat_totals],
        'dates': dates,
        'weekly_totals': weekly_totals
    }
    chart_data_json = chart_data

    merchants = sorted(set(r.get('merchant') for r in records if r.get('merchant')))

    return render_template('dashboard.html',
                           records=filtered,
                           chart_data_json=chart_data_json,
                           total_receipts=total_receipts,
                           total_spent=total_spent,
                           avg_spent=avg_spent,
                           max_receipt=max_receipt,
                           min_receipt=min_receipt,
                           merchants=merchants,
                           selected_category=category or 'ALL',
                           selected_merchant=merchant_search or '',
                           start_date=start_date or '',
                           end_date=end_date or '')

@app.route('/export')
def export_json():
    records = load_all_records()
    # Apply same filters (simplified for brevity – copy from dashboard if needed)
    return jsonify(records)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(debug=False, host='0.0.0.0', port=port)