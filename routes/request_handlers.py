"""
routes/request_handlers.py
แยก logic การดำเนินการของ view_request ตาม role เพื่อลดความซับซ้อน
"""

import json
import os
import shutil
from datetime import datetime
from flask import request, redirect, url_for, session, flash, current_app

from database import query_db, execute_db
from utils import (
    format_thai_date, get_remaining_days,
    create_notification, recalculate_total_only,
)
from utils.constants import (
    STATUS_DRAFT, STATUS_SUBMITTED, STATUS_EDIT, STATUS_WAIT_HISTORY,
    STATUS_WORKS_PASS, STATUS_WORKS_DUP, STATUS_DUP_PARTIAL, STATUS_WAIT_COMMITTEE,
    STATUS_PENDING, STATUS_APPEAL, STATUS_APPROVED, STATUS_REJECTED, STATUS_APPROVED_PARTIAL,
    CANCELLABLE_STATUSES, WORK_APPROVED, WORK_REJECTED, WORK_DUP, WORK_PASS, WORK_APPEAL,
)
from utils.helpers import safe_int


def log_history(req_id, action, comment=""):
    """บันทึกประวัติการดำเนินการ"""
    row = query_db('SELECT history_json FROM RequestRecord WHERE id = ?', (req_id,), one=True)
    try:
        history = json.loads(row['history_json']) if row and row.get('history_json') else []
    except (json.JSONDecodeError, TypeError):
        history = []
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


def _safe_float(val, default=None):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _apply_admin_score_edits(req_data):
    """ดึงคะแนน/ค่าตอบแทนจาก form ที่ admin แก้ แล้วอัปเดต req_data"""
    for i, work in enumerate(req_data['works']):
        for key, field in [('score_', 'score_calc'), ('comp_', 'payment_calc')]:
            if f"{key}{i}" in request.form:
                v = _safe_float(request.form.get(f"{key}{i}"))
                if v is not None:
                    work[field] = v
        if work.get('status') in [WORK_DUP, WORK_REJECTED]:
            work['payment_calc'] = 0
    req_data['score'] = sum(
        w.get('score_calc', 0) for w in req_data['works']
        if w.get('status') not in [WORK_DUP, WORK_REJECTED]
    )
    form_amount = request.form.get('amount')
    if form_amount is not None:
        try:
            req_data['approved_amount'] = float(form_amount)
        except (ValueError, TypeError):
            req_data['approved_amount'] = sum(w.get('payment_calc', 0) for w in req_data['works'])
    else:
        req_data['approved_amount'] = sum(w.get('payment_calc', 0) for w in req_data['works'])


