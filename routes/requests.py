"""
routes/requests.py
จัดการ route เกี่ยวกับการยื่นคำขอ ดูคำขอ และอุทธรณ์
ผู้รับผิดชอบ:
  - นายธนวรรธ ทองตื้อ 68114540258 (ผู้ยื่น/แบบฟอร์ม)
  - นายศุกลวัฒณ์ ไกรษี 68114540629 (ตรวจสอบคำขอ)
  - นางสาวเบญจมาศ จ่านันท์ 68114540344 (ยื่นอุทธรณ์)
"""

import json
import os
import shutil
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from database import query_db, execute_db
from utils import (
    to_thai_year, format_thai_date,
    is_within_timeline, get_remaining_days, get_current_fiscal_year,
    allowed_file, create_notification, calculate_compensation, recalculate_total_only,
    deserialize_request, parse_academic_position, parse_criteria_row,
)
from utils.constants import STATUS_DRAFT, STATUS_EDIT, STATUS_SUBMITTED, STATUS_WAIT_HISTORY, STATUS_PENDING, STATUS_APPEAL, STATUS_REJECTED
from .request_handlers import (
    log_history,
    handle_applicant,
    handle_administration,
    handle_research,
    handle_committee,
)

requests_bp = Blueprint('requests', __name__)


