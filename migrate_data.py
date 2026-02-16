import json
import os
from app import app, db, User, RequestRecord, WorkDetail, Notification

def migrate():
    print("🚀 Starting Data Migration (JSON -> SQLite)...")
    
    with app.app_context():
        # Clear existing data to avoid duplicates if rerun
        db.drop_all()
        db.create_all()
        print("✅ Database tables recreated.")

        # 1. Migrate Users
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8') as f:
                users = json.load(f)
                for u in users:
                    new_user = User(
                        username=u['username'],
                        password=u['password'],
                        role=u['role'],
                        name=u.get('name'),
                        title_name=u.get('title_name'),
                        academic_position=u.get('academic_position'),
                        department=u.get('department'),
                        faculty=u.get('faculty'),
                        position_date=u.get('position_date'),
                        position_number=u.get('position_number')
                    )
                    db.session.add(new_user)
            print(f"✅ Migrated {len(users)} users.")

        # 2. Migrate Notifications
        if os.path.exists('notifications.json'):
            with open('notifications.json', 'r', encoding='utf-8') as f:
                notifs = json.load(f)
                for n in notifs:
                    new_notif = Notification(
                        id=n['id'],
                        message=n['message'],
                        recipient_role=n.get('recipient_role'),
                        recipient_username=n.get('recipient_username'),
                        req_id=n.get('req_id'),
                        is_read=n.get('is_read', False),
                        timestamp=n.get('timestamp')
                    )
                    db.session.add(new_notif)
            print(f"✅ Migrated {len(notifs)} notifications.")

        # 3. Migrate Requests & WorkDetails
        if os.path.exists('requests.json'):
            with open('requests.json', 'r', encoding='utf-8') as f:
                reqs = json.load(f)
                for r in reqs:
                    new_req = RequestRecord(
                        id=r['id'],
                        applicant_username=r['applicant'],
                        applicant_name=r['applicant_name'],
                        fiscal_year=r.get('fiscal_year'),
                        status=r.get('status'),
                        date_submitted=r.get('date'),
                        total_score=float(r.get('score', 0) or 0),
                        approved_amount=float(r.get('approved_amount', 0) or 0),
                        comment=r.get('comment', ''),
                        timeline_status=r.get('timeline_status'),
                        batch_id=r.get('batch_id'),
                        applicant_info_json=json.dumps(r.get('applicant_info', {}), ensure_ascii=False)
                    )
                    db.session.add(new_req)
                    
                    # Migrate Works within this Request
                    for idx, w in enumerate(r.get('works', [])):
                        new_work = WorkDetail(
                            request_id=r['id'],
                            work_type=w.get('type'),
                            status=w.get('status'),
                            score_calc=float(w.get('score_calc', 0) or 0),
                            payment_calc=float(w.get('payment_calc', 0) or 0),
                            details_json=json.dumps(w.get('details', {}), ensure_ascii=False)
                        )
                        db.session.add(new_work)
            print(f"✅ Migrated {len(reqs)} requests and their associated works.")

        # Commit everything
        db.session.commit()
        print("\n✨ Migration finished successfully!")
        print("💡 You can now safely backup and remove your .json files.")
        print("💡 Don't forget to update your app.py to use database queries everywhere!")

if __name__ == "__main__":
    migrate()
