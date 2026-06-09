"""
KLUB x Frastea — US Email Sender v6
Flow B: VIP → 主管確認 → send_vip | GENERAL → 直接發
排程: 台灣 06:00 (UTC 22:00) 執行
"""
import sqlite3, smtplib, os, time, random, logging, schedule
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DB_PATH      = os.environ.get('DB_PATH', '/app/output/leads.db')
SMTP_HOST    = os.environ.get('SMTP_HOST', 'mail.frastea.com')
SMTP_PORT    = int(os.environ.get('SMTP_PORT', '465'))
SMTP_USER_E  = os.environ.get('SMTP_USER_EAST',  'mt08@frastea.com')
SMTP_PASS_E  = os.environ.get('SMTP_PASS_EAST',  '')
SMTP_USER_W  = os.environ.get('SMTP_USER_WEST',  'mt04@frastea.com')
SMTP_PASS_W  = os.environ.get('SMTP_PASS_WEST',  '')
MANAGER_EMAIL = os.environ.get('MANAGER_EMAIL',  'mt08@frastea.com')
REPORT_EMAIL  = os.environ.get('REPORT_EMAIL',   'mt23@klubtech.com')
TRACKER_URL   = os.environ.get('TRACKER_URL',    'https://klub-us-tracker.zeabur.app')
DAILY_LIMIT   = int(os.environ.get('DAILY_LIMIT', '40'))
DELAY_MIN     = int(os.environ.get('DELAY_MIN',   '180'))
DELAY_MAX     = int(os.environ.get('DELAY_MAX',   '480'))

# ── 模板（硬編碼，不可被 AI 竄改）──────────────────────────────────

HEADER = '<div style="background:#1c1c1c;padding:20px 30px;margin-bottom:30px;"><h1 style="color:#cda85e;margin:0;font-family:serif;font-size:22px;letter-spacing:2px;">FRASTEA</h1><p style="color:#777;margin:5px 0 0;font-family:sans-serif;font-size:11px;letter-spacing:1px;">PREMIUM TEA &amp; BEVERAGE SOLUTIONS</p></div>'

SIGN = '<div style="margin-top:30px;border-top:1px solid #eee;padding-top:20px;font-family:sans-serif;font-size:14px;line-height:1.6;"><p style="margin:0;"><strong>Elena Chiang</strong><br>Frastea Co. Ltd.<br>Email: <a href="mailto:mt08@frastea.com" style="color:#333;text-decoration:none;">mt08@frastea.com</a><br>Tel: +886 963 710 172<br>Web: <a href="http://www.frastea.com" style="color:#cda85e;text-decoration:none;">www.frastea.com</a><br>Add: 8F, No. 190, Ln. 461, Zhongfeng Rd., Longtan Dist., Taoyuan City 25025, Taiwan (R.O.C.)</p></div>'

# 產品圖片 inline base64（從公司模板截圖提取）
IMG_TEA     = os.environ.get('IMG_TEA',     'data:image/jpeg;base64,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')
IMG_MACHINE = os.environ.get('IMG_MACHINE', 'data:image/jpeg;base64,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')

def _product_block():
    img = f'<img src="{IMG_TEA}" alt="Frastea Tea Products" style="max-width:140px;display:block;margin-bottom:12px;">' if IMG_TEA else ''
    return f'<div style="border-top:1px solid #eee;border-bottom:1px solid #eee;padding:20px 0;margin:20px 0;display:table;width:100%;"><div style="display:table-cell;vertical-align:middle;width:160px;padding-right:20px;">{img}</div><div style="display:table-cell;vertical-align:middle;"><h4 style="margin:0 0 8px;letter-spacing:1px;font-family:sans-serif;">FEATURED PRODUCTS</h4><p style="margin:0;font-family:sans-serif;font-size:14px;">Premium tea &amp; herbal ingredients — sourced from 30+ origins with consistent quality and flexible MOQ.</p></div></div>'

def _equipment_block():
    img = f'<img src="{IMG_MACHINE}" alt="Tea&Espresso Machine" style="max-width:140px;display:block;margin-bottom:12px;">' if IMG_MACHINE else ''
    return f'<div style="border-top:1px solid #eee;border-bottom:1px solid #eee;padding:20px 0;margin:20px 0;display:table;width:100%;"><div style="display:table-cell;vertical-align:middle;width:160px;padding-right:20px;">{img}</div><div style="display:table-cell;vertical-align:middle;"><h4 style="margin:0 0 8px;letter-spacing:1px;font-family:sans-serif;">FEATURED EQUIPMENT</h4><p style="margin:0;font-family:sans-serif;font-size:14px;">Tea&amp;Espresso Two Group Head Machine — commercial brewing designed for high-volume operations.</p></div></div>'

