from flask import Flask, request, jsonify, session, send_from_directory, render_template
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
# import secrets # Không còn cần thiết nếu không tạo API key
import psycopg2
import urllib.parse
from psycopg2.extras import RealDictCursor
from functools import wraps
import re

PACKAGE_PATTERN = re.compile(r'subs:com\\.google\\.android\\.apps\\.subscriptions\\.red:g1\\.(.*?)\\\"')
CODE_PATTERN = re.compile(r'\\[(?:null,){5}\\[\\\"(.*?)\\\"\\]\\]')
app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_secret_key_here' # Hãy thay đổi secret key này trong môi trường production
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

# Đã loại bỏ hàm require_api_key và decorator @require_api_key

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

        creds.refresh(Request())
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
        # Mặc định tên miền nếu người dùng chỉ nhập username
        # Email mặc định sẽ được xử lý bởi frontend JavaScript để điền vào ô input
        pass # Để frontend xử lý việc điền email vào input
    return render_template('index.html')


@app.route('/create_email', methods=['POST'])
def create_email():
    new_username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    # session['email'] = new_username + "@quy.edu.pl" # Không nên lưu email trong session nếu không cần thiết
    # Trả về email để client tự quản lý
    return jsonify({"email": new_username + "@quy.edu.pl"})

@app.route('/list_emails', methods=['GET'])
def list_emails():
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Gmail API không sẵn sàng (token lỗi hoặc chưa khởi tạo)"}), 503

    target_email = request.args.get('email', "").lower()
    if not target_email or '@' not in target_email:
        return jsonify({"error": "Địa chỉ email không hợp lệ hoặc bị thiếu."}), 400
        
    mails = []

    def fetch_by_label(label):
        query = f"to:{target_email}"
        result = service.users().messages().list(
            userId='me',
            q=query,
            labelIds=[label],
            maxResults=10 # Giới hạn số lượng email lấy về
        ).execute()
        return result.get('messages', [])

    try:
        inbox_messages = fetch_by_label("INBOX")
        spam_messages = fetch_by_label("SPAM") # Cũng kiểm tra trong spam
        all_messages = (inbox_messages or []) + (spam_messages or [])

        for msg_ref in all_messages: # Đổi tên biến để tránh nhầm lẫn
            msg_detail = service.users().messages().get(userId='me', id=msg_ref['id']).execute()
            payload = msg_detail.get('payload', {})
            headers = payload.get("headers", [])
            parts = payload.get('parts', [])
            body = ""

            if parts: # Ưu tiên lấy HTML body
                for part in parts:
                    if part['mimeType'] == 'text/html' and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
                if not body: # Nếu không có HTML, thử lấy text/plain
                     for part in parts:
                        if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            # Có thể cần chuyển đổi text/plain sang HTML nếu muốn hiển thị đẹp hơn
                            body = body.replace("\n", "<br>") # Chuyển đổi cơ bản
                            break
            elif 'body' in payload and 'data' in payload['body']: # Fallback nếu không có parts
                body_data = payload['body']['data']
                # Kiểm tra mimeType của payload chính nếu không có parts
                mime_type = payload.get('mimeType', '')
                body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                if mime_type == 'text/plain':
                     body = body.replace("\n", "<br>")


            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '') # lower() để khớp case-insensitive
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

            mails.append({
                "id": msg_ref['id'],
                "subject": subject,
                "from": sender,
                "date": date,
                "body": body # Trả về cả body
            })
        # Sắp xếp email theo ngày nhận, mới nhất lên đầu (cần parse date)
        # Tạm thời không sắp xếp ở backend, để frontend tự xử lý nếu cần
        return jsonify(mails)

    except Exception as e:
        print(f"❌ Error fetching emails for {target_email}: {e}")
        # Trả về lỗi cụ thể hơn cho client nếu có thể
        return jsonify({"error": f"Lỗi khi lấy email: {str(e)}"}), 500


@app.route('/')
def serve_index():
    return render_template('index.html')

