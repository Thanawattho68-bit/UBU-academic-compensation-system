import json
import os
from database import init_db, execute_db, DATABASE_PATH

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
    print("✅ Database tables recreated.")

    # 1. Migrate Users
    if os.path.exists('users.json'):
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
            for u in users:
                execute_db('''
                    INSERT INTO User (username, password, role, name, title_name, academic_position, department, faculty, position_date, position_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    u['username'], u['password'], u['role'], u.get('name'),
                    u.get('title_name'), u.get('academic_position'), u.get('department'),
                    u.get('faculty'), u.get('position_date'), u.get('position_number')
                ))
        print(f"✅ Migrated {len(users)} users.")

    # 2. Migrate Notifications
    if os.path.exists('notifications.json'):
        with open('notifications.json', 'r', encoding='utf-8') as f:
            notifs = json.load(f)
            for n in notifs:
                execute_db('''
                    INSERT INTO Notification (id, message, recipient_role, recipient_username, req_id, is_read, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    n['id'], n['message'], n.get('recipient_role'), n.get('recipient_username'),
                    n.get('req_id'), 1 if n.get('is_read') else 0, n.get('timestamp')
                ))
        print(f"✅ Migrated {len(notifs)} notifications.")

    # 3. Migrate Requests & WorkDetails
    if os.path.exists('requests.json'):
        with open('requests.json', 'r', encoding='utf-8') as f:
            reqs = json.load(f)
            for r in reqs:
                execute_db('''
                    INSERT INTO RequestRecord (id, applicant_username, applicant_name, fiscal_year, status, date_submitted, total_score, approved_amount, comment, timeline_status, batch_id, applicant_info_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    r['id'], r['applicant'], r['applicant_name'], r.get('fiscal_year'),
                    r.get('status'), r.get('date'), float(r.get('score', 0) or 0),
                    float(r.get('approved_amount', 0) or 0), r.get('comment', ''),
                    r.get('timeline_status'), r.get('batch_id'),
                    json.dumps(r.get('applicant_info', {}), ensure_ascii=False)
                ))
                
                # Migrate Works within this Request
                for w in r.get('works', []):
                    execute_db('''
                        INSERT INTO WorkDetail (request_id, work_type, status, score_calc, payment_calc, details_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        r['id'], w.get('type'), w.get('status'),
                        float(w.get('score_calc', 0) or 0), float(w.get('payment_calc', 0) or 0),
                        json.dumps(w.get('details', {}), ensure_ascii=False)
                    ))
        print(f"✅ Migrated {len(reqs)} requests and their associated works.")

    # 4. Migrate Criteria
    if os.path.exists('criteria.json'):
        with open('criteria.json', 'r', encoding='utf-8') as f:
            criteria_list = json.load(f)
            for c in criteria_list:
                execute_db('''
                    INSERT INTO Criteria (fiscal_year, quality_scores_json, role_weights_json, payment_rules_json)
                    VALUES (?, ?, ?, ?)
                ''', (
                    c.get('fiscal_year'),
                    json.dumps(c.get('quality_scores', {}), ensure_ascii=False),
                    json.dumps(c.get('role_weights', {}), ensure_ascii=False),
                    json.dumps(c.get('payment_rules', {}), ensure_ascii=False)
                ))
        print(f"✅ Migrated {len(criteria_list)} criteria configs.")

    # 5. Migrate Work Types
    if os.path.exists('work_types.json'):
        with open('work_types.json', 'r', encoding='utf-8') as f:
            work_types = json.load(f)
            for wt in work_types:
                execute_db('''
                    INSERT INTO WorkType (id, label, is_custom)
                    VALUES (?, ?, ?)
                ''', (
                    wt.get('id'),
                    wt.get('label'),
                    1 if wt.get('is_custom') else 0
                ))
        print(f"✅ Migrated {len(work_types)} work types.")

    print("\n✨ Migration finished successfully!")
    print("💡 You can now safely backup and remove your .json files.")
    print("💡 Don't forget to update your app.py to use database queries everywhere!")

if __name__ == "__main__":
    migrate()
