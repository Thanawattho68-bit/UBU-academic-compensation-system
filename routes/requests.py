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
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from database import query_db, execute_db
from utils import (
    load_data, load_config, save_data,
    to_thai_year, format_thai_date,
    is_within_timeline, get_remaining_days, get_current_fiscal_year,
    allowed_file, create_notification, calculate_compensation,
)

requests_bp = Blueprint('requests', __name__)


def log_history(req_id, action, comment=""):
    """ บันทึกประวัติการดำเนินการลงใน RequestRecord """
    row = query_db('SELECT history_json FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    history = json.loads(row['history_json']) if row and row['history_json'] else []
    
    history.append({
        "timestamp": format_thai_date(datetime.now(), True),
        "user": session.get('username'),
        "name": session.get('name'),
        "role": session.get('role'),
        "action": action,
        "comment": comment
    })
    
    execute_db('UPDATE RequestRecord SET history_json = ? WHERE id = ?', 
               (json.dumps(history, ensure_ascii=False), req_id))


@requests_bp.route('/view_work/<req_id>/<int:work_index>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุกลวัฒณ์ ไกรษี 68114540629 (ตรวจสอบคำขอ)
def view_work(req_id, work_index):
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    row = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not row:
        return "Request not found", 404
    req = dict(row)
    req['works'] = json.loads(req['works_json']) if req.get('works_json') else []
    req['applicant_info'] = json.loads(req['applicant_info_json']) if req.get('applicant_info_json') else {}
    req['applicant'] = req['applicant_username'] # Compatibility
    req['date'] = req['date_submitted']
    req['score'] = req['total_score']
    
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

    can_submit = is_within_timeline()
    fiscal_year = get_current_fiscal_year()
    
    # Load Basic Info from DB
    raw_criteria = query_db('SELECT * FROM Criteria')
    criteria_list = []
    for c in raw_criteria:
        d = dict(c)
        for key in ['quality_scores', 'role_weights', 'payment_rules']:
            try: d[key] = json.loads(d[key]) if d[key] else {}
            except: d[key] = {}
        criteria_list.append(d)
        
    user_profile = dict(query_db('SELECT * FROM Account WHERE username = ?', (session['username'],), one=True) or {})
    if user_profile and user_profile.get('academic_position'):
        try:
            user_profile['academic_position'] = json.loads(user_profile['academic_position'])
            if not isinstance(user_profile['academic_position'], list):
                user_profile['academic_position'] = [user_profile['academic_position']]
        except (json.JSONDecodeError, TypeError):
            # If not a JSON list, handle as single string
            pass

    work_types = [dict(wt) for wt in query_db('SELECT * FROM WorkType')]

    # Check for edit mode
    edit_id = request.args.get('edit_id')
    edit_req = None
    if edit_id:
        row = query_db('SELECT * FROM RequestRecord WHERE id = ? AND applicant_username = ?', (edit_id, session['username']), one=True)
        if row:
            edit_req = dict(row)
            edit_req['applicant'] = edit_req['applicant_username'] # Compatibility
            edit_req['works'] = json.loads(edit_req['works_json']) if edit_req['works_json'] else []
            edit_req['applicant_info'] = json.loads(edit_req['applicant_info_json']) if edit_req['applicant_info_json'] else {}
    else:
        # Enforce one submission per year rule
        existing_req = query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND fiscal_year = ?', (session['username'], str(fiscal_year)), one=True)
        if existing_req:
            if existing_req['status'] == 'แบบร่าง':
                return redirect(url_for('requests.new_request', edit_id=existing_req['id']))
            else:
                flash("คุณได้ยื่นคำขอไปแล้วในปีงบประมาณนี้")
                return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        action, now_dt = request.form.get('action'), datetime.now()
        if action == 'submit' and not can_submit:
             # Check if this is a resubmission of a returned request
             is_resubmission = False
             if edit_req and edit_req.get('status') == 'แก้ไข':
                 is_resubmission = True
             
             if not is_resubmission:
                 flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
                 return redirect(url_for('requests.new_request', edit_id=edit_id))

        req_id = request.form.get('req_id') or f"REQ-{now_dt.year + 543}{now_dt.strftime('%m%d%H%M%S')}"
        works = json.loads(request.form.get('works_data', '[]'))

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
        if existing:
            execute_db('''
                UPDATE RequestRecord SET 
                    status = ?, total_score = ?, approved_amount = ?, applicant_info_json = ?, works_json = ?, date_submitted = ?
                WHERE id = ?
            ''', ("ส่งแล้ว" if action == "submit" else "แบบร่าง", score, comp, json.dumps(info, ensure_ascii=False), json.dumps(works, ensure_ascii=False), format_thai_date(now_dt, True), req_id))
            log_history(req_id, "ส่งคำขอ" if action == "submit" else "บันทึกแบบร่าง")
        else:
            execute_db('''
                INSERT INTO RequestRecord (id, applicant_username, applicant_name, fiscal_year, status, date_submitted, total_score, approved_amount, applicant_info_json, works_json, works_draft_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (req_id, session['username'], session['name'], fy_req, "ส่งแล้ว" if action == "submit" else "แบบร่าง", format_thai_date(now_dt, True), score, comp, json.dumps(info, ensure_ascii=False), json.dumps(works, ensure_ascii=False), json.dumps(works, ensure_ascii=False)))
            log_history(req_id, "สร้างคำขอใหม่" + (" (ส่ง)" if action == "submit" else " (แบบร่าง)"))

        if action == "submit": create_notification(f"มีคำขอใหม่ {req_id} จาก {session['name']}", recipient_role='administration', req_id=req_id)
        
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('main.dashboard'))
    
    return render_template('new_request.html', name=session['name'], role=session['role'], position=session.get('position',''), criteria=criteria_list, user=user_profile, edit_req=edit_req, fiscal_year=fiscal_year, can_submit=can_submit, work_types=work_types)


@requests_bp.route('/view_request/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุกลวัฒณ์ ไกรษี 68114540629 (ตรวจสอบคำขอ)
def view_request(req_id):
    if 'username' not in session: return redirect(url_for('auth.login'))
    row = query_db('SELECT * FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    if not row:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('main.dashboard'))
    
    req_data = dict(row)
    
    # Draft Ownership Logic
    if session['role'] in ['research', 'committee']:
        # If I am the owner of the draft, show me my draft.
        if req_data.get('draft_owner') == session['username']:
            req_data['works'] = json.loads(req_data['works_draft_json']) if req_data.get('works_draft_json') else json.loads(req_data['works_json'])
        else:
            # If I'm NOT the owner, I see the "base" official version.
            req_data['works'] = json.loads(req_data['works_json'])
    else:
        req_data['works'] = json.loads(req_data['works_json']) if req_data.get('works_json') else []

    req_data['applicant_info'] = json.loads(req_data['applicant_info_json']) if req_data.get('applicant_info_json') else {}
    req_data['audit_trail'] = json.loads(req_data['history_json']) if req_data.get('history_json') else []
    req_data['applicant'] = req_data['applicant_username'] # Compatibility
    req_data['date'] = req_data['date_submitted']
    
    # Recalculate score and amount for the current state (especially for draft mode)
    from utils import calculate_compensation
    s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
    req_data['score'] = s
    req_data['total_score'] = s
    req_data['approved_amount'] = c

    # Redirect drafts to edit page instead of view summary
    if req_data.get('status') == 'แบบร่าง' and session['role'] == 'applicant':
        return redirect(url_for('requests.new_request', edit_id=req_id))
    
    # Calculate Remaining Days for Edit/Appeal
    edit_remaining = None
    appeal_remaining = None
    
    if req_data.get('status') == 'แก้ไข' and req_data.get('return_date'):
        edit_remaining = get_remaining_days(req_data['return_date'])
        
    if req_data.get('status') == 'ไม่อนุมัติ' and req_data.get('rejection_date'):
        appeal_remaining = get_remaining_days(req_data['rejection_date'])

    if request.method == 'POST':
        action = request.form.get('action')
        redirect_url = url_for('main.dashboard')
        
        # Applicant Actions
        if session['role'] == 'applicant':
            if action == 'cancel':
                if req_data.get('status') in ['แบบร่าง', 'ส่งแล้ว', 'แก้ไข', 'รอตรวจประวัติการยื่นขอ', 'ผลงานผ่าน', 'รอเสนอพิจารณา', 'รอการพิจารณา']:
                    # ลบข้อมูลออกจากฐานข้อมูลตามคำขอของผู้ใช้
                    execute_db('DELETE FROM RequestRecord WHERE id = ?', (req_id,))
                    
                    # แจ้งเตือนแอดมินเกี่ยวกับการลบคำขอ
                    create_notification(f"คำขอ {req_id} ถูกลบออกจากระบบโดยผู้ยื่น", recipient_role='administration', req_id=req_id)
                    
                    # ลบไฟล์แนบที่อัปโหลดไว้ (ถ้ามี) เพื่อประหยัดพื้นที่
                    import shutil
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], req_id)
                    if os.path.exists(upload_path):
                        shutil.rmtree(upload_path)
                        
                    flash("ลบคำขอออกจากระบบเรียบร้อยแล้ว")
                else:
                    flash("ไม่สามารถลบคำขอได้ในสถานะนี้")
                
            elif action == 'submit_appeal':
                selected_for_appeal = request.form.getlist('appeal_items')
                if not selected_for_appeal:
                    flash("กรุณาเลือกรายการที่ต้องการอุทธรณ์อย่างน้อย 1 รายการ")
                    return redirect(url_for('requests.view_request', req_id=req_id))

                any_appealed = False
                for i in selected_for_appeal:
                    idx = int(i)
                    if idx < len(req_data['works']) and req_data['works'][idx].get('status') == 'ไม่อนุมัติ':
                        req_data['works'][idx]['status'] = 'รอการอุทธรณ์'
                        req_data['works'][idx]['appeal_comment'] = request.form.get(f'appeal_reason_{idx}', '').strip()
                        req_data['works'][idx]['already_appealed'] = True
                        any_appealed = True
                
                if any_appealed:
                    execute_db('UPDATE RequestRecord SET status = ?, works_json = ? WHERE id = ?', ('รอการอุทธรณ์', json.dumps(req_data['works'], ensure_ascii=False), req_id))
                    log_history(req_id, "ยื่นอุทธรณ์", f"จำนวน {len(selected_for_appeal)} รายการ")
                    create_notification(f"มีการยื่นอุทธรณ์คำขอ {req_id}", recipient_role='committee', req_id=req_id)
                    flash("ส่งคำอุทธรณ์เรียบร้อยแล้ว")
                else: flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับรายการที่เลือก")
            
            elif action == 'submit' and req_data.get('status') in ['แบบร่าง', 'แก้ไข']:
                 execute_db('UPDATE RequestRecord SET status = ?, date_submitted = ? WHERE id = ?', ('ส่งแล้ว', format_thai_date(datetime.now(), True), req_id))
                 log_history(req_id, "ส่งคำขอ (Resubmit)")
                 create_notification(f"คำขอ {req_id} ถูกส่งกลับมาเพื่อพิจารณาอีกครั้ง", recipient_role='administration', req_id=req_id)
                 flash("ส่งคำขอเรียบร้อยแล้ว")
                
        # Administration Actions
        elif session['role'] == 'administration':
            new_sum = 0
            for i, work in enumerate(req_data['works']):
                for key, field in [('score_', 'score_calc'), ('comp_', 'payment_calc')]:
                    if f"{key}{i}" in request.form:
                        try: work[field] = float(request.form.get(f"{key}{i}"))
                        except: pass
                if work.get('status') in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ']: work['payment_calc'] = 0
                new_sum += work.get('score_calc', 0) if work.get('status') not in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ'] else 0
            
            req_data['score'] = new_sum
            # Try to get amount from form (calculated by JS), otherwise fallback to current value
            form_amount = request.form.get('amount')
            if form_amount is not None:
                try: req_data['approved_amount'] = float(form_amount)
                except: req_data['approved_amount'] = sum(w.get('payment_calc', 0) for w in req_data['works'])
            else:
                req_data['approved_amount'] = sum(w.get('payment_calc', 0) for w in req_data['works'])

            if action == 'return':
                comment = request.form.get('comment', '').strip()
                if not comment: flash("กรุณาระบุสิ่งที่ต้องแก้ไข"); return redirect(url_for('requests.view_request', req_id=req_id))
                execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ? WHERE id = ?', 
                           ('แก้ไข', session['username'], req_id))
                log_history(req_id, "ส่งคืนแก้ไข", comment)
                create_notification(f"คำขอ {req_id} ถูกส่งคืน: {comment}", recipient_username=req_data['applicant_username'], req_id=req_id)
            elif action == 'pass':
                execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ? WHERE id = ?', 
                           ('รอตรวจประวัติการยื่นขอ', session['username'], req_id))
                log_history(req_id, "ส่งตรวจสอบประวัติ (งานวิจัย)")
                create_notification(f"คำขอ {req_id} รอตรวจประวัติ", recipient_role='research', req_id=req_id)
            elif action == 'mark_ready':
                # Preserve all works for history/display but committee will still see them filtered in UI
                # Check if there are any non-duplicate works to send.
                has_valid_works = any(w.get('status') != 'ผลงานซ้ำซ้อน' for w in req_data['works'])
                
                if not has_valid_works:
                    flash("ไม่สามารถส่งคำขอให้คณะกรรมการได้เนื่องจากผลงานทั้งหมดถูกพบว่าซ้ำซ้อน")
                    return redirect(url_for('requests.view_request', req_id=req_id))

                # Recalculate compensation for final submission to committee
                s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
                
                execute_db('''
                    UPDATE RequestRecord 
                    SET status = ?, works_json = ?, total_score = ?, approved_amount = ?, admin_viewer = ?
                    WHERE id = ?
                ''', ('รอการพิจารณา', json.dumps(req_data['works'], ensure_ascii=False), s, c, session['username'], req_id))
                log_history(req_id, "ส่งให้คณะกรรมการพิจารณา")
                create_notification(f"คำขอ {req_id} รอการพิจารณา (ส่งรายบุคคล)", recipient_role='committee', req_id=req_id)
                flash(f"ส่งคำขอ {req_id} ให้คณะกรรมการพิจารณาเรียบร้อยแล้ว (รายการซ้ำซ้อนจะถูกซ่อนจากกรรมการแต่ยังอยู่ในระบบ)")
                redirect_url = url_for('main.dashboard')
            elif action == 'reject':
                execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ? WHERE id = ?', 
                           ('ไม่อนุมัติ', session['username'], req_id))
                log_history(req_id, "ไม่อนุมัติ (โดยงานบุคคล)", request.form.get('comment', ''))
                create_notification(f"คำขอ {req_id} ไม่ผ่านการอนุมัติ", recipient_username=req_data['applicant_username'], req_id=req_id)
            else: # Manual Save
                execute_db('UPDATE RequestRecord SET works_json = ?, total_score = ?, approved_amount = ? WHERE id = ?', 
                          (json.dumps(req_data['works'], ensure_ascii=False), req_data['score'], req_data['approved_amount'], req_id))
                flash("บันทึกข้อมูลเรียบร้อยแล้ว")
                redirect_url = url_for('requests.view_request', req_id=req_id)

        # Research Actions
        elif session['role'] == 'research' and req_data['status'] == 'รอตรวจประวัติการยื่นขอ':
            if 'bulk' in action:
                status = 'ผลงานผ่าน' if 'verify' in action else 'ผลงานซ้ำซ้อน'
                for idx in map(int, request.form.getlist('selected_works')):
                    if idx < len(req_data['works']): req_data['works'][idx]['status'] = status
            elif 'work_' in action:
                idx = int(action.split('_')[-1])
                req_data['works'][idx]['status'] = 'ผลงานผ่าน' if 'verify' in action else 'ผลงานซ้ำซ้อน'
            elif action == 'finalize_research':
                if not all(w.get('status') in ['ผลงานผ่าน', 'ผลงานซ้ำซ้อน'] for w in req_data['works']):
                    flash("กรุณาตรวจสอบให้ครบทุกรายการ"); return redirect(url_for('requests.view_request', req_id=req_id))
                
                dups = any(w.get('status') == 'ผลงานซ้ำซ้อน' for w in req_data['works'])
                passes = any(w.get('status') == 'ผลงานผ่าน' for w in req_data['works'])
                
                # If everything is duplicate, it's just 'ผลงานซ้ำซ้อน'
                if dups and not passes:
                    new_status = 'ผลงานซ้ำซ้อน'
                elif dups and passes:
                    new_status = 'ซ้ำซ้อนบางส่วน'
                else:
                    new_status = 'ผลงานผ่าน'
                
                s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
                # Clear draft ownership when research is finalized
                execute_db('''
                    UPDATE RequestRecord SET status = ?, works_json = ?, works_draft_json = ?, total_score = ?, approved_amount = ?, research_viewer = ?, draft_owner = NULL 
                    WHERE id = ?
                ''', (new_status, json.dumps(req_data['works'], ensure_ascii=False), json.dumps(req_data['works'], ensure_ascii=False), s, c, session['username'], req_id))
                log_history(req_id, "ตรวจความซ้ำซ้อนเรียบร้อย", f"ผลลัพธ์: {new_status}")
                create_notification(f"ตรวจสอบผลงาน {req_id} แล้ว กรุณาส่งพิจารณาต่อ", recipient_role='administration', req_id=req_id)
            
            if 'finalize' not in action:
                execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?', (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
            redirect_url = url_for('requests.view_request', req_id=req_id) if 'finalize' not in action else url_for('main.dashboard')

        # Committee Actions (Individual Processing via Publish button or Bulk buttons)
        elif session['role'] == 'committee' and req_data['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์']:
            # Handle Individual Appeal Actions
            if action.startswith('committee_approve_appeal_') or action.startswith('committee_reject_appeal_'):
                idx = int(action.split('_')[-1])
                is_approve = 'approve' in action
                
                if idx < len(req_data['works']):
                    new_status = 'อนุมัติ' if is_approve else 'ไม่อนุมัติ'
                    req_data['works'][idx]['status'] = new_status
                    
                    # Store decision comment
                    decision_comment = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
                    if is_approve:
                        # Clear comments/appeals if approved
                        req_data['works'][idx]['comment'] = ""
                        req_data['works'][idx]['appeal_decision_comment'] = ""
                    else:
                        # Store as dedicated appeal decision comment
                        if decision_comment:
                            req_data['works'][idx]['appeal_decision_comment'] = decision_comment
                        else:
                            req_data['works'][idx]['appeal_decision_comment'] = "ไม่รับอุทธรณ์"
                    
                    s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
                    execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?', (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
                    
                    action_label = "อนุมัติอุทธรณ์" if is_approve else "ไม่อนุมัติอุทธรณ์"
                    log_history(req_id, f"{action_label} (รายการที่ {idx+1})", decision_comment)
                    flash(f"ดำเนินการ{action_label}เรียบร้อยแล้ว")
                    return redirect(url_for('requests.view_request', req_id=req_id))


            # Handle Bulk Actions (Updates work status but stays on page)
            if action in ['committee_bulk_approve', 'committee_bulk_reject']:
                selected_indices = request.form.getlist('selected_works')
                new_status = 'อนุมัติ' if action == 'committee_bulk_approve' else 'ไม่อนุมัติ'
                
                for i in selected_indices:
                    idx = int(i)
                    if idx < len(req_data['works']) and req_data['works'][idx].get('status') != 'ผลงานซ้ำซ้อน':
                        req_data['works'][idx]['status'] = new_status
                        # Per-item comment
                        per_item_comment = request.form.get(f'work_comment_{idx}', '').strip()
                        appeal_decision = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
                        if new_status == 'ไม่อนุมัติ':
                            if per_item_comment:
                                req_data['works'][idx]['comment'] = per_item_comment
                            if req_data['status'] == 'รอการอุทธรณ์' or req_data['works'][idx].get('appeal_comment'):
                                if appeal_decision:
                                    req_data['works'][idx]['appeal_decision_comment'] = appeal_decision
                                elif not req_data['works'][idx].get('appeal_decision_comment'):
                                    req_data['works'][idx]['appeal_decision_comment'] = "ไม่รับอุทธรณ์"
                        else:
                            # Clear comments if approved
                            req_data['works'][idx]['comment'] = ""
                            req_data['works'][idx]['appeal_decision_comment'] = ""
                
                # Just save the works state and stay (DRAFT only, owned by current user)
                s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
                execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?', (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
                return redirect(url_for('requests.view_request', req_id=req_id))


            # Handle Final Publication (Calculates total and finishes request)
            elif action == 'publish':
                # No longer rely on selected_works for approval.
                # All items must have a definitive status (Approve/Reject) or be Duplicate already.
                undecided_indices = [i + 1 for i, w in enumerate(req_data['works']) if w.get('status') not in ['อนุมัติ', 'ไม่อนุมัติ', 'ผลงานซ้ำซ้อน']]
                
                if undecided_indices:
                    flash(f"กรุณาระบุผลการพิจารณาให้ครบทุกรายการก่อนเผยแพร่ (ยังค้างรายการที่: {', '.join(map(str, undecided_indices))})")
                    return redirect(url_for('requests.view_request', req_id=req_id))

                any_approved = False
                for idx, w in enumerate(req_data['works']):
                    if w.get('status') == 'อนุมัติ':
                        any_approved = True
                        w['comment'] = "" # Ensure approved items have no rejection comments
                    elif w.get('status') == 'ไม่อนุมัติ':
                        # Try to get per-item comment
                        per_item_comment = request.form.get(f'work_comment_{idx}', '').strip()
                        appeal_decision = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
                        if per_item_comment:
                            w['comment'] = per_item_comment
                        
                        if req_data['status'] == 'รอการอุทธรณ์' or w.get('appeal_comment'):
                            if appeal_decision:
                                w['appeal_decision_comment'] = appeal_decision
                            elif not w.get('appeal_decision_comment'):
                                w['appeal_decision_comment'] = "ไม่รับอุทธรณ์"

                # Overall request status
                non_duplicate_works = [w for w in req_data['works'] if w.get('status') != 'ผลงานซ้ำซ้อน']
                total_to_consider = len(non_duplicate_works)
                approved_count = sum(1 for w in non_duplicate_works if w.get('status') == 'อนุมัติ')
                
                final_status = 'ไม่อนุมัติ'
                if approved_count > 0:
                    if approved_count == total_to_consider:
                        final_status = 'อนุมัติ'
                    else:
                        final_status = 'อนุมัติบางส่วน'
                
                s, c = calculate_compensation(req_data['works'], req_data['applicant_info'].get('academic_position', ''), req_data.get('fiscal_year'))
                
                execute_db('''
                    UPDATE RequestRecord SET status = ?, works_json = ?, works_draft_json = ?, total_score = ?, approved_amount = ?, committee_approver = ?, final_approver = ?, draft_owner = NULL
                    WHERE id = ?
                ''', (final_status, json.dumps(req_data['works'], ensure_ascii=False), json.dumps(req_data['works'], ensure_ascii=False), s, c, session['username'], session['username'], req_id))
                
                log_history(req_id, f"เผยแพร่ผลพิจารณา: {final_status}", "")
                create_notification(f"คำขอ {req_id} ได้รับการพิจารณาแล้ว ผลคือ: {final_status}", recipient_username=req_data['applicant_username'], req_id=req_id)
                flash(f"เผยแพร่ผลการพิจารณาคำขอ {req_id} เรียบร้อยแล้ว")
                return redirect(url_for('main.dashboard'))
            else:
                return redirect(url_for('requests.view_request', req_id=req_id))

        return redirect(redirect_url)

    # Fetch applicant history for duplicate checking from DB
    applicant_history = [dict(r) for r in query_db('SELECT * FROM RequestRecord WHERE applicant_username = ? AND id != ?', (req_data['applicant_username'], req_id))]
    
    # Load criteria for calc
    criteria_row = query_db('SELECT * FROM Criteria WHERE fiscal_year = ?', (str(req_data.get('fiscal_year')),), one=True)
    if not criteria_row: criteria_row = query_db('SELECT * FROM Criteria ORDER BY fiscal_year DESC LIMIT 1', one=True)
    criteria = dict(criteria_row) if criteria_row else {}
    if criteria.get('payment_rules'): criteria['payment_rules'] = json.loads(criteria['payment_rules'])

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
    
    req_data = dict(row)
    req_data['works'] = json.loads(req_data['works_json']) if req_data.get('works_json') else []
    
    if req_data['status'] != 'ไม่อนุมัติ':
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
        execute_db('UPDATE RequestRecord SET status = ? WHERE id = ?', ('รอการอุทธรณ์', req_id))
        create_notification(f"มีการยื่นอุทธรณ์สำหรับคำขอ {req_id}", recipient_role='committee', req_id=req_id)
        flash("ยื่นอุทธรณ์เรียบร้อยแล้ว")
        return redirect(url_for('requests.view_request', req_id=req_id))

    return render_template('appeal_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, appeal_remaining=appeal_remaining)