@app.route('/api/create', methods=['POST'])
def api_create_email():
    data = request.json or {}
    custom_username = data.get("username") # Đổi tên biến cho rõ ràng
    if custom_username:
        # Validate custom_username: chỉ cho phép chữ cái, số, và một số ký tự đặc biệt an toàn
        if not re.match(r"^[a-zA-Z0-9._-]+$", custom_username):
            return jsonify({"error": "Tên người dùng tùy chỉnh chứa ký tự không hợp lệ."}), 400
        email = f"{custom_username.lower()}@quy.edu.pl"
    else:
        email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@quy.edu.pl"
    return jsonify({"email": email})

@app.route('/api/inbox', methods=['GET'])
# Không còn @require_api_key
def api_list_emails():
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Lỗi xác thực Gmail API"}), 503

    target_email = request.args.get('email', "").lower()
    if not target_email or '@' not in target_email:
        return jsonify({"error": "Thiếu tham số email hoặc email không hợp lệ"}), 400

    def fetch_by_label(label):
        query = f"to:{target_email}"
        result = service.users().messages().list(
            userId='me', q=query, labelIds=[label], maxResults=10 # Giới hạn số lượng
        ).execute()
        return result.get('messages', [])

    try:
        inbox_msgs = fetch_by_label("INBOX")
        spam_msgs = fetch_by_label("SPAM")
        all_msgs_refs = (inbox_msgs or []) + (spam_msgs or [])

        mails = []
        for msg_ref in all_msgs_refs:
            detail = service.users().messages().get(userId='me', id=msg_ref['id']).execute()
            payload = detail.get("payload", {})
            headers = payload.get("headers", [])
            snippet = detail.get("snippet", "") # Giữ snippet cho danh sách nhanh
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

            mails.append({
                "id": msg_ref['id'],
                "subject": subject,
                "from": sender,
                "date": date_str,
                "snippet": snippet # Snippet có thể hữu ích cho hiển thị danh sách
            })
        return jsonify({"emails": mails})
    except Exception as e:
        print(f"Lỗi khi lấy danh sách email qua API cho {target_email}: {e}")
        return jsonify({"error": f"Lỗi máy chủ khi xử lý yêu cầu: {str(e)}"}), 500

