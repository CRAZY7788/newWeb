from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from flask import send_from_directory, request

app = Flask(__name__, template_folder="../new_web/templates", static_folder="../new_web/static")
app.secret_key = "your_secret_key_here"

# 模拟用户数据库
users = {
    "admin": {"password": "123456", "role": "管理员"},
    "user1": {"password": "111111", "role": "普通用户"}
}

@app.route("/")
def index():
    if "username" in session:
        return render_template("main.html", username=session["username"])
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and users[username]["password"] == password:
            session["username"] = username
            return redirect(url_for("index"))
        return render_template("auth.html", error="用户名或密码错误")
    return render_template("auth.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return render_template("logout.html")

@app.route("/files")
def get_files():
    # 模拟“待验收文件”
    files = [
        {"id": 1, "name": "合同_A.pdf"},
        {"id": 2, "name": "报告_B.docx"},
        {"id": 3, "name": "设计稿_C.png"}
    ]
    return jsonify(files)

@app.route("/accept", methods=["POST"])
def accept_file():
    data = request.json
    return jsonify({"status": "success", "message": f"文件 {data['file']} 已验收"})

@app.route("/reject", methods=["POST"])
def reject_file():
    data = request.json
    return jsonify({"status": "success", "message": f"文件 {data['file']} 已拒绝，原因: {data['reason']}"})




# 历史版本下载（受控路由）
@app.get("/versions/download")
def versions_download():
    file_name = request.args.get("file", "文件 A")
    v = request.args.get("v", "V1")
    # 期望真实文件路径：<static>/versions/{file_name}_{v}.pdf
    safe_dir = os.path.join(app.static_folder, "versions")
    # 确保目录存在
    os.makedirs(safe_dir, exist_ok=True)
    expected = f"{file_name}_{v}.pdf"
    expected_path = os.path.join(safe_dir, expected)

    if os.path.exists(expected_path):
        # 找到真实文件就返回它
        return send_from_directory(safe_dir, expected, as_attachment=False)

    # ✅ 回退：返回占位 PDF，避免 404
    # 请放一个占位文件：new_web/static/versions/sample.pdf
    placeholder = "history.pdf"
    placeholder_path = os.path.join(safe_dir, placeholder)
    if not os.path.exists(placeholder_path):
        # 如果还没放，占位生成提醒（也可以直接返回 204）
        # 这里简单返回 204，无内容但不报错
        return ("", 204)
    return send_from_directory(safe_dir, placeholder, as_attachment=False)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
