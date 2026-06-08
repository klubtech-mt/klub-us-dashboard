"""
us_lead_scheduler_v16.py  ──  KLUB × Frastea 美國市場 Lead 爬取排程器
- 台灣時間每天 04:00 觸發（UTC 20:00）
- 每天輪流爬 2 個城市，順序：西岸 → 東岸 → 中部
- 30 天自動停止
- SQLite 累積資料庫
- 每日彙總報告 CSV
- v16: 呼叫 step2_v10，VIP條件含工廠/製造商員工數>50，city_cursor從Boston開始(10)
"""

import os, time, random, logging, json, re, sqlite3, csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import schedule
import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── 常數 ──────────────────────────────────────
OUTPUT_DIR = Path("output")
REPORT_DIR = Path("reports")
OUTPUT_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
DB_FILE    = str(OUTPUT_DIR / "leads.db")
STATE_FILE = str(OUTPUT_DIR / "scheduler_state.json")
MAX_DAYS   = 30

# ── 目標產業關鍵字 ────────────────────────────
TARGET_KEYWORDS = {
    "Food Service Equipment Dealer":              ["food service equipment dealer","commercial kitchen equipment","restaurant equipment dealer","beverage equipment dealer"],
    "Bubble Tea Chain Store":                     ["bubble tea","boba tea","milk tea chain","tea bar","boba shop"],
    "Coffee Cafe Chain Store":                    ["coffee roaster","coffee roastery","specialty coffee","coffee cafe chain"],
    "Tea House Chain Store":                      ["tea house","teahouse","chinese tea house","japanese tea house"],
    "Tea Trading Company":                        ["tea trading","tea importer","tea exporter","tea company","tea supplier"],
    "Tea Wholesaler":                             ["tea wholesaler","tea wholesale","bulk tea","tea distributor"],
    "Beverage Equipment Maintenance and Service": ["beverage equipment repair","coffee machine repair","commercial kitchen repair","beverage equipment service"],
    "Beverage Material Store":                    ["bubble tea supply","boba supply","beverage material","tea supply store","boba ingredients"],
}

SENDER_EMAIL = {
    "East":    "mt08@frastea.com",
    "Central": "mt04@frastea.com",
    "West":    "mt04@frastea.com",
}

# VIP 條件
VIP_INDUSTRIES = set(TARGET_KEYWORDS.keys())
VIP_EMPLOYEES  = 50  # 工廠/製造商員工數 > 50 也算 VIP

# ── 排除關鍵字 ────────────────────────────────
EXCLUDE_KEYWORDS = [
    "personal workshop","franchise","franchisee",
    "cafe","coffee shop","coffee house","coffeehouse",
    "restaurant","bistro","diner","eatery",
    "clark","webstaurant","estella",
]

# ── 城市清單 ──────────────────────────────────
CITIES = [
    # 西岸 (0-7) 已完成
    {"city":"Los Angeles",  "state":"CA","region":"West"},
    {"city":"San Francisco","state":"CA","region":"West"},
    {"city":"San Jose",     "state":"CA","region":"West"},
    {"city":"Irvine",       "state":"CA","region":"West"},
    {"city":"Arcadia",      "state":"CA","region":"West"},
    {"city":"Seattle",      "state":"WA","region":"West"},
    {"city":"Portland",     "state":"OR","region":"West"},
    {"city":"Las Vegas",    "state":"NV","region":"West"},
    # 東岸 (8-13) New York(8), Flushing(9) 已完成，從 Boston(10) 繼續
    {"city":"New York",     "state":"NY","region":"East"},
    {"city":"Flushing",     "state":"NY","region":"East"},
    {"city":"Boston",       "state":"MA","region":"East"},
    {"city":"Washington",   "state":"DC","region":"East"},
    {"city":"Atlanta",      "state":"GA","region":"East"},
    {"city":"Miami",        "state":"FL","region":"East"},
    # 中部 (14-16)
    {"city":"Chicago",      "state":"IL","region":"Central"},
    {"city":"Houston",      "state":"TX","region":"Central"},
    {"city":"Dallas",       "state":"TX","region":"Central"},
]
CITIES_PER_DAY = 2

