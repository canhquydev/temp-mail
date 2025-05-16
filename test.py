import requests

# ✅ Cấu hình API endpoint và key
BASE_URL = "https://quy.edu.pl"  # Đổi nếu cần
API_KEY = "b077a4b5d585411f70de688f7ae38d0e"     # Dán API key cần test vào đây

# ✅ Email giả định để test
TEST_EMAIL = "chatgpt@quy.edu.pl"

# ✅ Test API: lấy inbox
resp = requests.get(
    f"{BASE_URL}/api/inbox",
    params={"email": TEST_EMAIL},
    headers={"Authorization": f"Bearer {API_KEY}"}  # nếu bạn bảo vệ bằng Bearer token
)

print("📥 Status:", resp.status_code)
print("📬 Nội dung:", resp.json())

# ✅ Test API: đọc nội dung email (nếu có)
data = resp.json()
if isinstance(data, dict) and "emails" in data and data["emails"]:
    msg_id = data["emails"][0]["id"]
    detail = requests.get(
        f"{BASE_URL}/api/email/{msg_id}",
        params={"email": TEST_EMAIL},
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    print("\n📖 Chi tiết email đầu tiên:")
    print(detail.json())
else:
    print("⚠️ Không có email để test chi tiết.")
