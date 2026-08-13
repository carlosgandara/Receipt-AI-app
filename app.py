import os
import json
import csv
import glob
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from ai_service import process_image
from utils import (
    generate_token, validate_token, mark_processed, is_duplicate,
    normalize_date, save_temp_data, load_temp_data, delete_temp_data,
    get_submission_id
)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configuration
UPLOAD_FOLDER = 'uploads'
IMAGE_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs('results/temp', exist_ok=True)
os.makedirs('results_clean', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------------
# HOME
# ------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# ------------------------------
# UPLOAD
# ------------------------------
@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['image']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    if not allowed_file(file.filename):
        flash('File type not allowed. Please use PNG, JPG, JPEG, or GIF.')
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Permanent image copy
    base_name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    new_filename = f"{base_name}_{timestamp}{ext}"
    permanent_path = os.path.join(IMAGE_FOLDER, new_filename)
    with open(filepath, 'rb') as src:
        with open(permanent_path, 'wb') as dst:
            dst.write(src.read())

    try:
        with open(filepath, 'rb') as f:
            image_bytes = f.read()
        extracted = process_image(image_bytes, filename)
        extracted['image_path'] = permanent_path
    except Exception as e:
        flash(f'AI processing failed: {e}')
        return redirect(url_for('index'))
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    if extracted.get('date'):
        extracted['date'] = normalize_date(extracted['date'])

    token = generate_token()
    temp_data = {
        'token': token,
        'extracted': extracted,
        'image_name': filename,
        'image_path': permanent_path,
        'created_at': datetime.now().isoformat()
    }
    save_temp_data(token, temp_data)

    return render_template('review.html', token=token, data=extracted)

# ------------------------------
# CONFIRM
# ------------------------------
@app.route('/confirm', methods=['POST'])
def confirm():
    token = request.form.get('token')
    if not token or not validate_token(token):
        flash('Your session has expired (30 minutes). Please upload the image again.')
        return redirect(url_for('index'))

    temp_data = load_temp_data(token)
    if not temp_data:
        flash('Session data not found. Please re-upload.')
        return redirect(url_for('index'))

    extracted = temp_data['extracted']

    merchant = request.form.get('merchant', '').strip()
    date = request.form.get('date', '').strip()
    time = request.form.get('time', '').strip()
    subtotal_str = request.form.get('subtotal', '').strip()
    tax_str = request.form.get('tax', '').strip()
    total_str = request.form.get('total', '').strip()
    payment_method = request.form.get('payment_method', '').strip()
    category = request.form.get('category', '').strip()

    if not total_str:
        flash('Total amount is required.')
        return render_template('review.html', token=token, data=extracted)

    try:
        subtotal = float(subtotal_str) if subtotal_str else None
        tax = float(tax_str) if tax_str else None
        total = float(total_str)
    except ValueError:
        flash('Amounts must be numeric (e.g., 19.99).')
        return render_template('review.html', token=token, data=extracted)

    submission_id = get_submission_id({'date': date, 'merchant': merchant, 'total': total})
    if is_duplicate(submission_id):
        flash('⚠️ This receipt appears to be already saved. Duplicate rejected.')
        delete_temp_data(token)
        return redirect(url_for('index'))

    valid_categories = ['FOOD','TRANSPORTATION','HOUSING','HEALTHCARE','ENTERTAINMENT','SHOPPING','EDUCATION','PERSONAL_CARE','TRAVEL','INSURANCE','OTHER']
    if category not in valid_categories:
        category = 'OTHER'

    cleaned = {
        'timestamp': datetime.now().isoformat(),
        'image_name': temp_data['image_name'],
        'image_path': temp_data['image_path'],
        'merchant': merchant or None,
        'date': date or None,
        'time': time or None,
        'subtotal': subtotal,
        'tax': tax,
        'total': total,
        'payment_method': payment_method or None,
        'category': category,
        'raw_description': extracted.get('raw_description', ''),
        'processed_at': datetime.now().isoformat()
    }

    # CSV
    csv_file = 'expenses_full.csv'
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        fieldnames = ['timestamp','image_name','image_path','merchant','date','time','subtotal','tax','total','payment_method','category','raw_description','processed_at']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(cleaned)

    # JSON
    base_name = os.path.splitext(temp_data['image_name'])[0]
    json_filename = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_clean.json"
    json_path = os.path.join('results_clean', json_filename)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    mark_processed(submission_id)
    delete_temp_data(token)

    return render_template('success.html', record=cleaned)

# ------------------------------
# DASHBOARD
# ------------------------------
@app.route('/dashboard')
def dashboard():
    json_files = glob.glob('results_clean/*_clean.json')
    records = []
    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                records.append(json.load(f))
        except:
            continue

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    merchant = request.args.get('merchant')

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
    if merchant:
        filtered = [r for r in filtered if merchant.lower() in (r.get('merchant') or '').lower()]

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

    merchants = sorted(set(r.get('merchant') for r in records if r.get('merchant')))

    categories = list(cat_totals.keys())
    cat_values = [cat_totals[c] for c in categories]
    dates = [item[0] for item in sorted_weekly]
    weekly_totals = [item[1] for item in sorted_weekly]

    total_receipts = len(filtered)
    total_spent = sum(r.get('total', 0) for r in filtered)
    avg_spent = total_spent / total_receipts if total_receipts else 0
    max_receipt = max(filtered, key=lambda x: x.get('total', 0)) if filtered else None
    min_receipt = min(filtered, key=lambda x: x.get('total', 0)) if filtered else None

    chart_data_json = json.dumps({
        'categories': categories,
        'cat_values': cat_values,
        'dates': dates,
        'weekly_totals': weekly_totals
    })

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
                           selected_merchant=merchant or '',
                           start_date=start_date or '',
                           end_date=end_date or '')

# ------------------------------
# EXPORT
# ------------------------------
@app.route('/export')
def export_json():
    json_files = glob.glob('results_clean/*_clean.json')
    records = []
    for fpath in json_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                records.append(json.load(f))
        except:
            continue

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    merchant = request.args.get('merchant')

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
    if merchant:
        filtered = [r for r in filtered if merchant.lower() in (r.get('merchant') or '').lower()]

    return jsonify(filtered)

# ------------------------------
# SERVE IMAGES (FIXES 404)
# ------------------------------
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

# ------------------------------
# MAIN
# ------------------------------
if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(debug=False, port=port)