# ══════════════════════════════════════════════
# SQLite 初始化
# ══════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company     TEXT,
            industry    TEXT,
            city        TEXT,
            state       TEXT,
            region      TEXT,
            contact     TEXT,
            title       TEXT,
            email       TEXT,
            phone       TEXT,
            website     TEXT,
            linkedin    TEXT,
            tier        TEXT,
            reviews     INTEGER,
            employees   INTEGER,
            locations   INTEGER,
            source      TEXT,
            crawl_date  TEXT,
            UNIQUE(company, city, industry)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT UNIQUE,
            cities      TEXT,
            new_count   INTEGER,
            vip_count   INTEGER,
            general_count INTEGER,
            duration_sec  INTEGER,
            day_number  INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_leads(rows: list, crawl_date: str) -> tuple:
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    added = dupes = 0
    for r in rows:
        try:
            c.execute("""
                INSERT INTO leads
                (company,industry,city,state,region,contact,title,email,
                 phone,website,linkedin,tier,reviews,employees,locations,source,crawl_date)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r.get("公司",""), r.get("產業",""), r.get("城市",""),
                r.get("State",""), r.get("東西岸",""), r.get("聯絡人",""),
                r.get("職稱",""), r.get("Email",""), r.get("電話",""),
                r.get("官網",""), r.get("LinkedIn",""), r.get("Tier","GENERAL"),
                int(r.get("Reviews",0) or 0), int(r.get("employees",0) or 0),
                int(r.get("locations_count",1) or 1), r.get("來源",""),
                crawl_date,
            ))
            added += 1
        except sqlite3.IntegrityError:
            dupes += 1
    conn.commit()
    conn.close()
    return added, dupes

def log_crawl(date_str, cities, new, vip, general, duration, day_number):
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO crawl_log
            (date,cities,new_count,vip_count,general_count,duration_sec,day_number)
            VALUES (?,?,?,?,?,?,?)
        """, (date_str, ",".join(cities), new, vip, general, duration, day_number))
        conn.commit()
    except Exception as e:
        log.error(f"log_crawl 失敗：{e}")
    finally:
        conn.close()

def get_total_stats():
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM leads")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE tier='VIP'")
    vip   = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT company) FROM leads")
    companies = c.fetchone()[0]
    conn.close()
    return {"total": total, "vip": vip, "general": total-vip, "companies": companies}

def get_crawl_logs(limit=30):
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
        SELECT date,cities,new_count,vip_count,general_count,duration_sec,day_number
        FROM crawl_log ORDER BY date DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {"date": r[0], "cities": r[1], "new_count": r[2], "vip_count": r[3],
         "general_count": r[4], "duration_sec": r[5], "day_number": r[6]}
        for r in rows
    ]

# ══════════════════════════════════════════════
# 狀態管理
# ══════════════════════════════════════════════
def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    # 預設從 Boston 開始（city_cursor=10）
    return {
        "city_cursor": 10,
        "day_number":  0,
        "start_date":  None,
        "stopped":     False,
    }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ══════════════════════════════════════════════
# 爬取核心
# ══════════════════════════════════════════════
def is_excluded(name):
    name_lower = name.lower()
    return any(kw in name_lower for kw in EXCLUDE_KEYWORDS)

def assign_tier(industry, employees):
    if industry in VIP_INDUSTRIES:
        return "VIP"
    if int(employees or 0) >= VIP_EMPLOYEES:
        return "VIP"
    return "GENERAL"

def google_places_search(keyword, city, state, industry):
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY","")
    if not api_key:
        return []
    url    = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{keyword} in {city} {state}", "language": "en", "key": api_key}
    results = []
    while len(results) < 60:
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            for p in data.get("results",[]):
                name = p.get("name","")
                if is_excluded(name):
                    continue
                results.append({
                    "公司": name, "產業": industry, "城市": city,
                    "State": state, "東西岸": "", "聯絡人": "", "職稱": "",
                    "Email": "", "電話": "", "官網": "", "LinkedIn": "",
                    "Reviews": p.get("user_ratings_total",0),
                    "Rating": p.get("rating",""), "來源": "Google Places",
                })
            next_token = data.get("next_page_token")
            if not next_token: break
            time.sleep(2)
            params = {"pagetoken": next_token, "key": api_key}
        except Exception as e:
            log.error(f"Google Places 失敗 ({city},{keyword}): {e}")
            break
    return results

def scrape_city(city_info):
    city, state, region = city_info["city"], city_info["state"], city_info["region"]
    log.info(f"爬取 {region}: {city}, {state}")
    all_rows = []
    for industry, keywords in TARGET_KEYWORDS.items():
        for kw in keywords:
            rows = google_places_search(kw, city, state, industry)
            for r in rows:
                r["東西岸"] = region
                r["Tier"] = assign_tier(industry, r.get("employees",0))
            all_rows.extend(rows)
            time.sleep(random.uniform(0.5,1.5))
    # 三重去重
    seen, unique = set(), []
    for r in all_rows:
        key = (r["公司"].strip().lower(), r["城市"].strip().lower(), r["產業"].strip().lower())
        if key[0] and key not in seen:
            seen.add(key)
            unique.append(r)
    log.info(f"  → {len(unique)} 筆（去重後）")
    return unique