@app.route('/api/email/<msg_id>', methods=['GET'])
# Endpoint này cũng không cần API key nữa
def api_read_email(msg_id):
    service = gmail_authenticate()
    if not service:
        return jsonify({"error": "Lỗi xác thực Gmail API"}), 503

    # `email` query parameter không thực sự cần thiết nếu msg_id là duy nhất toàn cục
    # và không có kiểm tra quyền sở hữu dựa trên email ở đây.
    # Tuy nhiên, client hiện tại gửi nó, nên ta có thể giữ lại hoặc bỏ qua.
    # target_email_param = request.args.get('email', '').lower()

    if not msg_id:
        return jsonify({"error": "Thiếu ID tin nhắn"}), 400

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
            if not body: # Fallback to text/plain if no HTML part
                for part in parts:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        # Chuyển đổi cơ bản text sang HTML cho hiển thị
                        body = body.replace("\n", "<br>").replace("\r\n", "<br>")
                        break
        elif 'body' in payload and 'data' in payload['body']: # No parts, check main body
            body_data = payload['body']['data']
            mime_type = payload.get('mimeType', '')
            body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
            if mime_type == 'text/plain':
                body = body.replace("\n", "<br>").replace("\r\n", "<br>")


        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

        return jsonify({
            "id": msg_id, # Trả về cả ID
            "subject": subject,
            "from": sender,
            "date": date_str,
            "body": body
        })
    except Exception as e:
        print(f"Lỗi khi đọc chi tiết email {msg_id} qua API: {e}")
        # Kiểm tra xem lỗi có phải do không tìm thấy email (404 từ Google) không
        if hasattr(e, 'resp') and e.resp.status == 404:
            return jsonify({"error": f"Không tìm thấy email với ID: {msg_id}"}), 404
        return jsonify({"error": f"Lỗi máy chủ khi xử lý yêu cầu: {str(e)}"}), 500

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """) # Bảng api_keys đã được loại bỏ
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Email và mật khẩu là bắt buộc."}), 400
    if '@' not in email: # Kiểm tra email hợp lệ cơ bản
        return jsonify({"error": "Địa chỉ email không hợp lệ."}), 400
    if len(password) < 6: # Yêu cầu mật khẩu tối thiểu
         return jsonify({"error": "Mật khẩu phải có ít nhất 6 ký tự."}), 400


    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"error": "Tài khoản đã tồn tại."}), 409 # 409 Conflict

    cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (email, generate_password_hash(password)))
    conn.commit()
    cur.close()
    conn.close()

    session['user'] = email # Tự động đăng nhập sau khi đăng ký
    return jsonify({"message": "Đăng ký thành công.", "email": email}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').lower().strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"error": "Email và mật khẩu là bắt buộc."}), 400

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


# Đã loại bỏ các API endpoint liên quan đến API Key:
# /api/create_api_key, /api/my_keys, /api/delete_key

@app.route('/congcu')
def change_package_page(): # Đổi tên hàm để tránh trùng với tên route
    return render_template('congcu.html')

@app.route("/api/congcu", methods=["POST"])
def api_congcu_process(): # Đổi tên hàm
    data = request.json or {}
    original_link = data.get("link") # Đổi tên biến
    new_pkg = data.get("newPkg")
    new_code = data.get("newCode")

    if not original_link or not new_pkg or not new_code:
        return jsonify({"error": "Thiếu dữ liệu đầu vào."}), 400

    try:
        updated_link = update_link_parameters(original_link, new_pkg, new_code) # Đổi tên hàm
        return jsonify({"new_link": updated_link})
    except Exception as e:
        print(f"Lỗi trong /api/congcu: {e}")
        return jsonify({"error": f"Lỗi xử lý: {str(e)}"}), 500

def update_link_parameters(original_link, new_pkg, new_code): # Đổi tên hàm
    try:
        # Sử dụng urllib.parse để xử lý URL một cách an toàn hơn
        # Tuy nhiên, logic hiện tại dựa trên thay thế chuỗi phức tạp, cần cẩn thận
        decoded_link = urllib.parse.unquote(original_link)
        
        # Thay thế package
        # Cần đảm bảo pattern này chính xác và không gây ra lỗi ngoài ý muốn
        # Ví dụ: subs:com.google.android.apps.subscriptions.red:g1.OLD_PACKAGE_NAME"
        # new_m_string = f'g1.{new_pkg}'
        # updated_link_pkg = re.sub(r'g1\.[^"]+', new_m_string, decoded_link) # Có thể không đủ an toàn

        # Giữ lại logic regex gốc nếu nó đã hoạt động đúng
        matches = re.findall(r'subs:com\.google\.android\.apps\.subscriptions\.red:g1\.[^"]+', decoded_link)
        if not matches:
            # Nếu không tìm thấy pattern package, có thể trả về link gốc hoặc báo lỗi
            # return original_link # Hoặc raise ValueError("Không tìm thấy pattern package trong link.")
            pass # Bỏ qua nếu không tìm thấy, sẽ cố gắng thay thế code

        updated_link_processing = original_link # Bắt đầu lại từ link gốc đã quote
        for m_pattern in matches:
            new_m_replacement_unquoted = re.sub(r'g1\.[^"]+', f'g1.{new_pkg}', m_pattern)
            updated_link_processing = updated_link_processing.replace(
                urllib.parse.quote(m_pattern, safe='/:=?.&'), 
                urllib.parse.quote(new_m_replacement_unquoted, safe='/:=?.&'), 
                1
            )
        
        # Thay thế mã code
        # Pattern gốc: r'%2C\d+%2C' -> tìm kiếm một số được bao bởi %2C (dấu phẩy đã mã hóa URL)
        # Ví dụ: ...%2COLD_CODE%2C...
        # Thay thế bằng: ...%2CNEW_CODE%2C...
        # count=1 để chỉ thay thế lần xuất hiện đầu tiên
        final_updated_link = re.sub(r'%2C\d+%2C', f'%2C{new_code}%2C', updated_link_processing, count=1)
        return final_updated_link
        
    except Exception as ex:
        print("❌ update_link_parameters() lỗi:", ex)
        raise # Ném lại lỗi để endpoint /api/congcu có thể bắt và trả về lỗi 500

# Static files (CSS, JS)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    # Chạy với debug=False trong môi trường production
    app.run(host='0.0.0.0', port=port, debug=False)
