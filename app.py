from flask import Flask, request, jsonify, session, send_from_directory
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import json
import base64
import random
import string

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def gmail_authenticate():
    credentials_data = os.environ.get('GOOGLE_CREDENTIALS')
    token_data = os.environ.get('GOOGLE_TOKEN')

    if not credentials_data or not token_data:
        raise Exception("Missing GOOGLE_CREDENTIALS or GOOGLE_TOKEN")

    creds = Credentials.from_authorized_user_info(json.loads(token_data), scopes=SCOPES)
    service = build('gmail', 'v1', credentials=creds)
    return service

gmail_service = gmail_authenticate()

@app.route('/create_email', methods=['POST'])
def create_email():
    new_username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    session['email'] = new_username + "@canhquy.pw"
    return jsonify({"email": session['email']})

@app.route('/list_emails', methods=['GET'])
def list_emails():
    target_email = request.args.get('email', "").lower()
    mails = []

    if not target_email:
        return jsonify([])

    try:
        query = f"to:{target_email}"
        results = gmail_service.users().messages().list(userId='me', q=query, maxResults=5).execute()
        messages = results.get('messages', [])

        for msg in messages:
            msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_detail.get('payload', {})
            headers = payload.get("headers", [])
            parts = payload.get('parts', [])
            body = ""

            if parts:
                for part in parts:
                    if part['mimeType'] == 'text/html':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode()

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
        print(f"Error fetching emails: {e}")
        return jsonify([])

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