# ══════════════════════════════════════════════
# 每日彙總報告 CSV
# ══════════════════════════════════════════════
def generate_daily_report(date_str, cities, new_rows, day_number, duration):
    vip     = sum(1 for r in new_rows if r.get("Tier")=="VIP")
    general = len(new_rows) - vip
    stats   = get_total_stats()

    report_path = REPORT_DIR / f"report_{date_str}.csv"
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["KLUB × Frastea 美國市場爬取日報"])
        writer.writerow(["日期", date_str])
        writer.writerow(["執行天數", f"{day_number} / {MAX_DAYS}"])
        writer.writerow(["爬取城市", ", ".join(cities)])
        writer.writerow(["耗時(秒)", duration])
        writer.writerow([])
        writer.writerow(["【本日新增】"])
        writer.writerow(["新增筆數", len(new_rows)])
        writer.writerow(["  VIP",    vip])
        writer.writerow(["  GENERAL",general])
        writer.writerow([])
        writer.writerow(["【累積統計】"])
        writer.writerow(["總筆數",   stats["total"]])
        writer.writerow(["  VIP",    stats["vip"]])
        writer.writerow(["  GENERAL",stats["general"]])
        writer.writerow(["公司數",   stats["companies"]])
        writer.writerow([])
        writer.writerow(["【產業分佈（本日）】"])
        industry_count = {}
        for r in new_rows:
            ind = r.get("產業","")
            industry_count[ind] = industry_count.get(ind,0) + 1
        for ind, cnt in sorted(industry_count.items(), key=lambda x:-x[1]):
            writer.writerow([ind, cnt])
        writer.writerow([])
        writer.writerow(["【本日新增明細】"])
        writer.writerow(["Tier","公司","產業","城市","State","東西岸","Email","來源"])
        for r in new_rows:
            writer.writerow([
                r.get("Tier",""), r.get("公司",""), r.get("產業",""),
                r.get("城市",""), r.get("State",""), r.get("東西岸",""),
                r.get("Email",""), r.get("來源",""),
            ])

    log.info(f"✅ 日報：{report_path}")
    return report_path

# ══════════════════════════════════════════════
# 每日主流程
# ══════════════════════════════════════════════
def daily_job():
    init_db()
    state = load_state()

    if state.get("stopped"):
        log.info("已達 30 天，排程停止。")
        return

    if not state.get("start_date"):
        state["start_date"] = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    state["day_number"] = state.get("day_number",0) + 1
    day_number = state["day_number"]

    if day_number > MAX_DAYS:
        state["stopped"] = True
        save_state(state)
        log.info(f"🛑 已達 {MAX_DAYS} 天，排程自動停止。")
        return

    log.info(f"=== 第 {day_number}/{MAX_DAYS} 天 ===")
    start_time = time.time()

    cursor = state.get("city_cursor", 10)
    today_cities = []
    for _ in range(CITIES_PER_DAY):
        today_cities.append(CITIES[cursor % len(CITIES)])
        cursor += 1
    state["city_cursor"] = cursor
    save_state(state)

    city_names = [c["city"] for c in today_cities]
    log.info(f"今日城市：{city_names}")

    all_rows = []
    for city_info in today_cities:
        rows = scrape_city(city_info)
        all_rows.extend(rows)
        time.sleep(random.uniform(2.0,4.0))

    if not all_rows:
        log.warning("本次無爬取結果")
        return

    tw_now   = datetime.now(timezone(timedelta(hours=8)))
    date_str = tw_now.strftime("%Y-%m-%d")
    ts       = tw_now.strftime("%Y%m%d_%H%M")
    csv_path = f"us_brands_{ts}.csv"
    pd.DataFrame(all_rows).to_csv(csv_path, index=False, encoding="utf-8-sig")

    enriched_rows = all_rows
    try:
        from us_lead_enricher_step2_v10 import run as step2_run
        step2_run(csv_path)
        import glob
        latest_xlsx = sorted(glob.glob(str(OUTPUT_DIR / "us_leads_最新爬取資料彙總_*.xlsx")), reverse=True)
        if latest_xlsx:
            df_new = pd.read_excel(latest_xlsx[0], sheet_name="本次新增")
            enriched_rows = df_new.to_dict("records")
            for r in enriched_rows:
                r["公司"] = str(r.get("公司",""))
                r["Tier"] = str(r.get("Tier","GENERAL"))
    except Exception as e:
        log.error(f"Step2 失敗：{e}")

    added, dupes = save_leads(enriched_rows, date_str)
    log.info(f"SQLite：新增 {added} 筆，重複 {dupes} 筆")

    duration = int(time.time() - start_time)
    vip      = sum(1 for r in enriched_rows if str(r.get("Tier",""))=="VIP")
    general  = len(enriched_rows) - vip

    log_crawl(date_str, city_names, added, vip, general, duration, day_number)
    generate_daily_report(date_str, city_names, enriched_rows, day_number, duration)

    log.info(f"完成！新增:{added} VIP:{vip} GENERAL:{general} 耗時:{duration}秒")

# ══════════════════════════════════════════════
# 排程入口
# ══════════════════════════════════════════════
def start_scheduler():
    init_db()
    schedule.every().day.at("20:00").do(daily_job)
    log.info(f"排程器啟動（UTC 20:00 = 台灣時間 04:00），共 {MAX_DAYS} 天")
    daily_job()  # 首次立刻執行
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    start_scheduler()
