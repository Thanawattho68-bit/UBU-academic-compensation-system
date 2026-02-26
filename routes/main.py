"""
routes/main.py
Route หน้าหลัก: index, dashboard, notifications, appeals
ผู้รับผิดชอบ:
  - นางสาวฐิติรัตน์ แสงห้าว (หน้าแรก / ค้นหาคำขอ)
  - นายฤทธิชัย โสนะกาล (แจ้งเตือน)
  - นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import query_db, execute_db
from utils import load_data, format_thai_date

main_bp = Blueprint('main', __name__)


@main_bp.route('/') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว (หน้าแรก)
def index():
    if 'username' in session: return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว (ค้นหาคำขอ)
def dashboard():
    if 'username' not in session: return redirect(url_for('auth.login'))
    
    role = session['role']
    username = session['username']
    
    # ดึงข้อมูลคำขอจาก database โดยกรองตามสิทธิ์การใช้งาน
    if role == 'applicant':
        rows = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ?', (username,))
    elif role in ['administration', 'research', 'committee']:
        # สำหรับเจ้าหน้าที่และกรรมการ ให้เห็นคำขอทั้งหมดที่ไม่ใช่แบบร่าง
        rows = query_db('SELECT * FROM RequestRecord WHERE status != ?', ('แบบร่าง',))
    else:
        rows = []
    
    display_reqs = []
    for row in rows:
        r = dict(row)
        # แปลงข้อมูล JSON ที่เก็บเป็น TEXT ใน DB กลับเป็น Object
        r['works'] = json.loads(r['works_json']) if r.get('works_json') else []
        r['applicant_info'] = json.loads(r['applicant_info_json']) if r.get('applicant_info_json') else {}
        
        # แมพชื่อฟิลด์เพื่อให้เข้ากับตัวแปรที่ template dashboard.html ใช้งาน
        r['applicant'] = r['applicant_username']
        r['date'] = r['date_submitted']
        r['score'] = r['total_score']
        display_reqs.append(r)
    
    # กรองรายการที่รอเสนอพิจารณา (เฉพาะสำหรับสิทธิ์ administration)
    pending_reqs = []
    if role == 'administration':
        pending_reqs = [r for r in display_reqs if r.get('status') == 'รอเสนอพิจารณา']
    
    # ดึงข้อมูลรอบการพิจารณา (Batch) - ยังคงดึงจาก JSON เพื่อความเข้ากันได้กับระบบเดิมที่ยังไม่มี table Batch ใน DB
    batches = load_data('batches.json')
    
    # สำหรับสิทธิ์ admin ดึงข้อมูลรายชื่อผู้ใช้งานทั้งหมด
    all_users = []
    if role == 'admin':
        user_rows = query_db('SELECT * FROM Account')
        all_users = [dict(u) for u in user_rows]
    
    return render_template('dashboard.html', 
                           name=session['name'], 
                           role=role, 
                           position=session.get('position',''), 
                           requests=display_reqs, 
                           batches=batches, 
                           pending_reqs=pending_reqs, 
                           users=all_users)


@main_bp.route('/api/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def get_notifications():
    if 'username' not in session: return jsonify([])
    
    # Query database for notifications
    notifs = query_db('''
        SELECT * FROM Notification 
        WHERE is_read = 0 
        AND (recipient_username = ? OR recipient_role = ?)
        ORDER BY timestamp DESC
    ''', (session['username'], session['role']))
    
    result = []
    for n in notifs:
        result.append({
            "id": n['id'],
            "message": n['message'],
            "req_id": n['req_id'],
            "timestamp": n['timestamp']
        })
    return jsonify(result)


@main_bp.route('/api/notifications/read/<notif_id>', methods=['POST']) # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def read_notification(notif_id):
    if 'username' not in session: return jsonify({"success": False})
    execute_db('UPDATE Notification SET is_read = 1 WHERE id = ?', (notif_id,))
    return jsonify({"success": True})


@main_bp.route('/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โสนะกาล (แจ้งเตือน)
def notifications_page():
    if 'username' not in session: return redirect(url_for('auth.login'))
    notifs = load_data('notifications.json')
    
    # Filter for user
    user_notifs = [
        n for n in notifs 
        if n.get('recipient_username') == session['username'] or
           (n.get('recipient_role') and n.get('recipient_role') == session['role'])
    ]
    
    return render_template('notifications.html', name=session['name'], role=session['role'], position=session.get('position',''), notifications=user_notifs)


@main_bp.route('/appeals') # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
def appeals_page():
    if 'username' not in session or session['role'] not in ['committee', 'applicant']:
        return redirect(url_for('auth.login'))
    
    all_reqs = load_data('requests.json')
    # Filter for appeal statuses
    if session['role'] == 'committee':
        appeal_reqs = [r for r in all_reqs if r.get('status') in ['รอการอุทธรณ์', 'ยื่นอุทธรณ์', 'กำลังพิจารณาอุทธรณ์', 'รอพิจารณาอุทธรณ์']]
    else:
        # Applicant sees their own appeals
        appeal_reqs = [r for r in all_reqs if r['applicant'] == session['username'] and r.get('status') == 'รอการอุทธรณ์']
    
    return render_template('appeals.html', name=session['name'], role=session['role'], position=session.get('position',''), requests=appeal_reqs)