def _both_block():
    img_t = f'<img src="{IMG_TEA}" alt="Tea" style="max-width:100px;display:block;margin-bottom:8px;">' if IMG_TEA else ''
    img_m = f'<img src="{IMG_MACHINE}" alt="Machine" style="max-width:100px;display:block;margin-bottom:8px;">' if IMG_MACHINE else ''
    return f'<div style="border-top:1px solid #eee;border-bottom:1px solid #eee;padding:20px 0;margin:20px 0;display:table;width:100%;"><div style="display:table-cell;vertical-align:top;width:50%;padding-right:16px;">{img_t}<h4 style="margin:0 0 6px;letter-spacing:1px;font-family:sans-serif;">TEA &amp; HERBAL</h4><p style="margin:0;font-family:sans-serif;font-size:13px;">Premium ingredients from 30+ origins.</p></div><div style="display:table-cell;vertical-align:top;padding-left:16px;border-left:1px solid #eee;">{img_m}<h4 style="margin:0 0 6px;letter-spacing:1px;font-family:sans-serif;">EQUIPMENT</h4><p style="margin:0;font-family:sans-serif;font-size:13px;">Tea&amp;Espresso Two Group Head Machine.</p></div></div>'

# lambda(name, company, locations_str)
TEMPLATES = {
    "VIP_INGREDIENT":  (
        "Tea & herbal supply for {company}",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>Running {loc} locations means ingredient consistency is everything — one off-batch and it shows across the board.</p><p>We&#39;re Frastea, and we supply premium tea leaves and herbal ingredients to multi-location beverage chains across the US. A few groups your size have made the switch and haven&#39;t looked back.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _product_block()
    ),
    "VIP_EQUIPMENT":   (
        "Brewing equipment built for {loc}-location operations",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>When equipment goes down at one of your {loc} locations, it&#39;s not just that store that feels it.</p><p>KLUB Technology builds commercial brewing machines for high-volume chains — designed for reliability and easy to standardize across locations. Happy to share what that looks like in practice.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _equipment_block()
    ),
    "VIP_BOTH":        (
        "One partner for ingredients & equipment",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>Most chains in your company size are managing separate vendors for ingredients and equipment — which works, until it doesn&#39;t.</p><p>Frastea and KLUB Technology are sister companies offering premium tea &amp; herbal ingredients alongside the commercial brewing machines to brew them right. One partner, end to end.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _both_block()
    ),
    "GENERAL_INGREDIENT": (
        "Free sample, tea & herbal ingredients for {company}",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>We supply premium tea leaves and herbal ingredients to cafes and beverage shops across the US.</p><p>If you&#39;re ever looking for a reliable source or just want to try something new on your menu, we&#39;d love to send over a sample. No commitment.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _product_block()
    ),
    "GENERAL_EQUIPMENT":  (
        "Brewing equipment for {company}, quick question",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>We make commercial brewing machines for cafes and beverage shops that need something reliable and easy to run day-to-day.</p><p>If your current setup ever gives you trouble, or you&#39;re thinking about expanding, we&#39;d love to show you what we have.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _equipment_block()
    ),
    "GENERAL_BOTH":       (
        "Ingredients & equipment for {company}",
        lambda n,c,loc: f"<p>Hi {n},</p><p>This is Elena from Frastea Co. Ltd. from Taiwan.</p><p>Frastea and KLUB Technology are sister companies — we handle premium tea &amp; herbal ingredients and the brewing machines to go with them.</p><p>If you&#39;re sourcing either right now (or just open to exploring), we&#39;d love to connect. Happy to send samples or a quick overview, whichever is more useful.</p><p>We can arrange a short discussion or meeting on how we can support your operation.</p>" + _both_block()
    ),
}

# ── 工具函式 ────────────────────────────────────────────────────────

def classify(industry):
    ind = str(industry).lower()
    if any(k in ind for k in ['equipment', 'machine', 'maintenance', 'food service']):
        return 'EQUIPMENT'
    if any(k in ind for k in ['material', 'trading', 'wholesaler', 'ingredient']):
        return 'INGREDIENT'
    return 'BOTH'

def get_smtp(region):
    if str(region).upper() == 'WEST':
        return SMTP_USER_W, SMTP_PASS_W
    return SMTP_USER_E, SMTP_PASS_E

def smtp_send(user, passwd, to_email, subject, html):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'Elena Chiang <{user}>'
    msg['To']      = to_email
    msg['Reply-To'] = user
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    s = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
    s.ehlo(); s.login(user, passwd); s.sendmail(user, [to_email], msg.as_string()); s.quit()

