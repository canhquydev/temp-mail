function showAuthLoading(state) {
    document.getElementById("authLoading").style.display = state ? "block" : "none";
}


async function authLogin() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value.trim();
    const errorBox = document.getElementById('authError');
    errorBox.innerText = '';
    showAuthLoading(true);
    if (!email || !password) {
        showAuthLoading(false);
        errorBox.innerText = "⚠️ Vui lòng nhập đầy đủ email và mật khẩu.";
        return;
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json().catch(() => ({ error: "❌ Lỗi phản hồi từ server." }));
        if (data.error) {
            errorBox.innerText = data.error;
            showAuthLoading(false);
        } else {
            closeAuthPopup();
            showAuthLoading(false);
            setTimeout(() => {
                location.reload();
            }, 100);
        }

    } catch (e) {
        console.error("Lỗi:", e);
        errorBox.innerText = "Không thể kết nối đến máy chủ.";
        showAuthLoading(false);
    }
}

async function authRegister() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value.trim();
    const errorBox = document.getElementById('authError');
    errorBox.innerText = '';
    showAuthLoading(true);
    if (!email || !password) {
        showAuthLoading(false);
        errorBox.innerText = "⚠️ Vui lòng nhập đầy đủ email và mật khẩu.";
        return;
    }

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json().catch(() => ({ error: "❌ Lỗi phản hồi từ server." }));
        if (data.error) {
            errorBox.innerText = data.error;
            showAuthLoading(false);
        } else {
            closeAuthPopup();
            showAuthLoading(false);
            setTimeout(() => {
                location.reload();
            }, 100);
        }

    } catch (e) {
        console.error("Lỗi:", e);
        errorBox.innerText = "Không thể kết nối đến máy chủ.";
        showAuthLoading(false);
    }
}
function logout() {
    document.getElementById('logoutBtn').innerText = "⏳ Đang đăng xuất...";
    document.getElementById('logoutBtn').disabled = true;

    fetch('/api/logout', { method: 'POST' }).then(() => {
        setTimeout(() => {
            location.reload();
        }, 100);
    });
}


async function checkLoginStatus() {
    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        if (data.email) {
            document.getElementById('createApiKeyBtn').style.display = 'inline-block';
            document.getElementById('loginBtn').style.display = 'none';
            document.getElementById('logoutBtn').style.display = 'inline-block';
        } else throw new Error();
    } catch {
        document.getElementById('createApiKeyBtn').style.display = 'none';
        document.getElementById('loginBtn').style.display = 'inline-block';
        document.getElementById('logoutBtn').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', checkLoginStatus);
document.addEventListener('DOMContentLoaded', () => {
    const emailInput = document.getElementById('emailInput');
    if (emailInput && emailInput.value === '') {
        emailInput.focus();
    }
});

const urlPath = window.location.pathname;
const match = urlPath.match(/^\/(.+@.+)$/);
if (match) {
    const email = decodeURIComponent(match[1]);
    document.addEventListener('DOMContentLoaded', () => {
        const input = document.getElementById('emailInput');
        input.value = email;
        setTimeout(() => fetchEmails(true), 300);
    });
}
let cachedEmails = [];

async function createEmail() {
    const res = await fetch('/create_email', { method: 'POST' });
    const data = await res.json();
    const emailInput = document.getElementById('emailInput');
    emailInput.value = data.email;

    // Đợi DOM cập nhật xong rồi mới gọi fetch
    setTimeout(() => fetchEmails(true), 200);
}


function renderEmails() {
    const emailList = document.getElementById('emailList');
    emailList.innerHTML = cachedEmails.length === 0
        ? "<p style='text-align:center;'>Không có thư nào hoặc lỗi.</p>"
        : cachedEmails.map((mail, index) => {
            const formattedDate = new Date(mail.date).toLocaleString("vi-VN", {
                timeZone: "Asia/Ho_Chi_Minh"
            });
            return `
                <div class="email-item" onclick="showPopup(${index})">
                    <strong>${mail.subject}</strong>
                    <small>From: ${mail.from}<br>Date: ${formattedDate}</small>
                </div>
            `;
        }).join('');
}

async function fetchEmails(showLoading = true) {
    const email = document.getElementById('emailInput').value.trim().toLowerCase();
    if (!email.includes('@')) return;

    if (showLoading) document.getElementById('loading').style.display = "block";

    try {
        const res = await fetch('/list_emails?email=' + encodeURIComponent(email));
        const data = await res.json();

        if (data.error) {
            if (showLoading) alert("⚠ " + data.error);
            cachedEmails = [];
        } else {
            // Luôn gán lại dữ liệu và render, kể cả khi giống
            cachedEmails = data;
        }

        renderEmails(); // luôn gọi để cập nhật UI
    } catch (e) {
        console.error("❌ Lỗi khi fetch:", e);
        cachedEmails = [];
        if (showLoading) alert("Lỗi khi lấy thư");
        renderEmails(); // vẫn gọi render để xoá UI cũ nếu lỗi
    }

    if (showLoading) document.getElementById('loading').style.display = "none";
}

function showPopup(index) {
    const mail = cachedEmails[index];
    const sanitizedBody = mail.body.replace(/<a\s/gi, '<a target="_blank" ');
    const formattedDate = new Date(mail.date).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh"
    });

    const popupBody = document.getElementById('popupBody');
    popupBody.innerHTML = `
        <h2 style="color:#4CAF50;">${mail.subject}</h2>
        <p><strong>From:</strong> ${mail.from}</p>
        <p><strong>Date:</strong> ${formattedDate}</p>
        <hr>
        <div style="max-height:400px;overflow:auto;border:1px solid #ccc;padding:10px;">${sanitizedBody}</div>
    `;
    document.getElementById('popupOverlay').style.display = "flex";
}


