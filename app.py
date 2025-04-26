from flask import Flask, request, jsonify, session, send_from_directory
import imaplib
import email
from email.header import decode_header
import random
import string
import os
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

IMAP_SERVER = 'imap.gmail.com'
EMAIL_ACCOUNT = 'nickcamitem@gmail.com'
APP_PASSWORD = 'pkoynswpaiqgsnzs'
DOMAIN = "canhquy.pw"

def parse_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/html" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode(errors="ignore")
                return body  # Giữ nguyên HTML
            if content_type == "text/plain" and "attachment" not in content_disposition and not body:
                body = "<pre>" + part.get_payload(decode=True).decode(errors="ignore") + "</pre>"
    else:
        content_type = msg.get_content_type()
        if content_type == "text/html":
            body = msg.get_payload(decode=True).decode(errors="ignore")
        elif content_type == "text/plain":
            body = "<pre>" + msg.get_payload(decode=True).decode(errors="ignore") + "</pre>"
    return body

def fetch_all_emails():
    mails = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)

        mail.select("INBOX")
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return []

        mail_ids = messages[0].split()[-5:]  # Chỉ lấy 5 mail mới nhất

        for num in reversed(mail_ids):
            status, data = mail.fetch(num, '(RFC822)')
            if status != "OK":
                continue
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    subject, encoding = decode_header(msg.get("Subject"))[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or 'utf-8', errors='ignore')
                    from_ = msg.get("From", "(No From)")
                    date_ = msg.get("Date", "(No Date)")
                    body = parse_email_body(msg)

                    mails.append({
                        "id": num.decode(),
                        "subject": subject,
                        "from": from_,
                        "date": date_,
                        "body": body
                    })
        mail.logout()
        return mails
    except Exception as e:
        print("Error fetching emails:", e)
        return []

@app.route('/create_email', methods=['POST'])
def create_email():
    new_email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@" + DOMAIN
    session['email'] = new_email
    return jsonify({"email": new_email})

@app.route('/list_emails', methods=['GET'])
def list_emails():
    mails = fetch_all_emails()
    return jsonify(mails)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)