def handle_applicant(req_id, req_data, action, edit_remaining, appeal_remaining):
    """จัดการ action ของผู้ยื่น คำขอ return redirect_url"""
    view_url = url_for('requests.view_request', req_id=req_id)

    if action == 'cancel':
        if req_data.get('status') in CANCELLABLE_STATUSES:
            execute_db('DELETE FROM RequestRecord WHERE id = ?', (req_id,))
            create_notification(f"คำขอ {req_id} ถูกลบออกจากระบบโดยผู้ยื่น",
                               recipient_role='administration', req_id=req_id)
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], req_id)
            if os.path.exists(upload_path):
                shutil.rmtree(upload_path)
            flash("ลบคำขอออกจากระบบเรียบร้อยแล้ว")
            return url_for('main.dashboard')
        flash("ไม่สามารถลบคำขอได้ในสถานะนี้")
        return view_url

    if action == 'submit_appeal':
        if appeal_remaining is not None and appeal_remaining < 0:
            flash("เกินกำหนดเวลาการยื่นอุทธรณ์ (7 วัน)")
            return view_url
        selected = request.form.getlist('appeal_items')
        if not selected:
            flash("กรุณาเลือกรายการที่ต้องการอุทธรณ์อย่างน้อย 1 รายการ")
            return view_url
        any_appealed = False
        for i in selected:
            idx = safe_int(i)
            if idx is None or idx < 0 or idx >= len(req_data['works']):
                continue
            w = req_data['works'][idx]
            if w.get('status') == WORK_REJECTED:
                w['status'] = WORK_APPEAL
                w['appeal_comment'] = request.form.get(f'appeal_reason_{idx}', '').strip()
                w['already_appealed'] = True
                any_appealed = True
        if any_appealed:
            execute_db('UPDATE RequestRecord SET status = ?, works_json = ? WHERE id = ?',
                       (STATUS_APPEAL, json.dumps(req_data['works'], ensure_ascii=False), req_id))
            log_history(req_id, "ยื่นอุทธรณ์", f"จำนวน {len(selected)} รายการ")
            create_notification(f"มีการยื่นอุทธรณ์คำขอ {req_id}", recipient_role='committee', req_id=req_id)
            flash(f"ส่งคำอุทธรณ์เรียบร้อยแล้ว คำขอ {req_id} สถานะถัดไป: กำลังพิจารณาอุทธรณ์", "success")
            return url_for('main.dashboard')
        flash("ไม่สามารถยื่นอุทธรณ์ได้สำหรับรายการที่เลือก")
        return view_url

    if action == 'submit' and req_data.get('status') in [STATUS_DRAFT, STATUS_EDIT]:
        if req_data.get('status') == STATUS_EDIT and edit_remaining is not None and edit_remaining < 0:
            flash("เกินกำหนดเวลาการส่งคืนแก้ไข (7 วัน) กรุณาติดต่อผู้ดูแลระบบ")
            return view_url
        execute_db('UPDATE RequestRecord SET status = ?, date_submitted = ? WHERE id = ?',
                   (STATUS_SUBMITTED, format_thai_date(datetime.now(), True), req_id))
        log_history(req_id, "ส่งคำขอ (Resubmit)")
        create_notification(f"คำขอ {req_id} ถูกส่งกลับมาเพื่อพิจารณาอีกครั้ง",
                           recipient_role='administration', req_id=req_id)
        flash(f"ส่งคำขอเรียบร้อยแล้ว คำขอ {req_id} จะถูกส่งตรวจสอบอีกครั้ง สถานะถัดไป: กำลังตรวจสอบคำขอ", "success")
        return url_for('main.dashboard')

    return view_url


def handle_administration(req_id, req_data, action):
    """จัดการ action ของงานบุคคล return redirect_url"""
    view_url = url_for('requests.view_request', req_id=req_id)

    _apply_admin_score_edits(req_data)

    if action == 'return':
        comment = request.form.get('comment', '').strip()
        if not comment:
            flash("กรุณาระบุสิ่งที่ต้องแก้ไข")
            return view_url
        return_dt = format_thai_date(datetime.now(), True)
        execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ?, return_date = ? WHERE id = ?',
                   (STATUS_EDIT, session['username'], return_dt, req_id))
        log_history(req_id, "ส่งคืนแก้ไข", comment)
        create_notification(f"คำขอ {req_id} ถูกส่งคืน: {comment}",
                           recipient_username=req_data['applicant_username'], req_id=req_id)
        return view_url

    if action == 'pass':
        execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ? WHERE id = ?',
                   (STATUS_WAIT_HISTORY, session['username'], req_id))
        log_history(req_id, "ส่งตรวจสอบประวัติ (งานวิจัย)")
        create_notification(f"คำขอ {req_id} รอตรวจประวัติ", recipient_role='research', req_id=req_id)
        return view_url

    if action == 'mark_ready':
        has_valid = any(w.get('status') != WORK_DUP for w in req_data['works'])
        if not has_valid:
            flash("ไม่สามารถส่งคำขอให้คณะกรรมการได้เนื่องจากผลงานทั้งหมดถูกพบว่าซ้ำซ้อน")
            return view_url
        s, c = recalculate_total_only(
            req_data['works'],
            req_data['applicant_info'].get('academic_position', ''),
            req_data.get('fiscal_year')
        )
        execute_db('''
            UPDATE RequestRecord SET status = ?, works_json = ?, total_score = ?, approved_amount = ?, admin_viewer = ?
            WHERE id = ?
        ''', (STATUS_PENDING, json.dumps(req_data['works'], ensure_ascii=False), s, c, session['username'], req_id))
        log_history(req_id, "ส่งให้คณะกรรมการพิจารณา")
        create_notification(f"คำขอ {req_id} รอการพิจารณา (ส่งรายบุคคล)", recipient_role='committee', req_id=req_id)
        flash(f"ส่งคำขอ {req_id} ให้คณะกรรมการพิจารณาเรียบร้อยแล้ว (รายการซ้ำซ้อนจะถูกซ่อนจากกรรมการแต่ยังอยู่ในระบบ)")
        return url_for('main.dashboard')

    if action == 'reject':
        reject_dt = format_thai_date(datetime.now(), True)
        execute_db('UPDATE RequestRecord SET status = ?, admin_viewer = ?, rejection_date = ? WHERE id = ?',
                   (STATUS_REJECTED, session['username'], reject_dt, req_id))
        log_history(req_id, "ไม่อนุมัติ (โดยงานบุคคล)", request.form.get('comment', ''))
        create_notification(f"คำขอ {req_id} ไม่ผ่านการอนุมัติ",
                           recipient_username=req_data['applicant_username'], req_id=req_id)
        return view_url

    # Manual Save
    execute_db('UPDATE RequestRecord SET works_json = ?, total_score = ?, approved_amount = ? WHERE id = ?',
               (json.dumps(req_data['works'], ensure_ascii=False), req_data['score'], req_data['approved_amount'], req_id))
    flash("บันทึกข้อมูลเรียบร้อยแล้ว")
    return view_url