function closePopup() {
    document.getElementById('popupOverlay').style.display = "none";
}

function handleOverlayClick(event) {
    const popupContent = document.getElementById('popupContent');
    if (!popupContent.contains(event.target)) {
        closePopup();
    }
}

document.getElementById('copyBtn').addEventListener('click', async function() {
    const email = document.getElementById('emailInput').value.trim();
    const copyBtn = document.getElementById('copyBtn');
    if (!email) return;

    try {
        await navigator.clipboard.writeText(email);
        copyBtn.innerHTML = "✅";
        setTimeout(() => copyBtn.innerHTML = "📋", 2000);
    } catch {
        copyBtn.innerHTML = "❌";
        setTimeout(() => copyBtn.innerHTML = "📋", 2000);
    }
});

document.getElementById('createBtn').addEventListener('click', createEmail);
document.getElementById('refreshBtn').addEventListener('click', () => fetchEmails(true));

// Auto-reload thư mỗi 10 giây mà không hiện loading
setInterval(() => {
    const email = document.getElementById('emailInput').value.trim().toLowerCase();
    if (email.includes('@')) {
        fetchEmails(false); // chỉ fetch khi có email
    }
}, 10000);
    
async function createApiKey() {
    const loadingBox = document.getElementById('apiKeyLoading');
    const toast = document.getElementById('apiKeyToast');
    loadingBox.style.display = 'block';
    toast.style.display = 'none';

    try {
        const res = await fetch('/api/create_api_key', { method: 'POST' });
        const data = await res.json();

        loadingBox.style.display = 'none';

        if (data.key) {
            showApiKeyToast("✅ Tạo API Key thành công!");
            loadApiKeys(); // Chỉ hiển thị ở danh sách
        } else {
            showApiKeyToast("❌ " + data.error, "red");
        }

    } catch (e) {
        loadingBox.style.display = 'none';
        showApiKeyToast("❌ Lỗi khi tạo API Key.", "red");
        console.error(e);
    }
}



function openApiPopup() {
    document.getElementById('apiPopup').style.display = 'flex';
}
function closeApiPopup() {
    document.getElementById('apiPopup').style.display = 'none';
    document.getElementById('apiKeyResult').innerText = "";
}

function openApiPopup() {
    document.getElementById('apiPopup').style.display = 'flex';
    loadApiKeys();
}

async function loadApiKeys() {
    const list = document.getElementById('apiKeyList');
    list.innerHTML = "🔄 Đang tải...";

    try {
        const res = await fetch('/api/my_keys');
        const data = await res.json();
        if (data.length === 0) {
            list.innerHTML = "";
            return;
        }

        list.innerHTML = data.map(k => `
            <div style="padding:8px; margin-bottom:8px; background:#f3f3f3; border-radius:6px; position:relative;">
                <code style="word-break:break-all; display:block;">${k.key}</code>
                <small style="color:#666;">📅 ${new Date(k.created).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })}</small>
                <div style="position:absolute; top:8px; right:8px;">
                    <button onclick="copyToClipboard('${k.key}')" style="margin-right:4px;">📋</button>
                    <button onclick="deleteApiKey('${k.key}')">🗑️</button>
                </div>
            </div>
        `).join('');

    } catch (e) {
        list.innerHTML = "<p style='color:red;'>Lỗi khi tải danh sách key.</p>";
    }
}

async function deleteApiKey(key) {
    if (!confirm("Xoá key này?")) return;
    const res = await fetch('/api/delete_key', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ key })
    });
    const data = await res.json();
    if (data.success) {
        loadApiKeys();
        showApiKeyToast("🗑️ Đã xoá API Key.");
    } else {
        showApiKeyToast("❌ " + (data.error || "Không thể xoá."), "red");
    }
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showApiKeyToast("📋 Đã copy API Key!");
    } catch {
        showApiKeyToast("❌ Không thể copy.", "red");
    }
}

function openAuthPopup() {
    document.getElementById('authPopup').style.display = 'flex';
}
function closeAuthPopup() {
    document.getElementById('authPopup').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        if (data.email) {
            document.getElementById('createApiKeyBtn').style.display = 'inline-block';
        }
    } catch (e) {
        console.warn("Không xác định được trạng thái đăng nhập:", e);
    }
});
function showApiKeyToast(msg, color = "#4CAF50") {
    const toast = document.getElementById("apiKeyToast");
    toast.innerText = msg;
    toast.style.color = color;
    toast.style.display = "block";
    setTimeout(() => { toast.style.display = "none"; }, 2500);
}
