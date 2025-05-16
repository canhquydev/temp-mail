import base64
import os

# Danh sách file cần mã hoá: (tên file gốc, tên file đã mã hoá)
html_files = [
    ("index.html", "index_obfuscated.html"),
    ("congcu.html", "congcu_obfuscated.html")
]

for original, output in html_files:
    path_in = os.path.join("templates", original)
    path_out = os.path.join("templates", output)

    if not os.path.exists(path_in):
        print(f"⚠️ Không tìm thấy {path_in}")
        continue

    with open(path_in, "r", encoding="utf-8") as f:
        html = f.read()

    encoded = base64.b64encode(html.encode()).decode()

    with open(path_out, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{original}</title></head><body>
<script>
    document.write(atob("{encoded}"));
</script>
</body></html>
""")

    print(f"✅ Đã mã hoá {original} → {output}")