@requests_bp.route('/view_work/<req_id>/<int:work_index>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุกลวัฒณ์ ไกรษี 68114540629 (ตรวจสอบคำขอ)
def view_work(req_id, work_index):
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    row = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not row:
        return "Request not found", 404
    req = deserialize_request(row)
    if work_index < 0 or work_index >= len(req.get('works', [])):
        flash("ไม่พบรายการผลงานที่ต้องการ")
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        if session['role'] != 'administration':
            flash("คุณไม่มีสิทธิ์แก้ไขข้อมูลนี้")
            return redirect(url_for('requests.view_work', req_id=req_id, work_index=work_index))
        
        # Admin is updating work details
        work = req['works'][work_index]
        
        # Update details based on work type
        if work['type'] in ['social', 'industry', 'teaching', 'policy', 'innovation'] or work['type'].startswith('custom_'):
            if 'level' in request.form:
                work['details']['level'] = request.form.get('level')
            
        # Recalculate compensation
        new_total_score, new_total_comp = calculate_compensation(
            req['works'], 
            req['applicant_info'].get('academic_position', ''),
            req.get('fiscal_year', '')
        )
        
        execute_db('''
            UPDATE RequestRecord SET works_json = ?, total_score = ?, approved_amount = ? 
            WHERE id = ?
        ''', (json.dumps(req['works'], ensure_ascii=False), new_total_score, new_total_comp, req_id))

        flash("แก้ไขข้อมูลผลงานและคำนวณคะแนนใหม่เรียบร้อยแล้ว")
        return redirect(url_for('requests.view_work', req_id=req_id, work_index=work_index))

    # Get the user info from DB
    applicant_user = dict(query_db('SELECT * FROM Account WHERE username = ?', (req['applicant_username'],), one=True) or {})

    # Authorization Check
    if session['role'] == 'applicant' and req['applicant_username'] != session['username']:
        flash("คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้")
        return redirect(url_for('main.dashboard'))
    
    return render_template('view_work.html', 
                          name=session['name'], 
                          role=session['role'], 
                          position=session.get('position', ''),
                          req=req,
                          user=applicant_user,
                          work_index=work_index)


@requests_bp.route('/new_request', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ 68114540258 (ผู้ยื่น/แบบฟอร์ม)
def new_request():
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('auth.login'))

    can_submit = is_within_timeline()[0]  # Returns (is_open, reason, next_open)
    fiscal_year = get_current_fiscal_year()
    
    # Load Basic Info from DB
    raw_criteria = query_db('SELECT * FROM Criteria')
    criteria_list = [parse_criteria_row(c) for c in raw_criteria]
        
    user_profile = dict(query_db('SELECT * FROM Account WHERE username = ?', (session['username'],), one=True) or {})
    if user_profile:
        user_profile['academic_position'] = parse_academic_position(user_profile.get('academic_position'))

    work_types = [dict(wt) for wt in query_db('SELECT * FROM WorkType')]

    # Check for edit mode
    edit_id = request.args.get('edit_id')
    edit_req = None
    if edit_id:
        row = query_db('SELECT * FROM RequestRecord WHERE id = ? AND applicant_username = ?', (edit_id, session['username']), one=True)
        if row:
            edit_req = deserialize_request(row)
    else:
        # Enforce one submission per year rule
        existing_req = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND fiscal_year = ?', (session['username'], str(fiscal_year)), one=True)
        if existing_req:
            if existing_req['status'] == STATUS_DRAFT:
                return redirect(url_for('requests.new_request', edit_id=existing_req['id']))
            else:
                flash("คุณได้ยื่นคำขอไปแล้วในปีงบประมาณนี้")
                return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        action, now_dt = request.form.get('action'), datetime.now()
        if action == 'submit' and not can_submit:
             # Check if this is a resubmission of a returned request
             is_resubmission = False
             if edit_req and edit_req.get('status') == STATUS_EDIT:
                 is_resubmission = True
             
             if not is_resubmission:
                 flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
                 return redirect(url_for('requests.new_request', edit_id=edit_id))

        req_id = request.form.get('req_id') or f"REQ-{now_dt.year + 543}{now_dt.strftime('%m%d%H%M%S')}"
        try:
            works = json.loads(request.form.get('works_data', '[]'))
        except (json.JSONDecodeError, TypeError):
            flash("ข้อมูลฟอร์มไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")
            return redirect(url_for('requests.new_request', edit_id=edit_id))

        # Handle Files
        for w in works:
            work_id = w.get('details', {}).get('id')
            file = request.files.get(f'evidence_file_{work_id}')
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], req_id, str(work_id))
                os.makedirs(save_dir, exist_ok=True)
                file.save(os.path.join(save_dir, filename))
                w['details'].update({'evidence_type': 'file', 'evidence_file': filename})

        if action == 'submit' and any(not (w.get('details', {}).get('evidence_url') or w.get('details', {}).get('evidence_file')) for w in works):
            flash("กรุณาแนบหลักฐานให้ครบถ้วน"); return redirect(url_for('requests.new_request', edit_id=edit_id if edit_id else None))

        pos = request.form.get('academic_position', user_profile['academic_position'] if user_profile else '')
        fy_req = request.form.get('fiscal_year_req')
        score, comp = calculate_compensation(works, pos, fy_req)
        
        info = {
            "title_name": user_profile['title_name'] if user_profile else '', "academic_position": pos,
            "position_date": user_profile['position_date'] if user_profile else '', "position_number": user_profile['position_number'] if user_profile else '',
            "department": user_profile['department'] if user_profile else '', "faculty": user_profile['faculty'] if user_profile else ''
        }

        # Save to DB
        existing = query_db('SELECT id FROM RequestRecord WHERE id = ?', (req_id,), one=True)
        status_val = STATUS_SUBMITTED if action == "submit" else STATUS_DRAFT
        if existing:
            execute_db('''
                UPDATE RequestRecord SET 
                    status = ?, total_score = ?, approved_amount = ?, applicant_info_json = ?, works_json = ?, date_submitted = ?
                WHERE id = ?
            ''', (status_val, score, comp, json.dumps(info, ensure_ascii=False), json.dumps(works, ensure_ascii=False), format_thai_date(now_dt, True), req_id))
            log_history(req_id, "ส่งคำขอ" if action == "submit" else "บันทึกแบบร่าง")
        else:
            execute_db('''
                INSERT INTO RequestRecord (id, applicant_username, applicant_name, fiscal_year, status, date_submitted, total_score, approved_amount, applicant_info_json, works_json, works_draft_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (req_id, session['username'], session['name'], fy_req, status_val, format_thai_date(now_dt, True), score, comp, json.dumps(info, ensure_ascii=False), json.dumps(works, ensure_ascii=False), json.dumps(works, ensure_ascii=False)))
            log_history(req_id, "สร้างคำขอใหม่" + (" (ส่ง)" if action == "submit" else " (แบบร่าง)"))

        if action == "submit":
            create_notification(f"มีคำขอใหม่ {req_id} จาก {session['name']}", recipient_role='administration', req_id=req_id)
            flash(f"ส่งคำขอเรียบร้อยแล้ว เลขที่คำขอ: {req_id} สถานะถัดไป: รอตรวจสอบ", "success")
        else:
            flash(f"บันทึกแบบร่างเรียบร้อยแล้ว เลขที่คำขอ: {req_id}", "success")
        return redirect(url_for('main.dashboard'))
    
    return render_template('new_request.html', name=session['name'], role=session['role'], position=session.get('position',''), criteria=criteria_list, user=user_profile, edit_req=edit_req, fiscal_year=fiscal_year, can_submit=can_submit, work_types=work_types)


@requests_bp.route('/view_request/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุกลวัฒณ์ ไกรษี 68114540629 (ตรวจสอบคำขอ)
def view_request(req_id):
    if 'username' not in session: return redirect(url_for('auth.login'))
    row = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not row:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('main.dashboard'))

    req_data = deserialize_request(row)
    if session['role'] in ['research', 'committee'] and req_data.get('draft_owner') == session['username'] and row.get('works_draft_json'):
        req_data['works'] = json.loads(row['works_draft_json'])
    
    # Recalculate score and amount for the current state (especially for draft mode)
    # calculate_compensation already imported at top of file
    s, c = recalculate_total_only(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
    req_data['score'] = s
    req_data['total_score'] = s
    req_data['approved_amount'] = c

    # Redirect drafts to edit page instead of view summary
    if req_data.get('status') == STATUS_DRAFT and session['role'] == 'applicant':
        return redirect(url_for('requests.new_request', edit_id=req_id))

    # Calculate Remaining Days for Edit/Appeal
    edit_remaining = None
    appeal_remaining = None
    if req_data.get('status') == STATUS_EDIT and req_data.get('return_date'):
        edit_remaining = get_remaining_days(req_data['return_date'])
    if req_data.get('status') in ('ไม่อนุมัติ', 'อนุมัติบางส่วน') and req_data.get('rejection_date'):
        appeal_remaining = get_remaining_days(req_data['rejection_date'])

    if request.method == 'POST':
        action = request.form.get('action')
        role = session['role']
        if role == 'applicant':
            url = handle_applicant(req_id, req_data, action, edit_remaining, appeal_remaining)
        elif role == 'administration':
            url = handle_administration(req_id, req_data, action)
        elif role == 'research' and req_data['status'] == STATUS_WAIT_HISTORY:
            url = handle_research(req_id, req_data, action)
        elif role == 'committee' and req_data['status'] in [STATUS_PENDING, STATUS_APPEAL]:
            url = handle_committee(req_id, req_data, action)
        else:
            url = url_for('requests.view_request', req_id=req_id)
        return redirect(url)

    # Fetch applicant history for duplicate checking from DB
    applicant_history = [dict(r) for r in query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND id != ?', (req_data['applicant_username'], req_id))]
    
    # Load criteria for calc
    criteria_row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (str(req_data.get('fiscal_year')),), one=True)
    if not criteria_row:
        criteria_row = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC LIMIT 1', one=True)
    criteria = parse_criteria_row(criteria_row) or {}

    # Calculate appealing_works for template
    appealing_works = [w for w in req_data['works'] if w.get('status') == 'รอการอุทธรณ์' or (session['role'] == 'committee' and w.get('appeal_comment'))]

    return render_template('view_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, history=applicant_history, edit_remaining=edit_remaining, appeal_remaining=appeal_remaining, criteria=criteria, appealing_works=appealing_works)


@requests_bp.route('/appeal/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ 68114540344 (ยื่นอุทธรณ์)
def appeal_request(req_id):
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('auth.login'))
    row = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not row:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('main.dashboard'))
    
    req_data = deserialize_request(row)
    if req_data['status'] != STATUS_REJECTED:
        flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับคำขอนี้")
        return redirect(url_for('requests.view_request', req_id=req_id))

    # Check 7 Days Limit
    appeal_remaining = None
    if row.get('rejection_date'): # This field is in JSON or we need to check decision date
        appeal_remaining = get_remaining_days(row['rejection_date'])
        if appeal_remaining < 0:
             flash("เกินกำหนดเวลาการยื่นอุทธรณ์ (7 วัน)")
             return redirect(url_for('requests.view_request', req_id=req_id))

    if request.method == 'POST':
        execute_db('UPDATE RequestRecord SET status = ? WHERE id = ?', (STATUS_APPEAL, req_id))
        create_notification(f"มีการยื่นอุทธรณ์สำหรับคำขอ {req_id}", recipient_role='committee', req_id=req_id)
        flash("ยื่นอุทธรณ์เรียบร้อยแล้ว")
        return redirect(url_for('requests.view_request', req_id=req_id))

    return render_template('appeal_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, appeal_remaining=appeal_remaining)
