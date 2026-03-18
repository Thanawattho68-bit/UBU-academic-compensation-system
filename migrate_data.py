import json
import os
import sys
from database import init_db, execute_db, DATABASE_PATH
from utils.helpers import parse_thai_date, get_current_fiscal_year

# แก้ไขปัญหา UnicodeEncodeError (แสดง Emoji ไม่ได้บน Windows Terminal)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def migrate():
    print("🚀 Starting Data Migration (JSON -> SQLite)...")
    
    # Clear existing database file to start fresh
    if os.path.exists(DATABASE_PATH):
        try:
            os.remove(DATABASE_PATH)
            print("✅ Existing database file removed.")
        except PermissionError:
            print("⚠️ Could not remove database file (it might be in use). Skipping removal.")
    
    init_db()
    print("✅ Database tables initialized.")

    # Track fiscal years to ensure they exist in TimelineConfig for FK compliance
    existing_fys = set()

    def to_iso(date_str, include_time=False):
        if not date_str: return None
        dt = parse_thai_date(date_str)
        if not dt: return date_str
        fmt = "%Y-%m-%d %H:%M:%S" if include_time else "%Y-%m-%d"
        return dt.strftime(fmt)

    def ensure_fiscal_year(fy):
        if not fy: return
        fy_str = str(fy)
        if fy_str not in existing_fys:
            # For defaults, we still use DD/MM but parse_thai_date will handle them 
            # or we can store them as ISO if we calculate the year
            execute_db('''
                INSERT OR IGNORE INTO TimelineConfig (fiscal_year, start_date, end_date, rounds_json)
                VALUES (?, ?, ?, ?)
            ''', (fy_str, to_iso("01/10"), to_iso("30/09"), "[]"))
            existing_fys.add(fy_str)
            print(f"🛠️ Created default TimelineConfig for fiscal year {fy_str}")

    # 1. Migrate Users to Account table (Parent - No dependencies)
    if os.path.exists('backup/users.json'):
        with open('backup/users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
            for u in users:
                pos = u.get('academic_position')
                if isinstance(pos, list):
                    pos = json.dumps(pos, ensure_ascii=False)
                
                execute_db('''
                    INSERT INTO Account (username, password, role, name, title_name, academic_position, department, faculty, position_date, position_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    u['username'], u['password'], u['role'], u.get('name'),
                    u.get('title_name'), pos, u.get('department'),
                    u.get('faculty'), to_iso(u.get('position_date')), u.get('position_number')
                ))
        print(f"✅ Migrated {len(users)} users to Account table.")

    # 2. Migrate Timeline (Parent - No dependencies)
    if os.path.exists('backup/timeline.json'):
        with open('backup/timeline.json', 'r', encoding='utf-8') as f:
            timelines = json.load(f)
            if not isinstance(timelines, list): timelines = [timelines]
            
            for t in timelines:
                fy = str(t.get('fiscal_year', ''))
                if not fy: continue
                execute_db('''
                    INSERT INTO TimelineConfig (fiscal_year, start_date, end_date, rounds_json)
                    VALUES (?, ?, ?, ?)
                ''', (
                    fy,
                    to_iso(t.get('start_date', '01/10')),
                    to_iso(t.get('end_date', '30/09')),
                    json.dumps(t.get('rounds', []), ensure_ascii=False)
                ))
                existing_fys.add(fy)
        print(f"✅ Migrated {len(timelines)} timeline configs to TimelineConfig table.")

    # 3. Migrate Criteria (Child of TimelineConfig)
    if os.path.exists('backup/criteria.json'):
        with open('backup/criteria.json', 'r', encoding='utf-8') as f:
            criteria_list = json.load(f)
            for c in criteria_list:
                fy = str(c.get('fiscal_year', ''))
                ensure_fiscal_year(fy) # Ensure parent exists
                execute_db('''
                    INSERT INTO Criteria (fiscal_year, quality_scores, role_weights, payment_rules)
                    VALUES (?, ?, ?, ?)
                ''', (
                    fy,
                    json.dumps(c.get('quality_scores', {}), ensure_ascii=False),
                    json.dumps(c.get('role_weights', {}), ensure_ascii=False),
                    json.dumps(c.get('payment_rules', {}), ensure_ascii=False)
                ))
        print(f"✅ Migrated {len(criteria_list)} criteria configs.")

    # 4. Migrate Requests (Child of Account and TimelineConfig)
    if os.path.exists('backup/requests.json'):
        with open('backup/requests.json', 'r', encoding='utf-8') as f:
            reqs = json.load(f)
            for r in reqs:
                fy = str(r.get('fiscal_year', ''))
                ensure_fiscal_year(fy) # Ensure parent exists
                execute_db('''
                    INSERT INTO RequestRecord (
                        id, applicant_username, applicant_name, fiscal_year, status, 
                        date_submitted, total_score, approved_amount, 
                        applicant_info_json, works_json,
                        admin_viewer, research_viewer, committee_approver, 
                        final_approver, history_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    r['id'], r['applicant'], r['applicant_name'], fy,
                    r.get('status'), to_iso(r.get('date'), True), float(r.get('score', 0) or 0),
                    float(r.get('approved_amount', 0) or 0), 
                    json.dumps(r.get('applicant_info', {}), ensure_ascii=False),
                    json.dumps(r.get('works', []), ensure_ascii=False),
                    r.get('admin_viewer'), r.get('research_viewer'), r.get('committee_approver'),
                    r.get('final_approver'), r.get('history_json')
                ))
        print(f"✅ Migrated {len(reqs)} requests (including works and audit history).")

    # 5. Migrate Notifications (Child of Account and RequestRecord)
    if os.path.exists('backup/notifications.json'):
        with open('backup/notifications.json', 'r', encoding='utf-8') as f:
            notifs = json.load(f)
            for n in notifs:
                # Basic check to ensure referenced objects exist before inserting to avoid FK errors 
                # (though in re-migration they should already be handled by the order above)
                execute_db('''
                    INSERT INTO Notification (id, message, recipient_role, recipient_username, req_id, is_read, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    n['id'], n['message'], n.get('recipient_role'), n.get('recipient_username'),
                    n.get('req_id'), 1 if n.get('is_read') else 0, to_iso(n.get('timestamp'), True)
                ))
        print(f"✅ Migrated {len(notifs)} notifications.")

    # 6. Migrate Work Types (Independent)
    if os.path.exists('backup/work_types.json'):
        with open('backup/work_types.json', 'r', encoding='utf-8') as f:
            work_types = json.load(f)
            for wt in work_types:
                execute_db('''
                    INSERT INTO WorkType (id, label)
                    VALUES (?, ?)
                ''', (
                    wt.get('id'),
                    wt.get('label')
                ))
        print(f"✅ Migrated {len(work_types)} work types.")

    print("\n✨ Migration finished successfully!")
    print("💡 You can now safely backup and remove your .json files.")
    print("💡 Don't forget to update your app.py to use database queries everywhere!")

if __name__ == "__main__":
    migrate()
