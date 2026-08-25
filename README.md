# 📄 Receipt AI

**Stop manual data entry. Turn receipt photos into structured expense data – with AI, a human review step, and a live dashboard.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚀 What it does

Upload a picture of any receipt. Receipt AI uses a **vision model** to read the text and a **language model** to extract:

- Merchant name  
- Date & time  
- Subtotal, tax, total  
- Payment method  
- Expense category (Food, Transport, etc.)

You get an **editable form** to correct anything the AI missed, then **one click** saves the record to CSV and JSON – with the original image stored permanently.

---

## ✨ Features

| Feature | Description |
| :--- | :--- |
| 📸 **Upload** | Supports PNG, JPG, JPEG, GIF – drag and drop or select. |
| 🤖 **AI extraction** | Powered by Novita AI (Vision + DeepSeek V3.2) – reliable and cheap. |
| ✏️ **Human review** | Edit any field before saving – no more silent AI errors. |
| 📊 **Dashboard** | Filter by date, category, merchant; view charts and table; export filtered data as JSON. |
| 💾 **Permanent storage** | Receipt images kept forever in `images/`; data stored as both CSV and individual JSON files. |
| 🔒 **Duplicate prevention** | Automatically rejects identical receipts. |
| 🧹 **Session expiry** | Draft data self‑destructs after 30 minutes. |

---

## 🖼️ Screenshots

### 1. Upload & AI extraction
<img width="600" alt="Upload page" src="https://github.com/user-attachments/assets/08f6b214-8f25-4241-bf45-f5041edde060" />

### 2. Review & edit form
<img width="600" alt="Review form" src="https://github.com/user-attachments/assets/42edc840-55c7-453b-b935-7552d67927e6" />

### 3. Dashboard – spending by category & weekly trend
<img width="600" alt="Dashboard charts" src="https://github.com/user-attachments/assets/73023dd8-cc57-4299-826e-de5103a9c391" />

### 4. Dashboard – filterable table with thumbnails
<img width="600" alt="Dashboard table" src="https://github.com/user-attachments/assets/9a196e00-46a0-4e5c-a2c6-f79868fae75a" />

### 5. Export filtered data as JSON
<img width="600" alt="Export" src="https://github.com/user-attachments/assets/cf5dc4cd-8b86-473f-9706-87a5ba180646" />

> 💡 **From ugly receipts to an organised dashboard – in seconds.**

---

## 🛠️ Tech Stack

| Component | Technology |
| :--- | :--- |
| Backend | Flask (Python 3.10+) |
| AI | Novita AI (OpenAI‑compatible) |
| Vision model | `qwen/qwen3-vl-235b-a22b-instruct` |
| Text model | `deepseek/deepseek-v3.2` |
| Charts | Chart.js |
| Data storage | CSV + JSON |
| Image storage | Local filesystem (`images/`) |

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.10 or higher
- A [Novita AI](https://novita.ai) account (get an API key)
- Git (optional, for cloning)

### 1. Clone the repository
```bash
git clone https://github.com/carlosgandara/Receipt-AI-app.git
cd Receipt-AI-app
