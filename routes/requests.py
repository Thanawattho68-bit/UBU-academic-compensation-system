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
    
    can_submit = is_within_timeline()
    
    criteria = load_config('criteria.json', [])

    fiscal_year = get_current_fiscal_year()
    
    users = load_data('users.json')
    user_profile = next((u for u in users if u['username'] == session['username']), {})

    # Check for edit mode
    edit_id = request.args.get('edit_id')
    edit_req = None
    if edit_id:
        all_reqs = load_data('requests.json')
        edit_req = next((r for r in all_reqs if r['id'] == edit_id and r['applicant'] == session['username']), None)
    else:
        # Enforce one submission per year rule for new requests
        all_reqs = load_data('requests.json')
        current_fy = str(fiscal_year)
        existing_req = next((r for r in all_reqs if r['applicant'] == session['username'] 
                            and str(r.get('fiscal_year')) == current_fy), None)
        
        if existing_req:
            if existing_req.get('status') == 'แบบร่าง':
                # If they have a draft, redirect to it instead of blocking
                return redirect(url_for('requests.new_request', edit_id=existing_req['id']))
            else:
                flash("คุณได้ยื่นคำขอไปแล้วในปีงบประมาณนี้ สามารถยื่นได้เพียงปีละ 1 ครั้งเท่านั้น")
                return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Handle traditional form submit or checks
        if action == 'submit' and not can_submit:
             flash("ไม่อยู่ในช่วงเวลาที่เปิดรับคำขอ")
             return redirect(url_for('requests.new_request'))

        # Prepare Request Data
        # For this complex form, we expect works to be gathered via JS and sent as JSON or structured form data
        # Let's assume we handle standard form submission but parse dynamic fields
        
        # Basic Info
        req_id = request.form.get('req_id') or f"REQ-{datetime.now().strftime(f'%Y{to_thai_year(datetime.now())}%m%d%H%M%S')}"
        # Actually standard REQ ID usually uses AD or specific format. 
        # User asked "Change AD to BE system". REQ ID often keeps sortable AD YYYY. 
        # But let's use BE Year in ID as requested? "REQ-2569..." might be confusing if sorted by strict string 
        # but locally fine. Let's stick to simple YYYYMMDD... but using BE?
        # Let's adjust REQ ID to use BE year: f"REQ-{year+543}..."
        now_dt = datetime.now()
        req_id = request.form.get('req_id') or f"REQ-{now_dt.year + 543}{now_dt.strftime('%m%d%H%M%S')}"
        
        # Works Processing
        works_json = request.form.get('works_data')
        works = json.loads(works_json) if works_json else []

        # Handle File Uploads for each work
        from flask import current_app
        for w in works:
            work_id = w.get('details', {}).get('id')
            if not work_id: continue
            
            file_key = f'evidence_file_{work_id}'
            if file_key in request.files:
                file = request.files[file_key]
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create directory for this request and work
                    save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], req_id, str(work_id))
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)
                    file.save(file_path)
                    w['details']['evidence_type'] = 'file'
                    w['details']['evidence_file'] = filename
                elif w['details'].get('evidence_type') == 'file':
                    # If it was already a file and no new file uploaded, keep it
                    # (This handles the case when editing a request)
                    pass
            # If evidence_type is 'link', it will be handled by the JSON data already

        # BEFORE CALCULATION: ensure that when submitting, each work has evidence
        if action == 'submit':
            missing = False
            for w in works:
                d = w.get('details', {})
                ev_type = d.get('evidence_type')
                if ev_type == 'link':
                    if not d.get('evidence_url'):
                        missing = True
                        break
                elif ev_type == 'file':
                    if not d.get('evidence_file'):
                        missing = True
                        break
                else:
                    missing = True
                    break
            if missing:
                flash("กรุณาแนบหลักฐานให้ครบถ้วนสำหรับทุกผลงานก่อนส่ง");
                # preserve edit_id if editing
                if edit_id:
                    return redirect(url_for('requests.new_request', edit_id=edit_id))
                else:
                    return redirect(url_for('requests.new_request'))

        total_score = 0
        suggested_compensation = 0
        
        # Helper Function for Calculation was moved to global scope


        # Run Calculation
        user_position_from_form = request.form.get('academic_position', '')
        # Fallback to profile if form data is empty (unlikely with required field)
        academic_position_to_use = user_position_from_form if user_position_from_form else user_profile.get('academic_position', '')
        
        req_fy = request.form.get('fiscal_year_req')
        total_score, suggested_compensation = calculate_compensation(works, academic_position_to_use, req_fy)
        
        req_data = {
            "id": req_id,
            "applicant": session['username'],
            "applicant_name": session['name'],
            "applicant_info": {
                "title_name": user_profile.get('title_name', ''),
                "academic_position": academic_position_to_use, # Use the submitted position
                "position_date": user_profile.get('position_date', ''),
                "position_number": user_profile.get('position_number', ''),
                "department": user_profile.get('department', ''),
                "faculty": user_profile.get('faculty', '')
            },
            "fiscal_year": request.form.get('fiscal_year_req'),
            "works": works,
            "date": format_thai_date(datetime.now(), True),
            "status": "ส่งแล้ว" if action == "submit" else "แบบร่าง",
            "score": total_score, 
            "suggested_compensation": suggested_compensation,
            "comment": "",
            "timeline_status": "ontime" if can_submit else "late",
            "certify": True if request.form.get('certify') else False
        }
        
        if action == "submit":
            create_notification(f"มีคำขอใหม่ {req_id} จาก {session['name']}", recipient_role='administration', req_id=req_id)
        
        all_reqs = load_data('requests.json')
        
        # Update if exists, else append
        existing_idx = next((i for i, r in enumerate(all_reqs) if r['id'] == req_id), -1)
        if existing_idx > -1:
            # Preserve some fields if needed, or just overwrite for Draft logic
            all_reqs[existing_idx].update(req_data)
        else:
            all_reqs.append(req_data)
            
        save_data('requests.json', all_reqs)
        flash("บันทึกข้อมูลเรียบร้อยแล้ว")
        return redirect(url_for('main.dashboard'))
    
    timeline = load_config('timeline.json', {})
    work_types = load_data('work_types.json')
    return render_template('new_request.html', name=session['name'], role=session['role'], position=session.get('position',''), criteria=criteria, user=user_profile, edit_req=edit_req, fiscal_year=fiscal_year, timeline=timeline, work_types=work_types, can_submit=can_submit)


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
        
        # Applicant Actions
        if req_data['status'] in ['แบบร่าง', 'แก้ไข'] and session['role'] == 'applicant':
            # Check for Edit Expiry if status is 'แก้ไข'
            if req_data['status'] == 'แก้ไข' and req_data.get('return_date'):
                rem = get_remaining_days(req_data['return_date'])
                if rem < 0:
                     flash("เกินกำหนดเวลาการแก้ไขคำขอ (7 วัน) ไม่สามารถบันทึกหรือส่งคำขอได้")
                     return redirect(url_for('requests.view_request', req_id=req_id))

            req_data['title'] = request.form.get('title')
            req_data['category'] = request.form.get('category')
            req_data['evidence'] = request.form.get('evidence_link')
            req_data['status'] = "ส่งแล้ว" if action == "submit" else req_data['status']
            req_data['date'] = format_thai_date(datetime.now(), True)
            if action == "submit":
                create_notification(f"มีการแก้ไข/ส่งคำขอ {req_id} โดย {session['name']}", recipient_role='administration', req_id=req_id)
            save_data('requests.json', all_reqs)
            flash("อัปเดตข้อมูลเรียบร้อยแล้ว")
            return redirect(url_for('main.dashboard'))
            
        # Appeal Action (Applicant) - Single Form
        if action == 'submit_appeal' and session['role'] == 'applicant':
            appeal_reason = request.form.get('appeal_reason', '').strip()
            appeal_evidence = request.form.get('appeal_evidence', '').strip()
            
            if not appeal_reason:
                flash("กรุณาระบุเหตุผลในการอุทธรณ์")
                return redirect(url_for('requests.view_request', req_id=req_id))

            appealed_count = 0
            for w in req_data['works']:
                if w.get('status') == 'ไม่อนุมัติ' and not w.get('already_appealed'):
                    w['status'] = 'รอการอุทธรณ์'
                    w['appeal_comment'] = appeal_reason
                    w['appeal_evidence'] = appeal_evidence
                    w['already_appealed'] = True
                    appealed_count += 1
            
            if appealed_count > 0:
                req_data['status'] = 'รอการอุทธรณ์'
                req_data['appeal_date'] = format_thai_date(datetime.now(), True)
                save_data('requests.json', all_reqs)
                create_notification(f"มีการยื่นอุทธรณ์คำขอ {req_id} ({appealed_count} รายการ)", recipient_role='committee', req_id=req_id)
                flash("ส่งคำอุทธรณ์เรียบร้อยแล้ว")
            else:
                flash("ไม่พบรายการที่สามารถยื่นอุทธรณ์ได้")
            
            return redirect(url_for('requests.view_request', req_id=req_id))

        # Cancel Action (Applicant)
        if action == 'cancel' and session['role'] == 'applicant':
            allowed_to_cancel = ['แบบร่าง', 'ส่งแล้ว', 'แก้ไข', 'รอตรวจประวัติการยื่นขอ', 'ผลงานผ่าน', 'รอเสนอพิจารณา']
            if req_data.get('status') in allowed_to_cancel:
                req_data['status'] = 'ยกเลิก'
                req_data['cancel_date'] = format_thai_date(datetime.now(), True)
                save_data('requests.json', all_reqs)
                create_notification(f"คำขอ {req_id} ถูกยกเลิกโดยผู้ยื่น", recipient_role='administration', req_id=req_id)
                flash("ยกเลิกคำขอเรียบร้อยแล้ว")
                return redirect(url_for('main.dashboard'))
            else:
                flash("ไม่สามารถยกเลิกคำขอได้ในสถานะนี้")
                return redirect(url_for('requests.view_request', req_id=req_id))

        # Legacy Individual Appeal (Keep for backward compatibility if needed, or remove)
        if action and action.startswith('appeal_work_') and session['role'] == 'applicant':
            try:
                work_idx = int(action.split('_')[-1])
                if work_idx < len(req_data['works']):
                    work = req_data['works'][work_idx]
                    
                    if work.get('already_appealed'):
                        flash("ไม่สามารถยื่นอุทธรณ์ได้มากกว่า 1 ครั้งสำหรับการดำเนินงานนี้")
                        return redirect(url_for('requests.view_request', req_id=req_id))
                        
                    # Capture new fields
                    comment = request.form.get(f'appeal_comment_{work_idx}', '').strip()
                    if not comment:
                        flash("กรุณาระบุเหตุผลในการอุทธรณ์")
                        return redirect(url_for('requests.view_request', req_id=req_id))
                    
                    work['appeal_comment'] = comment
                    work['appeal_evidence'] = request.form.get(f'appeal_evidence_{work_idx}')
                    work['status'] = 'รอการอุทธรณ์'
                    work['already_appealed'] = True
                    
                    # Also set the global status to trigger visibility in the Appeals panel
                    req_data['status'] = 'รอการอุทธรณ์'
                    req_data['appeal_date'] = format_thai_date(datetime.now(), True)
                    save_data('requests.json', all_reqs)
                    create_notification(f"มีการยื่นอุทธรณ์ผลงานในคำขอ {req_id}", recipient_role='committee', req_id=req_id)
                    flash(f"ยื่นอุทธรณ์ผลงานที่ {work_idx+1} เรียบร้อยแล้ว")
                    return redirect(url_for('requests.view_request', req_id=req_id))
            except (ValueError, IndexError):
                pass

        # Appeal Decision (Committee) logic removed to use unified global buttons
        
        # Administration Actions
        elif session['role'] == 'administration' and req_data['status'] in ['ส่งแล้ว', 'ผลงานผ่าน', 'ผลงานซ้ำซ้อน', 'ซ้ำซ้อนบางส่วน', 'รอเสนอพิจารณา', 'อยู่ในรอบพิจารณา']:
            # ALWAYS Update Scores, Payments, and Total Amount if they are in the form
            new_sum = 0
            for i, work in enumerate(req_data['works']):
                # Update Score
                score_key = f"score_{i}"
                if score_key in request.form:
                    try:
                        work['score_calc'] = float(request.form.get(score_key))
                    except ValueError: pass
                
                # Update Individual Compensation
                comp_key = f"comp_{i}"
                if comp_key in request.form:
                    try:
                        val = float(request.form.get(comp_key))
                        # Force 0 if duplicate
                        if work.get('status') in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ']:
                            val = 0
                        work['payment_calc'] = val
                    except ValueError: pass
                    
                if work.get('status') not in ['ผลงานซ้ำซ้อน', 'ไม่อนุมัติ']:
                    new_sum += work.get('score_calc', 0)
            
            req_data['score'] = new_sum
            
            # Recalculate Total Amount on Backend for integrity
            calculated_total_amount = sum(work.get('payment_calc', 0) for work in req_data['works'])
            
            # Update Total Amount (Prefer form value if provided, else use calculated)
            if request.form.get('amount'):
                try:
                    req_data['approved_amount'] = float(request.form.get('amount'))
                except ValueError:
                    req_data['approved_amount'] = calculated_total_amount
            else:
                req_data['approved_amount'] = calculated_total_amount

            # Handle Actions
            if action == 'return':
                comment = request.form.get('comment', '').strip()
                if not comment:
                    flash("กรุณาระบุสิ่งที่ต้องแก้ไข ก่อนทำการส่งคืน")
                    return redirect(url_for('requests.view_request', req_id=req_id))
                    
                req_data['status'] = 'แก้ไข'
                req_data['comment'] = comment
                req_data['return_date'] = format_thai_date(datetime.now())
                create_notification(f"คำขอ {req_id} ถูกส่งคืนแก้ไข: {comment}", recipient_username=req_data['applicant'], req_id=req_id)
                save_data('requests.json', all_reqs)
                flash("ส่งคืนคำขอให้ผู้ยื่นแก้ไขแล้ว")
                return redirect(url_for('main.dashboard'))

            elif action == 'pass':
                req_data['status'] = 'รอตรวจประวัติการยื่นขอ'
                save_data('requests.json', all_reqs)
                flash("ส่งต่อให้งานวิจัยเรียบร้อยแล้ว")
                create_notification(f"คำขอ {req_id} รอตรวจประวัติการยื่นขอ", recipient_role='research', req_id=req_id)
                return redirect(url_for('main.dashboard'))

            elif action == 'mark_ready':
                req_data['status'] = 'รอเสนอพิจารณา'
                save_data('requests.json', all_reqs)
                flash("บันทึกข้อมูลและเตรียมเสนอเข้าที่ประชุมเรียบร้อยแล้ว")
                return redirect(url_for('main.dashboard'))

            elif action == 'reject':
                comment = request.form.get('comment', '').strip()
                req_data['status'] = 'ไม่อนุมัติ'
                req_data['comment'] = comment
                req_data['rejection_date'] = format_thai_date(datetime.now())
                create_notification(f"คำขอ {req_id} ไม่อนุมัติการอนุมัติ", recipient_username=req_data['applicant'], req_id=req_id)
                save_data('requests.json', all_reqs)
                flash("ปฏิเสธคำขอเรียบร้อยแล้ว")
                return redirect(url_for('main.dashboard'))

            # If it was just a manual save or fallthrough
            save_data('requests.json', all_reqs)
            flash("บันทึกข้อมูลเรียบร้อยแล้ว")
            return redirect(url_for('requests.view_request', req_id=req_id))

        # Research Actions
        elif req_data['status'] == 'รอตรวจประวัติการยื่นขอ' and session['role'] == 'research':
            if action == 'research_bulk_verify':
                selected_indices = request.form.getlist('selected_works')
                for idx_str in selected_indices:
                    try:
                        idx = int(idx_str)
                        if idx < len(req_data['works']):
                            req_data['works'][idx]['status'] = 'ผลงานผ่าน'
                    except: pass
                flash(f"ยืนยัน 'ไม่เคยใช้' ให้กับ {len(selected_indices)} รายการ")
            elif action == 'research_bulk_duplicate':
                selected_indices = request.form.getlist('selected_works')
                for idx_str in selected_indices:
                    try:
                        idx = int(idx_str)
                        if idx < len(req_data['works']):
                            req_data['works'][idx]['status'] = 'ผลงานซ้ำซ้อน'
                    except: pass
                flash(f"ระบุ 'เคยใช้แล้ว' ให้กับ {len(selected_indices)} รายการ")
            elif action and action.startswith('verify_work_'):
                idx = int(action.split('_')[-1])
                if idx < len(req_data['works']):
                    req_data['works'][idx]['status'] = 'ผลงานผ่าน'
                    flash(f"ยืนยันความถูกต้องผลงานที่ {idx+1} เรียบร้อยแล้ว")
            elif action and action.startswith('duplicate_work_'):
                idx = int(action.split('_')[-1])
                if idx < len(req_data['works']):
                    req_data['works'][idx]['status'] = 'ผลงานซ้ำซ้อน'
                    flash(f"ระบุงานซ้ำซ้อนสำหรับผลงานที่ {idx+1}")
            elif action == 'finalize_research':
                # Check if all works have been reviewed
                all_reviewed = all(w.get('status') in ['ผลงานผ่าน', 'ผลงานซ้ำซ้อน'] for w in req_data['works'])
                if not all_reviewed:
                    flash("กรุณาตรวจสอบผลงานให้ครบทุกรายการก่อนส่งผล")
                    return redirect(url_for('requests.view_request', req_id=req_id))
                
                # Determine overall status
                any_duplicate = any(w.get('status') == 'ผลงานซ้ำซ้อน' for w in req_data['works'])
                any_pass = any(w.get('status') == 'ผลงานผ่าน' for w in req_data['works'])
                
                if any_duplicate and any_pass:
                    req_data['status'] = 'ซ้ำซ้อนบางส่วน'
                    create_notification(f"พบงานซ้ำซ้อนบางส่วนในคำขอ {req_id}", recipient_role='administration', req_id=req_id)
                elif any_duplicate:
                    req_data['status'] = 'ผลงานซ้ำซ้อน'
                    create_notification(f"พบงานซ้ำซ้อนทั้งหมดในคำขอ {req_id}", recipient_role='administration', req_id=req_id)
                else:
                    req_data['status'] = 'ผลงานผ่าน'
                    create_notification(f"ตรวจสอบผลงานคำขอ {req_id} เรียบร้อยแล้ว (ถูกต้องทั้งหมด)", recipient_role='administration', req_id=req_id)
                
                # Recalculate based on new research findings (duplicate works)
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['suggested_compensation'] = new_comp
                # Also update total fields used by display components
                req_data['total_score'] = new_score
                req_data['total_compensation'] = new_comp
                req_data['approved_amount'] = new_comp
                
                save_data('requests.json', all_reqs)
                flash("ส่งผลการตรวจสอบไปยังงานบุคคลเรียบร้อยแล้ว")
                return redirect(url_for('main.dashboard'))
                
            save_data('requests.json', all_reqs)
            return redirect(url_for('requests.view_request', req_id=req_id))

        # Committee Actions
        elif req_data['status'] in ['รอการพิจารณา', 'รอการอุทธรณ์'] and session['role'] == 'committee':
            original_status = req_data['status']
            comment = request.form.get('comment', '').strip()

            if action == 'approve':
                req_data['status'] = 'อนุมัติ'
                if original_status == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'อนุมัติ'
                
                # Update individual works undergoing appeal
                for w in req_data['works']:
                    if w.get('status') == 'รอการอุทธรณ์':
                        w['status'] = 'อนุมัติ'
                        w['comment'] = "ผ่านการอุทธรณ์"

                # Recalculate based on newly approved items
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['approved_amount'] = new_comp
                
                flash("อนุมัติคำขอและผลการอุทธรณ์เรียบร้อยแล้ว")
                create_notification(f"คำขอ {req_id} ได้รับการอนุมัติแล้ว", recipient_username=req_data['applicant'], req_id=req_id)
            
            elif action == 'reject':
                req_data['status'] = 'ไม่อนุมัติ'
                req_data['comment'] = comment
                req_data['rejection_date'] = format_thai_date(datetime.now())
                
                if original_status == 'รอการอุทธรณ์':
                     if 'appeal' not in req_data: req_data['appeal'] = {}
                     req_data['appeal']['status'] = 'ไม่อนุมัติ'
                
                # Update individual works undergoing appeal
                for w in req_data['works']:
                    if w.get('status') == 'รอการอุทธรณ์':
                        w['status'] = 'ไม่อนุมัติ'
                        w['comment'] = comment or "ไม่อนุมัติ"

                # Recalculate (score will drop)
                new_score, new_comp = calculate_compensation(
                    req_data['works'], 
                    req_data.get('applicant_info', {}).get('academic_position', ''), 
                    req_data.get('fiscal_year')
                )
                req_data['score'] = new_score
                req_data['approved_amount'] = new_comp

                flash("ไม่อนุมัติคำขอรวม")
                create_notification(f"คำขอ {req_id} ถูกปฏิเสธ (ไม่อนุมัติ)", recipient_username=req_data['applicant'], req_id=req_id)
            
            save_data('requests.json', all_reqs)
            return redirect(url_for('main.dashboard'))

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
