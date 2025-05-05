from flask import Flask, request, jsonify, session, send_from_directory
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64
import os
import random
import string
import json
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Gmail API Scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Telegram cảnh báo lỗi
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_alert(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 ALERT from TempMail:\n{message}"},
                timeout=5
            )
        except Exception as ex:
            print("⚠ Không gửi được Telegram:", ex)

def gmail_authenticate():
    try:
        credentials_data = os.environ.get('GOOGLE_CREDENTIALS')
        token_data = os.environ.get('GOOGLE_TOKEN')

        if not credentials_data or not token_data:
            msg = "❌ Thiếu biến môi trường: GOOGLE_CREDENTIALS hoặc GOOGLE_TOKEN"
            print(msg)
            send_telegram_alert(msg)
            return None

        creds = Credentials.from_authorized_user_info(json.loads(token_data), scopes=SCOPES)
        service = build('gmail', 'v1', credentials=creds)
        service.users().labels().list(userId='me').execute()  # kiểm tra token
        return service
    except Exception as e:
        msg = f"❌ Gmail API lỗi: {e}"
        print(msg)
        send_telegram_alert(msg)
        return None

# Bộ nhớ tạm
message_cache = {}

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

    after_timestamp = int((datetime.utcnow() - timedelta(minutes=15)).timestamp())
    query = f"to:{target_email} after:{after_timestamp}"

    def fetch_by_label(label):
        try:
            result = service.users().messages().list(
                userId='me',
                q=query,
                labelIds=[label],
                maxResults=10
            ).execute()
            return result.get('messages', [])
        except:
            return []

    try:
        inbox_messages = fetch_by_label("INBOX")
        spam_messages = fetch_by_label("SPAM")
        all_messages = (inbox_messages or []) + (spam_messages or [])

        for msg in all_messages:
            msg_id = msg['id']
            if msg_id in message_cache:
                msg_detail = message_cache[msg_id]
            else:
                msg_detail = service.users().messages().get(userId='me', id=msg_id).execute()
                message_cache[msg_id] = msg_detail

            payload = msg_detail.get('payload', {})
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

            mails.append({
                "id": msg_id,
                "subject": subject,
                "from": sender,
                "date": date,
                "body": body
            })
        return jsonify(mails)
    except Exception as e:
        print(f"Lỗi lấy email: {e}")
        return jsonify([])

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
