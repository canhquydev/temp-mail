// app.js — extracted from index.html

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
            setTimeout(() => location.reload(), 100);
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
            setTimeout(() => location.reload(), 100);
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
    fetch('/api/logout', { method: 'POST' }).then(() => setTimeout(() => location.reload(), 100));
}

async function checkLoginStatus() {
    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        document.getElementById('createApiKeyBtn').style.display = data.email ? 'inline-block' : 'none';
        document.getElementById('loginBtn').style.display = data.email ? 'none' : 'inline-block';
        document.getElementById('logoutBtn').style.display = data.email ? 'inline-block' : 'none';
    } catch {
        document.getElementById('createApiKeyBtn').style.display = 'none';
        document.getElementById('loginBtn').style.display = 'inline-block';
        document.getElementById('logoutBtn').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
    const emailInput = document.getElementById('emailInput');
    if (emailInput && emailInput.value === '') emailInput.focus();

    const urlPath = window.location.pathname;
    const match = urlPath.match(/^\/(.+@.+)$/);
    if (match) {
        const email = decodeURIComponent(match[1]);
        const input = document.getElementById('emailInput');
        input.value = email;
        setTimeout(() => fetchEmails(true), 300);
    }

    document.getElementById('copyBtn').addEventListener('click', async () => {
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
    setInterval(() => {
        const email = document.getElementById('emailInput').value.trim().toLowerCase();
        if (email.includes('@')) fetchEmails(false);
    }, 10000);
});
