import json
import re
import sqlite3

DB_PATH = "leads.db"

with open("us_lead_enricher_step2_v10.py", encoding="utf-8") as f:
    content = f.read()

m = re.search(r"VIP_INDUSTRIES\s*=\s*\{(.*?)\}", content, re.S)
VIP_INDUSTRIES = set(re.findall(r'"([^"]+)"', m.group(1)))
VIP_EMPLOYEES = int(re.search(r"VIP_EMPLOYEES\s*=\s*(\d+)", content).group(1))


def assign_tier(industry, employees):
    if (industry or "").lower() in VIP_INDUSTRIES:
        return "VIP"
    try:
        emp = int(employees or 0)
    except (ValueError, TypeError):
        emp = 0
    if emp >= VIP_EMPLOYEES:
        return "VIP"
    return "GENERAL"


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# --- Step 1: re-classify tier for the 1905 new rows ---
rows = conn.execute("SELECT id, industry, tier, employees FROM leads WHERE id > 7197").fetchall()
tier_updates = []
for r in rows:
    computed = assign_tier(r["industry"], r["employees"])
    if computed != (r["tier"] or "").upper():
        tier_updates.append((computed, r["id"]))

conn.executemany("UPDATE leads SET tier=? WHERE id=?", tier_updates)
print(f"tier updated: {len(tier_updates)} rows")

# --- Step 2: apply 58-row contact backfill ---
with open("backfill_candidates_20260612_v2.json", encoding="utf-8") as f:
    cands = json.load(f)

backfill_updates = []
for c in cands:
    backfill_updates.append((
        c["website"] or None,
        c["contact"] or None,
        c["title"] or None,
        c["email"] or None,
        c["linkedin"] or None,
        c["id"],
    ))

conn.executemany("""
    UPDATE leads SET website=?, contact=?, title=?, email=?, linkedin=?
    WHERE id=?
""", backfill_updates)
print(f"backfill applied: {len(backfill_updates)} rows")

conn.commit()

# --- verify ---
total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
vip_new = conn.execute("SELECT COUNT(*) FROM leads WHERE id > 7197 AND tier='VIP'").fetchone()[0]
general_new = conn.execute("SELECT COUNT(*) FROM leads WHERE id > 7197 AND tier='GENERAL'").fetchone()[0]
with_email = conn.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''").fetchone()[0]
print(f"\ntotal rows: {total}")
print(f"new rows (id>7197): VIP={vip_new}, GENERAL={general_new}")
print(f"total rows with email: {with_email}")

conn.close()
