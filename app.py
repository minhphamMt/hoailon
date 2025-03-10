from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import google.generativeai as genai
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app)

# 🔐 Cấu hình Flask và SQL Server
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.secret_key = os.urandom(24)

# 🔥 Cấu hình kết nối SQL Server qua pyodbc
DB_USERNAME = "root"
DB_PASSWORD = "YRdlpsKbwapkgrBqFOSJltJuvChzyHpR"
DB_HOST = "mysql.railway.internal"
DB_PORT = "3306"
DB_NAME = "railway"
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ✅ Khởi tạo SQLAlchemy
db = SQLAlchemy(app)

# 🔎 Tạo model cho bảng hội thoại
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text(collation="Latin1_General_CI_AI"), nullable=False)
    bot_reply = db.Column(db.Text(collation="Latin1_General_CI_AI"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())



# ✅ Tạo bảng trong SQL Server nếu chưa tồn tại
with app.app_context():
    db.create_all()
    print("✅ Table 'Conversation' đã được tạo hoặc đã tồn tại.")

# 🔑 API Key Google Gemini
GOOGLE_API_KEY = "AIzaSyD_SnGYXJ5puG0uG17exEhMju4o5DyClT8"
genai.configure(api_key=GOOGLE_API_KEY)

# ✅ Dùng model Gemini
MODEL_NAME = "models/gemini-1.5-pro"
model = genai.GenerativeModel(MODEL_NAME)

# ✅ Lấy lịch sử từ database
def get_conversation_history():
    history = []
    conversations = Conversation.query.order_by(Conversation.id).all()
    for conv in conversations:
        history.append({"role": "user", "parts": [conv.user_message]})
        history.append({"role": "model", "parts": [conv.bot_reply]})
    return history

# ✅ Lưu tin nhắn vào database (chuyển về UTF-8 trước khi lưu)
def save_message(user_message, bot_reply):
    try:
        # Chắc chắn rằng dữ liệu là chuỗi Unicode trước khi lưu
        user_message = str(user_message)
        bot_reply = str(bot_reply)
        new_conv = Conversation(user_message=user_message, bot_reply=bot_reply)
        db.session.add(new_conv)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Lỗi khi lưu vào database: {e}")


# ✅ Lấy toàn bộ lịch sử hội thoại
@app.route("/history", methods=["GET"])
def get_history():
    try:
        history = get_conversation_history()
        return jsonify({"history": history}), 200
    except Exception as e:
        print(f"❌ Lỗi khi lấy lịch sử hội thoại: {e}")
        return jsonify({"error": "Failed to load conversation history"}), 500

# ✅ Gửi tin nhắn và nhận phản hồi từ Gemini
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Thiếu dữ liệu đầu vào"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "Message is empty"}), 400

    try:
        # ✅ Lấy lịch sử hội thoại từ database
        history = get_conversation_history()

        # ✅ Khởi tạo session nếu chưa tồn tại
        if "conversation" not in session:
            session["conversation"] = history

        # ✅ Thêm tin nhắn người dùng vào session
        session["conversation"].append({"role": "user", "parts": [user_message]})

        # ✅ Khởi tạo ChatSession từ lịch sử hội thoại
        chat_session = model.start_chat(history=session["conversation"])

        # ✅ Gửi tin nhắn và nhận phản hồi từ Gemini
        gemini_response = chat_session.send_message(user_message)
        bot_reply = gemini_response.text.strip() if gemini_response.text else "⚠️ Không có phản hồi từ bot!"

        # ✅ Thêm phản hồi vào session
        session["conversation"].append({"role": "model", "parts": [bot_reply]})
        session.modified = True

        # ✅ Lưu vào database
        save_message(user_message, bot_reply)

        return jsonify({"response": bot_reply}), 200

    except Exception as e:
        print(f"❌ Lỗi khi gọi Gemini API: {e}")
        return jsonify({
            "error": "Failed to get response from Google Gemini",
            "details": str(e)
        }), 500

# ✅ Xóa toàn bộ hội thoại
@app.route("/reset", methods=["POST"])
def reset_conversation():
    try:
        # 🔄 Xóa toàn bộ hội thoại từ database
        db.session.query(Conversation).delete()
        db.session.commit()

        # 🔄 Xóa session
        session.pop("conversation", None)

        return jsonify({"status": "Conversation reset"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Lỗi khi reset hội thoại: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Kiểm tra kết nối SQL Server
@app.route("/check-db", methods=["GET"])
def check_db():
    try:
        # Test kết nối
        db.session.execute("SELECT 1")
        return jsonify({"status": "Database connected"}), 200
    except Exception as e:
        print(f"❌ Lỗi kết nối database: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Chạy ứng dụng Flask
if __name__ == "__main__":
    app.run(debug=True)
