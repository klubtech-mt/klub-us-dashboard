import csv
import sqlite3

DB_PATH = "leads.db"
CSV_PATH = r"C:\Users\Owner\Downloads\export.csv"

conn = sqlite3.connect(DB_PATH)

existing = set()
for company, city in conn.execute("SELECT company, city FROM leads"):
    existing.add((company or "", city or ""))

before = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

rows = []
with open(CSV_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        key = (row["company"] or "", row["city"] or "")
        if key in existing:
            continue
        existing.add(key)
        rows.append((
            row["company"] or None,
            row["industry"] or None,
            row["city"] or None,
            row["state"] or None,
            row["region"] or None,
            row["contact"] or None,
            row["title"] or None,
            row["email"] or None,
            row["phone"] or None,
            row["website"] or None,
            row["linkedin"] or None,
            row["tier"] or None,
            int(row["reviews"]) if row["reviews"] else None,
            row["employees"] or None,
            int(row["locations"]) if row["locations"] else None,
            row["source"] or None,
        ))

conn.executemany("""
INSERT INTO leads (company, industry, city, state, region, contact, title,
                    email, phone, website, linkedin, tier, reviews, employees,
                    locations_count, source)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", rows)

conn.commit()
after = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
print(f"before={before}, added={len(rows)}, after={after}")
conn.close()
