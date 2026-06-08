import sqlite3
import os
import sys
import traceback

try:
    from flask import Flask, render_template_string, request
except Exception as _e:
    with open("/tmp/startup_error.log", "a") as _f:
        _f.write("=== IMPORT ERROR ===\n")
        traceback.print_exc(file=_f)
    raise

try:
    app = Flask(__name__)
    DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "leads.db"))
except Exception as _e:
    with open("/tmp/startup_error.log", "a") as _f:
        _f.write("=== APP INIT ERROR ===\n")
        traceback.print_exc(file=_f)
    raise

HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>Leads Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #333; font-size: 14px; }
header { background: #1a1a2e; color: white; padding: 16px 32px; display:flex; align-items:center; justify-content:space-between; }
header h1 { font-size: 1.4rem; }
header p  { font-size: 0.8rem; color: #aaa; }

.container { max-width: 1400px; margin: 24px auto; padding: 0 20px; }

/* 統計卡片 */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 24px; }
.card { background: white; border-radius: 10px; padding: 16px 20px; box-shadow: 0 2px 6px rgba(0,0,0,.07); }
.card .num   { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
.card .label { font-size: 0.78rem; color: #888; margin-top: 4px; }

/* 篩選列 */
.filters { background: white; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px;
           box-shadow: 0 2px 6px rgba(0,0,0,.07); display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.filter-group { display: flex; flex-direction: column; gap: 4px; }
.filter-group label { font-size: 0.75rem; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.filter-group select,
.filter-group input  { padding: 7px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px;
                        background: white; min-width: 160px; outline: none; }
.filter-group select:focus,
.filter-group input:focus { border-color: #4f8ef7; }
.btn { padding: 7px 18px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
.btn-primary { background: #4f8ef7; color: white; }
.btn-primary:hover { background: #3a7ae0; }
.btn-reset   { background: #eee; color: #555; }
.btn-reset:hover { background: #ddd; }

/* 表格 */
.table-wrap { background: white; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,.07); overflow-x: auto; }
.table-meta { padding: 12px 20px; font-size: 12px; color: #888; border-bottom: 1px solid #f0f0f0; }
table { width: max-content; min-width: 100%; border-collapse: collapse; table-layout: fixed; }
th { background: #f7f8fa; padding: 8px 10px; text-align: left; font-size: 12px; font-weight: 700;
     color: #555; cursor: pointer; user-select: none; white-space: nowrap; border-bottom: 2px solid #e8e8e8; }
th:hover { background: #eef0f4; }
th .sort-icon { margin-left: 4px; color: #bbb; font-size: 10px; }
th.asc  .sort-icon::after { content: ' ▲'; color: #4f8ef7; }
th.desc .sort-icon::after { content: ' ▼'; color: #4f8ef7; }
th:not(.asc):not(.desc) .sort-icon::after { content: ' ⇅'; }
/* 各欄固定寬度 */
th:nth-child(1), td:nth-child(1)  { width: 160px; } /* 公司 */
th:nth-child(2), td:nth-child(2)  { width: 160px; } /* 產業 */
th:nth-child(3), td:nth-child(3)  { width:  90px; } /* 城市 */
th:nth-child(4), td:nth-child(4)  { width:  50px; } /* 州 */
th:nth-child(5), td:nth-child(5)  { width: 120px; } /* 聯絡人 */
th:nth-child(6), td:nth-child(6)  { width: 150px; } /* 職稱 */
th:nth-child(7), td:nth-child(7)  { width: 190px; } /* Email */
th:nth-child(8), td:nth-child(8)  { width: 120px; } /* 電話 */
th:nth-child(9), td:nth-child(9)  { width:  70px; } /* Tier */
th:nth-child(10),td:nth-child(10) { width:  70px; } /* 評論數 */
th:nth-child(11),td:nth-child(11) { width:  55px; } /* 網站 */
th:nth-child(12),td:nth-child(12) { width:  65px; } /* LinkedIn */
td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top;
     white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
tr:hover td { background: #fafbff; }
.badge { display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
.vip     { background:#fff3cd; color:#856404; }
.general { background:#e8f4fd; color:#0c5499; }
.tag-email { color: #2ecc71; font-size:12px; }
.no-data { text-align: center; padding: 40px; color: #aaa; }
a.link { color: #4f8ef7; text-decoration: none; font-size: 12px; }
a.link:hover { text-decoration: underline; }
</style>
</head>
<body>
<header>
  <div><h1>US Leads Dashboard</h1><p>資料庫：leads.db &nbsp;|&nbsp; {{ now }}</p></div>
  <div style="color:#aaa;font-size:12px;">共 {{ total_all }} 筆資料</div>
</header>

<div class="container">
  <!-- 統計卡片 -->
  <div class="stats">
    <div class="card"><div class="num">{{ total_all }}</div><div class="label">總筆數</div></div>
    <div class="card"><div class="num">{{ with_email }}</div><div class="label">有 Email</div></div>
    <div class="card"><div class="num">{{ with_contact }}</div><div class="label">有聯絡人</div></div>
    <div class="card"><div class="num" style="color:#856404;">{{ vip_count }}</div><div class="label">VIP</div></div>
    <div class="card"><div class="num" style="color:#0c5499;">{{ general_count }}</div><div class="label">GENERAL</div></div>
    <div class="card"><div class="num">{{ city_count }}</div><div class="label">城市數</div></div>
    <div class="card"><div class="num">{{ industry_count }}</div><div class="label">產業數</div></div>
  </div>

  <!-- 篩選列 -->
  <form class="filters" method="GET" action="/">
    <div class="filter-group">
      <label>產業</label>
      <select name="industry">
        <option value="">全部產業</option>
        {% for ind in industries %}
        <option value="{{ ind }}" {% if filters.industry == ind %}selected{% endif %}>{{ ind }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-group">
      <label>城市</label>
      <select name="city">
        <option value="">全部城市</option>
        {% for c in cities %}
        <option value="{{ c }}" {% if filters.city == c %}selected{% endif %}>{{ c }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="filter-group">
      <label>Tier</label>
      <select name="tier">
        <option value="">全部</option>
        <option value="VIP"     {% if filters.tier == 'VIP'     %}selected{% endif %}>VIP</option>
        <option value="GENERAL" {% if filters.tier == 'GENERAL' %}selected{% endif %}>GENERAL</option>
      </select>
    </div>
    <div class="filter-group">
      <label>公司名稱</label>
      <input type="text" name="q" placeholder="搜尋公司..." value="{{ filters.q }}">
    </div>
    <div class="filter-group">
      <label>Email</label>
      <select name="has_email">
        <option value="">全部</option>
        <option value="1" {% if filters.has_email == '1' %}selected{% endif %}>有 Email</option>
        <option value="0" {% if filters.has_email == '0' %}selected{% endif %}>無 Email</option>
      </select>
    </div>
    <div style="display:flex;gap:8px;align-items:flex-end;">
      <button class="btn btn-primary" type="submit">套用篩選</button>
      <a href="/" class="btn btn-reset">重置</a>
    </div>
  </form>

  <!-- 結果表格 -->
  <div class="table-wrap">
    <div class="table-meta">找到 <strong>{{ result_count }}</strong> 筆結果（點擊欄位標題排序）</div>
    <table id="leads-table">
      <thead>
        <tr>
          {% set cols = [('company','公司'),('industry','產業'),('city','城市'),('state','州'),
                         ('contact','聯絡人'),('title','職稱'),('email','Email'),
                         ('phone','電話'),('tier','Tier'),('reviews','評論數')] %}
          {% for col, label in cols %}
          <th data-col="{{ col }}" onclick="sortTable(this)"
              class="{{ 'asc' if sort==col and order=='asc' else 'desc' if sort==col and order=='desc' else '' }}">
            {{ label }}<span class="sort-icon"></span>
          </th>
          {% endfor %}
          <th>網站</th>
          <th>LinkedIn</th>
        </tr>
      </thead>
      <tbody>
        {% if rows %}
          {% for r in rows %}
          <tr>
            <td title="{{ r.company }}">{{ r.company or '' }}</td>
            <td title="{{ r.industry }}">{{ r.industry or '' }}</td>
            <td>{{ r.city or '' }}</td>
            <td>{{ r.state or '' }}</td>
            <td title="{{ r.contact }}">{{ r.contact or '' }}</td>
            <td title="{{ r.title }}">{{ r.title or '' }}</td>
            <td>
              {% if r.email %}
              <span class="tag-email">✉</span> {{ r.email }}
              {% endif %}
            </td>
            <td>{{ r.phone or '' }}</td>
            <td>
              {% if r.tier %}
              <span class="badge {{ 'vip' if r.tier=='VIP' else 'general' }}">{{ r.tier }}</span>
              {% endif %}
            </td>
            <td>{{ r.reviews or '' }}</td>
            <td>{% if r.website %}<a class="link" href="{{ r.website }}" target="_blank">連結</a>{% endif %}</td>
            <td>{% if r.linkedin %}<a class="link" href="{{ r.linkedin }}" target="_blank">連結</a>{% endif %}</td>
          </tr>
          {% endfor %}
        {% else %}
          <tr><td colspan="12" class="no-data">沒有符合條件的資料</td></tr>
        {% endif %}
      </tbody>
    </table>
  </div>
</div>

<script>
function sortTable(th) {
  const col   = th.dataset.col;
  const cur   = th.classList.contains('asc') ? 'asc' : th.classList.contains('desc') ? 'desc' : '';
  const next  = cur === 'asc' ? 'desc' : 'asc';
  const url   = new URL(window.location.href);
  url.searchParams.set('sort', col);
  url.searchParams.set('order', next);
  window.location.href = url.toString();
}
</script>
</body>
</html>
"""

ALLOWED_SORT = {"company","industry","city","state","contact","title","email","phone","tier","reviews"}

DB_EXISTS = os.path.exists(DB_PATH)

def query(sql, params=()):
    if not DB_EXISTS:
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def query_one(sql, params=()):
    if not DB_EXISTS:
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        val = conn.execute(sql, params).fetchone()
        conn.close()
        return val[0] if val else 0
    except Exception:
        return 0

@app.route("/")
def index():
    from datetime import datetime

    # 篩選參數
    industry  = request.args.get("industry", "")
    city      = request.args.get("city", "")
    tier      = request.args.get("tier", "")
    q         = request.args.get("q", "")
    has_email = request.args.get("has_email", "")
    sort      = request.args.get("sort", "company")
    order     = request.args.get("order", "asc")
    if sort not in ALLOWED_SORT:
        sort = "company"
    if order not in ("asc", "desc"):
        order = "asc"

    # 統計卡片（全量）
    total_all    = query_one("SELECT COUNT(*) FROM leads")
    with_email   = query_one("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''")
    with_contact = query_one("SELECT COUNT(*) FROM leads WHERE contact IS NOT NULL AND contact != ''")
    vip_count    = query_one("SELECT COUNT(*) FROM leads WHERE tier = 'VIP'")
    general_count= query_one("SELECT COUNT(*) FROM leads WHERE tier = 'GENERAL'")
    city_count   = query_one("SELECT COUNT(DISTINCT city) FROM leads")
    industry_count = query_one("SELECT COUNT(DISTINCT industry) FROM leads")

    # 下拉選單選項
    industries = [r[0] for r in query("SELECT DISTINCT industry FROM leads WHERE industry IS NOT NULL ORDER BY industry")]
    cities     = [r[0] for r in query("SELECT DISTINCT city FROM leads WHERE city IS NOT NULL ORDER BY city")]

    # 查詢條件
    where, params = [], []
    if industry:
        where.append("industry = ?"); params.append(industry)
    if city:
        where.append("city = ?"); params.append(city)
    if tier:
        where.append("tier = ?"); params.append(tier)
    if q:
        where.append("company LIKE ?"); params.append(f"%{q}%")
    if has_email == "1":
        where.append("email IS NOT NULL AND email != ''")
    elif has_email == "0":
        where.append("(email IS NULL OR email = '')")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""SELECT company, industry, city, state, contact, title, email,
                     phone, website, linkedin, tier, reviews
              FROM leads {where_sql}
              ORDER BY {sort} {order}
              LIMIT 500"""
    rows = query(sql, params)
    result_count = query_one(f"SELECT COUNT(*) FROM leads {where_sql}", params)

    return render_template_string(HTML,
        total_all=total_all, with_email=with_email, with_contact=with_contact,
        vip_count=vip_count, general_count=general_count,
        city_count=city_count, industry_count=industry_count,
        industries=industries, cities=cities,
        rows=rows, result_count=result_count,
        filters={"industry": industry, "city": city, "tier": tier, "q": q, "has_email": has_email},
        sort=sort, order=order,
        now=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8080))
        print(f"Dashboard 啟動中：http://localhost:{port}")
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as _e:
        with open("/tmp/startup_error.log", "a") as _f:
            _f.write("=== RUNTIME ERROR ===\n")
            traceback.print_exc(file=_f)
        raise
