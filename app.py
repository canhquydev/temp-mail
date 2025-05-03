from flask import Flask, request, jsonify, session, send_from_directory
 from google.oauth2.credentials import Credentials
 from googleapiclient.discovery import build
 import base64
 import os
 import random
 import string
 import json
 
 app = Flask(__name__)
 app.secret_key = 'your_secret_key_here'
 
 # Gmail API Scope
 SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
 
 def gmail_authenticate():
     creds = None
     credentials_data = os.environ.get('GOOGLE_CREDENTIALS')
     token_data = os.environ.get('GOOGLE_TOKEN')
 
     if credentials_data and token_data:
         creds = Credentials.from_authorized_user_info(json.loads(token_data), scopes=SCOPES)
     else:
         raise Exception("Missing GOOGLE_CREDENTIALS or GOOGLE_TOKEN environment variables.")
 
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
     def fetch_by_label(label):
         query = f"to:{target_email}"
         results = gmail_service.users().messages().list(
         result = gmail_service.users().messages().list(
             userId='me',
             q=query,
             labelIds=["INBOX", "SPAM"],  # 👈 QUAN TRỌNG: thêm label SPAM vào đây
             labelIds=[label],
             maxResults=10
         ).execute()
         messages = results.get('messages', [])
         return result.get('messages', [])
 
         for msg in messages:
     try:
         # lấy thư ở INBOX
         inbox_messages = fetch_by_label("INBOX")
         # lấy thư ở SPAM
         spam_messages = fetch_by_label("SPAM")
         
         all_messages = (inbox_messages or []) + (spam_messages or [])
 
         for msg in all_messages:
             msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id']).execute()
             payload = msg_detail.get('payload', {})
             headers = payload.get("headers", [])
             parts = payload.get('parts', [])
             body = ""
 
             if parts:
                 for part in parts:
                     if part['mimeType'] == 'text/html' and 'data' in part['body']:
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
