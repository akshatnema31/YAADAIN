from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import secrets
import string

app = Flask(__name__)
CORS(app)

DATABASE = "chat.db"


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- INITIALIZE DATABASE ----------------

def init_db():
    conn = get_db()

    # Rooms table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            code TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Messages table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ---------------- UPGRADE OLD DATABASE ----------------

def upgrade_db():
    conn = get_db()

    columns = conn.execute(
        "PRAGMA table_info(messages)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "room_code" not in column_names:
        conn.execute(
            "ALTER TABLE messages ADD COLUMN room_code TEXT"
        )
        conn.commit()

    conn.close()


# ---------------- GET MESSAGES ----------------

@app.get("/messages")
def get_messages():

    room_code = request.args.get("code", "").strip().upper()

    if not room_code:
        return jsonify({
            "error": "Room code is required"
        }), 400

    conn = get_db()

    rows = conn.execute("""
        SELECT id, room_code, name, text, timestamp
        FROM messages
        WHERE room_code = ?
        ORDER BY id ASC
    """, (room_code,)).fetchall()

    conn.close()

    return jsonify([
        dict(row) for row in rows
    ])


# ---------------- SEND MESSAGE ----------------

@app.post("/messages")
def send_message():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Invalid JSON"
        }), 400

    room_code = data.get("room_code", "").strip().upper()
    name = data.get("name", "").strip()
    text = data.get("text", "").strip()

    if not room_code:
        return jsonify({
            "error": "Room code is required"
        }), 400

    if not name or not text:
        return jsonify({
            "error": "Name and message are required"
        }), 400

    conn = get_db()

    # Check whether room exists
    room = conn.execute(
        "SELECT code FROM rooms WHERE code = ?",
        (room_code,)
    ).fetchone()

    if room is None:
        conn.close()

        return jsonify({
            "error": "Room does not exist"
        }), 404

    # Insert message
    cursor = conn.execute("""
        INSERT INTO messages (room_code, name, text)
        VALUES (?, ?, ?)
    """, (room_code, name, text))

    conn.commit()

    message_id = cursor.lastrowid

    # Get inserted message
    row = conn.execute("""
        SELECT id, room_code, name, text, timestamp
        FROM messages
        WHERE id = ?
    """, (message_id,)).fetchone()

    conn.close()

    return jsonify(dict(row)), 201


# ---------------- CREATE ROOM ----------------

@app.post("/create-room")
def create_room():

    conn = get_db()

    while True:

        code = ''.join(
            secrets.choice(
                string.ascii_uppercase + string.digits
            )
            for _ in range(6)
        )

        existing = conn.execute(
            "SELECT code FROM rooms WHERE code = ?",
            (code,)
        ).fetchone()

        if existing is None:
            break

    conn.execute(
        "INSERT INTO rooms (code) VALUES (?)",
        (code,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "code": code
    }), 201


# ---------------- CHECK ROOM ----------------

@app.get("/check-room/<code>")
def check_room(code):

    code = code.strip().upper()

    conn = get_db()

    room = conn.execute(
        "SELECT code FROM rooms WHERE code = ?",
        (code,)
    ).fetchone()

    conn.close()

    if room is None:
        return jsonify({
            "exists": False
        }), 404

    return jsonify({
        "exists": True,
        "code": code
    }), 200


# ---------------- START SERVER ----------------

if __name__ == "__main__":

    init_db()
    upgrade_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )