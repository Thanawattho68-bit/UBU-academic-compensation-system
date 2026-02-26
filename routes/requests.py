"""
routes/requests.py
จัดการ route เกี่ยวกับการยื่นคำขอ ดูคำขอ และอุทธรณ์
ผู้รับผิดชอบ:
  - นายธนวรรธ ทองตื้อ (ผู้ยื่น/แบบฟอร์ม)
  - นายศุภวัฒน์ ไกรศา (ตรวจสอบคำขอ)
  - นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
"""

import json
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from utils import (
    load_data, load_config, save_data,
    to_thai_year, format_thai_date,
    is_within_timeline, get_remaining_days, get_current_fiscal_year,
    allowed_file, create_notification, calculate_compensation,
)

requests_bp = Blueprint('requests', __name__)


@requests_bp.route('/view_work/<req_id>/<int:work_index>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุภวัฒน์ โกรธา (ตรวจสอบคำขอ)
def view_work(req_id, work_index):
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    requests_list = load_data('requests.json')
    req = next((r for r in requests_list if r['id'] == req_id), None)
    if not req:
        return "Request not found", 404
    
    if request.method == 'POST':
        if session['role'] != 'administration':
            flash("คุณไม่มีสิทธิ์แก้ไขข้อมูลนี้")
            return redirect(url_for('requests.view_work', req_id=req_id, work_index=work_index))
        
        # Admin is updating work details
        work = req['works'][work_index]
        
        # Update details based on work type - ALLOW LEVEL UPDATES for all relevant types including custom
        if work['type'] in ['social', 'industry', 'teaching', 'policy', 'innovation'] or work['type'].startswith('custom_'):
            if 'level' in request.form:
                work['details']['level'] = request.form.get('level')
            
        # Recalculate compensation for the whole request since one work changed
        new_total_score, new_total_comp = calculate_compensation(
            req['works'], 
            req['applicant_info'].get('academic_position', ''),
            req.get('fiscal_year', '')
        )
        req['total_score'] = new_total_score
        req['total_compensation'] = new_total_comp
        
        save_data('requests.json', requests_list)
        flash("แก้ไขข้อมูลผลงานและคำนวณคะแนนใหม่เรียบร้อยแล้ว")
        return redirect(url_for('requests.view_work', req_id=req_id, work_index=work_index))

    # Get the user who submitted this request to show their profile info
    users_list = load_data('users.json')
    applicant_user = next((u for u in users_list if u['username'] == req['applicant']), None)

    # Authorization Check
    if session['role'] == 'applicant' and req['applicant'] != session['username']:
        flash("คุณไม่มีสิทธิ์เข้าถึงข้อมูลนี้")
        return redirect(url_for('main.dashboard'))
    
    return render_template('view_work.html', 
                          name=session['name'], 
                          role=session['role'], 
                          position=session.get('position', ''),
                          req=req,
                          user=applicant_user,
                          work_index=work_index)


@requests_bp.route('/new_request', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายธนวรรธ ทองตื้อ (ผู้ยื่น/แบบฟอร์ม)
def new_request():
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('auth.login'))
    from database import query_db, execute_db

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
             flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ"); return redirect(url_for('requests.new_request'))

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
        else:
            execute_db('''
                INSERT INTO RequestRecord (id, applicant_username, applicant_name, fiscal_year, status, date_submitted, total_score, approved_amount, timeline_status, applicant_info_json, works_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (req_id, session['username'], session['name'], fy_req, "ส่งแล้ว" if action == "submit" else "แบบร่าง", format_thai_date(now_dt, True), score, comp, "ontime" if can_submit else "late", json.dumps(info, ensure_ascii=False), json.dumps(works, ensure_ascii=False)))

        if action == "submit": create_notification(f"มีคำขอใหม่ {req_id} จาก {session['name']}", recipient_role='administration', req_id=req_id)
        
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('main.dashboard'))
    
    return render_template('new_request.html', name=session['name'], role=session['role'], position=session.get('position',''), criteria=criteria_list, user=user_profile, edit_req=edit_req, fiscal_year=fiscal_year, can_submit=can_submit, work_types=work_types)


@requests_bp.route('/view_request/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นายศุภวัฒน์ โกรธา (ตรวจสอบคำขอ)
def view_request(req_id):
    if 'username' not in session: return redirect(url_for('auth.login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data:
        flash("ไม่พบข้อมูลคำขอ")
        return redirect(url_for('main.dashboard'))

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
                if req_data.get('status') in ['แบบร่าง', 'ส่งแล้ว', 'แก้ไข', 'รอตรวจประวัติการยื่นขอ', 'ผลงานผ่าน', 'รอเสนอพิจารณา']:
                    req_data.update({'status': 'ยกเลิก', 'cancel_date': format_thai_date(datetime.now(), True)})
                    create_notification(f"คำขอ {req_id} ถูกยกเลิกโดยผู้ยื่น", recipient_role='administration', req_id=req_id)
                    flash("ยกเลิกคำขอเรียบร้อยแล้ว")
                else: flash("ไม่สามารถยกเลิกคำขอได้ในสถานะนี้")
                
            elif action == 'submit_appeal':
                reason, evidence = request.form.get('appeal_reason', '').strip(), request.form.get('appeal_evidence', '').strip()
                if not reason: flash("กรุณาระบุเหตุผลในการอุทธรณ์"); return redirect(url_for('requests.view_request', req_id=req_id))
                
                appealed = 0
                for w in req_data['works']:
                    if w.get('status') == 'ไม่อนุมัติ' and not w.get('already_appealed'):
                        w.update({'status': 'รอการอุทธรณ์', 'appeal_comment': reason, 'appeal_evidence': evidence, 'already_appealed': True})
                        appealed += 1
                
                if appealed > 0:
                    req_data.update({'status': 'รอการอุทธรณ์', 'appeal_date': format_thai_date(datetime.now(), True)})
                    create_notification(f"มีการยื่นอุทธรณ์คำขอ {req_id}", recipient_role='committee', req_id=req_id)
                    flash("ส่งคำอุทธรณ์เรียบร้อยแล้ว")
                else: flash("ไม่พบรายการที่สามารถยื่นอุทธรณ์ได้")
                
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
            req_data['approved_amount'] = sum(w.get('payment_calc', 0) for w in req_data['works'])

            if action == 'return':
                comment = request.form.get('comment', '').strip()
                if not comment: flash("กรุณาระบุสิ่งที่ต้องแก้ไข"); return redirect(url_for('requests.view_request', req_id=req_id))
                req_data.update({'status': 'แก้ไข', 'comment': comment, 'return_date': format_thai_date(datetime.now())})
                create_notification(f"คำขอ {req_id} ถูกส่งคืน: {comment}", recipient_username=req_data['applicant'], req_id=req_id)
            elif action == 'pass':
                req_data['status'] = 'รอตรวจประวัติการยื่นขอ'
                create_notification(f"คำขอ {req_id} รอตรวจประวัติ", recipient_role='research', req_id=req_id)
            elif action == 'mark_ready': req_data['status'] = 'รอเสนอพิจารณา'
            elif action == 'reject':
                req_data.update({'status': 'ไม่อนุมัติ', 'comment': request.form.get('comment', ''), 'rejection_date': format_thai_date(datetime.now())})
                create_notification(f"คำขอ {req_id} ไม่ผ่านการอนุมัติ", recipient_username=req_data['applicant'], req_id=req_id)
            else: # Manual Save
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
                req_data['status'] = 'ซ้ำซ้อนบางส่วน' if dups and passes else ('ผลงานซ้ำซ้อน' if dups else 'ผลงานผ่าน')
                
                s, c = calculate_compensation(req_data['works'], req_data.get('applicant_info', {}).get('academic_position', ''), req_data.get('fiscal_year'))
                req_data.update({'score': s, 'total_score': s, 'total_compensation': c, 'approved_amount': c})
                create_notification(f"ตรวจสอบผลงาน {req_id} แล้ว", recipient_role='administration', req_id=req_id)
            
            redirect_url = url_for('requests.view_request', req_id=req_id) if 'finalize' not in action else url_for('main.dashboard')

        # Committee Actions
        elif session['role'] == 'committee' and req_data['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์']:
            is_appeal = req_data['status'] == 'รอการอุทธรณ์'
            status = 'อนุมัติ' if action == 'approve' else 'ไม่อนุมัติ'
            req_data['status'] = status
            if is_appeal: req_data.setdefault('appeal', {})['status'] = status
            
            for w in req_data['works']:
                if w.get('status') == 'รอการอุทธรณ์':
                    w['status'] = status
                    w['comment'] = "ผ่านการอุทธรณ์" if status == 'อนุมัติ' else request.form.get('comment', 'ไม่อนุมัติ')

            s, c = calculate_compensation(req_data['works'], req_data.get('applicant_info', {}).get('academic_position', ''), req_data.get('fiscal_year'))
            req_data.update({'score': s, 'approved_amount': c})
            create_notification(f"คำขอ {req_id} มีผล {status}", recipient_username=req_data['applicant'], req_id=req_id)

        save_data('requests.json', all_reqs)
        return redirect(redirect_url)

    # Fetch applicant history for duplicate checking
    applicant_history = [r for r in all_reqs if r['applicant'] == req_data['applicant'] and r['id'] != req_id]
    
    # Load criteria for calc
    all_criteria = load_config('criteria.json', [])
    criteria = next((c for c in all_criteria if str(c.get('fiscal_year')) == str(req_data.get('fiscal_year'))), {})

    return render_template('view_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, history=applicant_history, edit_remaining=edit_remaining, appeal_remaining=appeal_remaining, criteria=criteria)


@requests_bp.route('/appeal/<req_id>', methods=['GET', 'POST']) # ผู้รับผิดชอบ: นางสาวเบญจมาศ จ่านันท์ (ยื่นอุทธรณ์)
def appeal_request(req_id):
    if 'username' not in session or session['role'] != 'applicant': return redirect(url_for('auth.login'))
    all_reqs = load_data('requests.json')
    req_data = next((r for r in all_reqs if r['id'] == req_id), None)
    
    if not req_data or req_data['status'] != 'ไม่อนุมัติ':
        flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับคำขอนี้")
        return redirect(url_for('requests.view_request', req_id=req_id))

    if req_data.get('appeal'):
        flash("คุณได้ยื่นอุทธรณ์สำหรับคำขอนี้ไปแล้ว")
        return redirect(url_for('requests.view_request', req_id=req_id))
        
    # Check 7 Days Limit
    appeal_remaining = None
    if 'rejection_date' in req_data:
        appeal_remaining = get_remaining_days(req_data['rejection_date'])
        if appeal_remaining < 0:
             flash("เกินกำหนดเวลาการยื่นอุทธรณ์ (7 วัน)")
             return redirect(url_for('requests.view_request', req_id=req_id))

    if request.method == 'POST':
        req_data['status'] = 'รอการอุทธรณ์'
        req_data['appeal'] = {
            "reason": request.form.get('reason'),
            "evidence": request.form.get('evidence_link'),
            "date": format_thai_date(datetime.now(), True),
            "status": "รอพิจารณา"
        }
        create_notification(f"มีการยื่นอุทธรณ์สำหรับคำขอ {req_id}", recipient_role='committee', req_id=req_id)
        save_data('requests.json', all_reqs)
        flash("ยื่นอุทธรณ์เรียบร้อยแล้ว")
        return redirect(url_for('requests.view_request', req_id=req_id))

    return render_template('appeal_request.html', name=session['name'], role=session['role'], position=session.get('position',''), req=req_data, appeal_remaining=appeal_remaining)
