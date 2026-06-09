"""
KLUB x Frastea — Bounce & Open Tracker
endpoints:
  GET /approve/<lead_id>  — 主管批准，立即發 VIP 信
  GET /open/<lead_id>     — 追蹤開信像素
  GET /bounce             — 退信 webhook (query: email)
  GET /stats              — 統計頁
"""
import os, sqlite3, importlib.util, sys
from datetime import datetime
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

DB_PATH     = os.environ.get('DB_PATH', '/app/output/leads.db')
SENDER_PATH = os.environ.get('SENDER_PATH', '/app/us_email_sender.py')

PIXEL = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_sender():
    spec = importlib.util.spec_from_file_location('sender', SENDER_PATH)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ── 主管批准 ──────────────────────────────────────────────────────

@app.route('/approve/<int:lead_id>')
def approve(lead_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT company, email, email_status FROM leads WHERE id=?", (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return '❌ Lead not found', 404
    if row['email_status'] == 'sent':
        conn.close()
        return f'⚠️ {row["company"]} 已經發送過了', 200

    # 記錄批准
    cur.execute("UPDATE leads SET email_status='approved' WHERE id=?", (lead_id,))
    conn.commit(); conn.close()

    # 立即發信
    try:
        sender = load_sender()
        ok = sender.send_vip(lead_id)
        if ok:
            return f'✅ 已批准並發送給 {row["company"]} ({row["email"]})', 200
        else:
            return f'⚠️ 批准成功但發信失敗，請檢查 SMTP', 500
    except Exception as e:
        return f'❌ Error: {e}', 500

# ── 開信追蹤像素 ──────────────────────────────────────────────────

@app.route('/open/<int:lead_id>')
def track_open(lead_id):
    try:
        conn = db(); cur = conn.cursor()
        cur.execute("UPDATE leads SET email_opened=1 WHERE id=?", (lead_id,))
        conn.commit(); conn.close()
    except Exception:
        pass
    return Response(PIXEL, mimetype='image/gif')

# ── 退信 Webhook ─────────────────────────────────────────────────

@app.route('/bounce', methods=['GET', 'POST'])
def bounce():
    email = request.values.get('email', '')
    if not email:
        return 'missing email', 400
    try:
        conn = db(); cur = conn.cursor()
        cur.execute("UPDATE leads SET email_status='bounced' WHERE email=?", (email,))
        conn.commit(); conn.close()
        return f'marked bounced: {email}', 200
    except Exception as e:
        return str(e), 500

# ── 統計 ──────────────────────────────────────────────────────────

@app.route('/stats')
def stats():
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT email_status, COUNT(*) n FROM leads GROUP BY email_status")
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM leads WHERE email_opened=1")
    opened = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''")
    total_email = cur.fetchone()[0]
    conn.close()

    data = {r['email_status'] or 'unsent': r['n'] for r in rows}
    data['opened'] = opened
    data['total_with_email'] = total_email
    return jsonify(data)

@app.route('/')
def index():
    return '<h2>KLUB Tracker OK</h2><p><a href="/stats">Stats</a></p>'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