def build_customer_email(lead_id, tier, industry, company, contact, region, locations_count=None):
    cat   = classify(industry)
    key   = f"{(tier or 'GENERAL').upper()}_{cat}"
    tpl   = TEMPLATES.get(key, TEMPLATES['GENERAL_BOTH'])
    name  = (contact or '').strip() or 'Manager'
    co    = (company or '').strip() or 'your company'
    loc   = str(int(locations_count)) if locations_count and str(locations_count).isdigit() else 'multiple'
    subj  = tpl[0].replace('{company}', co).replace('{loc}', loc)
    body  = tpl[1](name, co, loc)
    pixel = f'<img src="{TRACKER_URL}/open/{lead_id}" width="1" height="1" style="display:none">'
    html  = f'<html><body style="font-family:serif;color:#333;max-width:600px;margin:0 auto;">{HEADER}{body}{SIGN}{pixel}</body></html>'
    return subj, html

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── 模式 1: vip_notify — 寄確認信給主管 ────────────────────────────

def vip_notify():
    if not os.path.exists(DB_PATH):
        log.error(f'DB not found: {DB_PATH}'); return
    conn = db_connect(); cur = conn.cursor()
    cur.execute("""
        SELECT id, company, industry, contact, email, tier, region
        FROM leads
        WHERE tier = 'VIP'
          AND email IS NOT NULL AND email != ''
          AND (email_status IS NULL OR email_status = '')
        ORDER BY RANDOM() LIMIT ?
    """, (DAILY_LIMIT,))
    leads = cur.fetchall()
    conn.close()

    log.info(f'[vip_notify] {len(leads)} VIP leads to notify')
    for row in leads:
        cat  = classify(row['industry'])
        subj_preview, _ = build_customer_email(row['id'], row['tier'], row['industry'],
                                               row['company'], row['contact'], row['region'],
                                               row['locations_count'])
        ok_url = f"{TRACKER_URL}/approve/{row['id']}"
        html = f"""<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;">
<h2 style="color:#1c1c1c;">📋 VIP 發信確認</h2>
<table style="border-collapse:collapse;width:100%;">
<tr><td style="padding:8px;color:#666;width:120px;">公司</td><td style="padding:8px;font-weight:bold;">{row['company']}</td></tr>
<tr style="background:#f9f9f9;"><td style="padding:8px;color:#666;">收件人</td><td style="padding:8px;">{row['contact'] or '(未知)'}</td></tr>
<tr><td style="padding:8px;color:#666;">Email</td><td style="padding:8px;">{row['email']}</td></tr>
<tr style="background:#f9f9f9;"><td style="padding:8px;color:#666;">類別</td><td style="padding:8px;">{row['industry']} → <strong>{cat}</strong></td></tr>
<tr><td style="padding:8px;color:#666;">信件主旨</td><td style="padding:8px;font-style:italic;">{subj_preview}</td></tr>
</table>
<div style="margin:30px 0;text-align:center;">
  <a href="{ok_url}" style="background:#27ae60;color:white;padding:14px 32px;text-decoration:none;border-radius:6px;font-size:16px;font-weight:bold;">✅ 批准發送</a>
</div>
<p style="color:#999;font-size:12px;text-align:center;">點擊後將立即寄出開發信給客戶，此動作無法撤回</p>
</body></html>"""
        try:
            smtp_send(SMTP_USER_E, SMTP_PASS_E, MANAGER_EMAIL,
                      f'[VIP 待批准] {row["company"]} — {row["email"]}', html)
            conn2 = db_connect(); cur2 = conn2.cursor()
            cur2.execute("UPDATE leads SET email_status='pending_approval', sent_at=? WHERE id=?",
                         (datetime.utcnow().isoformat(), row['id']))
            conn2.commit(); conn2.close()
            log.info(f'  Notified manager for [{row["id"]}] {row["company"]}')
            time.sleep(random.randint(10, 30))
        except Exception as e:
            log.error(f'  FAIL vip_notify [{row["id"]}]: {e}')

# ── 模式 2: run — 直接發給 GENERAL ─────────────────────────────────

