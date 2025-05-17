from flask import Flask, request, jsonify, session, send_from_directory
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import base64
import os
import random
import string
import json
import requests
import secrets
import psycopg2
import urllib.parse
import base64
from psycopg2.extras import RealDictCursor
from functools import wraps
import re
from flask import render_template
PACKAGE_PATTERN = re.compile(r'subs:com\\.google\\.android\\.apps\\.subscriptions\\.red:g1\\.(.*?)\\\"')
CODE_PATTERN = re.compile(r'\\[(?:null,){5}\\[\\\"(.*?)\\\"\\]\\]')
app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def send_telegram_alert(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"🚨 ALERT from TempMail:\n{message}"
            }, timeout=5)
        except Exception as ex:
            print("⚠ Không gửi được Telegram:", ex)
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM api_keys WHERE key=%s", (token,))
        valid = cur.fetchone()
        cur.close()
        conn.close()

        if not valid:
            return jsonify({"error": "API key không hợp lệ"}), 403
        return f(*args, **kwargs)
    return decorated
def gmail_authenticate():
    try:
        credentials_data = os.environ.get('GOOGLE_CREDENTIALS')
        refresh_token = os.environ.get('GOOGLE_TOKEN')

        if not credentials_data or not refresh_token:
            msg = "❌ Thiếu GOOGLE_CREDENTIALS hoặc GOOGLE_TOKEN"
            print(msg)
            send_telegram_alert(msg)
            return None

        creds_dict = json.loads(credentials_data)
        creds_dict['refresh_token'] = refresh_token

        creds = Credentials(
            token=None,
            refresh_token=creds_dict['refresh_token'],
            token_uri=creds_dict['token_uri'],
            client_id=creds_dict['client_id'],
            client_secret=creds_dict['client_secret'],
            scopes=SCOPES
        )

        creds.refresh(Request())  # Luôn tạo access_token mới
        service = build('gmail', 'v1', credentials=creds)
        service.users().labels().list(userId='me').execute()

        print("✅ Gmail API hoạt động với access_token mới")
        return service

    except Exception as e:
        msg = f"❌ Gmail API lỗi: {e}"
        print(msg)
        send_telegram_alert(msg)
        return None
@app.route('/<path:email>')
def serve_email_with_param(email):
    if '@' not in email:
        email += '@quy.edu.pl'  # nếu chỉ truyền tên thì thêm domain vào

    return send_from_directory('.', 'index.html')

@app.route('/create_email', methods=['POST'])
def create_email():
    new_username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    session['email'] = new_username + "@quy.edu.pl"
    return jsonify({"email": session['email']})

@app.route('/list_emails', methods=['GET'])
def list_emails():
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Gmail API không sẵn sàng (token lỗi hoặc chưa khởi tạo)"})

    target_email = request.args.get('email', "").lower()
    mails = []

    def fetch_by_label(label):
        query = f"to:{target_email}"
        result = service.users().messages().list(
            userId='me',
            q=query,
            labelIds=[label],
            maxResults=10
        ).execute()
        return result.get('messages', [])

    try:
        inbox_messages = fetch_by_label("INBOX")
        spam_messages = fetch_by_label("SPAM")
        all_messages = (inbox_messages or []) + (spam_messages or [])

        for msg in all_messages:
            msg_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_detail.get('payload', {})
            headers = payload.get("headers", [])
            parts = payload.get('parts', [])
            body = ""

            if parts:
                for part in parts:
                    if part['mimeType'] == 'text/html' and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
            else:
                if 'body' in payload and 'data' in payload['body']:
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            mails.append({
                "id": msg['id'],
                "subject": subject,
                "from": sender,
                "date": date,
                "body": body
            })

        return jsonify(mails)

    except Exception as e:
        print(f"❌ Error fetching emails: {e}")
        return jsonify([])

@app.route('/')
def serve_index():
    return render_template('index.html')
@app.route('/api/create', methods=['POST'])
def api_create_email():
    data = request.json or {}
    custom = data.get("username")
    if custom:
        email = f"{custom.lower()}@quy.edu.pl"
    else:
        email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@quy.edu.pl"
    return jsonify({"email": email})

@app.route('/api/inbox', methods=['GET'])
@require_api_key
def api_list_emails():
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Gmail API lỗi"})

    target_email = request.args.get('email', "").lower()
    if not target_email:
        return jsonify({"error": "Thiếu email"})

    def fetch_by_label(label):
        query = f"to:{target_email}"
        result = service.users().messages().list(
            userId='me', q=query, labelIds=[label], maxResults=10
        ).execute()
        return result.get('messages', [])

    try:
        inbox = fetch_by_label("INBOX")
        spam = fetch_by_label("SPAM")
        all_msgs = (inbox or []) + (spam or [])

        mails = []
        for msg in all_msgs:
            detail = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = detail.get("payload", {})
            headers = payload.get("headers", [])
            snippet = detail.get("snippet", "")
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            mails.append({
                "id": msg['id'],
                "subject": subject,
                "from": sender,
                "date": date,
                "snippet": snippet
            })

        return jsonify({"emails": mails})

    except Exception as e:
        return jsonify({"error": str(e)})