def handle_research(req_id, req_data, action):
    """จัดการ action ของงานวิจัย return redirect_url"""
    view_url = url_for('requests.view_request', req_id=req_id)

    if 'bulk' in action:
        st = WORK_PASS if 'verify' in action else WORK_DUP
        for i in request.form.getlist('selected_works'):
            idx = safe_int(i)
            if idx is not None and 0 <= idx < len(req_data['works']):
                req_data['works'][idx]['status'] = st
    elif 'work_' in action:
        idx = safe_int(action.split('_')[-1])
        if idx is not None and 0 <= idx < len(req_data['works']):
            req_data['works'][idx]['status'] = WORK_PASS if 'verify' in action else WORK_DUP
    elif action == 'finalize_research':
        if not all(w.get('status') in [WORK_PASS, WORK_DUP] for w in req_data['works']):
            flash("กรุณาตรวจสอบให้ครบทุกรายการ")
            return view_url
        dups = any(w.get('status') == WORK_DUP for w in req_data['works'])
        passes = any(w.get('status') == WORK_PASS for w in req_data['works'])
        new_status = STATUS_WORKS_DUP if (dups and not passes) else (
            STATUS_DUP_PARTIAL if (dups and passes) else STATUS_WORKS_PASS
        )
        s, c = recalculate_total_only(
            req_data['works'],
            req_data['applicant_info'].get('academic_position', ''),
            req_data.get('fiscal_year')
        )
        execute_db('''
            UPDATE RequestRecord SET status = ?, works_json = ?, works_draft_json = ?, total_score = ?, approved_amount = ?, research_viewer = ?, draft_owner = NULL
            WHERE id = ?
        ''', (new_status, json.dumps(req_data['works'], ensure_ascii=False), json.dumps(req_data['works'], ensure_ascii=False),
             s, c, session['username'], req_id))
        log_history(req_id, "ตรวจความซ้ำซ้อนเรียบร้อย", f"ผลลัพธ์: {new_status}")
        create_notification(f"ตรวจสอบผลงาน {req_id} แล้ว กรุณาส่งพิจารณาต่อ", recipient_role='administration', req_id=req_id)
        return url_for('main.dashboard')

    if 'finalize' not in action:
        execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?',
                   (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
    return url_for('main.dashboard') if 'finalize' in action else view_url


def handle_committee(req_id, req_data, action):
    """จัดการ action ของคณะกรรมการ return redirect_url"""
    view_url = url_for('requests.view_request', req_id=req_id)

    # Individual appeal approve/reject
    if action.startswith('committee_approve_appeal_') or action.startswith('committee_reject_appeal_'):
        idx = safe_int(action.split('_')[-1])
        is_approve = 'approve' in action
        if idx is not None and 0 <= idx < len(req_data['works']):
            req_data['works'][idx]['status'] = WORK_APPROVED if is_approve else WORK_REJECTED
            dc = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
            req_data['works'][idx]['appeal_decision_comment'] = "" if is_approve else dc
            s, c = recalculate_total_only(
                req_data['works'],
                req_data['applicant_info'].get('academic_position', ''),
                req_data.get('fiscal_year')
            )
            execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?',
                       (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
            lbl = "อนุมัติอุทธรณ์" if is_approve else "ไม่อนุมัติอุทธรณ์"
            log_history(req_id, f"{lbl} (รายการที่ {idx+1})", dc)
            flash(f"ดำเนินการ{lbl}เรียบร้อยแล้ว")
        return view_url

    # Bulk approve/reject
    if action in ['committee_bulk_approve', 'committee_bulk_reject']:
        new_st = WORK_APPROVED if action == 'committee_bulk_approve' else WORK_REJECTED
        for i in request.form.getlist('selected_works'):
            idx = safe_int(i)
            if idx is None or idx < 0 or idx >= len(req_data['works']):
                continue
            w = req_data['works'][idx]
            if w.get('status') == WORK_DUP:
                continue
            w['status'] = new_st
            if new_st == WORK_REJECTED:
                pc = request.form.get(f'work_comment_{idx}', '').strip()
                if pc:
                    w['comment'] = pc
                ad = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
                if req_data['status'] == STATUS_APPEAL or w.get('appeal_comment'):
                    w['appeal_decision_comment'] = ad if ad else w.get('appeal_decision_comment', '')
            else:
                w['appeal_decision_comment'] = ""
        s, c = recalculate_total_only(
            req_data['works'],
            req_data['applicant_info'].get('academic_position', ''),
            req_data.get('fiscal_year')
        )
        execute_db('UPDATE RequestRecord SET works_draft_json = ?, draft_owner = ? WHERE id = ?',
                   (json.dumps(req_data['works'], ensure_ascii=False), session['username'], req_id))
        return view_url

    # Publish (finalize)
    if action == 'publish':
        undecided = [i + 1 for i, w in enumerate(req_data['works'])
                     if w.get('status') not in [WORK_APPROVED, WORK_REJECTED, WORK_DUP]]
        if undecided:
            flash(f"กรุณาระบุผลการพิจารณาให้ครบทุกรายการก่อนเผยแพร่ (ยังค้างรายการที่: {', '.join(map(str, undecided))})")
            return view_url
        for idx, w in enumerate(req_data['works']):
            if w.get('status') == WORK_APPROVED:
                w['appeal_decision_comment'] = ""
            elif w.get('status') == WORK_REJECTED:
                pc = request.form.get(f'work_comment_{idx}', '').strip()
                if pc:
                    w['comment'] = pc
                ad = request.form.get(f'appeal_decision_comment_{idx}', '').strip()
                if req_data['status'] == STATUS_APPEAL or w.get('appeal_comment'):
                    w['appeal_decision_comment'] = ad if ad else w.get('appeal_decision_comment', '')
        non_dup = [w for w in req_data['works'] if w.get('status') != WORK_DUP]
        total = len(non_dup)
        approved = sum(1 for w in non_dup if w.get('status') == WORK_APPROVED)
        final_status = STATUS_REJECTED
        if approved > 0:
            final_status = STATUS_APPROVED if approved == total else STATUS_APPROVED_PARTIAL
        s, c = recalculate_total_only(
            req_data['works'],
            req_data['applicant_info'].get('academic_position', ''),
            req_data.get('fiscal_year')
        )
        reject_dt = format_thai_date(datetime.now(), True) if final_status in (STATUS_REJECTED, STATUS_APPROVED_PARTIAL) else None
        execute_db('''
            UPDATE RequestRecord SET status = ?, works_json = ?, works_draft_json = ?, total_score = ?, approved_amount = ?,
                committee_approver = ?, final_approver = ?, draft_owner = NULL, rejection_date = COALESCE(?, rejection_date)
            WHERE id = ?
        ''', (final_status, json.dumps(req_data['works'], ensure_ascii=False), json.dumps(req_data['works'], ensure_ascii=False),
             s, c, session['username'], session['username'], reject_dt, req_id))
        log_history(req_id, f"เผยแพร่ผลพิจารณา: {final_status}", "")
        create_notification(f"คำขอ {req_id} ได้รับการพิจารณาแล้ว ผลคือ: {final_status}",
                           recipient_username=req_data['applicant_username'], req_id=req_id)
        flash(f"เผยแพร่ผลการพิจารณาคำขอ {req_id} เรียบร้อยแล้ว")
        return url_for('main.dashboard')

    return view_url
