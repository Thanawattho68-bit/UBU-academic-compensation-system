"""
routes/main.py
Route หน้าหลัก: index, dashboard, notifications, appeals
ผู้รับผิดชอบ:
  - นางสาวฐิติรัตน์ แสงห้าว 68114540166 (หน้าแรก / ค้นหาคำขอ)
  - นายฤทธิชัย โลมะกาล 68114540533 (แจ้งเตือน)
  - นางสาวเบญจมาศ จ่านันท์ 68114540344 (ยื่นอุทธรณ์)
  - นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (สรุปยอดรวมของระบบ / ผู้ตรวจสอบ)
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from database import query_db, execute_db
from utils import load_data, format_thai_date, get_current_fiscal_year

main_bp = Blueprint('main', __name__)


@main_bp.route('/') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว 68114540166 (หน้าแรก)
def index():
    if 'username' in session: return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard') # ผู้รับผิดชอบ: นางสาวฐิติรัตน์ แสงห้าว 68114540166 (ค้นหาคำขอ)
def dashboard():
    if 'username' not in session: return redirect(url_for('auth.login'))
    
    role = session['role']
    username = session['username']
    
    # ลบข้อมูลที่สถานะเป็น 'ยกเลิก' ออกจากฐานข้อมูลอัตโนมัติตามความต้องการของระบบ
    execute_db("DELETE FROM RequestRecord WHERE status = 'ยกเลิก'")
    
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
        r['works'] = json.loads(r['works_json']) if r.get('works_json') else []
        r['applicant_info'] = json.loads(r['applicant_info_json']) if r.get('applicant_info_json') else {}
        r['applicant'] = r['applicant_username']
        r['date'] = r['date_submitted']
        r['score'] = r['total_score']
        display_reqs.append(r)
    
    # กรองรายการที่รอเสนอพิจารณา (เฉพาะสำหรับสิทธิ์ administration)
    pending_reqs = []
    if role == 'administration':
        pending_reqs = [r for r in display_reqs if r.get('status') == 'รอเสนอพิจารณา']
    
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
                           batches=[], # Remove batches
                           pending_reqs=pending_reqs, 
                           users=all_users)


@main_bp.route('/api/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โลมะกาล 68114540533 (แจ้งเตือน)
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


@main_bp.route('/api/notifications/read/<notif_id>', methods=['POST']) # ผู้รับผิดชอบ: นายฤทธิชัย โลมะกาล 68114540533 (แจ้งเตือน)
def read_notification(notif_id):
    if 'username' not in session: return jsonify({"success": False})
    execute_db('UPDATE Notification SET is_read = 1 WHERE id = ?', (notif_id,))
    return jsonify({"success": True})


@main_bp.route('/notifications') # ผู้รับผิดชอบ: นายฤทธิชัย โลมะกาล 68114540533 (แจ้งเตือน)
def notifications_page():
    if 'username' not in session: return redirect(url_for('auth.login'))
    
    # Get from DB
    notifs_rows = query_db('''
        SELECT * FROM Notification 
        WHERE recipient_username = ? OR (recipient_role = ?)
        ORDER BY timestamp DESC
    ''', (session['username'], session['role']))
    
    user_notifs = [dict(n) for n in notifs_rows]
    
    return render_template('notifications.html', name=session['name'], role=session['role'], position=session.get('position',''), notifications=user_notifs)


@main_bp.route('/appeals') # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ 68114540344 (ยื่นอุทธรณ์)
def appeals_page():
    if 'username' not in session or session['role'] not in ['committee', 'applicant']:
        return redirect(url_for('auth.login'))
    
    if session['role'] == 'committee':
        rows = query_db('SELECT * FROM RequestRecord WHERE status IN (?, ?, ?, ?)', 
                       ('รอการอุทธรณ์', 'ยื่นอุทธรณ์', 'กำลังพิจารณาอุทธรณ์', 'รอพิจารณาอุทธรณ์'))
    else:
        rows = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND status = ?', 
                       (session['username'], 'รอการอุทธรณ์'))
    
    appeal_reqs = []
    for row in rows:
        r = dict(row)
        r['works'] = json.loads(r['works_json']) if r.get('works_json') else []
        appeal_reqs.append(r)
    
    return render_template('appeals.html', name=session['name'], role=session['role'], position=session.get('position',''), requests=appeal_reqs)


@main_bp.route('/summary') # ผู้รับผิดชอบ: นายกฤษดา ตะเคียนเกลี้ยง 68114540065 (สรุปยอดรวมของระบบ)
def summary_page():
    if 'username' not in session: return redirect(url_for('auth.login'))
    
    # จำกัดสิทธิ์เฉพาะเจ้าหน้าที่และกรรมการเท่านั้น
    if session['role'] in ['applicant', 'research']:
        flash("คุณไม่มีสิทธิ์เข้าถึงหน้าสรุปยอดรวม")
        return redirect(url_for('main.dashboard'))
    
    # Get available fiscal years for the filter
    all_fy_rows = query_db('SELECT DISTINCT fiscal_year FROM RequestRecord ORDER BY fiscal_year DESC')
    available_years = [r['fiscal_year'] for r in all_fy_rows if r['fiscal_year']]
    
    # Get selected fiscal year from query string, default to current fiscal year
    selected_year = request.args.get('year')
    current_fy = str(get_current_fiscal_year())
    
    if not selected_year:
        selected_year = current_fy
    
    # Ensure current_fy is in available_years for the filter UI
    if current_fy not in available_years:
        available_years.insert(0, current_fy)
        available_years = sorted(list(set(available_years)), reverse=True)

    # Get stats for the selected year
    total_requests = query_db('SELECT COUNT(*) as count FROM RequestRecord WHERE fiscal_year = ? AND status != ?', (selected_year, 'แบบร่าง'), one=True)['count']
    approved_requests = query_db('SELECT COUNT(*) as count FROM RequestRecord WHERE status = ? AND fiscal_year = ?', ('อนุมัติ', selected_year), one=True)['count']
    pending_requests = query_db('SELECT COUNT(*) as count FROM RequestRecord WHERE status NOT IN (?, ?, ?, ?) AND fiscal_year = ?', ('อนุมัติ', 'ไม่อนุมัติ', 'ยกเลิก', 'แบบร่าง', selected_year), one=True)['count']
    total_amount = query_db('SELECT SUM(approved_amount) as total FROM RequestRecord WHERE status = ? AND fiscal_year = ?', ('อนุมัติ', selected_year), one=True)['total'] or 0
    
    # Get requests for summary table for the selected year (Exclude 'แบบร่าง' from summary)
    query = 'SELECT id, applicant_name, status, total_score, approved_amount, date_submitted FROM RequestRecord WHERE fiscal_year = ? AND status != ? ORDER BY date_submitted DESC'
    requests_rows = query_db(query, (selected_year, 'แบบร่าง'))
    requests = [dict(r) for r in requests_rows]
    
    # ──────────────────────────────────────────────
    # สถิติตามตำแหน่งวิชาการ (ผศ./รศ./ศ.)
    # ──────────────────────────────────────────────
    academic_query = '''
        SELECT rr.status, a.academic_position
        FROM RequestRecord rr
        JOIN Account a ON rr.applicant_username = a.username
        WHERE rr.fiscal_year = ? AND rr.status != ?
    '''
    academic_rows = query_db(academic_query, (selected_year, 'แบบร่าง'))
    
    academic_stats = {
        'ผศ.': {'total': 0, 'approved': 0, 'rejected': 0},
        'รศ.': {'total': 0, 'approved': 0, 'rejected': 0},
        'ศ.': {'total': 0, 'approved': 0, 'rejected': 0}
    }
    
    for row in academic_rows:
        status = row['status']
        pos_raw = row['academic_position']
        
        # Parse positions list
        positions = []
        if pos_raw:
            try:
                positions = json.loads(pos_raw)
                if not isinstance(positions, list): positions = [positions]
            except:
                positions = [pos_raw]
        
        # Categorize
        category = None
        for p in positions:
            if p == 'ศาสตราจารย์': category = 'ศ.'
            elif p == 'รองศาสตราจารย์': category = 'รศ.'
            elif p == 'ผู้ช่วยศาสตราจารย์': category = 'ผศ.'
            if category: break
            
        if category:
            academic_stats[category]['total'] += 1
            if status == 'อนุมัติ':
                academic_stats[category]['approved'] += 1
            elif status == 'ไม่อนุมัติ':
                academic_stats[category]['rejected'] += 1
                
    return render_template('summary.html', 
                           name=session['name'], 
                           role=session['role'], 
                           position=session.get('position',''),
                           total_requests=total_requests,
                           approved_requests=approved_requests,
                           pending_requests=pending_requests,
                           total_amount=total_amount,
                           requests=requests,
                           available_years=available_years,
                           selected_year=selected_year,
                           academic_stats=academic_stats)