def run_general():
    if not os.path.exists(DB_PATH):
        log.error(f'DB not found: {DB_PATH}'); return
    conn = db_connect(); cur = conn.cursor()
    cur.execute("""
        SELECT id, company, industry, contact, email, tier, region
        FROM leads
        WHERE (tier IS NULL OR tier != 'VIP')
          AND email IS NOT NULL AND email != ''
          AND (email_status IS NULL OR email_status = '')
        ORDER BY RANDOM() LIMIT ?
    """, (DAILY_LIMIT,))
    leads = cur.fetchall(); conn.close()

    log.info(f'[run_general] {len(leads)} GENERAL leads')
    sent = 0
    for row in leads:
        user, passwd = get_smtp(row['region'])
        try:
            subj, html = build_customer_email(row['id'], row['tier'], row['industry'],
                                              row['company'], row['contact'], row['region'],
                                              row['locations_count'])
            smtp_send(user, passwd, row['email'], subj, html)
            conn2 = db_connect(); cur2 = conn2.cursor()
            cur2.execute("UPDATE leads SET email_status='sent', sent_at=? WHERE id=?",
                         (datetime.utcnow().isoformat(), row['id']))
            conn2.commit(); conn2.close()
            sent += 1
            log.info(f'  Sent [{row["id"]}] {row["company"]} → {row["email"]}')
            if sent < len(leads):
                time.sleep(random.randint(DELAY_MIN, DELAY_MAX))
        except Exception as e:
            log.error(f'  FAIL [{row["id"]}] {row["email"]}: {e}')

# ── 模式 3: send_vip — 主管批准後立即發 ─────────────────────────────

def send_vip(lead_id):
    conn = db_connect(); cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE id=?", (lead_id,))
    row = cur.fetchone(); conn.close()
    if not row:
        log.error(f'send_vip: lead {lead_id} not found'); return False
    user, passwd = get_smtp(row['region'])
    try:
        subj, html = build_customer_email(lead_id, row['tier'], row['industry'],
                                          row['company'], row['contact'], row['region'],
                                          row['locations_count'])
        smtp_send(user, passwd, row['email'], subj, html)
        conn2 = db_connect(); cur2 = conn2.cursor()
        cur2.execute("UPDATE leads SET email_status='sent', sent_at=? WHERE id=?",
                     (datetime.utcnow().isoformat(), lead_id))
        conn2.commit(); conn2.close()
        log.info(f'  VIP sent [{lead_id}] {row["company"]} → {row["email"]}')
        return True
    except Exception as e:
        log.error(f'  FAIL send_vip [{lead_id}]: {e}'); return False

# ── 彙總報告 ──────────────────────────────────────────────────────

def send_report():
    if not os.path.exists(DB_PATH): return
    conn = db_connect(); cur = conn.cursor()
    cur.execute("SELECT email_status, COUNT(*) FROM leads GROUP BY email_status")
    stats = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute("SELECT COUNT(*) FROM leads WHERE email_opened=1")
    opened = cur.fetchone()[0]
    conn.close()

    html = f"""<html><body style="font-family:sans-serif;max-width:500px;margin:0 auto;">
<h2>📊 每日發信報告 — {datetime.now().strftime('%Y-%m-%d')}</h2>
<table style="border-collapse:collapse;width:100%;">
<tr style="background:#1c1c1c;color:#cda85e;"><th style="padding:10px;text-align:left;">狀態</th><th style="padding:10px;text-align:right;">筆數</th></tr>
{''.join(f'<tr style="background:{"#f9f9f9" if i%2 else "white"};"><td style="padding:10px;">{k or "未發送"}</td><td style="padding:10px;text-align:right;">{v}</td></tr>' for i,(k,v) in enumerate(stats.items()))}
<tr style="background:#e8f5e9;"><td style="padding:10px;font-weight:bold;">已開信</td><td style="padding:10px;text-align:right;font-weight:bold;">{opened}</td></tr>
</table>
</body></html>"""
    try:
        smtp_send(SMTP_USER_E, SMTP_PASS_E, REPORT_EMAIL,
                  f'[KLUB 發信報告] {datetime.now().strftime("%Y-%m-%d")}', html)
        log.info('Report sent')
    except Exception as e:
        log.error(f'Report fail: {e}')

# ── 排程主程式 ───────────────────────────────────────────────────────

def daily_job():
    log.info('=== Daily email job start ===')
    vip_notify()
    run_general()
    log.info('=== Daily email job done ===')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'vip_notify':   vip_notify()
        elif cmd == 'run':        run_general()
        elif cmd == 'send_vip' and len(sys.argv) > 2: send_vip(int(sys.argv[2]))
        elif cmd == 'report':     send_report()
        elif cmd == 'once':       daily_job(); send_report()
    else:
        # 台灣 06:00 = UTC 22:00
        schedule.every().day.at('22:00').do(daily_job)
        # 台灣 08:00 = UTC 00:00
        schedule.every().day.at('00:00').do(send_report)
        log.info('Scheduler started. Waiting for 22:00 UTC (06:00 TW)...')
        while True:
            schedule.run_pending()
            time.sleep(60)