@app.route('/api/email/<msg_id>', methods=['GET'])
def api_read_email(msg_id):
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Gmail API lỗi"})

    email = request.args.get('email', '').lower()
    if not email:
        return jsonify({"error": "Thiếu email"})

    try:
        msg_detail = service.users().messages().get(userId='me', id=msg_id).execute()
        payload = msg_detail.get("payload", {})
        headers = payload.get("headers", [])
        parts = payload.get('parts', [])
        body = ""

        if parts:
            for part in parts:
                if part['mimeType'] == 'text/html' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

        return jsonify({
            "subject": subject,
            "from": sender,
            "date": date,
            "body": body
        })

    except Exception as e:
        return jsonify({"error": str(e)})
API_KEY_FILE = "api_keys.json"
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            user_email TEXT REFERENCES users(email),
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '').strip()
    if not email or not password:
        return jsonify({"error": "Email và mật khẩu là bắt buộc."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        return jsonify({"error": "Tài khoản đã tồn tại."}), 400

    cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (email, generate_password_hash(password)))
    conn.commit()
    cur.close()
    conn.close()

    session['user'] = email
    return jsonify({"message": "Đăng ký thành công.", "email": email})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '').strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Sai email hoặc mật khẩu."}), 401

    session['user'] = email
    return jsonify({"message": "Đăng nhập thành công.", "email": email})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"message": "Đã đăng xuất."})


@app.route('/api/me', methods=['GET'])
def get_current_user():
    if 'user' in session:
        return jsonify({"email": session['user']})
    return jsonify({"error": "Chưa đăng nhập."}), 401


@app.route('/api/create_api_key', methods=['POST'])
def create_api_key():
    if 'user' not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    user_email = session['user']
    conn = get_db()
    cur = conn.cursor()

    # Kiểm tra user đã có key chưa
    cur.execute("SELECT key FROM api_keys WHERE user_email = %s", (user_email,))
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Bạn chỉ được tạo 1 API key. Vui lòng xoá key cũ trước."}), 400

    new_key = secrets.token_hex(16)
    created = datetime.utcnow()
    cur.execute("INSERT INTO api_keys (key, user_email, created) VALUES (%s, %s, %s)",
                (new_key, user_email, created))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"key": new_key})



@app.route('/api/my_keys', methods=['GET'])
def list_api_keys():
    if 'user' not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    user_email = session['user']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT key, created FROM api_keys WHERE user_email=%s", (user_email,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(rows)


@app.route('/api/delete_key', methods=['POST'])
def delete_api_key():
    if 'user' not in session:
        return jsonify({"error": "Chưa đăng nhập"}), 401

    data = request.json or {}
    key_to_delete = data.get("key")
    if not key_to_delete:
        return jsonify({"error": "Thiếu key"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM api_keys WHERE key=%s AND user_email=%s", (key_to_delete, session['user']))
    if cur.rowcount == 0:
        return jsonify({"error": "Không tìm thấy key hoặc không có quyền xoá"}), 403
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})
@app.route('/congcu')
def change_package():
    return render_template('congcu.html')

@app.route("/api/congcu", methods=["POST"])
def congcu():
    data = request.json or {}
    original = data.get("link")
    new_pkg = data.get("newPkg")
    new_code = data.get("newCode")

    if not original or not new_pkg or not new_code:
        return jsonify({"error": "Thiếu dữ liệu."}), 400

    try:
        updated = update_link(original, new_pkg, new_code)
        return jsonify({"new_link": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def update_link(original_link, new_pkg, new_code):
    try:
        decoded = urllib.parse.unquote(original_link)
        matches = re.findall(r'subs:com\.google\.android\.apps\.subscriptions\.red:g1\.[^"]+', decoded)
        if not matches:
            return original_link

        updated = original_link
        for m in matches:
            new_m = re.sub(r'g1\.[^"]+', f'g1.{new_pkg}', m)
            updated = updated.replace(urllib.parse.quote(m), urllib.parse.quote(new_m), 1)

        updated = re.sub(r'%2C\d+%2C', f'%2C{new_code}%2C', updated, count=1)
        return updated
    except Exception as ex:
        print("❌ update_link() lỗi:", ex)
        raise


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
