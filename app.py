from flask import Flask, request, jsonify, session, send_from_directory
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import base64
import email
import os
import random
import string

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Gmail API Scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

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

    try:
        query = f"to:{target_email}"
        results = gmail_service.users().messages().list(userId='me', q=query, maxResults=10).execute()
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

            subject = ""
            sender = ""
            date = ""
            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value']
                if header['name'] == 'Date':
                    date = header['value']

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